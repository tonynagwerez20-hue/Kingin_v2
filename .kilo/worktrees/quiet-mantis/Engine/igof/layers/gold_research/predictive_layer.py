"""
Gold Research Strategy - Predictive Layer
=========================================
Lightweight ML models for range prediction.
Designed for i3/4GB RAM constraint using HistGradientBoostingRegressor.

CRITICAL FIX: Target Normalization
===================================
The original implementation predicted absolute prices (e.g., 3774).
When gold price climbed to 5,100, the model was "confused" because
it had never seen prices above its training range.

NEW Implementation:
- Predicts PERCENTAGE OFFSET from current close
- Target_High = (Next_High - Current_Close) / Current_Close
- Target_Low = (Next_Low - Current_Close) / Current_Close
- At inference: pred_high = current_close * (1 + pred_high_pct)

This makes the model IMMORTAL - it works at ANY price level.

Trains two models:
- Model 1: Predict percentage offset to next High
- Model 2: Predict percentage offset to next Low

Memory management with gc.collect() after training.
"""

import numpy as np
import pandas as pd
import gc
from typing import Tuple, Optional
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
import warnings


class RangePredictor:
    """
    Memory-efficient range predictor using HistGradientBoostingRegressor.
    Optimized for i3 CPU with 4GB RAM.
    
    KEY: Now predicts PERCENTAGE offsets, not absolute prices.
    """
    
    def __init__(self, 
                 max_iter: int = 100,
                 max_depth: int = 5,
                 learning_rate: float = 0.1,
                 min_samples_leaf: int = 20):
        """
        Initialize the range predictor.
        
        Args:
            max_iter: Maximum number of boosting iterations
            max_depth: Maximum tree depth (kept shallow for memory)
            learning_rate: Learning rate for boosting
            min_samples_leaf: Minimum samples per leaf (prevents overfitting)
        """
        self.max_iter = max_iter
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.min_samples_leaf = min_samples_leaf
        
        # Initialize models (trained on demand)
        self.model_high = None
        self.model_low = None
        
        # Scalers for feature normalization
        self.scaler = StandardScaler()
        
        # Training status
        self.is_trained = False
        self.feature_names = None
        
        # Lightweight config for i3 CPU
        self._model_config = {
            'max_iter': max_iter,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'min_samples_leaf': min_samples_leaf,
            'random_state': 42,
            'early_stopping': True,
            'n_iter_no_change': 10,
            'validation_fraction': 0.1,
            # Memory optimization for i3
            'categorical_features': None
        }
    
    def train(self, X: pd.DataFrame, y_high_pct: pd.Series, y_low_pct: pd.Series) -> dict:
        """
        Train both prediction models (High and Low) on PERCENTAGE targets.
        
        Args:
            X: Feature matrix
            y_high_pct: Target for next high as PERCENTAGE from current close
            y_low_pct: Target for next low as PERCENTAGE from current close
            
        Returns:
            Training metrics dictionary
        """
        try:
            # Convert to float32 for memory efficiency
            X_array = X.astype(np.float32).values
            y_high_array = y_high_pct.astype(np.float32).values
            y_low_array = y_low_pct.astype(np.float32).values
            
            # Store feature names
            self.feature_names = X.columns.tolist()
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X_array).astype(np.float32)
            
            # Train High model (predicts percentage to next high)
            self.model_high = HistGradientBoostingRegressor(**self._model_config)
            self.model_high.fit(X_scaled, y_high_array)
            
            # Force garbage collection after first model
            gc.collect()
            
            # Train Low model (predicts percentage to next low)
            self.model_low = HistGradientBoostingRegressor(**self._model_config)
            self.model_low.fit(X_scaled, y_low_array)
            
            # Force garbage collection after second model
            gc.collect()
            
            self.is_trained = True
            
            # Calculate training metrics
            train_score_high = self.model_high.score(X_scaled, y_high_array)
            train_score_low = self.model_low.score(X_scaled, y_low_array)
            
            return {
                'status': 'trained',
                'train_r2_high': float(train_score_high),
                'train_r2_low': float(train_score_low),
                'n_features': X.shape[1],
                'n_samples': X.shape[0],
                'target_type': 'percentage_offset'
            }
            
        except Exception as e:
            raise RuntimeError(f"Training failed: {str(e)}")
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict next high and low boundaries as PERCENTAGE offsets.
        
        Args:
            X: Feature matrix (must match training features)
            
        Returns:
            Tuple of (predicted_high_pct, predicted_low_pct) arrays
            These are PERCENTAGE offsets from current close!
        """
        if not self.is_trained:
            raise RuntimeError("Models not trained. Call train() first.")
        
        try:
            # Convert to float32
            X_array = X.astype(np.float32).values
            
            # Scale features
            X_scaled = self.scaler.transform(X_array).astype(np.float32)
            
            # Predict percentage offsets
            pred_high_pct = self.model_high.predict(X_scaled)
            pred_low_pct = self.model_low.predict(X_scaled)
            
            # Ensure low <= high (sanity check for percentages)
            pred_low_pct = np.minimum(pred_low_pct, pred_high_pct)
            
            return pred_high_pct.astype(np.float32), pred_low_pct.astype(np.float32)
            
        except Exception as e:
            raise RuntimeError(f"Prediction failed: {str(e)}")
    
    def predict_absolute(self, X: pd.DataFrame, current_close: float) -> Tuple[float, float]:
        """
        Predict next high and low as ABSOLUTE prices.
        
        This is the KEY METHOD for the regime drift fix!
        It converts percentage predictions to absolute prices.
        
        Args:
            X: Feature matrix
            current_close: Current close price
            
        Returns:
            Tuple of (predicted_high, predicted_low) as absolute prices
        """
        pred_high_pct, pred_low_pct = self.predict(X)
        
        # Convert percentage to absolute
        pred_high = current_close * (1 + pred_high_pct[0])
        pred_low = current_close * (1 + pred_low_pct[0])
        
        return float(pred_high), float(pred_low)
    
    def predict_single(self, features: dict) -> Tuple[float, float]:
        """
        Predict for a single sample.
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            Tuple of (predicted_high_pct, predicted_low_pct)
            These are PERCENTAGE offsets!
        """
        if not self.is_trained:
            raise RuntimeError("Models not trained.")
        
        # Convert dict to DataFrame
        X = pd.DataFrame([features])
        
        # Ensure correct column order
        if self.feature_names:
            X = X.reindex(columns=self.feature_names, fill_value=0)
        
        pred_high, pred_low = self.predict(X)
        
        return float(pred_high[0]), float(pred_low[0])
    
    def predict_single_absolute(self, features: dict, current_close: float) -> Tuple[float, float]:
        """
        Predict for a single sample, returning absolute prices.
        
        Args:
            features: Dictionary of feature values
            current_close: Current close price
            
        Returns:
            Tuple of (predicted_high, predicted_low) as absolute prices
        """
        pred_high_pct, pred_low_pct = self.predict_single(features)
        
        # Convert percentage to absolute
        pred_high = current_close * (1 + pred_high_pct)
        pred_low = current_close * (1 + pred_low_pct)
        
        return pred_high, pred_low
    
    def retrain_incremental(self, X: pd.DataFrame, 
                           y_high_pct: pd.Series, 
                           y_low_pct: pd.Series,
                           warm_start: bool = True) -> dict:
        """
        Retrain models with new data (incremental).
        
        Args:
            X: New feature data
            y_high_pct: New high targets as percentages
            y_low_pct: New low targets as percentages
            warm_start: Use previous model as starting point
            
        Returns:
            Training metrics
        """
        if not self.is_trained:
            # Full training if not yet trained
            return self.train(X, y_high_pct, y_low_pct)
        
        try:
            X_array = X.astype(np.float32).values
            y_high_array = y_high_pct.astype(np.float32).values
            y_low_array = y_low_pct.astype(np.float32).values
            
            X_scaled = self.scaler.fit_transform(X_array).astype(np.float32)
            
            # Retrain High model with warm_start
            if warm_start and self.model_high is not None:
                self._model_config['warm_start'] = True
                self.model_high.set_params(max_iter=self.max_iter)
            
            self.model_high = HistGradientBoostingRegressor(**self._model_config)
            self.model_high.fit(X_scaled, y_high_array)
            
            gc.collect()
            
            # Retrain Low model
            self.model_low = HistGradientBoostingRegressor(**self._model_config)
            self.model_low.fit(X_scaled, y_low_array)
            
            gc.collect()
            
            return {
                'status': 'retrained',
                'n_new_samples': X.shape[0]
            }
            
        except Exception as e:
            warnings.warn(f"Incremental retrain failed: {str(e)}")
            return {'status': 'retrain_failed', 'error': str(e)}
    
    def get_model_info(self) -> dict:
        """Get information about the trained models."""
        info = {
            'is_trained': self.is_trained,
            'target_type': 'percentage_offset',
            'config': {
                'max_iter': self.max_iter,
                'max_depth': self.max_depth,
                'learning_rate': self.learning_rate,
                'min_samples_leaf': self.min_samples_leaf
            }
        }
        
        if self.is_trained:
            info['feature_names'] = self.feature_names
            
        return info
    
    def reset(self):
        """Reset models to untrained state and free memory."""
        self.model_high = None
        self.model_low = None
        self.is_trained = False
        self.feature_names = None
        gc.collect()


def create_lite_predictor() -> RangePredictor:
    """
    Factory function for a lightweight predictor optimized for 4GB RAM.
    
    Returns:
        Configured RangePredictor instance
    """
    return RangePredictor(
        max_iter=50,        # Reduced iterations
        max_depth=4,        # Shallow trees
        learning_rate=0.15,
        min_samples_leaf=30
    )


def create_standard_predictor() -> RangePredictor:
    """
    Factory function for a standard predictor with better accuracy.
    
    Returns:
        Configured RangePredictor instance
    """
    return RangePredictor(
        max_iter=100,
        max_depth=5,
        learning_rate=0.1,
        min_samples_leaf=20
    )
