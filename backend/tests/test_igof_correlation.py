
import unittest
import pandas as pd
from Engine.igof.correlation import CorrelationEngine

class TestCorrelationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CorrelationEngine()
        
    def test_structural_divergence_bullish(self):
        # Bullish: ZN Higher Low + GC Higher Low
        # ZN: Lows [10, 11, 12] -> Higher Low
        zn_candles = [
            {"high": 15, "low": 10, "close": 12},
            {"high": 16, "low": 11, "close": 13},
            {"high": 17, "low": 12, "close": 14}
        ]
        # GC: Lows [2000, 2001, 2002] -> Higher Low
        gc_candles = [
            {"high": 2005, "low": 2000, "close": 2002},
            {"high": 2006, "low": 2001, "close": 2003},
            {"high": 2007, "low": 2002, "close": 2004}
        ]
        
        # We need mock data for all inputs to analyze()
        # Mock 6E and ES as flat/irrelevant for this specific check logic
        mock_flat = [{"high": 1, "low": 1, "close": 1}] * 3
        
        # Manually verify internal logic or mock analyze?
        # Let's test checking logic via public method if exposes, or analyze result
        result = self.engine.analyze(gc_candles, zn_candles, mock_flat, mock_flat)
        self.assertEqual(result["signal"], "BULLISH_CONFIRMED")

    def test_structural_divergence_bearish(self):
        # Bearish: ZN Dumping (Close < Prev Lows) + GC Weak
        # ZN: Lows [10, 10], Last Close 9 -> Dump
        zn_candles = [
            {"high": 15, "low": 10, "close": 12},
            {"high": 15, "low": 10, "close": 12},
            {"high": 11, "low": 9, "close": 8} # Dump
        ]
        # GC: Lower Highs
        gc_candles = [
            {"high": 2010, "low": 2000, "close": 2005},
            {"high": 2008, "low": 2000, "close": 2004},
            {"high": 2006, "low": 2000, "close": 2002}
        ]
        
        result = self.engine.analyze(gc_candles, zn_candles, zn_candles, zn_candles) # Pass valid len arrays
        self.assertEqual(result["signal"], "BEARISH_CONFIRMED")

if __name__ == '__main__':
    unittest.main()
