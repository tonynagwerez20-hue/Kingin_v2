import sys
import os
import struct

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_feed import dtc_protocol as dtc

def verify_vls_packing():
    print("--- Verifying Encoding Request (VLS) ---")
    # This should still produce a FIXED format packet, but with Encoding=6
    enc = dtc.EncodingRequest(encoding=dtc.ENCODING_VARIABLE_LENGTH_STRINGS)
    enc_pkt = enc.pack()
    print(f"Packet: {enc_pkt.hex()}")
    # Expected: Size(2) Type(2) Proto(4) Enc(4) ProtoStr(4)
    # Size=16 (10 00)
    # Type=6 (06 00)
    # Proto=8 (08 00 00 00)
    # Enc=6 (06 00 00 00)  <-- THIS CHANGED
    # Str="DTC\0" (44 54 43 00)
    
    expected_hex = "10000600080000000600000044544300"
    if enc_pkt.hex() == expected_hex:
        print("SUCCESS: Encoding Request matches FIXED format with VLS encoding type.")
    else:
        print(f"FAIL: Expected {expected_hex}, Got {enc_pkt.hex()}")


    print("\n--- Verifying Logon Request (VLS) ---")
    logon = dtc.LogonRequest()
    logon_pkt = logon.pack(is_vls=True)
    print(f"Packet Size: {len(logon_pkt)}")
    print(f"Header + ProtoVer: {logon_pkt[:8].hex()}")
    
    # Verify Header
    size = struct.unpack('<H', logon_pkt[:2])[0]
    dtype = struct.unpack('<H', logon_pkt[2:4])[0]
    ver = struct.unpack('<i', logon_pkt[4:8])[0]
    
    print(f"Size: {size}")
    print(f"Type: {dtype} (Expected 1)")
    print(f"Ver:  {ver} (Expected 8)")
    
    if ver != 8:
        print("CRITICAL FAIL: Protocol Version is not 8!")
    else:
        print("SUCCESS: Protocol Version is 8.")

    # Check Offset 8 (Username VLS)
    # Should be Length(4) + String
    user_len = struct.unpack('<I', logon_pkt[8:12])[0]
    user_str = logon_pkt[12:12+user_len].decode('ascii')
    
    print(f"Username Len: {user_len}")
    print(f"Username Str: {user_str}")
    
    if user_str == "HedgeAgent":
        print("SUCCESS: Username encoded correctly as VLS.")
    else:
        print(f"FAIL: Username mismatch: {user_str}")

if __name__ == "__main__":
    verify_vls_packing()
