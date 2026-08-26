//+------------------------------------------------------------------+
//| V38_2_GateDiagnostic.mq5 — READ-ONLY GATE DIAGNOSTIC HARNESS      |
//|                                                                  |
//| PURPOSE: capture every gate input the canonical V38_2_EA sees,    |
//| without altering any decision and without trading. Diagnoses the  |
//| repeated "VETO: SESSION" / "VETO: SPREAD" behaviour on Exness     |
//| XAUUSDm by logging symbol spec, time sources, and gate outcomes.  |
//|                                                                  |
//| PROPERTIES:                                                       |
//|  - standalone: shares NO state with V38_2_EA (no #resource, no    |
//|    ONNX, no calibrator, no GlobalVariables, no trade calls)       |
//|  - read-only: only SymbolInfo*/Time*/iTime/FileWrite/Print        |
//|  - logs the legacy (raw points) AND normalized (price) spread     |
//|    verdicts side-by-side, so the exact failure mode is explicit   |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "V38.2 read-only gate diagnostic (no trades)"

// Canonical EA's gate parameters — copied verbatim, NOT linked at runtime.
// These mirror V38_2_EA.mq5 defaults (frozen). Do not "tune" them here;
// they exist so the log line can show the same limit the EA applies.
input int    InpStartHourEAT      = 10;    // mirror of canonical default
input int    InpEndHourEAT        = 22;    // mirror of canonical default
input bool   InpUseSessionFilter  = true;  // mirror of canonical default
input int    InpMaxSpreadPoints   = 30;    // mirror of canonical default (points)
input double InpMaxSpreadRefPoint = 0.01;  // reference point (2-digit XAUUSD)
input int    InpSpreadTickStride  = 50;    // spread line every Nth tick
input bool   InpLogToFile         = true;  // also write CSV to MQL5\Files
input string InpLogFile           = "v38_2_gate_diag.csv";

datetime g_lastBar  = 0;
long     g_tickNo   = 0;
int      g_fileH    = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| VERBATIM COPY of canonical SessionEAT() (V38_2_EA.mq5 L225-235).  |
//| Any change here invalidates the diagnostic.                       |
//+------------------------------------------------------------------+
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
//| One-time symbol/session ground truth                              |
//+------------------------------------------------------------------+
void LogSymbolSpec()
  {
   PrintFormat("[SYMBOL] sym=%s digits=%d _Point=%.5f tick_size=%.5f tick_value=%.5f "
               "spread_int=%d spread_float=%s stops_level=%d freeze_level=%d "
               "vol_min=%.2f vol_max=%.2f vol_step=%.2f contract=%.1f",
      _Symbol,
      (int)_Digits,
      _Point,
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE),
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
      SymbolInfoInteger(_Symbol, SYMBOL_SPREAD_FLOAT) ? "true" : "false",
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
      SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
      SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
      SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
      SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE));
   PrintFormat("[SYMBOL2] trade_mode=%d calc_mode=%d order_mode=%d filling_mode=%d exemode=%d",
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_CALC_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_ORDER_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE),
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE));
   PrintFormat("[GATESPEC] norm_cap_price=%.4f cap_native_points=%.1f",
      InpMaxSpreadPoints * InpMaxSpreadRefPoint,
      _Point > 0 ? (InpMaxSpreadPoints * InpMaxSpreadRefPoint) / _Point : -1);

   // Broker's actual trading sessions for this symbol
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

//+------------------------------------------------------------------+
//| Time-source table row                                             |
//+------------------------------------------------------------------+
void LogTime()
  {
   datetime tc  = TimeCurrent();
   datetime ts  = TimeTradeServer();
   datetime tl  = TimeLocal();
   datetime tg  = TimeGMT();
   datetime eat = tg + 10800;
   MqlDateTime xe; TimeToStruct(eat, xe);

   bool session_ok = SessionEAT();
   PrintFormat("[TIME] current=%s server=%s local=%s gmt=%s EAT=%s "
               "EAT_hour=%d dow=%d window=%d-%d session_allowed=%s "
               "(utc_window 07-19)",
      TimeToString(tc, TIME_DATE|TIME_SECONDS),
      TimeToString(ts, TIME_DATE|TIME_SECONDS),
      TimeToString(tl, TIME_DATE|TIME_SECONDS),
      TimeToString(tg, TIME_DATE|TIME_SECONDS),
      TimeToString(eat, TIME_DATE|TIME_SECONDS),
      xe.hour, xe.day_of_week,
      InpStartHourEAT, InpEndHourEAT,
      session_ok ? "PASS" : "FAIL");
  }

//+------------------------------------------------------------------+
//| Gate evaluation in the canonical EA's exact order                 |
//+------------------------------------------------------------------+
void LogGates(bool full)
  {
   MqlTick q;
   ZeroMemory(q);
   bool have_tick = SymbolInfoTick(_Symbol, q);

   double spread_price  = have_tick ? (q.ask - q.bid) : 0.0;
   double spread_points = have_tick ? spread_price / _Point : 0.0;

   // Gate 1: session (verbatim semantics)
   bool g_session = SessionEAT();
   // Gate 2 (legacy): raw points < V38_2_EA pre-fix formula
   bool g_spread_legacy = have_tick && !(spread_points > InpMaxSpreadPoints);
   // Gate 2 (normalized): price cap, identical on 2-digit, restored on 3-digit
   bool g_spread_norm   = have_tick &&
                          !(spread_price > InpMaxSpreadPoints * InpMaxSpreadRefPoint);

   if(full)
      PrintFormat("[GATES] tick#=%I64d session=%s spread_legacy=%s spread_norm=%s "
                  "bid=%.5f ask=%.5f spread_price=%.5f spread_native_points=%.1f "
                  "legacy_cap=%d norm_cap_price=%.4f "
                  "| downstream(candidate/ML/risk/order)=%s",
         g_tickNo,
         g_session ? "PASS" : "FAIL(VETO: SESSION)",
         g_spread_legacy ? "PASS" : "FAIL(VETO: SPREAD-legacy)",
         g_spread_norm ? "PASS" : "FAIL(VETO: SPREAD-norm)",
         q.bid, q.ask, spread_price, spread_points,
         InpMaxSpreadPoints, InpMaxSpreadPoints * InpMaxSpreadRefPoint,
         (g_session && g_spread_norm) ? "REACHABLE" : "BLOCKED");
   else
      PrintFormat("[GATES:SPREAD] tick#=%I64d spread_native_points=%.1f "
                  "legacy_cap=%d norm_cap_price=%.4f legacy=%s norm=%s",
         g_tickNo, spread_points, InpMaxSpreadPoints,
         InpMaxSpreadPoints * InpMaxSpreadRefPoint,
         g_spread_legacy ? "PASS" : "FAIL",
         g_spread_norm ? "PASS" : "FAIL");

   if(g_fileH != INVALID_HANDLE)
     {
      FileWrite(g_fileH,
         TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS),
         _Symbol, _Digits, DoubleToString(_Point, 5),
         q.bid, q.ask,
         DoubleToString(spread_price, 5),
         DoubleToString(spread_points, 2),
         g_session ? 1 : 0,
         g_spread_legacy ? 1 : 0,
         g_spread_norm ? 1 : 0);
      FileFlush(g_fileH);
     }
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   Print("V38_2_GateDiagnostic: init (read-only; places no trades)");
   LogSymbolSpec();
   if(InpLogToFile)
     {
      g_fileH = FileOpen(InpLogFile, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(g_fileH != INVALID_HANDLE)
         FileWrite(g_fileH, "gmt", "symbol", "digits", "point",
                   "bid", "ask", "spread_price", "spread_points",
                   "session_pass", "spread_pass_legacy", "spread_pass_normalized");
     }
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_fileH != INVALID_HANDLE) { FileClose(g_fileH); g_fileH = INVALID_HANDLE; }
   Print("V38_2_GateDiagnostic: shutdown");
  }

void OnTick()
  {
   g_tickNo++;
   if(g_tickNo % InpSpreadTickStride == 0)
      LogGates(false);   // intra-bar spread sampling

   datetime bar = iTime(_Symbol, PERIOD_M5, 0);
   if(bar != g_lastBar)
     {
      g_lastBar = bar;
      LogTime();
      LogGates(true);    // full block once per new M5 bar
     }
  }
//+------------------------------------------------------------------+
