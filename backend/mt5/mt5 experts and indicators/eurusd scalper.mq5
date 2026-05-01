//+------------------------------------------------------------------+
//|                                               eurusd scalper.mq5 |
//|                                                      dark kingin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property link      "https://www.mql5.com"
#property version   "2.00"

#include <Trade/Trade.mqh>

input double Lots = 0.1;
input double RiskPercent = 2.0;

input int OrderDistancePoints = 100;
input int TpPoints = 300;
input int SlPoints = 100;
input int TslPoints = 50;
input int TslTriggerPoints = 75;

input ENUM_TIMEFRAMES TimeFrame = PERIOD_H1;
input int BarsN = 5; 
input int ExpirationHours = 50;

input int Magic = 17;
CTrade trade;
ulong buyPos, sellPos;

int TotalBars;
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit(){
   trade.SetExpertMagicNumber(Magic);
   

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason){
  
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick(){
   processPos(buyPos);
   processPos(sellPos);

   int bars =iBars(_Symbol,TimeFrame);
   if(TotalBars != bars){
      TotalBars = bars;
      
      
      
      if(buyPos <= 0){
         double low = findLow();
         if(low < 0){
            executeBuy(low); 
         }
      }
      if(sellPos >= 0){
         double high = findHigh();
         if(high > 0){
         executeSell(high);
         }
      }
   }
 }
 
void OnTradeTransaction(
   const MqlTradeTransaction& trans,
   const MqlTradeRequest&     request,
   const MqlTradeResult&      result
 ){
   
   if(trans.type == TRADE_TRANSACTION_ORDER_ADD){ 
      COrderInfo order;
      if(order.Select(trans.order)){
         if(order.Magic() == Magic){
            if (order.OrderType() == ORDER_TYPE_BUY_STOP){
               buyPos=order.Ticket();
            }else if (order.OrderType() == ORDER_TYPE_SELL_STOP){
               sellPos = order.Ticket();
            }
         }
      }
   }
} 
void processPos(ulong &posTicket){
  if(posTicket <= 0) return;
  if(OrderSelect(posTicket)) return;
   
   CPositionInfo pos;
   if(pos.SelectByTicket(posTicket)){
      posTicket = 0;
      return;
   }else{
      if(pos.PositionType() == POSITION_TYPE_BUY){
         double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
         
         if (bid > pos.PriceOpen() + TslTriggerPoints * _Point){
            double Sl = bid -TslPoints * _Point;
            Sl = NormalizeDouble(Sl,_Digits);
            
            if(Sl > pos.PositionType()){
               trade.PositionModify(pos.Ticket(),Sl,pos.TakeProfit());      
            }
         }
         
      }else if(pos.PositionType() == POSITION_TYPE_SELL){
         double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASKHIGH);
         
         if(ask < pos.PriceOpen() - TslTriggerPoints * _Point){
            double Sl = ask + TslPoints * _Point;
            
            if(Sl < pos.StopLoss() || pos.StopLoss() == 0){
            trade.PositionModify(pos.Ticket(),Sl,pos.TakeProfit());
            }
         }
      }
   }
 
       if(buyPos > 0 && PositionSelectByTicket(buyPos) && OrderSelect(buyPos)){
            buyPos = 0;
            }
            
            if(sellPos > 0 && PositionSelectByTicket(sellPos) && OrderSelect(sellPos)){
            sellPos = 0;
            }
    }
 
void executeBuy(double entry){
            
           entry = NormalizeDouble(entry,_Digits);
           
           double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
           if(ask > entry - OrderDistancePoints * _Point) return;
           
           double TP = entry + TpPoints * _Point;
           TP = NormalizeDouble(TP,_Digits);
           
           double Sl = entry - SlPoints * _Point;
           Sl = NormalizeDouble(Sl,_Digits);
           
           double lots = Lots;
           if(RiskPercent > 0) lots = calclots(entry-Sl);
           
           datetime expiration = iTime(_Symbol,TimeFrame,0) + ExpirationHours * PeriodSeconds(PERIOD_H1);
            
           trade.BuyLimit(lots,entry,_Symbol,Sl,TP, ORDER_TIME_SPECIFIED,expiration); 
           
           buyPos = trade.ResultOrder();
           
}

void executeSell(double entry){
            
           entry = NormalizeDouble(entry,_Digits);
           
           double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
           if(bid < entry + OrderDistancePoints * _Point) return;
           
            double TP = entry - TpPoints * _Point;
           TP = NormalizeDouble(TP,_Digits);
           
           double Sl = entry + SlPoints * _Point;
           Sl = NormalizeDouble(Sl,_Digits);
           
           double lots = Lots;
           if(RiskPercent > 0) lots = calclots(Sl-entry);
           
           datetime expiration = iTime(_Symbol,TimeFrame,0) + ExpirationHours * PeriodSeconds(PERIOD_H1);
            
           trade.SellLimit(lots,entry,_Symbol,Sl,TP, ORDER_TIME_SPECIFIED,expiration); 
           
           sellPos = trade.ResultOrder();
           
}

double calclots(double SlPoints){
   double risk = AccountInfoDouble(ACCOUNT_BALANCE) * RiskPercent / 100;
   
   double ticksize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double tickvalue = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double lotstep = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   
   double moneyPerLotstep = SlPoints / ticksize * tickvalue * lotstep;
   double Lots = MathFloor(risk / moneyPerLotstep) * lotstep;
   
   Lots = MathMin(Lots,SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX));
   Lots = MathMax(Lots,SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN));
   
   return Lots;
}
    
  
double findHigh(){
   double highestHigh = 0;
   for(int i = 0; i < 200; i++){
      double high = iHigh(_Symbol,TimeFrame,i);
      if (i > BarsN && iHighest(_Symbol,TimeFrame,MODE_HIGH,BarsN*2+1,i-5) == i){
         if (high > highestHigh){
            Print(high," ",i);
            return high;
         }
      }
         highestHigh = MathMax(high,highestHigh);
   }
     return -1;
 }
 
double findLow(){
  double lowestLow = DBL_MAX;
  for(int i = 0; i < 200; i++){
     double low = iLow(_Symbol,TimeFrame,i);
     if(low < lowestLow){
       return low;
     }
     lowestLow = MathMin(low,lowestLow);
  }
 return -1;
 } 
//+------------------------------------------------------------------+
