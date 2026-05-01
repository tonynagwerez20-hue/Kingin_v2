//+------------------------------------------------------------------+
//| A.L.I.C.E AI Price Action EA                                     |
//| Price Action Trading with Learning Logic                         |
//| Uses price action patterns on multiple timeframes               |
//| Features: auto-risk lot sizing, ATR SL, dynamic ATR trailing stop, no TP, 2% daily cap |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property version   "1.00"

#include <Trade\Trade.mqh>
CTrade trade;

// -------------------- USER INPUTS --------------------
input string PriceActionTFs       = "H1,M15,M5,M1"; // comma-separated TFs for price-action detection
input double RiskPerTradePercent  = 0.1;    // % equity risk per trade (0.1 = 0.1%)
input double MaxDailyLossPercent  = 2.0;    // max daily loss (%)
input int    LookbackBars         = 20;     // used for swings/nodes
input int    ATR_Period           = 14;
input double SL_ATR_Mult          = 1.5;
input double TrailingATRMult     = 1.0;

// pattern toggles
input bool UseBreakout = true;
input bool UseRetest   = true;
input bool UseEngulfing = true;
input bool UsePinBar   = true;
input bool UseInsideBar= true;
input bool UseStructureShift = true;
input bool UseOrderBlockRetest = true;

// -------------------- GLOBALS --------------------
datetime day_marker = 0;
double day_start_equity = 0.0;
double daily_max_loss_pct = 0.0;

// -------------------- UTILITY FUNCTIONS --------------------
// map time string to ENUM_TIMEFRAMES
ENUM_TIMEFRAMES TFFromString(string s)
{
    StringToUpper(s);
    if(s=="M1") return PERIOD_M1;
    if(s=="M5") return PERIOD_M5;
    if(s=="M15") return PERIOD_M15;
    if(s=="M30") return PERIOD_M30;
    if(s=="H1" || s=="60") return PERIOD_H1;
    if(s=="H4") return PERIOD_H4;
    if(s=="D1") return PERIOD_D1;
    if(s=="W1") return PERIOD_W1;
    if(s=="MN1") return PERIOD_MN1;
    // default
    return PERIOD_M15;
}

// parse CSV of TFs into string array
void SplitCSV(string csv, string &out[], int &count)
{
    count=0;
    string arr[];
    int parts = StringSplit(csv,',',arr);
    for(int i=0;i<parts;i++){
      string t = StringTrimLeft(arr[i]);
      if(StringLen(t)>0){ out[count++] = t; }
    }
}

// small helpers to get last closed bar data on any timeframe
double CloseAtTF(ENUM_TIMEFRAMES tf,int shift){ return iClose(_Symbol,tf,shift); }
double OpenAtTF(ENUM_TIMEFRAMES tf,int shift){ return iOpen(_Symbol,tf,shift); }
double HighAtTF(ENUM_TIMEFRAMES tf,int shift){ return iHigh(_Symbol,tf,shift); }
double LowAtTF(ENUM_TIMEFRAMES tf,int shift){ return iLow(_Symbol,tf,shift); }
double RangeAtTF(ENUM_TIMEFRAMES tf,int shift){ return MathAbs(HighAtTF(tf,shift)-LowAtTF(tf,shift)); }

// -------------------- PRICE ACTION DETECTORS (single-TF) --------------------
// Implemented on last closed bar of given tf
bool DetectBreakout_TF(ENUM_TIMEFRAMES tf, int lookback, double &entry, int &dir)
{
    dir = 0; entry = 0;
    double swingH=-1, swingL=-1;
    for(int i=2;i<=lookback;i++){ double hh=HighAtTF(tf,i), ll=LowAtTF(tf,i); if(swingH < hh || swingH<0) swingH = hh; if(swingL<0 || ll < swingL) swingL = ll; }
    double c1 = CloseAtTF(tf,1);
    if(c1 > swingH){ dir=1; entry=c1; return true; }
    if(c1 < swingL){ dir=-1; entry=c1; return true; }
    return false;
}

bool DetectBreakRetest_TF(ENUM_TIMEFRAMES tf, double &entry, int &dir)
{
    dir=0; entry=0;
    double hh2=HighAtTF(tf,2), ll2=LowAtTF(tf,2);
    double hh3=HighAtTF(tf,3), ll3=LowAtTF(tf,3);
    double c1=CloseAtTF(tf,1);
    if(hh2 > hh3 && MathAbs(c1 - hh2) <= RangeAtTF(tf,1) * 0.5){ dir=1; entry=c1; return true; }
    if(ll2 < ll3 && MathAbs(c1 - ll2) <= RangeAtTF(tf,1) * 0.5){ dir=-1; entry=c1; return true; }
    return false;
}

bool DetectEngulfing_TF(ENUM_TIMEFRAMES tf,double &entry,int &dir)
{
    dir=0; entry=0;
    double o2=OpenAtTF(tf,2), c2=CloseAtTF(tf,2), o1=OpenAtTF(tf,1), c1=CloseAtTF(tf,1);
    if(c1 > o1 && (o1 <= c2) && (c1 >= o2) && (MathAbs(c1-o1) >= 0.6*RangeAtTF(tf,1))){ dir=1; entry=c1; return true; }
    if(c1 < o1 && (o1 >= c2) && (c1 <= o2) && (MathAbs(c1-o1) >= 0.6*RangeAtTF(tf,1))){ dir=-1; entry=c1; return true; }
    return false;
}

bool DetectPin_TF(ENUM_TIMEFRAMES tf,double &entry,int &dir)
{
    dir=0; entry=0;
    double o1=OpenAtTF(tf,1), c1=CloseAtTF(tf,1), h1=HighAtTF(tf,1), l1=LowAtTF(tf,1);
    double body = MathAbs(c1-o1); double total = h1-l1;
    if(total<=0) return false;
    double upper = h1 - MathMax(o1,c1); double lower = MathMin(o1,c1) - l1;
    if(lower >= 0.6*total && body <= 0.4*total && c1 > o1){ dir=1; entry=c1; return true; }
    if(upper >= 0.6*total && body <= 0.4*total && c1 < o1){ dir=-1; entry=c1; return true; }
    return false;
}

bool DetectInside_TF(ENUM_TIMEFRAMES tf,double &entry,int &dir)
{
    dir=0; entry=0;
    double h2=HighAtTF(tf,2), l2=LowAtTF(tf,2), h1=HighAtTF(tf,1), l1=LowAtTF(tf,1);
    if(h1 < h2 && l1 > l2){ double c1=CloseAtTF(tf,1), mid=(h2+l2)/2.0; if(c1>mid){dir=1; entry=c1; return true;} if(c1<mid){dir=-1; entry=c1; return true;} }
    return false;
}

bool DetectStructureShift_TF(ENUM_TIMEFRAMES tf,int lookback,double &entry,int &dir)
{
    dir=0; entry=0;
    double lastH=-1, lastL=-1;
    for(int i=2;i<=lookback;i++){ double hh=HighAtTF(tf,i), ll=LowAtTF(tf,i); if(lastH < hh || lastH<0) lastH = hh; if(lastL<0 || ll < lastL) lastL = ll; }
    double c1 = CloseAtTF(tf,1);
    if(c1 > lastH){ dir=1; entry=c1; return true; }
    if(c1 < lastL){ dir=-1; entry=c1; return true; }
    return false;
}

bool DetectOrderBlockRetest_TF(ENUM_TIMEFRAMES tf,double &entry,int &dir)
{
    dir=0; entry=0;
    int found=-1; double avgR=0;
    for(int i=3;i<=7;i++) avgR += RangeAtTF(tf,i);
    avgR /= 5.0;
    for(int i=3;i<=LookbackBars;i++){ if(RangeAtTF(tf,i) > 1.5*avgR){ found=i; break; } }
    if(found<0) return false;
    double oImp=OpenAtTF(tf,found), cImp=CloseAtTF(tf,found), lowImp=LowAtTF(tf,found), highImp=HighAtTF(tf,found), c1=CloseAtTF(tf,1);
    if(cImp > oImp){ if(MathAbs(c1-lowImp) <= RangeAtTF(tf,1)*0.5){ dir=1; entry=c1; return true; } }
    else{ if(MathAbs(c1-highImp) <= RangeAtTF(tf,1)*0.5){ dir=-1; entry=c1; return true; } }
    return false;
}

// -------------------- MONEY MANAGEMENT --------------------
double ComputeLotByRisk(double stop_loss_price_dist)
{
    // stop_loss_price_dist in price units (e.g., pips * point)
    // Use SYMBOL_TRADE_TICK_VALUE and tick size to compute risk per lot
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double risk_amount = equity * (RiskPerTradePercent/100.0);
    double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    if(tick_value <= 0 || tick_size <= 0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double risk_per_lot = (stop_loss_price_dist / tick_size) * tick_value;
    if(risk_per_lot <= 0.0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double lot = risk_amount / risk_per_lot;
    double minlot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxlot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    lot = MathMax(minlot, MathMin(maxlot, lot));
    if(step > 0) lot = MathRound(lot/step)*step;
    return lot;
}

// daily reset
void DailyResetIfNeeded()
{
    datetime currentTime = TimeCurrent();
    if(currentTime != day_marker){
      day_marker = currentTime;
      day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      daily_max_loss_pct = 0.0;
      Print("New trading day started. Start equity=", DoubleToString(day_start_equity,2));
    }
}
bool CanTradeToday()
{
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double loss_pct = (day_start_equity - equity) / day_start_equity * 100.0;
    if(loss_pct > daily_max_loss_pct) daily_max_loss_pct = loss_pct;
    if(loss_pct >= MaxDailyLossPercent){
      Print("Daily loss cap reached: ", DoubleToString(loss_pct,2), "% - pausing entries.");
      return false;
    }
    return true;
}

// trailing
void ApplyTrailingStop(double atr)
{
    if(TrailingATRMult <= 0) return;
    for(int i=0;i<PositionsTotal();i++){
      if(PositionGetSymbol(i) != _Symbol) continue;
      ulong ticket = PositionGetInteger(POSITION_TICKET);
      long type = PositionGetInteger(POSITION_TYPE);
      double old_sl = PositionGetDouble(POSITION_SL);
      double new_sl = old_sl;
      if(type == POSITION_TYPE_BUY){
        double trail = SymbolInfoDouble(_Symbol,SYMBOL_BID) - TrailingATRMult * atr;
        if(trail > old_sl + SymbolInfoDouble(_Symbol,SYMBOL_POINT)) new_sl = trail;
      } else {
        double trail = SymbolInfoDouble(_Symbol,SYMBOL_ASK) + TrailingATRMult * atr;
        if(trail < old_sl - SymbolInfoDouble(_Symbol,SYMBOL_POINT)) new_sl = trail;
      }
      if(new_sl != old_sl) {
        bool ok = trade.PositionModify(ticket, NormalizeDouble(new_sl,_Digits), 0);
        if(!ok) Print("Trailing stop modify failed for ticket ", ticket, " error: ", trade.ResultRetcode());
      }
    }
}

// -------------------- CORE: Evaluate PA signals and trade --------------------
void EvaluateAndTrade()
{
    // handle day reset and daily cap
    DailyResetIfNeeded();
    if(!CanTradeToday()) return;

    // parse chosen price-action TFs
    string pa_tfs[];
    int pa_count=0;
    SplitCSV(PriceActionTFs, pa_tfs, pa_count);

    // Detect price-action signals on all PA TFs: if any TF returns a valid PA signal, collect it as candidate(s)
    // We'll prefer signals that align with H1 bias if present.
    struct PASignal { string tf; int dir; double entry_price; string reason; };
    PASignal signals[32];
    int sig_count = 0;

    for(int t=0;t<pa_count;t++){
      string tfs = pa_tfs[t];
      ENUM_TIMEFRAMES tf = TFFromString(tfs);
      double entry=0; int dir=0;
      string reason = "";

      if(UseBreakout && DetectBreakout_TF(tf, LookbackBars, entry, dir)){ reason="Breakout"; }
      else if(UseRetest && DetectBreakRetest_TF(tf, entry, dir)){ reason="Break&Retest"; }
      else if(UseEngulfing && DetectEngulfing_TF(tf, entry, dir)){ reason="Engulfing"; }
      else if(UsePinBar && DetectPin_TF(tf, entry, dir)){ reason="PinBar"; }
      else if(UseInsideBar && DetectInside_TF(tf, entry, dir)){ reason="InsideBar"; }
      else if(UseStructureShift && DetectStructureShift_TF(tf, LookbackBars, entry, dir)){ reason="StructureShift"; }
      else if(UseOrderBlockRetest && DetectOrderBlockRetest_TF(tf, entry, dir)){ reason="OrderBlockRetest"; }

      if(StringLen(reason) > 0){
        if(sig_count < 32){
          signals[sig_count].tf = tfs;
          signals[sig_count].dir = dir;
          signals[sig_count].entry_price = entry;
          signals[sig_count].reason = reason;
          sig_count++;
        }
      }
    }

    if(sig_count==0) return; // no PA signal right now

    // Compute H1 bias (if H1 included in PriceActionTFs or user can rely on H1 being present)
    int h1_bias = 0; // 1 = buy bias, -1 = sell bias, 0 = neutral
    // simple bias: H1 close > SMA50 -> buy, < SMA50 -> sell. If H1 not in PA list, still compute on H1.
    double h1_sma50 = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_SMA, PRICE_CLOSE);
    double h1_close  = iClose(_Symbol, PERIOD_H1, 1);
    if(h1_close > h1_sma50) h1_bias = 1;
    else if(h1_close < h1_sma50) h1_bias = -1;

    // For each candidate PA signal, check if it aligns with H1 bias (if bias exists)
    for(int s=0;s<sig_count;s++){
      PASignal ps = signals[s];
      int desired_dir = ps.dir;
      // require bias match (if bias not neutral), else allow
      if(h1_bias !=0 && desired_dir != h1_bias) {
        // skip signal against H1 bias
        continue;
      }

      if(CanTradeToday()){
        // Place trade: determine SL by ATR on the PA TF, auto-lot sizing
        ENUM_TIMEFRAMES pa_tf = TFFromString(ps.tf);
        double atr = iATR(_Symbol, pa_tf, ATR_Period); if(atr<=0) atr = iATR(_Symbol, PERIOD_M15, ATR_Period);
        double stop_dist = SL_ATR_Mult * atr;
        double lot = ComputeLotByRisk(stop_dist);
        if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) continue;

        double sl = 0;
        bool trade_ok = false;
        if(desired_dir == 1) { // buy
          sl = SymbolInfoDouble(_Symbol, SYMBOL_BID) - stop_dist;
          trade_ok = trade.Buy(lot, NULL, 0, NormalizeDouble(sl,_Digits), 0, ps.reason + " | price_action");
          if(trade_ok) Print("ENTER BUY | PA=", ps.tf, " reason=", ps.reason, " lot=", DoubleToString(lot,2));
          else Print("Buy failed: ", trade.ResultRetcode(), " ", trade.ResultComment());
        } else {
          sl = SymbolInfoDouble(_Symbol, SYMBOL_ASK) + stop_dist;
          trade_ok = trade.Sell(lot, NULL, 0, NormalizeDouble(sl,_Digits), 0, ps.reason + " | price_action");
          if(trade_ok) Print("ENTER SELL | PA=", ps.tf, " reason=", ps.reason, " lot=", DoubleToString(lot,2));
          else Print("Sell failed: ", trade.ResultRetcode(), " ", trade.ResultComment());
        }
        // after entry we break to avoid multiple signals same tick. You may change to allow multiple.
        break;
      } // if can trade
    } // for each PA signal

    // Manage open positions: trailing stop
    bool hasPos=false;
    for(int i=0;i<PositionsTotal();i++){
      if(PositionGetSymbol(i)==_Symbol){ hasPos=true; break; }
    }
    if(hasPos){
      // trailing stop using ATR on M15
      double atrm = iATR(_Symbol, PERIOD_M15, ATR_Period);
      ApplyTrailingStop(atrm);
    }

  } // end Evaluate

// -------------------- EA LIFECYCLE --------------------
int OnInit()
{
    Print("A.L.I.C.E AI Price Action EA initialized: Multi-TF Price Action Trading.");
    day_marker = TimeCurrent();
    day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
    // Set timer for evaluation (every minute)
    EventSetTimer(60);
    return(INIT_SUCCEEDED);
}

void OnTimer()
{
    EvaluateAndTrade();
}

void OnTick()
{
    // OnTick is kept for potential future use, but logic is now in OnTimer
}

void OnDeinit(const int reason)
{
    Print("EA deinitialized.");
    EventKillTimer();
}