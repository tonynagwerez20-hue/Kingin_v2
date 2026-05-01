"""
Enhanced DTC Connection Diagnostic with Protocol Debugging
Captures actual DTC messages to diagnose connection failures
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import socket
import struct
import time

def main():
    print("="*60)
    print("ENHANCED DTC PROTOCOL DIAGNOSTIC")
    print("="*60)
    
    try:
        import data_feed.dtc_protocol as dtc
    except ImportError as e:
        print(f"❌ Failed to import DTC protocol: {e}")
        return
    
    # Manual connection with detailed logging
    print("\n[TEST] Creating socket...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    
    try:
        print("[TEST] Connecting to localhost:11099...")
        sock.connect(("localhost", 11099))
        print("✅ Socket connected")
        
        # Build and send logon request
        print("\n[TEST] Building logon request...")
        logon = dtc.LogonRequest()
        logon_data = logon.pack()
        print(f"  Logon packet size: {len(logon_data)} bytes")
        print(f"  Logon structure size: {logon.Size}")
        print(f"  Message type: {logon.Type} (LOGON_REQUEST)")
        print(f"  Protocol version: {logon.ProtocolVersion}")
        
        print("\n[TEST] Sending logon request...")
        sock.sendall(logon_data)
        print("✅ Logon request sent")
        
        # Wait for response
        print("\n[TEST] Waiting for logon response (timeout: 5s)...")
        recv_buffer = b""
        start_time = time.time()
        
        while time.time() - start_time < 5:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    print("❌ Socket closed by remote")
                    print("\n🔍 DIAGNOSIS:")
                    print("   Sierra Chart closed the connection immediately after logon")
                    print("\nPossible causes:")
                    print("  1. DTC Server not properly enabled in Sierra Chart")
                    print("  2. Protocol version mismatch (we're using v8)")
                    print("  3. Sierra Chart security settings rejecting connection")
                    print("  4. Logon packet format incompatible with Sierra's expectations")
                    break
                
                recv_buffer += chunk
                print(f"  Received {len(chunk)} bytes (total: {len(recv_buffer)})")
                
                # Try to parse header
                if len(recv_buffer) >= 4:
                    size, msg_type = struct.unpack("<HH", recv_buffer[:4])
                    print(f"\n✅ Received message:")
                    print(f"  Size: {size} bytes")
                    print(f"  Type: {msg_type}", end="")
                    
                    # Identify message type
                    if msg_type == dtc.DTC_MSG.LOGON_RESPONSE:
                        print(" (LOGON_RESPONSE) ✅")
                        print("\n✅ SUCCESS: Sierra Chart accepted the connection!")
                        print("\nNext step: Historical data request should work")
                        break
                    elif msg_type == dtc.DTC_MSG.LOGOFF:
                        print(" (LOGOFF) ❌")
                        print("\n❌ Sierra Chart sent LOGOFF")
                        print("   This means it explicitly rejected the connection")
                        break
                    elif msg_type == dtc.DTC_MSG.HEARTBEAT:
                        print(" (HEARTBEAT)")
                    else:
                        print(f" (Unknown type: {msg_type})")
                    
                    if len(recv_buffer) >= size:
                        # We have the full message
                        if msg_type == dtc.DTC_MSG.LOGON_RESPONSE:
                            # Parse logon response fields
                            try:
                                # This is a simplified parse - actual structure may vary
                                vals = struct.unpack("<HHi", recv_buffer[:8])
                                result = vals[2] if len(vals) > 2 else 0
                                if result == 1:
                                    print(f"  Result: SUCCESS")
                                else:
                                    print(f"  Result: {result} (may indicate error)")
                            except:
                                pass
                        break
                        
            except socket.timeout:
                print("  (waiting for data...)")
                continue
        else:
            print("\n⚠️  No response received within 5 seconds")
            print("\nPossible causes:")
            print("  1. Sierra Chart DTC server is not running")
            print("  2. Wrong port (should be 11099)")
            print("  3. Firewall blocking localhost communication")
        
    except ConnectionRefusedError:
        print("X Connection refused")
        print("\nDIAGNOSIS:")
        print("   Port 11099 is not accepting connections")
        print("\nTroubleshooting:")
        print("  1. Open Sierra Chart")
        print("  2. Go to: Global Settings -> Data/Trade Service Settings")
        print("  3. Check: 'DTC Protocol Server' is enabled")
        print("  4. Verify: Server Port = 11099")
        print("  5. Click 'OK' to apply settings")
        print("  6. Restart Sierra Chart if needed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            sock.close()
        except:
            pass
    
    print("\n" + "="*60)
    print("SIERRA CHART CONFIGURATION CHECKLIST")
    print("="*60)
    print("""
1. Sierra Chart is running: [ ]
2. XAUUSD chart is open: [ ]
3. Chart has historical data (Tools → Download Historical Data): [ ]
4. Global Settings opened: [ ]
5. Navigate to: Data/Trade Service Settings → DTC Protocol Server: [ ]
6. Settings to verify:
   - [✓] Enable DTC Protocol Server
   - Port: 11099
   - Allowed IPs: 127.0.0.1 (or leave blank for all)
   - Encoding: Binary or Binary with Variable Length Strings
   - Authentication: None (or set username/password if required)
7. Click OK to apply: [ ]
8. Check Sierra's message log for connection attempts: [ ]

If all above are checked and still failing, you may need to:
- Update Sierra Chart to latest version
- Check Windows Firewall isn't blocking port 11099
- Try using CSV mode instead (set DATA_SOURCE_TYPE=CSV in .env)
""")

if __name__ == "__main__":
    main()
