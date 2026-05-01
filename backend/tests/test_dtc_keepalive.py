"""
DTC Keep-Alive Verification
Tests if connection stays alive when NO data requests are sent (Logon only)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import socket
import data_feed.dtc_protocol as dtc

def main():
    print("="*60)
    print("DTC KEEP-ALIVE TEST")
    print("="*60)
    
    # 1. Connect Live Port
    PORT = 11099
    print(f"\n[TEST] Connecting to {PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    sock.connect(("localhost", PORT))

    # 2. Encoding Request (Type 6)
    print("[TEST] Sending Encoding Request...")
    enc_req = dtc.EncodingRequest(encoding=dtc.ENCODING_VARIABLE_LENGTH_STRINGS)
    sock.sendall(enc_req.pack())
    time.sleep(0.5)

    # 3. Logon
    print("[TEST] Sending Logon...")
    logon = dtc.LogonRequest()
    sock.sendall(logon.pack())
    
    # 4. Listen Loop (No Requests)
    print("[TEST] Listening for 30 seconds (sending heartbeats)...")
    start = time.time()
    next_hb = start + 10
    
    try:
        while time.time() - start < 30:
            # Send HB if needed
            if time.time() >= next_hb:
                print("[TEST] Sending Heartbeat...")
                hb = dtc.Heartbeat()
                sock.sendall(hb.pack())
                next_hb = time.time() + 10
            
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    print("[FAIL] Socket closed by remote!")
                    break
                
                print(f"[RECV] {len(chunk)} bytes")
                # Parse header
                if len(chunk) >= 4:
                    size, msg_type = dtc.parse_header(chunk)
                    print(f"       Type: {msg_type}")
                    if msg_type == dtc.DTC_MSG.LOGON_RESPONSE:
                        print("       [OK] Logon Accepted")
                    elif msg_type == dtc.DTC_MSG.HEARTBEAT:
                        print("       [OK] Heartbeat Received")
                        
            except socket.timeout:
                pass
                
    except KeyboardInterrupt:
        pass
        
    sock.close()
    print("\n[TEST] Complete")

if __name__ == "__main__":
    main()
