"""
ONNX Conversion Script for MT5 ML Trading Bot
=============================================
Builds ONNX model directly for use with MetaTrader 5's OnnxRun function.

Features (in order):
  0: ob_strength       - Order block strength (0.0-1.0)
  1: fvg_present       - Fair value gap present (0 or 1)
  2: bos_aligned       - Break of structure aligned (0 or 1)
  3: liquidity_swept   - Liquidity swept (0 or 1)
  4: adr_pct           - ADR percentage (0.0-1.0)
  5: pips_to_liquidity - Pips to next liquidity (0-100)
  6: session           - Trading session (0-3)
  7: htf_bias          - Higher timeframe bias (-1 to 1)

Author: AI Assistant
"""

import json
import numpy as np
from onnx import helper, TensorProto, numpy_helper
from onnx import save as onnx_save

# =============================================================================
# FEATURE CONFIGURATION (MUST MATCH JSON ORDER)
# =============================================================================

FEATURE_KEYS = [
    "ob_strength",
    "fvg_present",
    "bos_aligned",
    "liquidity_swept",
    "adr_pct",
    "pips_to_liquidity",
    "session",
    "htf_bias",
]

# Feature ranges for normalization (min, max)
FEATURE_RANGES = {
    "ob_strength": (0.0, 1.0),
    "fvg_present": (0.0, 1.0),
    "bos_aligned": (0.0, 1.0),
    "liquidity_swept": (0.0, 1.0),
    "adr_pct": (0.0, 1.0),
    "pips_to_liquidity": (0.0, 100.0),
    "session": (0.0, 3.0),
    "htf_bias": (-1.0, 1.0),
}


# =============================================================================
# BUILD ONNX MODEL DIRECTLY
# =============================================================================

def build_onnx_model(weights, output_path):
    """
    Build ONNX model directly with normalization and weighted sum.
    
    The model:
    1. Takes 8 input features
    2. Normalizes each feature to [0, 1]
    3. Applies weights and sums
    4. Clips output to [0, 1]
    
    IMPORTANT: Input shape is [1, 8] (batch_size=1) for MT5 compatibility.
    """
    n_features = len(FEATURE_KEYS)
    
    # Calculate max_score for normalization
    max_score = sum(abs(v) for v in weights.values()) if weights else 1.0
    
    # =================================================================
    # CREATE INPUT VALUE INFO
    # Shape: [batch_size, n_features] where batch_size is fixed at 1
    # =================================================================
    input_tensor = helper.make_tensor_value_info(
        'input',           # name
        TensorProto.FLOAT, # data_type
        [1, n_features]    # shape [1, 8] - FIXED batch size for MT5!
    )
    
    # =================================================================
    # CREATE OUTPUT VALUE INFO
    # Shape: [batch_size, 1] or just scalar [1]
    # =================================================================
    output_tensor = helper.make_tensor_value_info(
        'output',          # name
        TensorProto.FLOAT, # data_type
        [1]               # shape [1] - probability/confidence
    )
    
    # =================================================================
    # CREATE INITIALIZERS (constant tensors)
    # =================================================================
    
    # Feature mins
    mins = np.array([FEATURE_RANGES[k][0] for k in FEATURE_KEYS], dtype=np.float32)
    mins_tensor = numpy_helper.from_array(mins, name='mins')
    
    # Feature maxs
    maxs = np.array([FEATURE_RANGES[k][1] for k in FEATURE_KEYS], dtype=np.float32)
    maxs_tensor = numpy_helper.from_array(maxs, name='maxs')
    
    # Weights (reshape to [8, 1] for matrix multiplication)
    weights_array = np.array([weights.get(k, 0.0) for k in FEATURE_KEYS], dtype=np.float32)
    weights_tensor = numpy_helper.from_array(weights_array.reshape(-1, 1), name='weights')
    
    # Max score for normalization
    max_score_array = np.array([max_score], dtype=np.float32)
    max_score_tensor = numpy_helper.from_array(max_score_array, name='max_score')
    
    # Clip bounds
    clip_min_tensor = numpy_helper.from_array(np.array([0.0], dtype=np.float32), name='clip_min')
    clip_max_tensor = numpy_helper.from_array(np.array([1.0], dtype=np.float32), name='clip_max')
    
    # =================================================================
    # CREATE NODES (operations)
    # =================================================================
    
    nodes = []
    
    # Node 1: Subtract mins (broadcast)
    node_sub_mins = helper.make_node(
        'Sub',
        inputs=['input', 'mins'],
        outputs=['subtracted'],
        name='sub_mins'
    )
    nodes.append(node_sub_mins)
    
    # Node 2: Subtract mins from maxs to get ranges
    node_sub_range = helper.make_node(
        'Sub',
        inputs=['maxs', 'mins'],
        outputs=['ranges'],
        name='compute_ranges'
    )
    nodes.append(node_sub_range)
    
    # Node 3: Divide to normalize
    node_div = helper.make_node(
        'Div',
        inputs=['subtracted', 'ranges'],
        outputs=['normalized'],
        name='normalize'
    )
    nodes.append(node_div)
    
    # Node 4: Clip normalized values to [0, 1]
    node_clip = helper.make_node(
        'Clip',
        inputs=['normalized', 'clip_min', 'clip_max'],
        outputs=['clipped'],
        name='clip_normalized'
    )
    nodes.append(node_clip)
    
    # Node 5: Matrix multiply with weights (clipped is [1, 8], weights are [8, 1])
    # Result will be [1, 1]
    node_matmul = helper.make_node(
        'MatMul',
        inputs=['clipped', 'weights'],
        outputs=['weighted_sum'],
        name='weighted_sum'
    )
    nodes.append(node_matmul)
    
    # Node 6: Flatten result to 1D
    node_flatten = helper.make_node(
        'Flatten',
        inputs=['weighted_sum'],
        outputs=['flattened'],
        name='flatten',
        axis=0
    )
    nodes.append(node_flatten)
    
    # Node 7: Divide by max_score to normalize confidence
    node_norm = helper.make_node(
        'Div',
        inputs=['flattened', 'max_score'],
        outputs=['normalized_conf'],
        name='normalize_confidence'
    )
    nodes.append(node_norm)
    
    # Node 8: Clip final output to [0, 1]
    node_final_clip = helper.make_node(
        'Clip',
        inputs=['normalized_conf', 'clip_min', 'clip_max'],
        outputs=['output'],
        name='clip_output'
    )
    nodes.append(node_final_clip)
    
    # =================================================================
    # CREATE GRAPH
    # =================================================================
    graph_def = helper.make_graph(
        nodes=nodes,
        name='MLSignalFilter',
        inputs=[input_tensor],
        outputs=[output_tensor],
        initializer=[mins_tensor, maxs_tensor, weights_tensor, 
                     max_score_tensor, clip_min_tensor, clip_max_tensor]
    )
    
    # =================================================================
    # CREATE MODEL
    # =================================================================
    model_def = helper.make_model(
        graph_def,
        producer_name='MLSignalFilterConverter',
        opset_imports=[helper.make_opsetid("", 13)]  # MT5 supports opset 13+
    )
    
    # Set metadata
    model_def.ir_version = 8  # Latest stable IR version
    
    # Save model
    onnx_save(model_def, output_path)
    
    return model_def


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_model(weights, test_cases=None):
    """Test the model with sample inputs using numpy."""
    if test_cases is None:
        test_cases = [
            # Strong bullish signal
            [0.84, 1, 1, 1, 0.3, 10.0, 1.0, 1.0],
            # Weak signal
            [0.5, 0, 1, 0, 0.6, 30.0, 3.0, 0.0],
            # High ADR signal
            [0.7, 1, 1, 0, 0.85, 20.0, 1.0, 1.0],
        ]
    
    print("\n" + "=" * 60)
    print("MODEL TEST RESULTS")
    print("=" * 60)
    
    # Calculate max_score
    max_score = sum(abs(v) for v in weights.values()) if weights else 1.0
    
    for i, features in enumerate(test_cases):
        features_array = np.array(features, dtype=np.float32)
        
        # Normalize
        mins = np.array([FEATURE_RANGES[k][0] for k in FEATURE_KEYS], dtype=np.float32)
        maxs = np.array([FEATURE_RANGES[k][1] for k in FEATURE_KEYS], dtype=np.float32)
        ranges = maxs - mins
        
        normalized = (features_array - mins) / ranges
        normalized = np.clip(normalized, 0, 1)
        
        # Weighted sum
        weights_array = np.array([weights.get(k, 0.0) for k in FEATURE_KEYS], dtype=np.float32)
        score = np.dot(normalized, weights_array)
        
        # Normalize confidence
        confidence = score / max_score
        confidence = np.clip(confidence, 0, 1)
        
        decision = "TRADE ✓" if confidence > 0.65 else "SKIP"
        print(f"\nTest {i + 1}:")
        print(f"  Input:  {features}")
        print(f"  Normalized: {normalized}")
        print(f"  Score:  {score:.4f} / {max_score:.4f}")
        print(f"  Prob:   {confidence:.4f}")
        print(f"  Decision: {decision}")
    
    print("\n" + "=" * 60)


# =============================================================================
# FEATURE MAPPING PRINT
# =============================================================================

def print_feature_mapping():
    """Print feature mapping for MQL5 code."""
    print("\n" + "=" * 60)
    print("FEATURE MAPPING (MUST MATCH IN MQL5 CODE)")
    print("=" * 60)
    print("\nInput array index -> Feature name:")
    for i, key in enumerate(FEATURE_KEYS):
        range_info = FEATURE_RANGES[key]
        print(f"  [{i}] {key:20s} : Range [{range_info[0]:.1f}, {range_info[1]:.1f}]")
    print("\n" + "=" * 60)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Configuration
    MODEL_JSON = "lgbm_signal_filter_20y.json"
    OUTPUT_ONNX = "lgbm_signal_filter_20y.onnx"
    
    print("=" * 60)
    print("ONNX CONVERSION FOR METAQUOTES MT5")
    print("=" * 60)
    
    # Step 1: Load model from JSON
    print(f"\n[1] Loading model from: {MODEL_JSON}")
    with open(MODEL_JSON, 'r') as f:
        model_config = json.load(f)
    
    weights = model_config.get("weights", {})
    threshold = model_config.get("threshold", 0.65)
    
    print(f"    Model type: {model_config.get('model_type', 'unknown')}")
    print(f"    Threshold:  {threshold}")
    print(f"    Win rate:   {model_config.get('win_rate', 0):.2%}")
    print(f"    Weights:")
    for k, v in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
        direction = "+" if v > 0 else "-"
        print(f"      {k:20s}: {v:+.2f} ({direction})")
    
    # Step 2: Print feature mapping
    print_feature_mapping()
    
    # Step 3: Build ONNX model
    print(f"\n[2] Building ONNX model...")
    print(f"    Output: {OUTPUT_ONNX}")
    print(f"    Input shape: [1, 8] (batch_size=1, n_features=8)")
    
    model = build_onnx_model(weights, OUTPUT_ONNX)
    print(f"✓ ONNX model saved to: {OUTPUT_ONNX}")
    
    # Step 4: Test the model
    print("\n[3] Testing model...")
    test_model(weights)
    
    print("\n" + "=" * 60)
    print("✓ CONVERSION COMPLETE!")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. Copy {OUTPUT_ONNX} to your MT5 Data Folder (MQL5/Files/)")
    print(f"  2. Use the MQL5 code below to load and run the model")
    print("=" * 60)
