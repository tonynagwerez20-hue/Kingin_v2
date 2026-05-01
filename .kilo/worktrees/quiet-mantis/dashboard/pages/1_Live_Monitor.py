import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import time
import sys
import os

# Ensure dashboard root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from styles import apply_styles
except ImportError:
    from dashboard.styles import apply_styles

st.set_page_config(page_title="Live Monitor", page_icon="📈", layout="wide")
apply_styles()

st.markdown("<h1 class='page-title'>Live Market Monitor</h1>", unsafe_allow_html=True)

# Configuration
API_URL = "http://localhost:8000"

# Sidebar controls
st.sidebar.header("Controls")
refresh_rate = st.sidebar.slider("Refresh Rate (ms)", 100, 2000, 200, step=100)
timeframe = st.sidebar.selectbox("Timeframe", ["M5", "M15", "H1"], index=0)

# Create placeholders for real-time updates (Sierra Chart style)
price_placeholder = st.empty()
metrics_placeholder = st.empty()
chart_placeholder = st.empty()
delta_placeholder = st.empty()

# Track previous price for color animation
if 'prev_price' not in st.session_state:
    st.session_state.prev_price = 0

def fetch_latest_price():
    """Lightweight: Fetch ONLY current price (not 500 bars)"""
    try:
        resp = requests.get(f"{API_URL}/latest-tick", timeout=0.5)
        return resp.json()
    except:
        return None

def fetch_chart_data(tf, limit=20):
    """Fetch chart data (only when needed)"""
    try:
        resp = requests.get(f"{API_URL}/ohlc?tf={tf}&limit={limit}", timeout=1)
        return resp.json().get("candles", [])
    except:
        return []

# Main live loop
while True:
    try:
        # 1. Update Price Ticker (Ultra-fast, <0.1kb)
        tick_data = fetch_latest_price()
        
        if tick_data:
            current_price = tick_data.get("price", 0)
            bid = tick_data.get("bid", 0)
            ask = tick_data.get("ask", 0)
            volume = tick_data.get("volume", 0)
            delta_val = tick_data.get("delta", 0)
            
            # Calculate price change
            price_change = current_price - st.session_state.prev_price
            price_color = "#10b981" if price_change >= 0 else "#ef4444"
            arrow = "▲" if price_change >= 0 else "▼"
            
            # Update price display with animation
            with price_placeholder.container():
                st.markdown(f"""
                <div style='background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); 
                            border-radius: 12px; padding: 2rem; text-align: center;'>
                    <h4 style='color: #9ca3af; margin: 0;'>XAUUSD Live Price</h4>
                    <h1 style='color: {price_color}; font-size: 3.5rem; margin: 0.5rem 0; 
                               font-weight: 800; text-shadow: 0 0 20px {price_color}50;'>
                        {current_price:.2f}
                    </h1>
                    <p style='color: {price_color}; font-size: 1.2rem; margin: 0;'>
                        {arrow} {abs(price_change):.2f} ({abs(price_change/current_price*100):.3f}%)
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            # Update metrics row
            with metrics_placeholder.container():
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Bid</h4>
                        <h2 style='color: #ef4444;'>{bid:.2f}</h2>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Ask</h4>
                        <h2 style='color: #10b981;'>{ask:.2f}</h2>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Spread</h4>
                        <h2 style='color: #3b82f6;'>{(ask-bid):.1f}</h2>
                        <p style='color: #6b7280; font-size: 0.8rem;'>Pips</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col4:
                    delta_color = "#10b981" if delta_val >= 0 else "#ef4444"
                    st.markdown(f"""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Volume / Delta</h4>
                        <h2 style='color: #fff;'>{volume:,.0f}</h2>
                        <p style='color: {delta_color}; font-size: 0.9rem;'>Δ {delta_val:+.0f}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.session_state.prev_price = current_price
        
        # 2. Update Chart (Less frequently - every 5th iteration)
        if not hasattr(st.session_state, 'chart_counter'):
            st.session_state.chart_counter = 0
        
        st.session_state.chart_counter += 1
        
        if st.session_state.chart_counter % 5 == 0:  # Update chart every 5 ticks
            candles = fetch_chart_data(timeframe, limit=30)
            
            if candles:
                with chart_placeholder.container():
                    df = pd.DataFrame(candles)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    
                    fig = go.Figure(data=[go.Candlestick(
                        x=df['time'],
                        open=df['open'],
                        high=df['high'],
                        low=df['low'],
                        close=df['close'],
                        increasing_line_color='#10b981',
                        decreasing_line_color='#ef4444',
                        name='Price'
                    )])
                    
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='#e5e7eb',
                        height=500,
                        margin=dict(l=0, r=0, t=30, b=0),
                        xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
                        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', side='right')
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                # Delta analysis
                with delta_placeholder.container():
                    st.markdown("### Orderflow Flux Analysis")
                    try:
                        resp = requests.get(f"{API_URL}/delta?tf={timeframe}&limit=5", timeout=1)
                        delta_data = resp.json()
                        
                        if delta_data and "delta" in delta_data and len(delta_data["delta"]) > 0:
                            d_df = pd.DataFrame({
                                "Index": range(len(delta_data["delta"])),
                                "Delta": delta_data["delta"],
                                "Cumulative": delta_data["cumulative"]
                            }).set_index("Index")
                            st.table(d_df)
                        else:
                            st.info(f"Synchronizing orderflow stream for {timeframe}...")
                    except:
                        st.info(f"Waiting for delta data...")
        
        # Control tick speed (Sierra Chart style: 100-200ms for smooth updates)
        time.sleep(refresh_rate / 1000.0)
        
    except Exception as e:
        st.error(f"Connection error: {e}")
        time.sleep(2)
