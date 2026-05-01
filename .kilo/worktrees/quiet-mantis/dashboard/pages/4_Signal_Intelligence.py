import streamlit as st
import pandas as pd
import json
import os
import sys

# Ensure dashboard root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from styles import apply_styles
except ImportError:
    from dashboard.styles import apply_styles

st.set_page_config(page_title="Signal Intel", page_icon="📡", layout="wide")
apply_styles()

st.markdown("<h1 class='page-title'>Signal Intelligence Feed</h1>", unsafe_allow_html=True)

# Path to audit logs
LOG_PATH = "storage/logs/audit.json"

def load_signals():
    if not os.path.exists(LOG_PATH):
        return []
    
    try:
        with open(LOG_PATH, "r") as f:
            data = json.load(f)
            # Filter for strategy signals and CRO audits
            signals = [
                {
                    "Time": entry["timestamp"],
                    "Source": entry["module"],
                    "Event": entry["event"],
                    "Action": entry["metadata"].get("signal", {}).get("action", "N/A"),
                    "Symbol": entry["metadata"].get("signal", {}).get("symbol", "XAUUSD"),
                    "Price": entry["metadata"].get("signal", {}).get("price", "N/A"),
                    "SL": entry["metadata"].get("signal", {}).get("sl", "N/A"),
                    "Lots": entry["metadata"].get("signal", {}).get("lots", "N/A"),
                    "Reason/Desc": entry["metadata"].get("reason", entry["metadata"].get("signal", {}).get("desc", "N/A"))
                }
                for entry in reversed(data) 
                if entry["module"] in ["STRATEGY", "CRO"]
            ]
            return signals
    except Exception as e:
        st.error(f"Error loading logs: {e}")
        return []

signals = load_signals()

if signals:
    df = pd.DataFrame(signals)
    
    # Sidebar Filters
    st.sidebar.header("Signal Filters")
    source_filter = st.sidebar.multiselect("Source", options=["STRATEGY", "CRO"], default=["STRATEGY", "CRO"])
    action_filter = st.sidebar.multiselect("Action", options=list(df["Action"].unique()), default=list(df["Action"].unique()))
    
    filtered_df = df[(df["Source"].isin(source_filter)) & (df["Action"].isin(action_filter))]

    # Overview Metrics
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("Total Signals", len(filtered_df))
    s_col2.metric("Vetoed Trades", len(df[df["Event"] == "RISK_VETO"]))
    s_col3.metric("Passed Trades", len(df[df["Event"] == "PASS"]))

    st.write("---")
    
    # Custom display for signals
    for idx, row in filtered_df.iterrows():
        status_color = "#10b981" if row["Event"] == "PASS" else "#ef4444" if row["Event"] == "RISK_VETO" else "#3b82f6"
        
        with st.container():
            st.markdown(f"""
            <div class='metric-card' style='border-left: 5px solid {status_color};'>
                <div style='display: flex; justify-content: space-between;'>
                    <span style='font-weight: bold; color: {status_color};'>{row['Event']}</span>
                    <span style='font-size: 0.8rem; color: #6b7280;'>{row['Time']}</span>
                </div>
                <h3 style='margin: 10px 0;'>{row['Action']} @ {row['Price']}</h3>
                <p style='margin-bottom: 5px;'><b>Symbol:</b> {row['Symbol']} | <b>Lots:</b> {row['Lots']} | <b>SL:</b> {row['SL']}</p>
                <p style='color: #9ca3af; font-style: italic;'>{row['Reason/Desc']}</p>
            </div>
            """, unsafe_allow_html=True)
            
else:
    st.info("No signals detected in audit logs. Ensure the Trading Engine is running.")

if st.button("Clear Signal Logs"):
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w") as f:
            json.dump([], f)
        st.success("Logs cleared!")
        st.rerun()
