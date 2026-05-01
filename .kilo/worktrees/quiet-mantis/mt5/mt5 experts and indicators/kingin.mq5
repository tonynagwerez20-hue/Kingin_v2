//+------------------------------------------------------------------+
//|                                                       kingin.mq5 |
//|                                                      dark kingin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property link      "https://www.mql5.com"
#property version   "1.00"

#include <Trade\Trade.mqh>

input double  RiskPerPositionPercent = 0.1;     // percent risk per position (0.1 means 0.1%)
input double  MaxDailyLossPercent     = 1.5;     // max daily loss percent (1.5 means 1.5%)
input double  SL_In_Pips              = 50.0;    // stop loss in pips if not using ATR
input bool    UseATRForSL             = true;    // if true: use ATR to compute SL distance
input int     ATR_Period              = 14;      // ATR period
input double  ATR_Multiplier          = 1.0;     // ATR * multiplier -> stop in price units
input bool    ContinuousTrailing      = true;    // if true, continuously move SL to lock 50% profit
input int     MagicNumber             = 20250918; // magic number for EA positions
input ENUM_TIMEFRAMES SignalTF        = PERIOD_M15; // timeframe for optional demo signal
input int     EMA_Fast                = 8;       // demo EMA fast
input int     EMA_Slow                = 21;      // demo EMA slow
input bool    UseDemoSignal           = false;   // set true to enable demo EMA entries
input bool    AllowBuy                = true;
input bool    AllowSell               = true;
input bool    AllowManualReset        = true;    // allow pressing 'R' to reset today's lock

CTrade trade;

// runtime variables to track daily enforcement
double balance_at_day_start = 0.0;
datetime day_start_time = 0;
bool trading_locked_for_today = false;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(RiskPerPositionPercent <= 0) RiskPerPositionPercent == int 0.1;
   if(MaxDailyLossPercent <= 0) MaxDailyLossPercent == int 1.5;
   SetDayStart();
   EventSetTimer(5); // periodic checks every 5s
   Print("RiskMgrEA_v2 initialized. Press 'R' (chart focused) to reset daily lock if AllowManualReset=true.");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

//+------------------------------------------------------------------+
//| Timer handler                                                     |
//+------------------------------------------------------------------+
void OnTimer()
  {
   CheckDayChange();
   EnforceDailyLossClose();
   ManageOpenPositions();
  }

//+------------------------------------------------------------------+
//| Tick handler                                                      |
//+------------------------------------------------------------------+
void OnTick()
  {
   CheckDayChange();
   EnforceDailyLossClose();
   ManageOpenPositions();

   if(trading_locked_for_today) return;

   // optional demo entry
   if(UseDemoSignal)
     {
      int signal = CheckEntrySignal();
      if(signal == 1 && AllowBuy)  OpenMarketTradePublic(ORDER_TYPE_BUY);
      if(signal == -1 && AllowSell) OpenMarketTradePublic(ORDER_TYPE_SELL);
     }
  }

//+------------------------------------------------------------------+
//| Demo EMA crossover signal (optional)                             |
//+------------------------------------------------------------------+
int CheckEntrySignal()
  {
   double emaFast = iMA(_Symbol, PERIOD_M15, 0,MODE_EMA, PRICE_CLOSE, 1);
   double emaSlow = iMA(_Symbol, PERIOD_M15, 0, MODE_EMA, PRICE_CLOSE, 1);
   double emaFastPrev = iMA(_Symbol, PERIOD_M15, 0, MODE_EMA, PRICE_CLOSE, 2);
   double emaSlowPrev = iMA(_Symbol, PERIOD_M15, 0, MODE_EMA, PRICE_CLOSE, 2);

   if(emaFastPrev <= emaSlowPrev && emaFast > emaSlow) return 1;
   if(emaFastPrev >= emaSlowPrev && emaFast < emaSlow) return -1;
   return 0;
  }

//+------------------------------------------------------------------+
//| Set day start (midnight server time)                              |
//+------------------------------------------------------------------+
void SetDayStart()
  {
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   day_start_time = StructToTime(dt);
   balance_at_day_start = AccountInfoDouble(ACCOUNT_BALANCE);
   trading_locked_for_today = false;
   PrintFormat("Day start set: %s, balance_at_day_start=%.2f", TimeToString(day_start_time, TIME_DATE|TIME_SECONDS), balance_at_day_start);
  }

//+------------------------------------------------------------------+
//| Check day change and reset                                        |
//+------------------------------------------------------------------+
void CheckDayChange()
  {
   datetime now = TimeCurrent();
   MqlDateTime dt_now, dt_start;
   TimeToStruct(now, dt_now);
   TimeToStruct(day_start_time, dt_start);
   if(dt_now.day != dt_start.day || dt_now.mon != dt_start.mon || dt_now.year != dt_start.year)
      SetDayStart();
  }

//+------------------------------------------------------------------+
//| Maximum positions allowed by daily loss / risk per position       |
//+------------------------------------------------------------------+
int MaxPositionsAllowedToday()
  {
   double r = RiskPerPositionPercent / 100.0;
   double m = MaxDailyLossPercent / 100.0;
   if(r <= 0) return(0);
   int maxpos = (int)MathFloor(m / r);
   if(maxpos < 1) maxpos = 1;
   return maxpos;
  }

//+------------------------------------------------------------------+
//| Count open positions for this EA & symbol                         |
//+------------------------------------------------------------------+
int CountOpenPositions()
  {
   int count = 0;
   for(int i=0; i<PositionsTotal(); i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol)
            count++;
        }
     }
   return count;
  }

//+------------------------------------------------------------------+
//| Compute stopPips: either SL_In_Pips or ATR-based (in pips)        |
//+------------------------------------------------------------------+
double ComputeStopPips()
  {
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pip_multiplier = (digits==3 || digits==5) ? 10.0 : 1.0;

   if(UseATRForSL)
     {
      // ATR returns price units. Convert to pips.
      int atr_handle = iATR(_Symbol, _Period, 14); // ATR of last closed bar
      if(atr <= 0) return SL_In_Pips; // fallback
      double atr_pips = atr / _Point / pip_multiplier;
      double stopPips = atr_pips * ATR_Multiplier;
      // ensure not too small
      if(stopPips < 1.0) stopPips = 1.0;
      return stopPips;
     }
   else
     {
      if(SL_In_Pips <= 0) SL_In_Pips = 10.0;
      return SL_In_Pips;
     }
  }

//+------------------------------------------------------------------+
//| Calculate lot size given risk amount (money) and stop loss pips  |
//+------------------------------------------------------------------+
double CalculateLotByRisk(double riskMoney, double stopLossPips)
  {
   if(riskMoney <= 0 || stopLossPips <= 0) return 0;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pip_multiplier = (digits==3 || digits==5) ? 10.0 : 1.0;
   double stopLossPoints = stopLossPips * pip_multiplier;

   // tick_size/value approach
   double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0 || tick_value <= 0) return(0);

   double value_per_point_per_lot = tick_value / tick_size;
   double amount_lost_per_lot = stopLossPoints * value_per_point_per_lot;
   if(amount_lost_per_lot <= 0) return 0;

   double lots = riskMoney / amount_lost_per_lot;

   // Respect min/max lots and step
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(minLot <= 0 || maxLot <= 0 || step <= 0) return 0;

   double rounded = MathFloor(lots / step) * step;
   if(rounded < minLot) rounded = 0;
   if(rounded > maxLot) rounded = maxLot;

   // normalize to step decimals
   int precision = (int)MathMax(0, MathRound(MathLog10(1.0/step)));
   rounded = NormalizeDouble(rounded, precision);
   return rounded;
  }

//+------------------------------------------------------------------+
//| Public wrapper to open market orders using EA sizing/rules       |
//| You can call OpenMarketTradePublic(ORDER_TYPE_BUY) from other EA |
//+------------------------------------------------------------------+
void OpenMarketTradePublic(ENUM_ORDER_TYPE orderType)
  {
   if(trading_locked_for_today) 
     {
      Print("Trading locked for today: cannot open new trades.");
      return;
     }

   int current = CountOpenPositions();
   int allowed = MaxPositionsAllowedToday();
   if(current >= allowed)
     {
      PrintFormat("Max positions reached: %d/%d", current, allowed);
      return;
     }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * (RiskPerPositionPercent/100.0);

   double stopPips = ComputeStopPips();
   double lot = CalculateLotByRisk(riskMoney, stopPips);
   if(lot <= 0)
     {
      Print("Lot calculation returned zero or below min lot -> not opening trade.");
      return;
     }

   // price, sl, tp calculation
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pip_multiplier = (digits==3 || digits==5) ? 10.0 : 1.0;
   double stop_points = stopPips * pip_multiplier;
   double price = (orderType==ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl_price, tp_price;
   if(orderType == ORDER_TYPE_BUY)
     {
      sl_price = price - stop_points * _Point;
      tp_price = price + 3.0 * stop_points * _Point;
     }
   else
     {
      sl_price = price + stop_points * _Point;
      tp_price = price - 3.0 * stop_points * _Point;
     }

   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request); ZeroMemory(result);

   request.action   = TRADE_ACTION_DEAL;
   request.symbol   = _Symbol;
   request.volume   = lot;
   request.magic    = MagicNumber;
   request.deviation= 10;
   request.type     = orderType;
   request.price    = price;
   request.sl       = NormalizeDouble(sl_price, digits);
   request.tp       = NormalizeDouble(tp_price, digits);
   request.type_filling = ORDER_FILLING_FOK;
   request.type_time    = ORDER_TIME_GTC;

   if(!OrderSend(request, result))
     {
      PrintFormat("OrderSend failed: %d", GetLastError());
      return;
     }

   if(result.retcode == TRADE_RETCODE_DONE)
      PrintFormat("Opened %s lot=%.2f price=%.5f SL=%.5f TP=%.5f", EnumToString(orderType), lot, request.price, request.sl, request.tp);
   else
      PrintFormat("OpenMarketTradePublic retcode=%d comment=%s", result.retcode, result.comment);
  }

//+------------------------------------------------------------------+
//| Manage open positions: continuous trailing logic (50% lock)      |
//+------------------------------------------------------------------+
void ManageOpenPositions()
  {
   if(!ContinuousTrailing) return;

   for(int i=PositionsTotal()-1; i>=0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
      double current_price = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      int type = (int)PositionGetInteger(POSITION_TYPE);

      // if not in profit, skip
      if(type == POSITION_TYPE_BUY && current_price <= entry_price) continue;
      if(type == POSITION_TYPE_SELL && current_price >= entry_price) continue;

      // desired SL locks 50% of unrealized profit:
      double desired_sl;
      if(type == POSITION_TYPE_BUY)
         desired_sl = entry_price + 0.5 * (current_price - entry_price);
      else
         desired_sl = entry_price - 0.5 * (entry_price - current_price);

      // apply only if it's an improvement (move SL forward only)
      int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      if(type == POSITION_TYPE_BUY && desired_sl > sl + Point())
        ModifyPositionSL(PositionGetInteger(POSITION_TICKET), NormalizeDouble(desired_sl, digits));
      if(type == POSITION_TYPE_SELL && desired_sl < sl - Point())
        ModifyPositionSL(PositionGetInteger(POSITION_TICKET), NormalizeDouble(desired_sl, digits));
     }
  }

//+------------------------------------------------------------------+
//| Modify position SL only                                           |
//+------------------------------------------------------------------+
void ModifyPositionSL(ulong ticket, double new_sl)
  {
   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req); ZeroMemory(res);

   if(!PositionSelectByTicket(ticket)) return;
   string sym = PositionGetString(POSITION_SYMBOL);
   req.action = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol = sym;
   req.sl = new_sl;
   req.tp = PositionGetDouble(POSITION_TP);

   if(!OrderSend(req, res))
     {
      PrintFormat("Modify SL OrderSend failed: %d", GetLastError());
     }
   else
     {
      if(res.retcode == TRADE_RETCODE_DONE)
         PrintFormat("Modified SL of ticket %I64u to %.5f", ticket, req.sl);
      else
         PrintFormat("Modify SL retcode=%d comment=%s", res.retcode, res.comment);
     }
  }

//+------------------------------------------------------------------+
//| Enforce daily loss: close all when daily loss >= MaxDailyLoss    |
//+------------------------------------------------------------------+
void EnforceDailyLossClose()
  {
   double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double pnl_since_start = current_balance - balance_at_day_start;
   double allowed_loss = balance_at_day_start * (MaxDailyLossPercent/100.0);

   if(pnl_since_start <= -allowed_loss && !trading_locked_for_today)
     {
      CloseAllEAOrders();
      trading_locked_for_today = true;
      PrintFormat("Daily loss limit hit: closed positions and locked trading for today. loss=%.2f allowed=%.2f", -pnl_since_start, allowed_loss);
     }
  }

//+------------------------------------------------------------------+
//| Close all positions for this EA (same magic) and symbol          |
//+------------------------------------------------------------------+
void CloseAllEAOrders()
  {
   for(int i=PositionsTotal()-1; i>=0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      double vol = PositionGetDouble(POSITION_VOLUME);
      long type = PositionGetInteger(POSITION_TYPE);
      MqlTradeRequest req;
      MqlTradeResult  res;
      ZeroMemory(req); ZeroMemory(res);

      req.action = TRADE_ACTION_DEAL;
      req.position = ticket;
      req.symbol   = _Symbol;
      req.volume   = vol;
      req.type     = (type==POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.price    = (req.type==ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      req.deviation = 10;
      req.type_filling = ORDER_FILLING_FOK;
      req.type_time = ORDER_TIME_GTC;

      if(!OrderSend(req, res))
         PrintFormat("Close position failed: %d", GetLastError());
      else
         PrintFormat("Close pos retcode=%d comment=%s", res.retcode, res.comment);
     }
  }

//+------------------------------------------------------------------+
//| Utility enum->string                                              |
//+------------------------------------------------------------------+
string EnumToString(ENUM_ORDER_TYPE t)
  {
   if(t==ORDER_TYPE_BUY) return "BUY";
   if(t==ORDER_TYPE_SELL) return "SELL";
   return "UNKNOWN";
  }

//+------------------------------------------------------------------+
//| Chart event: listen for manual reset key (R)                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   // CHARTEVENT_KEYDOWN = id constant from MQL5
   // lparam contains the virtual-key code; ASCII 'R' = 82
   if(!AllowManualReset) return;
   if(id == CHARTEVENT_KEYDOWN)
     {
      int key = (int)lparam;
      if(key == 82) // 'R'
        {
         // Reset day start and unlock trading
         SetDayStart();
         trading_locked_for_today = false;
         Print("Manual reset (R) performed: trading unlocked and day start reset.");
        }
     }
  }
//+------------------------------------------------------------------+

