import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from Engine.cli_dashboard import CLIDashboard
from rich.live import Live

def run_dashboard_simulation():
    print("Initializing Professional CLI Dashboard Simulation...")
    dash = CLIDashboard()
    
    # Mock data templates
    layers = [
        "MechanicalStructure", "LiquiditySweep", "FVGDiscount", 
        "Displacement", "MicroMSS", "KillzoneFilter"
    ]
    
    mock_state = {
        "account": {"equity": 10.0, "balance": 10.0, "daily_pnl": 0.0, "daily_loss_pct": 0.0},
        "market": {"symbol": "XAUUSD", "price": 2025.50, "spread": 2.1, "htf_bias": "NEUTRAL"},
        "pipeline": [{"name": l, "status": False, "score": 0.0} for l in layers],
        "signals": []
    }

    print("Simulating Institutional Trading Session (5 updates)...")
    
    try:
        with Live(dash.layout, refresh_per_second=4, screen=True) as live:
            for i in range(5):
                # Simulate market movement
                mock_state["market"]["price"] += (i * 0.5)
                mock_state["account"]["equity"] += (i * 0.1)
                mock_state["account"]["daily_pnl"] = mock_state["account"]["equity"] - 10.0
                
                # Simulate pipeline progression
                if i > 1:
                    mock_state["pipeline"][0]["status"] = True
                    mock_state["pipeline"][0]["score"] = 1.0
                    mock_state["market"]["htf_bias"] = "BULLISH"
                
                if i > 3:
                    mock_state["pipeline"][1]["status"] = True
                    mock_state["pipeline"][1]["score"] = 1.0
                    mock_state["signals"].append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "LONG_CONFIRMED",
                        "price": mock_state["market"]["price"],
                        "sl": mock_state["market"]["price"] - 5.0,
                        "tp": mock_state["market"]["price"] + 10.0
                    })
                
                dash.update(mock_state)
                time.sleep(1)
        
        print("\n[PASSED] CLI Dashboard Rendering Verified.")
        return True
    except Exception as e:
        print(f"\n[FAILED] Dashboard Error: {e}")
        return False

if __name__ == "__main__":
    success = run_dashboard_simulation()
    sys.exit(0 if success else 1)
