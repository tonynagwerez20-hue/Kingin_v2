//+------------------------------------------------------------------+
//|                                                          ICT.mq5 |
//|                                                      dark kingin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

// ------------------ User Inputs ------------------------
input double RiskPercentPerTrade = 0.1;   // % equity risk per trade
input double MaxDailyLossPercent = 1.5;   // Max daily drawdown
input double ATR_Multiplier = 1.5;        // SL = ATR * multiplier
input double TP_Multiplier  = 3.0;        // TP = SL * multiplier
input int LookbackBars = 50;              // Bars to look back for FVG/OB
input int PullbackBars = 8;               // Bars to detect retrace
input int MagicNumber = 505050;
input bool UseTrailing = true;
input int TrailingStartPips = 20;
input int TrailingStepPips = 5;
input double MinBalanceToTrade = 10;
input int Slippage = 6;

// ICT session windows (GMT)
input int Window1_StartHour = 10; input int Window1_EndHour = 11;
input int Window2_StartHour = 14; input int Window2_EndHour = 15;
input int Window3_StartHour = 20; input int Window3_EndHour = 21;

// ------------------ Global Variables -------------------
datetime lastTradeDay = 0;
double dailyEquityHigh = 0;
double dailyEquityLow  = 0;
bool dailyLocked = false;

// ------------------ FVG + OB Structures -------------------
struct FVGZone {
   double top;
   double bottom;
   int direction; // +1 bullish, -1 bearish
   datetime created_time;
   bool active;
   int ageBars;
   string name;
};
FVGZone FVGs[];

struct OBZone {
   double top;
   double bottom;
   int direction; // +1 bullish OB, -1 bearish OB
   string name;
   bool active;
};
OBZone OBs[];

// ------------------ Helper Functions -------------------
double GetATR(int period)
{
   int handle = iATR(_Symbol, PERIOD_M1, period);
   if(handle==INVALID_HANDLE) return 0;
   double buf[];
   if(CopyBuffer(handle,0,1,1,buf)!=1){ IndicatorRelease(handle); return 0; }
   IndicatorRelease(handle);
   return buf[0];
}

double CalculateLotSize(double stopPrice)
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * RiskPercentPerTrade/100.0;
   double entry = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double stopDistance = MathAbs(entry-stopPrice);
   if(stopDistance<=0) return 0;
   double tickValue = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickValue==0 || tickSize==0) { double approxLots=riskAmount/(stopDistance/_Point)/10; return approxLots; }
   double valuePerPointPerLot = tickValue/tickSize;
   double lots = riskAmount/(stopDistance*valuePerPointPerLot);
   double minLot = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0) step=0.01;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   lots = MathFloor(lots/step+0.000001)*step;
   if(lots<minLot) lots=minLot;
   return lots;
}

bool IsWithinAnyWindow()
{
   datetime t = TimeGMT();
   MqlDateTime mt; TimeToStruct(t, mt);
   int h = mt.hour;
   bool w1 = (Window1_StartHour <= Window1_EndHour) ? (h >= Window1_StartHour && h < Window1_EndHour) : (h >= Window1_StartHour || h < Window1_EndHour);
   bool w2 = (Window2_StartHour <= Window2_EndHour) ? (h >= Window2_StartHour && h < Window2_EndHour) : (h >= Window2_StartHour || h < Window2_EndHour);
   bool w3 = (Window3_StartHour <= Window3_EndHour) ? (h >= Window3_StartHour && h < Window3_EndHour) : (h >= Window3_StartHour || h < Window3_EndHour);
   return w1 || w2 || w3;
}

void UpdateDailyLock()
{
   datetime today = (datetime)(TimeCurrent()/86400)*86400;
   if(lastTradeDay!=today)
   {
      lastTradeDay=today;
      dailyEquityHigh=AccountInfoDouble(ACCOUNT_EQUITY);
      dailyEquityLow=dailyEquityHigh;
      dailyLocked=false;
   }
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity>dailyEquityHigh) dailyEquityHigh=equity;
   if(equity<dailyEquityLow) dailyEquityLow=equity;
   double lossPercent=(dailyEquityHigh-equity)/dailyEquityHigh*100.0;
   if(lossPercent>=MaxDailyLossPercent) dailyLocked=true;
}

bool CanTradeNow()
{
   if(dailyLocked) return false;
   if(AccountInfoDouble(ACCOUNT_BALANCE)<MinBalanceToTrade) return false;
   if(!IsWithinAnyWindow()) return false;
   return true;
}

// ------------------ FVG Functions -------------------
bool DetectLatestFVG(FVGZone &zone, int lookback=50, double minGapPips=0)
{
   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_M1, 0, lookback+5, rates);
   if(copied<3) return false;

   for(int i=2; i<copied; i++)
   {
      double A_high = rates[i].high;
      double A_low  = rates[i].low;
      double C_high = rates[i-2].high;
      double C_low  = rates[i-2].low;

      if(A_high < C_low) { double gap=(C_low-A_high)/_Point; if(gap>=minGapPips){ zone.top=C_low; zone.bottom=A_high; zone.direction=+1; zone.created_time=rates[i-2].time; zone.active=true; zone.ageBars=0; zone.name="FVG_"+IntegerToString(TimeCurrent()); return true; } }
      if(A_low > C_high) { double gap=(A_low-C_high)/_Point; if(gap>=minGapPips){ zone.top=A_low; zone.bottom=C_high; zone.direction=-1; zone.created_time=rates[i-2].time; zone.active=true; zone.ageBars=0; zone.name="FVG_"+IntegerToString(TimeCurrent()); return true; } }
   }
   zone.active=false;
   return false;
}

void AddFVGToChart(FVGZone &fvg)
{
   ObjectCreate(0,fvg.name,OBJ_RECTANGLE,0,TimeCurrent(),fvg.top,TimeCurrent()+3600,fvg.bottom);
   ObjectSetInteger(0,fvg.name,OBJPROP_COLOR,(fvg.direction==+1?clrGreen:clrRed));
   ObjectSetInteger(0,fvg.name,OBJPROP_STYLE,STYLE_DOT);
   ObjectSetInteger(0,fvg.name,OBJPROP_WIDTH,2);
   ArrayResize(FVGs,ArraySize(FVGs)+1);
   FVGs[ArraySize(FVGs)-1]=fvg;
}

void UpdateFVGs()
{
   MqlRates rates[];
   CopyRates(_Symbol,PERIOD_M1,0,1,rates);
   double high= rates[0].high;
   double low = rates[0].low;

   for(int i=ArraySize(FVGs)-1;i>=0;i--)
   {
      FVGs[i].ageBars++;
      if((FVGs[i].direction==+1 && low <= FVGs[i].bottom) ||
         (FVGs[i].direction==-1 && high >= FVGs[i].top) ||
         FVGs[i].ageBars>8)
      {
         ObjectDelete(0, FVGs[i].name);
         ArrayRemove(FVGs,i);
      }
   }
}

// ------------------ OB Functions -------------------
bool DetectOrderBlock(bool bullish, double &obHigh, double &obLow, int lookback=50)
{
   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_M1, 0, lookback, rates);
   if(copied<2) return false;

   for(int i=1; i<copied; i++)
   {
      double open = rates[i].open;
      double close = rates[i].close;

      if(bullish && close<open) { obHigh=rates[i].high; obLow=rates[i].low; return true; }
      if(!bullish && close>open){ obHigh=rates[i].high; obLow=rates[i].low; return true; }
   }
   return false;
}

void AddOBToChart(double top,double bottom,int direction)
{
   OBZone ob;
   ob.top=top; ob.bottom=bottom; ob.direction=direction; ob.active=true;
   ob.name="OB_"+IntegerToString(TimeCurrent());
   ObjectCreate(0,ob.name,OBJ_RECTANGLE,0,TimeCurrent(),top,TimeCurrent()+3600,bottom);
   ObjectSetInteger(0,ob.name,OBJPROP_COLOR,(direction==+1?clrGreen:clrRed));
   ObjectSetInteger(0,ob.name,OBJPROP_STYLE,STYLE_SOLID);
   ObjectSetInteger(0,ob.name,OBJPROP_WIDTH,2);
   ArrayResize(OBs,ArraySize(OBs)+1);
   OBs[ArraySize(OBs)-1]=ob;
}

// ------------------ Trailing Stop -------------------
void TrailingStop()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      if(!PositionSelectByTicket(PositionGetTicket(i))) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double price = PositionGetDouble(POSITION_PRICE_CURRENT);
      int type = (int)PositionGetInteger(POSITION_TYPE);
      if(type == POSITION_TYPE_BUY)
      {
         double newSL = price - TrailingStartPips * _Point;
         if(newSL > sl)
         {
            trade.PositionModify(PositionGetTicket(i), newSL, tp);
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double newSL = price + TrailingStartPips * _Point;
         if(newSL < sl)
         {
            trade.PositionModify(PositionGetTicket(i), newSL, tp);
         }
      }
   }
}

// ------------------ Event Handlers -------------------
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   for(int i=0;i<ArraySize(FVGs);i++) ObjectDelete(0, FVGs[i].name);
   for(int i=0;i<ArraySize(OBs);i++) ObjectDelete(0, OBs[i].name);
}

void OnTick()
{
   UpdateDailyLock();
   if(!CanTradeNow()) return;

   static datetime lastBar = 0;
   datetime currentBar = iTime(_Symbol, PERIOD_M1, 0);
   if(lastBar == currentBar) return;
   lastBar = currentBar;

   UpdateFVGs();

   // Detect and add FVG
   FVGZone newFVG;
   if(DetectLatestFVG(newFVG, LookbackBars))
   {
      AddFVGToChart(newFVG);
   }

   // Detect and add OB
   double obHigh, obLow;
   if(DetectOrderBlock(true, obHigh, obLow, LookbackBars))
   {
      AddOBToChart(obHigh, obLow, +1);
   }
   if(DetectOrderBlock(false, obHigh, obLow, LookbackBars))
   {
      AddOBToChart(obHigh, obLow, -1);
   }

   // Check for entry on FVGs
   for(int i=0; i<ArraySize(FVGs); i++)
   {
      if(!FVGs[i].active) continue;
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(FVGs[i].direction == 1 && bid >= FVGs[i].top)
      {
         double entry = ask;
         double atr = GetATR(14);
         double sl = entry - atr * ATR_Multiplier;
         double tp = entry + atr * ATR_Multiplier * TP_Multiplier;
         double lots = CalculateLotSize(sl);
         trade.Buy(lots, _Symbol, entry, sl, tp, "FVG Buy");
         FVGs[i].active = false;
      }
      else if(FVGs[i].direction == -1 && ask <= FVGs[i].bottom)
      {
         double entry = bid;
         double atr = GetATR(14);
         double sl = entry + atr * ATR_Multiplier;
         double tp = entry - atr * ATR_Multiplier * TP_Multiplier;
         double lots = CalculateLotSize(sl);
         trade.Sell(lots, _Symbol, entry, sl, tp, "FVG Sell");
         FVGs[i].active = false;
      }
   }

   // Check for entry on OBs
   for(int i=0; i<ArraySize(OBs); i++)
   {
      if(!OBs[i].active) continue;
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(OBs[i].direction == 1 && bid >= OBs[i].top)
      {
         double entry = ask;
         double atr = GetATR(14);
         double sl = entry - atr * ATR_Multiplier;
         double tp = entry + atr * ATR_Multiplier * TP_Multiplier;
         double lots = CalculateLotSize(sl);
         trade.Buy(lots, _Symbol, entry, sl, tp, "OB Buy");
         OBs[i].active = false;
      }
      else if(OBs[i].direction == -1 && ask <= OBs[i].bottom)
      {
         double entry = bid;
         double atr = GetATR(14);
         double sl = entry + atr * ATR_Multiplier;
         double tp = entry - atr * ATR_Multiplier * TP_Multiplier;
         double lots = CalculateLotSize(sl);
         trade.Sell(lots, _Symbol, entry, sl, tp, "OB Sell");
         OBs[i].active = false;
      }
   }

   if(UseTrailing) TrailingStop();
}
//+------------------------------------------------------------------+
