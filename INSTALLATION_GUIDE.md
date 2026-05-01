# 🛠 KingIn Trading System — Installation & Setup Guide

This guide covers the full setup of the KingIn Institutional Trading System on a new machine.

## 📋 Prerequisites

Before you begin, ensure your machine meets the following requirements:

- **Operating System**: Windows 10/11 (64-bit)
- **Python**: Version 3.10 or higher ([Download](https://www.python.org/downloads/))
- **Node.js**: Version 18.x or higher ([Download](https://nodejs.org/))
- **Trading Platform**: MetaTrader 5 (MT5) with "Allow Algorithmic Trading" enabled.

---

## 🚀 Step-by-Step Installation

### 1. Clone or Copy the Code
Ensure the folder structure is maintained exactly as:
```text
kingin-master/
├── backend/
└── frontend/
```

### 2. Backend Environment Setup
Open a terminal in the `backend/` directory:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Environment Setup
Open a terminal in the `frontend/` directory:
```powershell
cd frontend
npm install
```

### 4. Configuration (`.env`)
Create a `.env` file in the `backend/` directory (you can use `.env.example` as a template). 
**CRITICAL**: Set your `KINGIN_USER_PASSWORD`. This is what you will use to log into the dashboard.

```env
KINGIN_USER_PASSWORD="your_secure_password"
MT5_LOGIN=12345678
MT5_PASSWORD="mt5_password"
MT5_SERVER="Broker-Server"
```

---

## ⚡ Running the System

### Standard Launch
Double-click the `START_SYSTEM.bat` file in the root directory. This script will:
1.  Check for Python and Node.js.
2.  Start the Backend API (Port 8088).
3.  Perform a health check until the API is responsive.
4.  Launch the Frontend Dashboard (Vite).

### Production Build
If you want to generate a standalone Windows executable:
1.  Go to `frontend/`.
2.  Run `npm run electron:build`.
3.  The installer will be generated in `frontend/dist_electron/`.

---

## 📂 Machine-to-Machine Transfer

To move KingIn to another computer, follow these steps to ensure a "seamless" transition:

1.  **Copy the Folder**: Copy the entire `kingin-master` folder to the new machine.
2.  **External dependencies**: Ensure Python 3.10+ and Node.js 18+ are installed on the target machine.
3.  **Update .env**: On the new machine, open `backend/.env` and verify the MT5 credentials and `KINGIN_USER_PASSWORD` are correct for that specific machine/user.
4.  **Re-run Installers**: Run `START_SYSTEM.bat`. The system is designed to automatically detect and install missing Python packages on first launch.
5.  **MT5 Permissions**: Ensure MetaTrader 5 on the new machine has **"Allow Algorithmic Trading"** and **"Allow DLL imports"** checked in `Tools > Options > Expert Advisors`.

---

## 🤖 ML Layer Constant Learning

The system is designed to learn constantly from live market data:
- **Trade Logging**: Every trade taken is recorded in `backend/data/trade_log.json`.
- **Online Learning**: The `RiverDriftMonitor` updates after *every closed trade*, adjusting the signal confidence based on recent performance.
- **Weekly Retraining**: The core LightGBM model is scheduled to retrain every **Sunday at 23:00 EAT** using the latest historical data.
- **Persistence**: Models are saved in the `backend/models/` folder. When moving machines, ensure you copy this folder to keep your system's "memory."

---

## ❓ Troubleshooting

- **Port Conflict**: If port 8088 or 5173 is in use, the system will fail to start. Check for other running instances.
- **MT5 Connection**: If the dashboard shows "MT5 DISCONNECTED", verify that the MT5 terminal is open and the credentials in `.env` are correct.
- **Execution Error**: Check `backend/storage/logs/engine_stdout.log` for detailed backend error messages.
