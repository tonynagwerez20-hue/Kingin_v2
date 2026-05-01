import sys
from pathlib import Path
import struct

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

def test_imports():
    print("[TEST] Importing DTC Modules...")
    try:
        import data_feed.dtc_protocol as dtc
        import data_feed.dtc_client as client
        print("[PASS] Imports successful.")
        
        # Test Struct Packing
        print("[TEST] Testing Logon Packing...")
        logon = dtc.LogonRequest("TestUser", "Pass123")
        packed = logon.pack()
        print(f"[PASS] Packed Logon: {len(packed)} bytes")
        
        # Test Header Parsing
        size, msg_type = dtc.parse_header(packed)
        print(f"[PASS] Parsed Header: Type={msg_type}, Size={size}")
        
        if msg_type == dtc.DTC_MSG.LOGON_REQUEST:
            print("[PASS] Message Type Logic Verified.")
        else:
            print(f"[FAIL] Message Type Mismatch: {msg_type}")
            
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        raise e

if __name__ == "__main__":
    test_imports()
