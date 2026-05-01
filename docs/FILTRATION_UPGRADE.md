# 📖 Multi-Layer Filtration System — Technical Documentation

## Overview
The upgraded filtration system transforms basic pattern recognition into a deterministic, high-probability execution framework. It follows a 6-layer waterfall logic where each layer must pass (or be manually bypassed) to allow trade execution.

---

## 🏗️ The 6-Layer Architecture

### Layer 1: H1 Structural Bias Engine
**Objective**: Define the "Directional Authority".
- **BOS (Break of Structure)**: Confirms trend continuation or reversal.
- **Displacement**: Measures the strength of the move via candle spread.
- **Imbalance (FVG)**: Identifies price inefficiencies (Fair Value Gaps).
- **Scoring**:
  - `3`: BOS + Displacement + Imbalance (Strong)
  - `2`: BOS + Moderate Impulse (Moderate)
  - `< 2`: Neutral/Weak (No trade permission)

### Layer 2: Zone Quality Engine
**Objective**: Score Supply/Demand zones based on institutional footprint.
- **Freshness**: Untouched zones have higher probability.
- **Impulse Departure**: Rapid price movement away from the zone.
- **HTF Alignment**: Alignment with the H1 Bias score from Layer 1.
- **Threshold**: Only zones scoring `≥ 3` are active for valid trades.

### Layer 3: Liquidity Event Confirmation
**Objective**: Trap identification and stop-hunting confirmation.
- Look for **EQH (Equal Highs)** or **EQL (Equal Lows)** sweeps.
- Confirms that retail liquidity has been purged before the real move starts.

### Layer 4: Microstructure Shift (mBOS)
**Objective**: LTF (M5) confirmation of control shift.
- Detection of **mBOS (Micro Break of Structure)**.
- Price must close beyond internal structure to confirm the shift.

### Layer 5: Displacement Validation
**Objective**: Ensure the entry candle has institutional backing.
- **Large Body**: High body-to-wick ratio (> 60%).
- **Spread**: Minimal overlap with previous candles.

### Layer 6: Candlestick Confirmation
**Objective**: Final trigger confirmation.
- **Bullish/Bearish Engulfing**.
- **Strong Rejection** (Pinbars/Hammer) inside the qualified zone.

---

## ⚙️ Configuration & Integration

### Activation Mode
The system is currently integrated into `Engine/main_loop.py` in **Audit Mode**.

- **Log-Only**: Signals are audited against IGOF layers, and results are printed to the console (`[IGOF] ✅ PASSED` or `[IGOF] 🛑 WOULD BLOCK`).
- **Blocking Mode**: To enable active filtration, uncomment the `continue` statement in `main_loop.py` at line 347.

### Key Files
- **Logic Engine**: [`v1_engine.py`](file:///e:/s.y.s.t.e.m/Engine/igof/v1_engine.py)
- **Controller**: [`stack.py`](file:///e:/s.y.s.t.e.m/Engine/igof/stack.py)
- **Signal Loop**: [`main_loop.py`](file:///e:/s.y.s.t.e.m/Engine/main_loop.py)

---

### Signal Replay (EA Integration)
To ensure the MT5 EA can read and execute the generated backtest signals, use the replay utility:

1. **Open MetaTrader 5** and ensure the `HedgeEA` is attached with ZMQ enabled.
2. Run the replay script:
   ```powershell
   python Engine/replay_signals_to_ea.py
   ```
This script reads `data/upgraded_signals.csv` and broadcasts each signal to the EA via the `Bridge` (ZMQ Port 5555).

### Performance Monitoring
To monitor the system effectiveness:
1. Run in backtest mode: `python Engine/main_loop.py --backtest`.
2. Review `audit_logs` in the position tracker database.
3. Compare `FILTER_VETO_READY` events with actual trade outcomes to fine-tune thresholds.

---

## 🧠 Core Philosophy
> "HTF = Direction | Zone = Location | Liquidity = Intent | Microstructure = Control Shift"

### MT5 Backtesting (Strategy Tester)
The upgraded signals are automatically written to data/backtest_signals.csv in the exact 9-column format required by the HedgeEA.

To run an offline backtest in MT5:
1. **Copy** e:\s.y.s.t.e.m\data\backtest_signals.csv to your MetaTrader 5 Common folder:
   - Path: %AppData%\MetaQuotes\Terminal\Common\Files
2. **Open MT5 Strategy Tester** and select HedgeEA.
3. **Set EA Inputs**:
   - `BACKTEST_MODE` = `true`
   - `BACKTEST_FILE` = `backtest_signals.csv`
   - `ENABLE_VISUAL_REPLAY` = `true` (CRITICAL: This bypasses the 1-hour signal expiration check, allowing historical signals to execute on the current chart for visual verification)
   - `SIGNAL_TIME_SHIFT`: Adjust if your broker's time differs from the signal time (Sierra Chart UTC).

### Option C: ZMQ Signal Injection (Live/Forward Test)
To verify the entire Python-to-EA pipeline (bypassing the internal CSV reader):
1. **Set EA Inputs**: `BACKTEST_MODE` = `false`.
2. **Start EA**: It will listen on port 5555.
3. **Run Python Injector**:
   ```bash
   python Engine/replay_signals_to_ea.py
   ```
   This script reads `backtest_signals.csv` and broadcasts them via ZeroMQ. The EA will receive and execute them as if they were live market signals.

4. **Start**: Click OK. The EA will now read the file and execute trades sequentially (simulated) as they appear in the file.
