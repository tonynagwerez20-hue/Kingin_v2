from abc import ABC, abstractmethod
from typing import Dict, Any

class FiltrationLayer(ABC):
    """
    Abstract base class for a filtration layer.
    Each layer has a single responsibility and processes a market snapshot.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the layer with its specific configuration.
        
        Args:
            config: Configuration dictionary for this specific layer
        """
        self.config = config

    @abstractmethod
    def process(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the market data and return the result.
        
        Args:
            market_snapshot: Dictionary containing market data (candles, zones, etc.)
            
        Returns:
            Dictionary with at least 'status' (True/False) and 'reason'.
        """
        pass
