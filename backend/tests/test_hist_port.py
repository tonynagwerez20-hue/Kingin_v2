"""
DTC Historical Port Diagnostic
Tests connection to Sierra Chart Historical Data Port (default 11098)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import socket
import struct
import time
import data_feed.dtc_protocol as dtc

def hex_dump(data, label=""):
    print(f"\n{label}")
    print("-" * 60)
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"{i:06x}  {hex_str:<48} {ascii_str}")

def main():
    print("="*60)
    print("DTC HISTORICAL PORT TEST (11098)")
    print("="*60)
    
    HIST_PORT = 11098
    
    # 1. Test Connection
    print(f"\n[TEST] connect(localhost:{HIST_PORT})...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    
    try:
        sock.connect(("localhost", HIST_PORT))
        print(f"[OK] Connected to port {HIST_PORT}")
    except ConnectionRefusedError:
        print(f"[FAIL] Connection refused on port {HIST_PORT}")
        print("      Sierra Chart Historical Data Server is likely disabled.")
        return
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        return

    # 2. Negotiate Encoding (Try 6 first)
    print("\n[TEST] Sending Encoding Request (Type 6)...")
    enc_req = dtc.EncodingRequest(encoding=dtc.ENCODING_VARIABLE_LENGTH_STRINGS)
    sock.sendall(enc_req.pack())
    time.sleep(0.5)

    # 3. Logon
    print("\n[TEST] Sending Logon...")
    logon = dtc.LogonRequest()
    sock.sendall(logon.pack())
    print("[OK] Logon sent")
    
    # 4. Request History
    print("\n[TEST] Requesting 1 day history for XAUUSD...")
    start_time = int(time.time()) - 86400
    hist_req = dtc.HistoricalPriceDataRequest(101, "XAUUSD", start_time=start_time)
    sock.sendall(hist_req.pack())
    print("[OK] Request sent")
    
    # 5. Listen
    print("\n[TEST] Listening for response (10s)...")
    start = time.time()
    while time.time() - start < 10:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                print("[INFO] Socket closed by remote")
                break
            
            print(f"\n[RECEIVED] {len(chunk)} bytes")
            hex_dump(chunk, "Packet Dump")
            
            # Check for "Not Supported" error
            if b"not supported" in chunk:
                print("\n[FAIL] Server replied: 'not supported'")
            elif b"XAUUSD" in chunk and len(chunk) > 50:
                 # Likely a header or record
                 print("\n[SUCCESS] Received potential data!")
                 
        except socket.timeout:
            pass
        except KeyboardInterrupt:
            break
            
    sock.close()

if __name__ == "__main__":
    main()
