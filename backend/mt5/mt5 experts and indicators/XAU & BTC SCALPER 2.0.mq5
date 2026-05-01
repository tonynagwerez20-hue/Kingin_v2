---------------------------+
-//|                                        XAU & BTC SCALPER 2.0.mq5 |
-//|                                                      dark kingin |
-//|                                             https://www.mql5.com |
-//+------------------------------------------------------------------+
-#property copyright "dark kingin"
-#property link      "https://www.mql5.com"
-#property version   "2.10"
-#property strict
-
-#include <Trade/Trade.mqh>
-CTrade trade;
-
-//--- Constants
-#define INVALID_ATR_HANDLE -1
-#define MIN_LOOKBACK_BARS 5
-#define MAX_LOOKBACK_BARS 50
-#define MIN_ATR_PERIOD 5
-#define MAX_ATR_PERIOD 50
-
-//--- Inputs
-input int    LookbackBars         = 12;     // bars to look back (shorter for scalps)
-input int    ATR_Period           = 14;     // ATR period
-input double SL_ATR_Multiplier    = 1.2;    // StopLoss multiplier (tighter for scalps)
-input double TP_ATR_Multiplier    = 2.0;    // TakeProfit multiplier
-input double Trail_ATR_Multiplier = 0.8;    // Trailing stop ATR multiple
-input int    ExpireMinutes        = 30;     // pending order expiry
-input double RiskPerTradePercent  = 0.1;    // % equity risked per trade
-input double MaxDailyLossPercent  = 1.5;    // % equity max daily loss
-input ulong  MagicNumber          = 909090; // magic number
-input string CommentTag           = "PA_Scalper_BTC_Gold";
-
-//--- Enums
-enum ENUM_TRADE_SIGNAL
-{
-    SIGNAL_NONE,
-    SIGNAL_BUY,
-    SIGNAL_SELL
-};
-
-//--- Globals
-datetime lastBarTime = 0;
-double   startEquityToday = 0.0;
-bool     tradingLocked = false;
-int      atrHandle = INVALID_ATR_HANDLE;
-
-//--- Cached symbol info
-double tickSize = 0.0;
-double tickValue = 0.0;
-double volumeStep = 0.0;
-double volumeMin = 0.0;
-double volumeMax = 0.0;
-
-//+------------------------------------------------------------------+
-//| Initialization function
-//+------------------------------------------------------------------+
-int OnInit()
-{
-    // Validate inputs
-    if (!ValidateInputs())
-    {
-        Print("Error: Invalid input parameters.");
-        return INIT_PARAMETERS_INCORRECT;
-    }
-
-    // Initialize ATR indicator
-    atrHandle = iATR(_Symbol, _Period, ATR_Period);
-    if (atrHandle == INVALID_HANDLE)
-    {
-        PrintFormat("Error: Failed to create ATR indicator. Error: %d", GetLastError());
-        return INIT_FAILED;
-    }
-
-    // Cache symbol information
-    if (!CacheSymbolInfo())
-    {
-        Print("Error: Failed to cache symbol information.");
-        return INIT_FAILED;
-    }
-
-    // Reset daily limits
-    ResetDailyLimits();
-
-    Print("EA initialized successfully.");
-    return INIT_SUCCEEDED;
-}
-
-//+------------------------------------------------------------------+
-//| Deinitialization function
-//+------------------------------------------------------------------+
-void OnDeinit(const int reason)
-{
-    // Release indicator handle
-    if (atrHandle != INVALID_HANDLE)
-    {
-        IndicatorRelease(atrHandle);
-        atrHandle = INVALID_HANDLE;
-    }
-
-    Print("EA deinitialized.");
-}
-
-//+------------------------------------------------------------------+
-//| Main tick function
-//+------------------------------------------------------------------+
-void OnTick()
-{
-    // Check for daily reset
-    if (IsNewDay())
-        ResetDailyLimits();
-
-    // Skip if trading is locked
-    if (tradingLocked)
-        return;
-
-    // Process only on new bar
-    if (!IsNewBar())
-        return;
-
-    // Get market data
-    double atrValue = GetATRValue();
-    if (atrValue <= 0.0)
-    {
-        Print("Warning: Invalid ATR value. Skipping tick.");
-        return;
-    }
-
-    // Calculate swing levels
-    double swingHigh = GetSwingHigh(LookbackBars);
-    double swingLow = GetSwingLow(LookbackBars);
-    if (swingHigh <= 0.0 || swingLow <= 0.0)
-    {
-        Print("Warning: Invalid swing levels. Skipping tick.");
-        return;
-    }
-
-    // Calculate order levels
-    double sellEntry = NormalizeDouble(swingHigh, _Digits);
-    double buyEntry  = NormalizeDouble(swingLow,  _Digits);
-    double sellSL    = NormalizeDouble(sellEntry + SL_ATR_Multiplier * atrValue, _Digits);
-    double sellTP    = NormalizeDouble(sellEntry - TP_ATR_Multiplier * atrValue, _Digits);
-    double buySL     = NormalizeDouble(buyEntry  - SL_ATR_Multiplier * atrValue, _Digits);
-    double buyTP     = NormalizeDouble(buyEntry  + TP_ATR_Multiplier * atrValue, _Digits);
-
-    // Calculate position size
-    double lotSize = CalculateLotSize(atrValue);
-    if (lotSize <= 0.0)
-    {
-        Print("Warning: Invalid lot size. Skipping trade.");
-        return;
-    }
-
-    // Check for rejection signals
-    ENUM_TRADE_SIGNAL signal = GetTradeSignal();
-    if (signal == SIGNAL_NONE)
-        return;
-
-    // Place orders
-    PlacePendingOrders(signal, buyEntry, sellEntry, buySL, buyTP, sellSL, sellTP, lotSize);
-
-    // Manage existing positions
-    ManagePositions(swingHigh, swingLow, atrValue);
-
-    // Check daily loss
-    CheckDailyLoss();
-}
-
-//+------------------------------------------------------------------+
-//| Validate input parameters
-//+------------------------------------------------------------------+
-bool ValidateInputs()
-{
-    if (LookbackBars < MIN_LOOKBACK_BARS || LookbackBars > MAX_LOOKBACK_BARS)
-        return false;
-    if (ATR_Period < MIN_ATR_PERIOD || ATR_Period > MAX_ATR_PERIOD)
-        return false;
-    if (SL_ATR_Multiplier <= 0.0 || TP_ATR_Multiplier <= 0.0 || Trail_ATR_Multiplier < 0.0)
-        return false;
-    if (ExpireMinutes <= 0)
-        return false;
-    if (RiskPerTradePercent <= 0.0 || MaxDailyLossPercent <= 0.0)
-        return false;
-    return true;
-}
-
-//+------------------------------------------------------------------+
-//| Cache symbol information for performance
-//+------------------------------------------------------------------+
-bool CacheSymbolInfo()
-{
-    tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
-    tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
-    volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
-    volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
-    volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
-
-    if (tickSize <= 0.0 || tickValue <= 0.0 || volumeStep <= 0.0 || volumeMin <= 0.0)
-        return false;
-    return true;
-}
-
-//+------------------------------------------------------------------+
-//| Check if it's a new trading day
-//+------------------------------------------------------------------+
-bool IsNewDay()
-{
-    static int lastDay = -1;
-    datetime currentTime = TimeCurrent();
-    MqlDateTime dt;
-    TimeToStruct(currentTime, dt);
-    int currentDay = dt.day;
-
-    if (currentDay != lastDay)
-    {
-        lastDay = currentDay;
-        return true;
-    }
-    return false;
-}
-
-//+------------------------------------------------------------------+
-//| Check if it's a new bar
-//+------------------------------------------------------------------+
-bool IsNewBar()
-{
-    MqlRates rates[];
-    if (CopyRates(_Symbol, _Period, 0, LookbackBars + 5, rates) <= 0)
-        return false;
-
-    datetime currentBarTime = rates[1].time;
-    if (currentBarTime == lastBarTime)
-        return false;
-
-    lastBarTime = currentBarTime;
-    return true;
-}
-
-//+------------------------------------------------------------------+
-//| Get ATR value
-//+------------------------------------------------------------------+
-double GetATRValue()
-{
-    if (atrHandle == INVALID_HANDLE)
-        return 0.0;
-
-    double atrBuffer[];
-    if (CopyBuffer(atrHandle, 0, 1, 1, atrBuffer) <= 0)
-        return 0.0;
-
-    return atrBuffer[0];
-}
-
-//+------------------------------------------------------------------+
-//| Get swing high
-//+------------------------------------------------------------------+
-double GetSwingHigh(int bars)
-{
-    double highs[];
-    if (CopyHigh(_Symbol, _Period, 1, bars, highs) <= 0)
-        return 0.0;
-
-    return highs[ArrayMaximum(highs, 0, bars)];
-}
-
-//+------------------------------------------------------------------+
-//| Get swing low
-//+------------------------------------------------------------------+
-double GetSwingLow(int bars)
-{
-    double lows[];
-    if (CopyLow(_Symbol, _Period, 1, bars, lows) <= 0)
-        return 0.0;
-
-    return lows[ArrayMinimum(lows, 0, bars)];
-}
-
-//+------------------------------------------------------------------+
-//| Calculate lot size based on risk
-//+------------------------------------------------------------------+
-double CalculateLotSize(double atrValue)
-{
-    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
-    if (equity <= 0.0)
-        return 0.0;
-
-    double riskAmount = equity * (RiskPerTradePercent / 100.0);
-    double stopDistance = SL_ATR_Multiplier * atrValue;
-    if (stopDistance <= 0.0)
-        return 0.0;
-
-    double ticks = stopDistance / tickSize;
-    double lotSize = riskAmount / (ticks * tickValue);
-
-    // Round to volume step
-    lotSize = MathFloor(lotSize / volumeStep) * volumeStep;
-
-    // Clamp to limits
-    if (lotSize < volumeMin)
-        lotSize = volumeMin;
-    if (volumeMax > 0.0 && lotSize > volumeMax)
-        lotSize = volumeMax;
-
-    return lotSize;
-}
-
-//+------------------------------------------------------------------+
-//| Get trade signal based on rejection patterns
-//+------------------------------------------------------------------+
-ENUM_TRADE_SIGNAL GetTradeSignal()
-{
-    MqlRates rates[];
-    if (CopyRates(_Symbol, _Period, 0, 2, rates) < 2)
-        return SIGNAL_NONE;
-
-    MqlRates prevBar = rates[1];
-    bool isBearRejection = (prevBar.close < prevBar.open &&
-                           (prevBar.high - MathMax(prevBar.close, prevBar.open)) >
-                           (prevBar.close - prevBar.low) * 1.5);
-    bool isBullRejection = (prevBar.close > prevBar.open &&
-                           (MathMin(prevBar.close, prevBar.open) - prevBar.low) >
-                           (prevBar.high - prevBar.close) * 1.5);
-
-    if (isBullRejection)
-        return SIGNAL_BUY;
-    if (isBearRejection)
-        return SIGNAL_SELL;
-    return SIGNAL_NONE;
-}
-
-//+------------------------------------------------------------------+
-//| Place pending orders
-//+------------------------------------------------------------------+
-void PlacePendingOrders(ENUM_TRADE_SIGNAL signal, double buyEntry, double sellEntry,
-                        double buySL, double buyTP, double sellSL, double sellTP, double lotSize)
-{
-    datetime expiry = TimeCurrent() + ExpireMinutes * 60;
-
-    if (signal == SIGNAL_BUY && !HasPendingOrder(ORDER_TYPE_BUY_LIMIT))
-    {
-        if (!trade.BuyLimit(lotSize, buyEntry, _Symbol, buySL, buyTP, CommentTag, MagicNumber, expiry))
-            PrintFormat("BuyLimit failed: %d", GetLastError());
-    }
-    else if (signal == SIGNAL_SELL && !HasPendingOrder(ORDER_TYPE_SELL_LIMIT))
-    {
-        if (!trade.SellLimit(lotSize, sellEntry, _Symbol, sellSL, sellTP, CommentTag, MagicNumber, expiry))
-            PrintFormat("SellLimit failed: %d", GetLastError());
-    }
-}
-
-//+------------------------------------------------------------------+
-//| Check if pending order exists
-//+------------------------------------------------------------------+
-bool HasPendingOrder(ENUM_ORDER_TYPE type)
-{
-    for (int i = OrdersTotal() - 1; i >= 0; i--)
-    {
-        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
-        {
-            if (OrderSymbol() == _Symbol && OrderMagicNumber() == MagicNumber && OrderType() == type)
-                return true;
-        }
-    }
-    return false;
-}
-
-//+------------------------------------------------------------------+
-//| Manage existing positions
-//+------------------------------------------------------------------+
-void ManagePositions(double swingHigh, double swingLow, double atrValue)
-{
-    ManageExits(swingHigh, swingLow);
-    ApplyTrailingStop(atrValue);
-}
-
-//+------------------------------------------------------------------+
-//| Manage position exits based on swing levels
-//+------------------------------------------------------------------+
-void ManageExits(double swingHigh, double swingLow)
-{
-    for (int i = PositionsTotal() - 1; i >= 0; i--)
-    {
-        if (PositionSelectByIndex(i))
-        {
-            if (PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
-            {
-                ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
-                double price = PositionGetDouble(POSITION_PRICE_OPEN);
-
-                if (type == POSITION_TYPE_BUY && price < swingLow)
-                    trade.PositionClose(_Symbol);
-                else if (type == POSITION_TYPE_SELL && price > swingHigh)
-                    trade.PositionClose(_Symbol);
-            }
-        }
-    }
-}
-
-//+------------------------------------------------------------------+
-//| Apply trailing stop
-//+------------------------------------------------------------------+
-void ApplyTrailingStop(double atrValue)
-{
-    for (int i = PositionsTotal() - 1; i >= 0; i--)
-    {
-        if (PositionSelectByIndex(i))
-        {
-            if (PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
-            {
-                ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
-                double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
-                double stopLoss = PositionGetDouble(POSITION_SL);
-                double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
-                double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
-
-                if (type == POSITION_TYPE_BUY)
-                {
-                    double newSL = bid - Trail_ATR_Multiplier * atrValue;
-                    if (newSL > stopLoss && newSL > openPrice)
-                        trade.PositionModify(_Symbol, newSL, PositionGetDouble(POSITION_TP));
-                }
-                else if (type == POSITION_TYPE_SELL)
-                {
-                    double newSL = ask + Trail_ATR_Multiplier * atrValue;
-                    if ((stopLoss == 0.0 || newSL < stopLoss) && newSL < openPrice)
-                        trade.PositionModify(_Symbol, newSL, PositionGetDouble(POSITION_TP));
-                }
-            }
-        }
-    }
-}
-
-//+------------------------------------------------------------------+
-//| Check daily loss limit
-//+------------------------------------------------------------------+
-void CheckDailyLoss()
-{
-    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
-    double drop = 100.0 * (startEquityToday - equity) / startEquityToday;
-    if (drop >= MaxDailyLossPercent)
-        tradingLocked = true;
-}
-
-//+------------------------------------------------------------------+
-//| Reset daily limits
-//+------------------------------------------------------------------+
-void ResetDailyLimits()
-{
-    startEquityToday = AccountInfoDouble(ACCOUNT_EQUITY);
-    tradingLocked = false;
-}
+//+------------------------------------------------------------------+
+//|                                        XAU & BTC SCALPER 2.0.mq4 |
+//|                                                      dark kingin |
+//|                                             https://www.mql5.com |
+//+------------------------------------------------------------------+
+#property copyright "dark kingin"
+#property link      "https://www.mql5.com"
+#property version   "2.10"
+
+//--- Constants
+#define MIN_LOOKBACK_BARS 5
+#define MAX_LOOKBACK_BARS 50
+#define MIN_ATR_PERIOD 5
+#define MAX_ATR_PERIOD 50
+
+//--- Inputs
+input int    LookbackBars         = 12;     // bars to look back (shorter for scalps)
+input int    ATR_Period           = 14;     // ATR period
+input double SL_ATR_Multiplier    = 1.2;    // StopLoss multiplier (tighter for scalps)
+input double TP_ATR_Multiplier    = 2.0;    // TakeProfit multiplier
+input double Trail_ATR_Multiplier = 0.8;    // Trailing stop ATR multiple
+input int    ExpireMinutes        = 30;     // pending order expiry
+input double RiskPerTradePercent  = 0.1;    // % equity risked per trade
+input double MaxDailyLossPercent  = 1.5;    // % equity max daily loss
+input int    MagicNumber          = 909090; // magic number
+input string CommentTag           = "PA_Scalper_BTC_Gold";
+
+//--- Enums
+enum ENUM_TRADE_SIGNAL
+{
+    SIGNAL_NONE,
+    SIGNAL_BUY,
+    SIGNAL_SELL
+};
+
+//--- Globals
+datetime lastBarTime = 0;
+double   startEquityToday = 0.0;
+bool     tradingLocked = false;
+
+//--- Cached symbol info
+double tickSize = 0.0;
+double tickValue = 0.0;
+double volumeStep = 0.0;
+double volumeMin = 0.0;
+double volumeMax = 0.0;
+
+//+------------------------------------------------------------------+
+//| Initialization function
+//+------------------------------------------------------------------+
+int OnInit()
+{
+    // Validate inputs
+    if (!ValidateInputs())
+    {
+        Print("Error: Invalid input parameters.");
+        return INIT_PARAMETERS_INCORRECT;
+    }
+
+    // Cache symbol information
+    if (!CacheSymbolInfo())
+    {
+        Print("Error: Failed to cache symbol information.");
+        return INIT_FAILED;
+    }
+
+    // Reset daily limits
+    ResetDailyLimits();
+
+    Print("EA initialized successfully.");
+    return INIT_SUCCEEDED;
+}
+
+//+------------------------------------------------------------------+
+//| Deinitialization function
+//+------------------------------------------------------------------+
+void OnDeinit(const int reason)
+{
+    Print("EA deinitialized.");
+}
+
+//+------------------------------------------------------------------+
+//| Main tick function
+//+------------------------------------------------------------------+
+void OnTick()
+{
+    // Check for daily reset
+    if (IsNewDay())
+        ResetDailyLimits();
+
+    // Skip if trading is locked
+    if (tradingLocked)
+        return;
+
+    // Process only on new bar
+    if (!IsNewBar())
+        return;
+
+    // Get market data
+    double atrValue = GetATRValue();
+    if (atrValue <= 0.0)
+    {
+        Print("Warning: Invalid ATR value. Skipping tick.");
+        return;
+    }
+
+    // Calculate swing levels
+    double swingHigh = GetSwingHigh(LookbackBars);
+    double swingLow = GetSwingLow(LookbackBars);
+    if (swingHigh <= 0.0 || swingLow <= 0.0)
+    {
+        Print("Warning: Invalid swing levels. Skipping tick.");
+        return;
+    }
+
+    // Calculate order levels
+    double sellEntry = NormalizeDouble(swingHigh, Digits);
+    double buyEntry  = NormalizeDouble(swingLow,  Digits);
+    double sellSL    = NormalizeDouble(sellEntry + SL_ATR_Multiplier * atrValue, Digits);
+    double sellTP    = NormalizeDouble(sellEntry - TP_ATR_Multiplier * atrValue, Digits);
+    double buySL     = NormalizeDouble(buyEntry  - SL_ATR_Multiplier * atrValue, Digits);
+    double buyTP     = NormalizeDouble(buyEntry  + TP_ATR_Multiplier * atrValue, Digits);
+
+    // Calculate position size
+    double lotSize = CalculateLotSize(atrValue);
+    if (lotSize <= 0.0)
+    {
+        Print("Warning: Invalid lot size. Skipping trade.");
+        return;
+    }
+
+    // Check for rejection signals
+    ENUM_TRADE_SIGNAL signal = GetTradeSignal();
+    if (signal == SIGNAL_NONE)
+        return;
+
+    // Place orders
+    PlacePendingOrders(signal, buyEntry, sellEntry, buySL, buyTP, sellSL, sellTP, lotSize);
+
+    // Manage existing positions
+    ManagePositions(swingHigh, swingLow, atrValue);
+
+    // Check daily loss
+    CheckDailyLoss();
+}
+
+//+------------------------------------------------------------------+
+//| Validate input parameters
+//+------------------------------------------------------------------+
+bool ValidateInputs()
+{
+    if (LookbackBars < MIN_LOOKBACK_BARS || LookbackBars > MAX_LOOKBACK_BARS)
+        return false;
+    if (ATR_Period < MIN_ATR_PERIOD || ATR_Period > MAX_ATR_PERIOD)
+        return false;
+    if (SL_ATR_Multiplier <= 0.0 || TP_ATR_Multiplier <= 0.0 || Trail_ATR_Multiplier < 0.0)
+        return false;
+    if (ExpireMinutes <= 0)
+        return false;
+    if (RiskPerTradePercent <= 0.0 || MaxDailyLossPercent <= 0.0)
+        return false;
+    return true;
+}
+
+//+------------------------------------------------------------------+
+//| Cache symbol information for performance
+//+------------------------------------------------------------------+
+bool CacheSymbolInfo()
+{
+    tickSize = MarketInfo(Symbol(), MODE_TICKSIZE);
+    tickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
+    volumeStep = MarketInfo(Symbol(), MODE_LOTSTEP);
+    volumeMin = MarketInfo(Symbol(), MODE_MINLOT);
+    volumeMax = MarketInfo(Symbol(), MODE_MAXLOT);
+
+    if (tickSize <= 0.0 || tickValue <= 0.0 || volumeStep <= 0.0 || volumeMin <= 0.0)
+        return false;
+    return true;
+}
+
+//+------------------------------------------------------------------+
+//| Check if it's a new trading day
+//+------------------------------------------------------------------+
+bool IsNewDay()
+{
+    static int lastDay = -1;
+    datetime currentTime = TimeCurrent();
+    int currentDay = TimeDay(currentTime);
+
+    if (currentDay != lastDay)
+    {
+        lastDay = currentDay;
+        return true;
+    }
+    return false;
+}
+
+//+------------------------------------------------------------------+
+//| Check if it's a new bar
+//+------------------------------------------------------------------+
+bool IsNewBar()
+{
+    static datetime lastBar = 0;
+    datetime currentBar = iTime(NULL, 0, 1);
+    if (lastBar != currentBar)
+    {
+        lastBar = currentBar;
+        return true;
+    }
+    return false;
+}
+
+//+------------------------------------------------------------------+
+//| Get ATR value
+//+------------------------------------------------------------------+
+double GetATRValue()
+{
+    double atr = iATR(NULL, 0, ATR_Period, 1);
+    return atr;
+}
+
+//+------------------------------------------------------------------+
+//| Get swing high
+//+------------------------------------------------------------------+
+double GetSwingHigh(int bars)
+{
+    double high = 0.0;
+    for (int i = 1; i <= bars; i++)
+    {
+        high = MathMax(high, iHigh(NULL, 0, i));
+    }
+    return high;
+}
+
+//+------------------------------------------------------------------+
+//| Get swing low
+//+------------------------------------------------------------------+
+double GetSwingLow(int bars)
+{
+    double low = EMPTY_VALUE;
+    for (int i = 1; i <= bars; i++)
+    {
+        low = MathMin(low, iLow(NULL, 0, i));
+    }
+    return low;
+}
+
+//+------------------------------------------------------------------+
+//| Calculate lot size based on risk
+//+------------------------------------------------------------------+
+double CalculateLotSize(double atrValue)
+{
+    double equity = AccountEquity();
+    if (equity <= 0.0)
+        return 0.0;
+
+    double riskAmount = equity * (RiskPerTradePercent / 100.0);
+    double stopDistance = SL_ATR_Multiplier * atrValue;
+    if (stopDistance <= 0.0)
+        return 0.0;
+
+    double ticks = stopDistance / tickSize;
+    double lotSize = riskAmount / (ticks * tickValue);
+
+    // Round to volume step
+    lotSize = MathFloor(lotSize / volumeStep) * volumeStep;
+
+    // Clamp to limits
+    if (lotSize < volumeMin)
+        lotSize = volumeMin;
+    if (volumeMax > 0.0 && lotSize > volumeMax)
+        lotSize = volumeMax;
+
+    return lotSize;
+}
+
+//+------------------------------------------------------------------+
+//| Get trade signal based on rejection patterns
+//+------------------------------------------------------------------+
+ENUM_TRADE_SIGNAL GetTradeSignal()
+{
+    double prevClose = iClose(NULL, 0, 1);
+    double prevOpen = iOpen(NULL, 0, 1);
+    double prevHigh = iHigh(NULL, 0, 1);
+    double prevLow = iLow(NULL, 0, 1);
+
+    bool isBearRejection = (prevClose < prevOpen &&
+                           (prevHigh - MathMax(prevClose, prevOpen)) >
+                           (prevClose - prevLow) * 1.5);
+    bool isBullRejection = (prevClose > prevOpen &&
+                           (MathMin(prevClose, prevOpen) - prevLow) >
+                           (prevHigh - prevClose) * 1.5);
+
+    if (isBullRejection)
+        return SIGNAL_BUY;
+    if (isBearRejection)
+        return SIGNAL_SELL;
+    return SIGNAL_NONE;
+}
+
+//+------------------------------------------------------------------+
+//| Place pending orders
+//+------------------------------------------------------------------+
+void PlacePendingOrders(ENUM_TRADE_SIGNAL signal, double buyEntry, double sellEntry,
+                        double buySL, double buyTP, double sellSL, double sellTP, double lotSize)
+{
+    datetime expiry = TimeCurrent() + ExpireMinutes * 60;
+
+    if (signal == SIGNAL_BUY && !HasPendingOrder(OP_BUYLIMIT))
+    {
+        if (OrderSend(Symbol(), OP_BUYLIMIT, lotSize, buyEntry, 0, buySL, buyTP, CommentTag, MagicNumber, expiry, clrNONE) == -1)
+            PrintFormat("BuyLimit failed: %d", GetLastError());
+    }
+    else if (signal == SIGNAL_SELL && !HasPendingOrder(OP_SELLLIMIT))
+    {
+        if (OrderSend(Symbol(), OP_SELLLIMIT, lotSize, sellEntry, 0, sellSL, sellTP, CommentTag, MagicNumber, expiry, clrNONE) == -1)
+            PrintFormat("SellLimit failed: %d", GetLastError());
+    }
+}
+
+//+------------------------------------------------------------------+
+//| Check if pending order exists
+//+------------------------------------------------------------------+
+bool HasPendingOrder(int type)
+{
+    for (int i = OrdersTotal() - 1; i >= 0; i--)
+    {
+        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
+        {
+            if (OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber && OrderType() == type)
+                return true;
+        }
+    }
+    return false;
+}
+
+//+------------------------------------------------------------------+
+//| Manage existing positions
+//+------------------------------------------------------------------+
+void ManagePositions(double swingHigh, double swingLow, double atrValue)
+{
+    ManageExits(swingHigh, swingLow);
+    ApplyTrailingStop(atrValue);
+}
+
+//+------------------------------------------------------------------+
+//| Manage position exits based on swing levels
+//+------------------------------------------------------------------+
+void ManageExits(double swingHigh, double swingLow)
+{
+    for (int i = OrdersTotal() - 1; i >= 0; i--)
+    {
+        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
+        {
+            if (OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber &&
+                (OrderType() == OP_BUY || OrderType() == OP_SELL))
+            {
+                double price = OrderOpenPrice();
+
+                if (OrderType() == OP_BUY && price < swingLow)
+                    OrderClose(OrderTicket(), OrderLots(), Bid, 3);
+                else if (OrderType() == OP_SELL && price > swingHigh)
+                    OrderClose(OrderTicket(), OrderLots(), Ask, 3);
+            }
+        }
+    }
+}
+
+//+------------------------------------------------------------------+
+//| Apply trailing stop
+//+------------------------------------------------------------------+
+void ApplyTrailingStop(double atrValue)
+{
+    for (int i = OrdersTotal() - 1; i >= 0; i--)
+    {
+        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
+        {
+            if (OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber &&
+                (OrderType() == OP_BUY || OrderType() == OP_SELL))
+            {
+                double openPrice = OrderOpenPrice();
+                double stopLoss = OrderStopLoss();
+
+                if (OrderType() == OP_BUY)
+                {
+                    double newSL = Bid - Trail_ATR_Multiplier * atrValue;
+                    if (newSL > stopLoss && newSL > openPrice)
+                        OrderModify(OrderTicket(), OrderOpenPrice(), newSL, OrderTakeProfit(), 0);
+                }
+                else if (OrderType() == OP_SELL)
+                {
+                    double newSL = Ask + Trail_ATR_Multiplier * atrValue;
+                    if ((stopLoss == 0.0 || newSL < stopLoss) && newSL < openPrice)
+                        OrderModify(OrderTicket(), OrderOpenPrice(), newSL, OrderTakeProfit(), 0);
+                }
+            }
+        }
+    }
+}
+
+//+------------------------------------------------------------------+
+//| Check daily loss limit
+//+------------------------------------------------------------------+
+void CheckDailyLoss()
+{
+    double equity = AccountEquity();
+    double drop = 100.0 * (startEquityToday - equity) / startEquityToday;
+    if (drop >= MaxDailyLossPercent)
+        tradingLocked = true;
+}
+
+//+------------------------------------------------------------------+
+//| Reset daily limits
+//+------------------------------------------------------------------+
+void ResetDailyLimits()
+{
+    startEquityToday = AccountEquity();
+    tradingLocked = false;
+}
 //+------------------------------------------------------------------+

