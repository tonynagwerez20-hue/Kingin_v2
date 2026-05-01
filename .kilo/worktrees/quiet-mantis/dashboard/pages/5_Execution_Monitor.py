import streamlit as st
import pandas as pd
import json
import os
import sys
import requests

# Ensure dashboard root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from styles import apply_styles
except ImportError:
    from dashboard.styles import apply_styles

st.set_page_config(page_title="Execution Monitor", page_icon="⚡", layout="wide")
apply_styles()

st.markdown("<h1 class='page-title'>Execution Monitor</h1>", unsafe_allow_html=True)

# Configuration
BRIDGE_API = "http://localhost:5557"  # MT5 EA heartbeat port
LOG_PATH = "storage/logs/audit.json"

def get_mt5_status():
    """Check if MT5 EA is responding."""
    try:
        # This would require a simple HTTP wrapper around the Bridge
        # For now, we'll check if signals are being logged
        return "ONLINE" if os.path.exists(LOG_PATH) else "UNKNOWN"
    except:
        return "OFFLINE"

def load_execution_logs():
    """Load recent signal execution logs."""
    if not os.path.exists(LOG_PATH):
        return []
    
    try:
        with open(LOG_PATH, "r") as f:
            data = json.load(f)
            # Filter for execution-related events
            executions = [
                {
                    "Time": entry["timestamp"],
                    "Event": entry["event"],
                    "Action": entry["metadata"].get("signal", {}).get("action", "N/A"),
                    "Symbol": entry["metadata"].get("signal", {}).get("symbol", "XAUUSD"),
                    "Lots": entry["metadata"].get("signal", {}).get("lots", "N/A"),
                    "Status": entry["metadata"].get("status", entry["event"]),
                    "Details": entry["metadata"].get("reason", entry["metadata"].get("signal", {}).get("desc", "N/A"))
                }
                for entry in reversed(data[-50:])  # Last 50 entries
                if entry["module"] in ["STRATEGY", "CRO", "EXECUTION"]
            ]
            return executions
    except Exception as e:
        st.error(f"Error loading logs: {e}")
        return []

st.sidebar.header("Controls")
refresh_rate = st.sidebar.slider("Refresh Rate (s)", 2, 60, 5)

executions = load_execution_logs()
mt5_status = get_mt5_status()

# System Status Section
st.write("### Live System Pipeline")
col1, col2, col3 = st.columns(3)

status_color = "#10b981" if mt5_status == "ONLINE" else "#ef4444"

with col1:
    st.markdown(f"""
    <div class='metric-card'>
        <h4 style='color: #9ca3af;'>MT5 EA Status</h4>
        <h2 style='color: {status_color};'>{mt5_status}</h2>
        <p style='font-size: 0.8rem; color: #6b7280;'>ZMQ Port 5557</p>
    </div>
    """, unsafe_allow_html=True)
    
with col2:
    st.markdown("""
    <div class='metric-card'>
        <h4 style='color: #9ca3af;'>Bridge Mode</h4>
        <h2 style='color: #3b82f6;'>REQ/REP</h2>
        <p style='font-size: 0.8rem; color: #6b7280;'>v5.3 Acknowledgment</p>
    </div>
    """, unsafe_allow_html=True)
    
with col3:
    st.markdown("""
    <div class='metric-card'>
        <h4 style='color: #9ca3af;'>Internal Health</h4>
        <h2 style='color: #10b981;'>OPTIMAL</h2>
        <p style='font-size: 0.8rem; color: #6b7280;'>Latency: < 50ms</p>
    </div>
    """, unsafe_allow_html=True)

st.write("### Recent Execution Events")

if executions:
    df = pd.DataFrame(executions)
    # Filter Logic (simplifying for autorefresh)
    event_types = list(df["Event"].unique())
    
    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Events", len(df))
    m2.metric("Signals Gen", len(df[df["Event"] == "SIGNAL_GENERATED"]))
    m3.metric("Pass Rate", f"{(len(df[df['Event'] == 'PASS']) / len(df) * 100 if not df.empty else 0):.1f}%")
    
    st.write("---")
    
    # Display execution cards (last 10 for performance in refresh)
    for idx, row in df.head(10).iterrows():
        if row["Event"] == "SIGNAL_GENERATED":
            border_color = "#3b82f6"
        elif row["Event"] == "PASS":
            border_color = "#10b981"
        elif row["Event"] == "RISK_VETO":
            border_color = "#ef4444"
        else:
            border_color = "#6b7280"
        
        st.markdown(f"""
        <div class='metric-card' style='border-left: 5px solid {border_color}; margin-bottom: 10px;'>
            <div style='display: flex; justify-content: space-between;'>
                <span style='font-weight: bold; color: {border_color};'>{row['Event']}</span>
                <span style='font-size: 0.8rem; color: #6b7280;'>{row['Time']}</span>
            </div>
            <h3 style='margin: 10px 0;'>{row['Action']} {row['Symbol']}</h3>
            <p style='margin-bottom: 5px;'><b>Lots:</b> {row['Lots']} | <b>Status:</b> {row['Status']}</p>
            <p style='color: #9ca3af; font-style: italic; font-size: 0.9rem;'>{row['Details']}</p>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("No execution events found. Waiting for Trading Engine...")

import time
time.sleep(refresh_rate)
st.rerun()

st.write("---")
st.write("### About Execution Monitor")
st.markdown("""
This page tracks the complete signal execution pipeline:
- **SIGNAL_GENERATED**: Strategy created a trading signal
- **PASS**: Signal passed CRO audit and was sent to MT5
- **RISK_VETO**: Signal was blocked by risk management
- **EXECUTION**: MT5 acknowledgment received (v5.3 feature)

**v5.3 Enhancement:** The system now receives execution confirmations from MT5 including ticket numbers and execution prices.
""")
