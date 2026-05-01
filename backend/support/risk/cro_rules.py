from typing import Dict, Any, Optional

class CRORules:
    def __init__(self, max_spread_pips: float = 3.0):
        self.max_spread_pips = max_spread_pips

    def audit_trade_request(self, trade_req: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs pre-trade audit.
        Returns a dict with 'status' (PASS/FAIL) and 'reason'.
        """
        # 1. Microstructure Filter: Spread Check
        current_spread = market_data.get("spread", 0.0)
        if current_spread > self.max_spread_pips:
            return {"status": "FAIL", "reason": f"Spread too high: {current_spread} > {self.max_spread_pips}"}

        # 2. Liquidity Check (Simple volume heuristic)
        current_volume = market_data.get("volume", 1.0)
        if current_volume <= 0:
            return {"status": "FAIL", "reason": "No market liquidity detected"}

        return {"status": "PASS", "reason": "Audit successful"}
