# KingIn Trading System - Installation & Setup Guide

This guide provides step-by-step instructions for installing and running the KingIn Institutional Trading System as a native desktop application on Windows.

## Prerequisites

1.  **Python 3.10+**: Ensure Python is installed and added to your PATH.
2.  **Node.js 18+**: Required for the Electron/React dashboard.
3.  **MetaTrader 5**: Installed and logged into your broker account.
4.  **MT5 Auto-Trading**: Enabled in the MT5 Terminal options.

## Installation

1.  **Clone the Repository**:
    ```bash
    git clone <repo-url>
    cd kingin-master
    ```

2.  **Initialize Environment**:
    Run the setup script to create the virtual environment and install dependencies:
    ```bash
    ./SETUP_PROJECT.bat
    ```

3.  **Configure Environment Variables**:
    Create a `.env` file in the root directory:
    ```env
    KINGIN_USER_PASSWORD=your_secure_password
    KINGIN_JWT_SECRET=your_random_secret_string
    ```

4.  **Install Node Dependencies**:
    ```bash
    npm install
    cd kingin-vite
    npm install
    cd ..
    ```

## Running the Application

### Development Mode
To run the system with hot-reloading:
```bash
npm run dev
```

### Building the Desktop App (Installer)
To generate a portable Windows installer (`.exe`):
```bash
npm run electron:build
```
The installer will be generated in the `dist_electron/` directory.

## Configuration

-   **Broker Symbols**: Map your broker's symbols in `Engine/data_feed/symbol_map.json`.
-   **Trading Parameters**: Adjust risk and strategy settings in `config/trading_params_lite.json`.
-   **ML Filter**: The ML layer is compulsory and loads its model from `models/lgbm_signal_filter.json`.

## Security

-   The application uses **JWT-based authentication**.
-   You must log in with the password defined in your `KINGIN_USER_PASSWORD` environment variable.
-   All API endpoints are protected and require a valid token.

---
© 2024 KingIn Institutional Trading
