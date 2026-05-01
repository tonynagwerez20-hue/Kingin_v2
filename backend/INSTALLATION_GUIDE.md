# KingIn Institutional Trading System - Installation Guide

This guide will help you set up the KingIn Trading System on any Windows machine.

## Prerequisites

1.  **Python 3.10 or higher**: [Download from Python.org](https://www.python.org/downloads/windows/)
    *   **IMPORTANT**: During installation, check the box **"Add Python to PATH"**.
2.  **Node.js 18 or higher**: [Download from Nodejs.org](https://nodejs.org/)
3.  **MetaTrader 5 (MT5)**: Installed and logged into your trading account.

## Setup Instructions

### 1. Install Python Dependencies
Open a terminal (PowerShell or CMD) in the project root and run:
```powershell
pip install -r requirements.txt
```

### 2. Install Project Dependencies
Run the following commands to install the necessary Node.js modules:
```powershell
npm install
cd kingin-vite
npm install
cd ..
```

### 3. Configure Environment Variables
Copy the environment template and set your access password:
```powershell
copy .env.example .env
```
Then open `.env` in any text editor and set your desired dashboard login password:
```
KINGIN_USER_PASSWORD=your_secure_password_here
```
> **This step is required.** Without it, the dashboard login will always reject your password.

### 4. Build the Desktop Application
To create the final installer, run the provided build script:
```powershell
.\BUILD_DESKTOP_APP.bat
```
This script will:
*   Clean up old build files.
*   Compile the React frontend.
*   Package the Electron application along with the Python backend.
*   Generate a professional installer in the `dist_electron` folder.

## Running the Application

### Option A: Using the Installer (Recommended)
1.  Go to the `dist_electron` folder.
2.  Run `KingIn Trading System Setup 1.0.0.exe`.
3.  The app will be installed to your Program Files and a shortcut will be added to your desktop.

### Option B: Running in Development Mode
If you want to run the app without installing it:
```powershell
npm run dev
```

## Troubleshooting

*   **Backend Connection Error**: Ensure no other process is using port 8080. If the app shows "OFFLINE", check if `python` is available in your terminal by typing `python --version`.
*   **MT5 Connection**: Make sure MT5 is open and "Algo Trading" is enabled in the MT5 settings.
*   **Missing Directories**: The system will automatically create `storage/logs` and `data` directories on first run.

## Support
For further assistance, refer to the `docs/` directory or contact the development team.
