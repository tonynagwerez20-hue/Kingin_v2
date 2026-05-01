import sys
import os
import struct

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_feed import dtc_protocol as dtc

def verify_packing():
    print("--- Verifying Encoding Request ---")
    enc = dtc.EncodingRequest(encoding=dtc.ENCODING_BINARY_FIXED)
    enc_pkt = enc.pack()
    print(f"Packet: {enc_pkt.hex()}")
    # Hex: Size(2) Type(2) Proto(4) Enc(4) ProtoStr(4)
    # Expected: 1000 0600 08000000 01000000 44544300
    # Size=16 (10 00)
    # Type=6 (06 00)
    # Proto=8 (08 00 00 00)
    # Enc=1 (01 00 00 00)
    # Str="DTC\0" (44 54 43 00)
    
    expected_hex = "10000600080000000100000044544300"
    if enc_pkt.hex() == expected_hex:
        print("SUCCESS: Encoding Request matches expectations.")
    else:
        print(f"FAIL: Expected {expected_hex}, Got {enc_pkt.hex()}")


    print("\n--- Verifying Logon Request (Fixed) ---")
    logon = dtc.LogonRequest()
    logon_pkt = logon.pack(is_vls=False)
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

    if size != len(logon_pkt):
        print(f"FAIL: Size field {size} != Len {len(logon_pkt)}")
    else:
        print("SUCCESS: Size field matches packet length.")

    # Check Offset 8 (Username)
    user_hex = logon_pkt[8:40].hex()
    print(f"Username Hex (First 32 bytes): {user_hex}")
    # "HedgeAgent" in hex: 48 65 64 67 65 41 67 65 6e 74
    if user_hex.startswith("48656467654167656e74"):
        print("SUCCESS: Username starts correctly.")
    else:
        print("FAIL: Username seems wrong.")

if __name__ == "__main__":
    verify_packing()
