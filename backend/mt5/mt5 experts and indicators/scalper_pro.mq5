//+------------------------------------------------------------------+
//|                                  HyperScalper_V5_SizeFixed.mq5   |
//|                                  Copyright 2024, Trading Systems |
//|           Safe SL/TP Logic for Small Accounts & Slow Hardware    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024"
#property version   "5.00"
#property strict

#include <Trade\Trade.mqh>

//--- INPUT PARAMETERS
input int      InpPeriod      = 10;          
input double   InpDeviations  = 2.0;         
input double   InpRiskPercent = 1.0;         
input int      InpMaxPositions = 10;          
input int      InpMinInterval  = 1;          
input int      InpDefaultSL    = 150;        // Default SL in Points (15 pips)
input int      InpDefaultTP    = 350;        // Default TP in Points (35 pips)
input int      InpMaxSpread    = 25;         

//--- GLOBAL VARIABLES
CTrade         trade;
int            handleBands;
bool           is_system_paused = false;
double         starting_equity;
datetime       last_alert_day;

int OnInit() {
   starting_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   handleBands = iBands(_Symbol, PERIOD_M1, InpPeriod, 0, InpDeviations, PRICE_CLOSE);
   trade.SetAsyncMode(true); 
   return(INIT_SUCCEEDED);
}

void OnTick() {
   if(is_system_paused || PositionsTotal() >= InpMaxPositions) return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread) return;

   double upper[], lower[], middle[];
   CopyBuffer(handleBands, 1, 0, 1, upper);
   CopyBuffer(handleBands, 2, 0, 1, lower);
   CopyBuffer(handleBands, 0, 0, 1, middle);

   double Ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double Bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // --- DYNAMIC SIZE CORRECTION ---
   // Get broker's minimum distance (Stop Level)
   int stopLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   
   // Ensure SL/TP are at least 'StopLevel + Spread' points away to avoid Error 130
   int safeSL = MathMax(InpDefaultSL, stopLevel + (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD));
   int safeTP = MathMax(InpDefaultTP, stopLevel + 5); 

   // Normalize to Digits (Ensures 1.08543 isn't sent as 1.0854321)
   double slPrice, tpPrice;

   if(Ask < lower[0]) // BUY SIGNAL
   {
      slPrice = NormalizeDouble(Ask - (safeSL * _Point), _Digits);
      tpPrice = NormalizeDouble(Ask + (safeTP * _Point), _Digits);
      double lot = CalculateLotSize(safeSL);
      trade.Buy(lot, _Symbol, Ask, slPrice, tpPrice, "Scalper_pro_V5_BUY");
   }
   
   if(Bid > upper[0]) // SELL SIGNAL
   {
      slPrice = NormalizeDouble(Bid + (safeSL * _Point), _Digits);
      tpPrice = NormalizeDouble(Bid - (safeTP * _Point), _Digits);
      double lot = CalculateLotSize(safeSL);
      trade.Sell(lot, _Symbol, Bid, slPrice, tpPrice, "Scalper_pro_V5_SELL");
   }
}

double CalculateLotSize(int sl_pts) {
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   // Risk $0.27 per trade (1% of $27)
   double riskMoney = balance * (InpRiskPercent / 100.0);
   double lot = riskMoney / (sl_pts * tickValue);
   
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   lot = MathFloor(lot / step) * step;
   return (lot < minLot) ? minLot : lot;
}