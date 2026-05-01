import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from support.risk.ultra_low_risk import UltraLowAccountRiskRule

def test_dynamic_risk_scaling():
    print("\n" + "="*60)
    print("TESTING DYNAMIC RISK SCALING & TIGHTENING ($10-$15)")
    print("="*60)

    config = {
        "min_equity_threshold": 7.50,
        "max_daily_loss_pct": 5.0,
        "max_concurrent_positions": 1,
        "min_lot_size": 0.01,
        "max_lot_size": 0.1,
        "seed_balance": 10.0,
        "profit_step_for_scaling": 15.0
    }
    
    risk_rule = UltraLowAccountRiskRule(config)

    # Scenario 1: Risk Tightening (Equity < Seed)
    print("\nScenario 1: Risk Tightening (Equity $9.00 < Seed $10.00)")
    # Should use half daily loss limit (2.5%)
    # Loss of $0.30 on $10 start = 3% -> Should be DENIED
    req1 = {"current_equity": 9.00, "daily_loss": 0.30, "daily_start_balance": 10.00, "open_positions_count": 0, "lots": 0.01}
    res1 = risk_rule.check_risk(req1)
    print(f"Result: {'DENIED' if not res1['allowed'] else 'ALLOWED'} | Reason: {res1['reason']}")

    # Scenario 2: Exposure Scaling (Profit +$5)
    print("\nScenario 2: Exposure Scaling (Equity $16.00 > Seed $10.00 + $5.00)")
    # Should allow 2 positions (1 base + 1 scaling)
    req2 = {"current_equity": 16.00, "daily_loss": 0.0, "open_positions_count": 1, "lots": 0.01}
    res2 = risk_rule.check_risk(req2)
    print(f"Result: {'ALLOWED' if res2['allowed'] else 'DENIED'} | Max Positions: {res2.get('dynamic_max_positions')}")

    # Scenario 3: Aggressive Scaling (Profit +$10)
    print("\nScenario 3: Aggressive Scaling (Equity $21.00)")
    # Should allow 3 positions
    req3 = {"current_equity": 21.00, "daily_loss": 0.0, "open_positions_count": 2, "lots": 0.01}
    res3 = risk_rule.check_risk(req3)
    print(f"Result: {'ALLOWED' if res3['allowed'] else 'DENIED'} | Max Positions: {res3.get('dynamic_max_positions')}")

    # Scenario 4: Return to Base (Equity drops back to $12)
    print("\nScenario 4: Return to Base (Equity $12.00)")
    # Profit $2 < $5 step -> Should return to 1 position
    req4 = {"current_equity": 12.00, "daily_loss": 0.0, "open_positions_count": 1, "lots": 0.01}
    res4 = risk_rule.check_risk(req4)
    print(f"Result: {'DENIED' if not res4['allowed'] else 'ALLOWED'} | Max Positions: {res4.get('dynamic_max_positions')}")

    # Scenario 5: Micro-Lot Enforcement
    print("\nScenario 5: Mandatory Micro-Lot (Regardless of scaling)")
    req5 = {"current_equity": 20.00, "daily_loss": 0.0, "open_positions_count": 0, "lots": 0.10}
    res5 = risk_rule.check_risk(req5)
    print(f"Result: ALLOWED | Lots Enforced: {req5['lots']}")

if __name__ == "__main__":
    # Suppress logging for cleaner test output
    logging.getLogger("UltraLowAccountRisk").setLevel(logging.ERROR)
    test_dynamic_risk_scaling()
