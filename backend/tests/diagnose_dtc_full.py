"""
Enhanced DTC Diagnostic - Captures ALL message types including rejections
Based on Sierra Chart troubleshooting guide
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import socket
import struct
import time
import data_feed.dtc_protocol as dtc

# Additional message types from Sierra Chart spec
DTC_MSG_LOGOFF = 5
DTC_MSG_HISTORICAL_DATA_REJECT = 8
DTC_MSG_MARKET_DATA_REJECT = 103

def parse_string_vls(data, offset):
    """Parse a variable-length string from binary data"""
    if len(data) < offset + 4:
        return "", offset
    str_len = struct.unpack("<I", data[offset:offset+4])[0]
    offset += 4
    if len(data) < offset + str_len:
        return "", offset
    string = data[offset:offset+str_len].decode('utf-8', errors='replace').rstrip('\x00')
    return string, offset + str_len

def main():
    print("="*70)
    print("ENHANCED DTC DIAGNOSTIC - FULL MESSAGE CAPTURE")
    print("="*70)
    
    # Test both ports
    for PORT, NAME in [(11099, "LIVE"), (11098, "HISTORICAL")]:
        print(f"\n{'='*70}")
        print(f"TESTING PORT {PORT} ({NAME})")
        print(f"{'='*70}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect(("localhost", PORT))
            print(f"[OK] Connected to {PORT}")
            
            # 1. Encoding Request
            print(f"[SEND] EncodingRequest (Type 6 - FIXED)")
            enc_req = dtc.EncodingRequest(encoding=dtc.ENCODING_BINARY_FIXED)
            sock.sendall(enc_req.pack())
            time.sleep(0.3)
            
            # 2. Logon
            print(f"[SEND] LogonRequest (Protocol v7)")
            logon = dtc.LogonRequest()
            sock.sendall(logon.pack())
            time.sleep(0.5)
            
            # 3. Try requesting data (will likely cause rejection)
            if PORT == 11099:
                print(f"[SEND] MarketDataRequest for XAUUSD")
                req = dtc.MarketDataRequest(1, "XAUUSD")
                sock.sendall(req.pack())
            else:
                print(f"[SEND] HistoricalPriceDataRequest for XAUUSD (5 days)")
                start_time = int(time.time()) - 432000
                hist_req = dtc.HistoricalPriceDataRequest(100, "XAUUSD", start_time=start_time)
                sock.sendall(hist_req.pack())
            
            # 4. Listen for responses
            print(f"\n[RECV] Listening for responses (10 seconds)...")
            start = time.time()
            recv_buffer = b""
            
            while time.time() - start < 10:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        print(f"[INFO] Socket closed by remote")
                        break
                    
                    recv_buffer += chunk
                    
                    # Parse all messages in buffer
                    while len(recv_buffer) >= 4:
                        size, msg_type = dtc.parse_header(recv_buffer)
                        if not size or len(recv_buffer) < size:
                            break
                        
                        msg_data = recv_buffer[:size]
                        recv_buffer = recv_buffer[size:]
                        
                        print(f"\n  [MSG] Type {msg_type}, Size {size} bytes")
                        
                        # Handle specific message types
                        if msg_type == 7:  # Encoding Response
                            print(f"       -> EncodingResponse")
                            try:
                                # ProtocolVersion(4), Encoding(4), ProtocolType(4)
                                # The body starts after the 4-byte header (not 8! Size included in header)
                                # Fields: ProtocolVersion(4), Encoding(4), ProtocolType(4)
                                if len(msg_data) >= 4 + 12: 
                                    v, e, pt = struct.unpack("<i i 4s", msg_data[4:16])
                                    print(f"       -> Protocol Version: {v}")
                                    print(f"       -> Encoding: {e} ({'VLS' if e==6 else 'Fixed' if e==2 else 'Unknown'})")
                                    print(f"       -> Protocol Type: {pt.decode('ascii').rstrip(chr(0))}")
                            except Exception as e:
                                print(f"       -> Failed to parse EncodingResponse: {e}")
                        
                        elif msg_type == 2:  # Logon Response
                            print(f"       -> LogonResponse")
                            # Try to parse result text
                            if len(msg_data) > 20:
                                try:
                                    # Result code at offset 8
                                    result = struct.unpack("<i", msg_data[8:12])[0]
                                    print(f"       -> Result Code: {result}")
                                    # Try to extract text (VLS format)
                                    if len(msg_data) > 40:
                                        text, _ = parse_string_vls(msg_data, 40)
                                        if text:
                                            print(f"       -> Message: '{text}'")
                                except:
                                    pass
                        
                        elif msg_type == DTC_MSG_LOGOFF:  # Logoff
                            print(f"       -> [LOGOFF] Server is disconnecting us!")
                            # Try to extract reason
                            try:
                                reason, _ = parse_string_vls(msg_data, 4)
                                print(f"       -> Reason: '{reason}'")
                            except:
                                print(f"       -> (Could not parse reason)")
                        
                        elif msg_type == DTC_MSG_HISTORICAL_DATA_REJECT:  # Historical Data Reject
                            print(f"       -> [REJECTED] HistoricalDataReject")
                            try:
                                # RequestID at offset 4
                                req_id = struct.unpack("<i", msg_data[4:8])[0]
                                print(f"       -> RequestID: {req_id}")
                                # Reject text
                                text, _ = parse_string_vls(msg_data, 8)
                                if text:
                                    print(f"       -> ERROR: '{text}'")
                            except:
                                print(f"       -> (Could not parse error message)")
                        
                        elif msg_type == DTC_MSG_MARKET_DATA_REJECT:  # Market Data Reject
                            print(f"       -> [REJECTED] MarketDataReject")
                            try:
                                # Symbol ID at offset 4
                                sym_id = struct.unpack("<i", msg_data[4:8])[0]
                                print(f"       -> SymbolID: {sym_id}")
                                # Reject text
                                text, _ = parse_string_vls(msg_data, 8)
                                if text:
                                    print(f"       -> ERROR: '{text}'")
                            except:
                                print(f"       -> (Could not parse error message)")
                        
                        elif msg_type == 3:  # Heartbeat
                            print(f"       -> Heartbeat")
                        
                        else:
                            print(f"       -> (Unknown type)")
                
                except socket.timeout:
                    pass
                except Exception as e:
                    print(f"[ERROR] {e}")
                    break
            
            sock.close()
            
        except ConnectionRefusedError:
            print(f"[FAIL] Connection refused - port {PORT} not accepting connections")
        except Exception as e:
            print(f"[FAIL] {e}")
    
    print(f"\n{'='*70}")
    print("DIAGNOSTIC COMPLETE")
    print("="*70)
    print("\nACTION ITEMS:")
    print("1. Check above for [REJECTED] or [LOGOFF] messages")
    print("2. Check Sierra Chart: Window >> Message Log for red text")
    print("3. Verify symbol format matches Chart Title Bar EXACTLY")
    print("4. Verify server settings: Global Settings >> Sierra Chart Server Settings")

if __name__ == "__main__":
    main()
