import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import data_feed.dtc_protocol as dtc
import struct

def main():
    print("Checking LogonRequest structure for Fixed Encoding...")
    req = dtc.LogonRequest()
    packed = req.pack()
    
    print(f"Total Size: {len(packed)}")
    print(f"Expected Size: 340")
    
    if len(packed) == 340:
        print("PASS: Size matches.")
    else:
        print(f"FAIL: Size mismatch! Diff: {len(packed) - 340}")
        
    # Check Header
    size, msg_type = struct.unpack("<HH", packed[:4])
    print(f"Size Field: {size}")
    print(f"Type Field: {msg_type}")
    
    if size == 340 and msg_type == 1:
        print("PASS: Header correct.")
    else:
        print("FAIL: Header incorrect.")

    # Check Protocol Version offset (should be at index 4)
    proto_ver = struct.unpack("<i", packed[4:8])[0]
    print(f"Protocol Version: {proto_ver}")
    
    if proto_ver == 8:
         print("PASS: Protocol Version correct.")
    else:
         print("FAIL: Protocol Version incorrect.")

if __name__ == "__main__":
    main()
