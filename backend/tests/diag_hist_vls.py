import socket
import struct
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_feed import dtc_protocol as dtc

# VLS Constants
ENCODING_VLS = 6
PORT_HIST = 11098
SYMBOL = "XAUUSD"

def pack_string_vls(s):
    """Pack string with 4-byte length prefix (VLS format)"""
    b = s.encode('ascii')
    return struct.pack("<I", len(b)) + b

def test_vls_hist():
    print(f"[TEST] Connecting to Historical Port {PORT_HIST} with VLS Encoding...")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('localhost', PORT_HIST))
        s.settimeout(5.0)
        
        # 1. Encoding Request (VLS)
        print("[TEST] Sending Encoding Request (Type 6)...")
        # Size(2), Type(2), Ver(4), Encoding(4), ProtoType(4)
        # 16 bytes total
        enc_req = struct.pack("<HH i i 4s", 16, 6, 8, ENCODING_VLS, b"DTC")
        s.sendall(enc_req)
        
        time.sleep(0.5)
        
        # 2. Logon Request (VLS)
        print("[TEST] Sending Logon Request (VLS)...")
        # Header(4) + ProtoVer(4) + User(VLS) + Pass(VLS) + GenText(VLS) + I1(4) + I2(4) + HB(4) + TradeAcc(VLS) + HW(VLS) + Client(VLS) + 4
        # Base size without strings: 4 + 4 + 4+4+4 + 4 = 24 bytes fixed fields? No, VLS is complex.
        # Let's simple-pack it manually
        
        # Fixed fields start
        base = struct.pack("<i", 8) # ProtocolVersion
        
        # VLS Fields
        base += pack_string_vls("user")      # Username
        base += pack_string_vls("pass")      # Password
        base += pack_string_vls("")          # GeneralText
        
        base += struct.pack("<iii", 0, 0, 60) # I1, I2, HB
        
        base += pack_string_vls("")          # TradeAccount
        base += pack_string_vls("")          # Hardware
        base += pack_string_vls("TestClient") # ClientName
        
        base += struct.pack("<i", 0)         # MarketDataCompression
        
        # Total Size
        total_size = 4 + len(base)
        header = struct.pack("<HH", total_size, 1) # Type 1 = LOGON_REQUEST
        
        s.sendall(header + base)
        
        # 3. Read Responses
        print("[TEST] Waiting for Logon Response...")
        resp = s.recv(1024)
        print(f"[TEST] Received {len(resp)} bytes: {resp.hex()[:40]}...")
        
        if len(resp) > 0:
             # 4. Request Historical Data
             print("[TEST] Sending Historical Data Request...")
             # Header(4) + ReqID(4) + Symbol(VLS) + Exch(VLS) + Interval(4) + Start(8) + End(8) + MaxDays(4) + ZLib(4) + File(4)
             
             req_id = 100
             start_ts = int(time.time()) - 86400 * 2 # 2 days
             
             h_body = struct.pack("<i", req_id)
             h_body += pack_string_vls(SYMBOL)
             h_body += pack_string_vls("") # Exchange
             h_body += struct.pack("<i q q i", 60, start_ts, 0, 0) # Interval, Start, End, MaxDays
             h_body += struct.pack("<i i", 0, 1) # No Compression, RequestIntradayDataFromFile=1
             
             h_size = 4 + len(h_body)
             h_header = struct.pack("<HH", h_size, 800) # 800 = HISTORICAL_PRICE_DATA_REQUEST
             
             s.sendall(h_header + h_body)
             
             # Listen for data
             start_wait = time.time()
             recs = 0
             while time.time() - start_wait < 10:
                 try:
                     d = s.recv(4096)
                     if not d: break
                     print(f"[TEST] Recv {len(d)} bytes")
                     recs += 1
                 except socket.timeout:
                     break
                     
             print(f"[TEST] Received {recs} chunks of data")
        
        s.close()
        
    except Exception as e:
        print(f"[TEST] Error: {e}")

if __name__ == "__main__":
    test_vls_hist()
