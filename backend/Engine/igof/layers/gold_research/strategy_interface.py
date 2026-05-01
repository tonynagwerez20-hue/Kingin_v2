"""
Gold Research Strategy - Strategy Interface
============================================
Main wrapper class that orchestrates all three layers:
- Feature Layer (feature_layer.py) - Price-agnostic features
- Predictive Layer (predictive_layer.py) - Percentage target prediction
- Signal Layer (signal_layer.py) - Trend filter + OOB safety

This is the single point of contact for your existing bot.

CRITICAL FIX: Regime Drift
==========================
The strategy now uses:
1. Percentage-based features (returns, not absolute prices)
2. Percentage-based targets (offset from current close)
3. Absolute price inference using: pred_high = close * (1 + pred_high_pct)
4. Trend filter: No SELL when price > EMA_24
5. Out-of-bounds safety: Force WAIT if price >2% outside predicted range

Usage:
    from gold_research_strategy.strategy_interface import GoldResearchStrategy
    
    # Initialize in your bot's setup
    gold_strat = GoldResearchStrategy()
    
    # Inside your bot's loop
    tick_data = get_latest_ohlc()  # Your bot's existing data fetcher
    signal, bounds = gold_strat.run_tick(tick_data)
    
    if signal == "BUY":
        execute_trade("BUY")

Designed for i3/4GB RAM constraint with float32 and gc.collect().
"""

import numpy as np
import pandas as pd
import gc
from typing import Tuple, Dict, Optional, Any
import warnings

from .feature_layer import GoldFeatureGenerator
from .predictive_layer import RangePredictor, create_lite_predictor
from .signal_layer import GoldSignalLogic, AdaptiveSignalLogic


class GoldResearchStrategy:
    """
    Main strategy wrapper that orchestrates feature generation,
    prediction, and signal generation.
    
    Designed as a pluggable module for existing trading bots.
    
    KEY: Now uses percentage-based targets for regime-drift immunity.
    """
    
    def __init__(self, 
                 use_adaptive_signals: bool = False,
                 lite_mode: bool = True,
                 proximity_threshold: float = 0.05,
                 ema_period: int = 24,
                 enable_trend_filter: bool = True,
                 out_of_bounds_threshold: float = 0.02):
        """
        Initialize the Gold Research Strategy.
        
        Args:
            use_adaptive_signals: Use adaptive signal logic (adjusts to volatility)
            lite_mode: Use lightweight predictor (for 4GB RAM)
            proximity_threshold: Signal threshold (0.05 = 5%)
            ema_period: Period for EMA trend filter (default 24 for H1)
            enable_trend_filter: Enable trend filter to avoid counter-trend trades
            out_of_bounds_threshold: OOB threshold (default 2%)
        """
        # Initialize layers
        self.ema_period = ema_period
        self.feature_generator = GoldFeatureGenerator(ema_period=ema_period)
        
        # Choose predictor based on memory constraint
        if lite_mode:
            self.predictor = create_lite_predictor()
        else:
            self.predictor = RangePredictor()
        
        # Choose signal logic with trend filter and OOB safety
        if use_adaptive_signals:
            self.signal_logic = AdaptiveSignalLogic(
                base_threshold=proximity_threshold,
                ema_period=ema_period,
                enable_trend_filter=enable_trend_filter
            )
        else:
            self.signal_logic = GoldSignalLogic(
                proximity_threshold=proximity_threshold,
                min_range_pct=0.002,  # Lower threshold for more signals
                ema_period=ema_period,
                enable_trend_filter=enable_trend_filter,
                out_of_bounds_threshold=out_of_bounds_threshold
            )
        
        # Internal state
        self.is_trained = False
        self.buffer_size = 100  # Rolling window for feature generation
        self.data_buffer = None
        self.last_signal = None
        self.last_bounds = None
        
        # Metadata
        self.training_history = []
        self.config = {
            'use_adaptive_signals': use_adaptive_signals,
            'lite_mode': lite_mode,
            'proximity_threshold': proximity_threshold,
            'ema_period': ema_period,
            'enable_trend_filter': enable_trend_filter,
            'out_of_bounds_threshold': out_of_bounds_threshold,
            'buffer_size': self.buffer_size
        }
    
    def train(self, 
              ohlcv_df: pd.DataFrame,
              dxy_df: Optional[pd.DataFrame] = None,
              retrain: bool = False) -> Dict[str, Any]:
        """
        Train the strategy on historical data.
        
        CRITICAL: Creates PERCENTAGE targets, not absolute prices.
        Target_High_Pct = (Next_High - Current_Close) / Current_Close
        
        Args:
            ohlcv_df: DataFrame with columns [open, high, low, close, volume]
            dxy_df: Optional DXY data for correlation
            retrain: Force retrain even if already trained
            
        Returns:
            Training results dictionary
        """
        try:
            # Check if already trained
            if self.is_trained and not retrain:
                return {'status': 'already_trained'}
            
            # Validate minimum data size
            if len(ohlcv_df) < 50:
                raise ValueError("Need at least 50 samples for training")
            
            # Convert to float32 for memory efficiency (only numeric columns)
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in ohlcv_df.columns:
                    ohlcv_df[col] = ohlcv_df[col].astype(np.float32)
            
            # ===== CREATE PERCENTAGE TARGETS =====
            # This is the KEY FIX for regime drift!
            # Instead of predicting absolute high/low, we predict percentage offset
            
            close = ohlcv_df['close']
            next_high = ohlcv_df['high'].shift(-1)
            next_low = ohlcv_df['low'].shift(-1)
            
            # Percentage targets (STATIONARY - work at any price level!)
            target_high_pct = (next_high - close) / close
            target_low_pct = (next_low - close) / close
            
            # Generate features and prepare training data with percentage targets
            X, y_high, y_low = self.feature_generator.prepare_training_data(
                ohlcv_df, target_high_pct, target_low_pct, dxy_df
            )
            
            # Drop any remaining NaN values
            valid_mask = ~(X.isna().any(axis=1) | y_high.isna() | y_low.isna())
            X = X[valid_mask]
            y_high = y_high[valid_mask]
            y_low = y_low[valid_mask]
            
            if len(X) < 30:
                raise ValueError("Not enough valid training samples after feature generation")
            
            # Train the predictor on percentage targets
            train_results = self.predictor.train(X, y_high, y_low)
            
            # Force garbage collection after training
            gc.collect()
            
            self.is_trained = True
            self.data_buffer = ohlcv_df.tail(self.buffer_size).copy()
            
            return {
                'status': 'trained',
                'n_samples': len(X),
                'n_features': X.shape[1],
                'train_r2_high': train_results.get('train_r2_high'),
                'train_r2_low': train_results.get('train_r2_low'),
                'target_type': 'percentage_offset'
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def run_tick(self, 
                 tick_data: pd.DataFrame) -> Tuple[str, Dict[str, float]]:
        """
        Process a single tick/update and return trading signal.
        
        This is the main entry point for your bot's loop.
        
        CRITICAL: Uses predict_absolute() to convert percentage predictions
        to absolute prices, ensuring predictions track the actual price.
        
        Args:
            tick_data: DataFrame with latest OHLCV data
                      Must contain [open, high, low, close, volume]
            
        Returns:
            Tuple of (signal, bounds_dict)
            - signal: "BUY", "SELL", or "WAIT"
            - bounds: {"pred_high": float, "pred_low": float}
        """
        try:
            # Validate input
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in tick_data.columns for col in required_cols):
                return "WAIT", {"error": f"Missing columns. Required: {required_cols}"}
            
            # Convert to float32
            tick_data = tick_data[required_cols].astype(np.float32)
            
            # Update data buffer
            if self.data_buffer is None:
                self.data_buffer = tick_data.copy()
            else:
                self.data_buffer = pd.concat(
                    [self.data_buffer, tick_data], 
                    ignore_index=True
                ).tail(self.buffer_size)
            
            # Check if trained
            if not self.is_trained:
                return "WAIT", {"error": "Strategy not trained. Call train() first."}
            
            # Generate features from current buffer
            features = self.feature_generator.generate_features(self.data_buffer)
            
            # Get the latest feature row for prediction
            if len(features) == 0:
                return "WAIT", {"error": "No features generated"}
            
            latest_features = features.iloc[-1:].copy()
            
            # Handle any NaN in features (from lag calculations)
            if latest_features.isna().any().any():
                return "WAIT", {"error": "NaN in features, need more warmup data"}
            
            # Get current price
            current_price = float(tick_data['close'].iloc[-1])
            
            # Get EMA for trend filtering
            current_ema = self.feature_generator.get_ema_current()
            
            # ===== KEY: Use predict_absolute to convert percentages to prices =====
            # This is the regime drift fix!
            # pred_high = current_close * (1 + pred_high_pct)
            pred_high, pred_low = self.predictor.predict_absolute(
                latest_features, 
                current_price
            )
            
            # Get trading signal with trend filter
            signal, signal_details = self.signal_logic.get_action(
                current_price, 
                pred_high, 
                pred_low,
                current_ema  # Pass EMA for trend filtering
            )
            
            # Store results
            self.last_signal = signal
            self.last_bounds = {
                "pred_high": pred_high,
                "pred_low": pred_low,
                "current_price": current_price,
                "current_ema": current_ema
            }
            
            return signal, self.last_bounds
            
        except Exception as e:
            return "WAIT", {"error": str(e)}
    
    def run_tick_dict(self, tick_dict: Dict) -> Tuple[str, Dict[str, float]]:
        """
        Process tick from dictionary input (for simpler integration).
        
        Args:
            tick_dict: Dictionary with keys: open, high, low, close, volume
            
        Returns:
            Tuple of (signal, bounds_dict)
        """
        # Convert dict to DataFrame
        df = pd.DataFrame([tick_dict])
        return self.run_tick(df)
    
    def update_parameters(self, **kwargs):
        """
        Update strategy parameters.
        
        Args:
            **kwargs: Parameters to update (proximity_threshold, etc.)
        """
        if 'proximity_threshold' in kwargs:
            threshold = kwargs['proximity_threshold']
            self.signal_logic.update_parameters(proximity_threshold=threshold)
            self.config['proximity_threshold'] = threshold
        
        if 'buffer_size' in kwargs:
            self.buffer_size = kwargs['buffer_size']
            self.config['buffer_size'] = self.buffer_size
        
        if 'enable_trend_filter' in kwargs:
            enable = kwargs['enable_trend_filter']
            self.signal_logic.update_parameters(enable_trend_filter=enable)
            self.config['enable_trend_filter'] = enable
        
        if 'out_of_bounds_threshold' in kwargs:
            threshold = kwargs['out_of_bounds_threshold']
            self.signal_logic.update_parameters(out_of_bounds_threshold=threshold)
            self.config['out_of_bounds_threshold'] = threshold
    
    def retrain(self, 
                new_data: pd.DataFrame,
                dxy_df: Optional[pd.DataFrame] = None) -> Dict:
        """
        Retrain with new data (incremental or full).
        
        Args:
            new_data: New OHLCV data
            dxy_df: Optional DXY data
            
        Returns:
            Retrain results
        """
        # Full retrain
        return self.train(new_data, dxy_df, retrain=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current strategy status."""
        return {
            'is_trained': self.is_trained,
            'config': self.config,
            'buffer_size': len(self.data_buffer) if self.data_buffer is not None else 0,
            'last_signal': self.last_signal,
            'predictor_info': self.predictor.get_model_info() if self.is_trained else None,
            'signal_stats': self.signal_logic.get_signal_stats()
        }
    
    def reset(self):
        """Reset strategy state and free memory."""
        self.is_trained = False
        self.data_buffer = None
        self.last_signal = None
        self.last_bounds = None
        self.predictor.reset()
        self.signal_logic.reset_history()
        gc.collect()
    
    def get_required_columns(self) -> list:
        """Return list of required input columns."""
        return ['open', 'high', 'low', 'close', 'volume']
    
    def validate_input(self, data: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate input data format.
        
        Args:
            data: Input DataFrame
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required = self.get_required_columns()
        
        if not isinstance(data, pd.DataFrame):
            return False, "Input must be a pandas DataFrame"
        
        missing = [col for col in required if col not in data.columns]
        if missing:
            return False, f"Missing columns: {missing}"
        
        if len(data) == 0:
            return False, "Empty DataFrame"
        
        return True, ""


class GoldStrategyBuilder:
    """
    Builder class for convenient strategy configuration.
    """
    
    @staticmethod
    def create_lite() -> GoldResearchStrategy:
        """Create a lite strategy for 4GB RAM constraint."""
        return GoldResearchStrategy(
            use_adaptive_signals=False,
            lite_mode=True,
            proximity_threshold=0.05,
            ema_period=24,
            enable_trend_filter=True,
            out_of_bounds_threshold=0.02
        )
    
    @staticmethod
    def create_standard() -> GoldResearchStrategy:
        """Create a standard strategy with better accuracy."""
        return GoldResearchStrategy(
            use_adaptive_signals=False,
            lite_mode=False,
            proximity_threshold=0.05,
            ema_period=24,
            enable_trend_filter=True,
            out_of_bounds_threshold=0.02
        )
    
    @staticmethod
    def create_adaptive() -> GoldResearchStrategy:
        """Create an adaptive strategy that adjusts to volatility."""
        return GoldResearchStrategy(
            use_adaptive_signals=True,
            lite_mode=True,
            proximity_threshold=0.05,
            ema_period=24,
            enable_trend_filter=True,
            out_of_bounds_threshold=0.02
        )
    
    @staticmethod
    def create_conservative() -> GoldResearchStrategy:
        """Create a conservative strategy with tight thresholds."""
        return GoldResearchStrategy(
            use_adaptive_signals=False,
            lite_mode=True,
            proximity_threshold=0.03,
            ema_period=24,
            enable_trend_filter=True,
            out_of_bounds_threshold=0.015
        )
    
    @staticmethod
    def create_aggressive() -> GoldResearchStrategy:
        """Create an aggressive strategy with loose thresholds."""
        return GoldResearchStrategy(
            use_adaptive_signals=False,
            lite_mode=False,
            proximity_threshold=0.10,
            ema_period=24,
            enable_trend_filter=False,  # No trend filter for aggressive
            out_of_bounds_threshold=0.03
        )
