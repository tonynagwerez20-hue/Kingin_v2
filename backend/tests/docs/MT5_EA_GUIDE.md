# MT5 Expert Advisor Guide

## Overview
The **HedgeEA** is a MetaTrader 5 Expert Advisor that receives trading signals from the Python Hedge Trading System via ZeroMQ and executes them with **dynamic exits** and **trailing stop loss** protection.

**Key Features:**
- ✅ **Zero dependencies** (No mql-zmq include library required)
- ✅ **Dynamic exits** based on delta reversals (no fixed TP)
- ✅ **Automatic reversal trades** when criteria align
- ✅ **Trailing stop loss** for profit protection
- ✅ **Direct DLL integration** (Fast and compatible)

---

## Installation

### 1. Requirements

The EA uses **direct DLL calls**. You only need two files:
1. `libzmq.dll`
2. `libsodium.dll`

**Download DLLs from**: [mql-zmq releases](https://github.com/dingmaotu/mql-zmq/releases) (Look for MT5 DLLs).

### 2. Installation Steps

1. **Copy DLLs**: Place `libzmq.dll` and `libsodium.dll` into your MT5 `MQL5/Libraries/` folder.
2. **Copy the EA**: Place `HedgeEA.mq5` into your MT5 `MQL5/Experts/` folder.
3. **Compile**:
   - Open MetaEditor (F4).
   - Find `HedgeEA.mq5` in the Navigator.
   - Press **F7** to compile.
   - **Note**: You do NOT need any additional `.mqh` files or the `Include/Zmq` folder.

**Find MT5 Data Folder:** File → Open Data Folder → Navigate to `MQL5/`

---

## Configuration

### Input Parameters

#### ZeroMQ Settings
- **ZMQ_HOST**: `localhost` (server address)
- **ZMQ_PORT**: `5555` (server port)
- **ZMQ_TOPIC**: `SIGNAL` (signal topic)

#### Risk Management
- **MAX_LOT_SIZE**: `1.0` (maximum lot size per trade)
- **MAX_OPEN_POSITIONS**: `1` (max concurrent positions - set to 1 for dynamic exits)
- **MAX_DAILY_DRAWDOWN_PCT**: `2.5` (daily drawdown limit %)

#### Trailing Stop Loss
- **ENABLE_TRAILING_SL**: `true` (enable/disable trailing SL)
- **TRAILING_STOP_PIPS**: `20.0` (distance from current price in pips)
- **TRAILING_STEP_PIPS**: `5.0` (minimum price movement to update SL)

#### Execution Settings
- **SLIPPAGE_POINTS**: `10` (maximum slippage)
- **MAGIC_NUMBER**: `123456` (unique identifier)
- **TRADE_COMMENT**: `HedgeEA` (trade comment)
- **REVERSAL_DELAY_MS**: `500` (delay between close and reversal)

#### Logging
- **LOG_LEVEL**: `INFO` (DEBUG, INFO, WARNING, ERROR)
- **ENABLE_FILE_LOG**: `false` (save logs to file)

---

## Usage

### 1. Start Python System

1.  **Open Terminal**: Navigate to the project root.
2.  **Run Setup** (New machines only): Run `SETUP_PROJECT.bat` to install global dependencies.
3.  **Run Master Script**: Run `START_ALL.bat`.

The system will automatically initialize the Data Server and the Strategy Engine. Look for the "v6.1 Breadcrumb" in the console.

### 2. Attach EA to Chart

1. Open XAUUSD chart in MT5
2. Drag **HedgeEA** from Navigator → Expert Advisors onto chart
3. Configure parameters
4. **Enable "Allow DLL imports"** (required!)
5. Click OK

### 3. Verify Connection

Check Experts log (View → Toolbox → Experts):

```
=== HedgeEA Initialization ===
[INFO] HedgeEA initialized successfully
[INFO] Listening on localhost:5555 for topic 'SIGNAL'
[INFO] Risk Limits: MaxLots=1.00, MaxPositions=1, MaxDD=2.5%
```

---

## Signal Types

The EA handles **6 signal types**:

### Entry Signals
- **LONG**: Open buy position
- **SHORT**: Open sell position

### Exit Signals
- **CLOSE_LONG**: Close existing long position
- **CLOSE_SHORT**: Close existing short position

### Reversal Signals
- **REVERSE_TO_LONG**: Close short + open long
- **REVERSE_TO_SHORT**: Close long + open short

### Signal Format (JSON)

```json
{
  "action": "LONG",
  "symbol": "XAUUSD",
  "price": 2045.50,
  "sl": 2043.50,
  "lots": 0.05,
  "bias": "BULLISH",
  "timestamp": 1702800000
}
```

**Required**: `action`, `symbol`, `price`, `sl`, `lots`  
**Optional**: `bias`, `timestamp`, `desc`

---

## Dynamic Exit Strategy

### How It Works

1. **Position Opens**: Python sends LONG/SHORT signal
2. **EA Monitors**: Tracks position, updates trailing SL
3. **Delta Reverses**: Python detects reversal
4. **Exit Decision**:
   - If reversal criteria met → Send REVERSE signal
   - Otherwise → Send CLOSE signal
5. **EA Executes**: Closes position (and opens reversal if applicable)

### Exit Triggers

Positions can close via:
1. **Delta Reversal**: Python detects opposite delta signal
2. **Trailing SL Hit**: Price retraces and hits trailing stop
3. **Initial SL Hit**: Price moves against position
4. **Manual Close**: User closes position manually

---

## Trailing Stop Loss

### Configuration

**ENABLE_TRAILING_SL = true**
- `TRAILING_STOP_PIPS = 20`: SL trails 20 pips behind price
- `TRAILING_STEP_PIPS = 5`: Updates when price moves 5 pips

### Behavior

**LONG Position:**
- SL trails **below** current price
- Updates when price moves **up** by step amount
- Never moves SL **above** entry (keeps profitable)

**SHORT Position:**
- SL trails **above** current price
- Updates when price moves **down** by step amount
- Never moves SL **below** entry (keeps profitable)

### Example

```
LONG @ 2045.00, Initial SL: 2043.00
Price → 2050.00: SL updates to 2030.00 (2050 - 20 pips)
Price → 2055.00: SL updates to 2035.00 (2055 - 20 pips)
Price → 2052.00: SL stays at 2035.00 (not enough movement)
Price → 2035.00: Position closes at SL (locked 35 pips profit)
```

### Tuning Tips

- **Tight trailing** (10-15 pips): Quick profit protection, may exit early
- **Loose trailing** (30-50 pips): Gives trades room, captures bigger moves
- **Larger step** (10+ pips): Reduces SL update frequency
- **Disable**: Set `ENABLE_TRAILING_SL = false`

---

## Risk Management

### 1. Lot Size Validation
- Checks broker min/max
- Enforces `MAX_LOT_SIZE`
- Normalizes to broker step

### 2. Position Limit
- Counts positions by magic number
- Rejects if `MAX_OPEN_POSITIONS` exceeded
- Recommended: Set to `1` for dynamic exits

### 3. Daily Drawdown Protection
- Tracks daily P&L (closed + open)
- Stops trading if loss > `MAX_DAILY_DRAWDOWN_PCT`
- Resets at midnight server time

### 4. Symbol Validation
- Verifies symbol exists and is tradable
- Checks symbol matches chart

---

## Monitoring

### Logs

**Experts Log** (View → Toolbox → Experts):

```
[INFO] Processing signal: {"action":"LONG","symbol":"XAUUSD",...}
[INFO] Trade executed: LONG 0.05 lots at 2045.50, SL: 2043.50, Ticket: 123456
[DEBUG] Trailing SL updated: Ticket 123456, New SL: 2047.50
[INFO] Position closed: Ticket 123456 at 2050.00
```

### Trade Tracking

All EA trades have:
- Magic number: `123456` (default)
- Comment: `HedgeEA`
- Visible in Terminal → Trade tab

---

## Troubleshooting

### EA Not Receiving Signals

**Check:**
1. Python system running: `python start_system.py`
2. Bridge active (check Python console)
3. EA initialized (check Experts log)
4. Port 5555 not blocked
5. "Allow DLL imports" enabled

**Test:**
```python
python tests/test_mt5_signals.py
```

### Signals Rejected

**Common reasons:**
- Symbol mismatch
- Lot size exceeds `MAX_LOT_SIZE`
- `MAX_OPEN_POSITIONS` reached
- Daily drawdown limit hit
- Invalid signal format

**Check Experts log for specific error.**

### Trailing SL Not Working

**Check:**
1. `ENABLE_TRAILING_SL = true`
2. Position is profitable (SL won't move past entry)
3. Price moved by `TRAILING_STEP_PIPS`
4. Check DEBUG logs for SL updates

### Compilation Errors

**"Cannot load library":**
- Copy `libzmq.dll` and `libsodium.dll` to `MQL5/Libraries/`.
- Enable "Allow DLL imports" in EA settings.

**"undeclared identifier/type mismatch":**
- Ensure you are using **HedgeEA v2.01** or later.
- Older versions required the mql-zmq include library; v2.01+ uses direct DLL calls.

**"as - unexpected token":**
- Some MT5 builds don't support the `as` keyword for aliasing. Use the latest version of the EA which uses overloaded wrapper functions instead.

---

## Advanced Configuration

### Disable Trailing SL

```mql5
ENABLE_TRAILING_SL = false
```

Positions will only close via:
- Delta reversal signals
- Initial SL hit

### Adjust Trailing Sensitivity

**Tighter trailing:**
```mql5
TRAILING_STOP_PIPS = 10.0
TRAILING_STEP_PIPS = 3.0
```

**Looser trailing:**
```mql5
TRAILING_STOP_PIPS = 40.0
TRAILING_STEP_PIPS = 10.0
```

### Multiple Symbols

1. Attach EA to each symbol's chart
2. Use different `MAGIC_NUMBER` per symbol
3. Adjust `MAX_OPEN_POSITIONS` accordingly

### File Logging

```mql5
ENABLE_FILE_LOG = true
```

Logs saved to: `<MT5_DATA_FOLDER>/MQL5/Files/HedgeEA_<DATE>.log`

---

## Integration with Python

### Signal Flow

```
Python Engine → Bridge (Port 5555) → MT5 EA → Execution
```

### Components

**Python** (`Engine/main_loop.py`):
- Analyzes data (bias, zones, delta)
- Detects delta reversals
- Generates signals (entry/exit/reversal)
- Sends via ZeroMQ

**Bridge** (`Engine/bridge.py`):
- PUB socket on port 5555
- Topic: "SIGNAL"

**MT5 EA** (`HedgeEA.mq5`):
- SUB socket
- Validates signals
- Executes trades
- Manages trailing SL

---

## Performance

- **Non-Blocking**: ZeroMQ receive doesn't freeze MT5
- **Efficient**: Trailing SL updates only on tick
- **Lightweight**: No historical data storage
- **Reconnection**: Auto-reconnects if bridge restarts

---

## Safety Features

1. **Dual Risk Validation**: Python + MT5
2. **Symbol Verification**: Only trades chart symbol
3. **Broker Compliance**: Respects lot limits
4. **Daily Reset**: Drawdown tracking resets daily
5. **Emergency Stop**: Stops on daily loss limit
6. **Profit Protection**: Trailing SL locks gains

---

## Version History

**v2.01** (2025-12-20)
- Migrated to direct ZMQ DLL calls.
- Removed dependency on `mql-zmq` include library.
- Fixed compatibility with all MT5 builds.

**v2.0** (2025-12-19)
- Added dynamic exit strategy
- Added trailing stop loss
- Handles 6 signal types
- Removed fixed TP
- Position tracking

**v1.0** (Initial)
- ZeroMQ signal reception
- Basic risk management
- Entry signals only
