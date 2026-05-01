# KingIn Institutional Trading System

A professional, secure, and portable desktop application for algorithmic trading via MetaTrader 5.

## 🚀 Quick Start

1.  **Install Prerequisites**: 
    - [Python 3.10+](https://www.python.org/downloads/)
    - [Node.js 18+](https://nodejs.org/)
    - MetaTrader 5 (Logged in)

2.  **Initialize Project**:
    Run the setup script to prepare the environment and initialize security:
    ```bash
    ./SETUP_PROJECT.bat
    ```

3.  **Set Access Password**:
    Open the generated `.env` file and set your `KINGIN_USER_PASSWORD`. This password is required to log into the desktop dashboard.

4.  **Build & Install**:
    Generate your professional Windows installer:
    ```bash
    ./BUILD_DESKTOP_APP.bat
    ```
    Launch the generated installer from `dist_electron/` to install KingIn to your machine with a desktop shortcut.

## 🛠️ Configuration

The first time you launch the application, you will be greeted by a **First-Run Setup Wizard**. This guides you through:
-   **Broker Connection**: MT5 Account, Server, and Password.
-   **Risk Management**: Lot sizes, risk percent, and confluence thresholds.
-   **System Setup**: Primary trading symbol.

Once completed, these settings can be managed at any time via the **Settings** panel in the main dashboard.

## 🔒 Security & Privacy

-   **JWT Authentication**: Secure local communication between the React dashboard and the Python trading engine.
-   **Protected Control**: All engine lifecycle commands (Start/Stop) require valid authentication.
-   **Local Operation**: Your trading data and credentials stay on your machine.

## 📉 Core Components

-   **IGOF Engine**: Sequential filtration pipeline with mandatory ML signal validation.
-   **ZMQ Bridge**: High-performance signal transmission to the MT5 HedgeEA.
-   **Aesthetic Dashboard**: Premium dark-mode interface for real-time monitoring and control.

---
© 2024 KingIn Institutional Trading
