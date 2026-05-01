"""Test SQLite database integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.hedge_db import HedgeDB

# Create/connect to database
db = HedgeDB("./data/hedge.db")

# Insert sample candles
db.insert_candle("XAUUSD", "M5", 1000.0, 1005.0, 999.0, 1002.0, 1702800000)
db.insert_candle("XAUUSD", "M5", 1002.0, 1010.0, 1001.0, 1008.0, 1702800300)
db.insert_candle("XAUUSD", "M5", 1008.0, 1012.0, 1006.0, 1009.0, 1702800600)

# Fetch candles
candles = db.get_candles("XAUUSD", "M5", limit=10)
print(f"Fetched {len(candles)} candles:")
for candle in candles:
    print(f"  {dict(candle)}")

# Insert a trade
trade_id = db.insert_trade("XAUUSD", entry_price=1002.5, lot_size=0.1, risk_amount=50.0, notes="Test trade")
print(f"\nInserted trade ID: {trade_id}")

# Close the trade
db.close_trade(trade_id, exit_price=1010.0, profit_loss=75.0)
print(f"Closed trade {trade_id}")

# Get database stats
stats = db.stats()
print(f"\nDatabase stats: {stats}")

db.close()
print("\nDatabase test completed successfully!")
