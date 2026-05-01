# System Migration Guide: v6.0 Institutional Trading Stack

This document outlines the precise steps required to migrate the trading system to a new machine while maintaining state integrity and connection stability.

## 📋 Pre-Migration Checklist
- [ ] Ensure the new machine has **Python 3.10+** installed.
- [ ] Ensure **MetaTrader 5 (MT5)** is installed and logged into the broker account.
- [ ] Ensure **Sierra Chart** is installed with DTC Server enabled (Port 11099).

---

## 🚀 Step-by-Step Migration

### 1. File Transfer
Copy the entire `s.y.s.t.e.m` directory to the new machine. 
> [!IMPORTANT]
> Do NOT copy the `.venv` folder. You must recreate the virtual environment on the new machine to ensure compatibility.

### 2. Environment Setup
Open a terminal in the project root and run:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. State & database Verification
Verify that the following files were transferred correctly to maintain trade history:
- `e:\s.y.s.t.e.m\data\hedge.db` (Crucial for trade history and balance tracking)
- `e:\s.y.s.t.e.m\storage\risk_state\risk_state.json` (Maintains the Global Kill Switch status)

### 4. Configuration Updates
Update the `.env` file on the new machine if local paths or Sierra Chart IP addresses have changed.

### 5. MT5 EA Installation
1. Open MT5 on the new machine.
2. Go to `File -> Open Data Folder`.
3. Navigate to `MQL5\Experts`.
4. Copy the EA files from `e:\s.y.s.t.e.m\mt5\experts` to this directory.
5. In MT5, ensure **"Allow DLL imports"** is checked in `Tools -> Options -> Expert Advisors`.

---

## ✅ DOs and ❌ DON'Ts

### The DOs
- **DO** run `python tests/diag_system_health.py` immediately after migration to verify all components (ZMQ, DTC, API) are communicating.
- **DO** use the `GLOBAL_START.bat` launcher to ensure the Server and Engine start in the correct dependency order.
- **DO** verify the first trade on a **Demo Account** before switching to institutional capital.
- **DO** ensure the computer's time is synced with UTC to prevent session filter errors.

### The DON'Ts
- **DON'T** run multiple instances of the `Engine` on the same machine (this will cause ZMQ port conflicts).
- **DON'T** bypass the virtual environment (running globally can lead to library version conflicts).
- **DON'T** delete `hedge.db` unless you want to wipe all performance history and audit trails.
- **DON'T** disable the `Global Kill Switch` until you have verified the real-time spread via the Dashboard.

---

## 🛠️ Troubleshooting Connection issues
If the system fails to connect after migration:
1. **ZMQ Port Error**: Check if Ports 5555, 5556, or 5557 are being used by another application. Port 5556 is use for the Conflated Market Data Tunnel.
2. **Execution Lag**: Ensure `zmq.CONFLATE` is set to 1 in the Engine settings to eliminate the 12-second drift.
3. **DTC Timeout**: Ensure Sierra Chart -> Global Settings -> DTC Server -> "Allow Remote Connections" is checked if the Engine is on a different machine.
4. **Module Error**: Run `pip install -r requirements.txt` again to ensure no libraries were skipped.
