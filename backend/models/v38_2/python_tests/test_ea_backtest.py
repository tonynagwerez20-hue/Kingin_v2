"""V38.2 EA Backtest Simulation — Python mirror of the MQL5 EA logic.

Since no MT5 terminal is available in this environment, this script simulates
what the V38.2 EA would do in the MT5 Strategy Tester:

1. Loads the M5 dataset (same data the EA would process)
2. For each candidate setup, applies the ML model + calibrator + threshold
3. Applies risk management (position sizing, daily loss cap, max trades)
4. Simulates trade outcomes using the barrier labels (TP=+2R, SL=-1R)
5. Generates performance metrics comparable to V37

This is NOT a replacement for the MT5 Strategy Tester. It uses the same
candidate setups and ML decisions, but assumes perfect execution at the
close price with no slippage. Real MT5 backtest results may differ.

Usage:
    python -m v38.v38_2.test_ea_backtest
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import joblib

from v38.config import V38Config
from v38.features.contract import FEATURE_NAMES, FEATURE_SPECS, N_FEATURES

PRICE_INDICES = [i for i in range(N_FEATURES) if FEATURE_SPECS[i].family != "MACRO_NEWS"]

ARTIFACT_DIR = Path(__file__).parent / "full_data_artifacts"
DATASET_PATH = ARTIFACT_DIR / "v38_2_dataset_M5_H1_lb240.parquet"
REPORT_PATH = ARTIFACT_DIR / "V38_2_EA_BACKTEST_REPORT.json"
TRADE_CSV_PATH = ARTIFACT_DIR / "V38_2_EA_BACKTEST_TRADES.csv"


def run_backtest(
    start_date: str = "2026-01-01",
    end_date: str = "2026-05-31",
    initial_deposit: float = 5000.0,
    risk_pct: float = 0.01,
    prob_threshold: float = 0.50,
    max_trades_per_day: int = 5,
    max_daily_loss_pct: float = 0.03,
    max_consec_losses: int = 5,
):
    """Simulate the V38.2 EA on the specified date range."""
    print(f"=== V38.2 EA Backtest Simulation ===", flush=True)
    print(f"Period: {start_date} → {end_date}", flush=True)
    print(f"Initial deposit: ${initial_deposit}", flush=True)
    print(f"Risk per trade: {risk_pct*100}%", flush=True)
    print(f"ML threshold: {prob_threshold}", flush=True)
    print(flush=True)

    # Load dataset
    print("Loading dataset...", flush=True)
    df = pd.read_parquet(DATASET_PATH)
    df = df.sort_values("timestamp").reset_index(drop=True)
    mask = df["label"].to_numpy() >= 0
    df = df[mask].reset_index(drop=True)

    # Filter to backtest period
    df["ts"] = pd.to_datetime(df["timestamp"])
    period_mask = (df["ts"] >= start_date) & (df["ts"] <= end_date)
    df_bt = df[period_mask].reset_index(drop=True)
    print(f"Setups in period: {len(df_bt)}", flush=True)

    # Load model + calibrator
    model = joblib.load(ARTIFACT_DIR / "v38_2_final_model.joblib")
    calibrator = joblib.load(ARTIFACT_DIR / "v38_2_calibrator.joblib")

    # Get feature matrix
    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]
    X = df_bt[feat_cols].to_numpy(dtype=np.float32)

    # ML predictions
    print("Running ML inference...", flush=True)
    raw_probs = model.predict_proba(X)[:, 1]
    cal_probs = calibrator.predict(raw_probs)
    decisions = (cal_probs >= prob_threshold).astype(int)

    # Simulate trades
    print("Simulating trades...", flush=True)
    trades = []
    equity = initial_deposit
    peak_equity = initial_deposit
    day_trades = defaultdict(int)
    day_pnl = defaultdict(float)
    consec_losses = 0
    daily_locked = set()
    max_drawdown = 0.0

    for i in range(len(df_bt)):
        row = df_bt.iloc[i]
        ts = row["ts"]
        day = ts.date()

        # Check daily lock
        if day in daily_locked:
            continue

        # Check max trades per day
        if day_trades[day] >= max_trades_per_day:
            continue

        # Check consecutive losses
        if consec_losses >= max_consec_losses:
            continue

        # Check daily loss
        if day_pnl[day] <= -max_daily_loss_pct * initial_deposit:
            daily_locked.add(day)
            continue

        if decisions[i] != 1:
            continue

        # Execute trade
        direction = row["direction"]
        entry_price = row["entry_price"]
        sl_price = row["sl"]
        tp_price = row["tp"]
        label = int(row["label"])
        rr = float(row["rr"])

        # SL distance for position sizing
        sl_dist = abs(entry_price - sl_price)
        if sl_dist <= 0:
            continue

        # Position sizing: risk amount / sl distance (simplified, 1 lot = $1 per $1 move)
        risk_amount = risk_pct * equity
        # For XAUUSD: 1 lot = 100 oz, so $1 move = $100 per lot
        # lots = risk_amount / (sl_dist * 100)
        contract_size = 100.0  # standard XAUUSD
        lots = risk_amount / (sl_dist * contract_size)
        if lots <= 0:
            continue

        # Trade outcome (label=1 means TP hit, label=0 means SL hit)
        if label == 1:
            profit = rr * risk_amount  # +2R
            consec_losses = 0
        else:
            profit = -risk_amount  # -1R
            consec_losses += 1

        equity += profit
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity
        max_drawdown = max(max_drawdown, drawdown)

        day_trades[day] += 1
        day_pnl[day] += profit

        trades.append({
            "timestamp": str(ts),
            "direction": direction,
            "entry_price": entry_price,
            "sl": sl_price,
            "tp": tp_price,
            "lots": round(lots, 4),
            "prob": round(float(cal_probs[i]), 4),
            "label": label,
            "profit": round(profit, 2),
            "equity": round(equity, 2),
            "rr": rr,
        })

    # Calculate metrics
    print(f"\n=== BACKTEST RESULTS ===", flush=True)
    if len(trades) == 0:
        print("No trades executed!", flush=True)
        return None

    trades_df = pd.DataFrame(trades)
    wins = trades_df[trades_df["label"] == 1]
    losses = trades_df[trades_df["label"] == 0]
    longs = trades_df[trades_df["direction"] == "bullish"]
    shorts = trades_df[trades_df["direction"] == "bearish"]
    long_wins = longs[longs["label"] == 1]
    short_wins = shorts[shorts["label"] == 1]

    gross_profit = wins["profit"].sum()
    gross_loss = abs(losses["profit"].sum())
    net_profit = trades_df["profit"].sum()
    win_rate = len(wins) / len(trades_df) * 100
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    expectancy = net_profit / len(trades_df)
    avg_win = wins["profit"].mean() if len(wins) > 0 else 0
    avg_loss = losses["profit"].mean() if len(losses) > 0 else 0
    long_wr = len(long_wins) / len(longs) * 100 if len(longs) > 0 else 0
    short_wr = len(short_wins) / len(shorts) * 100 if len(shorts) > 0 else 0
    rel_dd = max_drawdown * 100

    # Consecutive wins/losses
    streak = 0
    max_consec_win = 0
    max_consec_loss = 0
    for _, t in trades_df.iterrows():
        if t["label"] == 1:
            streak = max(streak, 0) + 1
            max_consec_win = max(max_consec_win, streak)
        else:
            streak = min(streak, 0) - 1
            max_consec_loss = max(max_consec_loss, abs(streak))
    # Simpler: track properly
    cur_w = 0; cur_l = 0; mw = 0; ml = 0
    for _, t in trades_df.iterrows():
        if t["label"] == 1:
            cur_w += 1; cur_l = 0; mw = max(mw, cur_w)
        else:
            cur_l += 1; cur_w = 0; ml = max(ml, cur_l)

    # Sharpe-like ratio (per-trade)
    if len(trades_df) > 1:
        returns = trades_df["profit"].values
        sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    recovery_factor = net_profit / (max_drawdown * initial_deposit) if max_drawdown > 0 else 0

    metrics = {
        "period": f"{start_date} → {end_date}",
        "initial_deposit": initial_deposit,
        "total_trades": len(trades_df),
        "candidate_setups": len(df_bt),
        "ml_filtered_setups": int(decisions.sum()),
        "ml_filter_rate": float(decisions.sum() / len(df_bt) * 100) if len(df_bt) > 0 else 0,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "net_profit": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "expectancy": round(expectancy, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "max_drawdown_pct": round(rel_dd, 2),
        "max_drawdown_abs": round(max_drawdown * initial_deposit, 2),
        "final_equity": round(equity, 2),
        "consecutive_wins": mw,
        "consecutive_losses": ml,
        "long_trades": len(longs),
        "short_trades": len(shorts),
        "long_win_rate": round(long_wr, 2),
        "short_win_rate": round(short_wr, 2),
        "sharpe_per_trade": round(float(sharpe), 3),
        "recovery_factor": round(float(recovery_factor), 2),
        "trade_frequency_per_day": round(len(trades_df) / max(1, len(day_trades)), 2),
        "risk_pct": risk_pct,
        "ml_threshold": prob_threshold,
    }

    # Print results
    print(f"  Total trades: {metrics['total_trades']}", flush=True)
    print(f"  Candidate setups: {metrics['candidate_setups']}", flush=True)
    print(f"  ML filtered setups: {metrics['ml_filtered_setups']} ({metrics['ml_filter_rate']:.1f}%)", flush=True)
    print(f"  Win rate: {metrics['win_rate']}%", flush=True)
    print(f"  Profit factor: {metrics['profit_factor']}", flush=True)
    print(f"  Net profit: ${metrics['net_profit']:.2f}", flush=True)
    print(f"  Gross profit: ${metrics['gross_profit']:.2f}", flush=True)
    print(f"  Gross loss: ${metrics['gross_loss']:.2f}", flush=True)
    print(f"  Expectancy: ${metrics['expectancy']:.2f} per trade", flush=True)
    print(f"  Avg win: ${metrics['avg_win']:.2f}", flush=True)
    print(f"  Avg loss: ${metrics['avg_loss']:.2f}", flush=True)
    print(f"  Max drawdown: {metrics['max_drawdown_pct']}% (${metrics['max_drawdown_abs']:.2f})", flush=True)
    print(f"  Final equity: ${metrics['final_equity']:.2f}", flush=True)
    print(f"  Consecutive wins: {metrics['consecutive_wins']}", flush=True)
    print(f"  Consecutive losses: {metrics['consecutive_losses']}", flush=True)
    print(f"  Long trades: {metrics['long_trades']} (WR: {metrics['long_win_rate']}%)", flush=True)
    print(f"  Short trades: {metrics['short_trades']} (WR: {metrics['short_win_rate']}%)", flush=True)
    print(f"  Sharpe (per-trade): {metrics['sharpe_per_trade']}", flush=True)
    print(f"  Recovery factor: {metrics['recovery_factor']}", flush=True)
    print(f"  Trade frequency: {metrics['trade_frequency_per_day']}/day", flush=True)

    # Save trade CSV
    trades_df.to_csv(TRADE_CSV_PATH, index=False)
    print(f"\n  Trade CSV saved: {TRADE_CSV_PATH}", flush=True)

    # Save report
    report = {
        "backtest_type": "Python simulation (no MT5 terminal available)",
        "metrics": metrics,
        "v37_reference": {
            "period": "2026-01-01 → 2026-05-31",
            "initial_deposit": 5000,
            "trades": 157,
            "win_rate": 43.31,
            "profit_factor": 1.29,
            "net_profit": 633.20,
            "max_drawdown": 11.63,
            "long_win_rate": 47.67,
            "short_win_rate": 38.03,
        },
        "notes": [
            "This is a Python simulation, NOT an MT5 Strategy Tester backtest",
            "Execution assumed at close price with no slippage",
            "Real MT5 backtest results may differ due to spread, slippage, commission",
            "ML model and feature pipeline are identical to what the EA uses",
            "Risk management logic mirrors the EA's MQL5 implementation",
        ],
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved: {REPORT_PATH}", flush=True)

    return metrics


if __name__ == "__main__":
    run_backtest()
