"""
DTC Historical Port Test - Version 7
Tests connection to Sierra Chart Historical Data Port (11098) using Protocol v7
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import socket
import struct
import time
import data_feed.dtc_protocol as dtc

def main():
    print("="*60)
    print("DTC HISTORICAL PORT TEST (v7 Compatibility)")
    print("="*60)
    
    HIST_PORT = 11098
    
    print(f"\n[TEST] connect(localhost:{HIST_PORT})...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect(("localhost", HIST_PORT))
    print(f"[OK] Connected")

    # 1. Send Encoding Request (Type 6)
    # Even if v7, SC usually wants encoding negotiation
    print("\n[TEST] Sending Encoding Request (Type 6)...")
    enc_req = dtc.EncodingRequest(encoding=dtc.ENCODING_VARIABLE_LENGTH_STRINGS)
    sock.sendall(enc_req.pack())
    time.sleep(0.5)

    # 2. Logon with Version 7
    print("\n[TEST] Sending Logon (Protocol v7)...")
    # Manually pack v7 logon to override default v8
    # struct LogonRequest: Size(H), Type(H), ProtoVer(i), ...
    logon = dtc.LogonRequest()
    logon.ProtocolVersion = 7
    sock.sendall(logon.pack())
    print("[OK] Logon sent")
    
    # 3. Request History
    print("\n[TEST] Requesting 1 day history for XAUUSD...")
    start_time = int(time.time()) - 86400
    hist_req = dtc.HistoricalPriceDataRequest(101, "XAUUSD", start_time=start_time)
    sock.sendall(hist_req.pack())
    print("[OK] Request sent")
    
    # 4. Listen
    print("\n[TEST] Listening for response (10s)...")
    start = time.time()
    resp_count = 0
    while time.time() - start < 10:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                print("[INFO] Socket closed by remote")
                break
            
            print(f"\n[RECEIVED] {len(chunk)} bytes")
            
            # Simple heuristic check
            if b"Unsupported" in chunk:
                print("[FAIL] Server rejected protocol version")
            elif b"Historical Price Data" in chunk and b"not supported" not in chunk:
                print("[SUCCESS] Data stream detected!")
            elif len(chunk) > 100:
                print("[INFO] Large data packet received - good sign")
            
            # Dump first 64 bytes
            hex_str = ' '.join(f'{b:02x}' for b in chunk[:32])
            print(f"Dump: {hex_str}...")
            
        except socket.timeout:
            pass
            
    sock.close()

if __name__ == "__main__":
    main()
