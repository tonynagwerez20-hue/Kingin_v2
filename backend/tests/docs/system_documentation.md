# Institutional Trading System: Production Documentation
**Status:** v5.5.0 Production Ready (9.5/10)
**Asset:** XAUUSD (Gold) Focus

---

## 🏗️ System Architecture
The system follows a modular "Defense in Depth" architecture, separating market data acquisition, alpha strategy generation, and risk enforcement.

### 1. Data Acquisition Layer
- **Primary:** Sierra Chart DTC Protocol (Binary VLS Encoding).
- **Secondary/Fallback:** Sierra Chart CSV Exports (Precise Delta Mapping).
- **Ingestion:** `DTCClient` maintains a persistent TCP stream for ultra-low latency ticks. `CSVBatchProcessor` provides high-precision historical delta audits.
- **Feed Server:** FastAPI provides high-speed access to OHLC buffers, Delta structures (CVD), and market spread via:
  - `/ohlc`: Candle history (Multi-TF)
  - `/delta`: Bid/Ask Volume imbalance and CVD (Precise Mapping)
  - `/latest-tick`: Real-time price and microstructure data

### 2. Alpha Strategy: "Two Filters + One Trigger"
The system implements a strict hierarchical confluence model managed by `StrategyManager`:

- **Filter 1 (Bias - H1):** `FilterOne` analyzes higher-timeframe swing structure (HH/HL or LH/LL) to establish global direction. No trades are allowed counter-bias.
- **Filter 2 (Zone - M15):** `FilterTwo` detects Supply and Demand zones. Price must be within an active, unmitigated zone to permit execution.
- **Trigger (Orderflow - M5):** `OrderflowStrategy` waits for specific microstructure events:
  - **FLIP:** Delta crossing zero with momentum alignment.
  - **SURGE:** Delta spike (>2σ) indicating aggressive participation.
- **Exit Logic:** Independent of filters. Positions are closed immediately on **Delta Reversal** or Stop Loss hit. There is **no Take Profit**; the system follows the trend until momentum shifts.

### 3. Risk Defense & Enforcement
A 5-Layer protection stack ensures capital survival:

| Layer | Component | Function |
| :--- | :--- | :--- |
| **I. Global** | `RiskManager` | Hard kill-switch and emergency system halt. |
| **II. Strategy** | `RiskCalculator` | Calculates zone-based SL and lots. **Max Stop: 50 pips**. |
| **III. Microstructure** | `CRORules` | Audits spread (<3.0 pips) and liquidity before entry. |
| **IV. Temporal** | `SessionFilter` | Restricts entries to London/NY window (**08:00 - 21:00 UTC**). |
| **V. Connectivity** | `BrokerWatchdog` | Ensures connection to MT5 EA/Bridge is stable. |

---

## 🚀 Execution Stack
- **Bridge:** ZeroMQ (REQ/REP) on port 5555 for trade execution and account sync.
- **Execution Agent:** MetaTrader 5 Expert Advisor (EA) running in MQL5.
- **Logic:** Fire-and-forget signal dispatch from Python to MT5 for sub-100ms execution of SL/Lot structured orders. Includes acknowledgment loop.

---

## 📋 Component Roadmap {#roadmap}
- [x] **v5.0:** Modular Bias/Zone logic.
- [x] **v5.2:** Session filters, Spread endpoint, and Max SL protection.
- [x] **v5.3:** MT5 Acknowledgment loop & Dynamic Account Balance fetching.
- [x] **v5.4:** Sierra Chart DTC Protocol integration (VLS Binary).
- [x] **v5.5:** Professional React (Next.js) Dashboard & Precise Delta Mapping.
- [ ] **v6.0 (Planned):** Monte Carlo Drawdown Simulation & Kelly Criterion Scaling.

---

## 🔧 Deployment Instructions
1. **DTC Server:** Enable DTC Server in Sierra Chart (Port 11099, Binary VLS).
2. **Data Feed:** Start `data_feed/server.py`.
3. **Execution:** Load `HedgeEA.mq5` in MT5. Ensure "Algo Trading" is enabled.
4. **Engine:** Run `UNIVERSAL_CONTROL.bat` or `python start_system.py`.
5. **UI:** Run `npm run dev` in `dashboard-react`.

---
*Document produced by Antigravity AI for Tony Nagwere.*

