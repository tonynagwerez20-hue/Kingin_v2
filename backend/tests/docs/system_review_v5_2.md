# Institutional Trading System - System Review v5.2 (Release Candidate)
**Date:** 2026-01-09
**Status:** Operational (DTC/CSV Hybrid)

## 1. System Architecture Overview
The system is a high-frequency, institutional-grade trading engine designed for **XAUUSD**. It operates on a hybrid architecture combining a Python-based Strategy Engine with a MetaTrader 5 (MT5) Execution Bridge and a Sierra Chart Data Feed.

### Core Components
-   **Data Feed (Hybrid)**:
    -   **Primary**: Sierra Chart DTC Protocol (Binary, Localhost:11099). Provides tick-by-tick precision.
    -   **Fallback**: CSV File Polling (High-Frequency, 1s interval).
-   **Aggregator**: Custom `TimeframeEngine` that maintains **M5, M15, H1** bars and **M5 Delta** stats in memory (500-candle history).
-   **Strategy Engine**: "The Brain". Evaluates confluence of:
    1.  **H1 Bias**: Market Structure (Bulls/Bears).
    2.  **M15 Zones**: Supply/Demand Zone detection.
    3.  **M5 Orderflow**: Delta Surge/Flip triggers.
-   **Execution Bridge**: ZeroMQ (ZMQ) connection to `HedgeEA.mq5` running on MT5.
-   **Persistence**: SQLite (`hedge.db`) via `HedgeDB` class. Automatically captures closed bars and trade history.

---

## 2. Recent Performance Upgrades (v5.2)

### ⚡ 500-Candle Deep History
-   **Buffer Expansion**: All analysis buffers (H1, M15, M5) now hold **500 candles** (previously 100).
-   **Impact**: drastically improves the accuracy of Supply/Demand zones and Trend Bias by analyzing a wider historical window.

### 🏎️ 1-Second Refresh Rate
-   **Latency Reduction**: The global `LOOP_INTERVAL` and data polling frequency were reduced from **5s to 1s**.
-   **Impact**: The system detects "FLIP" and "SURGE" orderflow signals almost instantly as they happen.

### 🏛️ DTC Protocol Migration
-   **Tick-Level Precision**: Migrated from simple CSV snapshots to the **DTC Protocol**.
-   **Delta Tracking**: The engine now calculates `MaxDelta`, `MinDelta`, and `CumulativeSessionDelta` from raw ticks.
-   **Instant Warm-Up**: Implemented `HistoricalPriceDataRequest` (Msg 5) to instantly backfill the 500-candle buffers on startup.

### 🧹 Environment Standardization
-   **Virtual Env**: Renamed `venv` to `.venv` for standard compliance.
-   **Configuration**: Centralized settings in `.env` file (Mode switching, Risk configs).

---

## 3. Operational Guide

### 📂 Directory Structure
-   **Root**: `e:\s.y.s.t.e.m`
-   **Virtual Env**: `.venv`
-   **Shortcuts**:
    -   `GLOBAL_START.bat`: Launches Data Feed + Engine + Dashboard.
    -   `START_TRADING_SYSTEM.bat`: Launches Console Only.
    -   `START_DASHBOARD.bat`: Launches Streamlit Dashboard.

### ⚙️ Configuration (.env)
Manage the system mode via the `.env` file in the root directory:
```bash
# DATA_SOURCE_TYPE=CSV  <-- Default fallback
DATA_SOURCE_TYPE=DTC    <-- Recommended for Live Trading
```

### 🚀 How to Start
1.  **Sierra Chart**: Ensure DTC Server is active (Port 11099).
2.  **MetaTrader 5**: Ensure `HedgeEA` is on a chart (Expert Advisors enabled).
3.  **Launch**: Double-click `GLOBAL_START.bat`.

---

## 4. Current System Health

| Component | Status | Notes |
| :--- | :--- | :--- |
| **Data Feed** | 🟢 READY | DTC Client implemented; CSV fallback active. |
| **Strategy** | 🟢 READY | Logic verified (Bias+Zone+Delta). |
| **Execution** | 🟡 PENDING | ZMQ Bridge active; EA needs `GET_POSITIONS` update. |
| **Dashboard** | 🟢 READY | Streamlit app functional. |
| **Buffers** | 🟢 PASS | 500-candle capacity verified. |

## 5. Next Steps
1.  **Monitor Live**: Run the system in `DTC` mode during an active session to verify orderflow alignment.
2.  **EA Update**: Update `HedgeEA.mq5` to fully support the new `GET_POSITIONS` checks if needed for advanced management.
3.  **Trade**: Wait for the "Triple Confluence" (H1 Bias + M15 Zone + M5 Trigger).
