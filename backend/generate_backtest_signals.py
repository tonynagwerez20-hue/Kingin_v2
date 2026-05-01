import pandas as pd
import json
import os
from pathlib import Path
import logging
from datetime import datetime
from bisect import bisect_right
from support.strategies.smc_strategy import SMCStrategy
from support.risk.ultra_low_risk import UltraLowAccountRiskRule
from unified_smc_ml import SMCBrain

# Setup forensic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MTF_Backtest")

# Session mapping for ML features
SESSION_MAP = {
    "asian": 0, "london": 1, "overlap": 2, "ny": 3
}

def get_session(dt) -> str:
    """Determine trading session from datetime."""
    h = dt.hour
    if 2 <= h < 8:
        return "asian"
    elif 8 <= h < 12:
        return "london"
    elif 12 <= h < 16:
        return "overlap"
    return "ny"

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
    
    # 2b. Initialize ML Brain (SMC + LightGBM filter)
    account_balance = config.get("risk", {}).get("account_balance", 1000.0)
    ml_brain = SMCBrain(account_balance=account_balance)
    logger.info(f"ML Brain initialized: threshold={ml_brain.ml.threshold}")

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
        # EA reads columns by POSITION - must match original order:
        # 0:Time, 1:Price, 2:L0, 3:L1, 4:L2, 5:L3, 6:L4, 7:L5, 8:Action, 9:Reason
        details = signal.get("layer_details", signal.get("details", {}))
        layer_scores = {
            "L0": details.get("KillzoneFilter", {}).get("score", 0),
            "L1": details.get("MechanicalStructure", {}).get("score", 0),
            "L2": details.get("FVGDiscount", {}).get("score", 0),
            "L3": details.get("LiquiditySweep", {}).get("score", 0),
            "L4": details.get("MicroMSS", {}).get("score", 0),
            "L5": details.get("Displacement", {}).get("score", 0),
        }
        # ML status field (for display)
        ml_status = "WAIT" if signal.get("action") != "TRADE" else ""
        
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
            "Reason": signal.get("reason", "N/A").replace(",", ";"),
            # === NEW ML COLUMNS (append after original 10) ===
            "L0_Score": f"{layer_scores['L0']:.2f}",
            "L1_Score": f"{layer_scores['L1']:.2f}",
            "L2_Score": f"{layer_scores['L2']:.2f}",
            "L3_Score": f"{layer_scores['L3']:.2f}",
            "L4_Score": f"{layer_scores['L4']:.2f}",
            "L5_Score": f"{layer_scores['L5']:.2f}",
            "OB_Score": f"{signal.get('confidence', 0):.2f}",
            "ML_Filter": ml_status,
            "ML_Conf": "",
            "ML_Blended": "",
        }
        # Don't append yet - will append after ML decision
        # forensic_signals.append(forensic_row)  # MOVED BELOW

        # --- EXECUTION DATA ---
        if signal.get("action") == "TRADE":
            # === ML FILTER GATE ===
            # Convert SMC signal to ML feature format
            details = signal.get("layer_details", {})
            
            ml_signal = {
                "ob_strength": signal.get("confidence", 0.5),
                "fvg_present": bool(details.get("FVGDiscount", {}).get("status", False)),
                "bos_aligned": bool(details.get("MechanicalStructure", {}).get("status", False)),
                "liquidity_swept": bool(details.get("LiquiditySweep", {}).get("status", False)),
                "adr_pct": 0.5,  # Default - calculate from price data if available
                "pips_to_liquidity": 15.0,  # Default
                "session": get_session(current_m5_time),
                "htf_bias": 1 if signal.get("direction") == "BUY" else -1,
                "direction": signal.get("direction", "BUY").lower(),
                "entry_price": signal.get("price"),
                "sl_price": signal.get("sl"),
                "tp_price": signal.get("tp")
            }
            
            # Evaluate through ML filter
            should_trade, ml_confidence, ml_debug = ml_brain.ml.evaluate_signal(ml_signal)
            
            # Log ML decision
            ml_decision = "ML_TRADE" if should_trade else "ML_SKIP"
            if not should_trade:
                logger.debug(f"ML filtered: conf={ml_confidence:.2%} < {ml_brain.ml.threshold:.2%}")
            
            # Apply ML filter decision
            if not should_trade:
                forensic_row["ML_Filter"] = "SKIP"
                forensic_row["ML_Conf"] = f"{ml_confidence:.1%}"
                forensic_row["ML_Blended"] = f"{ml_debug.get('blended', 0):.2%}"
                forensic_row["Reason"] = f"ML_FILTERED: {ml_debug.get('decision')}"
                continue
            
            # ML passed - proceed with execution
            signal["current_equity"] = 10.0
            signal["daily_loss"] = 0.0
            signal["open_positions_count"] = 0
            
            risk_res = risk_rule.check_risk(signal)
            if risk_res.get("allowed"):
                # === EA COMPATIBLE FORMAT ===
                ea_action = "LONG" if signal.get("direction") == "BUY" else "SHORT"
                execution_type = signal.get("execution_type", "MARKET")
                limit_price = signal.get("limit_price", signal.get("price"))
                bias = "BULLISH" if signal.get("direction") == "BUY" else "BEARISH"
                timestamp = int(current_m5_time.timestamp())
                
                # EA-compatible execution row (column order matches EA reading)
                exec_row = {
                    "Time": current_m5_time.strftime('%Y.%m.%d %H:%M:%S'),
                    "Symbol": symbol,
                    "Action": ea_action,             # 3: Action (LONG/SHORT)
                    "Price": signal.get('price'),   # 4: Price
                    "SL": signal.get('sl'),        # 5: SL
                    "TP": signal.get('tp'),        # 6: TP
                    "Lots": risk_res.get('enforced_lots', 0.01),  # 7: Lots
                    # 8: Desc (includes ML metadata)
                    "Desc": f"ML:{ml_confidence:.2f}|OB:{signal.get('confidence', 0):.2f}|{ml_decision}",
                    "Magic": "123456",             # 9: Magic
                    # Additional fields for reference
                    "ExecutionType": execution_type,
                    "LimitPrice": limit_price,
                    "ConfluenceScore": signal.get('score', 0),
                    # === ML ENGINE METADATA ===
                    "ML_Confidence": f"{ml_confidence:.4f}",
                    "ML_Decision": ml_decision,
                    "ML_LGBM_Score": f"{ml_debug.get('lgbm_score', 0):.4f}",
                    "ML_River_Score": f"{ml_debug.get('river_score', 0):.4f}",
                    "ML_Blended": f"{ml_debug.get('blended', 0):.4f}",
                    "ML_Threshold": f"{ml_brain.ml.threshold:.2f}",
                    "ML_Drift_Active": str(ml_debug.get('drift_active', False)),
                    "ML_Trained_Samples": ml_brain.ml.log.count(),
                    "ML_Live_WinRate": f"{ml_brain.ml.log.win_rate():.2f}"
                }
                execution_signals.append(exec_row)
                forensic_row["ML_Filter"] = "PASS"
                forensic_row["ML_Conf"] = f"{ml_confidence:.1%}"
                forensic_row["ML_Blended"] = f"{ml_debug.get('blended', 0):.2%}"
                forensic_row["OB_Score"] = f"{signal.get('confidence', 0):.2f}"
        else:
            forensic_row["ML_Filter"] = "N/A"
            forensic_row["ML_Conf"] = "N/A"
            forensic_row["ML_Blended"] = "N/A"
        
        # Append forensic row (after possible ML update)
        forensic_signals.append(forensic_row)

        if i % 5000 == 0:
            logger.info(f"Progress: {i}/{len(df_m5)} M5 bars synced")

    # 5. Save Results
    pd.DataFrame(forensic_signals).to_csv("isignals_backtest.csv", index=False)
    pd.DataFrame(execution_signals).to_csv("backtest_signals.csv", index=False)
    
    logger.info(f"SUCCESS: MTF Backtest Complete.")
    logger.info(f"Execution Setups Found: {len(execution_signals)}")

if __name__ == "__main__":
    run_mtf_backtest()
