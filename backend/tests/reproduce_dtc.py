import socket
import sys
import os
import struct
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_feed import dtc_protocol as dtc

HOST = "127.0.0.1"
PORT = 11099

def test_protocol_connection():
    print(f"\n[TEST] Testing DTC Connection with dtc_protocol.py classes...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((HOST, PORT))
        print(f"[CONN] Connected to {HOST}:{PORT}")

        # 1. Encoding Request (Binary Fixed)
        print("[STEP] Sending Encoding Request (BINARY_FIXED)...")
        enc = dtc.EncodingRequest(encoding=dtc.ENCODING_BINARY_FIXED)
        enc_pkt = enc.pack()
        print(f"[DEBUG] EncReq Hex: {enc_pkt.hex()}")
        s.sendall(enc_pkt)
        
        # Read Encoding Response
        resp = s.recv(1024)
        print(f"[RECV] EncResp Hex: {resp.hex()}")
        if len(resp) >= 4:
             r_size, r_type = struct.unpack('<HH', resp[:4])
             print(f"[RECV] Header: Size={r_size}, Type={r_type}")
             if r_type == dtc.DTC_MSG.ENCODING_RESPONSE:
                 print("[SUCCESS] Encoding Accepted!")

        # 2. Logon Request (Binary Fixed)
        print("\n[STEP] Sending Logon Request (BINARY_FIXED)...")
        logon = dtc.LogonRequest()
        logon_pkt = logon.pack(is_vls=False)
        print(f"[DEBUG] Logon Packet Size: {len(logon_pkt)}")
        header_hex = logon_pkt[:16].hex()
        # Header (4) + ProtoVer (4) + Username Start (8)
        # Expect: Size(2), Type(2), Ver(4), User...
        print(f"[DEBUG] Logon Head Hex: {header_hex}")
        
        # Manually decode first few fields to verify alignment
        l_size, l_type = struct.unpack('<HH', logon_pkt[:4])
        l_ver = struct.unpack('<i', logon_pkt[4:8])[0]
        l_user = logon_pkt[8:40].decode('ascii', 'ignore').strip()
        print(f"[VERIFY] Size={l_size}, Type={l_type}, Ver={l_ver}, User='{l_user}'")
        
        s.sendall(logon_pkt)

        # Read Logon Response
        resp = s.recv(1024)
        print(f"[RECV] LogonResp Hex: {resp.hex()}")
        if len(resp) >= 4:
            r_size, r_type = struct.unpack('<HH', resp[:4])
            print(f"[RECV] Header: Size={r_size}, Type={r_type}")
            
            if r_type == dtc.DTC_MSG.LOGON_RESPONSE:
                # Parse Logon Response (Fixed V1 is 108 bytes usually? or VLS?)
                # Try to find ResultText
                print(f"[RECV] Raw Response: {resp}")

        s.close()

    except Exception as e:
        print(f"[ERR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_protocol_connection()
