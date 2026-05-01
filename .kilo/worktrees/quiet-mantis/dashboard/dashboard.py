
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import time

# Load performance config
try:
    from config.performance_loader import perf_config
    ENABLE_LAZY_LOADING = perf_config.get_bool('enable_lazy_loading', True)
    MAX_PLOT_POINTS = perf_config.get_int('max_plot_points', 200)
except ImportError:
    # Try fallback to absolute path if package import fails
    try:
        import sys
        config_path = Path(__file__).parent.parent / "config"
        sys.path.append(str(config_path))
        from performance_loader import perf_config
        ENABLE_LAZY_LOADING = perf_config.get_bool('enable_lazy_loading', True)
        MAX_PLOT_POINTS = perf_config.get_int('max_plot_points', 200)
    except ImportError:
        ENABLE_LAZY_LOADING = True
        MAX_PLOT_POINTS = 200

# Setup paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "hedge.db"

st.set_page_config(page_title="Hedge Dashboard", layout="wide")

def get_db_connection():
    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}")
        return None
    return sqlite3.connect(DB_PATH)

def get_latest_price(conn, symbol):
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

st.title("Hedge Trading Dashboard")

conn = get_db_connection()

if conn:
    try:
        # --- Metrics ---
        # Closed Trades
        query_closed = "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time ASC"
        df_closed = pd.read_sql_query(query_closed, conn)
        
        total_pnl = 0.0
        win_rate = 0.0
        total_closed = 0
        
        if not df_closed.empty:
            df_closed['exit_time'] = pd.to_datetime(df_closed['exit_time'])
            df_closed['cumulative_pnl'] = df_closed['profit_loss'].cumsum()
            
            total_closed = len(df_closed)
            total_pnl = df_closed['profit_loss'].sum()
            winning_trades = len(df_closed[df_closed['profit_loss'] > 0])
            win_rate = (winning_trades / total_closed) * 100

        # Open Trades
        query_open = "SELECT * FROM trades WHERE status='open'"
        df_open = pd.read_sql_query(query_open, conn)
        total_open = len(df_open)

        # Display Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total PnL", f"${total_pnl:,.2f}")
        col2.metric("Win Rate", f"{win_rate:.1f}%")
        col3.metric("Open Trades", total_open)

        # --- Plots ---
        st.subheader("Account Progress")
        if not df_closed.empty:
            # Limit plot points for performance (low-spec optimization)
            plot_df = df_closed
            if ENABLE_LAZY_LOADING and len(df_closed) > MAX_PLOT_POINTS:
                # Sample data to reduce plot complexity
                step = len(df_closed) // MAX_PLOT_POINTS
                plot_df = df_closed.iloc[::step]
            
            # Using matplotlib for consistent style with previous task
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(plot_df['exit_time'], plot_df['cumulative_pnl'], marker='o', linestyle='-', color='b')
            ax.axhline(0, color='gray', linestyle='--', linewidth=0.8)
            ax.set_title("Equity Curve")
            ax.set_xlabel("Date")
            ax.set_ylabel("Cumulative PnL ($)")
            ax.grid(True, linestyle='--', alpha=0.6)
            st.pyplot(fig)
        else:
            st.info("No closed trades to plot.")

        # --- Tables ---
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Last 15 Closed Trades")
            if not df_closed.empty:
                # Show last 15 (which are at the end since we sorted ASC for plot)
                # Reverse to show newest first for table
                df_show = df_closed.sort_values('exit_time', ascending=False).head(15)
                # Select specific columns
                display_cols = ['symbol', 'entry_price', 'exit_price', 'lot_size', 'profit_loss', 'exit_time']
                display_cols = [c for c in display_cols if c in df_show.columns]
                st.dataframe(df_show[display_cols], width='stretch')
            else:
                st.write("No closed trades.")

        with col_right:
            st.subheader("Current Open Trades")
            if not df_open.empty:
                # Calculate Est PnL
                running_pnls = []
                current_prices = []
                
                for index, row in df_open.iterrows():
                    symbol = row['symbol']
                    curr_price = get_latest_price(conn, symbol)
                    current_prices.append(curr_price if curr_price else 0.0)
                    
                    if curr_price:
                        # Simple diff display as we don't know direction for sure without parsing notes/logic
                        # But we can display the price diff
                        diff = curr_price - row['entry_price']
                        running_pnls.append(f"{diff:.2f} (Price Diff)")
                    else:
                        running_pnls.append("N/A")
                
                df_open['current_price'] = current_prices
                df_open['est_pnl_hint'] = running_pnls
                
                display_cols_open = ['symbol', 'entry_price', 'current_price', 'lot_size', 'est_pnl_hint', 'entry_time']
                display_cols_open = [c for c in display_cols_open if c in df_open.columns]
                
                st.dataframe(df_open[display_cols_open], width='stretch')
            else:
                st.write("No open trades.")
                
    except Exception as e:
        st.error(f"Error reading data: {e}")
    finally:
        conn.close()

if st.button("Refresh Data"):
    st.rerun()
