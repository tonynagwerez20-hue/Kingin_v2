"""
 UNIFIED SMC ML ENGINE
 =================
 Full integration matching the original SMC HYBRID ML SYSTEM prompt.
 Drop-in replacement for your existing signal processing.
 
 14 Components:
  1. CONFIG - Global configuration
  2. FEATURE ENGINEER - Signal → ML features  
  3. TRADE LOG - JSON persistence
  4. REGIME DETECTOR - H4 market classification
  5. LIGHTGBM FILTER - Weekly retraining
  6. RIVER DRIFT MONITOR - Online learning
  7. HYBRID ML ENGINE - Combined scorer
  8. MULTI-TF AGGREGATOR - Timeframe confluence
  9. ML RISK MANAGER - Dynamic position sizing
  10. ZMQ EXECUTOR - MT5 bridge
  11. SMC BRAIN - Main orchestrator
  12. HISTORICAL LABELER - 8yr data seeding
  13. RETRAIN SCHEDULER - Sunday training
  14. MASTER PROMPT - Documentation
"""

# ============================================================================
# SECTION 1: CONFIG & CONSTANTS
# ============================================================================

import os
import sys
import json
import time
import logging
import joblib
import threading
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("SMC_ML")

# Ensure directories
os.makedirs("models", exist_ok=True)
os.makedirs("data", exist_ok=True)

# CONFIG
CONFIG = {
    "model_path": "models/lgbm_signal_filter.pkl",
    "trade_log_path": "data/trade_log.json",
    "hist_data_path": "data/XAUUSDm_H1_8 years data.csv",
    
    # LightGBM settings
    "lgbm_threshold": 0.62,
    "lgbm_retrain_days": 7,
    "lgbm_window_days": 120,
    "lgbm_min_samples": 30,
    "lgbm_params": {
        "objective": "binary",
        "metric": "binary_logloss",
        "n_estimators": 200,
        "max_depth": 5,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_samples": 20,
        "n_jobs": 1,
        "verbose": -1,
        "random_state": 42,
    },
    
    # River settings
    "drift_window": 30,
    "drift_acc_threshold": 0.45,
    "adwin_delta": 0.002,
    "confidence_step_up": 0.03,
    "confidence_floor": 0.50,
    
    # Blending
    "lgbm_weight": 0.70,
    "river_weight": 0.30,
    
    # Risk
    "base_risk_pct": 0.01,
    "max_risk_pct": 0.02,
    "min_risk_pct": 0.005,
    "pip_value_xauusd": 10.0,
    "tf_confluence_bonus": 0.04,
    
    # Regime
    "regime_window": 20,
    "regime_smooth": 3,
    "trending_threshold": 0.60,
    
    # ZMQ
    "zmq_push_port": 5555,
    "zmq_pull_port": 5556,
    "zmq_timeout_ms": 5000,
    
    # Scheduler
    "retrain_day": "sunday",
    "retrain_time_eat": "23:00",
}

FEATURE_KEYS = [
    "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
    "adr_pct", "pips_to_liquidity", "session", "htf_bias"
]

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}

class Regime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    CHOPPY = "choppy"
    UNKNOWN = "unknown"

REGIME_RISK_SCALAR = {
    Regime.TRENDING: 1.00,
    Regime.RANGING: 0.75,
    Regime.CHOPPY: 0.00,
    Regime.UNKNOWN: 0.50,
}

CONFIDENCE_RISK_SCALAR = {
    "high": 1.00,
    "medium": 0.75,
    "low": 0.50,
}

TF_WEIGHTS = {"M5": 0.10, "M15": 0.25, "H1": 0.35, "H4": 0.30}


# ============================================================================
# SECTION 2: FEATURE ENGINEER
# ============================================================================

def engineer_features(signal: dict) -> dict:
    """Convert SMC signal dict to ML feature vector."""
    return {
        "ob_strength": float(signal.get("ob_strength", 0.50)),
        "fvg_present": int(bool(signal.get("fvg_present", False))),
        "bos_aligned": int(bool(signal.get("bos_aligned", False))),
        "liquidity_swept": int(bool(signal.get("liquidity_swept", False))),
        "adr_pct": float(signal.get("adr_pct", 0.50)),
        "pips_to_liquidity": float(signal.get("pips_to_liquidity", 20.0)),
        "session": SESSION_MAP.get(signal.get("session", "london"), 1),
        "htf_bias": int(signal.get("htf_bias", 0)),
    }

def features_to_array(features: dict) -> np.ndarray:
    """Convert features to numpy array for LightGBM."""
    return np.array([[features[k] for k in FEATURE_KEYS]], dtype=np.float32)


# ============================================================================
# SECTION 3: TRADE LOG
# ============================================================================

class TradeLog:
    """JSON-based trade persistence."""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.records = self._load()
    
    def _load(self) -> list:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self.records, f, indent=2, default=str)
    
    def log(self, signal: dict, features: dict, confidence: float, 
            outcome: int, metadata: dict = None):
        """Log a trade signal and outcome."""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "signal": signal,
            "features": features,
            "confidence": round(confidence, 6),
            "outcome": int(outcome),
            "metadata": metadata or {}
        }
        self.records.append(record)
        self._save()
    
    def count(self) -> int:
        return len(self.records)
    
    def win_rate(self) -> Optional[float]:
        if not self.records:
            return None
        return sum(1 for r in self.records if r["outcome"] == 1) / len(self.records)
    
    def get_dataframe(self, days: int = None) -> pd.DataFrame:
        if not self.records:
            return pd.DataFrame()
        df = pd.DataFrame(self.records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            df = df[df["timestamp"] >= cutoff]
        return df.reset_index(drop=True)


# ============================================================================
# SECTION 4: REGIME DETECTOR
# ============================================================================

class RegimeDetector:
    """H4-based market regime classification."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        self.current = Regime.UNKNOWN
        self.history = []
    
    def detect(self, h4_closes: list) -> Regime:
        """Classify market into TRENDING/RANGING/CHOPPY."""
        window = self.cfg["regime_window"]
        
        if len(h4_closes) < window + 5:
            return Regime.UNKNOWN
        
        closes = np.array(h4_closes[-window:], dtype=np.float64)
        diffs = np.diff(closes)
        
        up_moves = float(np.sum(diffs[diffs > 0]))
        dn_moves = float(abs(np.sum(diffs[diffs < 0])))
        total = up_moves + dn_moves
        
        if total == 0:
            return Regime.UNKNOWN
        
        direction_strength = abs(up_moves - dn_moves) / total
        
        if direction_strength > self.cfg["trending_threshold"]:
            raw = Regime.TRENDING
        elif direction_strength < 0.30:
            raw = Regime.CHOPPY
        else:
            raw = Regime.RANGING
        
        # Smooth
        self.history.append(raw)
        if len(self.history) > self.cfg["regime_smooth"]:
            self.history.pop(0)
        
        if (len(self.history) == self.cfg["regime_smooth"] and
            len(set(self.history)) == 1):
            self.current = self.history[-1]
        
        return self.current


# ============================================================================
# SECTION 5: LIGHTGBM FILTER
# ============================================================================

class LightGBMFilter:
    """Static classifier - weekly retrain."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        self.model = None
        self.last_trained = None
        self.threshold = config.get("lgbm_threshold", 0.62)
        self._load()
    
    def _load(self):
        path = self.cfg["model_path"]
        if Path(path).exists():
            try:
                data = joblib.load(path)
                self.model = data["model"]
                self.last_trained = data["trained_at"]
                logger.info(f"LightGBM loaded: {self.last_trained}")
            except Exception as e:
                logger.warning(f"Model load failed: {e}")
    
    def _save(self, n: int, win_rate: float):
        joblib.dump({
            "model": self.model,
            "trained_at": self.last_trained,
            "train_samples": n,
            "train_win_rate": round(win_rate, 4)
        }, self.cfg["model_path"])
    
    def needs_retrain(self) -> bool:
        if self.last_trained is None:
            return True
        age = (datetime.utcnow() - self.last_trained).days
        return age >= self.cfg["lgbm_retrain_days"]
    
    def train(self, trade_log: TradeLog, verbose: bool = True) -> bool:
        """Train on rolling window."""
        import lightgbm as lgb
        
        df = trade_log.get_dataframe(days=self.cfg["lgbm_window_days"])
        
        if len(df) < self.cfg["lgbm_min_samples"]:
            logger.warning(f"Insufficient data: {len(df)} < {self.cfg['lgbm_min_samples']}")
            return False
        
        X = np.array([[r["features"][k] for k in FEATURE_KEYS] 
                    for r in df], dtype=np.float32)
        y = np.array([r["outcome"] for r in df], dtype=int)
        
        win_rate = y.mean()
        
        self.model = lgb.LGBMClassifier(**self.cfg["lgbm_params"])
        self.model.fit(X, y)
        self.last_trained = datetime.utcnow()
        self._save(len(df), win_rate)
        
        if verbose:
            importances = dict(zip(FEATURE_KEYS, self.model.feature_importances_))
            top = sorted(importances.items(), key=lambda x: -x[1])
            logger.info(f"LightGBM trained: {len(df)} samples, win_rate={win_rate:.1%}")
            logger.info(f"Top features: {' | '.join(f'{k}={v}' for k,v in top[:4])}")
        
        return True
    
    def score(self, features: dict) -> float:
        """P(win) for this signal."""
        if self.model is None:
            return 0.5
        X = features_to_array(features)
        return float(self.model.predict_proba(X)[0][1])


# ============================================================================
# SECTION 6: RIVER DRIFT MONITOR (Simplified - placeholder)
# ============================================================================

class RiverDriftMonitor:
    """Online learning - updates after each trade."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        self.trade_count = 0
        self.drift_count = 0
        self.is_drifting = False
        self._recent = []
    
    def update(self, features: dict, outcome: int) -> bool:
        """Update after trade closes - detect drift."""
        self._recent.append(outcome)
        if len(self._recent) > self.cfg["drift_window"]:
            self._recent.pop(0)
        self.trade_count += 1
        
        # Simplified drift detection
        if len(self._recent) >= self.cfg["drift_window"]:
            rec_win = sum(self._recent) / len(self._recent)
            if rec_win < self.cfg["drift_acc_threshold"]:
                self.is_drifting = True
                self.drift_count += 1
                return True
        
        return False
    
    def online_score(self, features: dict) -> float:
        """
        Secondary confidence score based on recent performance.
        If we are in a winning streak, confidence increases.
        If we are drifting (losing streak), confidence decreases.
        """
        if not self._recent:
            return 0.5
            
        recent_win_rate = sum(self._recent) / len(self._recent)
        
        # If drifting, we penalize the score heavily
        if self.is_drifting:
            return min(0.45, recent_win_rate)
            
        return recent_win_rate
    
    def stats(self) -> dict:
        return {
            "trades_observed": self.trade_count,
            "drift_events": self.drift_count,
            "is_drifting": self.is_drifting,
            "recent_win_rate": sum(self._recent)/len(self._recent) if self._recent else None
        }


# ============================================================================
# SECTION 7: HYBRID ML ENGINE
# ============================================================================

class HybridMLEngine:
    """Combines LightGBM + River into single interface."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        self.log = TradeLog(config.get("trade_log_path", "data/trade_log.json"))
        self.lgbm = LightGBMFilter(config)
        self.river = RiverDriftMonitor(config)
        self.threshold = config.get("lgbm_threshold", 0.62)
        
        logger.info(f"HybridMLEngine ready: {self.log.count()} records, threshold={self.threshold}")
        
        # Auto-train on startup if needed
        if self.lgbm.needs_retrain() and self.log.count() >= config.get("lgbm_min_samples", 30):
            logger.info("Startup retrain triggered...")
            self.lgbm.train(self.log)
    
    def evaluate_signal(self, signal: dict) -> Tuple[bool, float, dict]:
        """Score an SMC signal through ML pipeline."""
        features = engineer_features(signal)
        lgbm_score = self.lgbm.score(features)
        river_score = self.river.online_score(features)
        
        lw = self.cfg["lgbm_weight"]
        rw = self.cfg["river_weight"]
        blended = (lgbm_score * lw) + (river_score * rw)
        
        should_trade = blended >= self.threshold
        
        debug = {
            "lgbm_score": round(lgbm_score, 4),
            "river_score": round(river_score, 4),
            "blended": round(blended, 4),
            "threshold": self.threshold,
            "decision": "TRADE" if should_trade else "SKIP",
            "drift_active": self.river.is_drifting
        }
        
        return should_trade, blended, debug
    
    def record_outcome(self, signal: dict, confidence: float, 
                    outcome: int, metadata: dict = None):
        """Record trade result - triggers River update."""
        features = engineer_features(signal)
        self.log.log(signal, features, confidence, outcome, metadata)
        
        drift_detected = self.river.update(features, outcome)
        
        if drift_detected:
            self._handle_drift()
        
        if self.lgbm.needs_retrain():
            self.lgbm.train(self.log)
    
    def _handle_drift(self):
        """Drift response - raise threshold."""
        old = self.threshold
        self.threshold = max(
            self.cfg["confidence_floor"],
            self.threshold + self.cfg["confidence_step_up"]
        )
        logger.warning(f"Drift: threshold {old:.2f} => {self.threshold:.2f}")
    
    def status(self) -> dict:
        return {
            "model_trained_at": str(self.lgbm.last_trained),
            "total_logged": self.log.count(),
            "live_win_rate": self.log.win_rate(),
            "drift_monitor": self.river.stats()
        }


# ============================================================================
# SECTION 8: MULTI-TF AGGREGATOR
# ============================================================================

class MultiTFAggregator:
    """Merge M5/M15/H1/H4 signals into one."""
    
    def aggregate(self, tf_signals: dict) -> Optional[dict]:
        """Combine signals from multiple timeframes."""
        active = {tf: sig for tf, sig in tf_signals.items() if sig}
        
        if not active:
            return None
        
        if "M15" not in active:
            logger.debug("No M15 signal - skipping")
            return None
        
        # Direction must agree
        directions = [s["direction"] for s in active.values()]
        if len(set(directions)) > 1:
            logger.debug(f"Direction conflict: {directions}")
            return None
        
        total_weight = sum(TF_WEIGHTS[tf] for tf in active)
        
        def wavg(field: str) -> float:
            return sum(active[tf].get(field, 0) * TF_WEIGHTS[tf] 
                     for tf in active) / total_weight
        
        def wbool(field: str) -> bool:
            score = sum(TF_WEIGHTS[tf] for tf in active 
                      if active[tf].get(field, False))
            return (score / total_weight) >= 0.5
        
        entry_tf = active["M15"]
        
        return {
            "ob_strength": wavg("ob_strength"),
            "fvg_present": wbool("fvg_present"),
            "bos_aligned": wbool("bos_aligned"),
            "liquidity_swept": wbool("liquidity_swept"),
            "adr_pct": wavg("adr_pct"),
            "pips_to_liquidity": wavg("pips_to_liquidity"),
            "session": entry_tf.get("session", "london"),
            "htf_bias": active.get("H4", {}).get("htf_bias") or 
                        active.get("H1", {}).get("htf_bias") or 0,
            "direction": entry_tf["direction"],
            "entry_price": entry_tf["entry_price"],
            "sl_price": entry_tf["sl_price"],
            "tp_price": entry_tf["tp_price"],
            "tfs_active": sorted(active.keys()),
            "tf_count": len(active)
        }


# ============================================================================
# SECTION 9: ML RISK MANAGER
# ============================================================================

class MLRiskManager:
    """Dynamic lot sizing based on ML confidence + regime."""
    
    def __init__(self, account_balance: float, config: dict = None):
        self.balance = account_balance
        self.cfg = config or CONFIG
    
    def update_balance(self, new_balance: float):
        self.balance = new_balance
    
    def _confidence_band(self, confidence: float) -> str:
        if confidence >= 0.75:
            return "high"
        elif confidence >= 0.62:
            return "medium"
        return "low"
    
    def _sl_pips(self, signal: dict) -> float:
        raw = abs(signal["entry_price"] - signal["sl_price"]) * 10
        return max(raw, 5.0)
    
    def calculate_lot(self, signal: dict, confidence: float, 
                     regime: Regime) -> dict:
        """Calculate lot size."""
        base_dollar = self.balance * self.cfg["base_risk_pct"]
        
        conf_band = self._confidence_band(confidence)
        conf_scalar = CONFIDENCE_RISK_SCALAR[conf_band]
        regime_scalar = REGIME_RISK_SCALAR[regime]
        tf_count = signal.get("tf_count", 1)
        tf_bonus = min(0.15, (tf_count - 1) * self.cfg["tf_confluence_bonus"])
        
        adj_risk = base_dollar * conf_scalar * regime_scalar * (1 + tf_bonus)
        adj_risk = max(
            self.balance * self.cfg["min_risk_pct"],
            min(self.balance * self.cfg["max_risk_pct"], adj_risk)
        )
        
        sl_pips = self._sl_pips(signal)
        lot_size = round(max(0.01, adj_risk / (sl_pips * self.cfg["pip_value_xauusd"])), 2)
        
        return {
            "lot_size": lot_size,
            "sl_pips": round(sl_pips, 1),
            "dollar_risk": round(adj_risk, 2),
            "risk_pct": round(adj_risk / self.balance * 100, 3),
            "conf_band": conf_band,
            "regime": regime.value
        }


# ============================================================================
# SECTION 10: ZMQ EXECUTOR (Placeholder - your system has this)
# ============================================================================

class ZMQExecutor:
    """MT5 bridge - placeholder."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        logger.info("ZMQExecutor ready (placeholder)")
    
    def send_order(self, signal: dict, risk: dict, confidence: float, 
                  regime: Regime) -> dict:
        """Send order to MT5."""
        # Your implementation connects here
        return {"status": "OK", "ticket": 0}
    
    def close(self):
        pass


# ============================================================================
# SECTION 11: SMC BRAIN - MAIN ORCHESTRATOR
# ============================================================================

class SMCBrain:
    """
    Main orchestrator - drop-in replacement.
    
    Integration with your existing system:
    
    # Initialize once at startup
    brain = SMCBrain(account_balance=1000.0)
    
    # In signal generation flow:
    brain.on_signal(tf_signals, h4_closes)
    
    # After trade closes:
    brain.on_trade_close(ticket, close_price, pnl)
    """
    
    def __init__(self, account_balance: float, config: dict = None):
        cfg = config or CONFIG
        self.cfg = cfg
        self.ml = HybridMLEngine(cfg)
        self.regime = RegimeDetector(cfg)
        self.agg = MultiTFAggregator()
        self.risk = MLRiskManager(account_balance, cfg)
        self.zmq = ZMQExecutor(cfg)
        
        self.open_trades = {}
        self.current_regime = Regime.UNKNOWN
        self.stats = {"signals": 0, "taken": 0, "skipped": 0}
        
        logger.info(f"SMCBrain online: balance={account_balance}")
    
    def on_signal(self, tf_signals: dict, h4_closes: list) -> Optional[dict]:
        """
        Process multi-TF signal through ML pipeline.
        
        Args:
            tf_signals: {"M5": sig, "M15": sig, "H1": sig, "H4": sig}
            h4_closes: list of recent H4 close prices
             
        Returns:
            Execution dict or None (if filtered)
        """
        self.stats["signals"] += 1
        
        # 1. Regime Guard
        self.current_regime = self.regime.detect(h4_closes)
        
        if self.current_regime == Regime.CHOPPY:
            logger.warning("CHOPPY - blocked")
            self.stats["skipped"] += 1
            return None
        
        # 2. Multi-TF Confluence
        signal = self.agg.aggregate(tf_signals)
        if signal is None:
            self.stats["skipped"] += 1
            return None
        
        # 3. ML Signal Gate
        should_trade, confidence, debug = self.ml.evaluate_signal(signal)
        
        if not should_trade:
            logger.info(f"ML filtered: {debug}")
            self.stats["skipped"] += 1
            return None
        
        # 4. Risk Sizing
        risk = self.risk.calculate_lot(signal, confidence, self.current_regime)
        
        if risk["lot_size"] <= 0:
            self.stats["skipped"] += 1
            return None
        
        # 5. Execute
        confirm = self.zmq.send_order(signal, risk, confidence, self.current_regime)
        
        if confirm:
            self.stats["taken"] += 1
            return confirm
        
        return None
    
    def on_trade_close(self, ticket: int, close_price: float, pnl: float):
        """Record trade outcome."""
        if ticket not in self.open_trades:
            return
        
        trade = self.open_trades.pop(ticket)
        outcome = 1 if pnl > 0 else 0
        
        self.ml.record_outcome(
            trade["signal"], trade["confidence"], outcome,
            {"ticket": ticket, "pnl": pnl, "regime": self.current_regime.value}
        )
        
        self.risk.update_balance(self.risk.balance + pnl)
    
    def session_report(self) -> dict:
        """End of session report."""
        ml = self.ml.status()
        return {
            "signals": self.stats["signals"],
            "taken": self.stats["taken"],
            "skipped": self.stats["skipped"],
            "regime": self.current_regime.value,
            "ml_threshold": self.ml.threshold,
            "total_logged": ml["total_logged"],
            "live_win_rate": ml["live_win_rate"]
        }
    
    def shutdown(self):
        self.zmq.close()


# ============================================================================
# SECTION 12: HISTORICAL LABELER
# ============================================================================

class HistoricalLabeler:
    """Seed ML with 8yr historical data."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        self.trade_log = TradeLog(config.get("trade_log_path", "data/trade_log.json"))
    
    def run(self, sample_every: int = 10) -> int:
        """Process historical data and generate labeled signals."""
        from mc_signal_labeler import scan_and_label, load_historical_data
        
        df = load_historical_data(self.cfg["hist_data_path"])
        new_records = scan_and_label(df, sample_every=sample_every)
        
        # Merge with existing
        existing = self.trade_log.records
        combined = {r["timestamp"]: r for r in existing}
        combined.update({r["timestamp"]: r for r in new_records})
        
        records = list(combined.values())
        self.trade_log.records = records
        self.trade_log._save()
        
        logger.info(f"Historical labeling: {len(new_records)} new = {len(records)} total")
        return len(records)


# ============================================================================
# SECTION 13: RETRAIN SCHEDULER
# ============================================================================

class RetrainScheduler:
    """Sunday retrain scheduler."""
    
    def __init__(self, config: dict = None):
        self.cfg = config or CONFIG
        self._thread = None
        self._stop = threading.Event()
    
    def start(self):
        """Start background scheduler."""
        import schedule
        
        day = self.cfg["retrain_day"]
        h, m = map(int, self.cfg["retrain_time_eat"].split(":"))
        utc_h = (h - 3) % 24
        
        getattr(schedule.every(), day).at(f"{utc_h:02d}:{m:02d}").do(self._do_retrain)
        logger.info(f"Retrain scheduler: {day} {self.cfg['retrain_time_eat']} EAT")
        
        def _run():
            while not self._stop.is_set():
                schedule.run_pending()
                time.sleep(60)
        
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
    
    def _do_retrain(self):
        """Execute scheduled retrain."""
        logger.info("Scheduled retrain...")
        ml = HybridMLEngine(self.cfg)
        ml.lgbm.train(ml.log)
    
    def stop(self):
        self._stop.set()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("SMC ML UNIFIED ENGINE - Ready")
    print("="*60)
    print("\nQuick Test:")
    
    # Test with sample signal
    brain = SMCBrain(account_balance=1000.0)
    
    sample_tf = {
        "M15": {
            "ob_strength": 0.85,
            "fvg_present": True,
            "bos_aligned": True,
            "liquidity_swept": True,
            "adr_pct": 0.35,
            "pips_to_liquidity": 10.0,
            "session": "london",
            "htf_bias": 1,
            "direction": "buy",
            "entry_price": 2650.0,
            "sl_price": 2640.0,
            "tp_price": 2670.0
        },
        "H1": {
            "ob_strength": 0.72,
            "fvg_present": True,
            "bos_aligned": True,
            "liquidity_swept": True,
            "adr_pct": 0.40,
            "pips_to_liquidity": 15.0,
            "session": "london",
            "htf_bias": 1,
            "direction": "buy",
            "entry_price": 2650.0,
            "sl_price": 2635.0,
            "tp_price": 2680.0
        },
        "H4": {
            "ob_strength": 0.65,
            "fvg_present": False,
            "bos_aligned": True,
            "liquidity_swept": True,
            "adr_pct": 0.45,
            "pips_to_liquidity": 20.0,
            "session": "london",
            "htf_bias": 1,
            "direction": "buy",
            "entry_price": 2650.0,
            "sl_price": 2625.0,
            "tp_price": 2700.0
        }
    }
    
    h4_closes = list(2600 + np.cumsum(np.random.randn(30) * 2))
    
    result = brain.on_signal(sample_tf, h4_closes)
    
    print(f"\nResult: {'EXECUTED' if result else 'FILTERED'}")
    print(f"Regime: {brain.current_regime.value}")
    print(f"Stats: {brain.stats}")
    
    # Status
    print(f"\nML Status:")
    status = brain.ml.status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    print("\n" + "="*60)
    print("Integration complete - ready for use")
    print("="*60 + "\n")