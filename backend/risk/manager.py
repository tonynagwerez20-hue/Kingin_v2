"""Risk Manager."""
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class RiskState:
    daily_loss: float = 0.0
    trade_count: int = 0
    last_trade_date: str = ""


class RiskManager:
    def __init__(self):
        self._max_daily_loss = 500.0
        self._max_trades_per_day = 10
        self._max_concurrent = 3
        self._state = RiskState()
    
    def check_risk(self, signal_action: str, balance: float) -> tuple[bool, str]:
        today = date.today().isoformat()
        if self._state.last_trade_date != today:
            self._state.daily_loss = 0.0
            self._state.trade_count = 0
            self._state.last_trade_date = today
        if self._state.daily_loss >= self._max_daily_loss:
            return False, "MAX_DAILY_LOSS_REACHED"
        if self._state.trade_count >= self._max_trades_per_day:
            return False, "MAX_TRADES_PER_DAY"
        return True, ""
    
    def on_trade_opened(self, lots: float, pnl: float = 0.0):
        self._state.trade_count += 1
        if pnl < 0:
            self._state.daily_loss += abs(pnl)
    
    def get_state(self) -> RiskState:
        return self._state


_risk_manager: Optional[RiskManager] = None

def get_risk_manager() -> RiskManager:
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager