import sys
import os
from pathlib import Path
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from storage.hedge_db import HedgeDB

def verify_balance_shared_state():
    print("--- Verifying Balance Shared State Persistence ---")
    
    db = HedgeDB("data/hedge.db")
    
    # Simulate balance update from Engine
    test_balance = 12500.75
    test_ts = time.time()
    
    print(f"Update: Setting account_balance to {test_balance} and timestamp to {test_ts}")
    db.set_state("account_balance", test_balance)
    db.set_state("balance_last_sync", test_ts)
    
    # Retrieve from Dashboard context
    read_balance = db.get_state("account_balance")
    read_ts = db.get_state("balance_last_sync")
    
    print(f"Read: account_balance = {read_balance}, timestamp = {read_ts}")
    
    if read_balance == test_balance and read_ts == test_ts:
        print("\n[SUCCESS] Shared state persisted and verified via Database.")
    else:
        print("\n[FAILURE] Shared state verification failed.")

if __name__ == "__main__":
    verify_balance_shared_state()
