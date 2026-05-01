from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class AbstractStrategy(ABC):
    @abstractmethod
    def evaluate(self, htf_buffer: List[Dict], mtf_buffer: List[Dict], ltf_buffer: List[Dict], **kwargs) -> Optional[Dict]:
        """
        Evaluate market data and return a signal if conditions are met.
        
        Args:
            htf_buffer: Higher Timeframe candles (e.g., H1)
            mtf_buffer: Medium Timeframe candles (e.g., M15)
            ltf_buffer: Lower Timeframe candles (e.g., M5)
            **kwargs: Additional data (e.g., delta, account_balance, positions)
            
        Returns:
            Dict containing signal details or None if no signal.
            Format:
            {
                "action": "LONG" | "SHORT" | "CLOSE_LONG" | "CLOSE_SHORT",
                "symbol": str,
                "price": float,
                "sl": float,
                "tp": float,
                "lots": float,
                "desc": str
            }
        """
        pass
