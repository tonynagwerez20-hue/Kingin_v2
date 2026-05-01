 //+------------------------------------------------------------------+
//|                                                   EURUSD 2.0.mq5 |
//|                                                      dark kingin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property link      "https://www.mql5.com"
#property version   "2.00"

#include <Trade/Trade.mqh>
CTrade trade;

//inputs
input int LookBackBars                          = 24;    //bars to look back for swings
input int ATR_Period                            = 14;    //Atr period
input double  SL_ATR_Multiplier                 = 1.5;   //stoploss multiplier
input double  TP_ATR_Multiplier                 = 3.0;   //take profit multiplier
input double Trail_ATR_Multiplier               = 1.0;   //trailing stoploss multiplier
input int ExpireMinutes                         = 60;    //pending order expiry
input double RiskPerTradePercent                = 0.1;   //% equity risked per trade
input double MaxDailyLossPercent                = 1.5;   //%equity max daily loss
input ulong MagicNumber                         = 202509;//magic number
input string CommentTag                         = "PA_Scalper_Trail";

//----Globals
datetime lastBarTime                            = 0;
double StartEquityToday                         = 0;
bool tradingLocked                              = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
  
  ResetDailyLimits();
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//---
   
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick(){
  
   datetime servertime = TimeCurrent();//reset lock each new day
   static datetime lastDay  = -1;
   if(servertime != lastDay){
      ResetDailyLimits();
      lastDay = servertime;
      }
   if(tradingLocked) return;          //stop trading if dailyloss exceeded
   
   MqlRates rates[];
   if(CopyRates(_Symbol,PERIOD_CURRENT,0,LookBackBars+5,rates[]) <= 0) return;
   datetime curBarTime = rates[].time;
   if(curBarTime == lastBarTime) return;
   lastBarTime = curBarTime;
   
   //find swing highs/lows
   double highs[],lows[];
   CopyHigh(_Symbol,PERIOD_CURRENT,1,LookBackBars,highs);
   CopyLow(_Symbol,PERIOD_CURRENT,1,LookBackBars,lows);
   
   double swingHigh = highs[ArrayMaximum(highs,LookBackBars,0)];
   double SwingLow = lows[ArrayMinimum(lows,LookBackBars,0)];
   
   //----ATR
   double atr[];
   if(CopyBuffer(iATR(_Symbol,PERIOD_CURRENT,ATR_Period),0,1,1,atr) <= 0) return;
   double ATR = atr[0];
   
   //calculate order levels
   double sellEntry = NormalizeDouble(swingHigh,_Digits);
   double buyEntry = NormalizeDouble(SwingLow,_Digits);
   
   //sell order sl and tp
   double sellSL = NormalizeDouble(sellEntry + SL_ATR_Multiplier * ATR,_Digits);
   double sellTP = NormalizeDouble(sellEntry - TP_ATR_Multiplier * ATR,_Digits);
   
   //buy order sl and tp
   double buySL = NormalizeDouble(buyEntry - SL_ATR_Multiplier * ATR,_Digits);
   double buyTP = NormalizeDouble(buyEntry + TP_ATR_Multiplier * ATR,_Digits);
   
   //positon sizing
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (RiskPerTradePercent / 100.0);
   double tickVal = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double stopDist = SL_ATR_Multiplier * ATR;
   double lotStep = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double minlot = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double lotSize = MathMax(minlot,NormalizeDouble(riskAmount / (stopDist / tickSize *tickVal),2));
   lotSize = MathFloor(lotSize / lotStep) * lotStep;
      
   //----tighter filters
   MqlRates prevBar = rates[];
   bool isBearRejection = (prevBar.close < prevBar.open && (prevBar.high - MathMax(prevBar.close,prevBar.open)) > (prevBar.close - prevBar.low) * 1.5);
   bool isBullRejection = (prevBar.close > prevBar.open && (MathMin(prevBar.close,prevBar.open) - prevBar.low) > (prevBar.high - prevBar.close) * 1.5);
   bool allowSell = isBearRejection;
   bool allowBuy = isBullRejection;
   
   //----place pending orders if allowed
   
   //----sell limit
   if(allowSell && !HasPending(ORDER_TYPE_SELL_LIMIT)){
      trade.SellLimit(lotSize,sellEntry,_Symbol,sellSL,sellTP,c,MagicNumber,servertime + ExpireMinutes * 60);
   }
   
   //-----buy limit
   if(allowBuy && !HasPending(ORDER_TYPE_BUY_LIMIT)){
      trade.BuyLimit(lotSize,buyEntry,_Symbol,buySL,buyTP,CommentTag,MagicNumber,servertime + ExpireMinutes * 60);
   }
   
   //----exit logic
   ManageExits(swingHigh,swingLow);
   ApplyingTrailingStop(ATR);
   CheckDailyLoss();
 }
   
//-------------------------------------------------------------------
//-----helpers-------------------------------------------------------
//-------------------------------------------------------------------
   
void ResetDailyLimits(){
   StartEquityToday = AccountInfoDouble(ACCOUNT_EQUITY);
   tradingLocked = false;      
}

bool HasPending(ENUM_ORDER_TYPE type){
   for(int i = OrdersTotal() - 1; i >= 0; i--){
      if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES)){
         If(orderSymbol() == _Symbol && OrderMagicNumber == (long)MagicNumber && OrderGetDouble(ORDER_TYPE) == type) return true;
      }   
   }return false;
 }
 
void ManageExits(double swingHigh, double swingLow){
   for(int i = PositionsTotal() - 1; i >= 0; i--){
      if(PositonSelectByINdex(i)){
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber){
            long type = PositionGetInteger(POSITION_TYPE);
            double price = PositionGetDouble(POSITION_PRICE_OPEN);
            if(type == POSITION_TYPE_BUY && price < swingLow){
               trade.PositionClose(_Symbol,0);
            }//new low invalidates buy
            if(type == POSITION_TYPE_SELL && price > swingHigh){
               trade.PositionClose(_Symbol,0);
            }//new high invalidates sell
         }
      }  
   } 
}

void AppltTrailingStop(double ATR){
   for(int i = PositionsTotal() - 1; i >= 0; i--){
      if(PositionSelectByIndex(i)){
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber){
            long type = PositionGetInteger(POSITION_TYPE);
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            double stopLoss = PositionGetDouble(POSITION_SL);
            double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
            double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
            if(type == POSITION_TYPE_BUY){
               double newSL = bid - Trail_ATR_Multiplier * ATR;
               if(newSL > stopLoss && newSL > openPrice){
                  trade.PositionModify(_Symbol,newSL,PositionGetDouble(POSITION_TP));
               }
            }
            if(type == POSITION_TYPE_SELL){
               double newSL = bid - Trail_ATR_Multiplier * ATR;
               if(stopLoss == 0 || newSL < stopLoss && newSL < openPrice){
                  trade.PositionModify(_Symbol,newSL,PositionGetDouble(POSITION_TP));
               }
            }
         }
      }
   }
}

void CheckDailyLoss(){
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double drop = 100.0 * (StartEquityToday - equity) / StartEquityToday;
   if(drop >= MaxDailyLossPercent){
      tradingLocked = true;
   }
}
 
 
 
//+------------------------------------------------------------------+
