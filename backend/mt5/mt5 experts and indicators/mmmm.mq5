#property strict
#property copyright "MetaFolfor"
#property version "1.00"

// Correct user libraries (keep these paths if they match your Include structure)
#include <Json\Include\JAson.mqh>
#include <Hmac and SHA\mql5\Include\SHA256.mqh>

//---- Inputs ----
input int PORT = 5000;
input string HMAC_KEY = "jesuschrist";
input int MAGIC_NUMBER = 12345;
input int HEARTBEAT_INTERVAL = 60; // seconds
input int RATE_LIMIT_TRADES_PER_MINUTE = 5;
input int MAX_BUFFER_SIZE = 20;

//---- Globals ----
int serverSocket = INVALID_HANDLE;
int clientSocket = INVALID_HANDLE;
int seq_num = 0;
int last_seq_received = -1;
datetime last_heartbeat = 0;
datetime last_trade_time = 0;
int trade_count_this_minute = 0;

struct BufferedMessage {
    string json;
    int seq_num;
};

BufferedMessage message_buffer[];

//+------------------------------------------------------------------+
//| Custom HMAC-SHA256 function                                      |
//+------------------------------------------------------------------+
string CryptEncodeHMAC_SHA256(string key, string data, bool base64 = false)
{
    uchar key_buffer[], data_buffer[], hash_buffer[];
    
    StringToCharArray(key, key_buffer, 0, StringLen(key));
    StringToCharArray(data, data_buffer, 0, StringLen(data));
    
    // Simple HMAC implementation
    int res = CryptEncode(CRYPT_HMAC_SHA256, data_buffer, key_buffer, hash_buffer);
    
    if(res > 0)
    {
        if(base64)
            return CharArrayToString(hash_buffer, 0, WHOLE_ARRAY, CHART_BASE64);
        else
            return CharArrayToString(hash_buffer, 0, WHOLE_ARRAY, CHART_HEXADECIMAL);
    }
    
    return "";
}

//============================================================================================
// OnInit ! Create socket server, bind, listen
//============================================================================================
int OnInit() {
    serverSocket = SocketCreate();

    if (serverSocket == INVALID_HANDLE) {
        Print("SocketCreate failed. Error:", GetLastError());
        return INIT_FAILED;
    }

    if (!SocketBind(serverSocket, "127.0.0.1", PORT)) {
        Print("SocketBind failed. Error:", GetLastError());
        SocketClose(serverSocket);
        return INIT_FAILED;
    }

    if (!SocketListen(serverSocket, 1)) {
        Print("SocketListen failed. Error:", GetLastError());
        SocketClose(serverSocket);
        return INIT_FAILED;
    }

    // Timer drives the socket listener
    EventSetTimer(1);

    Print("Executor ready. Listening on port ", PORT);
    return INIT_SUCCEEDED;
}

//============================================================================================
// OnTimer ! Accept connections + read client data + heartbeat
//============================================================================================
void OnTimer() {
    // Accept client if none connected
    if (clientSocket == INVALID_HANDLE) {
        clientSocket = SocketAccept(serverSocket, 100);
        if (clientSocket != INVALID_HANDLE) {
            Print("Client connected");
            last_seq_received = -1;
            ArrayResize(message_buffer, 0);
        }
    }

    // Read incoming data
    if (clientSocket != INVALID_HANDLE) {
        uchar data[1024];
        int bytes = SocketRead(clientSocket, data, 0, 10);

        if (bytes > 0) {
            string incoming = CharArrayToString(data, 0, bytes);
            ProcessIncomingJSON(incoming);
        } else if (bytes == 0) {
            Print("Client disconnected");
            SocketClose(clientSocket);
            clientSocket = INVALID_HANDLE;
            last_seq_received = -1;
            ArrayResize(message_buffer, 0);
        } else if (bytes < 0) {
            // SocketRead error - print error and close socket to recover
            Print("SocketRead error: ", GetLastError());
            SocketClose(clientSocket);
            clientSocket = INVALID_HANDLE;
            last_seq_received = -1;
            ArrayResize(message_buffer, 0);
        }
    }

    // Send heartbeat
    if (clientSocket != INVALID_HANDLE && TimeCurrent() - last_heartbeat >= HEARTBEAT_INTERVAL) {
        SendHeartbeat();
        last_heartbeat = TimeCurrent();
    }

    // Process buffered messages
    ProcessBufferedMessages();
}

//============================================================================================
// JSON + HMAC handler with sequencing and acknowledgements
//============================================================================================
void ProcessIncomingJSON(string rawData) {
    CJAVal root;

    // Parse JSON
    if (!root.Deserialize(rawData)) {
        Print("Failed to parse JSON");
        return;
    }

    // Extract required fields
    string receivedHmac = root["hmac"].ToStr();
    if (receivedHmac == "") {
        Print("No HMAC found");
        return;
    }

    string messageId = root["message_id"].ToStr();
    if (messageId == "") {
        Print("No message_id found");
        return;
    }

    int receivedSeqNum = (int)root["seq_num"].ToInt();
    if (receivedSeqNum < 0) {
        Print("Invalid sequence number");
        return;
    }

    // Remove HMAC field prior to verification
    root.Delete("hmac");

    string messageBody = root.Serialize();
    string computedHmac = CryptEncodeHMAC_SHA256(HMAC_KEY, messageBody, false);

    if (computedHmac != receivedHmac) {
        Print("HMAC verification failed");
        return;
    }

    string msg_type = root["type"].ToStr();

    // Check sequencing
    if (receivedSeqNum == last_seq_received + 1) {
        last_seq_received = receivedSeqNum;
        ProcessMessage(root, messageId);
        // Process any buffered messages that are now in order
        ProcessBufferedMessages();
    } else if (receivedSeqNum > last_seq_received + 1) {
        // Buffer out-of-order message
        if (ArraySize(message_buffer) < MAX_BUFFER_SIZE) {
            int size = ArraySize(message_buffer);
            ArrayResize(message_buffer, size + 1);
            message_buffer[size].json = rawData;
            message_buffer[size].seq_num = receivedSeqNum;
            Print("Buffered out-of-order message, seq: ", receivedSeqNum);
        }
    }
    // else duplicate or old message, ignore
}

void ProcessBufferedMessages() {
    bool processed = true;
    while (processed) {
        processed = false;
        for (int i = 0; i < ArraySize(message_buffer); i++) {
            if (message_buffer[i].seq_num == last_seq_received + 1) {
                CJAVal root;
                if (root.Deserialize(message_buffer[i].json)) {
                    string messageId = root["message_id"].ToStr();
                    ProcessMessage(root, messageId);
                    last_seq_received = message_buffer[i].seq_num;
                    // Remove from buffer
                    for (int j = i; j < ArraySize(message_buffer) - 1; j++) {
                        message_buffer[j] = message_buffer[j + 1];
                    }
                    ArrayResize(message_buffer, ArraySize(message_buffer) - 1);
                    processed = true;
                    Print("Processed buffered message, seq: ", last_seq_received);
                    break;
                }
            }
        }
    }
}

void ProcessMessage(CJAVal &root, string messageId) {
    string msg_type = root["type"].ToStr();
    Print("Processing message type: ", msg_type);

    //--- Fetch account info ---
    if (msg_type == "request_account_data") {
        CJAVal reply;
        reply["type"] = "account_data";
        reply["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
        reply["equity"] = AccountInfoDouble(ACCOUNT_EQUITY);
        reply["timestamp"] = (long)TimeCurrent();
        SendMessageToEngine(reply);
        return;
    }

    //--- Fetch trades ---
    if (msg_type == "request_trades") {
        SendTradesData();
        return;
    }

    //--- Status query ---
    if (msg_type == "status_query") {
        CJAVal reply;
        reply["type"] = "status_response";
        reply["status"] = "active";
        reply["connected"] = (clientSocket != INVALID_HANDLE);
        reply["last_seq_received"] = last_seq_received;
        reply["buffered_messages"] = ArraySize(message_buffer);
        reply["timestamp"] = (long)TimeCurrent();
        SendMessageToEngine(reply);
        return;
    }

    //--- Otherwise: execute trading signals ---
    CJAVal signals = root["signals"];
    if (!signals.IsArray()) {
        return;
    }

    int n = signals.Size();
    Print("Processing ", n, " trading signals");

    // Send acknowledgement
    CJAVal ack;
    ack["type"] = "signal_ack";
    ack["message_id"] = messageId;
    ack["signals_count"] = n;
    ack["timestamp"] = (long)TimeCurrent();
    SendMessageToEngine(ack);

    for (int i = 0; i < n; i++) {
        string id = signals[i]["id"].ToStr();
        string symbol = signals[i]["symbol"].ToStr();
        string action = signals[i]["action"].ToStr();
        double volume = signals[i]["volume"].ToDbl();

        double sl_d = 0.0;
        double tp_d = 0.0;
        
        // Properly check for stop_loss_distance and take_profit_distance
        if (signals[i].KeyExists("stop_loss_distance")) {
            sl_d = signals[i]["stop_loss_distance"].ToDbl();
        }
        if (signals[i].KeyExists("take_profit_distance")) {
            tp_d = signals[i]["take_profit_distance"].ToDbl();
        }

        Print("Signal: ", id, " ", symbol, " ", action, " ", volume, " SL: ", sl_d, " TP: ", tp_d);

        // Rate limiting
        if (!CheckRateLimit()) {
            SendExecFail(id, "Rate limit exceeded");
            continue;
        }

        ExecuteTrade(id, symbol, action, volume, sl_d, tp_d);
    }
}

//============================================================================================
// Send Message ! Python Engine with standardized format
//============================================================================================
void SendMessageToEngine(CJAVal &msg) {
    if (clientSocket == INVALID_HANDLE) {
        Print("No client connected, cannot send message");
        return;
    }

    string body = msg.Serialize();
    string hmac = CryptEncodeHMAC_SHA256(HMAC_KEY, body, false);

    CJAVal wrapper;
    wrapper["type"] = msg["type"].ToStr();
    wrapper["message_id"] = GenerateMessageId();
    wrapper["seq_num"] = seq_num++;
    wrapper["hmac"] = hmac;
    wrapper["data"] = msg;

    string jsonString = wrapper.Serialize();
    uchar data[];
    StringToCharArray(jsonString, data, 0, StringLen(jsonString));
    int sent = SocketSend(clientSocket, data, ArraySize(data));
    
    if(sent > 0) {
        Print("Sent message: ", msg["type"].ToStr());
    } else {
        Print("Failed to send message, error: ", GetLastError());
    }
}

string GenerateMessageId() {
    static int counter = 0;
    return "msg_" + IntegerToString((long)TimeCurrent()) + "_" + IntegerToString(counter++);
}

void SendHeartbeat() {
    CJAVal heartbeat;
    heartbeat["type"] = "heartbeat";
    heartbeat["timestamp"] = (long)TimeCurrent();
    SendMessageToEngine(heartbeat);
}

//============================================================================================
// Send both Open + Closed Trades
//============================================================================================
void SendTradesData() {
    CJAVal reply;
    reply["type"] = "trades_data";

    //--- Open Positions ---
    CJAVal openArray;

    int total = PositionsTotal();

    for (int i = 0; i < total; i++) {
        if (!PositionSelectByIndex(i)) continue;

        string pos_symbol = PositionGetString(POSITION_SYMBOL);
        // Remove symbol filter to see all positions
        // if (pos_symbol != Symbol()) continue;

        CJAVal t;
        t["ticket"] = (long)PositionGetInteger(POSITION_TICKET);
        t["symbol"] = pos_symbol;
        t["type"] = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL";
        t["volume"] = PositionGetDouble(POSITION_VOLUME);
        t["price"] = PositionGetDouble(POSITION_PRICE_OPEN);
        t["sl"] = PositionGetDouble(POSITION_SL);
        t["tp"] = PositionGetDouble(POSITION_TP);
        t["pnl"] = PositionGetDouble(POSITION_PROFIT);

        openArray.Add(t);
    }
    reply["open_trades"] = openArray;

    //--- Closed trades (last 10) ---
    CJAVal closedArray;

    HistorySelect(0, TimeCurrent());
    int deals = HistoryDealsTotal();

    int count = 0;
    for (int i = deals - 1; i >= 0 && count < 5; i--) {
        ulong ticket = HistoryDealGetTicket(i);
        string deal_symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
        // Remove symbol filter to see all deals
        // if (deal_symbol != Symbol()) continue;

        CJAVal t;
        t["ticket"] = (long)ticket;
        t["symbol"] = deal_symbol;
        t["type"] = HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY ? "BUY" : "SELL";
        t["volume"] = HistoryDealGetDouble(ticket, DEAL_VOLUME);
        t["price"] = HistoryDealGetDouble(ticket, DEAL_PRICE);
        t["pnl"] = HistoryDealGetDouble(ticket, DEAL_PROFIT);
        t["time"] = (long)HistoryDealGetInteger(ticket, DEAL_TIME);

        closedArray.Add(t);
        count++;
    }

    reply["closed_trades"] = closedArray;
    reply["timestamp"] = (long)TimeCurrent();

    SendMessageToEngine(reply);
}

//============================================================================================
// Execute Trade (MQL5 Reference compliant) with rate limiting
//============================================================================================
void ExecuteTrade(string id, string symbol, string action, double volume, double sl_dist, double tp_dist) {
    if (!SymbolSelect(symbol, true)) {
        SendExecFail(id, "Failed to select symbol");
        return;
    }

    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);

    if ((ask == 0.0) && (bid == 0.0)) {
        SendExecFail(id, "Symbol not available");
        return;
    }

    MqlTradeRequest req;
    MqlTradeResult res;

    ZeroMemory(req);
    ZeroMemory(res);

    req.magic = (uint)MAGIC_NUMBER;
    req.symbol = symbol;
    req.volume = volume;
    req.type_filling = ORDER_FILLING_FOK;

    double price = 0.0;

    if (StringCompare(action, "BUY") == 0) {
        req.action = TRADE_ACTION_DEAL;
        req.type = ORDER_TYPE_BUY;
        price = SymbolInfoDouble(symbol, SYMBOL_ASK);
        req.price = price;

        if (sl_dist > 0) req.sl = price - sl_dist;
        if (tp_dist > 0) req.tp = price + tp_dist;
    } else if (StringCompare(action, "SELL") == 0) {
        req.action = TRADE_ACTION_DEAL;
        req.type = ORDER_TYPE_SELL;
        price = SymbolInfoDouble(symbol, SYMBOL_BID);
        req.price = price;

        if (sl_dist > 0) req.sl = price + sl_dist;
        if (tp_dist > 0) req.tp = price - tp_dist;
    } else {
        SendExecFail(id, "Unknown action: " + action);
        return;
    }

    bool ok = OrderSend(req, res);

    if (!ok) {
        SendExecFail(id, res.comment, (int)res.retcode);
    } else {
        SendExecSuccess(id, res.order, res.comment, (int)res.retcode);
        // Update rate limit
        trade_count_this_minute++;
        last_trade_time = TimeCurrent();
    }
}

bool CheckRateLimit() {
    datetime now = TimeCurrent();
    if (now - last_trade_time >= 60) {
        trade_count_this_minute = 0;
        last_trade_time = now;
    }
    return trade_count_this_minute < RATE_LIMIT_TRADES_PER_MINUTE;
}

//============================================================================================
// Helper: Execution result = FAILURE
//============================================================================================
void SendExecFail(string id, string comment, int retcode=0) {
    CJAVal reply;
    reply["type"] = "execution_result";
    reply["signal_id"] = id;
    reply["success"] = false;
    reply["comment"] = comment;
    reply["ticket"] = (long)0;
    reply["retcode"] = retcode;
    reply["timestamp"] = (long)TimeCurrent();
    SendMessageToEngine(reply);
}

//============================================================================================
// Helper: Execution result = SUCCESS
//============================================================================================
void SendExecSuccess(string id, ulong ticket, string comment, int retcode) {
    CJAVal reply;
    reply["type"] = "execution_result";
    reply["signal_id"] = id;
    reply["success"] = true;
    reply["ticket"] = (long)ticket;
    reply["comment"] = comment;
    reply["retcode"] = retcode;
    reply["timestamp"] = (long)TimeCurrent();
    SendMessageToEngine(reply);
}

//============================================================================================
// Cleanup
//============================================================================================
void OnDeinit(const int reason) {
    Print("EA Deinitialized - Reason: ", reason);
    
    if (clientSocket != INVALID_HANDLE) {
        SocketClose(clientSocket);
        clientSocket = INVALID_HANDLE;
    }

    if (serverSocket != INVALID_HANDLE) {
        SocketClose(serverSocket);
        serverSocket = INVALID_HANDLE;
    }

    EventKillTimer();
}