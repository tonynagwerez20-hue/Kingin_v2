"""
Test script to generate sample signals for dashboard verification.
Run this to populate the audit log with test data.
"""
import json
import time
from pathlib import Path

# Ensure storage directory exists
log_path = Path("storage/logs/audit.json")
log_path.parent.mkdir(parents=True, exist_ok=True)

# Sample signals
test_signals = [
    {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "module": "STRATEGY",
        "event": "SIGNAL_GENERATED",
        "metadata": {
            "signal": {
                "action": "LONG",
                "symbol": "XAUUSD",
                "price": 2045.50,
                "sl": 2042.00,
                "lots": 0.05,
                "sl_pips": 35.0,
                "desc": "LEGACY CONFLUENCE: FilterOne: Bullish Structure confirmed + FilterTwo: Demand Zone @ 2044.00 confirmed by TRIGGER"
            }
        }
    },
    {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 300)),
        "module": "CRO",
        "event": "PASS",
        "metadata": {
            "signal": {
                "action": "LONG",
                "symbol": "XAUUSD",
                "price": 2045.50,
                "sl": 2042.00,
                "lots": 0.05
            }
        }
    },
    {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 600)),
        "module": "STRATEGY",
        "event": "SIGNAL_GENERATED",
        "metadata": {
            "signal": {
                "action": "SHORT",
                "symbol": "XAUUSD",
                "price": 2050.20,
                "sl": 2053.00,
                "lots": 0.10,
                "sl_pips": 28.0,
                "desc": "LEGACY CONFLUENCE: FilterOne: Bearish Structure confirmed + FilterTwo: Supply Zone @ 2051.00 confirmed by TRIGGER"
            }
        }
    },
    {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 700)),
        "module": "CRO",
        "event": "RISK_VETO",
        "metadata": {
            "signal": {
                "action": "SHORT",
                "symbol": "XAUUSD",
                "price": 2050.20,
                "sl": 2053.00,
                "lots": 0.10
            },
            "reason": "Spread too high: 4.2 > 3.0"
        }
    }
]

# Write to file
with open(log_path, "w") as f:
    json.dump(test_signals, f, indent=4)

print(f"✅ Generated {len(test_signals)} test signals")
print(f"📂 Saved to: {log_path.absolute()}")
print("\n🔄 Refresh the Signal Intelligence page in your dashboard to see them!")
