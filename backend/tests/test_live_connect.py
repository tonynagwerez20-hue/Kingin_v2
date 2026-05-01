import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from data_feed.dtc_client import DTCClient
import time

def main():
    print("Testing Simplified JSON DTCClient...")
    from data_feed.dtc_client import DTCClient, DTCState
    client = DTCClient()
    if client.start():
        print("[Main] Waiting for DTC to populate buffers (Timeout: 90s)...")
        timeout = 90
        start_wait = time.time()
        
        while time.time() - start_wait < timeout:
            time.sleep(2)
            from data_feed.dispatcher import ohlc_buffers
            
            # Check readiness
            h1_ready = len(ohlc_buffers.get('H1', [])) > 0
            m15_ready = len(ohlc_buffers.get('M15', [])) > 0
            m5_ready = len(ohlc_buffers.get('M5', [])) > 0
            
            counts = {tf: len(ohlc_buffers[tf]) for tf in ohlc_buffers}
            print(f"[{int(time.time() - start_wait)}s] State: {client.state.name} | L={client.live_logon} H={client.hist_logon} | Ready: H1={int(h1_ready)} M15={int(m15_ready)} M5={int(m5_ready)} | Counts: {counts}")
            
            if h1_ready and m15_ready and m5_ready and client.state == DTCState.LIVE:
                print(f"✅ SUCCESS: All buffers populated. Starting Strategy! Final: {counts}")
                break
        else:
            print("⚠️ WARNING: Timeout reached. Proceeding with potentially incomplete buffers.")
        
        if client.state != DTCState.LIVE:
            print(f"TIMEOUT: Final State was {client.state.name}")
        
        client.running = False
        client._disconnect_all()
    else:
        print("FAILED to start client")

if __name__ == "__main__":
    main()
