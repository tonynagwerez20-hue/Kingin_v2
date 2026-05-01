# Master Strategy & Technical Specification v6.0

## 1. Core Architecture: Triple-TF Hierarchical Alignment
The system follows a strict "H1 Bias -> M15 Context -> M5 Execution" protocol. No layer may be skipped.

### A. V1 Filtration System (IGOF Upgrade)
The core logic has been upgraded to a 6-layer Integrated Gold Order Flow (IGOF) engine:
1.  **Macro Auction**: Weekly/Daily Profile location relative to Value Area (VA) and POC.
2.  **Liquidity Heatmap**: Rejection of trades into low-liquidity zones.
3.  **Correlation (Inter-market)**: Real-time alignment with DXY (Inverse), US10Y (Inverse), and SPX (Correlated).
4.  **H1 Structural Bias**: Market Structure Shift (MSS) and EMA Cloud trend definition.
5.  **M15 Zone Context**: Supply/Demand zone validation.
6.  **M5 Trigger**: Orderflow Delta Surge + Candlestick Pattern confirmation.

### B. Trigger Layer: LTF Execution (M5)
- **Timeframe**: M5 (5-Minute)
- **Function**: Precision entry and risk management.
- **Logic**: Uses Candlestick Patterns and Orderflow Delta.
- **Rule**: Entry signal must pass ALL 6 IGOF layers.

## 2. Technical Optimization: ZMQ Pipeline
To maintain sub-second execution speeds, the system utilizes an optimized ZeroMQ tunnel.

### A. Latency Management (CONFLATE)
- **Option**: `zmq.CONFLATE` is enabled on the market data SUB socket.
- **Result**: Eliminates buffer bloat by discarding stale messages, ensuring the strategy engine always processes the latest price tick.
- **Target**: 0ms queue latency.

### B. Signal Execution
- **Pattern**: PUB/SUB for signals, REQ/REP for execution acknowledgments.
- **Ports**: 
    - 5555: PUB (Signals to EA)
    - 5557: REQ (Command/Balance Sync with EA)
    - 5556: SUB (DTC/Sierra Market Data)

## 3. Risk & Validation
- **Global Kill Switch**: Monitored via `risk_state.json`.
- **Slippage Tolerance**: Dynamic spread audits via `CRO_Rules`.
- **Audit Logging**: Every decision (PASS, VETO, EXIT) is logged with a JSON context for post-trade analysis.
