import sys
from pathlib import Path
import unittest
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from Engine.igof.v1_engine import V1FiltrationEngine
from Engine.igof.layers import (
    H1StructuralBiasLayer, ZoneQualityLayer, SessionFilterLayer,
    LiquidityEventLayer, MicrostructureShiftLayer, DisplacementLayer
)
from Engine.igof.base import FiltrationLayer

class MockLayer(FiltrationLayer):
    def __init__(self, status: bool, reason: str = "Mock Result"):
        super().__init__({})
        self.status = status
        self.reason = reason
    def process(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": self.status, "reason": self.reason}

class TestModularFiltration(unittest.TestCase):
    def test_h1_bias_layer(self):
        layer = H1StructuralBiasLayer({"min_score": 2, "candle_maturity_seconds": 3300})
        # Mock candles for BOS + Displacement + Imbalance (Score 3)
        candles = [
            {"open": 1990, "high": 1995, "low": 1985, "close": 1992, "time": 0},
            {"open": 1992, "high": 1998, "low": 1990, "close": 1997, "time": 3600},
            {"open": 2000, "high": 2005, "low": 1995, "close": 2002, "time": 7200},
            {"open": 2002, "high": 2007, "low": 2001, "close": 2005, "time": 10800},
            {"open": 2005, "high": 2015, "low": 2006, "close": 2014, "time": 14400}, # Strong displacement + FVG
        ]
        snapshot = {"h1_candles": candles, "current_time": 14400 + 3500} # Mature
        res = layer.process(snapshot)
        print(f"H1 Bias Result: {res}")
        self.assertTrue(res["status"])
        self.assertEqual(res["score"], 3)

    def test_zone_scoring_layer(self):
        layer = ZoneQualityLayer({"min_score": 3, "impulse_departure_threshold": 1.0})
        zone = {"type": "demand", "low": 2000, "high": 2005, "index": 0, "mitigated": False, "volume_spike": True}
        h1_candles = [
            {"open": 2000, "high": 2005, "low": 1995, "close": 2002, "time": 0},
            {"open": 2002, "high": 2010, "low": 2002, "close": 2009, "time": 3600}, # Strong departure
        ]
        snapshot = {
            "active_zone": zone, 
            "h1_candles": h1_candles,
            "h1_bias_score": 2
        }
        res = layer.process(snapshot)
        print(f"Zone Quality Result: {res}")
        self.assertTrue(res["status"])
        self.assertGreaterEqual(res["score"], 3)

    def test_modular_engine_orchestration(self):
        # Create engine with mocked layers
        layers = [
            MockLayer(True, "Layer 1 Passed"),
            MockLayer(True, "Layer 2 Passed"),
            MockLayer(False, "Layer 3 Failed")
        ]
        engine = V1FiltrationEngine(layers=layers)
        
        res = engine.process_all_layers({})
        print(f"Engine Result (Mock): {res}")
        self.assertEqual(res["action"], "NO_TRADE")
        self.assertIn("Layer 3 Failed", res["reason"])

    def test_full_engine_with_real_layers(self):
        engine = V1FiltrationEngine() # Uses default layers
        snapshot = {
            "h1_candles": [{"open": 2000, "high": 2015, "low": 1995, "close": 2014, "time": 0}] * 10,
            "m5_candles": [{"open": 2010, "high": 2012, "low": 2008, "close": 2011, "time": 3600}] * 10,
            "active_zone": {"type": "demand", "index": 5, "mitigated": False, "volume_spike": True},
            "current_time": 10 * 3600 + 55 * 60 # Session active + mature
        }
        
        # This will likely fail depending on the mock data quality but tests the flow
        res = engine.process_all_layers(snapshot)
        print(f"Engine Full Process Result: {res}")
        # We just want to ensure it doesn't crash and returns a valid reason
        self.assertIn("action", res)

if __name__ == "__main__":
    unittest.main()
