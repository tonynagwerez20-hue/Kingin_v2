//+------------------------------------------------------------------+
//|                                                     HedgeEA.mq5  |
//|                                    Hedge Trading System MT5 EA   |
//|                           Fixed: Queue init, Port binding, Sync  |
//|                                              Version: 2.10-FIXED  |
//+------------------------------------------------------------------+
#property copyright "Hedge Trading System"
#property version   "2.10"
#property strict

//+------------------------------------------------------------------+
//|   USER ACTION: Uncomment to DISABLE DLL for backtesting only     |
//+------------------------------------------------------------------+
// #define DISABLE_ZMQ

//+------------------------------------------------------------------+
//| Log levels                                                       |
//+------------------------------------------------------------------+
enum ENUM_LOG_LEVEL
{
   LOG_LEVEL_DEBUG   = 0,
   LOG_LEVEL_INFO    = 1,
   LOG_LEVEL_WARNING = 2,
   LOG_LEVEL_ERROR   = 3
};

//+------------------------------------------------------------------+
//| Signal Data Structure                                            |
//+------------------------------------------------------------------+
struct SignalData
{
   string   id;
   string   action;          // LONG, SHORT, CLOSE_LONG, CLOSE_SHORT, REVERSE_TO_LONG, REVERSE_TO_SHORT
   string   symbol;
   double   price;
   double   sl;
   double   tp;
   double   lots;
   string   bias;            // BULLISH / BEARISH / NEUTRAL
   long     timestamp;
   string   execution_type;  // MARKET | LIMIT
   double   limit_price;
   double   confluence;      // 0.0 – 1.0
};

//+------------------------------------------------------------------+
//| ZeroMQ DLL Imports                                               |
//+------------------------------------------------------------------+
#ifndef DISABLE_ZMQ
#import "libzmq.dll"
   long zmq_ctx_new();
   int  zmq_ctx_destroy(long context);
   long zmq_socket(long context, int type);
   int  zmq_close(long socket);
   int  zmq_connect(long context, const uchar &endpoint[]);
   int  zmq_bind(long socket,    const uchar &endpoint[]);
   int  zmq_setsockopt(long socket, int option, const uchar &value[], int size);
   int  zmq_recv(long socket, uchar &buffer[], int length, int flags);
   int  zmq_send(long socket, const uchar &buffer[], int length, int flags);
#import
#endif

// ZMQ constants
#define ZMQ_SUB      2
#define ZMQ_REP      4
#define ZMQ_SUBSCRIBE  6
#define ZMQ_RCVTIMEO  27
#define ZMQ_SNDTIMEO  28
#define ZMQ_DONTWAIT   1

//+------------------------------------------------------------------+
//| Function Prototypes                                              |
//+------------------------------------------------------------------+
bool   InitZMQ();
void   CheckForSignals();
void   CheckHeartbeat();
void   ProcessSignalQueue();
int    ZmqSetSockOpt(long socket, int option, int value);
int    ZmqSetSockOpt(long socket, int option, const uchar &value[]);
void   ProcessSignal(string jsonSignal);
bool   ParseSignal(string json, SignalData &signal);
bool   ValidateSignal(SignalData &signal);
bool   CheckRiskLimits(SignalData &signal);
void   ExecuteTrade(SignalData &signal);
void   ClosePosition(SignalData &signal);
void   UpdateTrailingStops();
int    CountOpenPositions();
double GetDailyPnL();
void   CheckDailyReset();
double NormalizeLots(double lots);
string ExtractStringValue(string json, string key);
double ExtractDoubleValue(string json, string key);
void   LogDebug(string message);
void   LogInfo(string message);
void   LogWarning(string message);
void   LogError(string message);
string GetOpenPositionsJson();
string GetHistoryDealsJson(int days);
void   CheckForOfflineSignals();
void   CheckForForensicSignals();
void   UpdateForensicDisplay();

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input string         ZMQ_HOST              = "localhost";
input int            ZMQ_PORT              = 5555;    // SUB port (Python PUB)
input int            ZMQ_HB_PORT           = 5557;    // REP heartbeat port
input string         ZMQ_TOPIC             = "SIGNAL";
input double         MAX_LOT_SIZE          = 1.0;
input int            MAX_OPEN_POSITIONS    = 1;
input double         MAX_DAILY_DRAWDOWN_PCT = 2.5;
input bool           ENABLE_TRAILING_SL    = true;
input double         TRAILING_STOP_PIPS    = 20.0;
input double         TRAILING_STEP_PIPS    = 5.0;
input int            SLIPPAGE_POINTS       = 10;
input int            MAGIC_NUMBER          = 123456;
input string         TRADE_COMMENT         = "HedgeEA";
input int            REVERSAL_DELAY_MS     = 500;
input bool           BACKTEST_MODE         = false;
input string         BACKTEST_FILE         = "backtest_signals.csv";
input string         ISIGNAL_FILE          = "isignals_backtest.csv";
input int            SIGNAL_TIME_SHIFT     = 0;
input bool           ENABLE_VISUAL_REPLAY  = false;
input ENUM_LOG_LEVEL LOG_LEVEL             = LOG_LEVEL_INFO;
input bool           ENABLE_FILE_LOG       = true;

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
long zmqContext    = 0;
long zmqSubscriber = 0;
long zmqHeartbeat  = 0;
bool zmqConnected  = false;
bool hbBound       = false;   // ← tracks whether heartbeat REP is available

bool   IsBacktestActive = false;

// ── FIX 1: Signal queue pre-initialized to MAX_QUEUE_SIZE ─────────
// Previously declared as string signalQueue[] with no ArrayResize,
// causing "array out of range" crash on first signal push.
#define MAX_QUEUE_SIZE 50
string signalQueue[MAX_QUEUE_SIZE];   // static array — never needs resize
int    queueHead = 0;
int    queueTail = 0;

double   dailyStartBalance       = 0.0;
datetime currentDay              = 0;
ulong    currentPositionTicket   = 0;
string   currentPositionDirection = "";
long     lastProcessedLine       = 0;

// Forensic state
string   g_forensic_layers[6]  = {"N/A","N/A","N/A","N/A","N/A","N/A"};
string   g_forensic_action     = "WAITING";
string   g_forensic_reason     = "No data";
datetime g_last_forensic_time  = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("=== HedgeEA v2.10-FIXED Initializing ===");
   Print("=== Fixes: Queue init, Non-fatal HB port, REQ/REP sync ===");

   EventSetTimer(1);

   dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   currentDay        = TimeCurrent();

   IsBacktestActive = BACKTEST_MODE || (bool)MQLInfoInteger(MQL_TESTER);

#ifndef DISABLE_ZMQ
   if(!IsBacktestActive)
   {
      if(!InitZMQ())
      {
         Print("[ERROR] ZMQ initialization failed — EA cannot run live.");
         return(INIT_FAILED);
      }
      LogInfo(StringFormat("[INIT] SUB socket listening on %s:%d  topic='%s'",
                           ZMQ_HOST, ZMQ_PORT, ZMQ_TOPIC));
      if(hbBound)
         LogInfo(StringFormat("[INIT] Heartbeat REP socket bound on port %d", ZMQ_HB_PORT));
      else
         LogWarning(StringFormat("[INIT] Heartbeat REP NOT bound (port %d in use by another chart). "
                                 "Ping-pong will be unavailable on this instance.", ZMQ_HB_PORT));
   }
   else
   {
      Print(">>> HedgeEA: BACKTEST MODE ACTIVE <<<");
   }
#else
   if(!IsBacktestActive) { Print("[ERROR] ZMQ disabled via macro. Cannot run live."); return(INIT_FAILED); }
   Print(">>> BACKTEST MODE (ZMQ Disabled) <<<");
#endif

   LogInfo(StringFormat("[INIT] Risk: MaxLots=%.2f  MaxPositions=%d  MaxDD=%.1f%%",
                        MAX_LOT_SIZE, MAX_OPEN_POSITIONS, MAX_DAILY_DRAWDOWN_PCT));
   Print("=== HedgeEA Ready ===");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   LogInfo("HedgeEA shutting down...");
   EventKillTimer();

#ifndef DISABLE_ZMQ
   if(zmqConnected && !IsBacktestActive)
   {
      if(zmqSubscriber != 0) zmq_close(zmqSubscriber);
      if(hbBound && zmqHeartbeat != 0) zmq_close(zmqHeartbeat);
      if(zmqContext  != 0) zmq_ctx_destroy(zmqContext);
      zmqConnected = false;
   }
#endif
   Print("=== HedgeEA Deinitialized ===");
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   CheckDailyReset();

   if(ENABLE_TRAILING_SL)
      UpdateTrailingStops();

   if(IsBacktestActive)
   {
      CheckForOfflineSignals();
      CheckForForensicSignals();
   }
   else
      CheckForSignals();

   ProcessSignalQueue();

#ifndef DISABLE_ZMQ
   if(!IsBacktestActive && hbBound)
      CheckHeartbeat();
#endif
}

//+------------------------------------------------------------------+
//| OnTimer fallback                                                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(IsBacktestActive)
   {
      CheckForOfflineSignals();
      CheckForForensicSignals();
      ProcessSignalQueue();
   }
}

//+------------------------------------------------------------------+
//| InitZMQ                                                          |
//| FIX 2: Heartbeat port bind failure is WARNING, not INIT_FAILED   |
//+------------------------------------------------------------------+
bool InitZMQ()
{
#ifndef DISABLE_ZMQ
   Print("[ZMQ] Initializing ZeroMQ context...");

   zmqContext = zmq_ctx_new();
   if(zmqContext == 0) { LogError("[ZMQ] Failed to create context"); return false; }
   Print("[ZMQ] Context created: ", zmqContext);

   // ── SUB socket (receives signals from Python PUB) ──────────────
   zmqSubscriber = zmq_socket(zmqContext, ZMQ_SUB);
   if(zmqSubscriber == 0) { LogError("[ZMQ] Failed to create SUB socket"); return false; }

   ZmqSetSockOpt(zmqSubscriber, ZMQ_RCVTIMEO, 0);  // non-blocking

   string subEndpoint = StringFormat("tcp://%s:%d", ZMQ_HOST, ZMQ_PORT);
   uchar  subBytes[];
   StringToCharArray(subEndpoint, subBytes);
   ArrayResize(subBytes, ArraySize(subBytes) - 1);

   Print("[ZMQ] Connecting SUB → ", subEndpoint);
   if(zmq_connect(zmqSubscriber, subBytes) != 0)
   {
      LogError(StringFormat("[ZMQ] SUB connect failed: %s", subEndpoint));
      return false;
   }

   // Subscribe to topic
   uchar topicBytes[];
   StringToCharArray(ZMQ_TOPIC, topicBytes);
   ArrayResize(topicBytes, ArraySize(topicBytes) - 1);
   ZmqSetSockOpt(zmqSubscriber, ZMQ_SUBSCRIBE, topicBytes);
   Print("[ZMQ] SUB subscribed to topic '", ZMQ_TOPIC, "'");

   // ── REP socket (heartbeat / PING-PONG + JSON queries) ──────────
   // FIX 2: bind failure is non-fatal — multi-chart setups share one port
   zmqHeartbeat = zmq_socket(zmqContext, ZMQ_REP);
   if(zmqHeartbeat != 0)
   {
      ZmqSetSockOpt(zmqHeartbeat, ZMQ_RCVTIMEO, 1);
      ZmqSetSockOpt(zmqHeartbeat, ZMQ_SNDTIMEO, 1000);

      string hbEndpoint = StringFormat("tcp://*:%d", ZMQ_HB_PORT);
      uchar  hbBytes[];
      StringToCharArray(hbEndpoint, hbBytes);
      ArrayResize(hbBytes, ArraySize(hbBytes) - 1);

      Print("[ZMQ] Attempting to bind REP heartbeat → ", hbEndpoint);
      if(zmq_bind(zmqHeartbeat, hbBytes) == 0)
      {
         hbBound = true;
         Print("[ZMQ] Heartbeat REP bound successfully on ", hbEndpoint);
      }
      else
      {
         // ── NON-FATAL: port already held by another chart instance ──
         LogWarning(StringFormat("[ZMQ] Heartbeat port %d already in use — skipping bind. "
                                 "Only one chart needs to bind this port.", ZMQ_HB_PORT));
         zmq_close(zmqHeartbeat);
         zmqHeartbeat = 0;
         hbBound = false;
         // Do NOT return false — SUB socket is what matters for execution
      }
   }
   else
   {
      LogWarning("[ZMQ] Could not create REP socket — heartbeat unavailable.");
      hbBound = false;
   }

   zmqConnected = true;
   Print("[ZMQ] Initialization complete. Connected=true");
   return true;
#else
   return true;
#endif
}

//+------------------------------------------------------------------+
//| CheckForSignals — non-blocking receive from Python PUB           |
//+------------------------------------------------------------------+
void CheckForSignals()
{
#ifndef DISABLE_ZMQ
   if(!zmqConnected) return;

   uchar buffer[4096];
   ArrayInitialize(buffer, 0);

   int bytesReceived = zmq_recv(zmqSubscriber, buffer, 4096, ZMQ_DONTWAIT);
   if(bytesReceived > 0)
   {
      string message = CharArrayToString(buffer, 0, bytesReceived);
      LogDebug(StringFormat("[SUB] Raw message received (%d bytes): %s", bytesReceived, message));

      // Strip "SIGNAL " topic prefix
      int spacePos = StringFind(message, " ");
      if(spacePos > 0)
      {
         string jsonData = StringSubstr(message, spacePos + 1);

         // ── Push to pre-initialized queue ──────────────────────────
         int nextTail = (queueTail + 1) % MAX_QUEUE_SIZE;
         if(nextTail != queueHead)
         {
            signalQueue[queueTail] = jsonData;
            queueTail = nextTail;
            LogInfo(StringFormat("[QUEUE] Signal enqueued. QueueSize=%d", 
                                 (queueTail - queueHead + MAX_QUEUE_SIZE) % MAX_QUEUE_SIZE));
         }
         else
         {
            LogWarning("[QUEUE] Queue full — signal dropped!");
         }
      }
      else
      {
         LogWarning(StringFormat("[SUB] Received message with no topic space: %s", message));
      }
   }
#endif
}

//+------------------------------------------------------------------+
//| CheckHeartbeat — FIX 3: correct REQ/REP sync                    |
//| Python sends: "PING"  → EA replies: "PONG"                       |
//| Python sends: {"type":"GET_BALANCE"} → EA replies: JSON          |
//+------------------------------------------------------------------+
void CheckHeartbeat()
{
#ifndef DISABLE_ZMQ
   if(!zmqConnected || !hbBound || zmqHeartbeat == 0) return;

   uchar hbBuf[4096];
   ArrayInitialize(hbBuf, 0);
   int rec = zmq_recv(zmqHeartbeat, hbBuf, 4096, ZMQ_DONTWAIT);
   if(rec <= 0) return;

   string msg = CharArrayToString(hbBuf, 0, rec);
   LogDebug(StringFormat("[HB] Received heartbeat message: %s", msg));

   // ── PING → PONG ────────────────────────────────────────────────
   // FIX 3: Python ZMQBridge.check_connection() sends b"PING"
   // EA must reply b"PONG" — REP socket requires exactly one reply per recv
   if(msg == "PING")
   {
      uchar resp[4];
      resp[0] = 'P'; resp[1] = 'O'; resp[2] = 'N'; resp[3] = 'G';
      zmq_send(zmqHeartbeat, resp, 4, 0);
      LogDebug("[HB] PING → PONG replied");
      return;
   }

   // ── JSON request dispatch ──────────────────────────────────────
   string requestType = ExtractStringValue(msg, "type");
   string response    = "";

   if(requestType == "SIGNAL")
   {
      SignalData signal;
      if(ParseSignal(msg, signal) && ValidateSignal(signal) && CheckRiskLimits(signal))
      {
         MqlTradeRequest request; MqlTradeResult result;
         ZeroMemory(request);    ZeroMemory(result);
         request.action      = TRADE_ACTION_DEAL;
         request.symbol      = signal.symbol;
         request.volume      = NormalizeLots(signal.lots);
         request.type        = (signal.action == "LONG") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
         request.price       = (signal.action == "LONG") ? SymbolInfoDouble(signal.symbol, SYMBOL_ASK)
                                                          : SymbolInfoDouble(signal.symbol, SYMBOL_BID);
         request.sl          = signal.sl;
         request.tp          = signal.tp;
         request.deviation   = SLIPPAGE_POINTS;
         request.magic       = MAGIC_NUMBER;
         request.comment     = TRADE_COMMENT;
         request.type_filling = ORDER_FILLING_IOC;

         if(OrderSend(request, result) && result.retcode == TRADE_RETCODE_DONE)
            response = StringFormat("{\"status\":\"SUCCESS\",\"ticket\":%I64u,\"price\":%.5f}",
                                    result.order, result.price);
         else
            response = StringFormat("{\"status\":\"FAILED\",\"retcode\":%u,\"error\":\"%s\"}",
                                    result.retcode, result.comment);
      }
      else
         response = "{\"status\":\"FAILED\",\"error\":\"Validation or risk check failed\"}";
   }
   else if(requestType == "GET_BALANCE")
   {
      response = StringFormat("{\"status\":\"SUCCESS\",\"balance\":%.2f,\"equity\":%.2f,\"margin_free\":%.2f}",
                              AccountInfoDouble(ACCOUNT_BALANCE),
                              AccountInfoDouble(ACCOUNT_EQUITY),
                              AccountInfoDouble(ACCOUNT_MARGIN_FREE));
   }
   else if(requestType == "GET_POSITIONS")
   {
      response = GetOpenPositionsJson();
   }
   else if(requestType == "GET_HISTORY")
   {
      int days = (int)ExtractDoubleValue(msg, "days");
      if(days <= 0) days = 7;
      response = GetHistoryDealsJson(days);
   }
   else
   {
      response = StringFormat("{\"status\":\"ERROR\",\"error\":\"Unknown request type: %s\"}", requestType);
   }

   // Reply (REP must always send one reply per recv)
   uchar respBytes[];
   StringToCharArray(response, respBytes);
   ArrayResize(respBytes, ArraySize(respBytes) - 1);
   zmq_send(zmqHeartbeat, respBytes, ArraySize(respBytes), 0);
   LogDebug(StringFormat("[HB] Replied: %s", response));
#endif
}

//+------------------------------------------------------------------+
//| ProcessSignalQueue                                               |
//+------------------------------------------------------------------+
void ProcessSignalQueue()
{
   int processed = 0;
   while(queueHead != queueTail)
   {
      string jsonData = signalQueue[queueHead];
      signalQueue[queueHead] = "";          // clear slot for reuse
      queueHead = (queueHead + 1) % MAX_QUEUE_SIZE;
      processed++;
      LogInfo(StringFormat("[QUEUE] Dequeued signal #%d → ProcessSignal", processed));
      ProcessSignal(jsonData);
   }
}

//+------------------------------------------------------------------+
//| ProcessSignal — full dry-run pipeline logging                    |
//+------------------------------------------------------------------+
void ProcessSignal(string jsonSignal)
{
   LogInfo("──────────────────────────────────────────────────");
   LogInfo(StringFormat("[PIPELINE 1/4] ProcessSignal START  json=%s", jsonSignal));

   SignalData signal;
   if(!ParseSignal(jsonSignal, signal))
   {
      LogError("[PIPELINE FAIL] ParseSignal returned false — malformed JSON or missing fields");
      return;
   }
   LogInfo(StringFormat("[PIPELINE 1/4] Parsed OK → action=%s  symbol=%s  price=%.5f  sl=%.5f  lots=%.2f  exec=%s",
                        signal.action, signal.symbol, signal.price, signal.sl, signal.lots, signal.execution_type));

   if(signal.action == "LONG" || signal.action == "SHORT")
   {
      LogInfo(StringFormat("[PIPELINE 2/4] Validating entry signal: %s %s", signal.action, signal.symbol));
      if(!ValidateSignal(signal))  { LogWarning("[PIPELINE FAIL] ValidateSignal rejected"); return; }

      LogInfo("[PIPELINE 3/4] Risk check...");
      if(!CheckRiskLimits(signal)) { LogWarning("[PIPELINE FAIL] CheckRiskLimits rejected"); return; }

      LogInfo("[PIPELINE 4/4] Routing to ExecuteTrade...");
      ExecuteTrade(signal);
   }
   else if(signal.action == "CLOSE_LONG" || signal.action == "CLOSE_SHORT")
   {
      LogInfo(StringFormat("[PIPELINE EXIT] Closing position: %s", signal.action));
      ClosePosition(signal);
   }
   else if(signal.action == "REVERSE_TO_LONG" || signal.action == "REVERSE_TO_SHORT")
   {
      LogInfo(StringFormat("[PIPELINE REVERSE] Reversing → %s", signal.action));
      ClosePosition(signal);
      Sleep(REVERSAL_DELAY_MS);
      signal.action = (signal.action == "REVERSE_TO_LONG") ? "LONG" : "SHORT";
      if(!ValidateSignal(signal)) { LogWarning("[PIPELINE FAIL] Reversal validation failed"); return; }
      ExecuteTrade(signal);
   }
   else
   {
      LogWarning(StringFormat("[PIPELINE FAIL] Unknown action: '%s'", signal.action));
   }
   LogInfo("──────────────────────────────────────────────────");
}

//+------------------------------------------------------------------+
//| ParseSignal                                                      |
//+------------------------------------------------------------------+
bool ParseSignal(string json, SignalData &signal)
{
   signal.action         = ExtractStringValue(json, "action");
   signal.symbol         = ExtractStringValue(json, "symbol");
   signal.price          = ExtractDoubleValue(json, "price");
   signal.sl             = ExtractDoubleValue(json, "sl");
   signal.tp             = ExtractDoubleValue(json, "tp");
   signal.lots           = ExtractDoubleValue(json, "lots");
   signal.bias           = ExtractStringValue(json, "bias");
   if(signal.bias == "")  signal.bias = ExtractStringValue(json, "desc");
   signal.timestamp      = (long)NormalizeDouble(ExtractDoubleValue(json, "timestamp"), 0);
   signal.execution_type = ExtractStringValue(json, "execution_type");
   if(signal.execution_type == "") signal.execution_type = "MARKET";
   signal.limit_price    = ExtractDoubleValue(json, "limit_price");
   if(signal.limit_price == 0) signal.limit_price = signal.price;
   signal.confluence     = ExtractDoubleValue(json, "confluence_score");

   bool ok = (signal.action != "" && signal.symbol != "" && signal.price > 0);
   if(!ok)
      LogError(StringFormat("[PARSE/FAIL] action='%s' symbol='%s' price=%.5f — one or more required fields missing",
                            signal.action, signal.symbol, signal.price));
   return ok;
}

//+------------------------------------------------------------------+
//| ValidateSignal                                                   |
//| Supports broker suffixes: XAUUSDm, XAUUSD.pro, XAUUSDm+, etc.  |
//+------------------------------------------------------------------+
bool ValidateSignal(SignalData &signal)
{
   // Action check
   if(signal.action != "LONG"  && signal.action != "SHORT" &&
      signal.action != "CLOSE_LONG" && signal.action != "CLOSE_SHORT" &&
      signal.action != "REVERSE_TO_LONG" && signal.action != "REVERSE_TO_SHORT")
   {
      LogError(StringFormat("[VALIDATE/FAIL] Invalid action: '%s'", signal.action));
      return false;
   }

   // Symbol match — strip common suffixes for comparison
   string sigSym   = signal.symbol;
   string chartSym = _Symbol;
   StringToUpper(sigSym);
   StringToUpper(chartSym);
   // Accept if signal symbol is a substring of chart symbol or vice-versa
   bool symMatch = (sigSym == chartSym ||
                    StringFind(chartSym, sigSym)  != -1 ||
                    StringFind(sigSym, chartSym)  != -1);
   if(!symMatch)
   {
      LogError(StringFormat("[VALIDATE/FAIL] Symbol mismatch — signal='%s' chart='%s'", sigSym, chartSym));
      return false;
   }
   // Always execute using the exact broker symbol on this chart
   signal.symbol = _Symbol;
   LogDebug(StringFormat("[VALIDATE] Symbol mapped: '%s' → '%s'", sigSym, signal.symbol));

   if(!SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE))
   {
      LogError(StringFormat("[VALIDATE/FAIL] Symbol %s not tradable", _Symbol));
      return false;
   }

   if(signal.action == "CLOSE_LONG" || signal.action == "CLOSE_SHORT") return true;

   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(signal.lots < minLot || signal.lots > maxLot)
   {
      LogError(StringFormat("[VALIDATE/FAIL] Lots %.2f out of range [%.2f, %.2f]",
                            signal.lots, minLot, maxLot));
      return false;
   }

   if(signal.sl <= 0)
   {
      LogError("[VALIDATE/FAIL] SL <= 0");
      return false;
   }

   LogDebug("[VALIDATE/PASS]");
   return true;
}

//+------------------------------------------------------------------+
//| CheckRiskLimits                                                  |
//+------------------------------------------------------------------+
bool CheckRiskLimits(SignalData &signal)
{
   if(signal.lots > MAX_LOT_SIZE)
   {
      LogWarning(StringFormat("[RISK/FAIL] Lots %.2f > MaxLot %.2f", signal.lots, MAX_LOT_SIZE));
      return false;
   }
   int open = CountOpenPositions();
   if(open >= MAX_OPEN_POSITIONS)
   {
      LogWarning(StringFormat("[RISK/FAIL] Max positions reached (%d/%d)", open, MAX_OPEN_POSITIONS));
      return false;
   }
   double pnl     = GetDailyPnL();
   double maxLoss = dailyStartBalance * (MAX_DAILY_DRAWDOWN_PCT / 100.0);
   if(pnl < -maxLoss)
   {
      LogWarning(StringFormat("[RISK/FAIL] Daily drawdown %.2f exceeded limit %.2f", pnl, -maxLoss));
      return false;
   }
   LogDebug("[RISK/PASS]");
   return true;
}

//+------------------------------------------------------------------+
//| ExecuteTrade                                                     |
//+------------------------------------------------------------------+
void ExecuteTrade(SignalData &signal)
{
   MqlTradeRequest request; MqlTradeResult result;
   ZeroMemory(request);     ZeroMemory(result);

   double ask = SymbolInfoDouble(signal.symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(signal.symbol, SYMBOL_BID);

   if(ask <= 0 || bid <= 0)
   {
      LogError(StringFormat("[EXECUTE/FAIL] Invalid prices — Ask=%.5f Bid=%.5f", ask, bid));
      return;
   }

   bool isLimit = (signal.execution_type == "LIMIT");

   if(isLimit)
   {
      request.action      = TRADE_ACTION_PENDING;
      request.symbol      = signal.symbol;
      request.volume      = NormalizeLots(signal.lots);
      request.type        = (signal.action == "LONG") ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
      request.price       = signal.limit_price;
      request.sl          = signal.sl;
      request.tp          = signal.tp;
      request.deviation   = SLIPPAGE_POINTS;
      request.magic       = MAGIC_NUMBER;
      request.comment     = StringFormat("%s_LIMIT", TRADE_COMMENT);
      request.type_filling = ORDER_FILLING_IOC;
      LogInfo(StringFormat("[EXECUTE/LIMIT] %s %s %.2f lots @ %.5f  SL=%.5f",
                           signal.action, signal.symbol, request.volume, request.price, request.sl));
   }
   else
   {
      request.action      = TRADE_ACTION_DEAL;
      request.symbol      = signal.symbol;
      request.volume      = NormalizeLots(signal.lots);
      request.type        = (signal.action == "LONG") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      request.price       = (signal.action == "LONG") ? ask : bid;
      request.sl          = signal.sl;
      request.tp          = signal.tp;
      request.deviation   = SLIPPAGE_POINTS;
      request.magic       = MAGIC_NUMBER;
      request.comment     = TRADE_COMMENT;
      request.type_filling = ORDER_FILLING_IOC;
      LogInfo(StringFormat("[EXECUTE/MARKET] %s %s %.2f lots @ %.5f (Ask=%.5f Bid=%.5f) SL=%.5f",
                           signal.action, signal.symbol, request.volume, request.price, ask, bid, request.sl));
   }

   if(!OrderSend(request, result))
   {
      LogError(StringFormat("[EXECUTE/ERROR] OrderSend system error: %d — %s",
                            GetLastError(), result.comment));
      return;
   }

   if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
   {
      currentPositionTicket    = result.order;
      currentPositionDirection = signal.action;
      LogInfo(StringFormat("[EXECUTE/SUCCESS] %s ticket=%I64u  exec_price=%.5f",
                           isLimit ? "LIMIT placed" : "MARKET filled",
                           result.order, result.price));
   }
   else
   {
      LogError(StringFormat("[EXECUTE/REJECTED] retcode=%u  comment=%s", result.retcode, result.comment));
   }
}

//+------------------------------------------------------------------+
//| ClosePosition                                                    |
//+------------------------------------------------------------------+
void ClosePosition(SignalData &signal)
{
   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;
      if(PositionGetString(POSITION_SYMBOL) != signal.symbol) continue;

      found = true;
      long   posType   = PositionGetInteger(POSITION_TYPE);
      double posVolume = PositionGetDouble(POSITION_VOLUME);

      MqlTradeRequest req; MqlTradeResult res;
      ZeroMemory(req); ZeroMemory(res);
      req.action      = TRADE_ACTION_DEAL;
      req.position    = ticket;
      req.symbol      = signal.symbol;
      req.volume      = posVolume;
      req.type        = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.price       = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(signal.symbol, SYMBOL_BID)
                                                        : SymbolInfoDouble(signal.symbol, SYMBOL_ASK);
      req.deviation   = SLIPPAGE_POINTS;
      req.magic       = MAGIC_NUMBER;
      req.comment     = "Exit";
      req.type_filling = ORDER_FILLING_IOC;

      if(OrderSend(req, res) && res.retcode == TRADE_RETCODE_DONE)
      {
         LogInfo(StringFormat("[CLOSE/SUCCESS] Ticket %I64u closed @ %.5f", ticket, res.price));
         currentPositionTicket    = 0;
         currentPositionDirection = "";
      }
      else
         LogError(StringFormat("[CLOSE/FAIL] retcode=%u  %s", res.retcode, res.comment));
   }
   if(!found)
      LogWarning("[CLOSE] No matching open position found");
}

//+------------------------------------------------------------------+
//| UpdateTrailingStops                                              |
//+------------------------------------------------------------------+
void UpdateTrailingStops()
{
   if(!ENABLE_TRAILING_SL) return;

   double point      = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int    digits     = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double trailStop  = TRAILING_STOP_PIPS * point * 10;
   double trailStep  = TRAILING_STEP_PIPS * point * 10;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;

      string sym   = PositionGetString(POSITION_SYMBOL);
      if(sym != _Symbol) continue;

      long   pType  = PositionGetInteger(POSITION_TYPE);
      double curSL  = PositionGetDouble(POSITION_SL);
      double price  = (pType == POSITION_TYPE_BUY) ?
                      SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);

      double newSL  = 0;
      bool   update = false;

      if(pType == POSITION_TYPE_BUY)
      {
         newSL = NormalizeDouble(price - trailStop, digits);
         if(curSL == 0 || newSL > curSL + trailStep) update = true;
      }
      else
      {
         newSL = NormalizeDouble(price + trailStop, digits);
         if(curSL == 0 || newSL < curSL - trailStep) update = true;
      }

      if(update)
      {
         MqlTradeRequest req; MqlTradeResult res;
         ZeroMemory(req); ZeroMemory(res);
         req.action   = TRADE_ACTION_SLTP;
         req.position = ticket;
         req.symbol   = sym;
         req.sl       = newSL;
         req.tp       = PositionGetDouble(POSITION_TP);

         if(OrderSend(req, res) && res.retcode == TRADE_RETCODE_DONE)
            LogInfo(StringFormat("[TRAIL] SL updated ticket=%I64u  %.5f → %.5f", ticket, curSL, newSL));
         else
            LogError(StringFormat("[TRAIL/FAIL] retcode=%u", res.retcode));
      }
   }
}

//+------------------------------------------------------------------+
//| CountOpenPositions                                               |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && (int)PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| GetDailyPnL                                                      |
//+------------------------------------------------------------------+
double GetDailyPnL()
{
   double pnl        = 0.0;
   datetime todayStart = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   HistorySelect(todayStart, TimeCurrent());

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong t = HistoryDealGetTicket(i);
      if(t > 0 && (int)HistoryDealGetInteger(t, DEAL_MAGIC) == MAGIC_NUMBER)
         pnl += HistoryDealGetDouble(t, DEAL_PROFIT);
   }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && (int)PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
         pnl += PositionGetDouble(POSITION_PROFIT);
   }
   return pnl;
}

//+------------------------------------------------------------------+
//| CheckDailyReset                                                  |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
   datetime today   = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   datetime lastDay = StringToTime(TimeToString(currentDay, TIME_DATE));
   if(today != lastDay)
   {
      LogInfo(StringFormat("[DAILY RESET] Previous P&L: %.2f", GetDailyPnL()));
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      currentDay = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| NormalizeLots                                                    |
//+------------------------------------------------------------------+
double NormalizeLots(double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathMax(minLot, MathMin(maxLot, lots));
   lots = MathFloor(lots / lotStep) * lotStep;
   return lots;
}

//+------------------------------------------------------------------+
//| ExtractStringValue                                               |
//+------------------------------------------------------------------+
string ExtractStringValue(string json, string key)
{
   string searchKey = "\"" + key + "\"";
   int start = StringFind(json, searchKey);
   if(start == -1) return "";
   start = StringFind(json, "\"", start + StringLen(searchKey));
   if(start == -1) return "";
   start++;
   int end = StringFind(json, "\"", start);
   if(end == -1) return "";
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| ExtractDoubleValue                                               |
//+------------------------------------------------------------------+
double ExtractDoubleValue(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int start = StringFind(json, searchKey);
   if(start == -1) return 0.0;
   start += StringLen(searchKey);
   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '\t'))
      start++;
   int end = start;
   while(end < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, end);
      if(ch != '.' && ch != '-' && ch != 'e' && ch != 'E' && ch != '+' && (ch < '0' || ch > '9'))
         break;
      end++;
   }
   return StringToDouble(StringSubstr(json, start, end - start));
}

//+------------------------------------------------------------------+
//| Logging                                                          |
//+------------------------------------------------------------------+
void LogDebug(string m)   { if(LOG_LEVEL <= LOG_LEVEL_DEBUG)   Print("[DBG] ",  m); }
void LogInfo(string m)    { if(LOG_LEVEL <= LOG_LEVEL_INFO)    Print("[INFO] ", m); }
void LogWarning(string m) { if(LOG_LEVEL <= LOG_LEVEL_WARNING) Print("[WARN] ", m); }
void LogError(string m)   { if(LOG_LEVEL <= LOG_LEVEL_ERROR)   Print("[ERR] ",  m); }

//+------------------------------------------------------------------+
//| ZMQ wrapper helpers                                              |
//+------------------------------------------------------------------+
#ifndef DISABLE_ZMQ
int ZmqSetSockOpt(long socket, int option, int value)
{
   uchar bytes[4];
   bytes[0] = (uchar)( value         & 0xFF);
   bytes[1] = (uchar)((value >>  8)  & 0xFF);
   bytes[2] = (uchar)((value >> 16)  & 0xFF);
   bytes[3] = (uchar)((value >> 24)  & 0xFF);
   return zmq_setsockopt(socket, option, bytes, 4);
}
int ZmqSetSockOpt(long socket, int option, const uchar &value[])
{
   return zmq_setsockopt(socket, option, value, ArraySize(value));
}
#endif

//+------------------------------------------------------------------+
//| GetOpenPositionsJson                                             |
//+------------------------------------------------------------------+
string GetOpenPositionsJson()
{
   string json = "{\"status\":\"SUCCESS\",\"positions\":[";
   bool first = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;
      if(!first) json += ",";
      string typeStr = ((int)PositionGetInteger(POSITION_TYPE) == (int)POSITION_TYPE_BUY) ? "LONG" : "SHORT";
      json += "{\"ticket\":"       + (string)t
            + ",\"symbol\":\""     + PositionGetString(POSITION_SYMBOL) + "\""
            + ",\"type\":\""       + typeStr + "\""
            + ",\"lots\":"         + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2)
            + ",\"entry_price\":"  + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 5)
            + ",\"sl\":"           + DoubleToString(PositionGetDouble(POSITION_SL), 5)
            + ",\"profit\":"       + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2)
            + "}";
      first = false;
   }
   return json + "]}";
}

//+------------------------------------------------------------------+
//| GetHistoryDealsJson                                              |
//+------------------------------------------------------------------+
string GetHistoryDealsJson(int days)
{
   datetime end = TimeCurrent();
   HistorySelect(end - (days * 86400), end);
   string json = "{\"status\":\"SUCCESS\",\"history\":[";
   bool first = true;
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
   {
      ulong t = HistoryDealGetTicket(i);
      if((int)HistoryDealGetInteger(t, DEAL_MAGIC) != MAGIC_NUMBER) continue;
      if((int)HistoryDealGetInteger(t, DEAL_ENTRY) != (int)DEAL_ENTRY_OUT) continue;
      if(!first) json += ",";
      string tStr = ((int)HistoryDealGetInteger(t, DEAL_TYPE) == (int)DEAL_TYPE_BUY) ? "BUY" : "SELL";
      json += "{\"ticket\":"       + (string)t
            + ",\"symbol\":\""     + HistoryDealGetString(t, DEAL_SYMBOL) + "\""
            + ",\"type\":\""       + tStr + "\""
            + ",\"lots\":"         + DoubleToString(HistoryDealGetDouble(t, DEAL_VOLUME), 2)
            + ",\"exit_price\":"   + DoubleToString(HistoryDealGetDouble(t, DEAL_PRICE), 5)
            + ",\"profit\":"       + DoubleToString(HistoryDealGetDouble(t, DEAL_PROFIT), 2)
            + ",\"exit_time\":\""  + TimeToString((datetime)HistoryDealGetInteger(t, DEAL_TIME), TIME_DATE|TIME_SECONDS) + "\""
            + "}";
      first = false;
   }
   return json + "]}";
}

//+------------------------------------------------------------------+
//| CheckForOfflineSignals (Backtest / Replay)                       |
//+------------------------------------------------------------------+
void CheckForOfflineSignals()
{
   static datetime lastCheckTime = 0;
   if(TimeCurrent() == lastCheckTime) return;
   lastCheckTime = TimeCurrent();

   static long lastFileSize = 0;

   int fileHandle = FileOpen(BACKTEST_FILE, FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(fileHandle == INVALID_HANDLE)
      fileHandle = FileOpen(BACKTEST_FILE, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(fileHandle == INVALID_HANDLE)
   {
      static datetime lastWarn = 0;
      if(TimeCurrent() - lastWarn > 3600)
      { Print("[BACKTEST] Signal file not found: ", BACKTEST_FILE); lastWarn = TimeCurrent(); }
      return;
   }

   long fileSize = FileSize(fileHandle);
   if(fileSize < lastFileSize) { Print("[BACKTEST] File reset detected — resetting line counter"); lastProcessedLine = 0; }
   lastFileSize = fileSize;

   long currentLine = 0;
   int  newSignals  = 0;

   while(!FileIsEnding(fileHandle))
   {
      string tok = FileReadString(fileHandle);
      StringTrimLeft(tok); StringTrimRight(tok);
      if(tok == "") { if(FileIsEnding(fileHandle)) break; continue; }
      if(StringLen(tok) < 10 || (StringFind(tok, "-") == -1 && StringFind(tok, ".") == -1))
      { while(!FileIsLineEnding(fileHandle) && !FileIsEnding(fileHandle)) FileReadString(fileHandle); continue; }

      currentLine++;
      if(currentLine <= 1 || currentLine <= lastProcessedLine)
      { while(!FileIsLineEnding(fileHandle) && !FileIsEnding(fileHandle)) FileReadString(fileHandle); continue; }

      string rawTime = tok;
      StringReplace(rawTime, "-", ".");
      datetime sigTime = StringToTime(rawTime) + (SIGNAL_TIME_SHIFT * 3600);

      string sSymbol = FileReadString(fileHandle);
      string sAction = FileReadString(fileHandle);
      double dPrice  = StringToDouble(FileReadString(fileHandle));
      double dSL     = StringToDouble(FileReadString(fileHandle));
      double dTP     = StringToDouble(FileReadString(fileHandle));
      double dLots   = StringToDouble(FileReadString(fileHandle));
      string sDesc   = FileReadString(fileHandle);
      string sMagic  = FileReadString(fileHandle);

      StringTrimLeft(sSymbol); StringTrimRight(sSymbol);
      StringTrimLeft(sAction); StringTrimRight(sAction);

      datetime cur = TimeCurrent();
      if(!ENABLE_VISUAL_REPLAY && sigTime > cur)
      {
         static datetime lw = 0;
         if(cur - lw >= 60) { Print("[BACKTEST] Waiting for signal time: ", TimeToString(sigTime)); lw = cur; }
         FileClose(fileHandle); return;
      }
      if(!ENABLE_VISUAL_REPLAY && sigTime < cur - 3600)
      { Print("[BACKTEST] Skipping expired signal @ ", TimeToString(sigTime)); lastProcessedLine = currentLine; continue; }

      string pseudo = StringFormat("{\"action\":\"%s\",\"symbol\":\"%s\",\"price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"lots\":%.2f,\"desc\":\"%s\",\"timestamp\":%I64d}",
                                   sAction, sSymbol, dPrice, dSL, dTP, dLots, sDesc, (long)sigTime);
      ProcessSignal(pseudo);
      newSignals++;
      lastProcessedLine = currentLine;
   }
   if(newSignals > 0) Print("[BACKTEST] Processed ", newSignals, " new signal(s).");
   FileClose(fileHandle);
}

//+------------------------------------------------------------------+
//| CheckForForensicSignals                                          |
//+------------------------------------------------------------------+
void CheckForForensicSignals()
{
   if(TimeCurrent() == g_last_forensic_time) return;

   int fh = FileOpen(ISIGNAL_FILE, FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(fh == INVALID_HANDLE) fh = FileOpen(ISIGNAL_FILE, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(fh == INVALID_HANDLE) return;

   datetime target = TimeCurrent() + (SIGNAL_TIME_SHIFT * 3600);
   bool found = false;

   FileReadString(fh);
   while(!FileIsLineEnding(fh)) FileReadString(fh);

   while(!FileIsEnding(fh))
   {
      string sTime = FileReadString(fh);
      if(sTime == "") continue;
      StringReplace(sTime, "-", ".");
      datetime rowTime = StringToTime(sTime);
      if(rowTime <= target)
      {
         FileReadString(fh); // Price
         g_forensic_layers[0] = FileReadString(fh);
         g_forensic_layers[1] = FileReadString(fh);
         g_forensic_layers[2] = FileReadString(fh);
         g_forensic_layers[3] = FileReadString(fh);
         g_forensic_layers[4] = FileReadString(fh);
         g_forensic_layers[5] = FileReadString(fh);
         g_forensic_action    = FileReadString(fh);
         g_forensic_reason    = FileReadString(fh);
         found = true;
      }
      else break;
      while(!FileIsLineEnding(fh) && !FileIsEnding(fh)) FileReadString(fh);
   }
   FileClose(fh);
   g_last_forensic_time = TimeCurrent();
   if(found) UpdateForensicDisplay();
}

//+------------------------------------------------------------------+
//| UpdateForensicDisplay                                            |
//+------------------------------------------------------------------+
void UpdateForensicDisplay()
{
   string d  = "=== HEDGE-ENGINE FORENSIC INTELLIGENCE ===\n";
   d += StringFormat("Time:  %s\n", TimeToString(TimeCurrent()));
   d += "------------------------------------------\n";
   d += StringFormat("L0 Session:   [%s]\n", g_forensic_layers[0]);
   d += StringFormat("L1 HTF Bias:  [%s]\n", g_forensic_layers[1]);
   d += StringFormat("L2 Zone Qual: [%s]\n", g_forensic_layers[2]);
   d += StringFormat("L3 Liq Sweep: [%s]\n", g_forensic_layers[3]);
   d += StringFormat("L4 mBOS:      [%s]\n", g_forensic_layers[4]);
   d += StringFormat("L5 Displace:  [%s]\n", g_forensic_layers[5]);
   d += "------------------------------------------\n";
   d += StringFormat("ACTION: %s\n", g_forensic_action);
   d += StringFormat("REASON: %s\n", g_forensic_reason);
   d += "==========================================";
   Comment(d);
}
