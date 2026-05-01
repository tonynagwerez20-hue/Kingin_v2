//+------------------------------------------------------------------+
//|                                                         yxyx.mq5 |
//|                                                      dark kingin |
//|                                             https://www.mql5.com |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property link      "https://www.mql5.com"
#property version   "1.04"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//---- INPUT PARAMETERS
input int    LookbackBars           = 12;     // Lookback bars to find swings/range (short for HFT)
input int    TrendLookbackBars      = 20;     // Lookback bars to determine trend
input int    ATR_Period             = 14;     // ATR period for volatility calculation
input double SL_ATR_Multiplier      = 1.2;    // Stop loss multiplier based on ATR
input double TP_ATR_Multiplier      = 2.0;    // Take profit multiplier based on ATR
input double Trail_ATR_Multiplier   = 0.8;    // Trailing stop multiplier based on ATR
input double RiskPerTradePercent    = 0.1;    // Percentage of equity risked per trade
input double MaxDailyLossPercent    = 1.5;    // Maximum daily loss percentage before locking trading
input int    ExpireMinutes          = 30;     // Pending order expiry in minutes
input double SR_PctTolerance        = 0.5;    // Percentage tolerance for support/resistance levels
input ulong  MagicNumber            = 112233; // Unique magic number for orders/positions
input string CommentTag             = "HFT_Flow"; // Comment for orders

//---- GLOBAL VARIABLES
datetime lastBarTime = 0;           // Timestamp of the last processed bar
double startEquityToday = 0.0;      // Equity at the start of the trading day
bool tradingLocked = false;         // Flag to lock trading if daily loss limit is reached
int atrHandle = INVALID_HANDLE;     // Handle for ATR indicator

//---- ENUMERATIONS
enum ETREND
{
    TREND_BULL = 1,  // Bullish trend
    TREND_BEAR = -1, // Bearish trend
    TREND_SIDE = 0   // Sideways/no clear trend
};

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // Validate input parameters
    if (LookbackBars <= 0 || TrendLookbackBars <= 0 || ATR_Period <= 0 ||
        SL_ATR_Multiplier <= 0 || TP_ATR_Multiplier <= 0 || Trail_ATR_Multiplier < 0 ||
        RiskPerTradePercent <= 0 || MaxDailyLossPercent <= 0 || ExpireMinutes <= 0 ||
        SR_PctTolerance < 0)
    {
        Print("Error: Invalid input parameters. All values must be positive.");
        return INIT_PARAMETERS_INCORRECT;
    }

    // Initialize ATR indicator handle
    atrHandle = iATR(_Symbol, _Period, ATR_Period);
    if (atrHandle == INVALID_HANDLE)
    {
        PrintFormat("Error: Failed to create ATR indicator handle. Error code: %d", GetLastError());
        return INIT_FAILED;
    }

    // Reset daily tracking
    ResetDaily();

    Print("GABZY PRIME initialized successfully.");
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Release ATR indicator handle
    if (atrHandle != INVALID_HANDLE)
    {
        if (!IndicatorRelease(atrHandle))
        {
            PrintFormat("Warning: Failed to release ATR handle. Error code: %d", GetLastError());
        }
        atrHandle = INVALID_HANDLE;
    }

    Print("GABZY PRIME deinitialized.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Perform daily reset if necessary
    if (!PerformDailyReset())
        return;

    // Skip if trading is locked
    if (tradingLocked)
        return;

    // Process only on new bar close
    if (!IsNewBarClosed())
        return;

    // Retrieve and validate market data
    double atrValue = 0.0;
    double bid = 0.0, ask = 0.0;
    if (!GetMarketData(atrValue, bid, ask))
        return;

    // Determine trend
    ETREND trend = DetermineTrend(TrendLookbackBars);
    if (trend == TREND_SIDE && !IsBreakoutCondition())
        return; // No action in sideways without breakout

    // Calculate swing and range levels
    double swingHigh = GetSwingHigh(LookbackBars);
    double swingLow = GetSwingLow(LookbackBars);
    double rangeHigh = GetRangeHigh(LookbackBars);
    double rangeLow = GetRangeLow(LookbackBars);

    // Compute order levels
    double sellEntry = NormalizeDouble(swingHigh, _Digits);
    double buyEntry = NormalizeDouble(swingLow, _Digits);
    double sellSL = NormalizeDouble(sellEntry + SL_ATR_Multiplier * atrValue, _Digits);
    double sellTP = NormalizeDouble(sellEntry - TP_ATR_Multiplier * atrValue, _Digits);
    double buySL = NormalizeDouble(buyEntry - SL_ATR_Multiplier * atrValue, _Digits);
    double buyTP = NormalizeDouble(buyEntry + TP_ATR_Multiplier * atrValue, _Digits);

    // Calculate position size
    double lotSize = CalcLotByRisk(RiskPerTradePercent, SL_ATR_Multiplier * atrValue);
    if (lotSize <= 0)
    {
        Print("Warning: Invalid lot size calculated. Skipping trade.");
        return;
    }

    // Check for entry conditions
    ExecuteTrades(trend, bid, ask, swingLow, swingHigh, rangeHigh, rangeLow, buyEntry, sellEntry,
                  buySL, buyTP, sellSL, sellTP, lotSize);

    // Manage open positions
    ManagePositions(swingHigh, swingLow, atrValue);
}

//+------------------------------------------------------------------+
//| Perform daily reset if a new day has started                     |
//+------------------------------------------------------------------+
bool PerformDailyReset()
{
   static int lastDate = 0;  // Stores the last processed date as YYYYMMDD (0 = uninitialized)
    
    // Get current server time
    datetime currentTime = TimeCurrent();
    if (currentTime == 0)
    {
        Print("Error: Unable to retrieve current time. Skipping daily reset check.");
        return false;  // Prevent further processing if time is invalid
    }
    
    // Convert time to struct for component extraction
    MqlDateTime dt;
    if (!TimeToStruct(currentTime, dt))
    {
        Print("Error: Failed to convert time to struct. Skipping daily reset check.");
        return false;
    }
    
    // Compute unique date identifier (YYYYMMDD) using struct components
    int currentDate = dt.year * 10000 + dt.mon * 100 + dt.day;
    
    // Validate date components (basic sanity check)
    if (dt.day < 1 || dt.day > 31 || dt.mon < 1 || dt.mon > 12 || dt.year < 2000)  // Assuming EA runs post-2000
    {
        PrintFormat("Warning: Invalid date components detected (Date: %d). Skipping reset.", currentDate);
        return false;
    }
    
    // Check if it's a new day
    if (currentDate != lastDate)
    {
        // Perform daily reset
        ResetDaily();
        lastDate = currentDate;
        
        PrintFormat("Daily reset performed for date: %d", currentDate);
        return true;  // Reset successful, continue processing
    }
     
    return true; // Continue even if not reset
}

//+------------------------------------------------------------------+
//| Check if a new bar has closed                                     |
//+------------------------------------------------------------------+
bool IsNewBarClosed()
{
    int barsNeeded = MathMax(LookbackBars, TrendLookbackBars) + 5;
    MqlRates rates[];
    if (CopyRates(_Symbol, _Period, 0, barsNeeded, rates) <= 0)
    {
        PrintFormat("Error: Failed to copy rates. Error code: %d", GetLastError());
        return false;
    }
    if (ArraySize(rates) < 2)
        return false;

    datetime closedBarTime = rates[1].time;
    if (closedBarTime == lastBarTime)
        return false;

    lastBarTime = closedBarTime;
    return true;
}

//+------------------------------------------------------------------+
//| Retrieve and validate market data (ATR, bid, ask)                |
//+------------------------------------------------------------------+
bool GetMarketData(double &atrValue, double &bid, double &ask)
{
    // Get ATR value
    if (atrHandle == INVALID_HANDLE)
        return false;

    double atrBuffer[];
    if (CopyBuffer(atrHandle, 0, 0, 2, atrBuffer) <= 0 || ArraySize(atrBuffer) < 1)
    {
        PrintFormat("Error: Failed to copy ATR buffer. Error code: %d", GetLastError());
        return false;
    }
    atrValue = atrBuffer[0];
    if (atrValue <= 0)
    {
        Print("Warning: Invalid ATR value (<= 0). Skipping tick.");
        return false;
    }

    // Get bid/ask prices
    bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    if (bid <= 0 || ask <= 0)
    {
        Print("Warning: Invalid bid/ask prices. Skipping tick.");
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| Determine market trend based on price movements                  |
//+------------------------------------------------------------------+
ETREND DetermineTrend(int bars)
{
    if (bars < 3)
        bars = 3;

    MqlRates rates[];
    if (CopyRates(_Symbol, _Period, 1, bars + 1, rates) <= 0)
        return TREND_SIDE;

    int available = ArraySize(rates);
    if (available < 3)
        return TREND_SIDE;

    int increases = 0, decreases = 0;
    for (int i = available - 1; i > 0; i--)
    {
        int j = i - 1;
        if (rates[j].high > rates[i].high && rates[j].low > rates[i].low)
            increases++;
        else if (rates[j].high < rates[i].high && rates[j].low < rates[i].low)
            decreases++;
    }

    int needed = available - 1;
    if (increases >= needed - 1)
        return TREND_BULL;
    if (decreases >= needed - 1)
        return TREND_BEAR;
    return TREND_SIDE;
}

//+------------------------------------------------------------------+
//| Check for breakout conditions in sideways trend                   |
//+------------------------------------------------------------------+
bool IsBreakoutCondition()
{
    // This is a placeholder; original logic checks breakout in ExecuteTrades
    return true; // Allow breakout checks in ExecuteTrades
}

//+------------------------------------------------------------------+
//| Get the highest high in the lookback period                       |
//+------------------------------------------------------------------+
double GetSwingHigh(int lookback)
{
    if (lookback <= 0)
        return 0.0;

    double highs[];
    if (CopyHigh(_Symbol, _Period, 1, lookback, highs) <= 0 || ArraySize(highs) == 0)
        return 0.0;

    return highs[ArrayMaximum(highs, 0, ArraySize(highs))];
}

//+------------------------------------------------------------------+
//| Get the lowest low in the lookback period                         |
//+------------------------------------------------------------------+
double GetSwingLow(int lookback)
{
    if (lookback <= 0)
        return 0.0;

    double lows[];
    if (CopyLow(_Symbol, _Period, 1, lookback, lows) <= 0 || ArraySize(lows) == 0)
        return 0.0;

    return lows[ArrayMinimum(lows, 0, ArraySize(lows))];
}

//+------------------------------------------------------------------+
//| Get the highest high in the range period                          |
//+------------------------------------------------------------------+
double GetRangeHigh(int lookback)
{
    if (lookback <= 0)
        return 0.0;

    double highs[];
    if (CopyHigh(_Symbol, _Period, 1, lookback, highs) <= 0 || ArraySize(highs) == 0)
        return 0.0;

    double maxHigh = highs[0];
    for (int i = 1; i < ArraySize(highs); i++)
        if (highs[i] > maxHigh)
            maxHigh = highs[i];
    return maxHigh;
}

//+------------------------------------------------------------------+
//| Get the lowest low in the range period                            |
//+------------------------------------------------------------------+
double GetRangeLow(int lookback)
{
    if (lookback <= 0)
        return 0.0;

    double lows[];
    if (CopyLow(_Symbol, _Period, 1, lookback, lows) <= 0 || ArraySize(lows) == 0)
        return 0.0;

    double minLow = lows[0];
    for (int i = 1; i < ArraySize(lows); i++)
        if (lows[i] < minLow)
            minLow = lows[i];
    return minLow;
}

//+------------------------------------------------------------------+
//| Check if price is near a level within tolerance                   |
//+------------------------------------------------------------------+
bool IsPriceNear(double price, double level, double pctTolerance)
{
    if (level <= 0)
        return false;

    double diff = MathAbs(price - level);
    double tolerance = MathMax(MathAbs(level) * pctTolerance / 100.0, SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10.0);
    return diff <= tolerance;
}

//+------------------------------------------------------------------+
//| Check for bullish rejection pattern                               |
//+------------------------------------------------------------------+
bool IsBullRejection(const MqlRates &rates[], int index)
{
    int size = ArraySize(rates);
    if (size <= index)
        return false;

    MqlRates bar = rates[index];
    double body = MathAbs(bar.close - bar.open);
    double lowerWick = MathMin(bar.open, bar.close) - bar.low;
    double upperWick = bar.high - MathMax(bar.open, bar.close);
    return (body > 0 && lowerWick > body * 1.5 && lowerWick > upperWick * 1.2);
}

//+------------------------------------------------------------------+
//| Check for bearish rejection pattern                               |
//+------------------------------------------------------------------+
bool IsBearRejection(const MqlRates &rates[], int index)
{
    int size = ArraySize(rates);
    if (size <= index)
        return false;

    MqlRates bar = rates[index];
    double body = MathAbs(bar.close - bar.open);
    double upperWick = bar.high - MathMax(bar.open, bar.close);
    double lowerWick = MathMin(bar.open, bar.close) - bar.low;
    return (body > 0 && upperWick > body * 1.5 && upperWick > lowerWick * 1.2);
}

//+------------------------------------------------------------------+
//| Check if a pending order of specified type exists                 |
//+------------------------------------------------------------------+
bool HasPendingOrder(ENUM_ORDER_TYPE orderType)
{
    int total = OrdersTotal();
    for (int i = 0; i < total; i++)
    {
        if (!OrderSelect(i))
            continue;

        if (OrderGetString(ORDER_SYMBOL) != _Symbol ||
            (ulong)OrderGetInteger(ORDER_MAGIC) != MagicNumber ||
            (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) != orderType)
            continue;

        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Check if an open position of specified type exists                |
//+------------------------------------------------------------------+
bool HasOpenPosition(ENUM_POSITION_TYPE positionType)
{
    int total = PositionsTotal();
    for (int i = 0; i < total; i++)
    {
        ulong ticket = PositionGetTicket(i);
        if (ticket == 0 || !PositionSelectByTicket(ticket))
            continue;

        if (PositionGetString(POSITION_SYMBOL) != _Symbol ||
            (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber ||
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != positionType)
            continue;

        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk percentage                       |
//+------------------------------------------------------------------+
double CalcLotByRisk(double riskPercent, double stopDistance)
{
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    if (equity <= 0)
        return 0.0;

    double riskAmount = equity * riskPercent / 100.0;
    if (stopDistance <= 0 || riskAmount <= 0)
        return 0.0;

    double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    if (tickSize <= 0 || tickValue <= 0)
        return 0.0;

    double ticks = stopDistance / tickSize;
    double rawVolume = riskAmount / (ticks * tickValue);

    double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    double minVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

    if (step <= 0)
        step = 0.01;

    double volume = MathMax(minVol, MathRound(rawVolume / step) * step);
    if (volume < minVol)
        volume = minVol;
    if (maxVol > 0 && volume > maxVol)
        volume = maxVol;

    return volume;
}

//+------------------------------------------------------------------+
//| Execute trades based on trend and conditions                      |
//+------------------------------------------------------------------+
void ExecuteTrades(ETREND trend, double bid, double ask, double swingLow, double swingHigh,
                   double rangeHigh, double rangeLow, double buyEntry, double sellEntry,
                   double buySL, double buyTP, double sellSL, double sellTP, double lotSize)
{
    double tolerance = SR_PctTolerance / 100.0;
    bool atSupport = IsPriceNear(bid, swingLow, tolerance);
    bool atResistance = IsPriceNear(ask, swingHigh, tolerance);
    bool breakoutUp = (lastBarTime != 0 && GetRangeHigh(1) > rangeHigh); // Simplified breakout check
    bool breakoutDown = (lastBarTime != 0 && GetRangeLow(1) < rangeLow);

    MqlRates rates[];
    CopyRates(_Symbol, _Period, 0, 2, rates);
    bool bullRejection = IsBullRejection(rates, 1);
    bool bearRejection = IsBearRejection(rates, 1);

    if (trend == TREND_BULL && atSupport && bullRejection && !HasPendingOrder(ORDER_TYPE_BUY_LIMIT) && buyEntry > 0)
    {
        datetime expiry = TimeCurrent() + ExpireMinutes * 60;
        if (trade.BuyLimit(lotSize, buyEntry, _Symbol, buySL, buyTP, ORDER_TIME_GTC, CommentTag, MagicNumber))
            PrintFormat("BuyLimit placed: Entry=%.5f, SL=%.5f, TP=%.5f", buyEntry, buySL, buyTP);
        else
            PrintFormat("BuyLimit failed: Error %d", GetLastError());
    }
    else if (trend == TREND_BEAR && atResistance && bearRejection && !HasPendingOrder(ORDER_TYPE_SELL_LIMIT) && sellEntry > 0)
    {
        datetime expiry = TimeCurrent() + ExpireMinutes * 60;
        if (trade.SellLimit(lotSize, sellEntry, _Symbol, sellSL, sellTP, ORDER_TIME_GTC, CommentTag, MagicNumber))
            PrintFormat("SellLimit placed: Entry=%.5f, SL=%.5f, TP=%.5f", sellEntry, sellSL, sellTP);
        else
            PrintFormat("SellLimit failed: Error %d", GetLastError());
    }
    else if (trend == TREND_SIDE)
    {
        if (breakoutUp && !HasOpenPosition(POSITION_TYPE_BUY))
        {
            if (trade.Buy(lotSize, _Symbol, 0.0, buySL, buyTP, CommentTag))
                Print("Breakout Buy executed");
            else
                PrintFormat("Breakout Buy failed: Error %d", GetLastError());
        }
        if (breakoutDown && !HasOpenPosition(POSITION_TYPE_SELL))
        {
            if (trade.Sell(lotSize, _Symbol, 0.0, sellSL, sellTP, CommentTag))
                Print("Breakout Sell executed");
            else
                PrintFormat("Breakout Sell failed: Error %d", GetLastError());
        }
    }
}

//+------------------------------------------------------------------+
//| Manage open positions (exits and trailing stops)                  |
//+------------------------------------------------------------------+
void ManagePositions(double swingHigh, double swingLow, double atrValue)
{
    ManagePriceActionExits(swingHigh, swingLow);
    ApplyTrailingStop(atrValue);
}

//+------------------------------------------------------------------+
//| Close positions based on price action levels                     |
//+------------------------------------------------------------------+
void ManagePriceActionExits(double swingHigh, double swingLow)
{
    int total = PositionsTotal();
    for (int i = total - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if (ticket == 0 || !PositionSelectByTicket(ticket))
            continue;

        if (PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
            continue;

        ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

        if (posType == POSITION_TYPE_BUY && bid < swingLow)
        {
            if (!trade.PositionClose(ticket))
                PrintFormat("Failed to close Buy position %llu: Error %d", ticket, GetLastError());
        }
        else if (posType == POSITION_TYPE_SELL && ask > swingHigh)
        {
            if (!trade.PositionClose(ticket))
                PrintFormat("Failed to close Sell position %llu: Error %d", ticket, GetLastError());
        }
    }
}

//+------------------------------------------------------------------+
//| Apply trailing stop to open positions                             |
//+------------------------------------------------------------------+
void ApplyTrailingStop(double atrValue)
{
    if (atrValue <= 0)
        return;

    int total = PositionsTotal();
    for (int i = total - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if (ticket == 0 || !PositionSelectByTicket(ticket))
            continue;

        if (PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
            continue;

        ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        double currentSL = PositionGetDouble(POSITION_SL);
        double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

        if (posType == POSITION_TYPE_BUY)
        {
            // Trail SL for buy positions
            if (bid - openPrice > Trail_ATR_Multiplier * atrValue)
            {
                double desiredSL = NormalizeDouble(bid - Trail_ATR_Multiplier * atrValue, _Digits);
                if (desiredSL > currentSL && desiredSL > openPrice)
                {
                    if (!trade.PositionModify(ticket, desiredSL, PositionGetDouble(POSITION_TP)))
                        PrintFormat("Failed to trail SL for Buy position %llu: Error %d", ticket, GetLastError());
                }
            }
        }
        else if (posType == POSITION_TYPE_SELL)
        {
            // Trail SL for sell positions
            if (openPrice - ask > Trail_ATR_Multiplier * atrValue)
            {
                double desiredSL = NormalizeDouble(ask + Trail_ATR_Multiplier * atrValue, _Digits);
                bool shouldTrail = (currentSL == 0.0 || desiredSL < currentSL) && desiredSL < openPrice;
                if (shouldTrail)
                {
                    if (!trade.PositionModify(ticket, desiredSL, PositionGetDouble(POSITION_TP)))
                        PrintFormat("Failed to trail SL for Sell position %llu: Error %d", ticket, GetLastError());
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Check and enforce daily loss limit                                |
//+------------------------------------------------------------------+
void CheckDailyLoss()
{
    if (startEquityToday <= 0)
        return;

    double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
    double lossPercent = 100.0 * (startEquityToday - currentEquity) / startEquityToday;
    if (lossPercent >= MaxDailyLossPercent)
    {
        tradingLocked = true;
        PrintFormat("Daily loss limit reached (%.2f%%). Trading locked.", lossPercent);
    }
}

//+------------------------------------------------------------------+
//| Reset daily tracking variables                                   |
//+------------------------------------------------------------------+
void ResetDaily()
{
    startEquityToday = AccountInfoDouble(ACCOUNT_EQUITY);
    if (startEquityToday < 0)
        startEquityToday = 0.0;
    tradingLocked = false;
    Print("Daily reset performed.");
}
//+------------------------------------------------------------------+
//| End of file                                                       |
//+------------------------------------------------------------------+
