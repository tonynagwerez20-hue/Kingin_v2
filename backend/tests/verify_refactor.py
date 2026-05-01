import sys
from pathlib import Path
from collections import deque
import unittest
from datetime import datetime

# Setup Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_feed.dispatcher import dispatch_batch, ohlc_buffers
from support.strategies.composite_strategy import CompositeStrategy
from support.price_action.supply_and_demand import mitigate_zones

class TestRefactor(unittest.TestCase):
    def setUp(self):
        # Clear buffers
        for buf in ohlc_buffers.values():
            buf.clear()
            
    def test_dispatch_batch(self):
        print("\n--- Testing Dispatch Batch ---")
        target_buffer = ohlc_buffers["M5"]
        
        # Batch 1
        data1 = [{"time": 100, "close": 1.0}, {"time": 101, "close": 1.1}]
        dispatch_batch(data1, target_buffer)
        self.assertEqual(len(target_buffer), 2)
        self.assertEqual(target_buffer[0]["close"], 1.0)
        
        # Batch 2 (Should Replace Batch 1)
        data2 = [{"time": 200, "close": 2.0}, {"time": 201, "close": 2.1}, {"time": 202, "close": 2.2}]
        dispatch_batch(data2, target_buffer)
        self.assertEqual(len(target_buffer), 3)
        self.assertEqual(target_buffer[0]["close"], 2.0)
        print("Buffer cleared and refilled successfully.")

    def test_mitigation(self):
        print("\n--- Testing Mitigation ---")
        zones = [
            {"type": "demand", "low": 100, "high": 110, "index": 1}, # Valid
            {"type": "demand", "low": 100, "high": 110, "index": 2}, # Broken by Low Price
            {"type": "supply", "low": 150, "high": 160, "index": 3}, # Valid
            {"type": "supply", "low": 150, "high": 160, "index": 4}, # Broken by High Price
        ]
        
        current_price = 99 # Breaks demand
        mitigated = mitigate_zones(zones, current_price)
        # Should keep Supply (valid) and Supply (broken by high? No, 99 < 160 so valid)
        # Wait, current_price 99 breaks demand (low 100 > 99).
        # Supply: 99 < 160 (high). Safe.
        
        # Test specific break logic
        # Case 1: Price 98. Breaks Demand(100-110).
        z1 = mitigate_zones([zones[0]], 98) 
        self.assertEqual(len(z1), 0, "Demand should be broken")
        
        # Case 2: Price 161. Breaks Supply(150-160).
        z2 = mitigate_zones([zones[2]], 161)
        self.assertEqual(len(z2), 0, "Supply should be broken")
        
        print("Zone mitigation logic verified.")

    def test_strategy_signal(self):
        print("\n--- Testing Strategy Signal ---")
        strategy = CompositeStrategy()
        
        # Setup Perfect Storm
        # 1. Bias = BULLISH (Higher Highs, Higher Lows in H1)
        # We need zig-zag data to form swing points (High > prev/next)
        h1_data = []
        base_price = 2000
        for i in range(30):
            # Create a wave pattern: Up 2, Down 1
            if i % 4 == 0: price = base_price + 0
            elif i % 4 == 1: price = base_price + 20 # Peak (Swing High possible)
            elif i % 4 == 2: price = base_price + 10 # Retrace (Swing Low possible)
            elif i % 4 == 3: price = base_price + 30 # Higher Peak
            
            # Add general trend
            base_price += 10 
            
            h1_data.append({"time": i*3600, "open": price, "high": price+5, "low": price-5, "close": price})
        
        # Populate GLOBAL buffer for bias.py to see it
        # (Since we haven't refactored bias.py to accept arguments yet)
        target = ohlc_buffers["H1"]
        target.clear()
        target.extend(h1_data)
            
        # 2. Zone = Demand
        m15_data = [
            {"time": 1000, "open": 2050, "high": 2060, "low": 2040, "close": 2055}, # Base
            {"time": 1900, "open": 2100, "high": 2105, "low": 2050, "close": 2100}  # Revisit 2050
        ]
        # We manually inject a zone into logic or rely on detection.
        # Detection needs specific structure. 
        # Easier: Mock detect_supply_demand? 
        # Actually CompositeStrategy calls detect_supply_demand(df_m15).
        # Constructing data that triggers detection is hard.
        # But we can trust the unit tests for supply_and_demand.py if they exist.
        # Here we test the integration.
        
        # Let's bypass detection complexity by mocking detect_supply_demand
        import support.strategies.composite_strategy
        original_detect = support.strategies.composite_strategy.detect_supply_demand
        
        support.strategies.composite_strategy.detect_supply_demand = lambda df: [
            {"type": "demand", "low": 2045, "high": 2055, "index": 0}
        ]
        
        # 3. Delta = BUY (Surge/Flip)
        # We need d1 < 0 and d0 > 0 for BUY_FLIP
        delta_struct = {
            "delta": [100, -10, -20, -30], # d0=100, d1=-10 ...
            "max": [100, 5, -5, -10],
            "min": [0, -15, -25, -35],
            "cumulative": [200, 100, 50, 0] # Bullish
        }
        
        current_price = 2050 # Inside Demand (2045-2055)
        m15_data[-1]["close"] = current_price
        
        try:
             # Run Evaluate
            signal = strategy.evaluate(
                htf_buffer=h1_data,
                mtf_buffer=m15_data,
                ltf_buffer=m15_data, # Reuse
                delta_struct=delta_struct,
                position_tracker=None 
            )
            
            # Should produce LONG signal
            print(f"Signal Result: {signal}")
            self.assertIsNotNone(signal)
            self.assertEqual(signal["action"], "LONG")
            
        finally:
            # Restore
            support.strategies.composite_strategy.detect_supply_demand = original_detect

    def test_delta_inclusion(self):
        print("\n--- Testing Delta Inclusion in M5 Buffer ---")
        from data_feed.dispatcher import DataDispatcher
        import asyncio
        
        # Setup Dispatcher (mock)
        dispatcher = DataDispatcher()
        
        # 1. Dispatch M5 Candle
        dispatcher._handle_ohlc("M5", {"open": 100, "close": 101, "time": 1000, "tf": "M5", "type": "ohlc"})
        buf = ohlc_buffers["M5"]
        self.assertEqual(len(buf), 1)
        self.assertTrue("delta" not in buf[-1] or buf[-1].get("delta") is None)
        
        # 2. Dispatch Delta (Simulated)
        dispatcher._handle_delta("M5", {"value": 500.0, "tf": "M5", "type": "delta"})
        
        # 3. Verify Delta is merged
        self.assertIn("delta", buf[-1])
        self.assertEqual(buf[-1]["delta"], 500.0)
        print("Delta successfully merged into M5 candle.")

if __name__ == '__main__':
    unittest.main()
