# Trading on MT5 - Simplified Setup Guide

## ✅ Good News!

If you're **executing trades on MT5** (not Sierra Chart), you can **ignore the NTP Error 1314**. 

Sierra Chart is only used for **data feed** in your system. The NTP sync error won't affect:
- ✅ Market data reception
- ✅ Trade execution (handled by MT5)
- ✅ Dashboard updates
- ✅ Strategy signals

---

## What You Actually Need

### 1. Sierra Chart (Data Feed Only)

**Purpose**: Receive real-time market data via DTC protocol

**What's Required**:
- ✅ DTC Protocol Server enabled
- ✅ Connection to data feed (ports 11099, 11098)
- ❌ **NOT required**: Administrator rights
- ❌ **NOT required**: NTP sync
- ❌ **NOT required**: Trading enabled in Sierra Chart

**Why NTP Error is OK**:
- NTP sync only matters if Sierra Chart is sending orders to a broker
- Since you're using MT5 for execution, Sierra Chart just needs to receive data
- Data timestamps come from the feed server, not your local clock

---

### 2. MetaTrader 5 (Trade Execution)

**Purpose**: Execute all buy/sell orders

**What's Required**:
- ✅ Algo Trading enabled (green button)
- ✅ DLL imports allowed
- ✅ ZMQ Bridge EA running (smiley face 🙂)
- ✅ Connected to broker account

**This is your critical component for trading!**

---

## Simplified Startup (MT5 Execution Mode)

### Step 1: Start MetaTrader 5
```
1. Open MT5
2. Enable "Algo Trading" (green)
3. Connect to your Demo Account
```

### Step 2: Start The System (One-Click)
We have unified the startup sequence for maximum convenience.

1. Double-click the **`START_ALL.bat`** file in the project directory.

This script will automatically:
1. Turn the Master Switch **ON**.
2. Launch the **Data Feed Server** securely in the background.
3. Launch the **Professional CLI Dashboard** in your current window.
4. Begin acquiring Multi-Timeframe (MTF) Data and polling for signals.

---

## How It Works

```
MT5 Broker Data → Python Engine (MTF Analysis) 
     ↓                      ↓
 CLI Dashboard      Dynamic Risk Checks
     ↓                      ↓
 MT5 (Execution) ←- Validated Signals
```

**Data Flow**:
1. Python engine queries MT5 for H4, H1, M15, M5, and M1 data.
2. The `IGOFEngine` processes the data through 6 institutional layers.
3. The `UltraLowAccountRiskRule` verifies the trade against the $7.50 equity floor and dynamic scaling parameters.
4. Dashboard shows pipeline and account metrics in real-time.
5. ZMQ Bridge (if attached) handles execution based on the generated signal.

---

## Pre-Flight Checklist for Forward Testing

Before running `START_ALL.bat`, verify:

| Check | Expected |
|-------|----------|
| MetaTrader 5 open | Yes |
| Algo Trading button | Green |
| Account Balance | $10.00 |
| Equity Floor (config) | $7.50 |
| Lot Size (enforced) | 0.01 |
| Master Switch | Will be set ON by script |

> [!NOTE]
> Run `python verify_mt5_connection.py` to quickly confirm your MT5 connection is active before starting.


## What Actually Matters for Trading

| Component | Status Needed | Why |
|-----------|--------------|-----|
| **Sierra Chart DTC** | Connected | Provides market data |
| **MT5 Bridge** | Connected | Executes your trades |
| **MT5 Algo Trading** | Enabled | Allows EA to run |
| **Python Engine** | Running | Generates signals |

**Not Critical**:
- ❌ Sierra Chart admin rights
- ❌ NTP sync
- ❌ Sierra Chart trading enabled
- ❌ Windows Firewall (if using localhost)

---

## Troubleshooting

### "Still seeing Error 1314 in logs"
**Answer**: Ignore it! It doesn't affect data reception or MT5 execution.

### "Want to remove the error message"
**Answer**: Use Option A or B above to stop the NTP sync attempts.

### "Data not flowing to Python"
**Check**:
1. Sierra Chart shows "Conn" (connected to feed)
2. DTC server is listening on port 11099
3. Python shows `[DTC] LIVE Logon Success`

### "Trades not executing"
**Check**:
1. MT5 Algo Trading is GREEN
2. EA shows smiley face 🙂
3. Python shows `✅ [Pre-Flight] MT5 Bridge: CONNECTED`

---

## Summary

For **MT5 execution mode**:
- ✅ Sierra Chart: Just needs to receive data (no admin rights needed)
- ✅ MT5: Handles all trade execution (this is critical)
- ✅ Python: Connects both and runs strategy

**You can safely ignore Error 1314** - it won't affect your trading!
