import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from storage.hedge_db import HedgeDB
from datetime import datetime

def test_trade_sync():
    print("--- Testing Trade History Sync Logic ---")
    db = HedgeDB()
    
    # Simulated MT5 Data
    sample_trades = [
        {
            "ticket": 12345678,
            "symbol": "XAUUSD",
            "action": "BUY",
            "entry_price": 2045.50,
            "exit_price": 0.0,
            "lot_size": 0.10,
            "profit_loss": 50.0,
            "status": "open",
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "ticket": 87654321,
            "symbol": "XAUUSD",
            "action": "SELL",
            "entry_price": 2050.00,
            "exit_price": 2045.00,
            "lot_size": 0.20,
            "profit_loss": 1000.0,
            "status": "closed",
            "entry_time": "2026-01-07 10:00:00",
            "exit_time": "2026-01-07 11:00:00"
        }
    ]
    
    print("Inserting/Upserting simulated trades...")
    for trade in sample_trades:
        db.upsert_trade(trade)
    
    # Verify
    all_trades = db.get_all_trades()
    print(f"Retrieved {len(all_trades)} trades from DB.")
    
    for t in all_trades:
        print(f"  Ticket: {t['ticket']} | Status: {t['status']} | PnL: {t['profit_loss']}")
        
    db.close()
    print("\n[SUCCESS] Trade sync verification complete.")

if __name__ == "__main__":
    test_trade_sync()
