"""V38 risk engine and position manager.

Sizing, daily-loss / drawdown caps, consecutive-loss throttle, max trades/day,
news-mode gating, and a structured trade decision envelope. This is the layer
that turns an ML probability + structural SL/TP into an actual position decision
and is where the news modes take effect.

No real broker connection (this is the model/strategy layer); MQL5 EA wires the
final orders. The risk engine is deterministic and testable in Python.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

import pandas as pd

from ..config import V38Config, NEWS_OFF, NEWS_FILTER_ONLY, NEWS_REACTIVE, \
    NEWS_DIRECTIONAL, NEWS_HYBRID
from ..macro.engine import MacroEngine


@dataclass
class AccountState:
    balance: float = 10000.0
    equity: float = 10000.0
    day_start_balance: float = 10000.0
    day_trades: int = 0
    consecutive_losses: int = 0
    peak_balance: float = 10000.0
    trading_day: Optional[pd.Timestamp] = None


@dataclass
class TradeDecision:
    allow: bool
    direction: str
    entry: float
    sl: float
    tp: float
    rr: float
    probability: float
    calibrated_probability: float
    position_size_units: float
    risk_amount: float
    reasons: List[str] = field(default_factory=list)
    news: Optional[dict] = None


class RiskEngine:
    def __init__(self, cfg: V38Config, macro: Optional[MacroEngine] = None):
        self.cfg = cfg
        self.macro = macro
        self.account = AccountState()

    def update_account(self, balance: float, equity: float, ts: pd.Timestamp):
        day = pd.Timestamp(ts).normalize()
        if self.account.trading_day is None or day != self.account.trading_day:
            self.account.trading_day = day
            self.account.day_start_balance = balance
            self.account.day_trades = 0
        self.account.balance = balance
        self.account.equity = equity
        self.account.peak_balance = max(self.account.peak_balance, equity)

    def on_trade_closed(self, won: bool):
        if won:
            self.account.consecutive_losses = 0
        else:
            self.account.consecutive_losses += 1

    # ----------------------------------------------------------- decisions
    def evaluate(self, *, direction: str, entry: float, sl: float, tp: float,
                 probability: float, calibrated_probability: float,
                 ts: pd.Timestamp, atr: float,
                 threshold: float = 0.5) -> TradeDecision:
        reasons: List[str] = []
        allow = True

        # 1. probability gate (use calibrated prob if available)
        prob = calibrated_probability if calibrated_probability is not None else probability
        if prob < threshold:
            allow = False
            reasons.append(f"probability {prob:.3f} < threshold {threshold}")

        # 2. RR gate
        rr = (tp - entry) / (entry - sl) if direction == "bullish" else \
             (entry - tp) / (sl - entry)
        if rr < 1.0:
            allow = False
            reasons.append(f"RR {rr:.2f} < 1.0")

        # 3. daily loss cap
        day_loss = self.account.day_start_balance - self.account.equity
        if day_loss / self.account.day_start_balance >= self.cfg.max_daily_loss_pct:
            allow = False
            reasons.append("daily loss cap reached")

        # 4. total drawdown cap
        dd = (self.account.peak_balance - self.account.equity) / self.account.peak_balance
        if dd >= self.cfg.max_total_drawdown_pct:
            allow = False
            reasons.append("max drawdown reached")

        # 5. consecutive losses
        if self.account.consecutive_losses >= self.cfg.max_consecutive_losses:
            allow = False
            reasons.append("max consecutive losses reached")

        # 6. trades per day
        if self.account.day_trades >= self.cfg.max_trades_per_day:
            allow = False
            reasons.append("max trades/day reached")

        # 7. news-mode decision
        news_decision = None
        if self.macro is not None and self.cfg.news_mode != NEWS_OFF:
            news_decision = self.macro.decision(ts, direction, self.cfg)
            if news_decision.get("veto"):
                allow = False
                reasons.append("news veto: " + news_decision.get("reason", ""))
            if news_decision.get("confidence_adjustment", 0.0) != 0.0:
                # adjustment is informational; threshold uses raw calibrated prob
                pass

        # 8. position sizing (monetary risk = pct of balance)
        sl_distance = abs(entry - sl)
        risk_amount = self.cfg.risk_pct_account * self.account.equity
        # gold: contract size 100 oz; price-based SL distance -> units
        # units = risk_amount / (sl_distance_per_unit); for XAUUSD 1 unit = $1/oz move
        position_size_units = risk_amount / sl_distance if sl_distance > 0 else 0.0

        return TradeDecision(
            allow=allow, direction=direction, entry=entry, sl=sl, tp=tp,
            rr=float(rr), probability=float(probability),
            calibrated_probability=float(calibrated_probability),
            position_size_units=float(position_size_units),
            risk_amount=float(risk_amount), reasons=reasons, news=news_decision,
        )
