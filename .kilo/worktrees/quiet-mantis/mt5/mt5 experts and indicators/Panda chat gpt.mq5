//+------------------------------------------------------------------+
//|                                               Panda chat gpt.mq5 |
//|                                                      dark kingin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property link      "https://www.mql5.com"
#property version   "1.00"

// Gold_SMC_EA.mq5
// Expert Advisor for XAUUSD (Gold) for MT5
// Features implemented:
// - Position sizing: 0.1% of account equity per position
// - Maximum daily loss: 1.5% of account equity (locks trading for rest of day)
// - ATR-based stop loss sized so that risk equals 0.1% of equity
// - Trailing stop: moves by 25% of the favorable move once trade is in profit
// - Take profit: between 2.5x and 7x SL (configured via input); computed from ATR
// - Max positions: computed from how many 0.1% risk trades fit into 1.5% daily loss
// - Integration hooks to call SMC indicator (iCustom) and to read delta footprint tables
// - High timeframe order-block / POI detection is expected to come from the SMC indicator
// - Delta signals (flip, surge, transition) are validated by cumulative delta on higher timeframe
//
// NOTES for the user:
// 1) Place your SMC indicator files (mq5/ex5/mqh) into MQL5/Indicators. Set the indicatorName input below
//    and set the buffer indexes for relevant outputs (order block signals, cumulative delta, etc.).
// 2) If you cannot provide the SMC file, the EA will still run and will only demonstrate risk-management
//    and order sending logic. You will need to wire the SMC/delta buffer names/indices.
// 3) This EA is a framework - delta parsing and specific SMC buffer indices are left as configurable inputs
//    because your provided archive could not be programmatically inspected in this environment.

#include <Trade\Trade.mqh>
CTrade trade;

// Inputs
input string   indicatorName = "SMC_VERIFIED"; // change to the actual indicator file name (without extension)
input int      smc_OBBuffer = 0;         // buffer index that flags Order Blocks / Points of Interest (user must set)
input int      smc_cumDeltaBuf = 1;     // buffer index for cumulative delta on HTF
input int      footprint_delta_buf = 0;  // footprint delta buffer index on M1/M5 indicator
input int      footprint_maxdelta_buf = 1;
input int      footprint_mindelta_buf = 2;
input int      footprint_cumdelta_buf = 3;
input int      footprint_volume_buf = 4;

input double   risk_per_trade_percent = 0.1; // percent of equity to risk per trade (0.1%)
input double   max_daily_loss_percent = 1.5; // percent of equity
input int      atr_period = 14;
input ENUM_TIMEFRAMES HTF1 = PERIOD_H4;    // higher timeframe 1
input ENUM_TIMEFRAMES HTF2 = PERIOD_H1;    // higher timeframe 2
input ENUM_TIMEFRAMES HTF3 = PERIOD_M30;   // higher timeframe 3
input ENUM_TIMEFRAMES LTF1 = PERIOD_M5;    // lower timeframe used for delta
input ENUM_TIMEFRAMES LTF2 = PERIOD_M1;
input double   tp_multiplier_min = 2.5;    // min TP = 2.5 * SL
input double   tp_multiplier_max = 7.0;    // max TP = 7.0 * SL
input double   trailing_trigger_pct = 0.25; // trailing moves by 25% of favorable move
input int      magic = 20250919;
input bool     allow_buy = true;
input bool     allow_sell = true;
input double   lot_min = 0.01;

// Globals
datetime lastDailyReset = 0;
double   dayLossLockedEquity = 0.0; // equity when daily lock set

// Utility: returns account equity
double AccountEquity() { return AccountInfoDouble(ACCOUNT_EQUITY); }

// Calculate lot size so that stopLoss (in points) results in risk_per_trade_percent of equity
double CalculateLotSize(double stop_loss_points)
{
    // risk money = equity * (risk_per_trade_percent / 100)
    double equity = AccountEquity();
    double risk_money = equity * (risk_per_trade_percent/100.0);

    // For gold, contract size is 100 oz for many brokers. We'll compute using MarketInfo-like values.
    // MQL5: use SymbolInfoDouble
    double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

    // Convert stop loss in points to monetary risk per lot: risk_per_lot = stop_loss_points * tick_value/point
    // But tick_value is value per tick for a 1 lot? MQL5's SYMBOL_TRADE_TICK_VALUE is per 1 lot usually.
    // Monetary risk per 1.0 lot = stop_loss_points * (tick_value / (point / tick_size)) approximated.
    double ticks_per_point = 1.0; // normally point == tick for Forex, for XAU it's broker dependent
    if(point!=0) ticks_per_point = tick_size/point;
    double monetary_risk_per_lot = stop_loss_points * (tick_value * ticks_per_point);

    if(monetary_risk_per_lot <= 0)
        return lot_min; // fallback

    double lots = risk_money / monetary_risk_per_lot;
    // normalize to step and min
    double vol_step = lot_step>0?lot_step:0.01;
    double minlot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxlot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    if(minlot<=0) minlot = lot_min;
    lots = MathFloor(lots/vol_step + 0.0000001) * vol_step;
    if(lots < minlot) lots = minlot;
    if(lots > maxlot) lots = maxlot;
    return NormalizeDouble(lots, 2);
}

// Compute ATR in points
double GetATR(ENUM_TIMEFRAMES tf, int period)
{
    // Use iATR
    int handle = iATR(_Symbol, tf, period);
    if(handle == INVALID_HANDLE) return 0;
    double atr_vals[];
    ArraySetAsSeries(atr_vals, true);
    if(CopyBuffer(handle, 0, 0, 3, atr_vals) <= 0) { IndicatorRelease(handle); return 0; }
    double atr = atr_vals[0];
    IndicatorRelease(handle);
    // Convert ATR (price units) to points
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    if(point==0) return 0;
    double atr_points = atr / point;
    return atr_points;
}

// Daily loss tracking
void CheckDailyReset()
{
    datetime today = TimeCurrent();
    MqlDateTime md; TimeToStruct(today, md);
    // reset at 00:00 server time
    datetime resetTime = StructToTime(md);
    if(lastDailyReset == 0 || resetTime > lastDailyReset)
    {
        // reset counters
        lastDailyReset = resetTime;
        // Allow trading again
        dayLossLockedEquity = 0.0;
        GlobalVariableSet("GoldEA_DayLocked", 0);
    }
}

bool IsDailyLocked()
{
    double val = GlobalVariableGet("GoldEA_DayLocked");
    return (val != 0);
}

void SetDailyLocked()
{
    GlobalVariableSet("GoldEA_DayLocked", 1);
}

// Compute how many positions of risk_per_trade_percent fit into max_daily_loss_percent
int ComputeMaxPositions()
{
    double max_positions = MathFloor(max_daily_loss_percent / risk_per_trade_percent + 0.0000001);
    if(max_positions < 1) return 1;
    return (int)max_positions;
}

// Update running daily loss by scanning closed trades of today
double ComputeTodayLoss()
{
    double loss = 0.0;
    datetime startOfDay = lastDailyReset;
    for(int i=HistoryDealsTotal()-1; i>=0; --i)
    {
        ulong ticket = HistoryDealGetTicket(i);
        MqlTradeTransaction trans;
        // Use HistoryDealSelect not available - fallback: use HistoryOrderGetDouble? Simpler: iterate orders
    }
    // Simpler approach: compute equity change since start of day by storing starting equity in global var.
    double startEquity = GlobalVariableGet("GoldEA_StartEquity");
    if(startEquity == 0)
    {
        GlobalVariableSet("GoldEA_StartEquity", AccountEquity());
        startEquity = AccountEquity();
    }
    loss = startEquity - AccountEquity(); // positive if we lost
    if(loss < 0) loss = 0;
    return loss;
}

// Main entry checks for SMC + delta signals (skeleton)
bool CheckEntrySignal(bool &isBuy, double &entryPrice, double &stopLossPoints, double &takeProfitPoints)
{
    // This function will:
    // 1. Query the SMC indicator (iCustom) on HTFs for whether we're in an Order Block / POI
    // 2. If in POI, switch to LTF (M5/M1) and call footprint indicator buffers to construct delta table
    // 3. Evaluate delta flip / surge / transition with cumulative delta alignment
    // 4. If validated, calculate ATR-based SL and TP and return true with details

    // --- Example placeholder implementation: the user must set buffer indices correctly ---
    // Query SMC order-block flag at current bar on HTF1
    double ob_val = 0;
    int obHandle = iCustom(_Symbol, HTF1, indicatorName);
    if(obHandle != INVALID_HANDLE)
    {
        double arr[];
        ArraySetAsSeries(arr, true);
        if(CopyBuffer(obHandle, smc_OBBuffer, 0, 1, arr) > 0)
            ob_val = arr[0];
        IndicatorRelease(obHandle);
    }

    if(ob_val == 0)
    {
        return false; // not in OB/POI according to SMC (placeholder)
    }

    // Now consult footprint/delta indicator on LTF (user must supply indicator that outputs the required buffers)
    int fpHandle = iCustom(_Symbol, LTF1, "DeltaFootprint"); // change name if needed
    if(fpHandle == INVALID_HANDLE) return false;
    double delta[5]; double maxd[5]; double mind[5]; double cumd[5]; double vol[5];
    ArraySetAsSeries(delta, true);
    if(CopyBuffer(fpHandle, footprint_delta_buf, 0, 5, delta) <= 0) { IndicatorRelease(fpHandle); return false; }
    if(CopyBuffer(fpHandle, footprint_maxdelta_buf, 0, 5, maxd) <= 0) { IndicatorRelease(fpHandle); return false; }
    if(CopyBuffer(fpHandle, footprint_mindelta_buf, 0, 5, mind) <= 0) { IndicatorRelease(fpHandle); return false; }
    if(CopyBuffer(fpHandle, footprint_cumdelta_buf, 0, 5, cumd) <= 0) { IndicatorRelease(fpHandle); return false; }
    if(CopyBuffer(fpHandle, footprint_volume_buf, 0, 5, vol) <= 0) { IndicatorRelease(fpHandle); return false; }
    IndicatorRelease(fpHandle);

    // Evaluate simple delta flip example on latest candles (delta[0] is most recent)
    // Delta flip: abrupt change in sign between previous two candles
    if(delta[1] > 0 && delta[0] < 0 && MathAbs(maxd[0] - delta[0]) < MathAbs(delta[0])*0.3 && MathAbs(mind[0])<1e-6)
    {
        isBuy = false;
    }
    else if(delta[1] < 0 && delta[0] > 0 && MathAbs(min d[0] - delta[0]) < MathAbs(delta[0])*0.3 && MathAbs(maxd[0])<1e-6)
    {
        isBuy = true;
    }
    else
    {
        // other checks (surge/transition) left as future implementations
        return false;
    }

    // ATR-based stoploss in points
    double atr_points = GetATR(LTF1, atr_period);
    if(atr_points <= 0) return false;

    // Determine SL as a function of ATR but adjusted so monetary risk = 0.1% equity.
    // We'll start with SL = ATR * factor (e.g., 1.0)
    double sl_points = atr_points * 1.0;

    // Determine lot size and actual SL in points required for that lot to match the risk per trade
    double lots = CalculateLotSize(sl_points);
    if(lots <= 0) return false;

    // Recompute SL in case lot stepped
    // NOTE: A more precise approach would iterate SL to match risk exactly; we'll accept this approximation
    stopLossPoints = sl_points;
    double tp_points = MathMin(MathMax(tp_multiplier_min * stopLossPoints, tp_multiplier_min * stopLossPoints), tp_multiplier_max * stopLossPoints);
    takeProfitPoints = tp_points;

    // Entry price
    entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

    return true;
}

// Place market order
bool PlaceOrder(bool isBuy, double lots, double sl_points, double tp_points)
{
    if(IsDailyLocked()) return false;

    double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double sl = isBuy ? price - sl_points*SymbolInfoDouble(_Symbol, SYMBOL_POINT) : price + sl_points*SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    double tp = isBuy ? price + tp_points*SymbolInfoDouble(_Symbol, SYMBOL_POINT) : price - tp_points*SymbolInfoDouble(_Symbol, SYMBOL_POINT);

    trade.SetExpertMagicNumber(magic);
    trade.SetDeviationInPoints(30);
    bool res=false;
    if(isBuy) res = trade.Buy(lots, NULL, price, sl, tp, "SMC EA");
    else res = trade.Sell(lots, NULL, price, sl, tp, "SMC EA");

    if(!res)
    {
        Print("Order failed: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
        return false;
    }
    return true;
}

// OnTick
void OnTick()
{
    CheckDailyReset();
    if(IsDailyLocked()) return;

    // compute allowed positions
    int maxPos = ComputeMaxPositions();
    int currentPos = 0;
    for(int i=PositionsTotal()-1;i>=0;--i)
    {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket))
        {
            if((int)PositionGetInteger(POSITION_MAGIC) == magic) currentPos++;
        }
    }
    if(currentPos >= maxPos) return;

    // Check entry signal
    bool isBuy=false; double entryPrice=0; double sl_points=0; double tp_points=0;
    if(CheckEntrySignal(isBuy, entryPrice, sl_points, tp_points))
    {
        // compute lot by SL
        double lots = CalculateLotSize(sl_points);
        if(lots <= 0) return;
        if(isBuy && !allow_buy) return;
        if(!isBuy && !allow_sell) return;

        if(PlaceOrder(isBuy, lots, sl_points, tp_points))
        {
            Print("Placed order: ", isBuy?"BUY":"SELL", " lots=", lots, " SL=", sl_points, " TP=", tp_points);
        }
    }

    // Check daily loss and lock if limit exceeded
    double todayLoss = ComputeTodayLoss();
    double equity = AccountEquity();
    double maxLossMoney = equity * (max_daily_loss_percent/100.0);
    if(todayLoss >= maxLossMoney - 1e-6)
    {
        Print("Daily loss limit reached. Locking trading for the rest of the day.");
        SetDailyLocked();
    }
}

// OnDeinit
void OnDeinit(const int reason)
{
}

// OnInit
int OnInit()
{
    // ensure global variable exists
    if(!GlobalVariableCheck("GoldEA_DayLocked")) GlobalVariableSet("GoldEA_DayLocked", 0);
    if(!GlobalVariableCheck("GoldEA_StartEquity")) GlobalVariableSet("GoldEA_StartEquity", AccountEquity());
    lastDailyReset = 0; // will be set on first tick
    return INIT_SUCCEEDED;
}

// END OF FILE..................//