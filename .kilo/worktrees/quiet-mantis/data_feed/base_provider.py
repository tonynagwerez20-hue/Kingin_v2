import pandas as pd
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from datetime import datetime

class BaseDataProvider(ABC):
    """
    Standardized interface for all HedgeEA Data Providers.
    Ensures interchangeability between MT5, Sierra Chart, etc.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""
        pass

    @abstractmethod
    def get_latest_candles(self, symbol: str, timeframe: str, count: int) -> List[Dict]:
        """
        Fetch historical OHLCV data.
        Returns: List of standardized candle dictionary objects.
        """
        pass

    @abstractmethod
    def get_live_ticks(self, symbol: str) -> pd.DataFrame:
        """
        Fetch latest live price/volume data.
        Returns: DataFrame with standardized columns matching history.
        """
        pass

    def stitch_data(self, history: pd.DataFrame, live_ticks: pd.DataFrame) -> pd.DataFrame:
        """
        Ensures a continuous data stream by merging history with live ticks.
        Calculates the 'currently forming' candle from ticks if necessary.
        """
        if history.empty:
            return live_ticks
            
        # Basic implementation: 
        # 1. Take the historical buffer
        # 2. Append any live ticks that are newer than the last historical bar
        last_history_time = history['time'].iloc[-1]
        
        if not live_ticks.empty:
            new_ticks = live_ticks[live_ticks['time'] > last_history_time]
            if not new_ticks.empty:
                # In a real implementation, we would aggregate ticks into a candle here
                # but for simplicity, we concat the 'processed' live data
                combined = pd.concat([history, new_ticks]).drop_duplicates(subset=['time'], keep='last')
                return combined.sort_values(by='time').tail(len(history)).reset_index(drop=True)
                
        return history

    @abstractmethod
    def shutdown(self):
        """Clean up connections."""
        pass
