import sys
import asyncio
import time
from pathlib import Path

# Add project root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    from data_feed.dtc_client import DTCClient
    print("[TEST] Imported DTCClient successfully.")
except ImportError as e:
    print(f"[FAIL] Import Error: {e}")
    sys.exit(1)

def verify_connection():
    print("[TEST] Initializing DTCClient...")
    client = DTCClient(host="127.0.0.1", port_live=11099, port_hist=11098)
    
    print("[TEST] Attempting connection...")
    try:
        success = client.connect()
        if success:
            print("[SUCCESS] DTCClient.connect() returned True!")
            if client.live_connected:
                print("[SUCCESS] LIVE Socket connected.")
            else:
                print("[FAIL] LIVE Socket NOT connected.")
        else:
            print("[FAIL] DTCClient.connect() returned False.")
            
        # Give it more time to complete the handshake and process the logon response
        print("[TEST] Waiting 3 seconds for handshake completion...")
        time.sleep(3)
        
        if client.live_connected:
            print("[SUCCESS] LIVE connection verified.")
        else:
            print("[FAIL] LIVE connection lost or never established.")
            
    except Exception as e:
        print(f"[FAIL] Exception during connect: {e}")
    finally:
        # Cleanup
        client.running = False
        if client.sock_live: client.sock_live.close()
        if client.sock_hist: client.sock_hist.close()

if __name__ == "__main__":
    verify_connection()
