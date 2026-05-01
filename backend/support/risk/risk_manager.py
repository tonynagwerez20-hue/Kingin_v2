import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, date


class RiskManager:
    def __init__(self, state_path: str = "storage/risk_state/risk_state.json", config: Optional[Dict] = None):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        
        # Load config or use defaults
        self.config = config or {}
        self.max_daily_loss = self.config.get("max_daily_loss", 500.0)
        self.max_trades_per_day = self.config.get("max_trades_per_day", 10)
        self.max_concurrent_positions = self.config.get("max_concurrent_positions", 3)

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Default state
        default_state = {
            "global_kill_switch": False,
            "current_regime": "STABLE",
            "last_audit_status": "PASS",
            "active_risk_vetos": [],
            "daily_loss": 0.0,
            "daily_trades": 0,
            "last_reset_date": str(date.today()),
            "concurrent_positions": 0
        }
        self._save_state(default_state)
        return default_state

    def _save_state(self, state: Dict[str, Any]):
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=4)
    
    def _check_daily_reset(self):
        """Reset daily counters if it's a new day."""
        today = str(date.today())
        if self.state.get("last_reset_date") != today:
            self.state["daily_loss"] = 0.0
            self.state["daily_trades"] = 0
            self.state["last_reset_date"] = today
            self._save_state(self.state)
            print(f"[RiskManager] Daily counters reset for {today}")

    def check_execution_allowed(self) -> Tuple[bool, Optional[str]]:
        """
        Aggregates all risk checks. Returns (allowed, reason).
        
        Returns:
            Tuple of (bool, Optional[str]): (execution_allowed, veto_reason)
        """
        self._check_daily_reset()
        
        # Check kill switch
        if self.state.get("global_kill_switch", False):
            return False, "Global Kill Switch is ACTIVE"
        
        # Check daily loss limit
        if self.state.get("daily_loss", 0.0) >= self.max_daily_loss:
            return False, f"Daily loss limit reached (${self.state['daily_loss']:.2f} >= ${self.max_daily_loss:.2f})"
        
        # Check max trades per day
        if self.state.get("daily_trades", 0) >= self.max_trades_per_day:
            return False, f"Max trades per day reached ({self.state['daily_trades']} >= {self.max_trades_per_day})"
        
        # Check max concurrent positions
        if self.state.get("concurrent_positions", 0) >= self.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({self.state['concurrent_positions']} >= {self.max_concurrent_positions})"
        
        # Check audit status
        if self.state.get("last_audit_status") == "FAIL":
            return False, "Last audit failed"

        return True, None
    
    def record_trade(self, pnl: float) -> None:
        """
        Record a completed trade and update daily stats.
        
        Args:
            pnl: Profit/Loss of the trade
        """
        self._check_daily_reset()
        
        self.state["daily_trades"] = self.state.get("daily_trades", 0) + 1
        
        if pnl < 0:
            self.state["daily_loss"] = self.state.get("daily_loss", 0.0) + abs(pnl)
        
        self._save_state(self.state)
        print(f"[RiskManager] Trade recorded: PnL=${pnl:.2f}, Daily Loss=${self.state['daily_loss']:.2f}, Daily Trades={self.state['daily_trades']}")
    
    def update_position_count(self, count: int) -> None:
        """
        Update the count of concurrent positions.
        
        Args:
            count: Current number of open positions
        """
        self.state["concurrent_positions"] = count
        self._save_state(self.state)

    def update_regime(self, regime: str):
        """Update the current market regime."""
        self.state["current_regime"] = regime
        self._save_state(self.state)

    def set_kill_switch(self, status: bool):
        """Activate or deactivate the global kill switch."""
        self.state["global_kill_switch"] = status
        self._save_state(self.state)
        print(f"[RiskManager] Kill switch {'ACTIVATED' if status else 'DEACTIVATED'}")
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """Get current daily statistics."""
        self._check_daily_reset()
        return {
            "daily_loss": self.state.get("daily_loss", 0.0),
            "daily_trades": self.state.get("daily_trades", 0),
            "concurrent_positions": self.state.get("concurrent_positions", 0),
            "max_daily_loss": self.max_daily_loss,
            "max_trades_per_day": self.max_trades_per_day,
            "max_concurrent_positions": self.max_concurrent_positions
        }
