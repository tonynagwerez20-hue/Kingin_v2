import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from Engine.igof.igof_engine import IGOFEngine
from Engine.igof.layers.smc_layers import LayerFactory

def generate_mock_data(size=300):
    """
    Generates mock M5 data for testing.
    """
    base_price = 2000.0
    times = pd.date_range(end=datetime.now(), periods=size, freq='5min')
    
    # Create a trend with some noise
    data = []
    for i in range(size):
        price = base_price + (i * 0.1) + np.random.normal(0, 0.5)
        data.append({
            "time": int(times[i].timestamp()),
            "open": price,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price + 0.2,
            "volume": 100 + np.random.randint(0, 50)
        })
        
    # Inject a Bullish FVG at the end
    data[-3]['high'] = 2030.0
    data[-2]['open'] = 2031.0
    data[-2]['close'] = 2035.0 # Big candle
    data[-1]['low'] = 2032.0 # fvg_up: data[-1]['low'] > data[-3]['high'] is 2032 > 2030 -> TRUE
    
    return data

def test_smc_filtration():
    print("\n--- Testing SMC Institutional Filtration ---")
    
    # 1. Initialize Layers via Factory
    layer_names = [
        "MechanicalStructure", 
        "LiquiditySweep", 
        "FVGDiscount", 
        "Displacement", 
        "MicroMSS", 
        "KillzoneFilter"
    ]
    layers = LayerFactory.create_layers(layer_names)
    print(f"Initialized {len(layers)} SMC layers via Factory.")
    
    # 2. Setup IGOF Engine
    engine = IGOFEngine(layers=layers)
    
    # 3. Process Mock Data
    mock_candles = generate_mock_data()
    market_snapshot = {
        "m5_candles": mock_candles,
        "current_time": mock_candles[-1]['time']
    }
    
    print("\nProcessing market snapshot through SMC pipeline...")
    result = engine.process_all_layers(market_snapshot)
    
    print(f"\nEngine Result: {result['action']}")
    print(f"Reason: {result['reason']}")
    
    print("\nDetailed Layer Results:")
    for res in result.get("layer_results", []):
        layer_name = res['layer']
        status = res['result']['status']
        score = res['result'].get('score', 0.0)
        reason = res['result'].get('reason', '')
        print(f" - {layer_name}: {'PASS' if status else 'FAIL'} (Score: {score:.2f}) | {reason}")

if __name__ == "__main__":
    test_smc_filtration()
