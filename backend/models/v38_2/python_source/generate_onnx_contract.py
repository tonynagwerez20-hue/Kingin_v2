"""Generate the V38.2 ONNX-to-MT5 Interface Contract.

This produces a complete interface specification for the MQL5 EA team WITHOUT
exporting the production ONNX model and WITHOUT creating MQL5 code. The
contract covers every detail the EA needs to:
  - build the 56-feature vector in the correct order
  - feed it to ONNX Runtime
  - interpret the output probability
  - apply calibration (isotonic post-processing)
  - make a trading decision

It includes a Python reference-inference test and an ONNX Runtime inference
test using the existing (placeholder) ONNX model to validate the I/O shapes and
sample input/output.

NOTE: This contract describes the interface. The production ONNX model is NOT
exported here — it will be exported only after the readiness gate passes and
full-data training is authorized.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v38.config import (V38Config, DATASET_VERSION, FEATURE_CONTRACT_VERSION,
                        MODEL_VERSION, ONNX_VERSION, TRAINING_VERSION)
from v38.features.contract import FEATURE_NAMES, FEATURE_SPECS, N_FEATURES

V38_2_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[2]
ONNX_MODEL_PATH = BACKEND_DIR / "models" / "v38" / "v38_model.onnx"
DATASET_PATH = BACKEND_DIR / "models" / "v38" / "v38_dataset.parquet"
CALIBRATOR_META = BACKEND_DIR / "models" / "v38" / "v38_calibrator_meta.json"


def _encoding_maps() -> Dict:
    """Return the exact integer/float encoding maps for every categorical
    ('_enc') feature. These must be reproduced EXACTLY in MQL5."""
    return {
        "htf_regime_enc": {"bearish": 0.0, "neutral": 1.0, "bullish": 2.0},
        "ltf_regime_enc": {"bearish": 0.0, "neutral": 1.0, "bullish": 2.0},
        "last_event_direction_enc": {"bearish": -1.0, "neutral": 0.0, "bullish": 1.0},
        "nearest_liquidity_side_enc": {"above": -1.0, "none": 0.0, "below": 1.0},
        "ob_direction_enc": {"bearish": -1.0, "neutral": 0.0, "bullish": 1.0},
        "ob_freshness_enc": {"none": 0.0, "fresh": 1.0, "touched": 2.0, "stale": 3.0},
        "fvg_direction_enc": {"bearish": -1.0, "neutral": 0.0, "bullish": 1.0},
        "fvg_freshness_enc": {"none": 0.0, "open": 1.0, "partially_filled": 2.0, "fully_filled": 3.0},
        "pd_label_enc": {"discount": 0.0, "equilibrium": 1.0, "premium": 2.0},
        "volatility_regime_enc": {"low": 0.0, "normal": 1.0, "high": 2.0},
        "session_enc": {"asian": 0.0, "london": 1.0, "overlap": 2.0, "ny": 3.0, "off": 4.0},
        "session_phase_enc": {"early": 0.0, "mid": 1.0, "late": 2.0},
        "expected_gold_dir_enc": {"bearish": -1.0, "neutral": 0.0, "bullish": 1.0},
        "htf_alignment_enc": {"against": -1.0, "neutral": 0.0, "aligned": 1.0},
        "ltf_alignment_enc": {"against": -1.0, "neutral": 0.0, "aligned": 1.0},
    }


def _missing_value_behavior() -> Dict[str, Dict]:
    """Per-feature missing-value behavior (what the EA sends when a structure
    object is absent). This matches the V38.1 feature engine's default values."""
    defaults = {}
    for spec in FEATURE_SPECS:
        name = spec.name
        if name in _encoding_maps():
            # Categorical: send the "absent/none/neutral" sentinel
            enc = _encoding_maps()[name]
            default = enc.get("none", enc.get("neutral", 0.0))
            defaults[name] = {"behavior": "categorical_absent_sentinel",
                              "default_value": float(default)}
        elif name in ("protected_high", "protected_low"):
            defaults[name] = {"behavior": "zero_when_absent", "default_value": 0.0}
        elif name in ("surprise_zscore", "observed_reaction_atr"):
            defaults[name] = {"behavior": "zero_when_no_calendar_or_no_event",
                              "default_value": 0.0}
        elif spec.range == (0, 1) or spec.range == (0, None):
            defaults[name] = {"behavior": "zero_when_absent", "default_value": 0.0}
        else:
            defaults[name] = {"behavior": "zero_when_absent", "default_value": 0.0}
    # Special: forecast-dependent features are PIT-blocked (always 0)
    for name in ("normalized_surprise", "surprise_zscore", "expected_gold_dir_enc",
                 "observed_reaction_atr"):
        if name in defaults:
            defaults[name]["pit_blocked"] = True
            defaults[name]["pit_blocked_reason"] = (
                "Forecast-dependent / reaction-based macro feature. Remains 0.0 "
                "until PIT-verified economic calendar is loaded. MUST be sent as "
                "0.0 by the EA until the calendar integration is authorized.")
    return defaults


def _feature_table() -> List[Dict]:
    """Build the ordered feature table."""
    enc_maps = _encoding_maps()
    miss = _missing_value_behavior()
    table = []
    for spec in FEATURE_SPECS:
        entry = {
            "index": spec.index,
            "name": spec.name,
            "dtype": spec.dtype,
            "family": spec.family,
            "range": [spec.range[0], spec.range[1]] if spec.range[0] is not None else [None, spec.range[1]],
            "is_categorical": spec.name in enc_maps,
        }
        if spec.name in enc_maps:
            entry["encoding_map"] = enc_maps[spec.name]
            entry["encoding_type"] = "ordinal_integer_as_float32"
        entry["missing_value"] = miss.get(spec.name, {})
        entry["normalization"] = "none_raw"  # no scaling applied
        # forecast-dependent flag
        entry["is_forecast_dependent"] = spec.name in (
            "normalized_surprise", "surprise_zscore", "expected_gold_dir_enc",
            "observed_reaction_atr")
        entry["pit_blocked"] = entry["is_forecast_dependent"]
        table.append(entry)
    return table


def _onnx_runtime_test() -> Dict:
    """Run an ONNX Runtime inference test to validate I/O shapes and capture
    sample input/output. Uses the existing placeholder ONNX model."""
    try:
        import onnxruntime as ort
    except ImportError:
        return {"status": "SKIPPED", "reason": "onnxruntime not installed"}

    if not ONNX_MODEL_PATH.exists():
        return {"status": "SKIPPED", "reason": f"ONNX model not found at {ONNX_MODEL_PATH}"}

    sess = ort.InferenceSession(str(ONNX_MODEL_PATH), providers=["CPUExecutionProvider"])
    inputs = sess.get_inputs()
    outputs = sess.get_outputs()

    # Sample input: zeros (all-absent), ones (all-present), and a real row
    n = N_FEATURES
    sample_zero = np.zeros((1, n), dtype=np.float32)
    sample_one = np.ones((1, n), dtype=np.float32)

    # Try to load a real sample from the dataset
    sample_real = None
    real_meta = None
    if DATASET_PATH.exists():
        try:
            df = pd.read_parquet(DATASET_PATH)
            feat_cols = [f"f_{name}" for name in FEATURE_NAMES]
            X = df[feat_cols].to_numpy(dtype=np.float32)
            # Take a positive and negative sample
            y = df["label"].to_numpy()
            pos_idx = np.where(y == 1)[0]
            neg_idx = np.where(y == 0)[0]
            if len(pos_idx) > 0 and len(neg_idx) > 0:
                sample_real = X[pos_idx[0]:pos_idx[0] + 1]
                real_meta = {"source": "dataset", "row": int(pos_idx[0]),
                             "true_label": 1, "direction": str(df.iloc[pos_idx[0]]["direction"])}
            elif len(df) > 0:
                sample_real = X[0:1]
                real_meta = {"source": "dataset", "row": 0, "true_label": int(y[0])}
        except Exception as e:
            real_meta = {"error": str(e)}

    test_input = np.vstack([sample_zero, sample_one] + ([sample_real] if sample_real is not None else []))
    results = sess.run(None, {inputs[0].name: test_input})

    # Parse outputs
    if len(results) == 2:
        labels_out = results[0]
        probs_out = results[1]
    else:
        labels_out = results[0]
        probs_out = results[0]

    # Extract sample outputs
    sample_outputs = {
        "all_zeros_input": {
            "input": sample_zero.tolist(),
            "label": int(labels_out[0]) if labels_out.ndim == 1 else int(labels_out[0][0]),
            "probabilities": probs_out[0].tolist() if probs_out.ndim == 2 else [float(probs_out[0])],
            "p_positive": float(probs_out[0][1]) if probs_out.ndim == 2 else float(probs_out[0]),
        },
        "all_ones_input": {
            "input": sample_one.tolist(),
            "label": int(labels_out[1]) if labels_out.ndim == 1 else int(labels_out[1][0]),
            "probabilities": probs_out[1].tolist() if probs_out.ndim == 2 else [float(probs_out[1])],
            "p_positive": float(probs_out[1][1]) if probs_out.ndim == 2 else float(probs_out[1]),
        },
    }
    if sample_real is not None:
        idx = 2
        sample_outputs["real_sample_input"] = {
            "input": sample_real.tolist(),
            "label": int(labels_out[idx]) if labels_out.ndim == 1 else int(labels_out[idx][0]),
            "probabilities": probs_out[idx].tolist() if probs_out.ndim == 2 else [float(probs_out[idx])],
            "p_positive": float(probs_out[idx][1]) if probs_out.ndim == 2 else float(probs_out[idx]),
            "meta": real_meta,
        }

    return {
        "status": "PASSED",
        "onnx_runtime_version": ort.__version__,
        "model_path": str(ONNX_MODEL_PATH),
        "inputs": [{"name": i.name, "shape": list(i.shape), "type": i.type} for i in inputs],
        "outputs": [{"name": o.name, "shape": list(o.shape), "type": o.type} for o in outputs],
        "sample_outputs": sample_outputs,
        "note": ("This test uses the existing placeholder ONNX model (H1/H4 data, "
                 "weak signal) to validate I/O shapes and contract. The production "
                 "ONNX model is NOT exported until readiness gate passes."),
    }


def _python_reference_inference() -> Dict:
    """Python reference-inference code that the MQL5 implementation must
    reproduce exactly."""
    code = '''import numpy as np
import onnxruntime as ort
import joblib

# 1. Build the 56-feature vector in EXACT order (see feature_order below)
feature_vector = np.array([
    # ... 56 float32 values in contract order ...
], dtype=np.float32).reshape(1, 56)

# 2. Load ONNX model
sess = ort.InferenceSession("v38_model.onnx", providers=["CPUExecutionProvider"])
input_name = sess.get_inputs()[0].name  # "input"

# 3. Run inference (raw probabilities, BEFORE calibration)
results = sess.run(None, {input_name: feature_vector})
labels = results[0]       # shape [1], int64 — predicted class (0 or 1)
raw_probs = results[1]   # shape [1, 2], float32 — [P(class=0), P(class=1)]
raw_p_positive = float(raw_probs[0][1])  # raw P(setup succeeds)

# 4. Apply isotonic calibration (post-ONNX, same as MQL5)
cal_obj = joblib.load("v38_calibrator.joblib")
calibrator = cal_obj["calibrator"]
method = cal_obj["method"]
if method == "isotonic":
    calibrated_p = float(calibrator.predict(np.array([raw_p_positive])))
elif method == "sigmoid":
    eps = 1e-6
    p_clipped = np.clip(raw_p_positive, eps, 1 - eps)
    logit = np.log(p_clipped / (1 - p_clipped))
    calibrated_p = float(calibrator.predict_proba(np.array([[logit]]))[0][1])
else:
    calibrated_p = raw_p_positive

# 5. Trading decision
THRESHOLD = 0.5
if calibrated_p >= THRESHOLD:
    decision = "ENTER"   # take the setup
else:
    decision = "SKIP"    # do not enter
'''
    return {
        "language": "python",
        "code": code,
        "note": ("This is the reference implementation. The MQL5 EA must "
                 "reproduce this exact sequence: build features -> ONNX infer -> "
                 "calibrate -> threshold."),
    }


def build_contract():
    cfg = V38Config()
    enc_maps = _encoding_maps()

    # Load calibrator metadata
    cal_meta = {}
    if CALIBRATOR_META.exists():
        cal_meta = json.loads(CALIBRATOR_META.read_text())

    # Dataset range for cutoff
    data_cutoff = "unknown"
    data_range = {}
    if DATASET_PATH.exists():
        try:
            df = pd.read_parquet(DATASET_PATH)
            data_range = {
                "first_setup_ts": str(df["timestamp"].min()),
                "last_setup_ts": str(df["timestamp"].max()),
                "n_setups": int(len(df)),
                "holdout_split_80pct_ts": str(df["timestamp"].iloc[int(len(df) * 0.8)]),
            }
            data_cutoff = str(df["timestamp"].max())
        except Exception:
            pass

    contract = {
        "contract_name": "V38.2 ONNX-to-MT5 Interface Contract",
        "contract_version": "v38.2_interface_1",
        "created_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "INTERFACE_SPECIFICATION_ONLY",
        "warning": (
            "This contract defines the interface ONLY. The production ONNX model "
            "is NOT exported. MQL5 code is NOT generated. Both will be produced "
            "separately after the V38.2 readiness gate passes and full-data "
            "training is authorized."),
        # --- Model metadata ---
        "model_metadata": {
            "model_version": MODEL_VERSION,
            "onnx_version": ONNX_VERSION,
            "training_version": TRAINING_VERSION,
            "dataset_version": DATASET_VERSION,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "symbol": "XAUUSD",
            "task": "binary_classification",
            "model_type": "LightGBM gradient-boosted decision trees",
            "model_framework": "LightGBM -> ONNX (via onnxmltools, opset 15)",
            "calibration": {
                "method": cal_meta.get("method", "isotonic"),
                "applied_in": "post-ONNX (Python inference wrapper + MQL5 EA)",
                "calibrator_file": "v38_calibrator.joblib",
                "calibrator_meta_file": "v38_calibrator_meta.json",
                "note": "Calibration is applied AFTER ONNX inference, not baked into the graph",
            },
        },
        # --- Training-data cutoff ---
        "training_data_cutoff": {
            "last_setup_timestamp": data_cutoff,
            "data_range": data_range,
            "holdout_start_timestamp": data_range.get("holdout_split_80pct_ts"),
            "note": ("The model was trained on data up to the holdout split "
                     "(80% chronological). The last 20% is untouched holdout. "
                     "The production model (when exported) will be trained on "
                     "ALL available data up to the training cutoff."),
        },
        # --- Input tensor ---
        "input_tensor": {
            "name": "input",
            "dtype": "float32",
            "shape": [None, 56],
            "meaning": "[batch_size, n_features]. batch_size=1 for single-setup inference.",
            "layout": "row-major (C order)",
            "n_features": N_FEATURES,
        },
        # --- Output tensor ---
        "output_tensor": {
            "outputs": [
                {
                    "name": "label",
                    "dtype": "int64",
                    "shape": [1],
                    "meaning": "predicted class label (0 = negative/skip, 1 = positive/enter)",
                    "note": "This is the argmax of probabilities. For trading decisions, use the calibrated probability and threshold instead.",
                },
                {
                    "name": "probabilities",
                    "dtype": "float32",
                    "shape": [None, 2],
                    "meaning": "[P(class=0), P(class=1)] per sample. Column 1 = P(setup succeeds / TP hit).",
                    "note": "These are RAW (uncalibrated) probabilities. Apply isotonic calibration post-ONNX.",
                },
            ],
            "primary_output": "probabilities[0][1]",
            "primary_output_meaning": "Raw P(setup succeeds — TP barrier hit before SL barrier)",
        },
        # --- Output probability meaning ---
        "output_probability_meaning": {
            "p_positive_raw": "Raw (uncalibrated) probability from the LightGBM ensemble that the setup will succeed (TP=+2R hit before SL=-1R within the barrier horizon).",
            "p_positive_calibrated": "Isotonic-calibrated probability. This is the value used for the trading decision.",
            "label_definition": "Label=1 means: within label_max_bars bars, price reached +2R (TP) before -1R (SL). Label=0 means: price reached -1R (SL) before +2R (TP), or neither barrier was hit within the horizon (censored, excluded from training).",
            "label_max_bars_default": cfg.label_max_bars,
            "label_tp_r": cfg.label_tp_r,
            "label_sl_r": cfg.label_sl_r,
            "tie_break_policy": cfg.label_simultaneous_policy,
        },
        # --- Classification threshold ---
        "classification_threshold": {
            "value": 0.5,
            "applied_to": "calibrated probability (post-isotonic)",
            "decision_rule": "IF calibrated_p_positive >= 0.5 THEN ENTER ELSE SKIP",
            "note": "0.5 is the default threshold. It may be tuned later, but any change MUST be validated on out-of-sample data. Do NOT tune on holdout.",
            "alternative_thresholds": {
                "0.60": "More conservative — fewer trades, higher precision (if signal exists)",
                "0.70": "Very conservative — minimal false positives",
            },
        },
        # --- Feature order (exact) ---
        "feature_order": FEATURE_NAMES,
        "feature_count": N_FEATURES,
        # --- Feature table (detailed per-feature spec) ---
        "feature_table": _feature_table(),
        # --- Datatype ---
        "datatype": {
            "all_features": "float32",
            "input_tensor": "float32",
            "note": "ALL 56 features are float32. Categorical features are ordinal-encoded integers stored as float32. No string inputs.",
        },
        # --- Normalization / scaling ---
        "normalization_scaling": {
            "method": "none",
            "details": "Features are raw, unnormalized values. No StandardScaler, MinMaxScaler, or any fitted normalization is applied. The LightGBM model handles feature scaling internally via tree splits. The EA must send the EXACT raw values as specified in feature_table.",
            "atr_normalized_features": "Many features are already ATR-normalized (e.g., *_atr suffix), meaning they are divided by the ATR at the setup bar. These are dimensionless ratios.",
            "price_features": "protected_high and protected_low are absolute price levels (float32, no scaling).",
        },
        # --- Missing-value behavior ---
        "missing_value_behavior": _missing_value_behavior(),
        "global_missing_value_rule": {
            "default": 0.0,
            "rationale": "The V38.1 feature engine returns 0.0 for all absent structure objects (no OB, no FVG, no liquidity pool, etc.). The EA MUST replicate this exactly.",
            "categorical_absent": "For categorical (_enc) features, send the 'absent/none/neutral' sentinel from the encoding map (usually 0.0, but check encoding_map per feature).",
            "pit_blocked_features": "normalized_surprise, surprise_zscore, expected_gold_dir_enc, observed_reaction_atr MUST be 0.0 (PIT-blocked until calendar authorized).",
        },
        # --- Categorical encoding ---
        "categorical_encoding": {
            "method": "ordinal_integer_encoding_as_float32",
            "features": list(enc_maps.keys()),
            "encoding_maps": enc_maps,
            "note": "Each categorical feature maps a string category to a float32 integer. The MQL5 EA must reproduce these EXACT mappings. No one-hot encoding, no hashing.",
            "critical": "The encoding values are small integers (0, 1, 2, 3, 4 or -1, 0, 1). They are NOT arbitrary floats.",
        },
        # --- PIT-blocked features ---
        "pit_blocked_features": {
            "features": ["normalized_surprise", "surprise_zscore",
                         "expected_gold_dir_enc", "observed_reaction_atr"],
            "status": "BLOCKED_PIT_FORECAST",
            "required_value": 0.0,
            "reason": "These features depend on economic calendar forecasts or post-event reactions. Forecasts are NOT PIT-verified. They MUST be sent as 0.0 until the economic calendar is loaded and PIT-verified.",
            "never_modify": True,
        },
        # --- Python reference inference ---
        "python_reference_inference": _python_reference_inference(),
        # --- ONNX Runtime inference test ---
        "onnx_runtime_test": _onnx_runtime_test(),
        # --- Sample input/output ---
        "expected_sample_input_output": "see onnx_runtime_test.sample_outputs",
        # --- Opset ---
        "onnx_opset": 15,
        "onnx_ir_version": 8,
        # --- MQL5 notes (no code) ---
        "mql5_notes": {
            "status": "NOT_GENERATED",
            "note": "MQL5 EA code is NOT part of this contract. It will be implemented separately by the MQL5 team using this contract as the specification.",
            "key_implementation_points": [
                "Load v38_model.onnx via OnnxRun() in MQL5",
                "Build the 56-feature float32 array in EXACT feature_order",
                "Call ONNX inference to get raw probabilities [P(0), P(1)]",
                "Apply isotonic calibration to raw_p_positive (load calibrator coefficients)",
                "Compare calibrated probability to 0.5 threshold",
                "If >= threshold: execute trade with TP=+2R, SL=-1R",
                "If < threshold: skip the setup",
                "PIT-blocked features (indices 46,47,48,49) MUST be 0.0",
            ],
        },
        # --- Non-modifications ---
        "non_modifications": [
            "Forecast-dependent macro features NOT changed (remain PIT-blocked at 0.0)",
            "Feature contract NOT modified (V38.1, 56 features, 9 families)",
            "readiness_gate.py NOT modified",
            "economic_calendar.csv NOT created",
            "PIT rules NOT modified",
            "holiday classification NOT modified",
            "No production ONNX model exported (interface contract only)",
            "No MQL5 code generated",
            "No MT5 connection",
        ],
    }
    return contract


def main():
    contract = build_contract()

    # Save JSON
    json_path = V38_2_DIR / "V38_2_ONNX_MT5_INTERFACE_CONTRACT.json"
    json_path.write_text(json.dumps(contract, indent=2, default=str))
    print(f"JSON contract saved to {json_path}")

    # Save Markdown
    md_path = V38_2_DIR / "V38_2_ONNX_MT5_INTERFACE_CONTRACT.md"
    md = _build_markdown(contract)
    md_path.write_text(md)
    print(f"Markdown contract saved to {md_path}")


def _build_markdown(c: Dict) -> str:
    lines = []
    w = lines.append
    w(f"# {c['contract_name']}")
    w("")
    w(f"**Contract version:** {c['contract_version']}  ")
    w(f"**Created (UTC):** {c['created_utc']}  ")
    w(f"**Status:** {c['status']}")
    w("")
    w("> **WARNING:** " + c["warning"])
    w("")

    w("## 1. Model Metadata")
    w("")
    mm = c["model_metadata"]
    w(f"| Field | Value |")
    w(f"|-------|-------|")
    w(f"| Model version | `{mm['model_version']}` |")
    w(f"| ONNX version | `{mm['onnx_version']}` |")
    w(f"| Training version | `{mm['training_version']}` |")
    w(f"| Dataset version | `{mm['dataset_version']}` |")
    w(f"| Feature contract | `{mm['feature_contract_version']}` |")
    w(f"| Symbol | `{mm['symbol']}` |")
    w(f"| Task | `{mm['task']}` |")
    w(f"| Model type | {mm['model_type']} |")
    w(f"| Framework | {mm['model_framework']} |")
    w("")
    cal = mm["calibration"]
    w(f"**Calibration:** {cal['method']} (applied {cal['applied_in']})  ")
    w(f"> {cal['note']}")
    w("")

    w("## 2. Training-Data Timestamp Cutoff")
    w("")
    tdc = c["training_data_cutoff"]
    w(f"- **Last setup timestamp:** `{tdc['last_setup_timestamp']}`")
    dr = tdc.get("data_range", {})
    if dr:
        w(f"- **First setup timestamp:** `{dr.get('first_setup_ts')}`")
        w(f"- **Last setup timestamp:** `{dr.get('last_setup_ts')}`")
        w(f"- **Number of setups:** {dr.get('n_setups')}")
        w(f"- **Holdout split (80%) timestamp:** `{dr.get('holdout_split_80pct_ts')}`")
    w(f"- {tdc['note']}")
    w("")

    w("## 3. Input Tensor")
    w("")
    it = c["input_tensor"]
    w(f"| Property | Value |")
    w(f"|----------|-------|")
    w(f"| Name | `{it['name']}` |")
    w(f"| Dtype | `{it['dtype']}` |")
    w(f"| Shape | `{it['shape']}` |")
    w(f"| Layout | {it['layout']} |")
    w(f"| N features | {it['n_features']} |")
    w(f"| Meaning | {it['meaning']} |")
    w("")

    w("## 4. Output Tensor")
    w("")
    w("The ONNX model produces two outputs:")
    w("")
    for o in c["output_tensor"]["outputs"]:
        w(f"### `{o['name']}`")
        w(f"- **Dtype:** `{o['dtype']}`")
        w(f"- **Shape:** `{o['shape']}`")
        w(f"- **Meaning:** {o['meaning']}")
        if "note" in o:
            w(f"- **Note:** {o['note']}")
        w("")
    w(f"**Primary output:** `{c['output_tensor']['primary_output']}`  ")
    w(f"**Meaning:** {c['output_tensor']['primary_output_meaning']}")
    w("")

    w("## 5. Output Probability Meaning")
    w("")
    opm = c["output_probability_meaning"]
    w(f"- **Raw P(positive):** {opm['p_positive_raw']}")
    w(f"- **Calibrated P(positive):** {opm['p_positive_calibrated']}")
    w(f"- **Label=1 definition:** {opm['label_definition']}")
    w(f"- **Label max bars (default):** {opm['label_max_bars_default']}")
    w(f"- **TP:** +{opm['label_tp_r']}R | **SL:** -{opm['label_sl_r']}R | **Tie-break:** {opm['tie_break_policy']}")
    w("")

    w("## 6. Classification Threshold")
    w("")
    ct = c["classification_threshold"]
    w(f"- **Threshold:** {ct['value']}")
    w(f"- **Applied to:** {ct['applied_to']}")
    w(f"- **Decision rule:** `{ct['decision_rule']}`")
    w(f"- {ct['note']}")
    w("")

    w("## 7. Exact Feature Names and Order")
    w("")
    w(f"The {c['feature_count']} features MUST be provided in this EXACT order:")
    w("")
    w("| Index | Name |")
    w("|-------|------|")
    for i, name in enumerate(c["feature_order"]):
        w(f"| {i} | `{name}` |")
    w("")

    w("## 8. Datatype")
    w("")
    dt = c["datatype"]
    w(f"- **All features:** `{dt['all_features']}`")
    w(f"- **Input tensor:** `{dt['input_tensor']}`")
    w(f"- {dt['note']}")
    w("")

    w("## 9. Normalization / Scaling")
    w("")
    ns = c["normalization_scaling"]
    w(f"- **Method:** {ns['method']}")
    w(f"- {ns['details']}")
    w(f"- **ATR-normalized features:** {ns['atr_normalized_features']}")
    w(f"- **Price features:** {ns['price_features']}")
    w("")

    w("## 10. Missing-Value Behavior")
    w("")
    w(f"**Global default:** {c['global_missing_value_rule']['default']}  ")
    w(f"**Rationale:** {c['global_missing_value_rule']['rationale']}")
    w("")
    w(f"**Categorical absent:** {c['global_missing_value_rule']['categorical_absent']}")
    w("")
    w(f"**PIT-blocked:** {c['global_missing_value_rule']['pit_blocked_features']}")
    w("")
    w("Per-feature missing-value behavior:")
    w("")
    w("| Index | Name | Default | Behavior |")
    w("|-------|------|---------|----------|")
    for ft in c["feature_table"]:
        mv = ft.get("missing_value", {})
        w(f"| {ft['index']} | `{ft['name']}` | {mv.get('default_value', 0.0)} | {mv.get('behavior', '')} |")
    w("")

    w("## 11. Categorical Encoding")
    w("")
    ce = c["categorical_encoding"]
    w(f"- **Method:** {ce['method']}")
    w(f"- **Note:** {ce['note']}")
    w(f"- **Critical:** {ce['critical']}")
    w("")
    w("**Encoding maps (MUST be reproduced exactly in MQL5):**")
    w("")
    for name, emap in ce["encoding_maps"].items():
        w(f"### `{name}`")
        w("| Category | Encoded value |")
        w("|----------|-------------|")
        for cat, val in emap.items():
            w(f"| {cat} | {val} |")
        w("")

    w("## 12. PIT-Blocked Features (Forecast-Dependent)")
    w("")
    pb = c["pit_blocked_features"]
    w(f"- **Features:** {', '.join(f'`{f}`' for f in pb['features'])}")
    w(f"- **Status:** {pb['status']}")
    w(f"- **Required value:** {pb['required_value']}")
    w(f"- **Reason:** {pb['reason']}")
    w(f"- **Never modify:** {pb['never_modify']}")
    w("")

    w("## 13. Full Feature Table")
    w("")
    w("| Index | Name | Family | Dtype | Range | Categorical | PIT-blocked |")
    w("|-------|------|--------|-------|-------|-------------|-------------|")
    for ft in c["feature_table"]:
        r = ft["range"]
        rstr = f"[{r[0]}, {r[1]}]"
        w(f"| {ft['index']} | `{ft['name']}` | {ft['family']} | `{ft['dtype']}` | {rstr} | {ft['is_categorical']} | {ft.get('pit_blocked', False)} |")
    w("")

    w("## 14. Python Reference Inference")
    w("")
    w("```python")
    w(c["python_reference_inference"]["code"])
    w("```")
    w("")
    w(f"**Note:** {c['python_reference_inference']['note']}")
    w("")

    w("## 15. ONNX Runtime Inference Test")
    w("")
    ort_test = c["onnx_runtime_test"]
    w(f"**Status:** {ort_test['status']}")
    if "onnx_runtime_version" in ort_test:
        w(f"**ONNX Runtime version:** {ort_test['onnx_runtime_version']}")
    w(f"**Model path:** `{ort_test.get('model_path', 'N/A')}`")
    w("")
    if "note" in ort_test:
        w(f"> {ort_test['note']}")
        w("")
    if "inputs" in ort_test:
        w("**Inputs:**")
        w("")
        for i in ort_test["inputs"]:
            w(f"- `{i['name']}`: shape={i['shape']}, type={i['type']}")
        w("")
    if "outputs" in ort_test:
        w("**Outputs:**")
        w("")
        for o in ort_test["outputs"]:
            w(f"- `{o['name']}`: shape={o['shape']}, type={o['type']}")
        w("")

    w("## 16. Expected Sample Input/Output")
    w("")
    if "sample_outputs" in ort_test:
        for name, so in ort_test["sample_outputs"].items():
            w(f"### {name}")
            w("")
            meta = so.get("meta", {})
            if meta:
                w(f"**Meta:** {meta}")
                w("")
            w(f"**Input (56 float32 values):**")
            w("```")
            inp = so["input"][0] if isinstance(so["input"][0], list) else so["input"]
            w(f"[{', '.join(f'{v:.6f}' for v in inp)}]")
            w("```")
            w(f"**Label (int64):** {so['label']}")
            w(f"**Probabilities [P(0), P(1)]:** {so['probabilities']}")
            w(f"**P(positive) = P(1):** {so['p_positive']:.6f}")
            w("")

    w("## 17. MQL5 Notes (No Code)")
    w("")
    mn = c["mql5_notes"]
    w(f"**Status:** {mn['status']}")
    w(f"**Note:** {mn['note']}")
    w("")
    w("**Key implementation points:**")
    for p in mn["key_implementation_points"]:
        w(f"- {p}")
    w("")

    w("## 18. Non-Modifications")
    w("")
    for nm in c["non_modifications"]:
        w(f"- {nm}")
    w("")

    w("---")
    w(f"*This contract was generated by the V38.2 pre-modeling validation phase. It defines the interface only — no production model is exported and no MQL5 code is generated.*")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
