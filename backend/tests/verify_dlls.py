import ctypes
import os
import sys
import platform

# Paths to the DLLs in the project
base_path = r"e:\s.y.s.t.e.m\mt5\mql-zmq-master\mql-zmq-master\Library\MT5"
libsodium_path = os.path.join(base_path, "libsodium.dll")
libzmq_path = os.path.join(base_path, "libzmq.dll")

print(f"Python Architecture: {platform.architecture()[0]}")
print(f"Checking DLLs in: {base_path}")

def test_dll(path, name):
    print(f"\n[{name}] Testing...")
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return False
        
    try:
        # Try to load
        dll = ctypes.cdll.LoadLibrary(path)
        print(f"OK Successfully loaded {name}")
        return True
    except OSError as e:
        print(f"FAIL Failed to load {name}")
        print(f"   Error: {e}")
        print("   Possible verify causes:")
        print("   1. Architecture mismatch (32-bit vs 64-bit)")
        print("   2. Missing dependencies (Visual C++ Redistributable)")
        return False
    except Exception as e:
        print(f"FAIL Unexpected error: {e}")
        return False

# Test Sodium first (dependency of ZMQ often)
s_ok = test_dll(libsodium_path, "libsodium.dll")

# Test ZMQ
z_ok = test_dll(libzmq_path, "libzmq.dll")

if s_ok and z_ok:
    print("\n[RESULT] DLLs are VALID and loadable on this system.")
else:
    print("\n[RESULT] DLLs are INVALID or missing dependencies.")
    print("Please install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe")
