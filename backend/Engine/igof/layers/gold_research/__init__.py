"""
Gold Research Strategy Package
===============================

A modular, memory-efficient strategy package for Gold trading
based on "Informer" research (Range-Based Prediction).

Designed for i3 CPU with 4GB RAM constraint.

Modules:
- feature_layer: GoldFeatureGenerator - Memory-efficient feature generation
- predictive_layer: RangePredictor - HistGradientBoosting-based prediction
- signal_layer: GoldSignalLogic - Range-based trading signals
- strategy_interface: GoldResearchStrategy - Main orchestration class

Usage:
    from gold_research_strategy import GoldResearchStrategy
    
    # Initialize
    gold_strat = GoldResearchStrategy()
    
    # Train (once)
    gold_strat.train(historical_ohlcv)
    
    # Run tick (in your bot loop)
    signal, bounds = gold_strat.run_tick(tick_data)

Optimizations:
- All data uses float32 for memory efficiency
- HistGradientBoostingRegressor for CPU-efficient ML
- Manual gc.collect() after training
- No deep learning dependencies
"""

from .feature_layer import GoldFeatureGenerator
from .predictive_layer import RangePredictor, create_lite_predictor, create_standard_predictor
from .signal_layer import GoldSignalLogic, AdaptiveSignalLogic
from .strategy_interface import GoldResearchStrategy, GoldStrategyBuilder

__version__ = "1.0.0"

__all__ = [
    # Feature Layer
    "GoldFeatureGenerator",
    
    # Predictive Layer
    "RangePredictor",
    "create_lite_predictor",
    "create_standard_predictor",
    
    # Signal Layer
    "GoldSignalLogic",
    "AdaptiveSignalLogic",
    
    # Main Interface
    "GoldResearchStrategy",
    "GoldStrategyBuilder",
]
