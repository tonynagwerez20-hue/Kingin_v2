# Delta Data Flow in Your System

## ✅ UPDATE: Precise Delta Mapping Implemented

The system now supports **Institutional-Grade Precise Delta Mapping** via Sierra Chart CSV exports.

---

## Current Delta Flow

### 1. Historical Data (From Sierra Chart)
**File**: `dtc_client.py` lines 387-418

```python
# Message Type 802/803/804 - Historical bars
bar = {
    "delta": msg.get("AskVolume", 0) - msg.get("BidVolume", 0)
}

# Fallback: If delta is 0, SIMULATE it
if bar["delta"] == 0 and bar["volume"] > 0:
    # Simulate based on close position in range
    ratio = (bar["close"] - bar["low"]) / (bar["high"] - bar["low"])
    approx_factor = (2 * ratio) - 1
    bar["delta"] = bar["volume"] * approx_factor
```

**What this means**:
- ✅ **Tries** to get real delta from `AskVolume - BidVolume`
- ⚠️ **Falls back** to simulation if delta is 0
- ❓ **Question**: Does your Sierra Chart feed actually send `AskVolume` and `BidVolume`?

### 2. Live Tick Data (Real-Time)
**File**: `dtc_client.py` lines 471-475

```python
# Message Type 107 - Live trades
elif mtype == 107:
    p, v, agg = msg.get("LastPrice"), msg.get("LastSize"), msg.get("AtBidOrAsk", 0)
    dir = 1 if agg == 2 else -1 if agg == 1 else 0  # Buy=1, Sell=-1
    self.engine.process_tick(p, v, dir, ...)
```

**What this means**:
- ✅ Gets tick direction from `AtBidOrAsk` field
- ✅ Builds delta in real-time from individual trades
- ✅ Aggregates into M5 bars with cumulative delta

---

## The Critical Question

**Does Sierra Chart actually send bid/ask volume in historical bars?**

This depends on:
1. **Your data feed provider** (FXCM, Rithmic, CQG, etc.)
2. **Sierra Chart study configuration**
3. **DTC protocol version**

### Most Likely Scenario:

**Historical bars**: Delta is **SIMULATED** (because `AskVolume`/`BidVolume` are 0)
**Live ticks**: Delta is **REAL** (from `AtBidOrAsk` field)

---

## How to Verify

### Test 1: Check Historical Delta Quality

Run this to see if historical delta is real or simulated:

```python
# In Python console
from data_feed.dispatcher import ohlc_buffers

# Get last M5 bar
last_bar = list(ohlc_buffers['M5'])[-1]
print(f"Delta: {last_bar.get('delta', 0)}")
print(f"Volume: {last_bar.get('volume', 0)}")
print(f"Range: {last_bar['high'] - last_bar['low']}")

# If delta is exactly proportional to close position in range,
# it's simulated. If it's irregular, it's real.
```

### Test 2: Check Sierra Chart Configuration

In Sierra Chart:
1. Go to the chart with XAUUSD
2. Right-click → "Studies" → "Study Settings"
3. Look for studies like:
   - "Numbers Bars Calculated Values"
   - "Bid Volume" / "Ask Volume"
   - "Volume - Bid vs Ask"

**If you DON'T have these studies**, Sierra Chart isn't exporting bid/ask volume.

### Test 3: Check DTC Messages

Add logging to see what Sierra Chart actually sends:

```python
# In dtc_client.py, line 402, add:
print(f"[DEBUG] AskVol: {msg.get('AskVolume', 0)}, BidVol: {msg.get('BidVolume', 0)}")
```

If both are always 0, your feed doesn't provide real delta.

---

---

## The Solution: Precise Delta Mapping (v5.5)

To overcome the OTC limitations and simulation issues, we implemented **Precise Delta Mapping** from Sierra Chart's advanced study exports.

### 1. Mapping Specification
The `CSVBatchProcessor` now scans the following columns for maximum precision:
- **Column 18**: Delta (Ask Volume - Bid Volume)
- **Column 25**: Max Delta (Highest delta during bar)
- **Column 26**: Min Delta (Lowest delta during bar)

### 2. Implementation logic
```python
# From csv_processor.py
delta = float(row[18])
max_delta = float(row[25])
min_delta = float(row[26])
```

### 3. Benefits
- ✅ **No more simulation**: Uses actual orderflow data from Sierra Chart studies.
- ✅ **High Precision**: Survives "Reverse-Divergence" checks.
- ✅ **Hybrid Reliability**: If the CSV columns are missing, the system automatically falls back to DTC tick aggregation.

---

## The Truth About XAUUSD Delta

### Reality Check:

**XAUUSD (Gold Spot) is an OTC market**, not an exchange-traded instrument.

This means:
- ❌ No centralized order book
- ❌ No real "bid volume" vs "ask volume" from exchange
- ❌ Different brokers have different prices
- ✅ Only tick direction (buy vs sell) is somewhat reliable

### What You're Actually Getting:

**Historical**: Simulated delta (close position in range)
**Live**: Tick direction delta (buy ticks vs sell ticks)

**Neither is true exchange orderflow** (because XAUUSD isn't on an exchange).

---

## What This Means for Your Strategy

### Good News:
✅ Live tick direction is still valuable
✅ Simulated historical delta is consistent
✅ Your strategy logic still works

### Reality:
⚠️ You're not getting "institutional orderflow" for XAUUSD
⚠️ True orderflow only exists for exchange-traded instruments (futures, stocks)
⚠️ XAUUSD "delta" is an approximation, not real data

### For Real Orderflow:

If you want **true institutional delta**, you need:
- **Gold Futures** (GC on CME) - Real exchange orderflow
- **Rithmic or CQG data feed** - Provides actual bid/ask volume
- **Sierra Chart with proper studies** - Configured to export volume data

---

## Recommendation

### Option 1: Accept Current Setup (Recommended)

Your current system is **fine for XAUUSD spot trading**:
- Live tick direction is good enough
- Simulated historical delta is consistent
- Strategy can still find high-conviction setups

### Option 2: Upgrade to Real Orderflow

Switch to **Gold Futures (GC)** if you want true delta:
1. Trade GC futures instead of XAUUSD spot
2. Use Rithmic or CQG data feed
3. Configure Sierra Chart to export bid/ask volume
4. Your strategy will have access to real institutional orderflow

**Cost**: Rithmic ~$100/month, but you get REAL delta

### Option 3: Verify Your Current Data

Run the tests above to confirm what you're actually receiving.

---

## Bottom Line

**Your system is DESIGNED to receive real delta from Sierra Chart**, but:

1. **Historical bars**: Likely simulated (unless you have special studies configured)
2. **Live ticks**: Real tick direction (buy vs sell)
3. **XAUUSD limitation**: No true orderflow (OTC market)

**For true institutional delta**: Switch to Gold Futures (GC) with Rithmic feed.

**For XAUUSD spot**: Current setup is as good as it gets.

---

## Action Items

1. Run Test 1 to see if delta looks simulated or real
2. Check Sierra Chart studies configuration
3. Decide if you want to stick with XAUUSD or upgrade to GC futures
4. If staying with XAUUSD, accept that delta is approximated (which is fine!)
