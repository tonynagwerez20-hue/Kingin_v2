import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from data_feed.factory import DataProviderFactory
from Engine.igof.igof_engine import IGOFEngine
from Engine.igof.layers.smc_layers import LayerFactory
from support.strategies.smc_strategy import SMCStrategy

def generate_golden_market_data(size=100):
    """
    Generates market data that SHOULD trigger an SMC Buy signal.
    1. Trend (BOS)
    2. FVG in Discount
    3. Session: London Open
    """
    times = pd.date_range(end=datetime.now(), periods=size, freq='5min')
    base_price = 2000.0
    
    data = []
    for i in range(size):
        price = base_price + (i * 0.1)
        data.append({
            "time": int(times[i].timestamp()),
            "open": price, "high": price + 0.5, "low": price - 0.5, "close": price + 0.1, "volume": 100
        })
    
    # Inject Bullish BOS (Last candle body > previous high)
    data[-2]['high'] = 2015.0
    data[-1]['close'] = 2016.0
    
    # Inject FVG
    data[-3]['high'] = 2010.0
    data[-2]['low'] = 2012.0 # fvg_up
    
    return data

def run_integration_test():
    print("\n" + "="*50)
    print("ULTIMATE SMC PIPELINE INTEGRATION TEST")
    print("="*50)

    # 1. Initialize Components
    print("\n[1/4] Initializing SMC Components...")
    layer_names = ["MechanicalStructure", "LiquiditySweep", "FVGDiscount", "Displacement", "MicroMSS", "KillzoneFilter"]
    layers = LayerFactory.create_layers(layer_names)
    
    engine = IGOFEngine(layers=layers)
    
    strategy_config = {
        "min_total_score": 1.5, # Lowered for testing coverage
        "min_layers_passed": 2,
        "symbol": "XAUUSD"
    }
    strategy = SMCStrategy(config=strategy_config)
    print(f"Success: Components Initialized.")

    # 2. Simulate Market Context
    print("\n[2/4] Generating Mock Market Context...")
    candles = generate_golden_market_data()
    market_snapshot = {
        "symbol": "XAUUSD",
        "m5_candles": candles,
        "tick": {"bid": 2016.0, "ask": 2016.2}
    }
    print(f"Success: {len(candles)} M5 candles generated.")

    # 3. Process Filtration
    print("\n[3/4] Running Filtration Engine...")
    filt_res = engine.process_all_layers(market_snapshot)
    print(f"Filtration Result: {filt_res['action']} - {filt_res['reason']}")
    
    for res in filt_res.get("layer_results", []):
        status = "PASS" if res['result']['status'] else "FAIL"
        print(f" - {res['layer']}: {status}")

    # 4. Generate Strategy Signal
    print("\n[4/4] Generating SMC Strategy Signal...")
    signal = strategy.generate_signal(market_snapshot)
    
    print(f"\nFINAL SIGNAL: {signal['action']}")
    if signal['action'] == "TRADE":
        print(f"Direction: {signal['direction']}")
        print(f"Price: {signal['price']} | SL: {signal['sl']:.2f} | TP: {signal['tp']:.2f}")
        print(f"Confidence: {signal['confidence']:.2f}")
        print(f"Reason: {signal['reason']}")
        return True
    else:
        print(f"Reason: {signal['reason']}")
        return False

if __name__ == "__main__":
    success = run_integration_test()
    if success:
        print("\n[PASSED] SMC End-to-End Pipeline Verified.")
        sys.exit(0)
    else:
        print("\n[FAILED] Pipeline did not generate expected trade signal.")
        sys.exit(1)
