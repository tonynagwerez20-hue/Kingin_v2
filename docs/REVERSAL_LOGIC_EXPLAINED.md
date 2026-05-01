# How the System Handles Trend Reversals (Candlestick-Based)

## Current Architecture: Two Filters + One Trigger

Your system uses a **Triple-TF Hierarchical Alignment** protocol. Every entry must pass through a structural filter (H1), a strategic context filter (M15), and a high-precision trigger (M5).

---

## 1. The Triple-Layer System

### **Filter 1: H1 Bias** (Higher Timeframe Structure)
```python
# Analyzes swing highs/lows on H1 chart
bias = calculate_structure_bias("H1")  # Returns: "BULLISH", "BEARISH", or "NEUTRAL"
```

**What it detects**:
- **BULLISH**: Higher highs + higher lows (uptrend)
- **BEARISH**: Lower highs + lower lows (downtrend)
- **NEUTRAL**: Choppy/ranging market

**Reversal detection**: When H1 structure breaks (e.g., BULLISH → BEARISH)

---

### **Filter 2: M15 Zones** (Supply & Demand)
```python
# Detects institutional zones on M15 chart
zones = detect_supply_demand(m15_candles)
in_demand = zone["low"] <= price <= zone["high"]  # For longs
in_supply = zone["low"] <= price <= zone["high"]  # For shorts
```

**What it detects**:
- **Demand zones**: Areas where strong buying occurred (support)
- **Supply zones**: Areas where strong selling occurred (resistance)

**Reversal detection**: When price reaches opposite zone type
- In LONG → reaches supply zone = potential reversal
- In SHORT → reaches demand zone = potential reversal

---

### **Trigger: M5 Candlestick Patterns** (Entry/Exit Signal)
```python
# Recognizes 7 candlestick patterns on M5 chart
patterns = recognize_patterns(ltf_candles)

# Bullish patterns
- HAMMER
- BULLISH_ENGULFING  
- MORNING_STAR

# Bearish patterns
- SHOOTING_STAR
- BEARISH_ENGULFING
- EVENING_STAR

# Neutral
- DOJI (indecision)
```

**Reversal detection**: When pattern switches direction
- Bullish pattern → Bearish pattern = reversal signal
- Bearish pattern → Bullish pattern = reversal signal

---

## 2. How Reversals Are Detected

### **Scenario A: No Open Position** → Entry

All three must align:

```python
# Example: Uptrend reversal to downtrend
Filter 1 (H1): BEARISH bias ✓
Filter 2 (M15): Price in SUPPLY zone ✓  
Trigger (M5): SHOOTING_STAR pattern ✓

Result: Enter SHORT position
```

---

### **Scenario B: Open Position** → Exit or Reverse

The system checks **all three layers** against your current position:

```python
# Currently in LONG position
current_position = "LONG"

# Check each layer for reversal
exit_reasons = []

# A. Bias reversal?
if bias == "BEARISH":  # Was BULLISH, now BEARISH
    exit_reasons.append("Bias Reversal (H1)")

# B. Opposite zone reached?
if in_supply:  # Was in demand, now in supply
    exit_reasons.append("Opposite Zone Reached (Supply)")

# C. Trigger reversal?
if candlestick_signal == "SELL":  # Was BUY, now SELL
    exit_reasons.append("Trigger Reversal (Candlestick)")

# If ANY layer reverses → EXIT
if exit_reasons:
    action = "CLOSE_LONG"
```

**Key difference from orderflow**: System exits on **ANY** filter reversal, not just the trigger.

---

## 3. Real-World Example: LONG → SHORT Reversal

### Initial Setup (LONG Entry)
```
Time: 10:00 UTC
Price: 2640

Filter 1 (H1): BULLISH ✓
Filter 2 (M15): In DEMAND zone (2638-2642) ✓
Trigger (M5): BULLISH_ENGULFING ✓

Action: Enter LONG at 2640, SL at 2637
```

### Reversal Sequence

**10:30 UTC** - Price rises to 2650
```
Filter 1: Still BULLISH
Filter 2: Still in demand zone (trailing)
Trigger: No pattern
Action: Hold LONG (+10 pips profit)
```

**11:00 UTC** - Price reaches 2655 (supply zone)
```
Filter 1: Still BULLISH (lagging)
Filter 2: NOW IN SUPPLY ZONE ← REVERSAL DETECTED
Trigger: No pattern yet
Action: CLOSE_LONG at 2655 (+15 pips profit)
Reason: "Opposite Zone Reached (Supply)"
```

**11:05 UTC** - Bearish pattern forms
```
Filter 1: H1 breaks structure → BEARISH
Filter 2: In SUPPLY zone (2653-2657)
Trigger: SHOOTING_STAR pattern

Action: Enter SHORT at 2654, SL at 2658
Reason: "TRIPLE ENTRY: Bearish bias + Supply zone + Trigger confirmed"
```

---

## 4. Candlestick Pattern Details

### **Bullish Reversal Patterns**

#### HAMMER
```
      |
      |  ← Small body
    __|__
   |     |
   |     | ← Long lower wick (2x body)
   |_____|

Meaning: Sellers pushed down, buyers rejected strongly
```

#### BULLISH ENGULFING
```
Candle 1: ▼ (bearish)
Candle 2: ▲ (bullish, completely engulfs previous)

Meaning: Bulls overpowered bears
```

#### MORNING STAR
```
Candle 1: ▼ (large bearish)
Candle 2: - (small doji/indecision)
Candle 3: ▲ (large bullish)

Meaning: Trend exhaustion → reversal
```

---

### **Bearish Reversal Patterns**

#### SHOOTING STAR
```
   |_____|
   |     | ← Long upper wick (2x body)
   |     |
    __|__
      |  ← Small body
      |

Meaning: Buyers pushed up, sellers rejected strongly
```

#### BEARISH ENGULFING
```
Candle 1: ▲ (bullish)
Candle 2: ▼ (bearish, completely engulfs previous)

Meaning: Bears overpowered bulls
```

#### EVENING STAR
```
Candle 1: ▲ (large bullish)
Candle 2: - (small doji/indecision)
Candle 3: ▼ (large bearish)

Meaning: Trend exhaustion → reversal
```

---

## 5. Exit Logic (Triple Check)

The system is **conservative on exits** - it checks all three layers:

```python
# Exit triggers (ANY of these closes position)

1. Bias Reversal (H1)
   - LONG position + BEARISH bias = EXIT
   - SHORT position + BULLISH bias = EXIT

2. Opposite Zone (M15)
   - LONG position + reaches SUPPLY zone = EXIT
   - SHORT position + reaches DEMAND zone = EXIT

3. Trigger Reversal (M5)
   - LONG position + bearish pattern = EXIT
   - SHORT position + bullish pattern = EXIT
```

**Why this matters**: You can exit on zone alone, even if candlestick hasn't formed yet. This is **faster** than waiting for all three to align.

---

## 6. Entry Logic (Triple Confirmation)

The system is **strict on entries** - all three must align:

```python
# Entry requires ALL three

Filter 1 (H1 Bias):     BULLISH ✓
Filter 2 (M15 Zone):    In DEMAND ✓
Trigger (M5 Candle):    HAMMER ✓

→ Enter LONG

# If ANY filter fails, no entry
Filter 1: BULLISH ✓
Filter 2: In DEMAND ✓
Trigger: No pattern ✗

→ WAIT (logged as "Trigger not met")
```

---

## 7. Misalignment Protection

Even if all three generate signals, they must **agree on direction**:

```python
Filter 1: BULLISH → action = "LONG"
Filter 2: BULLISH → action = "LONG"  
Trigger:  BEARISH → action = "SHORT" ← MISMATCH!

Result: WAIT
Log: "Directions MISALIGNED - F1:LONG F2:LONG Trig:SHORT"
```

This prevents entering during choppy/conflicting conditions.

---

## 8. Comparison: Candlestick vs Orderflow

| Aspect | Candlestick (Current) | Orderflow (Alternative) |
|--------|----------------------|-------------------------|
| **Speed** | Slower (waits for candle close) | Faster (tick-by-tick) |
| **Reliability** | More visual, easier to verify | More institutional, harder to fake |
| **Data Required** | OHLC only | Volume delta required |
| **Reversal Detection** | Pattern-based (7 types) | Delta-based (FLIP/SURGE/TRANSITION) |
| **Exit Trigger** | ANY filter reversal | Configurable (strong/weak) |
| **False Signals** | Moderate (patterns can fail) | Lower (orderflow harder to manipulate) |

---

## 9. Configuration & Tuning

### Current Settings
```python
# In main_loop.py
alpha_strategies = [
    CandlestickStrategy(),  # Trigger
    FilterOne(),            # H1 Bias
    FilterTwo()             # M15 Zones
]

strategy_manager = StrategyManager(alpha_strategies)
```

### To Make More Aggressive
Add more patterns to `bullish_patterns` and `bearish_patterns`:
```python
# In candlestick_patterns.py
bullish_patterns = ["HAMMER", "BULLISH_ENGULFING", "MORNING_STAR", "DOJI"]  # Add DOJI
```

### To Make More Conservative
Require multiple patterns:
```python
# Modify get_candlestick_signal()
if len([p for p in patterns if p in bullish_patterns]) >= 2:  # Need 2+ patterns
    return "BUY"
```

---

## 10. Logging & Debugging

The system logs each filter check:

```
[Strategy] WAIT: Filter 1 (H1 Bias) not met
[Strategy] WAIT: Filter 2 (M15 Zone) not met  
[Strategy] WAIT: Trigger (M5 Candlestick) not met
[Strategy] WAIT: Directions MISALIGNED - F1:LONG F2:LONG Trig:SHORT
```

When all align:
```
[SIGNAL] LONG | TRIPLE ENTRY: Bullish bias + Demand zone + Trigger confirmed | Price: 2640 | Lots: 0.1
```

When exiting:
```
[SIGNAL] CLOSE_LONG | TRIPLE EXIT: Opposite Zone Reached (Supply), Trigger Reversal (Candlestick) | Price: 2655
```

---

## Summary

**Your candlestick-based system handles reversals through**:

1. ✅ **H1 Bias** - Detects higher timeframe structure breaks
2. ✅ **M15 Zones** - Detects when price reaches opposite zone type
3. ✅ **M5 Patterns** - Detects 7 reversal candlestick patterns
4. ✅ **Triple Exit Logic** - Exits on ANY filter reversal (conservative)
5. ✅ **Triple Entry Logic** - Enters only when ALL filters align (strict)
6. ✅ **Misalignment Protection** - Blocks entries when filters disagree

**Key Advantage**: Visual, easy to verify, works with standard OHLC data.

**Trade-off**: Slightly slower than orderflow (waits for candle close), but more accessible and easier to backtest.
