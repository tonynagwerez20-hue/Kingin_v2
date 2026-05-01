import streamlit as st
import os

# Set page config
st.set_page_config(
     page_title="Hedge System Premium Dashboard",
     page_icon="💠",
     layout="wide",
     initial_sidebar_state="expanded",
)

# Custom CSS for Premium Institutional Look
st.markdown("""
<style>
    /* Premium Obsidian Theme */
    :root {
        --primary-bg: #0f1115;
        --card-bg: rgba(255, 255, 255, 0.03);
        --accent-glow: #3b82f6;
    }
    
    .stApp {
        background-color: var(--primary-bg);
        color: #e5e7eb;
    }
    
    .stSidebar {
        background-color: #080a0d !important;
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    
    /* Glassmorphism Card Style */
    .metric-card {
        background: var(--card-bg);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: var(--accent-glow);
    }
    
    /* Title Gradient */
    .main-title {
        background: linear-gradient(90deg, #fff 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.5rem;
    }
    
    /* Button Premium */
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
    }
</style>
""", unsafe_allow_html=True)

def main():
    import sys
    from pathlib import Path
    # Ensure project root is in path
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        
    st.sidebar.markdown("<h1 style='color: #3b82f6;'>HEDGE RC</h1>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
    # Auto-refresh control
    time_to_refresh = st.sidebar.slider("Refresh frequency (s)", 2, 30, 5)
    
    st.markdown("<h1 class='main-title'>Trading System Overview</h1>", unsafe_allow_html=True)
    
    import requests
    import time
    
    # Create placeholders for smooth updates
    status_placeholder = st.empty()
    info_placeholder = st.empty()
    
    while True:
        try:
            # 1. Dynamic Data Feed Status
            data_status = "OFFLINE"
            status_color = "#ef4444" # red
            last_update_text = "No connection to API"
            
            try:
                resp = requests.get("http://localhost:8000/latest-tick", timeout=1)
                if resp.status_code == 200:
                    tick_data = resp.json()
                    last_ts = tick_data.get("timestamp", 0)
                    now_ts = time.time()
                    diff = now_ts - last_ts
                    
                    if diff < 120: # Within 2 minutes
                        data_status = "ONLINE"
                        status_color = "#10b981" # green
                        last_update_text = f"Live Sync ({int(diff)}s ago)"
                    else:
                        data_status = "STALE"
                        status_color = "#f59e0b" # amber
                        last_update_text = f"Latent ({int(diff/60)}m ago)"
                else:
                    data_status = "READY"
                    status_color = "#3b82f6" # blue
                    last_update_text = "Server up, waiting for data..."
            except Exception:
                pass
            
            from storage.hedge_db import HedgeDB
            db = HedgeDB("data/hedge.db")
            
            # Fetch real-time balance
            account_balance = db.get_state("account_balance", 0.0)
            balance_sync_ts = db.get_state("balance_last_sync", 0)
            
            if account_balance > 0:
                balance_display = f"${account_balance:,.2f}"
                if balance_sync_ts > 0:
                    b_diff = time.time() - balance_sync_ts
                    if b_diff < 300: # 5 mins
                        balance_subtext = f"Live Sync ({int(b_diff)}s ago)"
                        balance_color = "#fff"
                    else:
                        balance_subtext = f"Delayed Sync ({int(b_diff/60)}m ago)"
                        balance_color = "#9ca3af"
                else:
                    balance_subtext = "MT5 Synchronization"
                    balance_color = "#fff"
            else:
                balance_display = "$ --,---.--"
                balance_subtext = "MT5 Not Connected"
                balance_color = "#ef4444"
            
            # Update status cards using placeholder
            with status_placeholder.container():
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Data Feed Status</h4>
                        <h2 style='color: {status_color};'>{data_status}</h2>
                        <p style='font-size: 0.8rem; color: #6b7280;'>{last_update_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with col2:
                    st.markdown("""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Trading Engine</h4>
                        <h2 style='color: #10b981;'>ACTIVE</h2>
                        <p style='font-size: 0.8rem; color: #6b7280;'>UTC Window: 08:00 - 21:00</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with col3:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <h4 style='color: #9ca3af;'>Account Equity</h4>
                        <h2 style='color: {balance_color};'>{balance_display}</h2>
                        <p style='font-size: 0.8rem; color: #6b7280;'>{balance_subtext}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            with info_placeholder.container():
                st.markdown("---")
                st.write("### Production Health Check")
                
                # System info
                st.info("System is running in **DTC Protocol Mode**. Real-time data is being streamed from Sierra Chart.")
                
                st.markdown("""
                ### Dashboard Quick Links
                - **Live Monitor**: Visualizer for orderflow flux and candle data.
                - **Trade History**: Audit log of all signal events and executions.
                - **Weekly Report**: Statistical performance review.
                """)
            
            time.sleep(time_to_refresh)
            
        except Exception as e:
            st.error(f"Dashboard error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
