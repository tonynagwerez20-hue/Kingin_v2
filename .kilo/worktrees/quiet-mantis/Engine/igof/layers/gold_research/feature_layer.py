"""
Gold Research Strategy - Feature Layer
======================================
Memory-efficient feature generation for Gold OHLC data.
Designed for i3/4GB RAM constraint using float32.

CRITICAL FIX: Price-Agnostic Features
=======================================
The original implementation used absolute prices which caused regime drift.
When gold price climbed from 3,700 to 5,500, predictions got stuck at 3,700.

NEW Implementation:
- Uses percentage returns instead of absolute prices
- Uses percentage-based shadows and ranges
- Uses percentage-based distance from EMA
- This makes the model IMMORTAL regardless of price level

Features:
- Positional Encodings (hour_of_day, day_of_week)
- Returns: percentage changes (1, 3, 8-period lags)
- EMA-based: distance from EMA as percentage
- Range: (High - Low) / Close
- Shadows: upper_shadow and lower_shadow as percentages
"""

import numpy as np
import pandas as pd
import gc
from typing import Optional, Tuple


class GoldFeatureGenerator:
    """
    Generates memory-efficient, PRICE-AGNOSTIC features from Gold OHLCV data.
    All outputs are float32 to minimize RAM usage on 4GB systems.
    
    KEY: All price-based features are converted to percentage changes.
    """
    
    def __init__(self, lag_periods: list = None, ema_period: int = 24):
        """
        Initialize the feature generator.
        
        Args:
            lag_periods: List of lag periods for return features. 
                        Defaults to [1, 3, 8].
            ema_period: Period for EMA calculation (default 24 for H1)
        """
        self.lag_periods = lag_periods or [1, 3, 8]
        self.ema_period = ema_period
        self.dxy_aligned = None
        self._feature_columns = []
        self._last_close = None  # Store for inference
        self._ema_current = None  # Store for trend filtering
        
    def generate_features(self, ohlcv_df: pd.DataFrame, 
                          dxy_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Generate all PRICE-AGNOSTIC features from OHLCV data.
        
        Args:
            ohlcv_df: DataFrame with columns [open, high, low, close, volume]
            dxy_df: Optional DXY data for correlation alignment
            
        Returns:
            DataFrame with all generated features (float32)
        """
        try:
            # Validate input
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in ohlcv_df.columns for col in required_cols):
                raise ValueError(f"OHLCV DataFrame must contain: {required_cols}")
            
            # Convert to float32 immediately for memory efficiency
            df = ohlcv_df[required_cols].astype(np.float32)
            
            # Store last close for inference later
            self._last_close = float(df['close'].iloc[-1])
            
            # Generate features
            features = pd.DataFrame(index=df.index)
            
            # 1. Positional Encodings (unchanged - no price dependency)
            features = self._add_positional_encodings(features, df)
            
            # 2. PRICE-AGNOSTIC Returns (instead of absolute lags)
            features = self._add_percentage_returns(features, df)
            
            # 3. Price-Agnostic Range Features
            features = self._add_percentage_range_features(features, df)
            
            # 4. Price-Agnostic EMA Features
            features = self._add_ema_distance_features(features, df)
            
            # 5. DXY Correlation if provided (returns-based)
            if dxy_df is not None:
                features = self._add_dxy_correlation(features, df, dxy_df)
            
            # Store feature columns
            self._feature_columns = features.columns.tolist()
            
            # Force garbage collection
            gc.collect()
            
            return features
            
        except Exception as e:
            raise RuntimeError(f"Feature generation failed: {str(e)}")
    
    def _add_positional_encodings(self, features: pd.DataFrame, 
                                   df: pd.DataFrame) -> pd.DataFrame:
        """Add hour_of_day and day_of_week encodings."""
        # Try to extract datetime from index or column
        if isinstance(df.index, pd.DatetimeIndex):
            dt_index = df.index
        elif 'time' in df.columns and pd.api.types.is_datetime64_any_dtype(df['time']):
            dt_index = df['time']
        else:
            # Create synthetic time index for positional encoding
            dt_index = pd.date_range(start='2024-01-01', periods=len(df), freq='h')
        
        features['hour_of_day'] = dt_index.hour.astype(np.float32)
        features['day_of_week'] = dt_index.dayofweek.astype(np.float32)
        
        return features
    
    def _add_percentage_returns(self, features: pd.DataFrame, 
                                df: pd.DataFrame) -> pd.DataFrame:
        """
        Add percentage returns instead of absolute price lags.
        
        This is the KEY FIX for regime drift.
        Returns are STATIONARY - they don't depend on price level.
        """
        close = df['close']
        volume = df['volume']
        
        # Percentage returns (stationary!)
        returns = close.pct_change()
        
        for lag in self.lag_periods:
            # Return lags (percentage changes)
            features[f'return_lag_{lag}'] = returns.shift(lag).astype(np.float32)
            
            # Volume change lags (also percentage)
            vol_change = volume.pct_change()
            features[f'volume_change_lag_{lag}'] = vol_change.shift(lag).astype(np.float32)
        
        # Current return (for immediate signal)
        features['return_current'] = returns.astype(np.float32)
        
        # Cumulative return over last 8 bars (momentum)
        features['return_momentum_8'] = (close / close.shift(8) - 1).astype(np.float32)
        
        return features
    
    def _add_percentage_range_features(self, features: pd.DataFrame, 
                                       df: pd.DataFrame) -> pd.DataFrame:
        """
        Add percentage-based range and shadow features.
        
        These are STATIONARY - don't depend on price level.
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Range as percentage of close (stationary)
        range_pct = ((high - low) / close).astype(np.float32)
        features['range_pct'] = range_pct
        
        # Upper shadow as percentage of close
        upper_shadow = ((high - close) / close).astype(np.float32)
        features['upper_shadow_pct'] = upper_shadow
        
        # Lower shadow as percentage of close
        lower_shadow = ((close - low) / close).astype(np.float32)
        features['lower_shadow_pct'] = lower_shadow
        
        # Body size as percentage
        body_pct = (np.abs(close - df['open']) / close).astype(np.float32)
        features['body_pct'] = body_pct
        
        # Is bullish/bearish (binary)
        features['is_bullish'] = (close > df['open']).astype(np.float32)
        
        return features
    
    def _add_ema_distance_features(self, features: pd.DataFrame, 
                                   df: pd.DataFrame) -> pd.DataFrame:
        """
        Add EMA distance as PERCENTAGE.
        
        This is STATIONARY - EMA distance doesn't grow with price level.
        """
        close = df['close']
        
        # Calculate EMA
        ema = close.ewm(span=self.ema_period, adjust=False).mean()
        
        # Distance from EMA as percentage (STATIONARY!)
        ema_distance_pct = ((close - ema) / ema).astype(np.float32)
        features['ema_distance_pct'] = ema_distance_pct
        
        # EMA slope (momentum)
        ema_slope = ema.pct_change().astype(np.float32)
        features['ema_slope'] = ema_slope
        
        # Store EMA for trend filtering in signal layer
        self._ema_current = float(ema.iloc[-1])
        
        return features
    
    def _add_dxy_correlation(self, features: pd.DataFrame, 
                              df: pd.DataFrame, 
                              dxy_df: pd.DataFrame) -> pd.DataFrame:
        """
        Align and add DXY correlation features using RETURNS.
        
        Args:
            features: Feature DataFrame being built
            df: Gold OHLC data
            dxy_df: DXY data with 'close' column
        """
        try:
            # Ensure DXY has close column
            if 'close' not in dxy_df.columns:
                return features
            
            # Align DXY to Gold timestamps
            dxy_aligned = dxy_df['close'].reindex(df.index, method='ffill')
            dxy_aligned = dxy_aligned.astype(np.float32)
            
            # Store aligned DXY for later use
            self.dxy_aligned = dxy_aligned
            
            # DXY returns (stationary)
            dxy_returns = dxy_aligned.pct_change().astype(np.float32)
            features['dxy_return_current'] = dxy_returns
            
            # DXY return lags
            for lag in self.lag_periods:
                features[f'dxy_return_lag_{lag}'] = dxy_returns.shift(lag)
            
            # Gold-DXY return correlation (product = proxy for correlation)
            gold_returns = df['close'].pct_change().astype(np.float32)
            features['gold_dxy_return_corr'] = (gold_returns * dxy_returns).astype(np.float32)
            
            return features
            
        except Exception as e:
            # If DXY alignment fails, return features without DXY
            return features
    
    def get_ema_current(self) -> float:
        """Get current EMA value for trend filtering."""
        return getattr(self, '_ema_current', 0.0)
    
    def get_last_close(self) -> float:
        """Get last close price for inference conversion."""
        return self._last_close
    
    def get_feature_columns(self) -> list:
        """Return list of generated feature column names."""
        return self._feature_columns
    
    def prepare_training_data(self, ohlcv_df: pd.DataFrame,
                              target_high_pct: pd.Series,  # CHANGED: percentage targets
                              target_low_pct: pd.Series,    # CHANGED: percentage targets
                              dxy_df: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Prepare feature matrix and targets for training.
        
        Args:
            ohlcv_df: Input OHLCV data
            target_high_pct: Target for next high as PERCENTAGE from current close
            target_low_pct: Target for next low as PERCENTAGE from current close
            dxy_df: Optional DXY data
            
        Returns:
            Tuple of (features, target_high_pct, target_low_pct)
        """
        features = self.generate_features(ohlcv_df, dxy_df)
        
        # Align targets with features
        # Drop rows where targets are NaN
        valid_idx = ~(target_high_pct.isna() | target_low_pct.isna())
        
        X = features[valid_idx].astype(np.float32)
        y_high = target_high_pct[valid_idx].astype(np.float32)
        y_low = target_low_pct[valid_idx].astype(np.float32)
        
        # Additional cleanup: drop any rows with NaN in features
        valid_features = ~X.isna().any(axis=1)
        X = X[valid_features]
        y_high = y_high[valid_features]
        y_low = y_low[valid_features]
        
        return X, y_high, y_low
