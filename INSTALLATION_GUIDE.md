# KingIn Trading System - Setup Guide

This guide provides step-by-step instructions for setting up the KingIn Trading System on a new Windows machine.

## 🚀 Option 1: Quick Start (Running the Executable)
Use this if you just want to run the platform as a professional desktop application.

1.  **Prerequisites:**
    *   **MetaTrader 5 (MT5)** must be installed and running.
    *   **Python 3.10+** must be installed and added to your Windows PATH.
2.  **Steps:**
    *   Navigate to `frontend\dist_electron\`.
    *   Double-click `KingIn Trading System 1.0.0.exe`.
    *   Enter the Access Password (default: `kingin123`).
    *   Configure your MT5 credentials in the Settings panel and click **Start Engine**.

---

## 🛠️ Option 2: Development Setup (Source Code)
Use this if you want to modify the code or run in development mode.

### 1. Prerequisites
Ensure the following are installed on the new machine:
- [Python 3.10 or higher](https://www.python.org/downloads/)
- [Node.js 18 or higher](https://nodejs.org/)
- [MetaTrader 5](https://www.metatrader5.com/en/download)

### 2. Backend Setup
1.  Open a terminal in the `backend/` folder.
2.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Ensure your `.env` file exists in the `backend/` folder (copy from `.env.example` if available).

### 3. Frontend Setup
1.  Open a terminal in the `frontend/` folder.
2.  Install Node.js dependencies:
    ```bash
    npm install
    ```

### 4. Running the System
You can launch the entire system using the master script in the root directory:
- Run **`START_SYSTEM.bat`** (Starts both the FastAPI backend and Vite frontend).

---

## 🔐 MT5 Connection Requirements
For the Trading Engine to talk to your broker:
1.  In MT5, go to **Tools > Options > Expert Advisors**.
2.  Check **"Allow Algorithmic Trading"**.
3.  Check **"Allow DLL imports"**.
4.  Ensure the **HedgeEA** is attached to at least one chart (e.g., XAUUSD).

---

## 📁 Project Structure
- `backend/`: Python API, Trading Engine, and Configurations.
- `frontend/`: React Dashboard and Electron Shell.
- `dist_electron/`: Contains the final compiled executable.

---

## 🔧 Troubleshooting
- **Connection Failed:** Ensure `python` is typed correctly in your terminal. If `python` command is not found, the EXE cannot spawn the backend.
- **Empty Dashboard:** Check `backend/storage/logs/engine_live.log` for any engine-level errors.
- **Proxy Errors:** Ensure no other service is using ports **8088** or **5000**.
