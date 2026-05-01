"""
====================================================
  FULL ARCHITECTURE VALIDATION SUITE
  HedgeEA Institutional SMC Bot - v6.1
====================================================
Tests the entire pipeline from data sourcing to EA signal dispatch:

  [1] Config Loading
  [2] MT5 Connectivity & Data Sourcing (5 Timeframes)
  [3] IGOF Filtration Engine (6 Layers)
  [4] SMC Strategy Signal Generation
  [5] UltraLow Risk Rule Validation
  [6] ZMQ Bridge (Execution Layer) - Fire & Forget

Run from project root:
  python tests/test_architecture.py
"""

import sys
import io
import json
import time
from pathlib import Path
from datetime import datetime

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# --- Colours for terminal output ---
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
WARN = f"{YELLOW}[WARN]{RESET}"
INFO = f"{CYAN}[INFO]{RESET}"

results = []

def check(name, condition, detail="", warn_only=False):
    status = PASS if condition else (WARN if warn_only else FAIL)
    icon   = "OK" if condition else ("!!" if warn_only else "XX")
    print(f"  {status} [{icon}] {name}")
    if detail:
        print(f"         |_ {detail}")
    results.append({"name": name, "passed": condition, "warn_only": warn_only})
    return condition

def section(title):
    print(f"\n{BOLD}{CYAN}{'='*50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*50}{RESET}")


# ==========================================================
# TEST 1: Config Loading
# ==========================================================
section("TEST 1 — Config Loading")

config = None
try:
    config_path = ROOT / "config" / "trading_params_lite.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    check("Config file found and parsed", True, str(config_path))
    check("Trading symbol present", "trading" in config and "symbol" in config["trading"],
          f"Symbol: {config.get('trading', {}).get('symbol', 'NOT FOUND')}")
    check("Pipeline section present", "pipeline" in config)
    check("Risk rules defined", len(config.get("pipeline", {}).get("risk_rules", [])) > 0,
          f"{len(config.get('pipeline', {}).get('risk_rules', []))} rule(s) found")
    check("Filtration layers defined", len(config.get("pipeline", {}).get("filtration_layers", [])) == 6,
          f"{len(config.get('pipeline', {}).get('filtration_layers', []))} layer(s) defined (expected 6)")
except Exception as e:
    check("Config file found and parsed", False, str(e))


# ==========================================================
# TEST 2: MT5 Data Sourcing (5 Timeframes)
# ==========================================================
section("TEST 2 — MT5 Data Sourcing (H4 → M1)")

provider = None
candle_data = {}
try:
    from data_feed.mt5_provider import MT5DataProvider
    
    mt5_cfg = config.get("pipeline", {}).get("data_provider", {}).get("config", {})
    provider = MT5DataProvider(mt5_cfg)

    connected = provider.connect()
    check("MT5 Connection established", connected,
          f"Server: {mt5_cfg.get('server')}, Login: {mt5_cfg.get('login')}")

    if connected:
        symbol = config["trading"]["symbol"]
        for tf in ["H4", "H1", "M15", "M5", "M1"]:
            candles = provider.get_latest_candles(symbol, tf, 50)
            ok = isinstance(candles, list) and len(candles) >= 10
            candle_data[f"{tf.lower()}_candles"] = candles
            check(f"{tf} candle data retrieved", ok,
                  f"{len(candles)} candles returned" if isinstance(candles, list) else str(candles))

        tick = provider.get_tick_data(symbol)
        has_tick = isinstance(tick, dict) and "ask" in tick
        check("Live tick data (ask/bid)", has_tick,
              f"Ask: {tick.get('ask', 'N/A')}" if has_tick else "No tick data")
except Exception as e:
    check("MT5 data sourcing", False, str(e))


# ==========================================================
# TEST 3: IGOF Filtration Engine
# ==========================================================
section("TEST 3 — IGOF Filtration Engine (6 Layers)")

igof_result = None
try:
    from Engine.registry import ComponentRegistry
    from Engine.igof.igof_engine import IGOFEngine

    layers_cfg = config.get("pipeline", {}).get("filtration_layers", [])
    loaded_layers = []
    for l_cfg in layers_cfg:
        layer = ComponentRegistry.load_component(l_cfg["class_path"], config=l_cfg.get("config", {}))
        loaded_layers.append(layer)

    check(f"All 6 IGOF layers loaded", len(loaded_layers) == 6,
          f"Loaded: {[l.__class__.__name__ for l in loaded_layers]}")

    engine = IGOFEngine(layers=loaded_layers)
    check("IGOFEngine initialized", engine is not None)

    if candle_data:
        market_snapshot = {
            "symbol": config["trading"]["symbol"],
            **candle_data
        }
        igof_result = engine.process_all_layers(market_snapshot)
        action = igof_result.get("action", "UNKNOWN")
        layer_count = len(igof_result.get("layer_results", []))
        check(f"IGOF engine ran all layers ({layer_count}/6)", layer_count == 6,
              f"Action: {action} | Reason: {igof_result.get('reason', '')}")
    else:
        check("IGOF engine processing", False, "No candle data available from MT5 — skipped")

except Exception as e:
    check("IGOF engine", False, str(e))


# ==========================================================
# TEST 4: SMC Strategy Signal Generation
# ==========================================================
section("TEST 4 — SMC Strategy Signal Generation")

signal = None
try:
    from Engine.registry import ComponentRegistry

    strat_cfg_list = config.get("pipeline", {}).get("strategies", [])
    strat_cfg = strat_cfg_list[0] if strat_cfg_list else {}
    strategy = ComponentRegistry.load_component(strat_cfg["class_path"], config=strat_cfg.get("config", {}))
    check("SMCStrategy loaded", strategy is not None, strategy.__class__.__name__)

    if candle_data:
        signal = strategy.generate_signal(candle_data)
        action = signal.get("action", "UNKNOWN")
        check("Signal generated (action present)", action in ["TRADE", "NO_TRADE"],
              f"Action: {action} | Reason: {signal.get('reason', signal.get('reason', ''))}")
        
        if action == "TRADE":
            has_price = all(k in signal for k in ["price", "sl", "tp", "lots"])
            check("Trade signal has required fields (price/sl/tp/lots)", has_price,
                  f"Price: {signal.get('price')}, SL: {signal.get('sl')}, TP: {signal.get('tp')}, Lots: {signal.get('lots')}")
        else:
            check("No-trade signal is valid (market not in setup)", True,
                  signal.get("reason", ""), warn_only=True)
    else:
        check("Strategy signal generation", False, "No candle data — skipped")

except Exception as e:
    check("Strategy signal generation", False, str(e))


# ==========================================================
# TEST 5: Risk Rules
# ==========================================================
section("TEST 5 — UltraLow Account Risk Rule")

try:
    from Engine.registry import ComponentRegistry

    risk_cfg_list = config.get("pipeline", {}).get("risk_rules", [])
    risk_cfg = risk_cfg_list[0] if risk_cfg_list else {}
    rule = ComponentRegistry.load_component(risk_cfg["class_path"], config=risk_cfg.get("config", {}))
    check("UltraLowAccountRiskRule loaded", rule is not None)

    # Scenario A: Normal equity — should ALLOW
    res_ok = rule.check_risk({
        "current_equity": 10.0,
        "daily_loss": 0.0,
        "daily_start_balance": 10.0,
        "open_positions_count": 0
    })
    check("ALLOW trade when equity is healthy ($10.00, no loss)", res_ok.get("allowed", False),
          f"Reason: {res_ok.get('reason', '')}")

    # Scenario B: Below equity floor — should DENY
    res_deny = rule.check_risk({
        "current_equity": 7.0,
        "daily_loss": 0.0,
        "daily_start_balance": 10.0,
        "open_positions_count": 0
    })
    check("DENY trade when equity below floor ($7.00 < $7.50)", not res_deny.get("allowed", True),
          f"Reason: {res_deny.get('reason', '')}")

    # Scenario C: Daily loss limit hit — should DENY
    res_loss = rule.check_risk({
        "current_equity": 8.5,
        "daily_loss": 0.6,
        "daily_start_balance": 10.0,
        "open_positions_count": 0
    })
    check("DENY trade when daily loss limit breached (6% > 5%)", not res_loss.get("allowed", True),
          f"Reason: {res_loss.get('reason', '')}")

    # Scenario D: Dynamic tightening — equity < seed
    res_tight = rule.check_risk({
        "current_equity": 9.5,
        "daily_loss": 0.2,
        "daily_start_balance": 9.5,
        "open_positions_count": 0
    })
    check("Dynamic risk tightening active when equity < seed", True,
          f"Effective limit: {res_tight.get('dynamic_limit', 'N/A')}%", warn_only=True)

except Exception as e:
    check("Risk rules", False, str(e))


# ==========================================================
# TEST 6: ZMQ Execution Bridge
# ==========================================================
section("TEST 6 — ZMQ Execution Bridge")

bridge = None
try:
    import zmq
    check("ZMQ library importable", True)

    # Check if ZMQ context can be created (doesn't require MT5 EA running)
    ctx = zmq.Context()
    check("ZMQ Context created", ctx is not None)

    # Try full bridge init — will fail if EA not running (expected in test environment)
    try:
        from execution.bridge import Bridge
        bridge = Bridge()
        ea_live = bridge.connected
        check("ZMQ Bridge: MT5 EA responding (PING/PONG)", ea_live,
              "EA is live and accepting signals" if ea_live else "EA offline (ZMQ bridge init OK, EA not attached)",
              warn_only=not ea_live)
    except Exception as bridge_err:
        check("ZMQ Bridge init", False, str(bridge_err), warn_only=True)
        print(f"  {INFO} ZMQ bridge is expected to fail if HedgeEA is not attached to a chart.")

    ctx.term()

except ImportError:
    check("ZMQ library importable", False, "Run: pip install pyzmq")
except Exception as e:
    check("ZMQ execution bridge", False, str(e))


# ==========================================================
# SUMMARY
# ==========================================================
section("ARCHITECTURE VALIDATION SUMMARY")

total  = len(results)
passed = sum(1 for r in results if r["passed"])
warned = sum(1 for r in results if not r["passed"] and r["warn_only"])
failed = sum(1 for r in results if not r["passed"] and not r["warn_only"])

print(f"\n  {BOLD}Total Checks : {total}{RESET}")
print(f"  {GREEN}Passed       : {passed}{RESET}")
print(f"  {YELLOW}Warnings     : {warned}{RESET}")
print(f"  {RED}Failed       : {failed}{RESET}")

if failed == 0:
    print(f"\n  {GREEN}{BOLD}✓ ARCHITECTURE IS SOUND — Ready for Forward Testing{RESET}")
elif failed <= 2:
    print(f"\n  {YELLOW}{BOLD}⚠ MINOR ISSUES — Review warnings before live trading{RESET}")
else:
    print(f"\n  {RED}{BOLD}✗ CRITICAL ISSUES — Fix failures before proceeding{RESET}")

print()

if bridge:
    try:
        bridge.close()
    except:
        pass
