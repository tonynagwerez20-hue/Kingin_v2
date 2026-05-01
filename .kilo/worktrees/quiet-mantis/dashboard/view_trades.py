
import sqlite3
import pandas as pd
from pathlib import Path
import sys

# Setup paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "hedge.db"

# Constants from main_loop.py (assuming XAUUSD context)
PIP_VALUE = 10.0
PIP_SIZE = 0.01

def get_latest_price(conn, symbol):
    """Fetches the latest close price for a symbol from candles table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close_price FROM candles 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None

def view_trades():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    try:
        # --- Closed Trades ---
        query_closed = "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT 15"
        df_closed = pd.read_sql_query(query_closed, conn)
        
        print("\n" + "="*50)
        print("LAST 15 CLOSED TRADES")
        print("="*50)
        
        if df_closed.empty:
            print("No closed trades found.")
        else:
            # Select relevant columns
            cols = ['id', 'symbol', 'action', 'entry_price', 'exit_price', 'lot_size', 'profit_loss', 'exit_time']
            # Note: 'action' column might not exist in table based on hedge_db.py, 
            # checking hedge_db.py, it has: symbol, entry_price, exit_price, lot_size, risk_amount, profit_loss, status, ...
            # 'action' is not explicitly in the CREATE TABLE in hedge_db.py, need to check if it was added or inferred.
            # Looking at hedge_db.py:
            # CREATE TABLE ... trades ( ... symbol, entry_price, ... )
            # It DOES NOT have 'action' (Long/Short). 
            # We might have to infer it from entry vs exit or notes?
            # Or maybe it's missing. Let's inspect the columns available in df.
            
            # Let's just print available columns first to be safe, or just standard ones.
            # safe_cols = [c for c in cols if c in df_closed.columns]
            # Actually, I'll just print the whole DF with selected columns that definitely exist.
            
            display_cols = ['id', 'symbol', 'entry_price', 'exit_price', 'lot_size', 'profit_loss', 'exit_time']
            # Filter only existing columns
            display_cols = [c for c in display_cols if c in df_closed.columns]
            
            # Format
            print(df_closed[display_cols].to_string(index=False))


        # --- Open Trades ---
        query_open = "SELECT * FROM trades WHERE status='open'"
        df_open = pd.read_sql_query(query_open, conn)

        print("\n" + "="*50)
        print("CURRENT OPEN TRADES")
        print("="*50)

        if df_open.empty:
            print("No open trades found.")
        else:
            # We need to calculate running PnL
            # Since 'action' (LONG/SHORT) is missing from schema seen in hedge_db.py, 
            # we might have trouble knowing direction.
            # However, usually stop loss location or notes might have it.
            # For now, let's just show entry price and current price.
            
            running_pnls = []
            current_prices = []
            
            for index, row in df_open.iterrows():
                symbol = row['symbol']
                entry_price = row['entry_price']
                lot_size = row['lot_size']
                
                curr_price = get_latest_price(conn, symbol)
                current_prices.append(curr_price)
                
                if curr_price:
                    # We don't know direction! 
                    # If we don't know direction, we can't calculate PnL accurately.
                    # But wait, main_loop.py sends 'action' to bridge, but hedge_db.py doesn't seem to store it?
                    # Let's check if 'notes' contains the signal type.
                    # main_loop.py: "SIGNAL: {signal} ..." -> notes?
                    # hedge_db.py insert_trade doesn't seem to take action explicitly, but maybe update logic changed?
                    # I will assume "notes" or just display current price for now. 
                    pnl_str = "N/A (Unknown Dir)"
                    running_pnls.append(pnl_str)
                else:
                    running_pnls.append("N/A (No Data)")
            
            df_open['current_price'] = current_prices
            df_open['est_pnl'] = running_pnls
            
            display_cols_open = ['id', 'symbol', 'entry_price', 'current_price', 'lot_size', 'est_pnl', 'entry_time']
            display_cols_open = [c for c in display_cols_open if c in df_open.columns or c in ['current_price', 'est_pnl']]
            
            print(df_open[display_cols_open].to_string(index=False))

    except Exception as e:
        print(f"Error reading data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_trades()
