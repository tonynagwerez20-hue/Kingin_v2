# HedgeEA SMC v6.0 - Restored

Institutional-grade SMC (Smart Money Concepts) trading robot for MetaTrader 5.

## 🚀 One-Click Startup
Use the following batch files on your desktop or in the root folder:
- **`START_ALL.bat`**: Launches the entire system (Data Server, Engine, and CLI Dashboard).
- **`SYSTEM_ON.bat`**: Activates the trading logic if the engine is running.
- **`SYSTEM_OFF.bat`**: Deactivates trading logic (Standby mode).
- **`START_DASHBOARD.bat`**: Launches only the Streamlit GUI dashboard.

## 🛠 Project Structure
- **/Engine**: Core SMC pipeline and modular bootstrapper.
- **/data_feed**: Connectivity to MT5 and local data serving.
- **/config**: System parameters (trading symbols, risk rules, etc.).
- **/dashboard**: Web-based monitoring UI.
- **/storage/logs**: Real-time telemetry (`server_live.log`).

## ⚖️ Requirements
This system has been optimized to run on **Global Python 3.10**. 
- Virtual environments on this machine were found to be unstable (Exit code -1073741510).
- **MetaTrader 5 terminal must be open** and logged into your preferred account before starting.

## ⚙️ Account Configuration
The system prefers your **active MT5 terminal account**. 
If you want to use a specific account regardless of what is open, update `config/trading_params_lite.json` with your credentials:
```json
"data_provider": {
    "config": {
        "login": YOUR_ACCOUNT_NUMBER,
        "password": "YOUR_PASSWORD",
        "server": "YOUR_SERVER_NAME"
    }
}
```

## 📜 Maintenance
- **Logs**: Monitor `storage/logs/server_live.log` for execution errors.
- **Master Switch**: Toggles are found in `SYSTEM_ON.bat` and `SYSTEM_OFF.bat`.

## 📦 Deploying to a New Machine
If you are taking this code to a completely new laptop, desktop, or VPS, follow this exact sequence to re-bootstrap the entire stack:
1. **Python Dependencies**: Run `install.bat` once to grab `pywin32`, `zmq`, `MetaTrader5`, etc.
2. **Native Compilers**: Right-click `INSTALL_CPP_TOOLS_ADMIN.ps1` and select **Run with PowerShell** (you must click **Run As Administrator** if prompted). This will silently download the ~2GB Visual Studio C++ Compiler needed for the desktop UI.
3. **Build Target**: Finally, run `SETUP_TAURI.bat`. It will automatically rebuild the React frontend, link the native Windows application, and construct your `.exe` and Desktop icon!
