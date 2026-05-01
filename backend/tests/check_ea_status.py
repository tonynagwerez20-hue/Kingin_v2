import sqlite3
import time
import os

db_path = r'e:\s.y.s.t.e.m\data\hedge.db'

if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT value FROM system_state WHERE key='balance_last_sync'")
    row = c.fetchone()
    conn.close()

    current_time = time.time()
    
    if row:
        last_sync = float(row[0])
        diff = current_time - last_sync
        status = "CONNECTED" if diff < 120 else "DISCONNECTED"
        print(f"EA Status: {status}")
        print(f"Last Sync: {last_sync} (Diff: {diff:.1f}s)")
        print(f"Current Time: {current_time}")
    else:
        print("EA Status: NEVER SYNCED")

except Exception as e:
    print(f"Error checking DB: {e}")
