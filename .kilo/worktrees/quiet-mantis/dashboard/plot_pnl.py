import sys
print("Starting imports...", flush=True)

try:
    import sqlite3
    print("Imported sqlite3", flush=True)
    import pandas as pd
    print("Imported pandas", flush=True)
    import matplotlib
    matplotlib.use('Agg') # Set non-interactive backend
    import matplotlib.pyplot as plt
    print("Imported matplotlib", flush=True)
    import os
    from pathlib import Path
    print("Imports complete.", flush=True)
except Exception as e:
    print(f"Import failed: {e}", flush=True)
    sys.exit(1)

# Setup paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "hedge.db"
OUTPUT_PATH = SCRIPT_DIR / "account_progress.png"

def plot_pnl():
    """Reads trades from DB and plots cumulative PnL."""
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time ASC"
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("No closed trades found to plot.")
            return

        # Pre-process
        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df['cumulative_pnl'] = df['profit_loss'].cumsum()
        
        # Stats
        total_pnl = df['profit_loss'].sum()
        total_trades = len(df)
        win_rate = (len(df[df['profit_loss'] > 0]) / total_trades) * 100
        
        print(f"Total Closed Trades: {total_trades}")
        print(f"Total PnL: ${total_pnl:.2f}")
        print(f"Win Rate: {win_rate:.2f}%")

        # Plotting
        plt.figure(figsize=(10, 6))
        plt.plot(df['exit_time'], df['cumulative_pnl'], marker='o', linestyle='-', color='b', label='Equity Curve')
        plt.axhline(0, color='gray', linestyle='--', linewidth=0.8)
        
        plt.title(f"Account Progress (Total PnL: ${total_pnl:.2f})")
        plt.xlabel("Date")
        plt.ylabel("Cumulative PnL ($)")
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.tight_layout()
        
        plt.savefig(OUTPUT_PATH)
        print(f"Plot saved to: {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    plot_pnl()
