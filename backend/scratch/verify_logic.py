import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(r"c:\Users\LENOVO\Desktop\kingin-master\backend")
sys.path.append(str(backend_path))
sys.path.append(str(backend_path / "Engine"))

from Engine.igof.stack import FiltrationController
from Engine.igof.liquidity import LiquidityEngine

def test_stack_guard_logic():
    print("\n--- Testing Guard Logic in stack.py ---")
    fc = FiltrationController()
    
    # Mock correlation to return WAIT
    class MockCorr:
        def analyze(self, *args): return {"status": "WAIT"}
    fc.correlation = MockCorr()
    
    # Mock V1 to return TRADE_ALLOWED
    class MockV1:
        def process_all_layers(self, *args): return {"action": "TRADE_ALLOWED"}
    fc.v1 = MockV1()

    # Mock Macro
    class MockMacro:
        def check_context(self): return "BULLISH"
        def get_levels(self): return {"weekly_poc": 2300}
    fc.macro = MockMacro()
    
    snapshot = {"price": 2350.0}
    
    try:
        res = fc.process(snapshot)
        print(f"Filtration result (should not crash): {res}")
    except Exception as e:
        print(f"CRASH DETECTED: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def test_type_error_in_liquidity():
    print("\n--- Testing TypeError in liquidity.py ---")
    le = LiquidityEngine()
    le.on_depth_update(2350.0, 50.0, 1) # Key is (2350.0, 1)
    
    try:
        state = le.get_market_state(2350.5)
        print(f"Liquidity state: {state}")
    except TypeError as e:
        print(f"CAUGHT EXPECTED TYPEERROR: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_stack_guard_logic()
    test_type_error_in_liquidity()
