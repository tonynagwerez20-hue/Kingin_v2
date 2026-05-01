from typing import Dict, Any

class BrokerWatchdog:
    def __init__(self, min_margin_level: float = 100.0):
        self.min_margin_level = min_margin_level

    def check_health(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Checks broker connectivity and margin safety.
        """
        margin_level = account_info.get("margin_level", 1000.0)
        is_connected = account_info.get("is_connected", True)

        if not is_connected:
            return {"status": "FAIL", "reason": "Broker disconnected"}
        
        if margin_level < self.min_margin_level:
            return {"status": "FAIL", "reason": f"Low margin level: {margin_level}%"}

        return {"status": "PASS", "reason": "Broker status OK"}
