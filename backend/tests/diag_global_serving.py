import requests
import time

def test_global_serving():
    print("--- Diagnostic: Global Data Serving Check ---")
    API_URL = "http://localhost:8000"
    TFs = ["M5", "M15", "H1"]
    
    for tf in TFs:
        print(f"\nChecking {tf}...")
        try:
            # 1. Test OHLC Endpoint
            resp = requests.get(f"{API_URL}/ohlc?tf={tf}&limit=5")
            if resp.status_code == 200:
                data = resp.json()
                candles = data.get("candles", [])
                print(f"  OHLC: {len(candles)} candles received.")
                if candles:
                    print(f"  Latest Candle Time: {candles[-1].get('time')}")
            else:
                print(f"  [ERROR] /ohlc {tf} returned {resp.status_code}")

            # 2. Test Delta Endpoint
            resp = requests.get(f"{API_URL}/delta?tf={tf}&limit=2")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Delta: {len(data.get('delta', []))} records received.")
            else:
                print(f"  [ERROR] /delta {tf} returned {resp.status_code}")
                
        except Exception as e:
            print(f"  [FATAL] {tf} Connection error: {e}")

if __name__ == "__main__":
    test_global_serving()
