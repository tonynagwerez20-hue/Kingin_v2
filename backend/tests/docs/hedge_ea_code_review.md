# HedgeEA.mq5 Code Review
**Version:** 2.01
**Date:** 2026-01-09
**Review Status:** ✅ **PASSED** (With Minor Recommendations)

## 1. Architecture & Connectivity
The EA uses a **Direct DLL Binding** (`libzmq.dll`) to establish a ZeroMQ Subscriber (`SUB`) and Replier (`REP`) socket.
-   **Integration**: Correctly implements the Request/Reply pattern for heartbeats and the Pub/Sub pattern for signals.
-   **Non-Blocking**: Uses `ZMQ_DONTWAIT` flags for receiving data, ensuring the MT5 terminal UI does not freeze during high-frequency execution.
-   **Lifecycle**: Proper Context creation in `OnInit` and destruction in `OnDeinit`.

## 2. Risk Management
The EA implements robust on-board risk checks that operate *independently* of the Python engine (Safety Net):
-   **Daily Drawdown**: `GetDailyPnL()` correctly sums closed trades for the day + floating P&L. If `dailyPnL < -MAX_DAILY_DRAWDOWN_PCT`, new signals are rejected.
-   **Max Positions**: `CountOpenPositions()` enforces a hard limit (Default: 1).
-   **Lot Normalization**: `NormalizeLots()` ensures all orders comply with broker-specific step and min/max limits.

## 3. Execution Logic
-   **Order Type**: Uses `ORDER_FILLING_IOC` (Immediate or Cancel), which is standard for ECN/STP execution but might need to be `ORDER_FILLING_FOK` for some rigid brokers.
-   **Trailing Stop**: The `UpdateTrailingStops` function (Lines 767-858) includes logic to:
    -   Only move Stop Loss in the favorable direction (never widens risk).
    -   Ensure SL doesn't cross the Entry Price negatively (breakeven protection).
    -   This is a solid implementation.

## 4. Signal Handling
-   **Commands**: Supports `LONG`, `SHORT`, `CLOSE`, and `REVERSE`.
-   **JSON Parsing**: Custom `ExtractStringValue`/`ExtractDoubleValue` functions are used.
    -   *Note*: These are lightweight but fragile. They rely on specific formatting (e.g., matching `"key":value`). Ensure the Python sender uses standard `json.dumps()` without exotic formatting.
-   **Getters**: `GET_POSITIONS` and `GET_HISTORY` are fully implemented, enabling the Python dashboard to visualize MT5 state directly.

## 5. Deployment Recommendations
1.  **Compilation**: You **MUST** compile this source code (`.mq5`) to generate the executable (`.ex5`). The current `.ex5` may be outdated.
2.  **DLL Permissions**: Ensure "Allow DLL imports" is checked in MT5 Settings.
3.  **Filenames**: Ensure `libzmq.dll` and `libsodium.dll` are in logic paths (usually `MQL5/Libraries` or root MT5 directory depending on system).

## 6. Code Quality Rating
-   **Structure**: ⭐⭐⭐⭐⭐ (Clean, modular functions)
-   **Safety**: ⭐⭐⭐⭐⭐ (Explicit risk checks)
-   **robustness**: ⭐⭐⭐⭐ (JSON parsing is the only weak point, but efficient for this use case)

**Conclusion**: The code is production-ready.
