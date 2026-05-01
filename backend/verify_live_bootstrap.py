import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path.cwd()))

from Engine.modular_bootstrapper import ModularBootstrapper

def test_bootstrap():
    print("=== System Bootstrap Verification ===")
    config_file = "config/trading_params_lite.json"
    
    try:
        bootstrapper = ModularBootstrapper(config_file)
        print(f"1. Loaded config from {config_file}")
        
        # Build pipeline WITHOUT connecting to MT5 (Mock connection needed or just test build)
        # For now, let's see if it builds.
        # We might need to mock MT5 if it's not running.
        
        print("2. Building pipeline components...")
        # We'll patch DataProviderFactory.get_provider to return a dummy if MT5 fails
        # but let's try the real one first.
        bootstrapper.build_pipeline()
        print("Pipeline built successfully.")
        
        print(f"Data Provider: {bootstrapper.data_provider.__class__.__name__}")
        print(f"Filtration Engine: {len(bootstrapper.filtration_engine.layers)} layers loaded")
        print(f"Strategies: {len(bootstrapper.strategies)} loaded")
        print(f"Risk Rules: {len(bootstrapper.risk_rules)} loaded")
        
        print("\nBOOTSTRAP SUCCESSFUL")
        return True
    except Exception as e:
        print(f"\nBOOTSTRAP FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_bootstrap()
