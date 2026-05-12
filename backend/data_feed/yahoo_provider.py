"""
Web-based data provider using Yahoo Finance.
Alternative to MT5 for testing on Linux/non-Windows platforms.
"""
import pandas as pd
import yfinance as yf
from typing import Dict, Optional
import time

class YahooFinanceProvider:
    """Fetches gold futures data from Yahoo Finance."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.symbol = self.config.get("symbol", "GC=F")  # Gold futures
        self.intervals = {
            "M5": "5m",
            "M15": "15m", 
            "H1": "1h",
            "H2": "2h",
            "H4": "4h",
            "D": "1d"
        }
        self._last_fetch = {}
        
    def connect(self) -> bool:
        """Test connection by fetching a small sample."""
        try:
            ticker = yf.Ticker(self.symbol)
            df = ticker.history(period="1d", interval="1h")
            return len(df) > 0
        except Exception as e:
            print(f"[YahooFinProvider] Connection test failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return True
    
    def get_latest_candles(self, symbol: str, timeframe: str, count: int = 20) -> list:
        """Get latest candles for a symbol/timeframe."""
        # Map to yfinance interval
        yf_interval = self.intervals.get(timeframe, "1h")
        
        # Map period based on count and interval
        if timeframe == "M5":
            period = "1d"  # 5m only works for 1d
        elif timeframe == "M15":
            period = "5d"
        elif timeframe == "H1":
            period = "5d"
        else:
            period = "1mo"
        
        try:
            ticker = yf.Ticker(self.symbol)
            df = ticker.history(period=period, interval=yf_interval)
            
            if df.empty:
                return []
            
            # Convert to standard candle format
            candles = []
            for idx, row in df.iterrows():
                candles.append({
                    "time": int(idx.timestamp()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if "Volume" in row else 0
                })
            
            # Return last 'count' candles
            return candles[-count:]
            
        except Exception as e:
            print(f"[YahooFinProvider] Error fetching {timeframe}: {e}")
            return []
    
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """Get current price and spread estimate."""
        try:
            ticker = yf.Ticker(self.symbol)
            df = ticker.history(period="1d", interval="5m")
            
            if df.empty:
                return None
            
            last = df.iloc[-1]
            bid = last["Close"]
            # Estimate spread (yfinance doesn't provide spread)
            # Gold typically has 0.1-0.3 spread
            ask = bid + 0.2
            
            return {
                "bid": bid,
                "ask": ask,
                "spread": ask - bid,
                "last": last["Close"]
            }
        except Exception as e:
            print(f"[YahooFinProvider] Error getting price: {e}")
            return None


# Alternative function to populate buffers for testing
def populate_buffers_from_yahoo(ohlc_buffers: Dict, delta_buffers: Dict):
    """Populate buffers with Yahoo Finance data."""
    provider = YahooFinanceProvider()
    
    if not provider.connect():
        print("[YahooFinProvider] Failed to connect")
        return
    
    print("[YahooFinProvider] Populating buffers...")
    
    # Fetch all timeframes
    for tf in ["M5", "M15", "H1"]:
        candles = provider.get_latest_candles("GC=F", tf, 50)
        if candles:
            ohlc_buffers[tf] = candles
            print(f"[YahooFinProvider] Loaded {len(candles)} {tf} candles")
    
    print("[YahooFinProvider] Buffers populated successfully")


if __name__ == "__main__":
    # Test the provider
    provider = YahooFinanceProvider()
    
    print(f"Connected: {provider.connect()}")
    
    for tf in ["M5", "M15", "H1"]:
        candles = provider.get_latest_candles("GC=F", tf, 10)
        print(f"{tf}: {len(candles)} candles")
        if candles:
            print(f"  Last: {candles[-1]}")