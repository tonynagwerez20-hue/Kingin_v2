#!/usr/bin/env python3
"""Update engine_state.json with a fresh timestamp and a sample ml_filter.
Run: python scripts/update_engine_state.py
"""
import json
import datetime
from pathlib import Path

p = Path('engine_state.json')
if not p.exists():
    print('engine_state.json not found')
    raise SystemExit(1)

with p.open('r', encoding='utf-8') as f:
    s = json.load(f)

s['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
# Add sample ml_filter output
s['ml_filter'] = {
    "confidence": 0.82,
    "threshold": 0.6,
    "decision": "TRADE",
    "features": {
        "ob_strength": 0.84,
        "fvg_present": True,
        "bos_aligned": True,
        "liquidity_swept": True,
        "adr_pct": 0.3,
        "pips_to_liquidity": 10.0,
        "session": "london",
        "htf_bias": 1
    }
}

with p.open('w', encoding='utf-8') as f:
    json.dump(s, f, indent=2)

print('engine_state.json updated with ml_filter')
