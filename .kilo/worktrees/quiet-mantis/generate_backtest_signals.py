import pandas as pd
import json
import os
from pathlib import Path
import logging
from datetime import datetime
from bisect import bisect_right
from support.strategies.smc_strategy import SMCStrategy
from support.risk.ultra_low_risk import UltraLowAccountRiskRule

# Setup forensic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MTF_Backtest")

def load_config(config_path: str = "config/trading_params_lite.json"):
    with open(config_path, 'r') as f:
        return json.load(f)

def run_mtf_backtest():
    logger.info("Starting Institutional MTF Backtest Signal Generation (Optimized)...")
    config = load_config()
    symbol = config.get("trading", {}).get("symbol", "XAUUSD")
    data_dir = Path("data/backtest")

    # 1. Load All 5 Timeframes
    timeframes = ["H4", "H1", "M15", "M5", "M1"]
    dfs = {}
    df_times = {}
    for tf in timeframes:
        path = data_dir / f"{symbol}_{tf}_6mo.csv"
        if not path.exists():
            logger.error(f"Missing {tf} data. Run download_6mo_data.py.")
            return
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'])
        dfs[tf] = df
        df_times[tf] = df['time'].tolist() # For fast bisect search
        logger.info(f"Loaded {tf}: {len(df)} bars")

    # 2. Initialize Components
    strat_cfg = config.get("pipeline", {}).get("strategies", [{}])[0].get("config", {})
    strat_cfg["symbol"] = symbol
    strategy = SMCStrategy(strat_cfg)
    
    risk_cfg = config.get("pipeline", {}).get("risk_rules", [{}])[0].get("config", {})
    risk_rule = UltraLowAccountRiskRule(risk_cfg)

    # 3. Synchronized Loop (Master Anchor: M5)
    execution_signals = []
    forensic_signals = []
    
    df_m5 = dfs["M5"]
    m5_times = df_times["M5"]
    logger.info(f"Processing {len(df_m5)} M5 anchor bars...")

    for i in range(100, len(df_m5)):
        current_m5_time = m5_times[i]
        
        # Create MTF Snapshot (Bars strictly closed BEFORE or AT current M5 time)
        # Using bisect for O(log N) search instead of O(N) filtering
        snapshot = {}
        for tf in timeframes:
            # Find the position where current_m5_time would be inserted
            # idx is the index of the first bar AFTER current_m5_time
            idx = bisect_right(df_times[tf], current_m5_time)
            
            # Take up to 100 bars ending at idx-1
            # .iloc[max(0, idx-100):idx] is very fast
            tf_snapshot_df = dfs[tf].iloc[max(0, idx-100):idx]
            snapshot[f"{tf.lower()}_candles"] = tf_snapshot_df.to_dict('records')

        # Dummy tick data for pricing
        snapshot["tick"] = {
            "bid": df_m5.iloc[i]['close'],
            "ask": df_m5.iloc[i]['close'] + 0.02,
            "time": current_m5_time
        }

        # 4. Generate Signal
        signal = strategy.generate_signal(snapshot)
        
        # --- FORENSIC DATA ---
        details = signal.get("layer_details", signal.get("details", {}))
        forensic_row = {
            "Time": current_m5_time.strftime('%Y.%m.%d %H:%M:%S'),
            "Price": f"{df_m5.iloc[i]['close']:.2f}",
            "L0": "PASS" if details.get("KillzoneFilter", {}).get("status") else "FAIL",
            "L1": "PASS" if details.get("MechanicalStructure", {}).get("status") else "FAIL",
            "L2": "PASS" if details.get("FVGDiscount", {}).get("status") else "FAIL",
            "L3": "PASS" if details.get("LiquiditySweep", {}).get("status") else "FAIL",
            "L4": "PASS" if details.get("MicroMSS", {}).get("status") else "FAIL",
            "L5": "PASS" if details.get("Displacement", {}).get("status") else "FAIL",
            "Action": signal.get("action", "WAIT"),
            "Reason": signal.get("reason", "N/A").replace(",", ";")
        }
        forensic_signals.append(forensic_row)

        # --- EXECUTION DATA ---
        if signal.get("action") == "TRADE":
            signal["current_equity"] = 10.0
            signal["daily_loss"] = 0.0
            signal["open_positions_count"] = 0
            
            risk_res = risk_rule.check_risk(signal)
            if risk_res.get("allowed"):
                ea_action = "LONG" if signal.get("direction") == "BUY" else "SHORT"
                
                # Get execution type from liquidity layer or use default
                execution_type = signal.get("execution_type", "MARKET")
                limit_price = signal.get("limit_price", signal.get("price"))
                
                exec_row = {
                    "Time": current_m5_time.strftime('%Y.%m.%d %H:%M:%S'),
                    "Symbol": symbol,
                    "Action": ea_action,
                    "Price": f"{signal.get('price'):.2f}",
                    "SL": f"{signal.get('sl'):.2f}",
                    "TP": f"{signal.get('tp'):.2f}",
                    "Lots": f"{risk_res.get('enforced_lots', 0.01):.2f}",
                    "Desc": "MTF_SMC_SIGNAL",
                    "Magic": "123456",
                    "ExecutionType": execution_type,
                    "LimitPrice": f"{limit_price:.2f}",
                    "ConfluenceScore": f"{signal.get('score', 0):.2f}"
                }
                execution_signals.append(exec_row)

        if i % 5000 == 0:
            logger.info(f"Progress: {i}/{len(df_m5)} M5 bars synced")

    # 5. Save Results
    pd.DataFrame(forensic_signals).to_csv("isignals_backtest.csv", index=False)
    pd.DataFrame(execution_signals).to_csv("backtest_signals.csv", index=False)
    
    logger.info(f"SUCCESS: MTF Backtest Complete.")
    logger.info(f"Execution Setups Found: {len(execution_signals)}")

if __name__ == "__main__":
    run_mtf_backtest()
