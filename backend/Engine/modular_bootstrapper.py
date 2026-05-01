import json
import logging
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque
from contextlib import nullcontext

# ── Ensure Engine/ directory is on sys.path so zmq_bridge resolves correctly ─
# This fixes "No module named 'zmq_bridge'" regardless of where the .bat file
# sets the working directory from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
# ─────────────────────────────────────────────────────────────────────────────

from Engine.registry import ComponentRegistry
from Engine.igof.igof_engine import IGOFEngine
from Engine.base_interfaces import BaseDataProvider, BaseFiltrationLayer, BaseStrategy, BaseRiskRule
from Engine.lite_log_handler import setup_lite_logging
from storage.hedge_db import HedgeDB

# ── ZMQ Bridge import ─────────────────────────────────────────────────────────
# zmq_bridge.py must be in the same Engine/ folder as this file.
# It auto-installs pyzmq on first run, so no manual pip install needed.
_ZMQ_IMPORT_ERROR: str = ""
try:
    from zmq_bridge import ZMQBridge
    _ZMQ_IMPORT_ERROR = ""
except ImportError as _e:
    ZMQBridge = None
    _ZMQ_IMPORT_ERROR = (
        f"zmq_bridge.py not found in the Engine/ folder ({_e}). "
        "Copy zmq_bridge.py into your Engine/ directory and restart."
    )
except Exception as _e:
    ZMQBridge = None
    _ZMQ_IMPORT_ERROR = f"zmq_bridge.py failed to load: {_e}"
# ─────────────────────────────────────────────────────────────────────────────

# ── Path anchor ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
# ──────────────────────────────────────────────────────────────────────────────

# ── StateExporter: writes engine_state.json for the tkinter dashboard ─────────
try:
    from state_exporter import StateExporter as _StateExporter
    _state_exporter = _StateExporter(str(BASE_DIR / "engine_state.json"))
except Exception as _se_err:
    _state_exporter = None
    logging.getLogger("ModularBootstrapper").warning(
        f"[StateExporter] Not available — dashboard will show OFFLINE: {_se_err}"
    )
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ModularBootstrapper")


class ModularBootstrapper:
    """
    Dynamically loads and connects components based on trading_params_lite.json.
    Supports "Hot Swapping" and "Lite Mode" for low-end hardware.
    """

    def __init__(self, config_path: str):
        # Anchor relative paths to BASE_DIR (this file's folder) so the system
        # works regardless of which directory the launcher script runs from.
        # This is the root cause of "The system cannot find the path specified".
        _p = Path(config_path)
        self.config_path = _p if _p.is_absolute() else BASE_DIR / _p
        self.config = self._load_json_config()

        # Performance Settings
        perf_cfg = self.config.get("performance", {})
        self.lite_mode = perf_cfg.get("lite_mode", False)
        self.loop_delay = perf_cfg.get("loop_delay_seconds", 1.0)

        # Initialize optimized logging for Lite mode
        if self.lite_mode:
            setup_lite_logging(str(BASE_DIR / "engine_lite.log"))
            logger.info("LITE MODE ENABLED: Performance optimizations active.")

        # Pipeline components
        self.data_provider: BaseDataProvider = None
        self.filtration_engine: IGOFEngine = None
        self.strategies: List[BaseStrategy] = []
        self.risk_rules: List[BaseRiskRule] = []

        # RiskManager — instantiated here so regime gate and daily stats are accessible
        from support.risk.risk_manager import RiskManager
        risk_cfg = self.config.get("pipeline", {}).get("risk_manager", {})
        self.risk_manager = RiskManager(config=risk_cfg)

        # Shared state dict exposed to React dashboard endpoint
        self._current_state: Dict = {}

        # Initialize database for state persistence
        db_path = BASE_DIR / "data" / "hedge.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = HedgeDB(str(db_path))
        self.last_balance_sync = 0.0

        # ── ZMQ Bridge to HedgeEA ──────────────────────────────────────────────
        zmq_cfg  = self.config.get("zmq", {})
        if ZMQBridge is None:
            logger.error(
                f"[BOOTSTRAP] ZMQ Bridge UNAVAILABLE — {_ZMQ_IMPORT_ERROR}\n"
                "  Signals will be dropped until this is fixed."
            )
            self.bridge = None
        else:
            self.bridge = ZMQBridge(
                host          = zmq_cfg.get("host",           "localhost"),
                pub_port      = zmq_cfg.get("port",           5555),
                hb_port       = zmq_cfg.get("heartbeat_port", 5557),
                topic         = zmq_cfg.get("topic",          "SIGNAL"),
                hb_timeout_ms = zmq_cfg.get("hb_timeout_ms",  2000),
            )

        # Track sent signal IDs to prevent duplicate sends within the same session
        self._sent_signal_ids: set   = set()
        self._signals_count:   int   = 0
        self._dashboard_logs:  deque = deque(maxlen=50) # Keep last 50 events

    # ──────────────────────────────────────────────────────────────────────────
    # Config
    # ──────────────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────────────
    # Internal Handlers
    # ──────────────────────────────────────────────────────────────────────────

    def emit_dashboard_msg(self, msg: str):
        """Adds a message to the dashboard log buffer."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._dashboard_logs.append(f"[{ts}] {msg}")
        # Also log to standard logger
        logger.debug(f"[DASHBOARD] {msg}")

    def _load_json_config(self) -> Dict:
        """Reads the JSON configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            logging.shutdown()
            sys.exit(1)

    # ──────────────────────────────────────────────────────────────────────────
    # Pipeline builder
    # ──────────────────────────────────────────────────────────────────────────

    def build_pipeline(self):
        """
        Builds the entire trading pipeline dynamically using the Registry.
        Supports both the standard 'v6' and simplified 'Lite' configuration formats.
        """
        logger.info("[VERIFICATION] Building modular pipeline v6.1 (Latest)...")
        pipeline_cfg = self.config.get("pipeline", {})

        # 1. Load Data Provider
        from data_feed.factory import DataProviderFactory

        active_source = pipeline_cfg.get("active_data_source", "MT5_PROVIDER")
        dp_cfg = pipeline_cfg.get("data_provider", {})

        # Merge performance settings into provider config
        dp_config = dp_cfg.get("config", {})
        if self.lite_mode:
            dp_config["lite_mode"] = True

        try:
            self.data_provider = DataProviderFactory.get_provider(active_source, dp_config)
            if not self.data_provider.connect():
                logger.error(f"Data Provider {active_source} failed to connect.")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Critical error loading data provider: {e}")
            logging.shutdown()
            sys.exit(1)

        # 2. Load Filtration Layers
        layers_cfg = pipeline_cfg.get("filtration_layers", [])
        
        # --- LITE CONFIG SUPPORT ---
        # If 'pipeline' key is missing, look for simpler 'layers' and 'filters' keys
        if not layers_cfg and ("layers" in self.config or "filters" in self.config):
            logger.info("[BOOTSTRAP] Mapping 'Lite' configuration to modular pipeline...")
            lite_layers = self.config.get("layers", {})
            
            # Lookup table for shorthand names -> full class paths (SMC Gold Edition)
            layer_map = {
                "KillzoneFilterLayer":      "Engine.igof.layers.smc.killzone.KillzoneFilterLayer",
                "MechanicalStructureLayer": "Engine.igof.layers.smc.structure.MechanicalStructureLayer",
                "LiquiditySweepLayer":      "Engine.igof.layers.smc.liquidity.LiquiditySweepLayer",
                "DisplacementLayer":        "Engine.igof.layers.smc.displacement.DisplacementLayer",
                "FVGDiscountLayer":         "Engine.igof.layers.smc.fvg.FVGDiscountLayer",
                "MicroMSSLayer":            "Engine.igof.layers.smc.mss.MicroMSSLayer",
                "NewsEventLayer":           "Engine.igof.layers.smc.news_layer.NewsEventLayer",
                "MLFilterLayer":            "Engine.igof.layers.ml_layer.MLFilterLayer",
            }

            for name, enabled in lite_layers.items():
                if enabled and name in layer_map:
                    layers_cfg.append({
                        "class_path": layer_map[name],
                        "config": self.config.get("filters", {})
                    })
            
            # COMPULSORY: Ensure MLFilterLayer is always active
            if "MLFilterLayer" not in [l.get("class_path", "").split(".")[-1] for l in layers_cfg]:
                logger.info("[BOOTSTRAP] Injecting compulsory MLFilterLayer into pipeline.")
                layers_cfg.append({
                    "class_path": layer_map["MLFilterLayer"],
                    "config": self.config.get("filters", {})
                })


        loaded_layers = []
        for l_cfg in layers_cfg:
            try:
                layer = ComponentRegistry.load_component(l_cfg["class_path"], config=l_cfg.get("config"))
                loaded_layers.append(layer)
            except Exception as le:
                logger.warning(f"Failed to load layer {l_cfg.get('class_path')}: {le}")

        self.filtration_engine = IGOFEngine(layers=loaded_layers)

        # 3. Load Strategies
        strat_cfg = pipeline_cfg.get("strategies", [])
        
        # --- LITE CONFIG SUPPORT ---
        if not strat_cfg:
            # Always ensure at least one strategy is active
            logger.info("[BOOTSTRAP] No strategy configured. Defaulting to SMCStrategy.")
            strat_cfg = [{
                "class_path": "support.strategies.smc_strategy.SMCStrategy",
                "config": self.config.get("trading", {})
            }]

        self.strategies = []
        for s_cfg in strat_cfg:
            try:
                strategy = ComponentRegistry.load_component(s_cfg["class_path"], config=s_cfg.get("config"))
                self.strategies.append(strategy)
            except Exception as se:
                logger.warning(f"Failed to load strategy {s_cfg.get('class_path')}: {se}")

        # 4. Load Risk Rules
        risk_cfg = pipeline_cfg.get("risk_rules", [])
        
        # --- LITE CONFIG SUPPORT ---
        if not risk_cfg:
             logger.info("[BOOTSTRAP] Using default UltraLowAccountRiskRule for capital preservation.")
             risk_cfg = [{
                 "class_path": "support.risk.ultra_low_risk.UltraLowAccountRiskRule",
                 "config": self.config.get("trading", {})
             }]

        self.risk_rules = []
        for r_cfg in risk_cfg:
            try:
                rule = ComponentRegistry.load_component(r_cfg["class_path"], config=r_cfg.get("config"))
                self.risk_rules.append(rule)
            except Exception as re:
                logger.warning(f"Failed to load risk rule {r_cfg.get('class_path')}: {re}")

        logger.info(f"Pipeline built successfully: {len(self.filtration_engine.layers)} layers, {len(self.strategies)} strategies.")

    # ──────────────────────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────────────────────

    def run_main_loop(self):
        """
        Main trading loop with Lite mode support, CLI Dashboard, regime gating,
        HTF direction alignment, account context injection, and news scalp path.
        """
        logger.info(f"Starting Modular Main Loop (Delay: {self.loop_delay}s)...")
        symbol = self.config.get("trading", {}).get("symbol", "XAUUSD")

        # ── Desktop Dashboard Sync Helper ────────────────────────────────────
        def _sync_desktop_state():
            if _state_exporter:
                acc     = current_state.get("account", {})
                market  = current_state.get("market",  {})
                sigs    = current_state.get("signals", [])
                last_sig = sigs[-1] if sigs else {}
                price    = market.get("price", 0.0)
                bias_raw = market.get("htf_bias", "NEUTRAL").upper()
                layer_list = []
                for lp in current_state.get("pipeline", []):
                    layer_list.append({
                        "name":   lp.get("name", ""),
                        "passed": lp.get("status", False),
                        "score":  lp.get("score",  0.0),
                        "reason": lp.get("reason", ""),
                    })
                conf_score = sum(l["score"] for l in layer_list)
                kz_name = ""
                for lp in layer_list:
                    if "Killzone" in lp["name"]:
                        kz_name = lp.get("reason", "")[:28]
                        break
                # Get the most recent strategy signal, even if it wasn't a trade (e.g. WAIT)
                # This ensures the dashboard doesn't look stuck on an old signal.
                strat_sig = current_state.get("current_strategy_signal", {})
                
                # Determine current Risk Tier from UltraLowAccountRiskRule
                risk_tier = "Standard"
                for rule in self.risk_rules:
                    if hasattr(rule, "get_risk_tier"):
                        risk_tier = rule.get_risk_tier(acc.get("equity", 0.0))
                        break

                _state_exporter.export({
                    "timestamp":        datetime.now(timezone.utc).isoformat(),
                    "symbol":           market.get("symbol", symbol),
                    "bias":             bias_raw,
                    "current_price":    price,
                    "signal_action":    strat_sig.get("action", "NONE"),
                    "entry_price":      strat_sig.get("price",  price),
                    "stop_loss":        strat_sig.get("sl",     0.0),
                    "take_profit":      strat_sig.get("tp",     0.0),
                    "lot_size":         strat_sig.get("lots",   0.01),
                    "execution_type":   strat_sig.get("execution_type", "MARKET"),
                    "confluence_score": conf_score,
                    "killzone_name":    kz_name,
                    "session_time":     "",
                    "rr_ratio":         "—",
                    "layers":           layer_list,
                    "last_trade":       last_sig,
                    "account_equity":   acc.get("equity",    0.0),
                    "account_balance":  acc.get("balance",   0.0),
                    "floating_pnl":     acc.get("floating_pnl", 0.0),
                    "open_trades_count":acc.get("total_positions", 0),
                    "open_positions":   acc.get("positions",       []),
                    "signals_generated":self._signals_count,
                    "pipeline_logs":    list(self._dashboard_logs),
                    "risk_tier":        risk_tier,
                    "active_warnings":  [],
                })
        # ───────────────────────────────────────────────────────────────────

        # ── Initial state ──────────────────────────────────────────────────────
        dashboard = None
        _default_bal = self.config.get("trading", {}).get("default_account_balance", 0.0)
        current_state = {
            "account": {
                "balance":         _default_bal,
                "equity":          0.0,
                "floating_pnl":    0.0,
                "daily_pnl":       0.0,
                "daily_loss_pct":  0.0,
                "daily_loss":      0.0,
                "positions":       [],
                "total_positions": 0,
            },
            "market": {
                "symbol":        symbol,
                "price":         0.0,
                "spread":        0.0,
                "htf_bias":      "NEUTRAL",
                "h1_bias":       "NEUTRAL",
                "regime":        "STABLE",
                "next_event":    "",
                "master_switch": True,
            },
            "pipeline":     [],
            "signals":      [],
            "news_events":  [],
        }

        # ── CLI Dashboard ──────────────────────────────────────────────────────
        # ── CLI Dashboard (Deactivated as per user request — GUI only) ─────────
        if False: # self.config.get("performance", {}).get("enable_cli_dashboard", True):
            from Engine.cli_dashboard import CLIDashboard
            from rich.live import Live
            dashboard = CLIDashboard()
            logger.info("CLI Dashboard enabled.")

        # ── Initial account sync ───────────────────────────────────────────────
        try:
            acc_info = self.data_provider.get_account_info()
            current_state["account"]["balance"]         = acc_info.get("balance", current_state["account"]["balance"])
            current_state["account"]["equity"]          = acc_info.get("equity", 0.0)
            current_state["account"]["positions"]       = acc_info.get("positions", [])
            current_state["account"]["total_positions"] = acc_info.get("total_positions", 0)
            current_state["account"]["floating_pnl"]    = round(acc_info.get("equity", 0.0) - acc_info.get("balance", 0.0), 2)
            
            self.last_balance_sync = time.time()
            login_id = acc_info.get("login", "Unknown")
            logger.info(f"Initial Account Sync: ${current_state['account']['balance']:,.2f} | Positions: {current_state['account']['total_positions']} (Account: {login_id})")
        except Exception as e:
            logger.error(f"Initial account sync failed: {e}")

        # ── Optional React dashboard API ───────────────────────────────────────
        perf_cfg = self.config.get("performance", {})
        if perf_cfg.get("enable_react_dashboard", False):
            self._start_dashboard_api(port=perf_cfg.get("react_dashboard_port", 3000))

        # ── ZMQ Bridge startup check ───────────────────────────────────────────
        if self.bridge and self.bridge.is_ready:
            logger.info("[BOOTSTRAP] ZMQBridge: ✓ PUB socket ready — signals will flow to HedgeEA")
            ea_alive = self.bridge.check_connection()
            if ea_alive:
                logger.info("[BOOTSTRAP] ZMQBridge: ✓ HedgeEA heartbeat OK — EA is running in MT5")
            else:
                logger.warning(
                    "[BOOTSTRAP] ZMQBridge: HedgeEA heartbeat did NOT respond. "
                    "Ensure HedgeEA.mq5 is attached to a chart in MT5. "
                    "Signals will be sent and buffered by ZMQ until EA connects."
                )
        elif self.bridge and not self.bridge.is_ready:
            logger.error(
                "[BOOTSTRAP] ZMQBridge: PUB socket NOT ready. "
                "Run: pip install pyzmq  then restart the engine."
            )
        else:
            logger.error("[BOOTSTRAP] ZMQBridge: bridge object is None — signals will be dropped.")

        # ── Main loop ──────────────────────────────────────────────────────────
        try:
            ctx = Live(dashboard.layout, refresh_per_second=4) if dashboard else nullcontext()
            with ctx:
                while True:
                    # ── FIX: Initialize signal variable at start of loop to avoid UnboundLocalError ──
                    signal = {"action": "WAIT"}

                    # 1. Check Master Switch (fast responsiveness)
                    try:
                        with open(self.config_path, 'r') as f:
                            latest_config = json.load(f)
                        master_on = latest_config.get("trading", {}).get("master_switch", True)
                    except Exception as e:
                        logger.error(f"Error reloading config: {e}")
                        master_on = True  # Default to ON if read fails

                    current_state["market"]["master_switch"] = master_on

                    if not master_on:
                        current_state["pipeline"] = []
                        current_state["market"]["htf_bias"] = "STANDBY"
                        if dashboard:
                            dashboard.update(current_state)
                        _sync_desktop_state()
                        time.sleep(1.0)  # Shorter pulse on standby for faster UI response
                        continue

                    # 2. Fetch market data (only when master is ON)
                    count = 10 if self.lite_mode else 100
                    market_snapshot = {
                        "symbol":      symbol,
                        "tick":        self.data_provider.get_tick_data(symbol),
                        "h4_candles":  self.data_provider.get_latest_candles(symbol, "H4",  count),
                        "h1_candles":  self.data_provider.get_latest_candles(symbol, "H1",  count),
                        "m15_candles": self.data_provider.get_latest_candles(symbol, "M15", count),
                        "m5_candles":  self.data_provider.get_latest_candles(symbol, "M5",  count),
                        "m1_candles":  self.data_provider.get_latest_candles(symbol, "M1",  count),
                    }

                    if not market_snapshot["m5_candles"] or not market_snapshot["tick"]:
                        if dashboard:
                            dashboard.update(current_state)
                        _sync_desktop_state()
                        time.sleep(self.loop_delay)
                        continue

                    tick = market_snapshot["tick"]
                    current_state["market"]["price"]  = tick.get("ask", 0.0)
                    current_state["market"]["bid"]    = tick.get("bid", 0.0)
                    current_state["market"]["ask"]    = tick.get("ask", 0.0)
                    current_state["market"]["spread"] = round((tick.get("ask", 0.0) - tick.get("bid", 0.0)) * 100, 1)

                    # 3. Run IGOF filtration
                    filt_res = self.filtration_engine.process_all_layers(market_snapshot)
                    self.emit_dashboard_msg(f"IGOF Filtration: {filt_res['action']} - Score: {filt_res.get('total_score',0):.1f}")

                    # Update pipeline status for dashboard
                    current_state["pipeline"] = []
                    for layer_res in filt_res.get("layer_results", []):
                        status_raw = layer_res["result"]["status"]
                        # Convert status string to boolean so dashboard correctly shows PASS/FAIL
                        passed = True if str(status_raw).upper() in ("PASS", "TRUE", "TRADE_ALLOWED") else False
                        
                        current_state["pipeline"].append({
                            "name":   layer_res["layer"],
                            "status": status_raw,
                            "passed": passed,
                            "score":  layer_res["result"].get("score", 0.0),
                            "reason": layer_res["result"].get("reason", ""),
                            "bias":   layer_res["result"].get("bias", "neutral"),
                        })
                        if not passed:
                            self.emit_dashboard_msg(f"  [-] {layer_res['layer']} BLOCKED: {layer_res['result'].get('reason')}")

                    # ── Extract HTF structural bias and regime context (ALWAYS EXTRACT for UI) ────
                    htf_bias          = "neutral"
                    news_scalp_signal = None
                    for layer_res in filt_res.get("layer_results", []):
                        layer_name   = layer_res.get("layer", "")
                        layer_result = layer_res.get("result", {})
                        if "Structure" in layer_name and "bias" in layer_result:
                            htf_bias = layer_result["bias"]
                        if "News" in layer_name and layer_result.get("scalp_signal"):
                            news_scalp_signal = layer_result["scalp_signal"]

                    current_state["market"]["htf_bias"] = htf_bias.upper()
                    current_state["market"]["h1_bias"]  = htf_bias.upper()
                    current_state["market"]["h4_bias"]  = htf_bias.upper()

                    # ── Regime from RiskManager ────────────────────────────────────
                    current_regime = self.risk_manager.state.get("current_regime", "STABLE")
                    current_state["market"]["regime"] = current_regime

                    # ── News calendar ──
                    for fl in self.filtration_engine.layers:
                        if "News" in fl.__class__.__name__:
                            if hasattr(fl, "get_todays_events"):
                                todays = fl.get_todays_events()
                                current_state["news_events"] = todays
                                now_utc = datetime.now(timezone.utc)
                                for ev in todays:
                                    try:
                                        et = datetime.fromisoformat(ev["time_utc"]).astimezone(timezone.utc)
                                        if et > now_utc and ev.get("impact", 0) >= 2:
                                            current_state["market"]["next_event"] = (
                                                et.strftime("%H:%M ") + ev.get("title", "")[:18]
                                            )
                                            break
                                    except Exception: pass
                            break

                    # 4. Generate Strategy Signal (ALWAYS UPDATE for UI visibility)
                    for strategy in self.strategies:
                        sig = strategy.generate_signal(market_snapshot)
                        current_state["current_strategy_signal"] = {
                            "action": sig.get("action", "WAIT"),
                            "price":  tick.get("ask", 0.0) if sig.get("direction") == "buy" else tick.get("bid", 0.0),
                            "sl":     sig.get("sl", 0.0),
                            "tp":     sig.get("tp", 0.0),
                            "lots":   sig.get("lots", 0.01),
                            "execution_type": sig.get("execution_type", "MARKET")
                        }
                        # We only treat it as "active" for the loop below if action is TRADE
                        signal = sig 

                    # 5. Filtration Action Gate
                    if filt_res["action"] != "TRADE_ALLOWED":
                        if dashboard: dashboard.update(current_state)
                        _sync_desktop_state()
                        time.sleep(self.loop_delay)
                        continue

                    if signal.get("action") == "TRADE":
                        self._signals_count += 1
                        self.emit_dashboard_msg(f"STRATEGY TRIGGER: {signal.get('direction','N/A').upper()} @ {tick.get('ask' if signal.get('direction')=='buy' else 'bid', 0.0):.2f}")

                        # ── FIX #4: HTF direction alignment gate ───────────────
                        signal_direction = signal.get("direction", "").lower()
                        if signal_direction == "buy":
                            mapped_direction = "bullish"
                        elif signal_direction == "sell":
                            mapped_direction = "bearish"
                        else:
                            mapped_direction = signal_direction

                        if htf_bias != "neutral" and mapped_direction:
                            if mapped_direction != htf_bias.lower():
                                logger.info(
                                    f"DIRECTION VETO: Signal={signal_direction.upper()} "
                                    f"conflicts with HTF bias={htf_bias.upper()} — skipped"
                                )
                                continue  # skip to next strategy; do not send to risk

                        # ── FIX #3: Inject live account context ───────────────
                        signal["current_equity"]       = (
                            current_state["account"].get("equity")
                            or current_state["account"].get("balance", 0.0)
                        )
                        signal["balance"]              = current_state["account"].get("balance", 0.0)
                        signal["daily_loss"]           = current_state["account"].get("daily_loss", 0.0)
                        signal["daily_start_balance"]  = current_state["account"].get("balance", 0.0)
                        signal["open_positions_count"] = len([
                            s for s in current_state.get("signals", [])
                            if s.get("action") == "TRADE"
                        ])

                        # 5. Check risk rules
                        all_risk_passed = True
                        for rule in self.risk_rules:
                            risk_res = rule.check_risk(signal)
                            if not risk_res.get("allowed", False):
                                logger.info(f"Trade denied by risk rule: {rule.__class__.__name__}")
                                all_risk_passed = False
                                break

                        if all_risk_passed:
                            # Enrich signal to full MT5-EA-compatible format
                            ea_signal = self._enrich_signal(
                                signal, tick, htf_bias,
                                risk_res=risk_res if "risk_res" in dir() else None,
                                symbol=symbol,
                            )
                            ea_signal["time"] = datetime.now().strftime("%H:%M:%S")

                            # ── Dry-run pipeline log ──────────────────
                            logger.info(
                                f"[PIPELINE] Signal enriched: "
                                f"action={ea_signal['action']}  "
                                f"symbol={ea_signal.get('symbol')}  "
                                f"price={ea_signal.get('price')}  "
                                f"sl={ea_signal.get('sl')}  "
                                f"lots={ea_signal.get('lots')}  "
                                f"exec={ea_signal.get('execution_type','MARKET')}"
                            )

                            # ── Send via ZMQ bridge (deduplicated) ────
                            sig_id = (
                                f"{ea_signal['action']}_"
                                f"{ea_signal.get('symbol')}_"
                                f"{ea_signal.get('price')}_"
                                f"{ea_signal.get('timestamp')}"
                            )
                            if sig_id not in self._sent_signal_ids:
                                if self.bridge and self.bridge.is_ready:
                                    sent = self.bridge.send_signal(ea_signal)
                                    if sent:
                                        self._sent_signal_ids.add(sig_id)
                                        # Keep the dedup set bounded
                                        if len(self._sent_signal_ids) > 500:
                                            self._sent_signal_ids = set(
                                                list(self._sent_signal_ids)[-250:]
                                            )
                                        logger.info(
                                            f"[PIPELINE] → Sent to HedgeEA: "
                                            f"action={ea_signal['action']} "
                                            f"@ {ea_signal.get('price')}"
                                        )
                                        self.emit_dashboard_msg(f"✓ SENT TO HEDGEEA: {ea_signal['action']} @ {ea_signal.get('price')}")

                                        # ── FIX: Append to dashboard signals on the SENT path, not duplicate path ──
                                        current_state["signals"].append(ea_signal)
                                        if len(current_state["signals"]) > 50:
                                            current_state["signals"] = current_state["signals"][-50:]
                                    else:
                                        logger.warning(
                                            "[PIPELINE] Bridge send failed — "
                                            "check pyzmq install and EA connection"
                                        )
                                        self.emit_dashboard_msg("✗ ERROR: ZMQ Send Failed")
                                else:
                                    logger.error(
                                        "[PIPELINE] Bridge not ready — signal dropped. "
                                        "Run: pip install pyzmq"
                                    )
                            else:
                                logger.debug(f"[PIPELINE] Duplicate signal suppressed: {sig_id}")

                        # ── News scalp path (bypasses IGOF but not risk) ───────────────
                        if news_scalp_signal and self.config.get("pipeline", {}).get("enable_news_scalp", False):
                            scalp = {
                                "action":               "TRADE",
                                "direction":            news_scalp_signal.get("direction", "").lower(),
                                "type":                 "NEWS_SCALP",
                                "sl_atr_mult":          news_scalp_signal.get("sl_atr_mult", 1.5),
                                "tp_rr":                news_scalp_signal.get("tp_rr", 1.5),
                                "max_bars":             news_scalp_signal.get("max_bars", 3),
                                "trigger":              news_scalp_signal.get("trigger", ""),
                                "current_equity":       (
                                    current_state["account"].get("equity")
                                    or current_state["account"].get("balance", 0.0)
                                ),
                                "balance":              current_state["account"].get("balance", 0.0),
                                "daily_loss":           current_state["account"].get("daily_loss", 0.0),
                                "daily_start_balance":  current_state["account"].get("balance", 0.0),
                                "open_positions_count": len([
                                    s for s in current_state.get("signals", [])
                                    if s.get("action") == "TRADE"
                                ]),
                            }
                            scalp_risk_ok = True
                            for rule in self.risk_rules:
                                r = rule.check_risk(scalp)
                                if not r.get("allowed", False):
                                    scalp_risk_ok = False
                                    break
                            if scalp_risk_ok:
                                ea_scalp = self._enrich_signal(
                                    scalp, tick, htf_bias, symbol=symbol
                                )
                                ea_scalp["time"] = datetime.now().strftime("%H:%M:%S")
                                logger.info(
                                    f"[NEWS SCALP] action={ea_scalp['action']} "
                                    f"trigger={ea_scalp.get('trigger')} "
                                    f"price={ea_scalp.get('price')}"
                                )
                                scalp_id = (
                                    f"SCALP_{ea_scalp['action']}_"
                                    f"{ea_scalp.get('price')}_"
                                    f"{ea_scalp.get('timestamp')}"
                                )
                                if scalp_id not in self._sent_signal_ids:
                                    if self.bridge and self.bridge.is_ready:
                                        if self.bridge.send_signal(ea_scalp):
                                            self._sent_signal_ids.add(scalp_id)

                                current_state["signals"].append(ea_scalp)
                                if len(current_state["signals"]) > 50:
                                    current_state["signals"] = current_state["signals"][-50:]

                    else:
                        # Filtration blocked — reset bias/regime for dashboard
                        current_state["market"]["htf_bias"] = "NEUTRAL"
                        current_state["market"]["h1_bias"]  = "NEUTRAL"
                        current_regime = self.risk_manager.state.get("current_regime", "STABLE")
                        current_state["market"]["regime"] = current_regime

                    # 6. Periodic account sync (every 30 s)
                    if time.time() - self.last_balance_sync > 30:
                        try:
                            acc_info = self.data_provider.get_account_info()
                            balance  = acc_info.get("balance", 0.0)
                            equity   = acc_info.get("equity", 0.0)
                            pos      = acc_info.get("positions", [])
                            total    = acc_info.get("total_positions", 0)
                            
                            self.db.set_state("account_balance", balance)
                            self.db.set_state("balance_last_sync", time.time())
                            
                            current_state["account"]["balance"]         = balance
                            current_state["account"]["equity"]          = equity
                            current_state["account"]["positions"]       = pos
                            current_state["account"]["total_positions"] = total
                            current_state["account"]["floating_pnl"]    = round(equity - balance, 2)
                            
                            self.last_balance_sync = time.time()
                            logger.info(f"Account Sync: Balance=${balance:,.2f} | Equity=${equity:,.2f} | Positions={total}")
                        except Exception as e:
                            logger.error(f"Failed to sync account balance: {e}")

                    # Sync shared state for React dashboard endpoint
                    self._current_state = current_state

                    # Update CLI Dashboard
                    if dashboard:
                        dashboard.update(current_state)

                    # ── Write engine_state.json for tkinter desktop dashboard ─
                    _sync_desktop_state()

                    time.sleep(self.loop_delay)

        except KeyboardInterrupt:
            logger.info("System shutting down...")
            if hasattr(self.data_provider, 'shutdown'):
                self.data_provider.shutdown()
            if self.bridge:
                self.bridge.close()
            sys.exit(0)
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            if hasattr(self.data_provider, 'shutdown'):
                self.data_provider.shutdown()
            if self.bridge:
                self.bridge.close()
            sys.exit(1)

    # ──────────────────────────────────────────────────────────────────────────
    # Signal enrichment — builds a fully MT5-EA-compatible JSON signal dict
    # ──────────────────────────────────────────────────────────────────────────

    def _enrich_signal(self, signal: Dict, tick: Dict, htf_bias: str,
                       risk_res: Dict = None, symbol: str = "XAUUSD") -> Dict:
        """
        Convert an internal strategy signal into the exact JSON shape that
        HedgeEA.mq5 ParseSignal() expects:

          Required by EA:
            action          — LONG | SHORT | CLOSE_LONG | CLOSE_SHORT
            symbol          — broker symbol string (e.g. XAUUSD)
            price           — fill price (ask for LONG, bid for SHORT)
            sl              — stop loss price (must be > 0)
            tp              — take profit price
            lots            — lot size (> 0)
            bias            — BULLISH | BEARISH | NEUTRAL  (EA field: bias / desc fallback)
            timestamp       — unix seconds (integer)
            execution_type  — MARKET | LIMIT
            limit_price     — limit entry price (defaults to price for MARKET)
            confluence_score — 0.0–1.0  (EA reads key "confluence_score")

        Internal fields used by risk layer (stripped by EA, harmless to include):
            current_equity, balance, daily_loss, daily_start_balance,
            open_positions_count, direction, score, type, trigger
        """
        enriched = dict(signal)  # shallow copy — preserve all strategy fields

        # ── Action: map internal TRADE + direction → EA action codes ──────────
        direction  = enriched.get("direction", "").lower()
        raw_action = enriched.get("action", "")

        if raw_action == "SELL" or direction == "sell":
            enriched["action"] = "SHORT"
        elif raw_action in ("TRADE", "BUY") or direction == "buy":
            enriched["action"] = "LONG"
        elif raw_action in ("CLOSE_LONG", "CLOSE_SHORT",
                            "REVERSE_TO_LONG", "REVERSE_TO_SHORT"):
            pass  # pass through
        else:
            # Last-resort inference from direction field
            if direction == "sell":
                enriched["action"] = "SHORT"
            elif direction == "buy":
                enriched["action"] = "LONG"

        # ── Symbol ────────────────────────────────────────────────────────────
        enriched.setdefault("symbol", symbol)

        # ── Price: LONG fills at ask, SHORT fills at bid (MT5 convention) ─────
        if tick:
            if enriched["action"] == "LONG":
                enriched.setdefault("price", tick.get("ask", 0.0))
            elif enriched["action"] == "SHORT":
                enriched.setdefault("price", tick.get("bid", 0.0))
            else:
                enriched.setdefault("price", tick.get("ask", tick.get("close", 0.0)))
        else:
            enriched.setdefault("price", 0.0)

        price = enriched.get("price", 0.0)

        # ── SL / TP: use risk_res if available, else ATR-based fixed defaults ─
        if risk_res:
            if "sl" in risk_res:
                enriched["sl"] = risk_res["sl"]
            if "tp" in risk_res:
                enriched["tp"] = risk_res["tp"]

        if price > 0:
            if enriched["action"] == "LONG":
                enriched.setdefault("sl", round(price - 0.50, 2))   # $0.50 Gold default
                enriched.setdefault("tp", round(price + 1.00, 2))
            elif enriched["action"] == "SHORT":
                enriched.setdefault("sl", round(price + 0.50, 2))
                enriched.setdefault("tp", round(price - 1.00, 2))
        else:
            enriched.setdefault("sl", 0.0)
            enriched.setdefault("tp", 0.0)

        # ── Lots: prefer risk_res enforced_lots, else default ─────────────────
        if risk_res and "enforced_lots" in risk_res:
            enriched["lots"] = risk_res["enforced_lots"]
        else:
            enriched.setdefault("lots", 0.01)

        # ── bias: EA accepts BULLISH/BEARISH/NEUTRAL; also reads "desc" as fallback
        enriched.setdefault("bias", htf_bias.upper() if htf_bias else "NEUTRAL")

        # ── timestamp, execution_type, limit_price ────────────────────────────
        enriched.setdefault("timestamp",      int(time.time()))
        enriched.setdefault("execution_type", "MARKET")
        enriched.setdefault("limit_price",    enriched.get("price", 0.0))

        # ── confluence_score: EA ParseSignal reads key "confluence_score" ──────
        # score from strategy layers is 0–100; EA expects 0.0–1.0
        enriched.setdefault(
            "confluence_score",
            round(enriched.get("score", 0.0) / 100.0, 4)
        )

        return enriched

    # ──────────────────────────────────────────────────────────────────────────
    # React dashboard API
    # ──────────────────────────────────────────────────────────────────────────

    def _start_dashboard_api(self, port: int = 3000):
        """
        Starts a lightweight FastAPI server in a background daemon thread
        so the React dashboard can poll /dashboard-state for live engine data.

        Runs on port+1 (default 3001) to avoid conflicting with the data feed
        server on port 8000. Falls back to stdlib http.server if FastAPI/uvicorn
        are not installed so the engine always starts — dashboard is optional.
        """
        state_ref = self

        def _serve():
            try:
                import json as _json
                from fastapi import FastAPI
                from fastapi.middleware.cors import CORSMiddleware
                import uvicorn

                app = FastAPI(title="HedgeEA Dashboard API", docs_url=None)
                app.add_middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_methods=["GET", "POST"],
                    allow_headers=["*"],
                )

                @app.get("/dashboard-state")
                def dashboard_state():
                    return state_ref._current_state

                @app.get("/health")
                def health():
                    return {"status": "ok", "engine": "HedgeEA v6.2"}

                @app.post("/master-switch")
                def master_switch(payload: dict):
                    """Toggle the master switch from the React dashboard."""
                    try:
                        new_val  = bool(payload.get("master_switch", True))
                        cfg_path = state_ref.config_path
                        with open(cfg_path, "r") as f:
                            cfg = _json.load(f)
                        cfg.setdefault("trading", {})["master_switch"] = new_val
                        with open(cfg_path, "w") as f:
                            _json.dump(cfg, f, indent=4)
                        return {"ok": True, "master_switch": new_val}
                    except Exception as ex:
                        return {"ok": False, "error": str(ex)}

                logger.info(f"React dashboard API listening on http://localhost:{port + 1}")
                uvicorn.run(app, host="0.0.0.0", port=port + 1, log_level="error")

            except ImportError:
                # FastAPI/uvicorn not installed — fall back to stdlib JSON server
                import json as _json
                from http.server import BaseHTTPRequestHandler, HTTPServer

                class _Handler(BaseHTTPRequestHandler):
                    def do_GET(self):
                        if self.path in ("/dashboard-state", "/health"):
                            data = _json.dumps(state_ref._current_state).encode()
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                        else:
                            self.send_response(404)
                            self.end_headers()

                    def log_message(self, *args):
                        pass  # silence stdlib request logs

                srv = HTTPServer(("0.0.0.0", port + 1), _Handler)
                logger.info(f"React dashboard API (stdlib) listening on http://localhost:{port + 1}")
                srv.serve_forever()

            except Exception as e:
                logger.error(f"Dashboard API failed to start: {e}")

        t = threading.Thread(target=_serve, daemon=True, name="DashboardAPI")
        t.start()


if __name__ == "__main__":
    config_file = BASE_DIR / "config" / "trading_params_lite.json"
    bootstrapper = ModularBootstrapper(config_file)
    bootstrapper.build_pipeline()
    bootstrapper.run_main_loop()
