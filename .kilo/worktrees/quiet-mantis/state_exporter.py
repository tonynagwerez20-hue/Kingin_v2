"""
state_exporter.py — ITS Atomic Engine State Writer
====================================================
Standalone module. Import anywhere in the engine:

    from state_exporter import StateExporter
    exporter = StateExporter()
    exporter.export(state_dict)

Rules:
  — Completely decoupled from the engine; removable without side effects
  — Background daemon thread (never blocks the engine)
  — Atomic write: .tmp → os.replace() → engine_state.json
  — All IO errors are silently swallowed
  — Output: <repo_root>/engine_state.json
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty

# ── Output path: repo root directory (same dir as this file) ────────────────
_BASE    = Path(__file__).resolve().parent
_OUT     = str(_BASE / "engine_state.json")
_TMP     = str(_BASE / "engine_state.tmp")


class StateExporter:
    """
    Thread-safe, non-blocking engine state exporter.
    Writes JSON to engine_state.json atomically on every export() call.
    """

    def __init__(self, output_path: str = _OUT):
        self._path     = output_path
        self._tmp_path = output_path.replace(".json", ".tmp")
        self._queue    = Queue(maxsize=1)   # only keep latest state
        self._thread   = threading.Thread(
            target=self._worker, daemon=True, name="StateExporter"
        )
        self._thread.start()

    # ── Public API ───────────────────────────────────────────────────────────

    def export(self, state_dict: dict) -> None:
        """
        Queue state_dict for export. Non-blocking.
        Automatically stamps the export with a UTC timestamp if not present.
        """
        if not isinstance(state_dict, dict):
            return
        # stamp
        state_dict.setdefault(
            "timestamp",
            datetime.now(timezone.utc).isoformat()
        )
        # drain queue so only latest is pending
        try:
            self._queue.get_nowait()
        except Empty:
            pass
        try:
            self._queue.put_nowait(state_dict)
        except Exception:
            pass

    # ── Background worker ────────────────────────────────────────────────────

    def _worker(self) -> None:
        while True:
            try:
                state = self._queue.get(timeout=5)
                self._write(state)
            except Empty:
                pass
            except Exception:
                pass  # always keep the thread alive

    def _write(self, state: dict) -> None:
        """Atomic write: tmp → replace."""
        try:
            payload = json.dumps(state, default=str, indent=2)
            with open(self._tmp_path, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(self._tmp_path, self._path)
        except Exception:
            pass  # silent — never crash the engine


# ── Demo / test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    print(f"[StateExporter] Writing demo state to {_OUT} ...")
    exp = StateExporter()
    demo = {
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "symbol":           "XAUUSD",
        "bias":             "BULLISH",
        "current_price":    3125.50,
        "signal_action":    "LONG",
        "entry_price":      3125.50,
        "stop_loss":        3120.00,
        "take_profit":      3135.00,
        "lot_size":         0.01,
        "execution_type":   "MARKET",
        "confluence_score": 6.0,
        "killzone_name":    "London Open",
        "session_time":     "08:00–11:00 UTC",
        "rr_ratio":         "1:1.91",
        "layers": [
            {"name": "KillzoneFilterLayer",    "passed": True,  "score": 1.0, "reason": "London Active"},
            {"name": "MechanicalStructureLayer","passed": True,  "score": 1.0, "reason": "Bullish BOS"},
            {"name": "LiquiditySweepLayer",    "passed": True,  "score": 1.0, "reason": "Sweep at 3118"},
            {"name": "DisplacementLayer",      "passed": True,  "score": 1.0, "reason": "H1 Impulse"},
            {"name": "FVGDiscountLayer",       "passed": True,  "score": 0.75,"reason": "Bullish IFVG"},
            {"name": "MicroMSSLayer",          "passed": False, "score": 0.0, "reason": "No M1 flip"},
            {"name": "NewsEventLayer",         "passed": True,  "score": 1.0, "reason": "Clear"},
        ],
        "last_trade": {
            "action": "LONG", "symbol": "XAUUSD", "price": 3120.00,
            "sl": 3115.00, "tp": 3130.00, "lots": 0.01, "bias": "BULLISH",
            "execution_type": "MARKET", "confluence_score": 5.75,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "account_equity":    88.50,
        "account_balance":   86.80,
        "floating_pnl":      1.70,
        "open_trades_count": 1,
        "open_positions": [
            {
                "symbol": "XAUUSD", "type": "BUY", "lots": 0.01,
                "open_price": 3120.00, "current_price": 3125.50,
                "sl": 3115.00, "tp": 3130.00, "floating_pnl": 0.55,
                "open_time": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "active_warnings": [],
    }
    exp.export(demo)
    time.sleep(1)
    print(f"[OK] engine_state.json written.")
