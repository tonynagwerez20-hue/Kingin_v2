import sys
import pandas as pd
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from data_feed.factory import DataProviderFactory

def verify_normalization():
    print("\n--- Testing Data Provider Normalization ---")
    
    # Mock config for testing
    mt5_config = {
        "login": 123456,
        "password": "password",
        "server": "MetaQuotes-Demo",
        "lite_mode": True
    }
    
    sierra_config = {
        "host": "127.0.0.1",
        "port": 11099
    }

    providers = [
        ("MT5_PROVIDER", mt5_config),
        ("SIERRA_PROVIDER", sierra_config)
    ]

    for p_type, cfg in providers:
        print(f"\nTesting Provider: {p_type}")
        try:
            provider = DataProviderFactory.get_provider(p_type, cfg)
            
            # Check basic connection interface
            connected = provider.connect()
            print(f" - Connection Interface: {'OK' if connected else 'FAILED'}")
            
            # Request history (mocked if not connected)
            df = provider.get_history("XAUUSD", "M5", 10)
            
            # Validate Contract (Columns)
            expected_columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            if list(df.columns) == expected_columns or df.empty:
                print(f" - Column Normalization: PASSED")
                if not df.empty:
                    print(f" - Data Types: {df.dtypes.to_dict()}")
            else:
                print(f" - Column Normalization: FAILED (Found: {list(df.columns)})")
                
            # Check Stitch Logic
            mock_live = pd.DataFrame([{"time": pd.Timestamp.now(), "open": 2000, "high": 2001, "low": 1999, "close": 2000.5, "volume": 100}])
            stitched = provider.stitch_data(df, mock_live)
            print(f" - Hybrid Stitch Logic: {'OK' if len(stitched) >= len(df) else 'FAILED'}")

        except Exception as e:
            print(f" - Provider Initializtion Error: {e}")

if __name__ == "__main__":
    verify_normalization()
