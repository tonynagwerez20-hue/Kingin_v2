# Institutional Trading System v6.1 (Restored)

Professional-grade SMC (Smart Money Concepts) trading robot for MetaTrader 5 with real-time orderflow and multi-layer filtration.

## 📥 New Machine Setup
Follow these steps to replicate this exact environment on a new machine:

1. **Install Python 3.10.x**: 
   - [Download from Python.org](https://www.python.org/downloads/windows/)
   - **IMPORTANT**: During installation, tick the box: **"Add Python 3.10 to PATH"**.
2. **Install MetaTrader 5**: 
   - Ensure your broker terminal is installed and logged in.
3. **Run `SETUP_PROJECT.bat`**: 
   - This will install all necessary libraries (`fastapi`, `streamlit`, `mt5`, etc.) into your global Python environment.
   - It is the most stable method for this system.

## 🚀 One-Click Control
- **`START_ALL.bat`**: The master button. Launches the Data Server, Strategy Engine, and Dashboard together.
- **`SYSTEM_ON.bat` / `SYSTEM_OFF.bat`**: Toggles the trading logic without stopping the engine.
- **`START_DASHBOARD.bat`**: Launches the Streamlit performance monitor.

## ⚙️ Configuration
The system uses **`config/trading_params_lite.json`** as its single source of truth.
- Update your **Login**, **Password**, and **Server** under the `data_provider` section.
- The system enforces a **STRICT LOGIN** policy — it will only trade on the account provided in the config.

## 📂 Architecture
- **`/Engine`**: The "Brain". Contains SMC logic and IGOF filtration layers.
- **`/data_feed`**: The "Nervous System". Connects to MT5 and serves live market data.
- **`/storage/logs`**: Real-time audit logs (`server_live.log`).
- **`/dashboard`**: Premium monitoring UI.

## 🛠 Stability Note
If the system crashes with code `-1073741510`, it is usually due to a corrupted Virtual Environment. Always prefer the **Global Python** path on Windows for maximum reliability.