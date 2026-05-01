import requests
import time

def test_h1_serving():
    print("--- Diagnostic: Testing H1 Data Serving ---")
    API_URL = "http://localhost:8000"
    
    try:
        # 1. Test OHLC Endpoint for H1
        print("Fetching /ohlc?tf=H1&limit=5...")
        resp = requests.get(f"{API_URL}/ohlc?tf=H1&limit=5")
        if resp.status_code == 200:
            data = resp.json()
            candles = data.get("candles", [])
            print(f"  Status: SUCCESS")
            print(f"  Candles Received: {len(candles)}")
            if candles:
                latest = candles[-1]
                print(f"  Latest Close: {latest.get('close')}")
            else:
                print("  [WARNING] No candles returned for H1.")
        else:
            print(f"  [ERROR] /ohlc H1 returned {resp.status_code}")

        # 2. Test Delta Endpoint for H1
        print("\nFetching /delta?tf=H1&limit=2...")
        resp = requests.get(f"{API_URL}/delta?tf=H1&limit=2")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Status: SUCCESS")
            print(f"  Delta Count: {len(data.get('delta', []))}")
        else:
            print(f"  [ERROR] /delta H1 returned {resp.status_code}")
            
    except Exception as e:
        print(f"  [FATAL] Connection error: {e}")

if __name__ == "__main__":
    test_h1_serving()
