"""
toggle_system.py
Usage:
    python toggle_system.py ON
    python toggle_system.py OFF

Reads / writes config/trading_params_lite.json and engine_state.json.
Safe against missing files, empty files, and missing keys.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR    = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "trading_params_lite.json"
STATE_PATH  = BASE_DIR / "engine_state.json"


def _load_json_safe(path: Path, default: dict) -> dict:
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def _default_config(switch: bool) -> dict:
    return {
        "trading": {
            "master_switch": switch,
            "symbol": "XAUUSD",
            "lot_size": 0.01,
            "max_open_trades": 1,
            "risk_percent": 1.0,
            "execution_type": "MARKET",
            "sl_buffer_pips": 2.0,
            "tp_multiplier": 2.0
        },
        "dashboard": {
            "enable_streamlit_dashboard": False,
            "enable_react_dashboard": False
        },
        "enable_streamlit_dashboard": False,
        "enable_react_dashboard": False,
        "filters": {
            "killzone_filter": True,
            "news_filter": True,
            "session": "london_new_york"
        },
        "layers": {
            "KillzoneFilterLayer": True,
            "MechanicalStructureLayer": True,
            "LiquiditySweepLayer": True,
            "DisplacementLayer": True,
            "FVGDiscountLayer": True,
            "MicroMSSLayer": True,
            "NewsEventLayer": True
        },
        "confluence": {
            "min_score": 5.0,
            "max_score": 7.0
        }
    }


def _default_state(switch: bool) -> dict:
    return {
        "master_switch": switch,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "bias": "NEUTRAL",
        "current_price": 0.0,
        "signal_action": "NONE",
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "lot_size": 0.01,
        "execution_type": "MARKET",
        "confluence_score": 0.0,
        "killzone_name": "",
        "session_time": "",
        "rr_ratio": "-",
        "layers": [],
        "last_trade": {},
        "account_equity": 0.0,
        "account_balance": 0.0,
        "floating_pnl": 0.0,
        "open_trades_count": 0,
        "open_positions": [],
        "active_warnings": []
    }


def toggle_system(force_state: str = None):
    if force_state == "ON":
        switch = True
    elif force_state == "OFF":
        switch = False
    else:
        print("Usage: python toggle_system.py ON|OFF")
        sys.exit(1)

    label = "ON" if switch else "OFF"

    # ── 1. Update primary config ──────────────────────────────────────────────
    config = _load_json_safe(CONFIG_PATH, _default_config(switch))

    # Ensure nested "trading" key exists
    if "trading" not in config or not isinstance(config["trading"], dict):
        config["trading"] = _default_config(switch)["trading"]

    config["trading"]["master_switch"] = switch

    try:
        _save_json(CONFIG_PATH, config)
    except OSError as e:
        print(f"[ERROR] Failed to write config: {e}")
        sys.exit(1)

    # ── 2. Update engine_state.json ───────────────────────────────────────────
    state = _load_json_safe(STATE_PATH, _default_state(switch))
    state["master_switch"] = switch
    state["timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        _save_json(STATE_PATH, state)
    except OSError as e:
        print(f"[WARNING] Could not write engine_state.json: {e}")

    # ── 3. Report ─────────────────────────────────────────────────────────────
    style = "\033[92m" if switch else "\033[91m"
    reset = "\033[0m"
    status = "ENABLED" if switch else "DISABLED"

    print("\n" + "=" * 40)
    print(f"   SYSTEM MASTER SWITCH: {style}{status}{reset}")
    print("=" * 40)
    print(f"The modular engine will now {'resume' if switch else 'pause'} execution.")


if __name__ == "__main__":
    arg = sys.argv[1].upper() if len(sys.argv) > 1 else None
    toggle_system(arg)
