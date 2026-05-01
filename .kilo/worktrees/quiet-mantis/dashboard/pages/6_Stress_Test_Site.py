import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

# Fix paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from support.statistical.monte_carlo_engine import MonteCarloEngine

st.set_page_config(page_title="Stress Test Site", layout="wide")

st.title("🛡️ Institutional Stress Test Site")
st.markdown("---")

# Sidebar - Simulation Parameters
st.sidebar.header("Simulation Settings")
iterations = st.sidebar.slider("Iterations", 100, 5000, 1000, step=100)
slippage = st.sidebar.slider("Slippage (Pips)", 0.0, 5.0, 1.5, step=0.1)
initial_balance = st.sidebar.number_input("Initial Balance ($)", 1000, 1000000, 10000)

st.sidebar.markdown("---")
if st.sidebar.button("🚀 Run Monte Carlo Simulation"):
    with st.spinner("Analyzing trade permutations..."):
        engine = MonteCarloEngine()
        results = engine.run_simulation(
            iterations=iterations, 
            slippage_pips=slippage, 
            initial_balance=initial_balance
        )
        
        if results.get("status") == "ERROR":
            st.error(results["message"])
        else:
            st.session_state['mc_results'] = results
            st.success(f"Simulation Complete: {iterations} iterations processed.")

# Main View
if 'mc_results' in st.session_state:
    res = st.session_state['mc_results']
    
    # 1. High-Level Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg Final Balance", f"${res['avg_final_balance']:,.2f}")
    m2.metric("Avg Max Drawdown", f"{res['max_drawdown_avg']*100:.2f}%")
    m3.metric("Prob. of Ruin (50%)", f"{res['prob_of_ruin']*100:.2f}%")
    m4.metric("Total Iterations", res['iterations'])
    
    st.markdown("### 📈 Equity Curve Projections")
    
    # Plot top 10 simulations
    fig = go.Figure()
    for sim in res['simulations']:
        fig.add_trace(go.Scatter(y=sim['equity_curve'], mode='lines', opacity=0.4))
        
    fig.update_layout(
        title="Sample Monte Carlo Iterations (First 10 Shuffles)",
        xaxis_title="Trade Count",
        yaxis_title="Account Balance ($)",
        showlegend=False,
        template="plotly_dark"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. Risk Distribution
    st.markdown("### 📊 Risk Distribution")
    c1, c2 = st.columns(2)
    
    # Histograms for final balance
    df_sims = pd.DataFrame(res['simulations']) # Use sample for distribution visualization
    # Note: In a real app we'd pass all final balances to df
    
    c1.markdown("**Final Balance Distribution**")
    st.info("Histogram visualization would go here for all final balances.")
    
    c2.markdown("**Max Drawdown Distribution**")
    st.info("Histogram visualization would go here for all drawdown samples.")

else:
    st.info("👈 Configure the simulation in the sidebar and click 'Run' to begin stress testing your signals.")
    
    # Show status of backtest_signals.csv
    signals_file = project_root / "data" / "backtest_signals.csv"
    if signals_file.exists():
        df_count = pd.read_csv(signals_file)
        st.write(f"✅ Found **{len(df_count)} recorded signals** ready for analysis.")
    else:
        st.warning("⚠️ No recorded signals found. Run the Trading Engine with `--backtest` to generate signal data.")
