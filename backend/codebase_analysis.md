# KingIn Institutional Trading System - Codebase Analysis

## 1. Architecture Overview
The KingIn Trading System is a multi-tier application designed for high-frequency institutional trading. It combines a high-performance Python back-end with a modern React front-end, all wrapped in an Electron shell for a native desktop experience.

### High-Level Stack:
-   **Frontend**: React + Vite (UI/UX)
-   **Middleware API**: FastAPI (RESTful bridge)
-   **Native Wrapper**: Electron (Window & Lifecycle Management)
-   **Core Engine**: Python (Trading Logic, ML Filtering, ZMQ Bridge)
-   **Data Storage**: SQLite (Trade logs and historical data)

---

## 2. Component Breakdown

### A. The Native Wrapper (`electron/`)
This layer handles the operating system level integration.
-   **`main.js`**: The entry point. It manages the application lifecycle (ready, quit, window-all-closed) and **spawns the Python backend** automatically. It also implements the **IPC Bridge**, proxying API calls from the UI to the Python server to bypass CORS issues.
-   **`preload.js`**: A security layer that safely exposes specific Electron functions (like `apiCall`) to the React frontend.

### B. The Backend API (`kingin_api.py`)
This is the "Brain" that connects the user interface to the trading engine.
-   **Endpoint Management**: Provides routes for starting/stopping the trading engine, checking system status, and authenticating users.
-   **Portability Logic**: Dynamically creates necessary directories (`storage/logs`, `data`) and manages the engine's subprocess state.
-   **Security**: Implements JWT (JSON Web Tokens) for UI login and a separate `X-Control-Token` for secure engine management.

### C. The Trading Engine (`Engine/`)
This is where the actual quantitative trading logic resides.
-   **`main_loop.py`**: The heart of the trading logic. It orchestrates signal generation, filtering, and execution.
-   **`modular_bootstrapper.py`**: A complex initialization system that loads the strategy pipeline (Data Providers, Layers, and Filters).
-   **`zmq_bridge.py`**: Connects the Python engine to MetaTrader 5 (MT5). It sends execution commands to the **HedgeEA** expert advisor over a local bridge.
-   **`signal_generator.py`**: Contains the logic for generating entry/exit signals based on institutional SMC (Smart Money Concepts) or other alpha strategies.
-   **`historical_backtest.py`**: Allows users to test strategies on historical data before going live.

### D. Machine Learning Layer (`models/`)
-   **`lgbm_signal_filter.pkl`**: A pre-trained LightGBM model used to filter signals. It analyzes market context to decide if a generated signal has a high probability of success, reducing drawdowns.

### E. The Dashboard UI (`kingin-vite/`)
A state-of-the-art dashboard for monitoring and control.
-   **`api.js`**: Handles communication. It uses a custom **IPC Adapter** in production to route calls through Electron, ensuring 100% connectivity.
-   **`KingInDashboard.jsx`**: The main interface. It visualizes the trading engine state, account balance, and active trade logs in real-time.

---

## 3. Data Flow Analysis

1.  **Start Engine**: User clicks "START" in the React Dashboard.
2.  **API Call**: The dashboard sends an IPC request to Electron Main, which calls the `/api/engine/start` endpoint in `kingin_api.py`.
3.  **Spawn Engine**: `kingin_api.py` spawns `Engine/main_loop.py` as a subprocess.
4.  **Signal Generation**: `main_loop.py` reads market data from MT5, generates a signal, and runs it through the ML filter in `models/`.
5.  **Execution**: If the signal passes, `zmq_bridge.py` sends a JSON command over a local socket to the MetaTrader 5 EA.
6.  **Reporting**: The engine updates the SQLite database and logs. The Dashboard polls the API every 3 seconds to reflect these changes visually.

---

## 4. Key Security & Reliability Features
-   **IPC Proxying**: Ensures that network issues or browser firewalls cannot disconnect the UI from the Engine.
-   **Standardized API Tokens**: Prevents unauthorized external control of the trading engine.
-   **Automatic Path Discovery**: Allows the app to find its own scripts regardless of whether it's in a dev folder or installed in `Program Files`.
-   **Self-Healing Logs**: The backend automatically clears old logs or creates new ones to prevent filesystem bloat or crashes.
