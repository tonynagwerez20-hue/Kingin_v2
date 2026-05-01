import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import data_feed.dtc_protocol as dtc
import socket
import struct
import time

def main():
    HOST = "localhost"
    PORT = 11098
    SYMBOL = "XAUUSD[M]"
    
    print(f"Connecting to {HOST}:{PORT} to verify Market Data for {SYMBOL}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((HOST, PORT))
        
        # 1. Encoding
        print("[SEND] EncodingRequest (Fixed)")
        enc = dtc.EncodingRequest(dtc.ENCODING_BINARY_FIXED)
        sock.sendall(enc.pack())
        time.sleep(0.2)
        
        # 2. Logon
        print("[SEND] LogonRequest")
        logon = dtc.LogonRequest()
        sock.sendall(logon.pack())
        time.sleep(0.2)
        
        # 3. Market Data Request
        print(f"[SEND] MarketDataRequest for {SYMBOL}")
        # ID=1
        req = dtc.MarketDataRequest(1, SYMBOL)
        sock.sendall(req.pack())
        
        print("\n[RECV] Listening for Market Data (10s)...")
        start = time.time()
        recv_buffer = b""
        
        has_snapshot = False
        updates_count = 0
        
        while time.time() - start < 10:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                print(f"DEBUG RECV: {chunk.hex()}")
                recv_buffer += chunk
                
                while len(recv_buffer) >= 4:
                    size, msg_type = dtc.parse_header(recv_buffer)
                    if not size or len(recv_buffer) < size:
                        break
                        
                    msg_data = recv_buffer[:size]
                    recv_buffer = recv_buffer[size:]
                    
                    if msg_type == 104: # Snapshot
                        print(f"  -> [OK] Received MARKET_DATA_SNAPSHOT (104)")
                        has_snapshot = True
                    elif msg_type == 107: # Trade
                         print(f"  -> [OK] Received MARKET_DATA_UPDATE_TRADE (107)")
                         updates_count += 1
                    elif msg_type == 108: # BidAsk
                         print(f"  -> [OK] Received MARKET_DATA_UPDATE_BID_ASK (108)")
                         updates_count += 1
                    elif msg_type == 103: # Reject
                         print(f"  -> [FAIL] MARKET_DATA_REJECT (103)")
                         # Try to read reason?
                         # Fixed encoding: symbol(4)+reason(64)?
                         # Msg 103: SymbolID(4), RejectText(96)
                         try:
                             reason = msg_data[8:104].decode('ascii').rstrip('\x00')
                             print(f"     Reason: {reason}")
                         except:
                             pass
                         return
                    elif msg_type == 2:
                        print("  -> Received LogonResponse")
                    elif msg_type == 7:
                        print("  -> Received EncodingResponse")
                        
            except socket.timeout:
                pass
                
        if has_snapshot:
            print("\nSUCCESS: Received Market Data Snapshot!")
        elif updates_count > 0:
            print(f"\nSUCCESS: Received {updates_count} updates (but no snapshot?)")
        else:
             print("\nFAILURE: No market data received.")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
