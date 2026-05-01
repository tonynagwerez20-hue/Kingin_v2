from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

class BaseDataProvider(ABC):
    """
    Abstract Base Class for all data providers (MT5, Sierra, etc.)
    """
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the connection is active."""
        pass

    @abstractmethod
    def get_latest_candles(self, symbol: str, timeframe: str, count: int) -> List[Dict]:
        """Fetch the most recent OHLCV data."""
        pass

    @abstractmethod
    def get_tick_data(self, symbol: str) -> Dict:
        """Fetch the latest tick/real-time volume data."""
        pass

class BaseFiltrationLayer(ABC):
    """
    Abstract Base Class for IGOF filtration layers.
    """
    def __init__(self, config: Dict):
        self.config = config

    @abstractmethod
    def process(self, data: Dict) -> Dict:
        """
        Validate data and return a result dictionary.
        Must contain 'status' (bool) and 'reason' (str).
        """
        pass

class BaseStrategy(ABC):
    """
    Abstract Base Class for Alphas/Trading Strategies.
    """
    def __init__(self, config: Dict):
        self.config = config

    @abstractmethod
    def generate_signal(self, data: Dict) -> Dict:
        """
        Generate a trading signal based on provided data.
        Returns a signal dictionary (action, directon, etc).
        """
        pass

class BaseRiskRule(ABC):
    """
    Abstract Base Class for risk management rules.
    """
    def __init__(self, config: Dict):
        self.config = config

    @abstractmethod
    def check_risk(self, trade_request: Dict) -> Dict:
        """
        Evaluate a trade request against risk parameters.
        Returns a result with status (allowed/denied).
        """
        pass
