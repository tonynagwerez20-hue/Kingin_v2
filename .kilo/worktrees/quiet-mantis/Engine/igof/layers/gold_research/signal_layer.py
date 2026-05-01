"""
Gold Research Strategy - Signal Layer
=====================================
Implements the "Research-Based Range Strategy" for Gold trading.

CRITICAL FIX: Out-of-Bounds Safety & Trend Filter
=================================================
The original implementation had no protection against:
1. Black swan events where price moves outside training range
2. Trading against strong trends

NEW Implementation:
- Out-of-Bounds Safety: If price is >2% outside predicted range, force WAIT
- Trend Filter: If Price > EMA_24, ignore all SELL signals
- This prevents the "Permanent Sell" bug during price surges

Signal Logic:
- BUY: If current_price is within 5% of pred_low
- SELL: If current_price is within 5% of pred_high AND trend allows
- WAIT: If price is in the middle OR out of bounds OR against trend

Designed for i3/4GB RAM constraint.
"""

import numpy as np
from typing import Tuple, Optional
import gc


class GoldSignalLogic:
    """
    Implements range-based trading signals for Gold with regime drift protection.
    
    Strategy based on "Informer" research - Range-Based Prediction:
    - Buy near predicted low (undervalued)
    - Sell near predicted high (overvalued)
    - Wait in the middle (no clear edge)
    
    NEW: Out-of-bounds protection + EMA trend filter
    """
    
    def __init__(self, 
                 proximity_threshold: float = 0.05,
                 min_range_pct: float = 0.002,
                 confidence_filter: float = 0.0,
                 ema_period: int = 24,
                 enable_trend_filter: bool = True,
                 out_of_bounds_threshold: float = 0.02):
        """
        Initialize the signal logic.
        
        Args:
            proximity_threshold: % threshold from boundary (default 5%)
            min_range_pct: Minimum predicted range as % (filter noise)
            confidence_filter: Minimum R² score to trust predictions
            ema_period: Period for EMA trend calculation (default 24 for H1)
            enable_trend_filter: Enable trend filter to avoid counter-trend trades
            out_of_bounds_threshold: % threshold for out-of-bounds detection (2%)
        """
        self.proximity_threshold = proximity_threshold
        self.min_range_pct = min_range_pct
        self.confidence_filter = confidence_filter
        self.ema_period = ema_period
        self.enable_trend_filter = enable_trend_filter
        self.out_of_bounds_threshold = out_of_bounds_threshold
        
        # EMA for trend filtering (set during prediction)
        self.current_ema = None
        self.current_close = None
        
        # Signal history for analysis
        self.signal_history = []
        self.max_history = 100
    
    def set_ema(self, ema_value: float):
        """Set current EMA value for trend filtering."""
        self.current_ema = ema_value
    
    def set_current_price(self, price: float):
        """Set current close price."""
        self.current_close = price
    
    def get_action(self, 
                   current_price: float, 
                   pred_high: float, 
                   pred_low: float,
                   current_ema: Optional[float] = None) -> Tuple[str, dict]:
        """
        Determine trading action based on current price and predictions.
        
        Args:
            current_price: Current market price
            pred_high: Predicted next high
            pred_low: Predicted next low
            current_ema: Current EMA value for trend filtering (optional)
            
        Returns:
            Tuple of (signal, details_dict)
            Signals: "BUY", "SELL", "WAIT"
        """
        try:
            # Input validation
            if current_price <= 0 or pred_high <= 0 or pred_low <= 0:
                return "WAIT", {"error": "Invalid price values"}
            
            # Store for trend filtering
            self.current_close = current_price
            if current_ema is not None:
                self.current_ema = current_ema
            
            # Calculate predicted range
            predicted_range = pred_high - pred_low
            range_pct = predicted_range / current_price
            
            # ===== OUT-OF-BOUNDS SAFETY CHECK =====
            # If price is too far outside predicted range, model is "confused"
            dist_above_pred = (current_price - pred_high) / current_price
            dist_below_pred = (pred_low - current_price) / current_price
            
            is_out_of_bounds = (dist_above_pred > self.out_of_bounds_threshold or 
                              dist_below_pred > self.out_of_bounds_threshold)
            
            if is_out_of_bounds:
                return "WAIT", {
                    "reason": "out_of_bounds",
                    "dist_above_pred": float(dist_above_pred),
                    "dist_below_pred": float(dist_below_pred),
                    "threshold": self.out_of_bounds_threshold,
                    "current_price": float(current_price),
                    "pred_high": float(pred_high),
                    "pred_low": float(pred_low)
                }
            
            # Filter: Minimum range check
            if range_pct < self.min_range_pct:
                return "WAIT", {
                    "reason": "range_too_small",
                    "range_pct": float(range_pct),
                    "threshold": self.min_range_pct
                }
            
            # Calculate distances from boundaries
            dist_to_low = current_price - pred_low
            dist_to_high = pred_high - current_price
            
            # Calculate proximity as percentage of range
            if predicted_range > 0:
                pct_from_low = dist_to_low / predicted_range
                pct_from_high = dist_to_high / predicted_range
            else:
                return "WAIT", {"error": "Invalid predicted range"}
            
            # ===== TREND FILTER =====
            # If trend is up (price > EMA), don't SELL
            is_uptrend = current_ema is not None and current_price > current_ema
            
            if is_uptrend and self.enable_trend_filter:
                # In uptrend, only allow BUY or WAIT
                trend_filter_active = True
            else:
                trend_filter_active = False
            
            # Signal determination
            signal = "WAIT"
            details = {
                "current_price": float(current_price),
                "pred_high": float(pred_high),
                "pred_low": float(pred_low),
                "predicted_range": float(predicted_range),
                "range_pct": float(range_pct),
                "pct_from_low": float(pct_from_low),
                "pct_from_high": float(pct_from_high),
                "is_uptrend": bool(is_uptrend) if current_ema else None,
                "trend_filter_active": trend_filter_active
            }
            
            # BUY: Price within threshold of predicted low
            if pct_from_low <= self.proximity_threshold:
                signal = "BUY"
                details["signal_reason"] = "near_predicted_low"
                details["proximity_to_low"] = float(pct_from_low)
            
            # SELL: Price within threshold of predicted high
            # BUT check trend filter first!
            elif pct_from_high <= self.proximity_threshold:
                if trend_filter_active:
                    # In uptrend, ignore SELL signals
                    signal = "WAIT"
                    details["signal_reason"] = "sell_blocked_by_trend"
                    details["trend_reason"] = "price_above_ema_uptrend"
                else:
                    signal = "SELL"
                    details["signal_reason"] = "near_predicted_high"
                    details["proximity_to_high"] = float(pct_from_high)
            
            # WAIT: Price in the middle
            else:
                signal = "WAIT"
                details["signal_reason"] = "in_middle_range"
            
            # Record signal in history
            self._record_signal(signal, details)
            
            # Force garbage collection periodically
            if len(self.signal_history) % 10 == 0:
                gc.collect()
            
            return signal, details
            
        except Exception as e:
            return "WAIT", {"error": str(e)}
    
    def get_action_with_confidence(self,
                                    current_price: float,
                                    pred_high: float,
                                    pred_low: float,
                                    model_confidence: float = 1.0,
                                    current_ema: Optional[float] = None) -> Tuple[str, dict]:
        """
        Get action with model confidence filtering and trend filter.
        
        Args:
            current_price: Current market price
            pred_high: Predicted next high
            pred_low: Predicted next low
            model_confidence: Model R² score (0-1)
            current_ema: Current EMA for trend filtering
            
        Returns:
            Tuple of (signal, details_dict)
        """
        # If model confidence is below threshold, always wait
        if model_confidence < self.confidence_filter:
            return "WAIT", {
                "reason": "low_model_confidence",
                "confidence": float(model_confidence),
                "threshold": self.confidence_filter
            }
        
        # Get base signal with trend filter
        signal, details = self.get_action(current_price, pred_high, pred_low, current_ema)
        
        # Add confidence to details
        details["model_confidence"] = float(model_confidence)
        
        return signal, details
    
    def _record_signal(self, signal: str, details: dict):
        """Record signal in history for analysis."""
        record = {
            "signal": signal,
            "timestamp": details.get("current_price"),  # Using price as placeholder
            "details": details
        }
        
        self.signal_history.append(record)
        
        # Trim history if too long
        if len(self.signal_history) > self.max_history:
            self.signal_history = self.signal_history[-self.max_history:]
    
    def get_signal_stats(self) -> dict:
        """Get statistics on signal distribution."""
        if not self.signal_history:
            return {"total_signals": 0}
        
        signals = [s["signal"] for s in self.signal_history]
        
        return {
            "total_signals": len(signals),
            "buy_count": signals.count("BUY"),
            "sell_count": signals.count("SELL"),
            "wait_count": signals.count("WAIT"),
            "buy_ratio": signals.count("BUY") / len(signals),
            "sell_ratio": signals.count("SELL") / len(signals)
        }
    
    def reset_history(self):
        """Clear signal history."""
        self.signal_history = []
        gc.collect()
    
    def update_parameters(self, 
                         proximity_threshold: Optional[float] = None,
                         min_range_pct: Optional[float] = None,
                         enable_trend_filter: Optional[bool] = None,
                         out_of_bounds_threshold: Optional[float] = None):
        """
        Update strategy parameters.
        
        Args:
            proximity_threshold: New proximity threshold
            min_range_pct: New minimum range percentage
            enable_trend_filter: Enable/disable trend filter
            out_of_bounds_threshold: New OOB threshold
        """
        if proximity_threshold is not None:
            self.proximity_threshold = proximity_threshold
        if min_range_pct is not None:
            self.min_range_pct = min_range_pct
        if enable_trend_filter is not None:
            self.enable_trend_filter = enable_trend_filter
        if out_of_bounds_threshold is not None:
            self.out_of_bounds_threshold = out_of_bounds_threshold


class AdaptiveSignalLogic(GoldSignalLogic):
    """
    Adaptive version of GoldSignalLogic that adjusts thresholds
    based on market volatility.
    """
    
    def __init__(self, 
                 base_threshold: float = 0.05,
                 volatility_multiplier: float = 1.5,
                 min_threshold: float = 0.02,
                 max_threshold: float = 0.15,
                 ema_period: int = 24,
                 enable_trend_filter: bool = True):
        """
        Initialize adaptive signal logic.
        
        Args:
            base_threshold: Base proximity threshold
            volatility_multiplier: Multiply threshold in high volatility
            min_threshold: Minimum threshold cap
            max_threshold: Maximum threshold cap
            ema_period: Period for EMA trend
            enable_trend_filter: Enable trend filter
        """
        super().__init__(
            proximity_threshold=base_threshold,
            ema_period=ema_period,
            enable_trend_filter=enable_trend_filter
        )
        
        self.base_threshold = base_threshold
        self.volatility_multiplier = volatility_multiplier
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        
        self.current_volatility = 0.0
    
    def update_volatility(self, recent_prices: list):
        """
        Update current volatility estimate.
        
        Args:
            recent_prices: List of recent closing prices
        """
        if len(recent_prices) < 2:
            return
        
        try:
            prices = np.array(recent_prices, dtype=np.float32)
            returns = np.diff(prices) / prices[:-1]
            self.current_volatility = float(np.std(returns))
            
            # Adjust threshold based on volatility
            if self.current_volatility > 0.02:  # High volatility
                new_threshold = self.base_threshold * self.volatility_multiplier
            else:
                new_threshold = self.base_threshold
            
            # Cap threshold
            self.proximity_threshold = max(
                self.min_threshold,
                min(self.max_threshold, new_threshold)
            )
            
        except Exception:
            pass  # Keep previous threshold on error
    
    def get_action_adaptive(self,
                           current_price: float,
                           pred_high: float,
                           pred_low: float,
                           recent_prices: list = None,
                           current_ema: float = None) -> Tuple[str, dict]:
        """
        Get action with adaptive threshold adjustment and trend filter.
        
        Args:
            current_price: Current market price
            pred_high: Predicted next high
            pred_low: Predicted next low
            recent_prices: Recent prices for volatility calculation
            current_ema: Current EMA for trend filtering
            
        Returns:
            Tuple of (signal, details_dict)
        """
        # Update volatility if prices provided
        if recent_prices is not None:
            self.update_volatility(recent_prices)
        
        # Get signal with adaptive threshold
        signal, details = self.get_action(current_price, pred_high, pred_low, current_ema)
        
        # Add volatility info to details
        details["current_volatility"] = self.current_volatility
        details["adaptive_threshold"] = self.proximity_threshold
        
        return signal, details


def create_conservative_signal() -> GoldSignalLogic:
    """Factory for conservative (tight) signal logic."""
    return GoldSignalLogic(
        proximity_threshold=0.03,  # 3% threshold
        min_range_pct=0.002,       # 0.2% min range
        enable_trend_filter=True,
        out_of_bounds_threshold=0.02
    )


def create_aggressive_signal() -> GoldSignalLogic:
    """Factory for aggressive (loose) signal logic."""
    return GoldSignalLogic(
        proximity_threshold=0.10,  # 10% threshold
        min_range_pct=0.005,       # 0.5% min range
        enable_trend_filter=False, # Disable for aggressive
        out_of_bounds_threshold=0.03
    )
