"""
DTC Raw Packet Capture Tool
Captures and displays raw binary data from Sierra Chart to reverse-engineer struct format
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import socket
import struct
import time
import binascii

def hex_dump(data, label=""):
    """Pretty print hex dump of binary data"""
    if label:
        print(f"\n{label}")
    print("Offset  Hex                                              ASCII")
    print("-" * 70)
    
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"{i:06x}  {hex_str:<48} {ascii_str}")
    print()

def main():
    print("="*70)
    print("DTC RAW PACKET CAPTURE")
    print("="*70)
    
    # Import protocol
    try:
        import data_feed.dtc_protocol as dtc
    except ImportError as e:
        print(f"[ERROR] Failed to import DTC protocol: {e}")
        return
    
    # Connect
    print("\n[1] Connecting to Sierra Chart DTC server...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    
    try:
        sock.connect(("localhost", 11099))
        print("[OK] Connected to localhost:11099")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return
    
    # Send Encoding Request
    print("\n[2a] Sending Encoding Request (Type 6)...")
    enc_req = dtc.EncodingRequest(encoding=dtc.ENCODING_VARIABLE_LENGTH_STRINGS)
    sock.sendall(enc_req.pack())
    time.sleep(0.5)

    # Send logon
    print("\n[2b] Sending Logon Request...")
    logon = dtc.LogonRequest()
    logon_data = logon.pack()
    
    hex_dump(logon_data, "[SENT] Logon Request:")
    sock.sendall(logon_data)
    print("[OK] Logon sent")
    
    time.sleep(1)

    # Send Historical Data Request
    print("\n[2c] Sending Historical Data Request...")
    # Request 1 day of data
    start_time = int(time.time()) - 86400
    hist_req = dtc.HistoricalPriceDataRequest(101, "XAUUSD", start_time=start_time)
    hist_data = hist_req.pack()
    hex_dump(hist_data, "[SENT] Historical Data Request:")
    sock.sendall(hist_data)
    print("[OK] Historical request sent")
    
    # Receive and display responses
    print("\n[3] Capturing responses for 20 seconds...")
    print("    (Press Ctrl+C to stop early)\n")
    
    recv_buffer = b""
    start_time = time.time()
    message_count = 0
    
    try:
        while time.time() - start_time < 20:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    print("[INFO] Socket closed by remote")
                    break
                
                recv_buffer += chunk
                
                # Try to parse messages
                while len(recv_buffer) >= 4:
                    size, msg_type = struct.unpack("<HH", recv_buffer[:4])
                    
                    if len(recv_buffer) < size:
                        break  # Need more data
                    
                    # Extract full message
                    msg_data = recv_buffer[:size]
                    recv_buffer = recv_buffer[size:]
                    
                    message_count += 1
                    
                    # Identify message type
                    msg_name = "UNKNOWN"
                    if msg_type == dtc.DTC_MSG.LOGON_RESPONSE:
                        msg_name = "LOGON_RESPONSE"
                    elif msg_type == dtc.DTC_MSG.HEARTBEAT:
                        msg_name = "HEARTBEAT"
                    elif msg_type == dtc.DTC_MSG.MARKET_DATA_UPDATE_TRADE:
                        msg_name = "MARKET_DATA_UPDATE_TRADE"
                    elif msg_type == dtc.DTC_MSG.HISTORICAL_PRICE_DATA_RESPONSE_HEADER:
                        msg_name = "HISTORICAL_RESPONSE_HEADER"
                    elif msg_type == dtc.DTC_MSG.HISTORICAL_PRICE_DATA_RECORD_RESPONSE:
                        msg_name = "HISTORICAL_RECORD"
                    elif msg_type == dtc.DTC_MSG.MARKET_DATA_SNAPSHOT:
                        msg_name = "MARKET_DATA_SNAPSHOT"
                    
                    print(f"\n{'='*70}")
                    print(f"MESSAGE #{message_count}")
                    print(f"{'='*70}")
                    print(f"Type: {msg_type} ({msg_name})")
                    print(f"Size: {size} bytes")
                    
                    # Hex dump
                    hex_dump(msg_data)
                    
                    # Try to parse key fields based on type
                    if msg_type == dtc.DTC_MSG.HISTORICAL_PRICE_DATA_RECORD_RESPONSE:
                        print("PARSING ATTEMPT (Historical Record):")
                        print("-" * 70)
                        
                        # Try different struct formats
                        print("\n[Format 1] Compact Binary (float32):")
                        try:
                            # Header(4) + ReqID(4) + DateTime(8) + OHLC(4*4) + Vol(4) + Count(4) + BidVol(4) + AskVol(4)
                            vals = struct.unpack("<HH i d f f f f f I f f", msg_data[:48])
                            print(f"  RequestID: {vals[2]}")
                            print(f"  DateTime:  {vals[3]}")
                            print(f"  Open:  {vals[4]}")
                            print(f"  High:  {vals[5]}")
                            print(f"  Low:   {vals[6]}")
                            print(f"  Close: {vals[7]}")
                            print(f"  Volume: {vals[8]}")
                            print(f"  Count:  {vals[9]}")
                            print(f"  BidVol: {vals[10]}")
                            print(f"  AskVol: {vals[11]}")
                        except Exception as e:
                            print(f"  ERROR: {e}")
                        
                        print("\n[Format 2] Extended Binary (double):")
                        try:
                            # All doubles
                            vals = struct.unpack("<HH i d d d d d d I d d", msg_data[:76])
                            print(f"  RequestID: {vals[2]}")
                            print(f"  DateTime:  {vals[3]}")
                            print(f"  Open:  {vals[4]}")
                            print(f"  High:  {vals[5]}")
                            print(f"  Low:   {vals[6]}")
                            print(f"  Close: {vals[7]}")
                            print(f"  Volume: {vals[8]}")
                            print(f"  Count:  {vals[9]}")
                            print(f"  BidVol: {vals[10]}")
                            print(f"  AskVol: {vals[11]}")
                        except Exception as e:
                            print(f"  ERROR: {e}")
                        
                        print("\n[Format 3] Variable Length Strings (try different offsets):")
                        # Try reading as int64 timestamp
                        try:
                            vals = struct.unpack("<HH i q f f f f f I f f", msg_data[:48])
                            print(f"  RequestID: {vals[2]}")
                            print(f"  DateTime (as int64):  {vals[3]}")
                            print(f"  Open:  {vals[4]}")
                            print(f"  High:  {vals[5]}")
                            print(f"  Low:   {vals[6]}")
                            print(f"  Close: {vals[7]}")
                            print(f"  Volume: {vals[8]}")
                        except Exception as e:
                            print(f"  ERROR: {e}")
                    
                    elif msg_type == dtc.DTC_MSG.MARKET_DATA_UPDATE_TRADE:
                        print("PARSING ATTEMPT (Trade Update):")
                        print("-" * 70)
                        try:
                            vals = struct.unpack("<HH i H 2x d d d", msg_data[:36])
                            print(f"  SymbolID: {vals[2]}")
                            print(f"  AtBidOrAsk: {vals[3]}")
                            print(f"  Price: {vals[4]}")
                            print(f"  Volume: {vals[5]}")
                            print(f"  DateTime: {vals[6]}")
                        except Exception as e:
                            print(f"  ERROR: {e}")
                    
            except socket.timeout:
                pass
            except KeyboardInterrupt:
                print("\n\n[INFO] Capture interrupted by user")
                break
            
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        sock.close()
    
    print(f"\n{'='*70}")
    print(f"CAPTURE COMPLETE")
    print(f"{'='*70}")
    print(f"Total messages captured: {message_count}")
    print("\nAnalyze the hex dumps above to determine correct struct format.")
    print("Look for patterns in the OHLC values (should be around 2600-2700 for XAUUSD)")

if __name__ == "__main__":
    main()
