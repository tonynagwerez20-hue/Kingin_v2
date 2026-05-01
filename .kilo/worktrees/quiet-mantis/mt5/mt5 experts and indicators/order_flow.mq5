  //+------------------------------------------------------------------+
//| PriceAction_Orderflow_Delta_EA_v8_full.mq5                       |
//| Multi-TF Price Action + Delta Entry Setups (Surge/Transition/Flip)|
//| Uses price action on user-chosen timeframes and delta patterns   |
//| (Delta API: single-TF by default; optional multi-TF if API supports ?tf=) |
//| Features: auto-risk lot sizing (RiskPerTradePercent), ATR SL,    |
//| dynamic ATR trailing stop, no TP, exit on delta flip, 2% daily cap |
//+------------------------------------------------------------------+
#property copyright "dark kingin"
#property version   "1.00"

#include <Trade\Trade.mqh>
CTrade trade;

// -------------------- USER INPUTS --------------------
input string PriceActionTFs       = "H1,M15,M5,M1"; // comma-separated TFs for price-action detection
input string DeltaAPI_TF          = "M15";          // timeframe the API returns when in single-TF mode
input bool   UseMultiTFDelta      = false;          // set true if API supports /latest_signal?tf=...
input string DeltaTFs             = "M15,M5,M1";   // when UseMultiTFDelta=true, list of delta TFs to query
input string api_url              = "http://127.0.0.1:5000/latest_signal";
input string api_key              = "";
input int    PollSeconds          = 1;

// strategy / risk inputs
input double RiskPerTradePercent  = 0.1;    // % equity risk per trade (0.1 = 0.1%)
input double MaxDailyLossPercent  = 2.0;    // max daily loss (%)
input int    LookbackBars         = 20;     // used for swings/nodes
input int    ATR_Period           = 14;
input double SL_ATR_Mult          = 1.5;
input double TrailingATRMult     = 1.0;
input double DeltaThreshold      = 20.0;  // minimal delta for direction
input double DeltaImpulseThreshold = 35.0; // impulse threshold for surge/flip
input double FlipThreshold       = 200.0; // large change for Delta Flip (absolute diff)
input bool   RequireCumDeltaDirection = true;

// pattern toggles
input bool UseBreakout = true;
input bool UseRetest   = true;
input bool UseEngulfing = true;
input bool UsePinBar   = true;
input bool UseInsideBar= true;
input bool UseStructureShift = true;
input bool UseOrderBlockRetest = true;

// delta setup toggles
input bool UseDeltaSurge      = true;
input bool UseDeltaTransition = true;
input bool UseDeltaFlip       = true;

// -------------------- GLOBALS --------------------
datetime last_fetch = 0;
datetime day_marker = 0;
double day_start_equity = 0.0;
double daily_max_loss_pct = 0.0;

// For delta history windows (per tf string): maintain last N samples
#define DELTA_WINDOW 8
struct DeltaSample {
   double delta;
   double cum_delta;
   double max_delta;
   double min_delta;
   datetime  t;
};
struct DeltaWindow {
   DeltaSample buf[DELTA_WINDOW];
   int head; // next write pos
   int count;
   void Clear(){ head=0; count=0; for(int i=0;i<DELTA_WINDOW;i++){ buf[i].delta=0; buf[i].cum_delta=0; buf[i].max_delta=0; buf[i].min_delta=0; buf[i].t=0; } }
   void Init(){ Clear(); }
   void Push(double d,double c,double mx,double mn,datetime time){
     buf[head].delta=d; buf[head].cum_delta=c; buf[head].max_delta=mx; buf[head].min_delta=mn; buf[head].t=time;
     head = (head+1) % DELTA_WINDOW;
     if(count<DELTA_WINDOW) count++;
   }
   // get last i-th: i=1 -> last pushed, i=2 -> one before, etc.
   DeltaSample Last(int i){
     DeltaSample s; s.delta=0; s.cum_delta=0; s.max_delta=0; s.min_delta=0; s.t=0;
     if(i<1 || i>count) return s;
     int idx = (head - i + DELTA_WINDOW) % DELTA_WINDOW;
     return buf[idx];
   }
};


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

// store delta windows by TF string (we will maintain up to a few TFs)
#define MAX_TF_HANDLES 8
string DeltaTFList[MAX_TF_HANDLES];
DeltaWindow DeltaWindows[MAX_TF_HANDLES];
int DeltaTFCount = 0;

// find index in DeltaTFList
int FindDeltaTFIndex(string tf)
{
   for(int i=0;i<DeltaTFCount;i++) if(DeltaTFList[i]==tf) return i;
   return -1;
}
int EnsureDeltaTF(string tf)
{
   int idx = FindDeltaTFIndex(tf);
   if(idx>=0) return idx;
   if(DeltaTFCount < MAX_TF_HANDLES){
     DeltaTFList[DeltaTFCount] = tf;
     DeltaWindows[DeltaTFCount].Init();
     DeltaTFCount++;
     return DeltaTFCount-1;
   }
   return -1;
}

// -------------------- API FETCH & PARSING --------------------
// Fetch one timeframe from API. If UseMultiTFDelta=false, tf param is ignored and API is called once.
bool FetchDeltaForTF(string tf, double &delta, double &cum_delta, double &max_d, double &min_d)
{
   delta = cum_delta = max_d = min_d = 0.0;
   string url = api_url;
   if(UseMultiTFDelta){
     // append query param
     if(StringFind(api_url,"?")>=0) url = api_url + "&tf=" + tf;
     else url = api_url + "?tf=" + tf;
   }
   string headers = "X-API-KEY: " + api_key + "\r\n";
   char result[];//  output array for response body
   string result_headers;// output string for response headers
   char data[];//
   int res = WebRequest("GET", url, headers, 5000,data,result,result_headers);
   if(res != 200){
     // failed - leave zeros
     Print("WebRequest failed code=",res," url=",url);
     return false;
   }
   string body = CharArrayToString(result);
   int p,e;
   if(StringFind(body,"\"delta\"")>=0)
   {
      p = StringFind(body,"\"delta\"");
      p = StringFind(body,":",p);
      e = StringFind(body,",",p);
      if(e<0) e = StringFind(body,"}",p);
      string num = StringSubstr(body,p+1,e-p-1);
      delta = StringToDouble(StringTrimRight(num));
   }
   if(StringFind(body,"\"cumulative_delta\"")>=0)
   {
      p = StringFind(body,"\"cumulative_delta\"");
      p = StringFind(body,":",p);
      e = StringFind(body,",",p);
      if(e<0) e = StringFind(body,"}",p);
      string num = StringSubstr(body,p+1,e-p-1);
      cum_delta = StringToDouble(StringTrimRight(num));
   }
   if(StringFind(body,"\"max_delta\"")>=0)
   {
      p = StringFind(body,"\"max_delta\"");
      p = StringFind(body,":",p);
      e = StringFind(body,",",p);
      if(e<0) e = StringFind(body,"}",p);
      string num = StringSubstr(body,p+1,e-p-1);
      max_d = StringToDouble(StringTrimRight(num));
   }
   if(StringFind(body,"\"min_delta\"")>=0)
   {
      p = StringFind(body,"\"min_delta\"");
      p = StringFind(body,":",p);
      e = StringFind(body,",",p);
      if(e<0) e = StringFind(body,"}",p);
      string num = StringSubstr(body,p+1,e-p-1);
      min_d = StringToDouble(StringTrimRight(num));
   }
   return true;
}

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

// -------------------- DELTA PATTERN DETECTORS (using sliding windows of last DELTA_WINDOW samples) --------------------
// Delta Surge: 4-bar signature: first opposing, then 3 consecutive bars in direction with increasing strength
bool DetectDeltaSurge(DeltaWindow &w, int dir)
{
   if(w.count < 4) return false;
   // get last 4 deltas (1..4)
   double d1 = w.Last(4).delta;
   double d2 = w.Last(3).delta;
   double d3 = w.Last(2).delta;
   double d4 = w.Last(1).delta;
   // For buy surge: d1 < 0, d2 > 0, d3 > d2, d4 > d3 and d4 sufficiently large
   if(dir == 1){
     if(d1 < 0 && d2 > 0 && d3 > d2 && d4 > d3 && d4 >= DeltaImpulseThreshold) return true;
   } else {
     if(d1 > 0 && d2 < 0 && d3 < d2 && d4 < d3 && MathAbs(d4) >= DeltaImpulseThreshold) return true;
   }
   return false;
}

// Delta Transition: soft flip across last 5 samples: magnitudes reduce then sign flips
bool DetectDeltaTransition(DeltaWindow &w, int dir)
{
   if(w.count < 5) return false;
   // get last 5 deltas: older..newer
   double older = w.Last(5).delta;
   double s2 = w.Last(4).delta;
   double s3 = w.Last(3).delta;
   double s4 = w.Last(2).delta;
   double s5 = w.Last(1).delta;
   // determine if magnitudes are tapering then flip
   // for buy transition (dir=1): older negative->gradually increase to small positive
   if(dir==1){
     if(older < 0 && s2 <= 0 && s3 <= 0 && s4 >= 0 && s5 > 0 && MathAbs(s5) >= DeltaThreshold) return true;
     // or decreasing magnitude on previous side then small positive - flexible check
     if(older < 0 && MathAbs(s2) < MathAbs(older) && MathAbs(s3) < MathAbs(s2) && s4 >= 0 && s5 > 0) return true;
   } else {
     if(older > 0 && s2 >= 0 && s3 >= 0 && s4 <= 0 && s5 < 0 && MathAbs(s5) >= DeltaThreshold) return true;
     if(older > 0 && MathAbs(s2) < MathAbs(older) && MathAbs(s3) < MathAbs(s2) && s4 <= 0 && s5 < 0) return true;
   }
   return false;
}

// Delta Flip: sudden large change between last two samples; max/min patterns check
bool DetectDeltaFlip(DeltaWindow &w, int dir)
{
   if(w.count < 2) return false;
   DeltaSample prev = w.Last(2);
   DeltaSample cur  = w.Last(1);
   double diff = cur.delta - prev.delta;
   if(dir==1){
     // expecting big jump positive
     if(diff >= FlipThreshold && cur.max_delta >= cur.delta*0.9 && MathAbs(cur.min_delta) < MathAbs(cur.delta)*0.2) return true;
   } else {
     if(diff <= -FlipThreshold && cur.min_delta <= cur.delta*0.9 && MathAbs(cur.max_delta) < MathAbs(cur.delta)*0.2) return true;
   }
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
     // clear delta windows
     for(int i=0;i<DeltaTFCount;i++) DeltaWindows[i].Clear();
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

// -------------------- CORE: Evaluate PA + Delta confirmations and trade --------------------
void EvaluateAndTrade()
{
   // handle day reset and daily cap
   DailyResetIfNeeded();
   if(!CanTradeToday()) return;

   // parse chosen price-action TFs
   string pa_tfs[];
   int pa_count=0;
   SplitCSV(PriceActionTFs, pa_tfs, pa_count);

   // parse delta TFs if using multi TF delta; otherwise use single DeltaAPI_TF as the data source
   string used_delta_tfs[];
   int dcount=0;
   if(UseMultiTFDelta){
     SplitCSV(DeltaTFs, used_delta_tfs, dcount);
     if(dcount==0){ used_delta_tfs[0] = DeltaAPI_TF; dcount=1; }
   } else {
     used_delta_tfs[0] = DeltaAPI_TF; dcount=1;
   }

   // Ensure delta windows exist
   for(int i=0;i<dcount;i++) EnsureDeltaTF(used_delta_tfs[i]);

   // Fetch delta for each used delta TF (or single TF if API doesn't support tf)
   for(int i=0;i<dcount;i++){
     double d=0, c=0, mx=0, mn=0;
     bool ok = FetchDeltaForTF(used_delta_tfs[i], d, c, mx, mn);
     // push into window with current time
     int idx = FindDeltaTFIndex(used_delta_tfs[i]);
     if(idx>=0){
       DeltaWindows[idx].Push(d, c, mx, mn, TimeCurrent());
     }
     // if fetch failed, we still continue using previous data
   }

   // Now detect price-action signals on all PA TFs: if any TF returns a valid PA signal, collect it as candidate(s)
   // For each PA TF, run detectors and build candidate signals list; we'll prefer signals that align with H1 bias if present.
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

   // Optionally compute H1 bias (if H1 included in PriceActionTFs or user can rely on H1 being present)
   int h1_bias = 0; // 1 = buy bias, -1 = sell bias, 0 = neutral
   // simple bias: H1 close > SMA50 -> buy, < SMA50 -> sell. If H1 not in PA list, still compute on H1.
   double h1_sma50 = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_SMA, PRICE_CLOSE);
   double h1_close  = iClose(_Symbol, PERIOD_H1, 1);
   if(h1_close > h1_sma50) h1_bias = 1;
   else if(h1_close < h1_sma50) h1_bias = -1;

   // For each candidate PA signal, verify delta confirmations:
   // We'll check majority agreement across the delta TFs (if multi), else check single feed window.
   // For each delta TF we have a DeltaWindow; interpret patterns there according to the user's game plan (surge/transition/flip).
   for(int s=0;s<sig_count;s++){
     PASignal ps = signals[s];
     int desired_dir = ps.dir;
     // require bias match (if bias not neutral), else allow
     if(h1_bias !=0 && desired_dir != h1_bias) {
       // skip signal against H1 bias (you can change this behavior)
       continue;
     }

     int confirm_votes = 0;
     int needed_votes = (dcount>=2) ? (dcount/2 + 1) : 1; // majority of delta TFs
     // evaluate each delta TF window
     for(int di=0; di<dcount; di++){
       int idx = FindDeltaTFIndex(used_delta_tfs[di]);
       if(idx < 0) continue;
       DeltaWindow w = DeltaWindows[idx];
       
       bool vote = false;
       // apply Mukasa-style delta entry checks from the Game Plan:
       // Priority: Delta Flip (violent), Delta Surge, Delta Transition (so that violent flips get used first)
       if(UseDeltaFlip && DetectDeltaFlip(w, desired_dir)) vote = true;
       else if(UseDeltaSurge && DetectDeltaSurge(w, desired_dir)) vote = true;
       else if(UseDeltaTransition && DetectDeltaTransition(w, desired_dir)) vote = true;

       // also require basic direction & magnitude check as minimal guard
       DeltaSample last = w.Last(1);
       if(last.t == 0) vote = false;
       else {
         if(desired_dir == 1 && last.delta < DeltaThreshold) vote = false;
         if(desired_dir == -1 && last.delta > -DeltaThreshold) vote = false;
       }

       if(vote) confirm_votes++;
     } // end delta TF loop

     if(confirm_votes >= needed_votes && CanTradeToday()){
       // Place trade: determine SL by ATR on the PA TF (we use the PA TF timeframe for SL distance), auto-lot sizing
       ENUM_TIMEFRAMES pa_tf = TFFromString(ps.tf);
       double atr = iATR(_Symbol, pa_tf, ATR_Period); if(atr<=0) atr = iATR(_Symbol, PERIOD_M15, ATR_Period);
       double stop_dist = SL_ATR_Mult * atr;
       double lot = ComputeLotByRisk(stop_dist);
       if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) continue;

       double sl = 0;
       bool trade_ok = false;
       if(desired_dir == 1) { // buy
         sl = SymbolInfoDouble(_Symbol, SYMBOL_BID) - stop_dist;
         trade_ok = trade.Buy(lot, NULL, 0, NormalizeDouble(sl,_Digits), 0, ps.reason + " | delta_confirmed");
         if(trade_ok) Print("ENTER BUY | PA=", ps.tf, " reason=", ps.reason, " lot=", DoubleToString(lot,2));
         else Print("Buy failed: ", trade.ResultRetcode(), " ", trade.ResultComment());
       } else {
         sl = SymbolInfoDouble(_Symbol, SYMBOL_ASK) + stop_dist;
         trade_ok = trade.Sell(lot, NULL, 0, NormalizeDouble(sl,_Digits), 0, ps.reason + " | delta_confirmed");
         if(trade_ok) Print("ENTER SELL | PA=", ps.tf, " reason=", ps.reason, " lot=", DoubleToString(lot,2));
         else Print("Sell failed: ", trade.ResultRetcode(), " ", trade.ResultComment());
       }
       // after entry we break to avoid multiple signals same tick. You may change to allow multiple.
       break;
     } // if confirmed
   } // for each PA signal

   // Manage open positions: exit on delta flip when profitable & trailing stop
   // We'll check the single authoritative delta window (DeltaAPI_TF) for flips, or majority flips across windows
   int pos_type=0; bool hasPos=false;
   for(int i=0;i<PositionsTotal();i++){
     if(PositionGetSymbol(i)==_Symbol){ long t = PositionGetInteger(POSITION_TYPE); if(t==POSITION_TYPE_BUY) pos_type=1; else pos_type=-1; hasPos=true; break; }
   }
   if(hasPos){
     // check delta flip across windows: if majority indicate flip against position and position profitable -> close
     int flips = 0;
     for(int di=0; di<dcount; di++){
       int idx = FindDeltaTFIndex(used_delta_tfs[di]);
       if(idx<0) continue;
       DeltaWindow w = DeltaWindows[idx];
       if(w.count < 2) continue;
       double prev = w.Last(2).delta;
       double cur  = w.Last(1).delta;
       if(pos_type==1 && cur < 0 && (prev - cur) >= DeltaThreshold) flips++;
       if(pos_type==-1 && cur > 0 && (cur - prev) >= DeltaThreshold) flips++;
     }
     int req = (dcount>=2) ? (dcount/2 + 1) : 1;
     double profit = PositionGetDouble(POSITION_PROFIT);
     if(flips >= req && profit > 0){
       Print("Closing position due to delta flip confirmations. profit=", DoubleToString(profit,2));
       bool close_ok = trade.PositionClose(_Symbol);
       if(!close_ok) Print("Position close failed: ", trade.ResultRetcode(), " ", trade.ResultComment());
     }
     // trailing stop using ATR on position's TF (use M15 as default)
     double atrm = iATR(_Symbol, PERIOD_M15, ATR_Period);
     ApplyTrailingStop(atrm);
   }

 } // end Evaluate

// -------------------- EA LIFECYCLE --------------------
int OnInit()
{
   /*  
    static bool IsInIt = false;
    if (IsInIt){
       IsInIt = true;
       
       //check if the user is allowed to use program.
       long AccountCustomer = 11000459289; //always adjust before shipping to the customer
       long AccountNo = AccountInfoInteger(ACCOUNT_LOGIN);
       Print(AccountNo);
       if(AccountCustomer == AccountNo){
         Print(__FUNCTION__,"> License verified...");
       }else{
         Print(__FUNCTION__,"> License is invalid..." );
         ExpertRemove();
         return INIT_FAILED;
       }
    }
 /*   
    //Check if testing period expired
    if(TimeCurrent() < StringToTime("2025.09.27")){
      Print(__FUNCTION__,"> Program is still active...");
    }else{
      Print(__FUNCTION__,"> Program has expired...");
      ExpertRemove();
      return INIT_FAILED;
    }
  */
   
   Print("EA v8 initialized: Multi-TF PA + Delta Surge/Transition/Flip entries.");
   day_marker = TimeCurrent();
   day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   // initialize delta TF list
   DeltaTFCount = 0;
   // if UseMultiTFDelta parse DeltaTFs else ensure DeltaAPI_TF
   if(UseMultiTFDelta){
     string parts[]; int c=0; SplitCSV(DeltaTFs, parts, c);
     for(int i=0;i<c;i++) EnsureDeltaTF(StringTrimLeft(parts[i]));
   } else {
     EnsureDeltaTF(DeltaAPI_TF);
   }
   // Set timer for polling
   EventSetTimer(PollSeconds);
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
