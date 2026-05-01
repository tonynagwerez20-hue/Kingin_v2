import sys
import os
import struct
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_feed import dtc_protocol as dtc

def verify_json_packing():
    print("--- Verifying Encoding Request (to JSON) ---")
    # This MUST still be Fixed format (Binary) for the bootstrap message
    enc = dtc.EncodingRequest(encoding=dtc.ENCODING_JSON)
    enc_pkt = enc.pack()
    print(f"Packet: {enc_pkt.hex()}")
    
    # Expected: Size(2) Type(2) Proto(4) Enc(4) ProtoStr(4)
    # Size=16 (10 00)
    # Type=6 (06 00) - EncodingRequest
    # Proto=8 (08 00 00 00)
    # Enc=4 (04 00 00 00) - JSON
    # Str="DTC\0" (44 54 43 00)
    expected_hex = "10000600080000000400000044544300"
    if enc_pkt.hex() == expected_hex:
        print("SUCCESS: Encoding Request (Binary Fixed) correctly requesting JSON.")
    else:
        print(f"FAIL: Expected {expected_hex}, Got {enc_pkt.hex()}")

    print("\n--- Verifying Logon Request (Headerless JSON) ---")
    logon = dtc.LogonRequest()
    logon_pkt = logon.pack_json()
    print(f"Packet Total Size: {len(logon_pkt)}")
    
    # In JSON mode over TCP, there is NO binary header.
    # The message should start with '{'
    if logon_pkt[0:1] == b'{':
        print("SUCCESS: JSON message starts with '{'.")
    else:
        print(f"FAIL: JSON message starts with {logon_pkt[0:1]}, expected '{{'.")

    # The message should end with '\0'
    if logon_pkt.endswith(b'\0'):
        print("SUCCESS: JSON message ends with null terminator.")
        json_body = logon_pkt[:-1].decode('ascii')
    else:
        print("FAIL: Missing null terminator at end of JSON.")
        json_body = logon_pkt.decode('ascii', 'ignore')
    
    print(f"JSON Body: {json_body}")
    
    data = json.loads(json_body)
    if data.get("ProtocolVersion") == 8 and data.get("Username") == "HedgeAgent":
         print("SUCCESS: JSON Logon fields are present and correct.")
    else:
         print(f"FAIL: JSON fields mismatch: {data}")

if __name__ == "__main__":
    verify_json_packing()
