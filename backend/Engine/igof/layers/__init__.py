from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from ..base import FiltrationLayer

class SessionFilterLayer(FiltrationLayer):
    """
    Layer 0: Session Filter.
    Ensures trading only occurs during London + NY sessions (08:00-21:00 UTC).
    """
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if not self.config.get('enabled', True):
            return {"status": True, "reason": "Session filter disabled"}
        
        current_time = market_snapshot.get("current_time")
        if current_time:
            dt = datetime.fromtimestamp(current_time, tz=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        
        hour_utc = dt.hour
        start_hour = self.config.get('start_hour_utc', 8)
        end_hour = self.config.get('end_hour_utc', 21)
        
        if start_hour <= hour_utc < end_hour:
            return {"status": True, "reason": f"Within session (UTC {hour_utc})"}
        return {"status": False, "reason": f"Outside trading session (UTC {hour_utc})"}

class H1StructuralBiasLayer(FiltrationLayer):
    """
    Layer 1: H1 Structural Bias.
    Validates BOS, Displacement, and Imbalance on H1 timeframe.
    """
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        h1_candles = market_snapshot.get("h1_candles", [])
        if len(h1_candles) < 5:
            return {"status": False, "reason": "Insufficient H1 data"}
        
        c1 = h1_candles[-1] # Current (developing)
        c2 = h1_candles[-2]
        c3 = h1_candles[-3]
        
        current_time = market_snapshot.get("current_time")
        candle_mature = True
        if current_time:
            candle_start = c1.get('time', 0)
            elapsed = current_time - candle_start
            maturity_threshold = self.config.get('candle_maturity_seconds', 3300)
            if elapsed < maturity_threshold:
                candle_mature = False
        
        # 1. BOS
        bos = candle_mature and (c1['close'] > c2['high'] or c1['close'] < c2['low'])
        
        # 2. Displacement
        last_spread = abs(c1['close'] - c1['open'])
        avg_spread = sum(abs(c['close'] - c['open']) for c in h1_candles[-6:-1]) / 5
        multiplier = self.config.get('displacement_multiplier', 1.5)
        displacement = candle_mature and (last_spread > avg_spread * multiplier)
        
        # 3. Imbalance (FVG)
        imbalance = (c1['low'] > c3['high']) or (c1['high'] < c3['low'])
        
        score = 0
        if bos: score += 1
        if displacement: score += 1
        if imbalance: score += 1
        
        market_snapshot["h1_bias_score"] = score
        
        min_score = self.config.get('min_score', 2)
        if score >= min_score:
            return {"status": True, "reason": f"H1 Bias strong ({score}/{min_score})", "score": score}
        return {"status": False, "reason": f"H1 Bias weak ({score}/{min_score})", "score": score}

class ZoneQualityLayer(FiltrationLayer):
    """
    Layer 2: Zone Quality.
    Evaluates supply/demand zones based on freshness, departure, and volume.
    """
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        zone = market_snapshot.get("active_zone")
        h1_candles = market_snapshot.get("h1_candles", [])
        h1_bias_score = market_snapshot.get("h1_bias_score", 0)
        
        if not zone:
            return {"status": False, "reason": "No active zone detected"}
        
        score = 0
        # 1. Freshness
        if not zone.get("mitigated", False): score += 1
            
        # 2. Departure
        idx = zone.get("index", -1)
        if idx != -1 and idx < len(h1_candles) - 1:
            departure_candle = h1_candles[idx + 1]
            spread = abs(departure_candle['close'] - departure_candle['open'])
            threshold = self.config.get('impulse_departure_threshold', 1.0)
            if spread > threshold: score += 1
        
        # 3. Volume
        if zone.get("volume_spike", False): score += 1
        # 4. Sweep
        if zone.get("sweep", False): score += 1
        # 5. HTF Alignment
        if h1_bias_score >= 2: score += 1
            
        min_score = self.config.get('min_score', 3)
        if score >= min_score:
            return {"status": True, "reason": f"Zone quality high ({score}/{min_score})", "score": score}
        return {"status": False, "reason": f"Zone quality low ({score}/{min_score})", "score": score}

class LiquidityEventLayer(FiltrationLayer):
    """
    Layer 3: Liquidity Event.
    Confirms sweep of previous lows/highs.
    """
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        candles = market_snapshot.get("m5_candles", [])
        if len(candles) < 10:
            return {"status": False, "reason": "Insufficient M5 data"}
            
        last = candles[-1]
        lookback = self.config.get('sweep_lookback_candles', 5)
        prev_min = min(c['low'] for c in candles[-(lookback+1):-1])
        prev_max = max(c['high'] for c in candles[-(lookback+1):-1])
        
        if last['low'] < prev_min or last['high'] > prev_max:
            return {"status": True, "reason": "Liquidity sweep detected"}
        return {"status": False, "reason": "No liquidity event detected"}

class MicrostructureShiftLayer(FiltrationLayer):
    """
    Layer 4: Microstructure Shift.
    Detects mBOS with volume confirmation.
    """
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        candles = market_snapshot.get("m5_candles", [])
        if len(candles) < 3:
            return {"status": False, "reason": "Insufficient data"}
            
        curr = candles[-1]
        prev = candles[-2]
        
        if curr['close'] > prev['high'] or curr['close'] < prev['low']:
            spread = abs(curr['close'] - curr['open'])
            threshold = self.config.get('displacement_threshold', 0.5)
            if spread > threshold:
                return {"status": True, "reason": "Microstructure shift confirmed"}
                
        return {"status": False, "reason": "No microstructure shift detected"}

class DisplacementLayer(FiltrationLayer):
    """
    Layer 5: Displacement.
    Validates candle momentum and body-to-wick ratio.
    """
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        candles = market_snapshot.get("m5_candles", [])
        if not candles:
            return {"status": False, "reason": "No candle data"}
            
        candle = candles[-1]
        spread = abs(candle['close'] - candle['open'])
        body_to_wick = spread / (candle['high'] - candle['low'] + 0.001)
        
        min_ratio = self.config.get('body_to_wick_ratio', 0.6)
        min_spread = self.config.get('min_spread', 0.5)
        
        if body_to_wick > min_ratio and spread > min_spread:
            return {"status": True, "reason": "Displacement validated"}
        return {"status": False, "reason": f"Weak displacement (Ratio: {body_to_wick:.2f})"}

class MLFilterLayer(FiltrationLayer):
    """
    Layer 6: Machine Learning Filter.
    Bridges to the unified_smc_ml.py Hybrid Engine.
    Enables constant learning and adaptive confidence thresholds.
    """
    _engine = None

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Lazy initialization to avoid overhead if not used
        self.enabled = config.get('enabled', True)

    def _get_engine(self):
        if MLFilterLayer._engine is None:
            try:
                from unified_smc_ml import HybridMLEngine
                MLFilterLayer._engine = HybridMLEngine()
            except ImportError as e:
                print(f"[ML] Failed to load HybridMLEngine: {e}")
                self.enabled = False
        return MLFilterLayer._engine

    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": True, "reason": "ML Filter disabled or failed to load"}
        
        engine = self._get_engine()
        if not engine:
            return {"status": True, "reason": "ML Engine unavailable"}

        # Prepare signal dictionary for ML engine
        # Map snapshot fields to what engineer_features expects
        signal_data = {
            "ob_strength": market_snapshot.get("h1_bias_score", 0) / 3.0,
            "fvg_present": market_snapshot.get("h1_bias_score", 0) >= 3,
            "bos_aligned": market_snapshot.get("h1_bias_score", 0) >= 1,
            "liquidity_swept": "Liquidity sweep detected" in str(market_snapshot.get("layer_results", "")),
            "session": market_snapshot.get("session", "london"),
            "htf_bias": market_snapshot.get("h1_bias_score", 0) - 1, # Center at 0
        }

        should_trade, confidence, debug = engine.evaluate_signal(signal_data)
        
        # Inject ML results back into snapshot for the orchestrator/UI
        market_snapshot["ml_confidence"] = confidence
        market_snapshot["ml_debug"] = debug
        
        if should_trade:
            return {
                "status": True, 
                "reason": f"ML Confirmed (Conf: {confidence:.2f})",
                "confidence": confidence,
                "debug": debug
            }
            
        return {
            "status": False, 
            "reason": f"ML Filtered (Conf: {confidence:.2f})",
            "confidence": confidence,
            "debug": debug
        }
