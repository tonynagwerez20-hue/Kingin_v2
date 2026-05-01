import pandas as pd
import logging
from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any
from Engine.base_interfaces import BaseFiltrationLayer as IBaseFiltrationLayer

logger = logging.getLogger("SMCBase")

class SMCLayerBase(IBaseFiltrationLayer, ABC):
    """
    Abstract Base Class for modular SMC Filtration Layers.
    """
    def __init__(self, name: str = "SMC_Layer", threshold: float = 0.5, config: dict = None):
        self.name = name
        self.threshold = threshold
        self.config = config or {}  # Store config for layer-specific settings
        if config:
            self.name = config.get("name", self.name)
            self.threshold = config.get("threshold", self.threshold)
         
        super().__init__(config=self.config)

    def _get_candles(self, data: dict, tf_key: str = None) -> List[Dict]:
        """
        Safely extract candle data from the data dictionary.
        Returns [] if data is missing or not a list, never returns None.
        """
        key = tf_key or self.config.get("timeframe_key", "m5_candles")
        candles = data.get(key)
        return candles if isinstance(candles, list) else []

    def _build_result(self, status: bool, score: float, reason: str, bias: str = "neutral", **extra) -> Dict[str, Any]:
        """
        Build a standardized result dictionary with bias validation.
        """
        # Validate bias
        if bias not in ("bullish", "bearish", "neutral"):
            bias = "neutral"
            
        result = {
            "status": bool(status),
            "score": float(score),
            "reason": str(reason),
            "bias": bias
        }
        # Merge any extra fields
        result.update(extra)
        return result

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Calculates institutional logic.
        Returns: (pass/fail, confidence_score)
        """
        pass

    def process(self, data: dict) -> dict:
        """
        IGOF Engine Compatibility Wrapper.
        """
        # Allow routing to different timeframes (H1, M15, M5, M1)
        tf_key = self.config.get("timeframe_key", "m5_candles")
        candles = self._get_candles(data, tf_key)
        
        if not candles:
            return self._build_result(False, 0.0, f"{self.name}: No {tf_key} data")
            
        try:
            df = pd.DataFrame(candles)
            status, score = self.validate(df)
        except Exception as e:
            return self._build_result(False, 0.0, f"{self.name}: validate() error - {e}")
            
        # Use _reason if set by validate, otherwise use default reason
        reason = getattr(self, "_reason", f"SMC {self.name}: {'Qualified' if status else 'Rejected'} (Score: {score:.2f})")
        # Use _bias if set by validate, otherwise default to neutral
        bias = getattr(self, "_bias", "neutral")
        
        return self._build_result(status, score, reason, bias=bias)
