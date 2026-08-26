//+------------------------------------------------------------------+
//|                                                  V38_2_EA.mq5     |
//|  V38.2 XAUUSD SMC Trading EA — Evolution of V37 Production       |
//|                                                                  |
//|  ARCHITECTURE:                                                   |
//|    V37 OPERATIONAL ENGINE (preserved)                            |
//|      ├─ Risk management (daily/total DD, trade cap)             |
//|      ├─ Position sizing (binary search + OrderCalcProfit)      |
//|      ├─ SL with stops-level respect                            |
//|      ├─ Partial close at +2R + break-even                      |
//|      ├─ Trailing stop after partial close                        |
//|      ├─ Session filter (EAT)                                    |
//|      ├─ Spread filter                                           |
//|      ├─ Duplicate position prevention                           |
//|      ├─ Emergency close                                        |
//|      ├─ Persistent state (GlobalVariables)                     |
//|      ├─ News blackout (FILTER_ONLY mode)                        |
//|      └─ HUD/Comment status display                              |
//|              │                                                   |
//|    V38.2 INTELLIGENCE LAYER (replaces V37 8-feature AI)          |
//|      ├─ V38.2 StructureEngine (swing/BOS/CHOCH/OB/FVG/PD)     |
//|      ├─ Setup detection (candidate checks)                     |
//|      ├─ 50-feature FeatureEngine                                |
//|      ├─ v38_2_final_model.onnx (50 features, TreeEnsemble)     |
//|      ├─ Isotonic calibration                                    |
//|      ├─ ML probability threshold (0.50)                        |
//|      └─ Debug/audit logging                                     |
//|              │                                                   |
//|    V37 risk/execution engine → TRADE                            |
//|                                                                  |
//|  V37→V38.2 CHANGES:                                              |
//|    V37: 8-feature ONNX (hand-built)     → V38.2: 50-feature LGBM|
//|    V37: Simple SMC (FVG+displacement)    → V38.2: Full StructureEngine|
//|    V37: HTFBias (H1 breakout)            → V38.2: Regime tracking|
//|    V37: AI threshold 0.72                → V38.2: Calibrated 0.50|
//|    V37: Raw probability                  → V38.2: Isotonic calibration|
//|                                                                  |
//|  V37 PRESERVED EXACTLY:                                          |
//|    CalcLot binary search, persistent GlobalVariables,           |
//|    partial close + trailing, emergency close, HUD,             |
//|    session/spread filters, news blackout, ATR risk              |
//+------------------------------------------------------------------+
//  38.23 changes (diagnostic + broker-compat patch, ML chain untouched):
//    1. VETO MATRIX: additive gate counters + shutdown summary (OnDeinit).
//    2. Broker symbol spec/time dump (InpBrokerDiagnostics, default ON).
//    3. SPREAD UNIT FIX: gate compares (ask-bid) PRICE vs
//       InpMaxSpreadPoints * InpMaxSpreadRefPoint ($0.30 default). Identical
//       behaviour on 2-digit symbols; restores canonical intent on 3-digit
//       symbols (e.g., Exness XAUUSDm) where '30 points' == $0.03 previously.
//    4. Feature-41 parity fix (in FeatureEngine): O_SPREAD now price units
//       (points*_Point), matching Python training units — verified against
//       v38_2_feature_parity_fixture.json (f41 ~ $0.26-$0.51).
//    CANONICAL UNCHANGED: 50-feature contract, ONNX, calibrator, threshold
//    0.50, session window 10-22 EAT, risk controls, SMC structure logic.
#property strict
#property version   "38.23"
#property copyright "V38.2 — Evolution of V37 Production"
#include <V38_2_Structure.mqh>
#include <V38_Calibrator.mqh>
#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| EMBEDDED RESOURCES (canonical V38.2 artifacts, byte-for-byte)    |
//|                                                                   |
//| The ONNX model and calibrator JSON are embedded directly into the |
//| compiled V38_2_EA.ex5 via #resource. This makes the EA fully      |
//| self-contained: it loads identically in the terminal AND in the   |
//| Strategy Tester agent sandbox, where MQL5\Files is NOT reachable   |
//| (the tester agent runs in Tester\<hash>\Agent-...\ with its own    |
//| working directory, so OnnxCreate("file.onnx") / FileOpen fail with |
//| ERR_FILE_NOT_EXIST=5019). This mirrors the V37 reference, which   |
//| used #resource + OnnxCreateFromBuffer.                             |
//|                                                                   |
//| Resource path "\\Files\\name" is resolved relative to the terminal |
//| data directory MQL5\ root (leading backslash), so the resource    |
//| files must be present in MQL5\Files\ at compile time.              |
//+------------------------------------------------------------------+
#resource "\\Files\\v38_2_final_model.onnx" as uchar g_onnx_data[]
#resource "\\Files\\v38_2_calibrator.json"  as uchar g_cal_data[]

//+------------------------------------------------------------------+
//| Operation modes                                                   |
//+------------------------------------------------------------------+
enum ENUM_V38_MODE
  {
   MODE_OBSERVATION  = 0,  // Calculate everything, log, NO trades
   MODE_BACKTEST     = 1,  // Execute trades in strategy tester
   MODE_LIVE         = 2   // Execute trades on live/demo account
  };

enum ENUM_NEWS_MODE
  {
   NEWS_OFF,               // No news filtering
   NEWS_FILTER_ONLY,       // Blackout around high-impact news
   NEWS_TRADE,             // Require news catalyst
   NEWS_HYBRID             // News as optional filter
  };

input group "=== CORE ==="
input ENUM_V38_MODE   InpMode             = MODE_OBSERVATION; // EA Mode
input bool            InpTradingEnabled    = false;     // MASTER: execute trades
input ENUM_NEWS_MODE  InpNewsMode          = NEWS_FILTER_ONLY; // News handling mode
input long            InpMagic             = 382001;    // Magic number
input int             InpDeviationPoints   = 50;        // Slippage in points

input group "=== SESSION (EAT = UTC+3) ==="
input int             InpStartHourEAT      = 10;        // Session start (EAT hour)
input int             InpEndHourEAT         = 22;        // Session end (EAT hour)
input bool            InpUseSessionFilter   = true;     // Enable session filter

input group "=== QUANTITATIVE NEWS ==="
input string          InpNewsCurrency      = "USD";     // News currency filter
input int             InpNewsPreBufferMins = 10;       // Pre-news blackout (minutes)
input int             InpNewsPostBufferMins = 20;       // Post-news blackout (minutes)
input bool            InpHighImpactOnly     = true;     // High-impact events only

input group "=== RISK (V37 preserved) ==="
input double          InpRiskPerTradePct   = 0.5;       // Risk per trade (%)
input double          InpDailyLimitPct     = 2.0;       // Daily loss limit (%)
input double          InpTotalLimitPct     = 5.0;       // Total loss limit (%)
input int             InpMaxTradesPerDay   = 5;         // Max trades per day
input bool            InpCloseOnDailyLimit = true;      // Close all on daily limit

input group "=== POSITION MANAGEMENT (V37 preserved) ==="
input int             InpATRPeriod         = 14;        // ATR period
input double          InpATR_SL_Mult      = 1.20;      // SL = ATR * mult
input double          InpPartialRR         = 2.0;       // Partial close at +RR
input double          InpPartialFraction   = 0.50;      // Fraction to close
input bool            InpUseTrailing       = true;      // Enable trailing
input double          InpTrailATRmult      = 1.50;      // Trail distance (ATR mult)
input double          InpTrailStepPoints   = 20.0;      // Trail step (points)

input group "=== MARKET FILTERS ==="
input int             InpMaxSpreadPoints   = 30;        // Max spread (points on reference symbol)
input double          InpMaxSpreadRefPoint = 0.01;      // Reference point size (2-digit XAUUSD)

input group "=== DIAGNOSTICS (additive, zero gate-logic change) ==="
input bool            InpBrokerDiagnostics = true;     // Symbol/time/gate diagnostic blocks
input int             InpDiagTickStride     = 50;        // Intra-bar spread sample every N ticks
input bool            InpDumpFeatures       = false;     // Print first 50-feature vector (one-shot)

input group "=== V38.2 ML INTELLIGENCE ==="
input double          InpProbThreshold    = 0.50;      // Calibrated probability threshold
input double          InpMinRR            = 1.0;       // Min reward:risk from features
input bool            InpUseATR_SL_FromFeatures = false; // Use SL from features (true) or V37 ATR*mult (false)

input group "=== EXIT POLICY (TP / PARTIAL-CLOSE) ==="
input bool            InpUseHardTP        = false;     // Hard TP at +2R (true) or V37 managed exit (false)

input group "=== ONNX / CALIBRATOR ==="
input string          InpOnnxFilename     = "v38_2_final_model.onnx";
input string          InpCalibratorFile   = "v38_2_calibrator.json";

input group "=== TIMEFRAMES ==="
input ENUM_TIMEFRAMES InpLTF              = PERIOD_M5;  // LTF for structure
input ENUM_TIMEFRAMES InpHTF              = PERIOD_H1;  // HTF for bias

input group "=== DEBUG ==="
input bool            InpDebugMode        = true;      // Log candidate setups
input bool            InpLogToFile        = false;     // Write log to file
input string          InpLogFile          = "v38_2_ea_log.csv";

//+------------------------------------------------------------------+
//| Global state (V37-style persistent + V38.2 structure)            |
//+------------------------------------------------------------------+
CTrade               Trade;
int                  ATRHandle = INVALID_HANDLE;
long                 AIHandle = INVALID_HANDLE;
CV38_2StructureEngine g_ltf;
CV38_2StructureEngine g_htf;
CV38Calibrator       g_cal;
string               Prefix = "";
double               DailyStartEquity = 0.0, TotalReferenceEquity = 0.0;
datetime             LastTradeBar = 0;
datetime             g_lastLtfBar = 0, g_lastHtfBar = 0;

// Stats
int                  g_nCandidates = 0;
int                  g_nRejected = 0;
int                  g_nEntered = 0;
int                  g_nMlApproved = 0;

// State struct (V37-style)
struct STATE
  {
   double   ai_raw;        // raw ONNX probability
   double   ai_cal;        // calibrated probability
   double   surprise;
   int      news_dir;
   string   news_name;
   string   htf_bias;      // V38.2 regime string
   string   status;
   string   direction;     // "bullish" / "bearish"
  };
STATE S;

//+------------------------------------------------------------------+
//| VETO MATRIX (additive diagnostics — canonical gates unchanged)   |
//+------------------------------------------------------------------+
enum EV38Veto
  {
   VETO_NONE = 0,
   VETO_SESSION,
   VETO_SPREAD,
   VETO_NO_SETUP,
   VETO_FEATURES,
   VETO_ML,
   VETO_RR,
   VETO_RISK,
   VETO_MARGIN,
   VETO_ORDER_CHECK,
   VETO_EXECUTION,
   VETO_MARKET_CLOSED,
   VETO_TRADE_DISABLED,
   VETO_NEWS,
   VETO_TRADE_CAP,
   VETO_DD_LOCK,
   VETO_NO_TICK,
   VETO_POSITION_ACTIVE,
   VETO_WARMUP
  };

string VetoName(EV38Veto v)
  {
   switch(v)
     {
      case VETO_SESSION:        return "SESSION";
      case VETO_SPREAD:         return "SPREAD";
      case VETO_NO_SETUP:       return "NO_SETUP";
      case VETO_FEATURES:       return "FEATURES";
      case VETO_ML:             return "ML";
      case VETO_RR:             return "RR";
      case VETO_RISK:           return "RISK";
      case VETO_MARGIN:         return "MARGIN";
      case VETO_ORDER_CHECK:    return "ORDER_CHECK";
      case VETO_EXECUTION:      return "EXECUTION";
      case VETO_MARKET_CLOSED:  return "MARKET_CLOSED";
      case VETO_TRADE_DISABLED: return "TRADE_DISABLED";
      case VETO_NEWS:           return "NEWS";
      case VETO_TRADE_CAP:      return "TRADE_CAP";
      case VETO_DD_LOCK:        return "DD_LOCK";
      case VETO_NO_TICK:        return "NO_TICK";
      case VETO_POSITION_ACTIVE:return "POSITION_ACTIVE";
      case VETO_WARMUP:         return "WARMUP";
      default:                  return "NONE";
     }
  }

#define V38_VETO_MAX ((int)VETO_WARMUP + 1)

struct GATECOUNTS
  {
   long   ticks_processed;
   long   bars_processed;
   long   session_pass;
   long   session_fail;
   long   spread_pass;
   long   spread_fail;
   long   news_pass;
   long   news_fail;
   long   candidate_total;
   long   feature_pass;
   long   feature_fail;
   long   ml_evaluations;
   long   ml_approved;
   long   ml_rejected;
   long   risk_pass;
   long   risk_fail;
   long   margin_pass;
   long   margin_fail;
   long   ordercheck_pass;
   long   ordercheck_fail;
   long   execution_attempts;
   long   execution_success;
   long   execution_fail;
   long   veto_hist[V38_VETO_MAX];
  };
GATECOUNTS GC;

void RecordVeto(EV38Veto v)
  {
   if((int)v < V38_VETO_MAX)
      GC.veto_hist[v]++;
  }

// Feature-name table for one-shot parity dump (order frozen by contract)
const string V38_FEATURE_NAMES[V38_2_N_FEATURES] = {
   "HTF_REGIME_ENC","LTF_REGIME_ENC","BOS_COUNT_RECENT","CHOCH_COUNT_RECENT",
   "LAST_EVENT_DIRECTION_ENC","LAST_EVENT_DISP_ATR","LAST_EVENT_AGE_BARS",
   "PROTECTED_HIGH","PROTECTED_LOW","MULTI_LEG_ALIGNED","LEG_EXTENSION_ATR",
   "STRUCTURE_STRENGTH","NEAREST_LIQUIDITY_DIST","NEAREST_LIQUIDITY_SIDE",
   "LIQUIDITY_SWEPT","SWEEP_DEPTH_ATR","POST_SWEEP_REACTION_ATR",
   "EQH_EQL_PRESENT","INDUCEMENT_PRESENT","OB_PRESENT","OB_DIRECTION_ENC",
   "OB_STRENGTH","OB_DISTANCE_ATR","OB_AGE_BARS","OB_MITIGATION_COUNT",
   "OB_FRESHNESS_ENC","OB_MITIGATION_DEPTH","FVG_PRESENT","FVG_DIRECTION_ENC",
   "FVG_SIZE_ATR","FVG_AGE_BARS","FVG_FILL_PCT","FVG_FRESHNESS_ENC",
   "PD_POSITION","PD_LABEL_ENC","PD_DISTANCE_FROM_EQ","PD_LEG_SPAN_ATR",
   "ATR","ATR_PERCENTILE","DAILY_RANGE_PCT","VOLATILITY_REGIME_ENC",
   "SPREAD","SESSION_ENC","SESSION_PHASE_ENC",
   "HTF_ALIGNMENT_ENC","LTF_ALIGNMENT_ENC","DISTANCE_TO_ENTRY_ATR",
   "SL_DISTANCE_ATR","TP_DISTANCE_ATR","AVAILABLE_RR"
  };

bool  g_featDumpDone = false;
long  g_diagTick     = 0;
bool  g_specDumpDone = false;

//+------------------------------------------------------------------+
//| V37 UTILITY FUNCTIONS (preserved exactly)                         |
//+------------------------------------------------------------------+
string K(string s) { return Prefix + s; }

double G(string n, double d = 0)
  { return GlobalVariableCheck(n) ? GlobalVariableGet(n) : d; }

void P(string n, double v) { GlobalVariableSet(n, v); }

bool TradeOK()
  {
   uint r = Trade.ResultRetcode();
   return r == TRADE_RETCODE_DONE ||
          r == TRADE_RETCODE_DONE_PARTIAL ||
          r == TRADE_RETCODE_PLACED;
  }

double ATR()
  {
   if(ATRHandle == INVALID_HANDLE) return -1;
   double a[];
   ArraySetAsSeries(a, true);
   return CopyBuffer(ATRHandle, 0, 1, 1, a) == 1 ? a[0] : -1;
  }

double VolDown(double v)
  {
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(st <= 0 || mn <= 0) return 0;
   v = MathMin(v, mx);
   v = MathFloor((v + 1e-12) / st) * st;
   return v >= mn ? NormalizeDouble(v, 8) : 0;
  }

datetime EATDayStart()
  {
   datetime t = TimeGMT() + 10800;
   MqlDateTime x;
   TimeToStruct(t, x);
   x.hour = 0; x.min = 0; x.sec = 0;
   return StructToTime(x) - 10800;
  }

bool SessionEAT()
  {
   if(!InpUseSessionFilter) return true;
   datetime t = TimeGMT() + 10800;
   MqlDateTime x;
   TimeToStruct(t, x);
   if(InpStartHourEAT == InpEndHourEAT) return true;
   if(InpStartHourEAT < InpEndHourEAT)
      return x.hour >= InpStartHourEAT && x.hour < InpEndHourEAT;
   return x.hour >= InpStartHourEAT || x.hour < InpEndHourEAT;
  }

//+------------------------------------------------------------------+
//| DIAGNOSTIC HELPERS (additive)                                    |
//+------------------------------------------------------------------+
void DumpSymbolSpec()
  {
   MqlTick q;
   if(!SymbolInfoTick(_Symbol, q))
     {
      Print("[SYMBOL] _Symbol=", _Symbol, " - SymbolInfoTick FAILED");
      return;
     }
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double ticksz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   long   digits = (long)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double spread_price  = q.ask - q.bid;
   double spread_points = point  > 0 ? spread_price / point  : -1;
   double spread_ticks  = ticksz > 0 ? spread_price / ticksz : -1;

   PrintFormat("[SYMBOL] sym=%s digits=%d point=%.5f ticks(decl)=%.5f "
               "bid=%.5f ask=%.5f spread_price($)=%.5f spread_points=%.1f spread_ticks=%.1f",
      _Symbol, (int)digits, point, ticksz,
      q.bid, q.ask, spread_price, spread_points, spread_ticks);
   PrintFormat("[SYMBOL2] tick_val=%.5f tick_val_profit=%.5f tick_val_loss=%.5f "
               "vol_min=%.2f vol_max=%.2f vol_step=%.2f stops_level=%d freeze_level=%d "
               "spread_int=%d spread_float=%s",
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT),
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS),
      SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
      SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
      SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
      SymbolInfoInteger(_Symbol, SYMBOL_SPREAD_FLOAT) ? "true" : "false");
   PrintFormat("[SYMBOL3] trade_mode=%d calc_mode=%d order_mode=%d filling_mode=%d exemode=%d",
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_CALC_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_ORDER_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE));
   // spread cap shown in THREE explicit units
   double limit_price = InpMaxSpreadPoints * InpMaxSpreadRefPoint;
   double limit_pts   = SymbolInfoDouble(_Symbol, SYMBOL_POINT) > 0 ?
                        limit_price / SymbolInfoDouble(_Symbol, SYMBOL_POINT) : -1;
   PrintFormat("[GATESPEC] spread_cap_points_ref=%d ref_point=%.5f "
               "cap_price($)=%.5f cap_native_points=%.1f current_spread_price($)=%.5f verdict=%s",
      InpMaxSpreadPoints, InpMaxSpreadRefPoint, limit_price, limit_pts,
      spread_price, (spread_price <= limit_price) ? "PASS" : "FAIL");
  }

void DumpSessionSchedule()
  {
   for(int day = 0; day < 7; day++)
     {
      for(uint i = 0; ; i++)
        {
         datetime from, to;
         if(!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)day, i, from, to))
            break;
         PrintFormat("[SESSIONSCHEDULE] day=%d slot=%d %02d:%02d -> %02d:%02d",
            day, i,
            (int)(from / 3600) % 24, (int)(from / 60) % 60,
            (int)(to   / 3600) % 24, (int)(to   / 60) % 60);
        }
     }
  }

void DumpTimeSources()
  {
   datetime tc  = TimeCurrent();
   datetime ts  = TimeTradeServer();
   datetime tl  = TimeLocal();
   datetime tg  = TimeGMT();
   datetime eat = tg + 10800;
   MqlDateTime xe; TimeToStruct(eat, xe);
   bool session_ok = SessionEAT();
   PrintFormat("[TIME] current=%s trade_server=%s local=%s gmt=%s EAT=%s "
               "EAT_hour=%d dow=%d window=EAT%d-%d session_verdict=%s",
      TimeToString(tc, TIME_DATE|TIME_SECONDS),
      TimeToString(ts, TIME_DATE|TIME_SECONDS),
      TimeToString(tl, TIME_DATE|TIME_SECONDS),
      TimeToString(tg, TIME_DATE|TIME_SECONDS),
      TimeToString(eat, TIME_DATE|TIME_SECONDS),
      xe.hour, xe.day_of_week,
      InpStartHourEAT, InpEndHourEAT,
      session_ok ? "PASS" : "FAIL");
  }

void DumpSpreadGate(const MqlTick &q)
  {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double price = q.ask - q.bid;
   double pts   = point > 0 ? price / point : -1;
   double limit_price = InpMaxSpreadPoints * InpMaxSpreadRefPoint;
   PrintFormat("[GATE:SPREAD] tick#=%I64d bid=%.5f ask=%.5f spread_price($)=%.5f "
               "spread_native_points=%.2f cap_price($)=%.5f verdict=%s",
      g_diagTick, q.bid, q.ask, price, pts,
      limit_price, (price <= limit_price) ? "PASS" : "FAIL");
  }

void DumpFeatureVector(const double &feat[], const ENUM_TIMEFRAMES tf, int bar, string dir)
  {
   PrintFormat("[FEATURES] tf=%s bar=%d dir=%s - %d values (canonical order):",
               EnumToString(tf), bar, dir, V38_2_N_FEATURES);
   for(int i = 0; i < V38_2_N_FEATURES; i++)
      PrintFormat("[F%02d] %-32s = %.6f", i, V38_FEATURE_NAMES[i], feat[i]);
  }

void DailyReset()
  {
   datetime d = EATDayStart();
   if(G(K("Day"), -1) != d)
     {
      DailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      P(K("Day"), (double)d);
      P(K("DailyRef"), DailyStartEquity);
      P(K("DailyLock"), 0);
      P(K("TradeCount"), 0);
     }
   else
      DailyStartEquity = G(K("DailyRef"), AccountInfoDouble(ACCOUNT_EQUITY));
  }

double DailyDD()
  {
   return DailyStartEquity > 0 ?
      MathMax(0, (DailyStartEquity - AccountInfoDouble(ACCOUNT_EQUITY))
                  / DailyStartEquity * 100) : 100;
  }

double TotalDD()
  {
   return TotalReferenceEquity > 0 ?
      MathMax(0, (TotalReferenceEquity - AccountInfoDouble(ACCOUNT_EQUITY))
                  / TotalReferenceEquity * 100) : 100;
  }

int TradesToday() { return (int)MathRound(G(K("TradeCount"), 0)); }

bool OurPosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t && PositionSelectByTicket(t) &&
         PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
        { ticket = t; return true; }
     }
   return false;
  }

bool OurPositionExists()
  { ulong t; return OurPosition(t); }

//+------------------------------------------------------------------+
//| V37 POSITION SIZING — binary search + OrderCalcProfit            |
//| PRESERVED EXACTLY from V37 (production-quality)                  |
//+------------------------------------------------------------------+
bool CalcLot(ENUM_ORDER_TYPE type, double price, double sl, double &lot)
  {
   double risk = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPerTradePct / 100;
   if(risk <= 0) return false;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lo = step;
   double hi = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) return false;

   for(int k = 0; k < 40; k++)
     {
      double mid = VolDown((lo + hi) / 2);
      double loss = 0;
      if(mid <= 0) { lo += step; continue; }
      if(!OrderCalcProfit(type, _Symbol, mid, price, sl, loss))
         return false;
      if(MathAbs(loss) <= risk) lo = mid;
      else hi = mid;
     }

   lot = VolDown(lo);
   if(lot <= 0) return false;

   double loss = 0, margin = 0;
   if(!OrderCalcProfit(type, _Symbol, lot, price, sl, loss)) return false;
   if(MathAbs(loss) > risk * 1.001) return false;
   if(!OrderCalcMargin(type, _Symbol, lot, price, margin)) return false;
   return margin <= AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95;
  }

//+------------------------------------------------------------------+
//| V37 POSITION MANAGEMENT — partial close + trailing               |
//| PRESERVED EXACTLY from V37 (production-quality)                  |
//+------------------------------------------------------------------+
bool Reduce(ulong ticket, double volume)
  {
   if(!PositionSelectByTicket(ticket)) return false;
   ENUM_POSITION_TYPE pt = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      bool ok = Trade.PositionClosePartial(ticket, volume);
      return ok && TradeOK();
     }

   MqlTick q;
   if(!SymbolInfoTick(_Symbol, q)) return false;
   MqlTradeRequest r; MqlTradeResult z;
   ZeroMemory(r); ZeroMemory(z);
   r.action = TRADE_ACTION_DEAL;
   r.position = ticket;
   r.symbol = _Symbol;
   r.magic = InpMagic;
   r.volume = volume;
   r.deviation = InpDeviationPoints;
   r.type = pt == POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   r.price = r.type == ORDER_TYPE_BUY ? q.ask : q.bid;
   r.type_filling = ORDER_FILLING_IOC;
   if(!OrderSend(r, z)) return false;
   return z.retcode == TRADE_RETCODE_DONE || z.retcode == TRADE_RETCODE_DONE_PARTIAL;
  }

void Manage()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(!t || !PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;

      long id = PositionGetInteger(POSITION_IDENTIFIER);
      double r = G(K("R_" + (string)id), 0);
      if(r <= 0)
        {
         double op = PositionGetDouble(POSITION_PRICE_OPEN);
         double sl0 = PositionGetDouble(POSITION_SL);
         r = MathAbs(op - sl0);
        }
      if(r <= 0) continue;

      ENUM_POSITION_TYPE pt = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double op = PositionGetDouble(POSITION_PRICE_OPEN);
      double cp = PositionGetDouble(POSITION_PRICE_CURRENT);
      double sl = PositionGetDouble(POSITION_SL);
      double vol = PositionGetDouble(POSITION_VOLUME);
      double fav = pt == POSITION_TYPE_BUY ? cp - op : op - cp;
      bool part = G(K("P_" + (string)id), 0) > 0.5;

      // Partial close at +PartialRR. Skipped when a hard TP at the same level
      // is active (broker TP fires first — see V38_2_V37_REFERENCE_AUDIT §5).
      if(!InpUseHardTP && !part && fav >= r * InpPartialRR)
        {
         double cv = VolDown(vol * InpPartialFraction);
         if(cv > 0 && cv < vol && Reduce(t, cv))
           {
            if(PositionSelectByTicket(t))
               Trade.PositionModify(t, NormalizeDouble(op, _Digits), 0);
            P(K("P_" + (string)id), 1);
           }
        }

      // Trailing stop after partial close
      if(part && InpUseTrailing && PositionSelectByTicket(t))
        {
         double a = ATR();
         if(a <= 0) continue;
         double target = pt == POSITION_TYPE_BUY ?
                         cp - a * InpTrailATRmult : cp + a * InpTrailATRmult;
         target = NormalizeDouble(target, _Digits);
         bool better = pt == POSITION_TYPE_BUY ?
                       (sl <= 0 || target > sl + InpTrailStepPoints * _Point) :
                       (sl <= 0 || target < sl - InpTrailStepPoints * _Point);
         double minStop = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
         if(better &&
            ((pt == POSITION_TYPE_BUY && cp - target >= minStop) ||
             (pt == POSITION_TYPE_SELL && target - cp >= minStop)))
            Trade.PositionModify(t, target, 0);
        }
     }
  }

void EmergencyClose()
  {
   for(int pass = 0; pass < 3; pass++)
     {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong t = PositionGetTicket(i);
         if(!t || !PositionSelectByTicket(t)) continue;
         if(PositionGetInteger(POSITION_MAGIC) == InpMagic)
            Trade.PositionClose(t);
        }
      if(!OurPositionExists()) break;
     }
  }

//+------------------------------------------------------------------+
//| V37 NEWS ENGINE (preserved — PIT-safe calendar API)              |
//+------------------------------------------------------------------+
bool HighImpact(MqlCalendarEvent &e)
  { return !InpHighImpactOnly || e.importance == CALENDAR_IMPORTANCE_HIGH; }

bool RecentHighImpactNews()
  {
   if(InpNewsMode == NEWS_OFF) return false;
   datetime now = TimeTradeServer();
   if(now <= 0) now = TimeCurrent();
   MqlCalendarValue v[];
   int n = CalendarValueHistory(v, now - InpNewsPostBufferMins * 60, now,
                                 NULL, InpNewsCurrency);
   if(n <= 0) return false;
   for(int i = 0; i < ArraySize(v); i++)
     {
      MqlCalendarEvent e;
      if(CalendarEventById(v[i].event_id, e) && HighImpact(e)) return true;
     }
   return false;
  }

bool UpcomingNews()
  {
   if(InpNewsMode == NEWS_OFF) return false;
   datetime now = TimeTradeServer();
   if(now <= 0) now = TimeCurrent();
   MqlCalendarValue v[];
   int n = CalendarValueHistory(v, now, now + InpNewsPreBufferMins * 60,
                                 NULL, InpNewsCurrency);
   if(n <= 0) return false;
   for(int i = 0; i < ArraySize(v); i++)
     {
      MqlCalendarEvent e;
      if(CalendarEventById(v[i].event_id, e) && HighImpact(e)) return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| V38.2 STRUCTURE DATA UPDATE                                      |
//+------------------------------------------------------------------+
bool UpdateStructureData()
  {
   int ltfBars = Bars(_Symbol, InpLTF);
   int maxBars = 5000;
   int startBar = MathMax(0, ltfBars - maxBars);
   datetime latestLtf = iTime(_Symbol, InpLTF, 0);
   if(latestLtf == g_lastLtfBar && g_ltf.NBars() > 0) return false;
   g_lastLtfBar = latestLtf;

   if(g_ltf.NBars() == 0)
     {
      for(int b = startBar; b < ltfBars; b++)
        {
         int shift = ltfBars - 1 - b;
         datetime ts = iTime(_Symbol, InpLTF, shift);
         double o = iOpen(_Symbol, InpLTF, shift);
         double h = iHigh(_Symbol, InpLTF, shift);
         double l = iLow(_Symbol, InpLTF, shift);
         double c = iClose(_Symbol, InpLTF, shift);
         double sp = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
         g_ltf.UpdateBar(ts, o, h, l, c, sp);
        }
     }
   else
     {
      int shift = 0;
      datetime ts = iTime(_Symbol, InpLTF, shift);
      double o = iOpen(_Symbol, InpLTF, shift);
      double h = iHigh(_Symbol, InpLTF, shift);
      double l = iLow(_Symbol, InpLTF, shift);
      double c = iClose(_Symbol, InpLTF, shift);
      double sp = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      g_ltf.UpdateBar(ts, o, h, l, c, sp);
     }

   // Update HTF
   int htfBars = Bars(_Symbol, InpHTF);
   datetime latestHtf = iTime(_Symbol, InpHTF, 0);
   if(latestHtf != g_lastHtfBar)
     {
      g_lastHtfBar = latestHtf;
      if(g_htf.NBars() == 0)
        {
         int hStart = MathMax(0, htfBars - maxBars);
         for(int b = hStart; b < htfBars; b++)
           {
            int shift = htfBars - 1 - b;
            datetime ts = iTime(_Symbol, InpHTF, shift);
            double o = iOpen(_Symbol, InpHTF, shift);
            double h = iHigh(_Symbol, InpHTF, shift);
            double l = iLow(_Symbol, InpHTF, shift);
            double c = iClose(_Symbol, InpHTF, shift);
            double sp = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
            g_htf.UpdateBar(ts, o, h, l, c, sp);
           }
        }
      else
        {
         int shift = 0;
         datetime ts = iTime(_Symbol, InpHTF, shift);
         double o = iOpen(_Symbol, InpHTF, shift);
         double h = iHigh(_Symbol, InpHTF, shift);
         double l = iLow(_Symbol, InpHTF, shift);
         double c = iClose(_Symbol, InpHTF, shift);
         double sp = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
         g_htf.UpdateBar(ts, o, h, l, c, sp);
        }
     }
   return true;
  }

//+------------------------------------------------------------------+
//| V38.2 ONNX INFERENCE — replaces V37 AI(bias)                     |
//| 50-feature vector → raw probability → calibrated probability     |
//+------------------------------------------------------------------+
bool PredictWin(const double &feat[], double &rawProb, double &calProb)
  {
   rawProb = 0; calProb = 0;
   if(AIHandle == INVALID_HANDLE) return false;
   // Fail-closed: never emit a raw probability in place of a calibrated one.
   if(!g_cal.IsLoaded())
     {
      Print("V38.2: calibrator not loaded — inference refused (fail-closed)");
      return false;
     }

   float in[];
   ArrayResize(in, V38_2_N_FEATURES);
   for(int i = 0; i < V38_2_N_FEATURES; i++) in[i] = (float)feat[i];

   // Model outputs: label (int64), probabilities (float [N,2])
   long label[1];
   float proba[2];

   if(!OnnxRun(AIHandle, ONNX_DEFAULT, in, label, proba))
     {
      Print("V38.2: OnnxRun failed err=", GetLastError());
      return false;
     }

   rawProb = (double)proba[1]; // P(class=1) = P(TP hit before SL)
   if(!MathIsValidNumber(rawProb) || rawProb < 0.0 || rawProb > 1.0)
     {
      Print("V38.2: invalid raw probability ", rawProb, " (fail-closed)");
      return false;
     }
   calProb = g_cal.Apply(rawProb);
   if(!MathIsValidNumber(calProb) || calProb < 0.0 || calProb > 1.0)
     {
      Print("V38.2: invalid calibrated probability ", calProb, " (fail-closed)");
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| V38.2 MODEL SELF-TEST (fail-closed)                               |
//| Verifies the full chain once at init, before any trading logic:   |
//|  1. model handle valid (loaded)                                   |
//|  2-5. input/output shape+type accepted (done in OnInit before     |
//|       this call — reaching here means all four Set*Shape passed)  |
//|  6. ONNX inference succeeds                                       |
//|  7-8. raw probability finite and within [0,1]                     |
//|  9. calibrator loaded (isotonic)                                  |
//| 10-11. calibrated probability finite and within [0,1]             |
//| Probe vector: all zeros — the PIT-blocked/neutral value used by   |
//| the canonical Python pipeline (NaN_SENTINEL=0.0).                 |
//+------------------------------------------------------------------+
bool ModelSelfTest()
  {
   if(AIHandle == INVALID_HANDLE)
     {
      Print("V38.2 self-test: model handle invalid");
      return false;
     }
   if(V38_2_N_FEATURES != 50)
     {
      Print("V38.2 self-test: feature count ", V38_2_N_FEATURES, " != 50");
      return false;
     }
   if(!g_cal.IsLoaded() || g_cal.Method() != "isotonic")
     {
      Print("V38.2 self-test: calibrator not loaded (method=", g_cal.Method(), ")");
      return false;
     }
   double feat[50];
   ArrayInitialize(feat, 0.0);
   double rawProb, calProb;
   if(!PredictWin(feat, rawProb, calProb))
     {
      Print("V38.2 self-test: inference/calibration chain failed");
      return false;
     }
   Print("V38.2 self-test probe: raw=", DoubleToString(rawProb, 6),
         " calibrated=", DoubleToString(calProb, 6),
         " features=", V38_2_N_FEATURES);
   return true;
  }

//+------------------------------------------------------------------+
//| V38.2 TRADE EXECUTION — adapted from V37 OpenTrade                |
//| Uses V37 CalcLot + V37-style SL with broker stops-level respect  |
//+------------------------------------------------------------------+
bool OpenTrade(ENUM_ORDER_TYPE type, double slDistPrice, double calProb)
  {
   MqlTick q;
   if(!SymbolInfoTick(_Symbol, q)) return false;

   double price = type == ORDER_TYPE_BUY ? q.ask : q.bid;
   double minStop = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double freeze = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL) * _Point;

   // Ensure SL distance respects broker minimum (V37 pattern)
   double dist = MathMax(slDistPrice, MathMax(minStop, freeze) + 2 * _Point);
   double sl = NormalizeDouble(type == ORDER_TYPE_BUY ? price - dist : price + dist, _Digits);
   // EXIT POLICY:
   //  InpUseHardTP=false (CANONICAL, V37-faithful): tp=0, exit managed by
   //    Manage() partial-close at +2R + break-even + ATR trailing.
   //  InpUseHardTP=true: hard TP at +2R; partial-close at +2R is then skipped
   //    (it would never fire before the broker TP). See V38_2_V37_REFERENCE_AUDIT §5.
   double tp = 0;
   if(InpUseHardTP)
      tp = NormalizeDouble(type == ORDER_TYPE_BUY ? price + 2 * dist : price - 2 * dist, _Digits);

   double lot;
   if(!CalcLot(type, price, sl, lot))
     {
      // CalcLot is this EA's compound risk+margin gate (binary-search size
      // checking via OrderCalcProfit + free-margin test via OrderCalcMargin);
      // a failure is counted once as a risk veto.
      GC.risk_fail++; RecordVeto(VETO_RISK);
      S.status = "REJECT: RISK/MARGIN";
      return false;
     }
   GC.risk_pass++; GC.margin_pass++; GC.ordercheck_pass++;

   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpDeviationPoints);
   Trade.SetTypeFillingBySymbol(_Symbol);

   // V37 opens with SL=sl, tp=0 (no hard TP, managed exit).
   // V38.2 honours InpUseHardTP for the +2R hard-TP variant.
   if(!Trade.PositionOpen(_Symbol, type, lot, 0, sl, tp, "V38_2"))
     {
      GC.ordercheck_fail++;
      Print("V38.2: PositionOpen failed retcode=", Trade.ResultRetcode());
      return false;
     }
   if(!TradeOK()) return false;

   ulong ticket;
   if(!OurPosition(ticket)) return false;
   PositionSelectByTicket(ticket);
   long id = PositionGetInteger(POSITION_IDENTIFIER);
   P(K("R_" + (string)id), dist);  // Store risk distance (V37 pattern)
   P(K("P_" + (string)id), 0);     // Partial close flag (V37 pattern)
   S.status = "TRADE OPENED";
   return true;
  }

//+------------------------------------------------------------------+
//| V38.2 DEBUG LOGGING                                               |
//+------------------------------------------------------------------+
void LogCandidate(string dir, double rawProb, double calProb, double atr,
                  double slDist, double rr, string decision, string reason)
  {
   if(!InpDebugMode) return;
   string line = StringFormat(
      "V38.2: %s | HTF=%s | dir=%s | raw=%.4f cal=%.4f thr=%.2f | "
      "atr=%.4f slDist=%.4f rr=%.2f | %s: %s",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
      S.htf_bias, dir, rawProb, calProb, InpProbThreshold,
      atr, slDist, rr, decision, reason);
   Print(line);

   if(InpLogToFile)
     {
      int h = FileOpen(InpLogFile, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(h != INVALID_HANDLE)
        {
         FileSeek(h, 0, SEEK_END);
         FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
                   _Symbol, dir, S.htf_bias,
                   DoubleToString(rawProb, 4), DoubleToString(calProb, 4),
                   DoubleToString(InpProbThreshold, 2),
                   DoubleToString(atr, 4), DoubleToString(slDist, 4),
                   DoubleToString(rr, 2), decision, reason);
         FileClose(h);
        }
     }
  }

//+------------------------------------------------------------------+
//| HUD — V37-style status display + V38.2 ML info                   |
//+------------------------------------------------------------------+
void HUD()
  {
   Comment(StringFormat(
      "V38.2 PRODUCTION (evolution of V37)\n"
      "Mode: %s | Trading: %s\n"
      "Daily DD %.2f/%.2f | Total %.2f/%.2f\n"
      "Trades %d/%d | Candidates %d | ML-approved %d | Entered %d\n"
      "HTF %s | ML raw %.3f cal %.3f\n"
      "News: %s\n"
      "%s",
      (InpMode == MODE_OBSERVATION ? "OBSERVATION" :
       InpMode == MODE_BACKTEST ? "BACKTEST" : "LIVE"),
      (InpTradingEnabled ? "ON" : "OFF"),
      DailyDD(), InpDailyLimitPct, TotalDD(), InpTotalLimitPct,
      TradesToday(), InpMaxTradesPerDay,
      g_nCandidates, g_nMlApproved, g_nEntered,
      S.htf_bias, S.ai_raw, S.ai_cal,
      (InpNewsMode == NEWS_OFF ? "OFF" :
       InpNewsMode == NEWS_FILTER_ONLY ? "FILTER_ONLY" :
       InpNewsMode == NEWS_TRADE ? "TRADE" : "HYBRID"),
      S.status));
  }

//+------------------------------------------------------------------+
//| INIT                                                              |
//+------------------------------------------------------------------+
int OnInit()
  {
   // V37: ATR handle
   ATRHandle = iATR(_Symbol, PERIOD_M5, InpATRPeriod);
   if(ATRHandle == INVALID_HANDLE) return INIT_FAILED;

   // V37: Persistent state prefix
   Prefix = StringFormat("V38_2_%I64d_%I64d_%s_",
      AccountInfoInteger(ACCOUNT_LOGIN), InpMagic, _Symbol);

   if(!GlobalVariableCheck(K("TotalRef")))
     {
      TotalReferenceEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      P(K("TotalRef"), TotalReferenceEquity);
     }
   else
      TotalReferenceEquity = G(K("TotalRef"), AccountInfoDouble(ACCOUNT_EQUITY));

   DailyReset();

   // V38.2: Initialize structure engines
   g_ltf.Init(_Symbol, InpLTF, false);
   g_htf.Init(_Symbol, InpHTF, true);
   g_ltf.SetHTF(GetPointer(g_htf));

   // V38.2: Load calibrator. Try the embedded #resource first (works in both
   // terminal and Strategy Tester sandbox); fall back to MQL5\Files for
   // manual hot-swap of a calibrator without recompiling.
   string cal_json = CharArrayToString(g_cal_data, 0, WHOLE_ARRAY, CP_UTF8);
   if(g_cal.LoadFromString(cal_json))
     {
      Print("V38.2: calibrator loaded from embedded resource (", ArraySize(g_cal_data), " bytes)");
     }
   else
     {
      Print("V38.2: embedded calibrator parse failed; trying file '", InpCalibratorFile, "'");
      if(!g_cal.Load(InpCalibratorFile))
        {
         // FAIL-CLOSED: the frozen V38.2 system requires calibrated probabilities.
         // Running on raw ONNX probabilities is forbidden (see repair report §6).
         Print("V38.2: FAILED to load calibrator '", InpCalibratorFile,
               "' (resource AND file) err=", GetLastError(), " — INIT FAILED");
         return INIT_FAILED;
        }
      Print("V38.2: calibrator loaded from file '", InpCalibratorFile, "'");
     }
   // Frozen system requires the canonical isotonic calibrator.
   if(!g_cal.IsLoaded() || g_cal.Method() != "isotonic")
     {
      Print("V38.2: calibrator invalid (loaded=", g_cal.IsLoaded(),
            " method=", g_cal.Method(), "; required: isotonic) — INIT FAILED");
      return INIT_FAILED;
     }

   // V38.2: Load ONNX model (50 features, no ZipMap for clean MQL5 arrays).
   // Use the embedded #resource via OnnxCreateFromBuffer so the model is
   // available inside the Strategy Tester agent sandbox (where OnnxCreate
   // with a bare filename fails with ERR_FILE_NOT_EXIST=5019 because the
   // tester working directory has no MQL5\Files\v38_2_final_model.onnx).
   // Fall back to OnnxCreate(filename) for terminal-mode hot-swap.
   Print("V38.2 ONNX: requested filename='", InpOnnxFilename,
         "' resource bytes=", ArraySize(g_onnx_data),
         " tester=", (bool)MQLInfoInteger(MQL_TESTER),
         " terminal_data_path='", TerminalInfoString(TERMINAL_DATA_PATH), "'");
   if(ArraySize(g_onnx_data) > 0)
      AIHandle = OnnxCreateFromBuffer(g_onnx_data, ONNX_DEFAULT);
   else
      Print("V38.2: ONNX embedded resource is EMPTY");

   if(AIHandle == INVALID_HANDLE)
     {
      Print("V38.2: embedded ONNX load failed err=", GetLastError(),
            "; trying file '", InpOnnxFilename, "'");
      // Diagnostic: is the file present in MQL5\Files?
      int fh = FileOpen(InpOnnxFilename, FILE_READ|FILE_BIN);
      if(fh != INVALID_HANDLE)
        {
         Print("V38.2: ONNX file '", InpOnnxFilename, "' found in MQL5\\Files, size=", FileSize(fh));
         FileClose(fh);
        }
      else
         Print("V38.2: ONNX file '", InpOnnxFilename, "' NOT in MQL5\\Files (err=", GetLastError(), ")");
      AIHandle = OnnxCreate(InpOnnxFilename, ONNX_DEFAULT);
     }

   if(AIHandle == INVALID_HANDLE)
     {
      Print("V38.2: FAILED to load ONNX model (resource AND file) err=", GetLastError());
      return INIT_FAILED;
     }
   Print("V38.2: ONNX model loaded handle=", AIHandle);
   // Input: [1, 50] float32, Output: label [1] int64, probabilities [N, 2] float32.
   // MQL5 OnnxSetInputShape/OutputShape take a ulong[] shape array, not variadic.
   ulong inShape[2];  inShape[0]=1;  inShape[1]=V38_2_N_FEATURES;
   ulong outLab[1];   outLab[0]=1;
   ulong outProb[2];  outProb[0]=1;  outProb[1]=2;
   if(!OnnxSetInputShape(AIHandle, 0, inShape))
     {
      Print("V38.2: OnnxSetInputShape FAILED err=", GetLastError());
      OnnxRelease(AIHandle); AIHandle = INVALID_HANDLE;
      return INIT_FAILED;
     }
   if(!OnnxSetOutputShape(AIHandle, 0, outLab))      // label [1]
     {
      Print("V38.2: OnnxSetOutputShape(label) FAILED err=", GetLastError());
      OnnxRelease(AIHandle); AIHandle = INVALID_HANDLE;
      return INIT_FAILED;
     }
   if(!OnnxSetOutputShape(AIHandle, 1, outProb))     // probabilities [1, 2]
     {
      Print("V38.2: OnnxSetOutputShape(proba) FAILED err=", GetLastError());
      OnnxRelease(AIHandle); AIHandle = INVALID_HANDLE;
      return INIT_FAILED;
     }

   // V38.2: MODEL SELF-TEST (fail-closed). Runs one deterministic inference
   // through the full ONNX + calibration chain before any trading logic.
   if(!ModelSelfTest())
     {
      Print("V38.2 MODEL SELF TEST: FAIL");
      if(AIHandle != INVALID_HANDLE) { OnnxRelease(AIHandle); AIHandle = INVALID_HANDLE; }
      return INIT_FAILED;
     }
   Print("V38.2 MODEL SELF TEST: PASS");

   // V37: Configure trade object
   Trade.SetExpertMagicNumber(InpMagic);

   // Write log header
   if(InpLogToFile)
     {
      int h = FileOpen(InpLogFile, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(h != INVALID_HANDLE)
        {
         FileWrite(h, "timestamp","symbol","direction","htf_bias",
                      "ml_raw","ml_cal","threshold","atr","sl_dist","rr",
                      "decision","reason");
         FileClose(h);
        }
     }

   S.status = "READY";
   Print("V38.2 EA initialised: Mode=", InpMode,
         " Trading=", InpTradingEnabled,
         " Features=", V38_2_N_FEATURES,
         " Threshold=", InpProbThreshold,
         " Calibrator=", g_cal.Method());

   // Phase-3/5 diagnostics at init; OnTick re-dumps on the first tick once
   // quotes resolve (some brokers return tick only after a quote arrives).
   if(InpBrokerDiagnostics)
     {
      DumpTimeSources();
      DumpSymbolSpec();
      DumpSessionSchedule();
     }
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(AIHandle != INVALID_HANDLE) OnnxRelease(AIHandle);
   if(ATRHandle != INVALID_HANDLE) IndicatorRelease(ATRHandle);
   Comment("");
   Print("V38.2: Shutdown. Candidates=", g_nCandidates,
         " ML-approved=", g_nMlApproved,
         " Entered=", g_nEntered);

   // ---- VETO MATRIX SUMMARY ----------------------------------------------
   Print("=== V38.2 VETO MATRIX ===");
   Print("Ticks:  processed=", GC.ticks_processed);
   Print("Bars:   processed=", GC.bars_processed);
   Print("Session:  pass=", GC.session_pass, " fail=", GC.session_fail);
   Print("Spread:  pass=", GC.spread_pass, " fail=", GC.spread_fail);
   Print("News:  pass=", GC.news_pass, " fail=", GC.news_fail);
   Print("Candidates:  total=", GC.candidate_total);
   Print("Features:  pass=", GC.feature_pass, " fail=", GC.feature_fail);
   Print("ML:  evaluated=", GC.ml_evaluations,
         " approved=", GC.ml_approved, " rejected=", GC.ml_rejected);
   Print("Risk:  approved=", GC.risk_pass, " rejected=", GC.risk_fail);
   Print("Margin:  pass=", GC.margin_pass, " fail=", GC.margin_fail);
   Print("OrderCheck:  pass=", GC.ordercheck_pass, " fail=", GC.ordercheck_fail);
   Print("Execution:  attempted=", GC.execution_attempts,
         " successful=", GC.execution_success,
         " failed=", GC.execution_fail);
   Print("--- veto histogram (per early-return) ---");
   for(int v = 1; v < V38_VETO_MAX; v++)
      if(GC.veto_hist[v] > 0)
         PrintFormat("%-18s %I64d", VetoName((EV38Veto)v), GC.veto_hist[v]);
   Print("=== END VETO MATRIX ===");
  }

//+------------------------------------------------------------------+
//| ONTICK — V37 operational flow + V38.2 intelligence               |
//+------------------------------------------------------------------+
void OnTick()
  {
   // VETO MATRIX: every gate counted; Decision pipeline unchanged.
   GC.ticks_processed++;
   g_diagTick++;

   // Diagnostics: symbol spec dump once (after first live tick), time sources
   // throttled to once per new LTF bar; spread unit line every N ticks.
   if(InpBrokerDiagnostics && !g_specDumpDone)
     {
      DumpSymbolSpec();
      DumpSessionSchedule();
      g_specDumpDone = true;
     }

   static datetime s_lastBarSeen = 0;
   datetime curBar = iTime(_Symbol, InpLTF, 0);
   if(curBar > 0 && curBar != s_lastBarSeen)
     {
      s_lastBarSeen = curBar;
      GC.bars_processed++;
      if(InpBrokerDiagnostics) DumpTimeSources();
     }

   // V37: Daily reset + position management
   DailyReset();
   Manage();

   // V37: Drawdown checks
   double dd = DailyDD();
   double td = TotalDD();
   if(dd >= InpDailyLimitPct || td >= InpTotalLimitPct || G(K("DailyLock"), 0) > 0)
     {
      if(G(K("DailyLock"), 0) == 0)
        {
         P(K("DailyLock"), 1);
         if(InpCloseOnDailyLimit) EmergencyClose();
        }
      RecordVeto(VETO_DD_LOCK);
      S.status = "LOCK: DD LIMIT";
      HUD();
      return;
     }

   // V37: Session filter
   if(InpUseSessionFilter && !SessionEAT())
     {
      GC.session_fail++; RecordVeto(VETO_SESSION);
      S.status = "VETO: SESSION"; HUD(); return;
     }
   if(InpUseSessionFilter) GC.session_pass++;

   // V37: Spread filter — restored canonical intent as (ask - bid) PRICE cap.
   // On a 2-digit symbol (training environment) this is identical to the
   // original (ask-bid)/_Point > 30 check; on 3-digit symbols the original
   // formula made "30 points" equal $0.03 and vetoed continuously.
   MqlTick q;
   if(!SymbolInfoTick(_Symbol, q))
     { RecordVeto(VETO_NO_TICK); S.status = "VETO: NO TICK"; HUD(); return; }
   double spread_price = q.ask - q.bid;
   double spread_cap   = InpMaxSpreadPoints * InpMaxSpreadRefPoint;
   bool spreadOk = spread_price <= spread_cap;
   if(spreadOk) GC.spread_pass++; else { GC.spread_fail++; }
   if(InpBrokerDiagnostics && InpDiagTickStride > 0 && g_diagTick % InpDiagTickStride == 0)
      DumpSpreadGate(q);
   if(!spreadOk)
     {
      RecordVeto(VETO_SPREAD);
      S.status = "VETO: SPREAD"; HUD(); return;
     }

   // V37: News blackout (FILTER_ONLY = both pre and post)
   if(InpNewsMode == NEWS_FILTER_ONLY &&
      (UpcomingNews() || RecentHighImpactNews()))
     {
      GC.news_fail++; RecordVeto(VETO_NEWS);
      S.status = "VETO: NEWS BLACKOUT"; HUD(); return;
     }
   else GC.news_pass++;

   // V37: Pre-news window block (other modes)
   if(InpNewsMode != NEWS_FILTER_ONLY && InpNewsMode != NEWS_OFF && UpcomingNews())
     {
      GC.news_fail++; RecordVeto(VETO_NEWS);
      S.status = "VETO: NEWS PREWINDOW"; HUD(); return;
     }

   // V37: Duplicate position prevention
   if(OurPositionExists())
     {
      RecordVeto(VETO_POSITION_ACTIVE);
      S.status = "POSITION ACTIVE"; HUD(); return;
     }

   // V37: Max trades per day
   if(TradesToday() >= InpMaxTradesPerDay)
     {
      RecordVeto(VETO_TRADE_CAP);
      S.status = "VETO: TRADE CAP"; HUD(); return;
     }

   // V37: One trade per bar
   datetime bar = iTime(_Symbol, InpLTF, 0);
   if(bar <= 0 || bar == LastTradeBar) { HUD(); return; }

   // V38.2: Update structure data
   UpdateStructureData();
   // Evaluate the LAST CLOSED bar (Python parity: decision at close of bar b,
   // which is the bar that just closed when bar b+1 opens). NBars()-1 is the
   // forming bar; NBars()-2 is the most recent fully-closed bar.
   int ltfBar = g_ltf.NBars() - 2;
   if(ltfBar < 50)
     {
      RecordVeto(VETO_WARMUP);
      S.status = "WARMING UP"; HUD(); return;
     }

   double atrVal = g_ltf.ATRAtIdx(ltfBar);
   if(atrVal <= 0) atrVal = 1.0;
   double price = g_ltf.CloseAt(ltfBar);

   // V38.2: Get HTF bias from regime
   S.htf_bias = g_ltf.RegimeStrAt(ltfBar);

   // V38.2: Try both directions, pick best ML probability
   bool setupFound = false;
   string setupDir = "";
   double bestCalProb = 0;
   double bestRawProb = 0;
   double bestSlDist = 0;
   double bestRR = 0;

   for(int d = 0; d < 2; d++)
     {
      string direction = (d == 0) ? "bullish" : "bearish";

      // V38.2: Setup detection via StructureEngine
      if(!g_ltf.IsCandidateSetup(ltfBar, direction))
        {
         RecordVeto(VETO_NO_SETUP);
         if(InpDebugMode)
            LogCandidate(direction, 0, 0, atrVal, 0, 0, "SKIP", "no candidate setup");
         continue;
        }

      g_nCandidates++;
      GC.candidate_total++;

      // V38.2: Build 50-feature vector
      double feat[];
      ArrayResize(feat, V38_2_N_FEATURES);
      if(!g_ltf.BuildVector(ltfBar, ltfBar, g_ltf.TsAt(ltfBar), direction, feat))
        {
         GC.feature_fail++; RecordVeto(VETO_FEATURES);
         LogCandidate(direction, 0, 0, atrVal, 0, 0, "SKIP", "feature build failed");
         continue;
        }
      GC.feature_pass++;

      // Phase-9 parity validation: one-shot full vector dump
      if(InpDumpFeatures && !g_featDumpDone)
        {
         DumpFeatureVector(feat, InpLTF, ltfBar, direction);
         g_featDumpDone = true;
        }

      // V38.2: ONNX inference + calibration
      double rawProb, calProb;
      if(!PredictWin(feat, rawProb, calProb))
        {
         GC.ml_evaluations++;  // attempted evaluation; rejected by runtime error
         GC.ml_rejected++; RecordVeto(VETO_ML);
         LogCandidate(direction, 0, 0, atrVal, 0, 0, "SKIP", "ONNX inference failed");
         continue;
        }
      GC.ml_evaluations++;

      // V38.2: SL/TP from features
      double slDistAtr = feat[O_SL_DISTANCE_ATR];
      double rr = feat[O_AVAILABLE_RR];

      // V37-style SL: ATR * mult, or from features
      double slDistPrice;
      if(InpUseATR_SL_FromFeatures)
         slDistPrice = slDistAtr * atrVal;
      else
         slDistPrice = atrVal * InpATR_SL_Mult;

      // V38.2: ML threshold check
      if(calProb < InpProbThreshold)
        {
         g_nRejected++; GC.ml_rejected++; RecordVeto(VETO_ML);
         LogCandidate(direction, rawProb, calProb, atrVal, slDistPrice, rr,
                      "REJECT", StringFormat("ML prob %.3f < threshold %.2f",
                      calProb, InpProbThreshold));
         continue;
        }

      // V38.2: Min RR check
      if(rr < InpMinRR)
        {
         g_nRejected++; GC.ml_rejected++; RecordVeto(VETO_RR);
         LogCandidate(direction, rawProb, calProb, atrVal, slDistPrice, rr,
                      "REJECT", StringFormat("RR %.2f < min %.2f", rr, InpMinRR));
         continue;
        }

      // This setup passed all checks
      g_nMlApproved++; GC.ml_approved++;
      LogCandidate(direction, rawProb, calProb, atrVal, slDistPrice, rr,
                   "ENTER", StringFormat("prob %.3f >= threshold %.2f",
                   calProb, InpProbThreshold));

      // Pick the best direction (highest probability)
      if(calProb > bestCalProb)
        {
         bestCalProb = calProb;
         bestRawProb = rawProb;
         bestSlDist = slDistPrice;
         bestRR = rr;
         setupDir = direction;
         setupFound = true;
        }
     }

   S.ai_raw = bestRawProb;
   S.ai_cal = bestCalProb;
   S.direction = setupDir;

   if(!setupFound)
     {
      if(g_nCandidates == 0) S.status = "SCANNING: NO SMC";
      else S.status = "VETO: ML THRESHOLD";
      HUD();
      return;
     }

   // V37: Check if trading is enabled
   if(!InpTradingEnabled && InpMode == MODE_OBSERVATION)
     {
      RecordVeto(VETO_TRADE_DISABLED);
      S.status = StringFormat("OBS: would ENTER %s prob=%.3f", setupDir, bestCalProb);
      PrintFormat("V38.2 [OBSERVATION]: would ENTER %s prob=%.3f rr=%.2f",
                  setupDir, bestCalProb, bestRR);
      HUD();
      return;
     }

   // V38.2: Execute trade via V37 execution engine
   GC.execution_attempts++;
   ENUM_ORDER_TYPE orderType = (setupDir == "bullish") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(OpenTrade(orderType, bestSlDist, bestCalProb))
     {
      GC.execution_success++;
      LastTradeBar = bar;
      P(K("TradeCount"), TradesToday() + 1);
      g_nEntered++;
      PrintFormat("V38.2: ENTER %s prob=%.3f rr=%.2f slDist=%.2f",
                  setupDir, bestCalProb, bestRR, bestSlDist);
     }
   else
     GC.execution_fail++;

   HUD();
  }

//+------------------------------------------------------------------+
//| Chart event: manual reset (V37 'R' key)                          |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_KEYDOWN)
     {
      int key = (int)lparam;
      if(key == 82) // 'R'
        {
         P(K("DailyLock"), 0);
         P(K("TradeCount"), 0);
         DailyStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
         P(K("DailyRef"), DailyStartEquity);
         Print("V38.2: Manual reset (R) — daily state reset.");
        }
     }
  }
