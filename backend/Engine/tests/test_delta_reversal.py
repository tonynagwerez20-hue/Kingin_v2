"""
Test script for delta reversal detection logic.
Tests the new exit detection functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from support.orderflow.delta_logic import evaluate_delta, detect_delta_reversal, get_delta_direction

def test_delta_direction():
    """Test delta direction extraction."""
    print("=== Testing Delta Direction Extraction ===")
    
    tests = [
        ("BUY_FLIP", "BUY"),
        ("BUY_SURGE", "BUY"),
        ("BUY_TRANSITION", "BUY"),
        ("SELL_FLIP", "SELL"),
        ("SELL_SURGE", "SELL"),
        ("SELL_TRANSITION", "SELL"),
        (None, "NONE"),
        ("", "NONE"),
    ]
    
    for signal, expected in tests:
        result = get_delta_direction(signal)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} get_delta_direction('{signal}') = '{result}' (expected: '{expected}')")

def test_reversal_detection():
    """Test delta reversal detection."""
    print("\n=== Testing Delta Reversal Detection ===")
    
    tests = [
        # (previous, current, strong_only, expected)
        ("BUY_SURGE", "SELL_FLIP", False, True),   # Reversal
        ("SELL_FLIP", "BUY_SURGE", False, True),   # Reversal
        ("BUY_SURGE", "BUY_FLIP", False, False),   # Same direction
        ("SELL_SURGE", "SELL_TRANSITION", False, False),  # Same direction
        ("BUY_SURGE", "SELL_TRANSITION", True, False),  # Weak reversal (filtered)
        ("BUY_SURGE", "SELL_FLIP", True, True),    # Strong reversal
        (None, "SELL_FLIP", False, False),         # No previous
        ("BUY_SURGE", None, False, False),         # No current
    ]
    
    for prev, curr, strong_only, expected in tests:
        result = detect_delta_reversal(prev, curr, strong_only)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} detect_delta_reversal('{prev}', '{curr}', strong_only={strong_only}) = {result} (expected: {expected})")

def test_delta_evaluation():
    """Test delta evaluation with sample data."""
    print("\n=== Testing Delta Evaluation ===")
    
    # Sample delta structure (BUY signal)
    delta_struct_buy = {
        "delta": [5.0, 3.0, 2.0, -1.0],  # d0, d1, d2, d3 (increasing positive)
        "max": [5.0, 3.0, 2.0, -1.0],
        "min": [-1.0, -1.0, -1.0, -1.0],
        "cumulative": [9.0, 4.0, 1.0, -1.0]
    }
    
    # Sample delta structure (SELL signal)
    delta_struct_sell = {
        "delta": [-5.0, -3.0, -2.0, 1.0],  # Increasing negative
        "max": [1.0, 1.0, 1.0, 1.0],
        "min": [-5.0, -3.0, -2.0, 1.0],
        "cumulative": [-9.0, -4.0, -1.0, 1.0]
    }
    
    result_buy = evaluate_delta(delta_struct_buy)
    result_sell = evaluate_delta(delta_struct_sell)
    
    print(f"BUY structure result: {result_buy}")
    print(f"SELL structure result: {result_sell}")
    
    if result_buy:
        direction_buy = get_delta_direction(result_buy)
        print(f"  -> Direction: {direction_buy}")
    
    if result_sell:
        direction_sell = get_delta_direction(result_sell)
        print(f"  -> Direction: {direction_sell}")

def test_reversal_scenario():
    """Test a complete reversal scenario."""
    print("\n=== Testing Complete Reversal Scenario ===")
    
    # Scenario: Position LONG, delta reverses to SELL
    previous_signal = "BUY_SURGE"
    current_signal = "SELL_FLIP"
    
    print(f"Previous signal: {previous_signal}")
    print(f"Current signal: {current_signal}")
    
    is_reversal = detect_delta_reversal(previous_signal, current_signal, strong_only=False)
    print(f"Reversal detected: {is_reversal}")
    
    if is_reversal:
        prev_dir = get_delta_direction(previous_signal)
        curr_dir = get_delta_direction(current_signal)
        print(f"Direction change: {prev_dir} -> {curr_dir}")
        print("[PASS] EXIT SIGNAL: Close LONG position")
        print("  Check if reversal criteria met for SHORT entry...")

if __name__ == "__main__":
    print("Testing Delta Reversal Detection Logic\n")
    
    test_delta_direction()
    test_reversal_detection()
    test_delta_evaluation()
    test_reversal_scenario()
    
    print("\n=== All Tests Complete ===")
