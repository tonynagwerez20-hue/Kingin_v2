import json
import sys
from pathlib import Path

def toggle_system(force_state: str = None):
    config_path = Path("config/trading_params_lite.json")
    
    if not config_path.exists():
        print(f"[ERROR] Configuration file not found at {config_path}")
        sys.exit(1)
        
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            
        current_state = config.get("trading", {}).get("master_switch", True)
        
        if force_state == "ON":
            new_state = True
        elif force_state == "OFF":
            new_state = False
        else:
            new_state = not current_state
        
        config["trading"]["master_switch"] = new_state
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
            
        status = "ENABLED" if new_state else "DISABLED"
        style = "\033[92m" if new_state else "\033[91m"
        reset = "\033[0m"
        
        print("\n" + "="*40)
        print(f"   SYSTEM MASTER SWITCH: {style}{status}{reset}")
        print("="*40)
        print(f"The modular engine will now {'resume' if new_state else 'pause'} execution.")
        
    except Exception as e:
        print(f"[ERROR] Failed to update system: {e}")
        sys.exit(1)

if __name__ == "__main__":
    arg = sys.argv[1].upper() if len(sys.argv) > 1 else None
    toggle_system(arg)
