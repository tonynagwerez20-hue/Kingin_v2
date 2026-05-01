import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# Ensure dashboard root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from styles import apply_styles
except ImportError:
    from dashboard.styles import apply_styles

st.set_page_config(page_title="Weekly Report", page_icon="📊", layout="wide")
apply_styles()

st.markdown("<h1 class='page-title'>Weekly Performance Analytics</h1>", unsafe_allow_html=True)

# Mock stats
st.write("### System Efficiency Metrics")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Win Rate", "64%", delta="2%")
col2.metric("Profit Factor", "1.85", delta="0.1")
col3.metric("Avg R:R", "1.4", delta="None")
col4.metric("Max Drawdown", "4.2%", delta="-0.5%")

st.write("---")

# Performance Charts
c1, c2 = st.columns(2)

with c1:
    st.write("#### PnL by Day (UTC)")
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    pnl = [450, -200, 800, 120, 300]
    st.bar_chart(pd.DataFrame({"Day": days, "PnL": pnl}).set_index("Day"))

with c2:
    st.write("#### Strategy Contribution")
    labels = 'Orderflow FLIP', 'Orderflow SURGE', 'Reversal Exit'
    sizes = [45, 30, 25]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
    ax.axis('equal')
    # Dark mode pie chart
    fig.patch.set_facecolor('#0f1115')
    ax.set_facecolor('#0f1115')
    for text in ax.texts:
        text.set_color('white')
    st.pyplot(fig)

st.write("---")
st.write("### Expert Panel Notes")
st.markdown("""
> **Institutional Observation:** System performance remains stable during NY open. Orderflow SURGE signals show higher conviction but lower frequency.
> **Risk Note:** Current DD is well within parameters. Maintaining 0.1% risk per trade.
""")
