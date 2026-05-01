import sys
import struct
from pathlib import Path

# Add project root to path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    import data_feed.dtc_protocol as dtc
    print("Imported dtc_protocol successfully")
except ImportError as e:
    print(f"Failed to import dtc_protocol: {e}")
    sys.exit(1)

def debug_pack():
    print(f"DTC_VERSION: {dtc.DTC_VERSION}")
    
    # default uses VLS (6)
    req = dtc.EncodingRequest(encoding=dtc.ENCODING_VARIABLE_LENGTH_STRINGS)
    packed = req.pack()
    print(f"Packed (VLS): {packed.hex()}")
    print(f"Size: {len(packed)}")
    
    # Decode header
    try:
        size, msg_type = struct.unpack("<HH", packed[:4])
        print(f"Header: Size={size}, Type={msg_type}")
        
        # Decode body
        # Ver(4), Enc(4), PType(4)
        ver, enc, ptype = struct.unpack("<ii4s", packed[4:])
        print(f"Body: Ver={ver}, Enc={enc}, PType={ptype}")
    except Exception as e:
        print(f"Decode failed: {e}")

if __name__ == "__main__":
    debug_pack()
