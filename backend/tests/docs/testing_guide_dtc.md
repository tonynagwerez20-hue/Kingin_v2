# Testing Guide: DTC Protocol & Signal Generation

This guide outlines how to verify the end-to-end trading flow using the Sierra Chart DTC Protocol integration.

## 1. Verify DTC Connectivity ( Sierra Chart -> Python )
Before testing signals, ensure Python is successfully receiving tick data from Sierra Chart.

1.  **Configure `.env`**: Set `DATA_SOURCE_TYPE=DTC`.
2.  **Enable DTC in Sierra**: In Sierra Chart, go to `Global Settings` -> `DTC Service Settings`.
    -   Ensure "Enable DTC Server" is checked.
    -   Server Port should be `11099` (or match your `.env`).
3.  **Run Data Feed Server**: Run `python data_feed/server.py`.
4.  **Check Logs**: Look for:
    -   `[DTC] Connected to localhost:11099`
    -   `[DTC] Logon Successful`
    -   `[DTC] Received Tick: ...` (after subscribing to a symbol)

## 2. Verify Buffer Population
Verify that the `TimeframeEngine` is correctly aggregating data into the 5M, 15M, and H1 buffers.

1.  **Run Diagnostics**: Use the comprehensive health check:
    ```bash
    python tests/diag_system_health.py
    ```
2.  **Validation**:
    -   Buffers should show **500 candles**.
    -   OHLC values should match your Sierra Chart charts.
    -   Delta values should be populated (either via DTC or CSV fallback).

## 3. Verify Signal Generation ( Strategy -> EA )
To test if signals are actually generated and sent to MT5 without waiting for a real market setup, you can use the **Strategy Simulator**.

1.  **Run Signal Test Script**:
    ```bash
    python tests/test_strategy_signal.py
    ```
2.  **Monitor MT5 Experts Tab**:
    -   You should see `[INFO] Processing signal: {"action":"LONG", ...}`.
    -   If a trade is executed, it will show `OrderSend successful`.

## 4. End-to-End Live Test
1.  **Start MT5**: Load `HedgeEA` on an XAUUSD chart. Ensure "Allow DLL imports" is ON.
2.  **Start System**: Run `UNIVERSAL_CONTROL.bat`.
3.  **Observe Dashboard**: 
    -   **React**: Open `http://localhost:3000` (Professional view)
    -   **Streamlit**: Open `http://localhost:8501` (Analytical view)
4.  **Wait for Signal**: When the H1 Bias, M15 Zone, and M5 Delta align, a signal will be broadcasted to MT5 via ZMQ.

---

### Troubleshooting
-   **No DTC Connection?** Check firewall settings for port 11099.
-   **EA says "Unknown Request"?** Ensure you recompiled the `.mq5` file as per previous instructions.
-   **Buffer empty?** Ensure Sierra Chart has enough historical data loaded for the requested symbol.

