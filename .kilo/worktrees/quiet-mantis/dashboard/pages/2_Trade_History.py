import streamlit as st
import pandas as pd
import sys
import os

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from storage.hedge_db import HedgeDB
except ImportError:
    HedgeDB = None

try:
    from styles import apply_styles
except ImportError:
    from dashboard.styles import apply_styles

st.set_page_config(page_title="Trade History", page_icon="📜", layout="wide")
apply_styles()

st.markdown("<h1 class='page-title'>Institutional Trade History</h1>", unsafe_allow_html=True)

# Fetch real trades from database
def get_actual_trades():
    if not HedgeDB:
        return []
    try:
        db = HedgeDB()
        raw_trades = db.get_all_trades(limit=200)
        db.close()
        
        # Map DB columns to Display Columns
        formatted = []
        for t in raw_trades:
            formatted.append({
                "Ticket": t["ticket"],
                "Symbol": t["symbol"],
                "Action": t["action"],
                "Entry": t["entry_price"],
                "Exit": t["exit_price"],
                "Lots": t["lot_size"],
                "PnL": t["profit_loss"],
                "Status": t["status"].capitalize(),
                "Time": t["entry_time"]
            })
        return formatted
    except Exception as e:
        st.error(f"Database error: {e}")
        return []

st.sidebar.header("Controls")
refresh_rate = st.sidebar.slider("Refresh Rate (s)", 2, 60, 10)
status_filter = st.sidebar.multiselect("Status", ["Open", "Closed"], default=["Open", "Closed"])

placeholder = st.empty()

trades = get_actual_trades()
if trades:
    df = pd.DataFrame(trades)
    # Handle capitalization for filtering
    df['Status'] = df['Status'].apply(lambda x: x.capitalize())
    filtered_df = df[df['Status'].isin(status_filter)]
else:
    columns = ["Ticket", "Symbol", "Action", "Entry", "Exit", "Lots", "PnL", "Status", "Time"]
    df = pd.DataFrame(columns=columns)
    filtered_df = pd.DataFrame(columns=columns)

# Metrics
col1, col2, col3 = st.columns(3)
total_pnl = filtered_df['PnL'].sum() if not filtered_df.empty else 0.0

with col1:
    st.markdown(f"""
    <div class='metric-card'>
        <h4 style='color: #9ca3af;'>Total PnL</h4>
        <h2 style='color: {"#10b981" if total_pnl >= 0 else "#ef4444"};'>${total_pnl:,.2f}</h2>
    </div>
    """, unsafe_allow_html=True)
    
with col2:
    active_count = len(df[df['Status'] == 'Open']) if not df.empty else 0
    st.markdown(f"""
    <div class='metric-card'>
        <h4 style='color: #9ca3af;'>Active Trades</h4>
        <h2 style='color: #fff;'>{active_count}</h2>
    </div>
    """, unsafe_allow_html=True)
    
with col3:
    total_count = len(df) if not df.empty else 0
    st.markdown(f"""
    <div class='metric-card'>
        <h4 style='color: #9ca3af;'>Total Executions</h4>
        <h2 style='color: #fff;'>{total_count}</h2>
    </div>
    """, unsafe_allow_html=True)

st.write("### Detailed Execution Log")

# Color coding PnL
def color_pnl(val):
    if not isinstance(val, (int, float)): return ''
    color = 'green' if val > 0 else 'red' if val < 0 else '#9ca3af'
    return f'color: {color}'

if not filtered_df.empty:
    st.dataframe(filtered_df.style.applymap(color_pnl, subset=['PnL']), use_container_width=True)
else:
    st.info("No trades found matching filters.")

st.write("### Equity Curve Visualizer")
if not filtered_df.empty:
    # Sort by time for equity curve (handle missing time if any)
    curve_df = filtered_df.dropna(subset=['Time']).sort_values('Time')
    if not curve_df.empty:
        equity = curve_df['PnL'].cumsum()
        st.line_chart(equity)
    else:
        st.info("Insufficient timestamped data for curve.")
else:
    st.info("No trade data available for visualization.")

import time
time.sleep(refresh_rate)
st.rerun()

