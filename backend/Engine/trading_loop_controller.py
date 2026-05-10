"""
TradingLoopController — Fixed Edition
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

        # ATR multiplier defaults (can be overridden by config)
        self.sl_atr_mult = 1.5
        self.tp_atr_mult = 3.0

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
        self.processed_tickets = set()
        self.last_history_check = 0

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
        if current_time - self.last_balance_check > 5:  # Check connection/balance more frequently (every 5s)
            if self.bridge:
                # Always refresh the connection status
                is_connected = self.bridge.check_connection()
                
                # Store connection status in DB for the dashboard
                if self.db:
                    self.db.set_state("bridge_connected", is_connected)
                    self.db.set_state("bridge_last_check", current_time)

                # Fetch balance/equity. The bridge internally handles falling back to 
                # direct MT5 session if ZMQ is down.
                fetched_balance = self.bridge.get_account_balance()
                fetched_equity = self.bridge.get_account_equity()

                if fetched_balance is not None:
                    self.account_balance = fetched_balance
                    self._account["balance"] = fetched_balance
                    if self.db:
                        self.db.set_state("account_balance", self.account_balance)
                
                if fetched_equity is not None:
                    self._account["equity"] = fetched_equity
                    if self.db:
                        self.db.set_state("account_equity", fetched_equity)
                
                if self.db and (fetched_balance is not None or fetched_equity is not None):
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

    def _calculate_atr(self, candles: list, period: int = 14) -> float:
        """Simple ATR calculation from candle list."""
        if len(candles) < period + 1:
            return 0.0
        
        trs = []
        for i in range(1, len(candles)):
            high = candles[i].get("high", 0)
            low = candles[i].get("low", 0)
            prev_close = candles[i-1].get("close", 0)
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
            
        # Return simple moving average of TR
        relevant_trs = trs[-period:]
        return sum(relevant_trs) / len(relevant_trs)

    def _apply_dynamic_sl_tp(self, signal_dict: Dict, candles: list):
        """Calculate and set SL/TP based on ATR."""
        price = signal_dict.get("price", 0.0)
        if price <= 0 or not candles:
            signal_dict.setdefault("sl", 0.0)
            signal_dict.setdefault("tp", 0.0)
            return

        atr = self._calculate_atr(candles)
        # Gold price is ~2300, ATR might be ~2.0 (20 pips). 
        # If ATR fails, fall back to a sensible minimum for gold (e.g. 1.0 = 10 pips)
        if atr <= 0:
            atr = 1.0 

        action = signal_dict.get("action")
        if action == "LONG":
            signal_dict.setdefault("sl", price - (atr * self.sl_atr_mult))
            signal_dict.setdefault("tp", price + (atr * self.tp_atr_mult))
        elif action == "SHORT":
            signal_dict.setdefault("sl", price + (atr * self.sl_atr_mult))
            signal_dict.setdefault("tp", price - (atr * self.tp_atr_mult))

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
                filtration_result = self.filtration.process(market_snapshot)
            except Exception as e:
                print(f"[TradingLoop] Filtration error: {e}")
                filtration_result = {}

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

        # Calculate SL/TP based on signal and risk parameters (using dynamic ATR)
        # Using M15 candles for ATR as a balanced timeframe for Gold
        # Create a local session for the candle fetch since we may not have one in scope
        try:
            async with aiohttp.ClientSession() as _atr_session:
                m15_candles = await self.fetch_candle_data(_atr_session, "M15", 30)
        except Exception:
            m15_candles = []
        self._apply_dynamic_sl_tp(signal_dict, m15_candles)

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

        # Attach filtration layers to the signal for auditing and dashboard
        if filtration_result and "layer_results" in filtration_result:
            enriched_signal["layers"] = filtration_result["layer_results"]

        # ── Execute ───────────────────────────────────────────────────
        if self.bridge and self.bridge.connected and not self.backtest_mode:
            try:
                result = self.bridge.send_signal(enriched_signal)
                if result:
                    print(f"[TradingLoop] Signal executed: {enriched_signal}")
                    
                    # Store ML context in position tracker for later learning
                    ml_context = None
                    if filtration_result and "layer_results" in filtration_result:
                        for res in filtration_result["layer_results"]:
                            # Check if res is a dict (V1FiltrationEngine returns dicts)
                            if isinstance(res, dict) and "MLFilterLayer" in str(res.get("reason", "")):
                                ml_context = {
                                    "signal": enriched_signal,
                                    "confidence": res.get("confidence", 0.5)
                                }
                                break
                    
                    ticket = 0
                    if isinstance(result, dict):
                        ticket = result.get("ticket", 0)
                    
                    if self.position_tracker:
                        self.position_tracker.open_position(
                            direction=enriched_signal["action"],
                            symbol=enriched_signal["symbol"],
                            entry_price=enriched_signal["price"],
                            lots=enriched_signal["lots"],
                            sl=enriched_signal["sl"],
                            mt5_ticket=ticket,
                            ml_context=ml_context
                        )

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

        # Calculate dynamic ATR-based SL/TP for news scalp
        # Use M5 candles for tighter, faster news scalp time horizon
        try:
            async with aiohttp.ClientSession() as _atr_session:
                m5_candles = await self.fetch_candle_data(_atr_session, "M5", 20)
        except Exception:
            m5_candles = []
        # Use tighter ATR multipliers for news scalp (faster exit)
        orig_sl_mult, orig_tp_mult = self.sl_atr_mult, self.tp_atr_mult
        self.sl_atr_mult, self.tp_atr_mult = 1.0, 1.5  # tighter for news scalp
        self._apply_dynamic_sl_tp(trade_dict, m5_candles)
        self.sl_atr_mult, self.tp_atr_mult = orig_sl_mult, orig_tp_mult  # restore

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
                    print(f"[TradingLoop] NEWS SCALP executed: {enriched_trade.get('trigger', 'N/A')}")
                    return True
            except Exception as e:
                print(f"[TradingLoop] News scalp execution error: {e}")
        elif self.backtest_mode:
            print(f"[TradingLoop] [BACKTEST] News scalp: {enriched_trade.get('trigger', 'N/A')}")
            return True
        return False

    async def check_trade_history(self) -> None:
        """Poll MT5 for closed trades and update ML layer."""
        current_time = time.time()
        # Check history every 60 seconds
        if current_time - self.last_history_check < 60:
            return
            
        self.last_history_check = current_time
        
        if not self.bridge or not self.bridge.connected or self.backtest_mode:
            return
            
        try:
            history = self.bridge.get_trade_history(days=1)
            if not history:
                return
                
            for trade in history:
                ticket = trade.get("ticket")
                if not ticket or ticket in self.processed_tickets:
                    continue
                
                # This is a new closed trade!
                pnl = trade.get("profit", 0) + trade.get("commission", 0) + trade.get("swap", 0)
                outcome = 1 if pnl > 0 else 0
                
                # Check if we have the ML context for this trade
                pos_info = self.position_tracker.get_position_info() if self.position_tracker else None
                
                if pos_info and pos_info.get("mt5_ticket") == ticket:
                    ml_ctx = pos_info.get("ml_context")
                    if ml_ctx and self.filtration:
                        print(f"[ML] Learning from trade {ticket}: outcome={'WIN' if outcome else 'LOSS'} (PnL: {pnl:.2f})")
                        self.filtration.record_trade_outcome(
                            signal=ml_ctx["signal"],
                            confidence=ml_ctx["confidence"],
                            outcome=outcome,
                            metadata={"ticket": ticket, "pnl": pnl}
                        )
                
                self.processed_tickets.add(ticket)
                
        except Exception as e:
            print(f"[TradingLoop] Error checking history: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        print("\n" + "=" * 60)
        print("TRADING LOOP STARTED")
        print("=" * 60 + "\n")

        last_heartbeat = 0

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

                    # --- HEARTBEAT LOGGING (For Dashboard Sync) ---
                    if time.time() - last_heartbeat > 10:
                        if self.audit_logger:
                            heartbeat_data = {
                                "status": "RUNNING",
                                "regime": result.get("regime", "STABLE"),
                                "bias": result.get("htf_bias", "NEUTRAL"),
                                "layers": result.get("filtration", {}).get("layer_results", []),
                                "killzone": result.get("filtration", {}).get("layer_results", [{}])[0].get("reason", "N/A") if result.get("filtration") else "N/A"
                            }
                            self.audit_logger.log_event("SYSTEM", "HEARTBEAT", heartbeat_data)
                        last_heartbeat = time.time()

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

                    # Update ML feedback loop
                    await self.check_trade_history()

                    await asyncio.sleep(self.loop_interval)

                except KeyboardInterrupt:
                    print("\n[TradingLoop] Shutdown requested")
                    break
                except Exception as e:
                    print(f"[TradingLoop] Error in main loop: {e}")
                    await asyncio.sleep(self.loop_interval)
