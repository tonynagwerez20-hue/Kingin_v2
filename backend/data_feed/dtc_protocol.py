"""
Sierra Chart DTC Protocol - Proper Variable-Length String Support

Sierra Chart uses ENCODING_VARIABLE_LENGTH_STRINGS (encoding 6) by default,
not compact binary. This requires a completely different parsing approach.

Key differences:
- Strings are null-terminated with 4-byte length prefix
- Numbers are still binary but messages are larger
- Historical data response structure is different
"""
import struct
from enum import IntEnum

# DTC Protocol Constants
DTC_VERSION = 8
ENCODING_BINARY_FIXED = 1
ENCODING_JSON = 4
ENCODING_VARIABLE_LENGTH_STRINGS = 6
CURRENT_ENCODING = ENCODING_JSON  # Switching to JSON for robustness

class DTC_MSG(IntEnum):
    LOGON_REQUEST = 1
    LOGON_RESPONSE = 2
    HEARTBEAT = 3
    LOGOFF = 5
    ENCODING_REQUEST = 6
    ENCODING_RESPONSE = 7
    MARKET_DATA_REQUEST = 101
    MARKET_DATA_REJECT = 103
    MARKET_DATA_SNAPSHOT = 104
    MARKET_DATA_UPDATE_TRADE = 107
    MARKET_DATA_UPDATE_BID_ASK = 108
    MARKET_DEPTH_UPDATE_LEVEL = 101 # Level 2 Update
    MARKET_DEPTH_REQUEST = 102
    MARKET_DEPTH_REJECT = 103
    MARKET_DEPTH_SNAPSHOT_LEVEL = 122 # Level 2 Snapshot
    HISTORICAL_PRICE_DATA_REQUEST = 800
    HISTORICAL_PRICE_DATA_RESPONSE_HEADER = 801
    HISTORICAL_PRICE_DATA_RECORD_RESPONSE = 802

def parse_header(data):
    """Parse DTC message header (always 4 bytes: size + type)"""
    if len(data) < 4:
        return None, None
    size, msg_type = struct.unpack("<HH", data[:4])
    return size, msg_type

class DTCMessage:
    def __init__(self, msg_type):
        self.Size = 0
        self.Type = msg_type

    def pack(self):
        raise NotImplementedError

    def pack_json(self):
        """DTC JSON over TCP: JSON payload + null terminator (No binary header)"""
        import json
        # Extract public fields. Note: 'Type' is already in self.__dict__
        data = {k: v for k, v in self.__dict__.items() if not k.startswith('_') and k != 'Size'}
        json_str = json.dumps(data) + "\0"
        return json_str.encode('ascii')

# Encoding Request - Ask Sierra Chart to use specific encoding
class EncodingRequest(DTCMessage):
    def __init__(self, encoding=ENCODING_BINARY_FIXED):
        super().__init__(DTC_MSG.ENCODING_REQUEST)
        self.Encoding = encoding
        self.ProtocolVersion = DTC_VERSION
        self.ProtocolType = "DTC"
    
    def pack(self):
        # DTC Encoding Request structure (Bootstrap):
        # ALWAYS uses Binary Fixed format so the server can read it before knowing the encoding.
        # uint16 Size, uint16 Type, int32 ProtocolVersion, int32 Encoding, char[4] ProtocolType
        
        protocol_bytes = pack_fixed_string(self.ProtocolType, 4)
        body = struct.pack("<ii", self.ProtocolVersion, self.Encoding) + protocol_bytes
        self.Size = 4 + len(body)
        return struct.pack("<HH", self.Size, self.Type) + body


def pack_fixed_string(s, length):
    """Pack string into fixed length buffer, null terminated"""
    b = s.encode('ascii', 'ignore')[:length]
    return b + b'\x00' * (length - len(b))

def pack_vls_string(s):
    """Pack string with 4-byte length prefix (VLS format)"""
    b = s.encode('ascii', 'ignore')
    return struct.pack("<I", len(b)) + b

def pad_message(body):
    """Ensure body length is multiple of 4 bytes"""
    pad_len = (4 - (len(body) % 4)) % 4
    if pad_len:
        return body + (b'\x00' * pad_len)
    return body

# Logon Request
class LogonRequest(DTCMessage):
    def __init__(self, username="HedgeAgent", password="", heartbeat_interval=60):
        super().__init__(DTC_MSG.LOGON_REQUEST)
        self.ProtocolVersion = DTC_VERSION
        self.Username = username
        self.Password = password
        self.GeneralTextData = ""
        self.Integer_1 = 0
        self.Integer_2 = 0
        self.HeartbeatInterval = heartbeat_interval
        self.TradeAccount = ""
        self.HardwareIdentifier = ""
        self.ClientName = "HedgeAgent Client"

    def pack(self, is_vls=False):
        if is_vls:
            # VLS Packing (Type 6)
            # Fixed fields: ProtoVer(4)
            body = struct.pack("<i", self.ProtocolVersion)
            
            # VLS Fields
            body += pack_vls_string(self.Username)
            body += pack_vls_string(self.Password)
            body += pack_vls_string(self.GeneralTextData)
            
            # Fixed fields: I1(4), I2(4), HB(4)
            body += struct.pack("<iii", self.Integer_1, self.Integer_2, self.HeartbeatInterval)
            
            # VLS Fields
            body += pack_vls_string(self.TradeAccount)
            body += pack_vls_string(self.HardwareIdentifier)
            body += pack_vls_string(self.ClientName)
            
            # Fixed fields: MDComp(4)
            body += struct.pack("<i", 0)
            
            self.Size = 4 + len(body)
            header = struct.pack("<HH", self.Size, self.Type)
            return header + body
            
        else:
            # Strict Binary Packing (Type 1) - Manual offset management
            # Header(4) + ProtoVer(4) + User(32) + Pass(32) + GenText(64) + I1(4) + I2(4) + HB(4) + TradeAcc(32) + HW(64) + Client(32) + MDComp(4)
            # = 340 bytes
            
            # 1. Body part (336 bytes)
            body = struct.pack("<i", self.ProtocolVersion)        # Offset 4
            body += pack_fixed_string(self.Username, 32)          # Offset 8
            body += pack_fixed_string(self.Password, 32)          # Offset 40
            body += pack_fixed_string(self.GeneralTextData, 64)   # Offset 72
            body += struct.pack("<iii", self.Integer_1, self.Integer_2, self.HeartbeatInterval) # Offset 136
            body += pack_fixed_string(self.TradeAccount, 32)      # Offset 148
            body += pack_fixed_string(self.HardwareIdentifier, 64)# Offset 180
            body += pack_fixed_string(self.ClientName, 32)        # Offset 244
            body += struct.pack("<i", 0)                          # Offset 276 (MarketDataCompression)
            
            # Pad body to reach 280 or whatever standard size is? 
            # Actually, standard DTC fixed logon is usually 104 bytes in old versions, but grown over time.
            # Let's trust the fields we have (280 bytes) and NOT arbitrarily pad to 336.
            # Sierra Chart should adhere to the Size in header.
            
            self.Size = 4 + len(body)
            header = struct.pack("<HH", self.Size, self.Type)
            return header + body

# Heartbeat
class Heartbeat(DTCMessage):
    def __init__(self, num=0):
        super().__init__(DTC_MSG.HEARTBEAT)
        self.NumMessages = num
        self.CurrentDateTime = 0

    def pack(self):
        fmt = "<HH I q"
        body = struct.pack(fmt, 0, self.Type, self.NumMessages, self.CurrentDateTime) # Size is placeholder
        body = pad_message(body[4:]) # Pad the body part, excluding placeholder header
        self.Size = 4 + len(body)
        return struct.pack("<HH", self.Size, self.Type) + body

# Market Data Request
class MarketDataRequest(DTCMessage):
    def __init__(self, symbol_id, symbol, exchange=""):
        super().__init__(DTC_MSG.MARKET_DATA_REQUEST)
        self.RequestAction = 1  # Subscribe
        self.SymbolID = symbol_id
        self.Symbol = symbol
        self.Exchange = exchange
        self.Interval = 0

    def pack(self):
        # Fixed Length Packing (Encoding 2)
        # Header(4) + ReqAction(4) + SymbolID(4) + Symbol(64) + Exchange(16) + Interval(4)
        
        body = struct.pack("<ii", self.RequestAction, self.SymbolID)
        body += pack_fixed_string(self.Symbol, 64)
        body += pack_fixed_string(self.Exchange, 16)
        body += struct.pack("<i", self.Interval)
        
        self.Size = 4 + len(body)
        header = struct.pack("<HH", self.Size, self.Type)
        return header + body

class MarketDepthRequest(DTCMessage):
    def __init__(self, symbol_id, symbol, exchange="", num_levels=20):
        super().__init__(DTC_MSG.MARKET_DEPTH_REQUEST)
        self.RequestAction = 1 # Subscribe
        self.SymbolID = symbol_id
        self.Symbol = symbol
        self.Exchange = exchange
        self.NumLevels = num_levels

    def pack(self):
        # Header(4) + ReqAction(4) + SymbolID(4) + Symbol(64) + Exchange(16) + NumLevels(4)
        body = struct.pack("<ii", self.RequestAction, self.SymbolID)
        body += pack_fixed_string(self.Symbol, 64)
        body += pack_fixed_string(self.Exchange, 16)
        body += struct.pack("<i", self.NumLevels)
        
        self.Size = 4 + len(body)
        header = struct.pack("<HH", self.Size, self.Type)
        return header + body

class HistoricalPriceDataRequest(DTCMessage):
    def __init__(self, request_id, symbol, exchange="", record_interval=60, start_time=0):
        super().__init__(DTC_MSG.HISTORICAL_PRICE_DATA_REQUEST)
        self.RequestID = request_id
        self.Symbol = symbol
        self.Exchange = exchange
        self.RecordInterval = record_interval
        self.StartDateTime = start_time
        self.EndDateTime = 0
        self.MaxDaysToReturn = 5
        self.UseZLibCompression = 0
        self.RequestDividendAdjustedStockData = 0
        self.Integer_1 = 1 

    def pack(self, is_vls=False):
        if is_vls:
            # VLS Packing (Type 6)
            # Header(4) + ReqID(4) + Symbol(VLS) + Exch(VLS) + RecInt(4) + Start(8) + End(8) + MaxDays(4) + ZLib(4) + File(4)
            body = struct.pack("<i", self.RequestID)
            body += pack_vls_string(self.Symbol)
            body += pack_vls_string(self.Exchange)
            body += struct.pack("<iqqi", self.RecordInterval, self.StartDateTime, self.EndDateTime, self.MaxDaysToReturn)
            body += struct.pack("<ii", 0, 1) # UseZLibCompression, RequestIntradayDataFromFile
            
            self.Size = 4 + len(body)
            header = struct.pack("<HH", self.Size, self.Type)
            return header + body
        else:
            # Fixed Length Packing (Encoding 2)
            # Header(4) + ReqID(4) + Symbol(64) + Exchange(16) + RecInt(4) + Start(8) + End(8) + MaxDays(4) + ZLib(4) + File(4)
            
            body = struct.pack("<i", self.RequestID)
            body += pack_fixed_string(self.Symbol, 64)
            body += pack_fixed_string(self.Exchange, 16)
            body += struct.pack("<iqqi", self.RecordInterval, self.StartDateTime, self.EndDateTime, self.MaxDaysToReturn)
            body += struct.pack("<ii", 0, 1) # UseZLibCompression, RequestIntradayDataFromFile
            
            self.Size = 4 + len(body)
            header = struct.pack("<HH", self.Size, self.Type)
            return header + body

# Parse Trade Update - Variable length encoding
def parse_trade_update(data):
    """
    Parse MARKET_DATA_UPDATE_TRADE message
    If Sierra is using variable-length encoding, structure is different
    """
    try:
        if len(data) < 30:
            return None
        
        # Try compact binary first (Size, Type, SymbolID, AtBidOrAsk, Price, Volume, DateTime)
        # 2 + 2 + 4 + 2 + pad(2) + 8 + 8 + 8 = 36 bytes with padding
        vals = struct.unpack("<HH i H 2x d d d", data[:36])
        return {
            "SymbolID": vals[2],
            "AtBidOrAsk": vals[3],
            "Price": vals[4],
            "Volume": vals[5],
            "timestamp": vals[6]
        }
    except:
        return None

# Parse Historical Record - Variable length encoding aware
def parse_historical_record(data):
    """
    Parse HISTORICAL_PRICE_DATA_RECORD_RESPONSE
    """
    try:
        # Minimum size check (fixed and float formats)
        if len(data) < 48:
            return None
            
        # Try with float32 prices (48 bytes)
        # Header(4) + ReqID(4) + DateTime(8) + OHLC(4*4) + Vol(4) + Count(4) + BidVol(4) + AskVol(4)
        if len(data) <= 56: # common small record
            fmt = "<HH i d f f f f f I f f"
            # Some versions add a few bytes for IsFinalRecord at end
            vals = struct.unpack(fmt, data[:48])
            is_final = 0
            if len(data) >= 49:
                is_final = data[48] # uint8 at offset 48
            
            return {
                "RequestID": vals[2],
                "time": int(vals[3]),  # timestamp
                "open": vals[4],
                "high": vals[5],
                "low": vals[6],
                "close": vals[7],
                "volume": vals[8],
                "count": vals[9],
                "bid_vol": vals[10],
                "ask_vol": vals[11],
                "is_final": is_final
            }
        else:
            # Try with double prices (76 bytes)
            # Header(4) + ReqID(4) + DateTime(8) + OHLC(4*8) + Vol(8) + Count(4) + BidVol(8) + AskVol(8)
            fmt = "<HH i d d d d d d I d d"
            vals = struct.unpack(fmt, data[:76])
            is_final = 0
            if len(data) >= 77:
                is_final = data[76] # uint8 at offset 76
                
            return {
                "RequestID": vals[2],
                "time": int(vals[3]),
                "open": vals[4],
                "high": vals[5],
                "low": vals[6],
                "close": vals[7],
                "volume": vals[8],
                "count": vals[9],
                "bid_vol": vals[10],
                "ask_vol": vals[11],
                "is_final": is_final
            }
    except Exception as e:
        print(f"[DTC] Historical record parse error: {e}")
        return None
