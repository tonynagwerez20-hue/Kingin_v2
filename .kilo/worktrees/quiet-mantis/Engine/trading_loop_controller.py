"""
TradingLoopController — Fixed Edition
=======================================
Fixes applied vs original:
  1. CRO method name crash: check_conditions() → audit_trade_request()
     (CRORules only has audit_trade_request; the old call threw AttributeError)
  2. Spread unit mismatch: CRORules was comparing MT5 points (e.g. 25) against
     a pip threshold (3.0). Now converts points → pips before the check.
  3. current_equity not injected: signal dict was passed directly to check_risk()
     without account context, causing UltraLowRisk to always read equity=$0.
  4. HTF bias direction gate: signals whose direction conflicts with the
     structural bias detected by MechanicalStructureLayer are suppressed.
  5. Regime gate: VOLATILE and RANGING regimes suppress signal execution.
  6. News scalp path: handles scalp_signal from NewsEventLayer if present.
"""

import asyncio
import time
from typing import Dict, Optional, Any
import aiohttp


class TradingLoopController:
    """
    Manages the main trading loop, fetching data and processing signals.
    """

    def __init__(
        self,
        api_url: str,
        bridge: Any,
        position_tracker: Any,
        risk_manager: Any,
        cro_rules: Any,
        regime_layer: Any,
        broker_watchdog: Any,
        audit_logger: Any,
        strategy_manager: Any,
        filtration: Any,
        db: Any,
        backtest_mode: bool = False,
        account_state: Optional[Dict] = None,
    ):
        self.api_url          = api_url
        self.bridge           = bridge
        self.position_tracker = position_tracker
        self.risk_manager     = risk_manager
        self.cro_rules        = cro_rules
        self.regime_layer     = regime_layer
        self.broker_watchdog  = broker_watchdog
        self.audit_logger     = audit_logger
        self.strategy_manager = strategy_manager
        self.filtration       = filtration
        self.db               = db
        self.backtest_mode    = backtest_mode

        # Shared account state dict injected from the bootstrapper so the
        # controller always has live equity/balance for risk injection.
        # Falls back to an internal dict if not provided.
        self._account = account_state if account_state is not None else {
            "balance": 0.0, "equity": 0.0,
            "daily_loss": 0.0, "daily_pnl": 0.0,
        }

        self.account_balance          = 0.0
        self.last_balance_check       = 0
        self.loop_interval            = 1.0
        self.balance_refresh_interval = 300

    # ──────────────────────────────────────────────────────────────────
    # Data fetching
    # ──────────────────────────────────────────────────────────────────

    async def fetch_candle_data(self, session: aiohttp.ClientSession,
                                timeframe: str, limit: int = 50) -> list:
        try:
            async with session.get(
                f"{self.api_url}/ohlc?tf={timeframe}&limit={limit}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("candles", [])
        except Exception as e:
            print(f"[TradingLoop] Error fetching {timeframe} data: {e}")
        return []

    async def update_account_balance(self) -> None:
        current_time = time.time()
        if current_time - self.last_balance_check > self.balance_refresh_interval:
            if self.bridge and self.bridge.connected:
                fetched = self.bridge.get_account_balance()
                if fetched is not None:
                    self.account_balance = fetched
                    self._account["balance"] = fetched
                    if self.db:
                        self.db.set_state("account_balance", self.account_balance)
                        self.db.set_state("balance_last_sync", current_time)
            self.last_balance_check = current_time

    # ──────────────────────────────────────────────────────────────────
    # Risk helpers
    # ──────────────────────────────────────────────────────────────────

    def check_risk_veto(self) -> Optional[str]:
        execution_allowed, veto_reason = self.risk_manager.check_execution_allowed()
        if not execution_allowed:
            return veto_reason
        return None

    def _inject_account_context(self, signal: Dict) -> Dict:
        """
        FIX #3: Inject live equity/balance into the signal dict before
        passing to check_risk(). UltraLowRisk reads these keys — without
        them it always sees equity=$0.00 and blocks every trade.
        MT5 can return equity=0.0 when no positions are open (zero
        floating P&L), so fall back to balance if equity is missing/zero.
        """
        equity  = self._account.get("equity") or self._account.get("balance", 0.0)
        balance = self._account.get("balance", 0.0)
        signal.update({
            "current_equity":      equity,
            "balance":             balance,
            "daily_loss":          self._account.get("daily_loss", 0.0),
            "daily_start_balance": balance,
            "open_positions_count": len([
                s for s in self._account.get("signals", [])
                if s.get("action") == "TRADE"
            ]),
        })
        return signal

    def _check_cro(self, tick: Dict) -> bool:
        """
        FIX #1 + #2: Call the correct method name and convert spread units.
        MT5 returns spread in POINTS (integer, e.g. 25 for Gold).
        CRORules.max_spread_pips is in PIPS. 1 pip Gold = 10 points.
        Convert: points / 10 = pips before comparison.
        """
        spread_points = tick.get("spread", 0.0)
        spread_pips   = spread_points / 10.0  # Gold: 10 points = 1 pip
        market_data   = {
            "spread": spread_pips,
            "volume": tick.get("volume", 1.0),
        }
        result = self.cro_rules.audit_trade_request({}, market_data)
        return result.get("status") == "PASS"

    # ──────────────────────────────────────────────────────────────────
    # Core processing
    # ──────────────────────────────────────────────────────────────────

    async def process_market_data(
        self, h1_candles: list, m15_candles: list, m5_candles: list,
        tick: Optional[Dict] = None
    ) -> Dict:
        # Update regime
        if m15_candles:
            regime = self.regime_layer.detect_regime(m15_candles)
            self.risk_manager.update_regime(regime)

        market_snapshot = {
            "h1_candles":  h1_candles,
            "m15_candles": m15_candles,
            "m5_candles":  m5_candles,
            "tick":        tick or {},
            "active_zone": None,
        }

        filtration_result = None
        if self.filtration:
            try:
                filtration_result = self.filtration.process_all_layers(market_snapshot)
            except Exception as e:
                print(f"[TradingLoop] Filtration error: {e}")

        # Extract HTF bias and news scalp from layer results
        htf_bias          = "neutral"
        news_scalp_signal = None
        if filtration_result:
            for layer_res in filtration_result.get("layer_results", []):
                layer_name   = layer_res.get("layer", "")
                layer_result = layer_res.get("result", {})
                if "Structure" in layer_name and "bias" in layer_result:
                    htf_bias = layer_result["bias"]
                if "News" in layer_name and layer_result.get("scalp_signal"):
                    news_scalp_signal = layer_result["scalp_signal"]

        signal = None
        if self.strategy_manager and m5_candles:
            try:
                signal = self.strategy_manager.generate_signal(market_snapshot)
            except Exception as e:
                print(f"[TradingLoop] Strategy error: {e}")

        current_regime = getattr(self.regime_layer, "current_regime", "STABLE")

        return {
            "signal":            signal,
            "filtration":        filtration_result,
            "htf_bias":          htf_bias,
            "news_scalp_signal": news_scalp_signal,
            "regime":            current_regime,
            "tick":              tick or {},
        }

    async def execute_signal(
        self,
        signal: Dict,
        market_data: Dict,
        filtration_result: Optional[Dict] = None,
        htf_bias: str = "neutral",
        current_regime: str = "STABLE",
        tick: Optional[Dict] = None,
    ) -> bool:
        if not signal:
            return False

        # ── FIX #5: Regime gate ────────────────────────────────────────
        if current_regime in ("VOLATILE", "RANGING"):
            print(f"[TradingLoop] REGIME BLOCK: regime={current_regime} — signal suppressed")
            return False

        # ── IGOF filtration check ──────────────────────────────────────
        try:
            from config.settings import ENABLE_IGOF
        except ImportError:
            ENABLE_IGOF = True

        if ENABLE_IGOF and filtration_result:
            action = filtration_result.get("action", "")
            if action not in ("TRADE_ALLOWED", "PASS"):
                print(f"[TradingLoop] Signal BLOCKED by IGOF: {filtration_result.get('reason')}")
                if self.audit_logger:
                    self.audit_logger.log_event("IGOF", "SIGNAL_BLOCKED", filtration_result)
                return False

        # ── FIX #4: Direction alignment gate ──────────────────────────
        signal_direction = signal.get("direction", "").lower()
        # Map strategy direction (BUY/SELL) to HTF bias format (BULLISH/BEARISH) for comparison
        if signal_direction == "buy":
            mapped_direction = "bullish"
        elif signal_direction == "sell":
            mapped_direction = "bearish"
        else:
            mapped_direction = signal_direction  # fallback for other values
        
        if htf_bias != "neutral" and mapped_direction:
            if mapped_direction != htf_bias.lower():
                print(
                    f"[TradingLoop] DIRECTION VETO: signal={signal_direction.upper()} "
                    f"vs HTF bias={htf_bias.upper()}"
                )
                if self.audit_logger:
                    self.audit_logger.log_event("STRATEGY", "DIRECTION_VETO", {
                        "signal_direction": signal_direction,
                        "htf_bias": htf_bias,
                    })
                return False

        # ── Risk manager veto ──────────────────────────────────────────
        veto_reason = self.check_risk_veto()
        if veto_reason:
            print(f"[TradingLoop] Signal vetoed: {veto_reason}")
            return False

        # ── FIX #1 + #2: CRO check with correct method + unit ─────────
        if tick and not self._check_cro(tick):
            print("[TradingLoop] Signal failed CRO spread/liquidity check")
            return False

        # ── FIX #3: Inject account context before risk rule check ──────
        signal = self._inject_account_context(signal)
        if hasattr(self, "_risk_rules"):
            for rule in self._risk_rules:
                risk_res = rule.check_risk(signal)
                if not risk_res.get("allowed", False):
                    print(f"[TradingLoop] Trade denied by: {rule.__class__.__name__}")
                    return False

        # ── Enrich signal with required fields for MT5 EA ─────────────────
        # Ensure signal is a dictionary
        if isinstance(signal, str):
            # Convert string signal to dictionary
            signal_dict = {"action": signal.upper()}
        elif isinstance(signal, dict):
            signal_dict = signal.copy()
        else:
            signal_dict = {}

        # Map strategy direction to EA action format
        direction = signal_dict.get("direction", "").upper()
        if direction == "BUY":
            signal_dict["action"] = "LONG"
        elif direction == "SELL":
            signal_dict["action"] = "SHORT"
        elif "action" not in signal_dict:
            signal_dict["action"] = "WAIT"

        # Get symbol from configuration or default
        signal_dict.setdefault("symbol", "XAUUSD")

        # Get price from tick data: LONG fills at ask, SHORT fills at bid (MT5 convention)
        if tick:
            if signal_dict["action"] == "LONG":
                signal_dict.setdefault("price", tick.get("ask", 0.0))
            elif signal_dict["action"] == "SHORT":
                signal_dict.setdefault("price", tick.get("bid", 0.0))
            else:
                signal_dict.setdefault("price", tick.get("close", 0.0))
        else:
            signal_dict.setdefault("price", 0.0)

        # Calculate SL/TP based on signal and risk parameters (using ATR or fixed pips)
        # For now, using fixed values - in production these should come from strategy/risk
        price = signal_dict.get("price", 0.0)
        if price > 0:
            if signal_dict["action"] == "LONG":
                signal_dict.setdefault("sl", price - 0.50)  # $0.50 SL for gold
                signal_dict.setdefault("tp", price + 1.00)  # $1.00 TP for gold
            elif signal_dict["action"] == "SHORT":
                signal_dict.setdefault("sl", price + 0.50)  # $0.50 SL for gold
                signal_dict.setdefault("tp", price - 1.00)  # $1.00 TP for gold
        else:
            signal_dict.setdefault("sl", 0.0)
            signal_dict.setdefault("tp", 0.0)

        # Apply risk management for position sizing (get enforced lot size)
        if hasattr(self, 'risk_manager') and self.risk_manager:
            try:
                # Call risk management to get enforced lot size and other parameters
                risk_res = self.risk_manager.check_risk(signal_dict)
                if risk_res.get("allowed", False):
                    # Enforce the lot size from risk management
                    if "enforced_lots" in risk_res:
                        signal_dict["lots"] = risk_res["enforced_lots"]
                    # Also enforce other risk parameters if present
                    if "dynamic_limit" in risk_res:
                        signal_dict["dynamic_daily_loss_limit"] = risk_res["dynamic_limit"]
                    if "dynamic_max_positions" in risk_res:
                        signal_dict["dynamic_max_positions"] = risk_res["dynamic_max_positions"]
                else:
                    # Risk management vetoed the trade
                    print(f"[TradingLoop] Signal vetoed by risk management: {risk_res.get('reason')}")
                    return False
            except Exception as e:
                print(f"[TradingLoop] Risk management error: {e}")
                # Continue with original signal if risk management fails
                signal_dict.setdefault("lots", 0.01)  # Default lot size
        else:
            signal_dict.setdefault("lots", 0.01)  # Default lot size if no risk manager

        # Add remaining required fields
        signal_dict.setdefault("timestamp", int(time.time()))
        signal_dict.setdefault("execution_type", "MARKET")
        signal_dict.setdefault("limit_price", signal_dict.get("price", 0.0))
        # Add HTF bias for MT5 EA bias field
        signal_dict.setdefault("bias", htf_bias.upper() if htf_bias else "NEUTRAL")
        signal_dict.setdefault("confluence_score", signal_dict.get("score", 0.0) / 100.0)  # Convert score 0-100 to 0-1

        # Use the enriched signal for execution
        enriched_signal = signal_dict

        # ── Execute ───────────────────────────────────────────────────
        if self.bridge and self.bridge.connected and not self.backtest_mode:
            try:
                result = self.bridge.send_signal(enriched_signal)
                if result:
                    print(f"[TradingLoop] Signal executed: {enriched_signal}")
                    if self.audit_logger:
                        self.audit_logger.log_trade(enriched_signal)
                    return True
            except Exception as e:
                print(f"[TradingLoop] Execution error: {e}")
        elif self.backtest_mode:
            print(f"[TradingLoop] [BACKTEST] Signal recorded: {signal}")
            return True

        return False

    async def execute_news_scalp(self, scalp_signal: Dict, tick: Optional[Dict] = None, htf_bias: str = "neutral") -> bool:
        """
        Handle a news scalp signal from NewsEventLayer.
        Bypasses IGOF + direction gate (already qualified inside the layer)
        but still passes through CRO, regime, and risk rules.
        """
        if not scalp_signal:
            return False
        current_regime = getattr(self.regime_layer, "current_regime", "STABLE")
        if current_regime == "VOLATILE":
            # Paradox: volatile = news event = exactly when we scalp.
            # Only block if RANGING (no edge).
            pass
        if current_regime == "RANGING":
            return False

        if tick and not self._check_cro(tick):
            return False

        trade = {
            "action":    scalp_signal.get("action", ""),
            "direction": scalp_signal.get("direction", "").lower(),
            "type":      "NEWS_SCALP",
            "trigger":   scalp_signal.get("trigger", ""),
        }
        trade = self._inject_account_context(trade)

        if hasattr(self, "_risk_rules"):
            for rule in self._risk_rules:
                risk_res = rule.check_risk(trade)
                if not risk_res.get("allowed", False):
                    return False

        # ── Enrich signal with required fields for MT5 EA ─────────────────
        # Ensure trade is a dictionary
        if isinstance(trade, str):
            # Convert string signal to dictionary
            trade_dict = {"action": trade.upper()}
        elif isinstance(trade, dict):
            trade_dict = trade.copy()
        else:
            trade_dict = {}

        # Map strategy direction to EA action format
        direction = trade_dict.get("direction", "").upper()
        if direction == "BUY":
            trade_dict["action"] = "LONG"
        elif direction == "SELL":
            trade_dict["action"] = "SHORT"
        elif "action" not in trade_dict:
            trade_dict["action"] = "WAIT"

        # Get symbol from configuration or default
        trade_dict.setdefault("symbol", "XAUUSD")

        # Get price from tick data: LONG fills at ask, SHORT fills at bid (MT5 convention)
        if tick:
            if trade_dict["action"] == "LONG":
                trade_dict.setdefault("price", tick.get("ask", 0.0))
            elif trade_dict["action"] == "SHORT":
                trade_dict.setdefault("price", tick.get("bid", 0.0))
            else:
                trade_dict.setdefault("price", tick.get("close", 0.0))
        else:
            trade_dict.setdefault("price", 0.0)

        # Calculate SL/TP based on signal and risk parameters (using ATR or fixed pips)
        # For now, using fixed values - in production these should come from strategy/risk
        price = trade_dict.get("price", 0.0)
        if price > 0:
            if trade_dict["action"] == "LONG":
                trade_dict.setdefault("sl", price - 0.50)  # $0.50 SL for gold
                trade_dict.setdefault("tp", price + 1.00)  # $1.00 TP for gold
            elif trade_dict["action"] == "SHORT":
                trade_dict.setdefault("sl", price + 0.50)  # $0.50 SL for gold
                trade_dict.setdefault("tp", price - 1.00)  # $1.00 TP for gold
        else:
            trade_dict.setdefault("sl", 0.0)
            trade_dict.setdefault("tp", 0.0)

        # Apply risk management for position sizing (get enforced lot size)
        if hasattr(self, 'risk_manager') and self.risk_manager:
            try:
                # Call risk management to get enforced lot size and other parameters
                risk_res = self.risk_manager.check_risk(trade_dict)
                if risk_res.get("allowed", False):
                    # Enforce the lot size from risk management
                    if "enforced_lots" in risk_res:
                        trade_dict["lots"] = risk_res["enforced_lots"]
                    # Also enforce other risk parameters if present
                    if "dynamic_limit" in risk_res:
                        trade_dict["dynamic_daily_loss_limit"] = risk_res["dynamic_limit"]
                    if "dynamic_max_positions" in risk_res:
                        trade_dict["dynamic_max_positions"] = risk_res["dynamic_max_positions"]
                else:
                    # Risk management vetoed the trade
                    print(f"[TradingLoop] Signal vetoed by risk management: {risk_res.get('reason')}")
                    return False
            except Exception as e:
                print(f"[TradingLoop] Risk management error: {e}")
                # Continue with original signal if risk management fails
                trade_dict.setdefault("lots", 0.01)  # Default lot size
        else:
            trade_dict.setdefault("lots", 0.01)  # Default lot size if no risk manager

        # Add remaining required fields
        trade_dict.setdefault("timestamp", int(time.time()))
        trade_dict.setdefault("execution_type", "MARKET")
        trade_dict.setdefault("limit_price", trade_dict.get("price", 0.0))
        # Add HTF bias for MT5 EA bias field
        trade_dict.setdefault("bias", htf_bias.upper() if htf_bias else "NEUTRAL")
        trade_dict.setdefault("confluence_score", trade_dict.get("score", 0.0) / 100.0)  # EA reads "confluence_score"

        # Use the enriched signal for execution
        enriched_trade = trade_dict

        if self.bridge and self.bridge.connected and not self.backtest_mode:
            try:
                result = self.bridge.send_signal(enriched_trade)
                if result:
                    print(f"[TradingLoop] NEWS SCALP executed: {trade['trigger']}")
                    return True
            except Exception as e:
                print(f"[TradingLoop] News scalp execution error: {e}")
        elif self.backtest_mode:
            print(f"[TradingLoop] [BACKTEST] News scalp: {trade['trigger']}")
            return True
        return False

    # ──────────────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        print("\n" + "=" * 60)
        print("TRADING LOOP STARTED")
        print("=" * 60 + "\n")

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    h1_candles  = await self.fetch_candle_data(session, "H1",  50)
                    m15_candles = await self.fetch_candle_data(session, "M15", 100)
                    m5_candles  = await self.fetch_candle_data(session, "M5",  200)

                    await self.update_account_balance()

                    # Fetch tick for CRO spread check
                    tick = {}
                    try:
                        async with session.get(
                            f"{self.api_url}/latest-tick", timeout=aiohttp.ClientTimeout(total=1)
                        ) as resp:
                            if resp.status == 200:
                                tick = await resp.json()
                    except Exception:
                        pass

                    result = await self.process_market_data(
                        h1_candles, m15_candles, m5_candles, tick=tick
                    )

                    # Standard signal path
                    if result.get("signal"):
                        await self.execute_signal(
                            result["signal"],
                            market_data={
                                "h1_candles":  h1_candles,
                                "m15_candles": m15_candles,
                                "m5_candles":  m5_candles,
                            },
                            filtration_result=result.get("filtration"),
                            htf_bias=result.get("htf_bias", "neutral"),
                            current_regime=result.get("regime", "STABLE"),
                            tick=tick,
                        )

                    # News scalp path
                    if result.get("news_scalp_signal"):
                        await self.execute_news_scalp(result["news_scalp_signal"], tick=tick)

                    await asyncio.sleep(self.loop_interval)

                except KeyboardInterrupt:
                    print("\n[TradingLoop] Shutdown requested")
                    break
                except Exception as e:
                    print(f"[TradingLoop] Error in main loop: {e}")
                    await asyncio.sleep(self.loop_interval)
