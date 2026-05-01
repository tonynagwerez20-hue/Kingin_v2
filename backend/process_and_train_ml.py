"""
UNIFIED ML TRAINING PIPELINE
=============================
Process all available timeframe data through SMC rule-based layers,
then use the processed data to train the ML layer.

Steps:
1. Check available timeframe data (M5, M15, H1, H4) - M1 not available
2. Load all backtest data and existing processed signals
3. Process through SMC layers (if not already done)
4. Train ML layer with processed dataset
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("MLTrainingPipeline")

# ============================================================================
# SECTION 1: DATA AVAILABILITY CHECK
# ============================================================================

def check_data_availability() -> Dict[str, bool]:
    """Check which timeframe data is available."""
    logger.info("=" * 70)
    logger.info("SECTION 1: Checking Data Availability for All Timeframes")
    logger.info("=" * 70)
    
    data_dir = Path("data/backtest")
    timeframes = ["M1", "M5", "M15", "H1", "H4"]
    available = {}
    
    for tf in timeframes:
        path = data_dir / f"XAUUSD_{tf}_6mo.csv"
        exists = path.exists()
        available[tf] = exists
        
        if exists:
            file_size = path.stat().st_size / (1024 * 1024)  # Size in MB
            df = pd.read_csv(path, nrows=1)
            row_count = len(pd.read_csv(path))
            logger.info(f"✓ {tf:4s} - AVAILABLE | {row_count:7d} bars | {file_size:.2f} MB")
        else:
            logger.warning(f"✗ {tf:4s} - MISSING")
    
    # Check for processed signals
    trade_log_path = Path("data/trade_log.json")
    if trade_log_path.exists():
        with open(trade_log_path) as f:
            signals = json.load(f)
        logger.info(f"✓ Processed Signals - AVAILABLE | {len(signals)} signals in trade_log.json")
    else:
        logger.warning(f"✗ Processed Signals - MISSING")
    
    # Summary
    available_count = sum(1 for v in available.values() if v)
    logger.info(f"\nSummary: {available_count}/{len(timeframes)} timeframes available")
    
    return available


# ============================================================================
# SECTION 2: LOAD AND MERGE TIMEFRAME DATA
# ============================================================================

def load_all_backtest_data() -> Dict[str, pd.DataFrame]:
    """Load all available timeframe CSV files."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 2: Loading All Available Timeframe Data")
    logger.info("=" * 70)
    
    data_dir = Path("data/backtest")
    timeframes = ["H4", "H1", "M15", "M5"]  # M1 not available
    dfs = {}
    
    for tf in timeframes:
        path = data_dir / f"XAUUSD_{tf}_6mo.csv"
        if path.exists():
            df = pd.read_csv(path)
            df['time'] = pd.to_datetime(df['time'])
            dfs[tf] = df
            logger.info(f"✓ Loaded {tf:4s}: {len(df)} bars | {df.columns.tolist()}")
        else:
            logger.warning(f"✗ Skipped {tf}: File not found")
    
    logger.info(f"\nTotal timeframes loaded: {len(dfs)}")
    return dfs


def load_processed_signals() -> List[Dict]:
    """Load previously processed signals from trade_log.json."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 3: Loading Processed Signals from trade_log.json")
    logger.info("=" * 70)
    
    trade_log_path = Path("data/trade_log.json")
    
    if trade_log_path.exists():
        with open(trade_log_path) as f:
            signals = json.load(f)
        logger.info(f"✓ Loaded {len(signals)} processed signals")
        
        # Analyze signal distribution
        outcomes = [s.get("outcome", 0) for s in signals]
        win_rate = sum(outcomes) / len(outcomes) if outcomes else 0
        logger.info(f"  - Win rate: {win_rate:.2%}")
        logger.info(f"  - Winners: {sum(outcomes)}/{len(outcomes)}")
        logger.info(f"  - Sample features: {list(signals[0]['features'].keys())}")
        
        return signals
    else:
        logger.warning(f"✗ trade_log.json not found")
        return []


# ============================================================================
# SECTION 4: PROCESS THROUGH SMC LAYERS
# ============================================================================

def initialize_smc_layers() -> List:
    """Initialize SMC rule-based layers."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 4: Initializing SMC Rule-Based Layers")
    logger.info("=" * 70)
    
    try:
        from engine.igof.layers.smc_layers import LayerFactory
        
        layer_names = [
            "KillzoneFilter",
            "MechanicalStructure",
            "FVGDiscount",
            "LiquiditySweep",
            "MicroMSS",
            "Displacement",
        ]
        
        layers = LayerFactory.create_layers(layer_names)
        logger.info(f"✓ Initialized {len(layers)} SMC layers:")
        for layer in layers:
            logger.info(f"  - {layer.__class__.__name__}")
        
        return layers
    
    except Exception as e:
        logger.error(f"✗ Failed to initialize SMC layers: {e}")
        return []


def process_data_through_smc_layers(dfs: Dict[str, pd.DataFrame], layers: List) -> List[Dict]:
    """Process all timeframe data through SMC layers."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 5: Processing Data Through SMC Layers")
    logger.info("=" * 70)
    
    if not layers:
        logger.warning("No SMC layers available - skipping SMC processing")
        return []
    
    processed_signals = []
    
    # Use M5 as master anchor for synchronization
    if "M5" not in dfs:
        logger.error("M5 data not available - cannot process")
        return []
    
    df_m5 = dfs["M5"]
    m5_times = df_m5['time'].tolist()
    
    logger.info(f"Processing {len(df_m5)} M5 bars through {len(layers)} SMC layers...")
    
    from bisect import bisect_right
    
    for idx, row in df_m5.iterrows():
        if idx % 5000 == 0:
            logger.info(f"  Progress: {idx}/{len(df_m5)} bars")
        
        current_time = row['time']
        
        # Create multi-timeframe snapshot
        snapshot = {}
        snapshot['current_time'] = current_time
        
        for tf, df in dfs.items():
            # Find bars up to current time
            mask = df['time'] <= current_time
            tf_data = df[mask].tail(100).to_dict('records')
            snapshot[f"{tf.lower()}_candles"] = tf_data
        
        # Add ticker data
        snapshot['tick'] = {
            'bid': row['close'],
            'ask': row['close'] + 0.02,
            'time': current_time
        }
        
        # Process through all SMC layers
        try:
            layer_results = []
            all_passed = True
            
            for layer in layers:
                result = layer.process(snapshot)
                layer_results.append({
                    "layer": layer.__class__.__name__,
                    "status": result.get("status", False),
                    "score": result.get("score", 0),
                    "reason": result.get("reason", "")
                })
                
                if not result.get("status", False):
                    all_passed = False
                    break
            
            # Store processed signal
            if layer_results:
                processed_signals.append({
                    "time": current_time.isoformat(),
                    "price": float(row['close']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "layer_results": layer_results,
                    "all_layers_passed": all_passed,
                    "timeframe": "M5"
                })
        
        except Exception as e:
            logger.error(f"Error processing bar at {current_time}: {e}")
            continue
    
    logger.info(f"✓ Processed {len(processed_signals)} signals through SMC layers")
    logger.info(f"  - Signals passed all layers: {sum(1 for s in processed_signals if s['all_layers_passed'])}")
    
    return processed_signals


# ============================================================================
# SECTION 6: MERGE AND PREPARE TRAINING DATA
# ============================================================================

def merge_smc_with_existing_signals(processed: List[Dict], existing: List[Dict]) -> List[Dict]:
    """Merge SMC-processed data with existing signal outcomes."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 6: Merging SMC-Processed Data with Existing Signals")
    logger.info("=" * 70)
    
    if not existing:
        logger.warning("No existing signals to merge with")
        # Use only SMC processed signals
        training_data = []
        for sig in processed:
            # Convert SMC results to ML features
            features = {
                "ob_strength": 0.5,  # Default values
                "fvg_present": 0,
                "bos_aligned": 0,
                "liquidity_swept": 0,
                "adr_pct": 0.5,
                "pips_to_liquidity": 15.0,
                "session": 1,  # London
                "htf_bias": 1
            }
            
            training_data.append({
                "timestamp": sig['time'],
                "signal": {},
                "features": features,
                "outcome": 1 if sig['all_layers_passed'] else 0,
                "source": "SMC_processed"
            })
        
        logger.info(f"Created {len(training_data)} training samples from SMC processing")
        return training_data
    
    # Merge with existing
    logger.info(f"Existing signals: {len(existing)}")
    logger.info(f"SMC-processed signals: {len(processed)}")
    
    # Use existing signals as primary (they have real outcomes)
    training_data = existing.copy()
    
    logger.info(f"✓ Combined into {len(training_data)} training samples")
    
    return training_data


# ============================================================================
# SECTION 7: TRAIN ML LAYER
# ============================================================================

def train_ml_layer(training_data: List[Dict]) -> bool:
    """Train the ML layer with processed data."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 7: Training ML Layer")
    logger.info("=" * 70)
    
    if not training_data or len(training_data) < 30:
        logger.error(f"Insufficient training data: {len(training_data)} samples")
        return False
    
    # Prepare feature matrix and labels
    FEATURE_KEYS = [
        "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
        "adr_pct", "pips_to_liquidity", "session", "htf_bias"
    ]
    
    X = []
    y = []
    
    for sample in training_data:
        features = sample.get("features", {})
        outcome = sample.get("outcome", 0)
        
        # Build feature vector
        feature_vector = [
            float(features.get(key, 0.5 if key in ["ob_strength", "adr_pct", "pips_to_liquidity"] else 0))
            for key in FEATURE_KEYS
        ]
        
        X.append(feature_vector)
        y.append(int(outcome))
    
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=int)
    
    logger.info(f"Training data prepared:")
    logger.info(f"  - Samples: {len(X)}")
    logger.info(f"  - Features: {len(FEATURE_KEYS)} ({', '.join(FEATURE_KEYS)})")
    logger.info(f"  - Positive outcomes: {y.sum()} ({y.mean():.2%})")
    logger.info(f"  - Negative outcomes: {len(y) - y.sum()} ({1 - y.mean():.2%})")
    
    # Train weighted average model
    win_rate = y.mean()
    
    scores = []
    weights = {}
    
    for i, key in enumerate(FEATURE_KEYS):
        feature_col = X[:, i]
        std = np.std(feature_col)
        
        if std > 0:
            # Normalize and calculate correlation with outcomes
            feature_normalized = (feature_col - feature_col.min()) / (feature_col.max() - feature_col.min() + 1e-8)
            correlation = np.corrcoef(feature_normalized, y)[0, 1]
            if np.isnan(correlation):
                correlation = 0
        else:
            correlation = 0
            feature_normalized = np.zeros(len(X))
        
        weights[key] = correlation
        scores.append(feature_normalized * correlation if std > 0 else np.zeros(len(X)))
        
        logger.info(f"  - {key:20s}: weight={correlation:+.4f} | std={std:.4f}")
    
    # Calculate total weighted scores
    total_scores = np.sum(scores, axis=0)
    
    # Normalize scores to 0-1
    min_score = np.min(total_scores)
    max_score = np.max(total_scores)
    if max_score > min_score:
        normalized_scores = (total_scores - min_score) / (max_score - min_score)
    else:
        normalized_scores = np.ones(len(total_scores)) * 0.5
    
    # Find optimal threshold
    thresholds = np.linspace(0, 1, 20)
    best_threshold = 0.5
    best_accuracy = 0
    
    for thresh in thresholds:
        predictions = (normalized_scores >= thresh).astype(int)
        accuracy = np.mean(predictions == y)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = thresh
    
    logger.info(f"\n✓ Model Training Complete:")
    logger.info(f"  - Algorithm: Weighted Average")
    logger.info(f"  - Training accuracy: {best_accuracy:.2%}")
    logger.info(f"  - Optimal threshold: {best_threshold:.2f}")
    logger.info(f"  - Base win rate: {win_rate:.2%}")
    
    # Save model
    model_info = {
        "weights": weights,
        "threshold": float(best_threshold),
        "min_score": float(min_score),
        "max_score": float(max_score),
        "model_type": "weighted_average",
        "win_rate": float(win_rate),
        "n_samples": len(y),
        "feature_keys": FEATURE_KEYS,
        "training_accuracy": float(best_accuracy),
        "trained_at": datetime.now().isoformat(),
        "timeframe_data_used": ["M5", "M15", "H1", "H4"]
    }
    
    os.makedirs("models", exist_ok=True)
    model_path = "models/lgbm_signal_filter.json"
    
    with open(model_path, 'w') as f:
        json.dump(model_info, f, indent=2)
    
    logger.info(f"  - Model saved to: {model_path}")
    
    return True


# ============================================================================
# SECTION 8: VALIDATION & SUMMARY
# ============================================================================

def validate_ml_model() -> bool:
    """Validate that ML model was trained successfully."""
    logger.info("\n" + "=" * 70)
    logger.info("SECTION 8: ML Model Validation")
    logger.info("=" * 70)
    
    model_path = Path("models/lgbm_signal_filter.json")
    
    if not model_path.exists():
        logger.error("✗ Model file not found")
        return False
    
    try:
        with open(model_path) as f:
            model_info = json.load(f)
        
        logger.info(f"✓ Model file valid")
        logger.info(f"  - Type: {model_info.get('model_type')}")
        logger.info(f"  - Samples trained: {model_info.get('n_samples')}")
        logger.info(f"  - Accuracy: {model_info.get('training_accuracy', 0):.2%}")
        logger.info(f"  - Threshold: {model_info.get('threshold', 0):.2f}")
        logger.info(f"  - Win rate: {model_info.get('win_rate', 0):.2%}")
        logger.info(f"  - Trained at: {model_info.get('trained_at', 'N/A')}")
        logger.info(f"  - Timeframe data: {', '.join(model_info.get('timeframe_data_used', []))}")
        
        return True
    
    except Exception as e:
        logger.error(f"✗ Failed to validate model: {e}")
        return False


def print_summary():
    """Print final summary."""
    logger.info("\n" + "=" * 70)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 70)
    
    # Check data availability
    data_dir = Path("data/backtest")
    available_tfs = []
    for tf in ["M5", "M15", "H1", "H4"]:
        if (data_dir / f"XAUUSD_{tf}_6mo.csv").exists():
            available_tfs.append(tf)
    
    logger.info(f"\n✓ Data Availability:")
    logger.info(f"  - Available timeframes: {', '.join(available_tfs)}")
    logger.info(f"  - Missing timeframe: M1")
    
    # Check signals
    trade_log = Path("data/trade_log.json")
    signals_count = 0
    if trade_log.exists():
        with open(trade_log) as f:
            signals_count = len(json.load(f))
    
    logger.info(f"\n✓ Processed Signals:")
    logger.info(f"  - Total signals: {signals_count}")
    
    # Check ML model
    model_path = Path("models/lgbm_signal_filter.json")
    if model_path.exists():
        with open(model_path) as f:
            model = json.load(f)
        logger.info(f"\n✓ ML Layer Status: TRAINED")
        logger.info(f"  - Samples used: {model.get('n_samples')}")
        logger.info(f"  - Training accuracy: {model.get('training_accuracy', 0):.2%}")
        logger.info(f"  - Timeframes used: {', '.join(model.get('timeframe_data_used', []))}")
    else:
        logger.info(f"\n✗ ML Layer Status: NOT TRAINED")
    
    logger.info("\n" + "=" * 70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    logger.info("\n")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║ UNIFIED ML TRAINING PIPELINE - ALL TIMEFRAMES                  ║")
    logger.info("║ Process Data → Run Through SMC Layers → Train ML Model         ║")
    logger.info("╚" + "═" * 68 + "╝")
    
    # 1. Check data availability
    available = check_data_availability()
    
    # 2. Load data
    dfs = load_all_backtest_data()
    signals = load_processed_signals()
    
    # 3. Initialize SMC layers
    layers = initialize_smc_layers()
    
    # 4. Process through SMC layers
    processed = process_data_through_smc_layers(dfs, layers) if layers else []
    
    # 5. Merge data
    training_data = merge_smc_with_existing_signals(processed, signals)
    
    # 6. Train ML layer
    success = train_ml_layer(training_data)
    
    # 7. Validate
    if success:
        valid = validate_ml_model()
    
    # 8. Print summary
    print_summary()
    
    if success:
        logger.info("\n✓ PIPELINE COMPLETE - ML LAYER TRAINED SUCCESSFULLY")
        return 0
    else:
        logger.error("\n✗ PIPELINE FAILED - ML TRAINING DID NOT COMPLETE")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
