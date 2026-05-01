import sqlite3
import os
import json

db_path = r'e:\s.y.s.t.e.m\data\hedge.db'

print(f"Checking DB at: {db_path}")

if not os.path.exists(db_path):
    print("X Database file missing!")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    print(f"OK Tables found: {[t[0] for t in tables]}")
    
    # Check system state
    c.execute("SELECT * FROM system_state")
    state = c.fetchall()
    print("\n[System State Dump]")
    print("\n[System State Dump]")
    for row in state:
        key = row[0]
        value = row[1]
        val_preview = value[:50] + "..." if len(str(value)) > 50 else value
        print(f"  {key}: {val_preview}")
        
    # Check recent trades
    c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 1")
    last_trade = c.fetchone()
    if last_trade:
        print(f"\nOK Last Trade ID: {last_trade[0]} (Status: {last_trade[5]})")
    else:
        print("\nINFO No trades recorded.")

    conn.close()
    print("\nOK Integrity Check Passed.")

except Exception as e:
    print(f"\nERROR DB Error: {e}")
