import aiohttp
import asyncio
import json

async def diagnostic():
    url = "http://127.0.0.1:8000"
    print(f"--- KingIn Engine Diagnostic ---")
    print(f"Target API: {url}")
    
    async with aiohttp.ClientSession() as session:
        # 1. Check API Health
        try:
            async with session.get(f"{url}/api/engine/state") as resp:
                data = await resp.json()
                print(f"[OK] API reached. Engine State: {data.get('state', 'Unknown')}")
        except Exception as e:
            print(f"[FAIL] API NOT REACHED: {e}")
            return

        # 2. Check Data Feed (OHLC)
        timeframes = ["H1", "M15", "M5"]
        for tf in timeframes:
            try:
                async with session.get(f"{url}/ohlc?tf={tf}&limit=50") as resp:
                    candles = await resp.json()
                    count = len(candles)
                    if count >= 10:
                        print(f"[OK] {tf} Buffer: {count} candles (Healthy)")
                    else:
                        print(f"[WARN] {tf} Buffer: {count} candles (Too few, need 10+)")
            except Exception as e:
                print(f"[FAIL] Could not fetch {tf} data: {e}")

        # 3. Check MT5 Connection
        try:
            async with session.get(f"{url}/latest-tick") as resp:
                tick = await resp.json()
                if tick:
                    print(f"[OK] MT5 Connection: ACTIVE (Tick received)")
                else:
                    print(f"[FAIL] MT5 Connection: NO DATA (Is EA running in MT5?)")
        except Exception as e:
            print(f"[FAIL] MT5 Connection check failed: {e}")

if __name__ == "__main__":
    asyncio.run(diagnostic())
