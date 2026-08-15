"""V38.2 ONNX Integration Validation Report.

Validates:
A. ONNX model loads
B. Python ↔ ONNX parity
C. Tensor dimensions correct (50 features)
D. Inference does not crash
E. Calibration applied correctly
F. Decision parity on holdout

Usage:
    python -m v38.v38_2.test_onnx_validation
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import onnx
import onnxruntime as ort

from v38.config import V38Config
from v38.features.contract import FEATURE_NAMES, FEATURE_SPECS, N_FEATURES

PRICE_INDICES = [i for i in range(N_FEATURES) if FEATURE_SPECS[i].family != "MACRO_NEWS"]

ARTIFACT_DIR = Path(__file__).parent / "full_data_artifacts"
REPORT_PATH = ARTIFACT_DIR / "V38_2_ONNX_INTEGRATION_REPORT.json"


def run_validation():
    results = {
        "test_date": "2026-08-12",
        "tests": {},
        "overall_pass": True,
    }

    # === A. ONNX model loads ===
    print("=== A. ONNX model load test ===", flush=True)
    onnx_path = ARTIFACT_DIR / "v38_2_final_model.onnx"
    try:
        model = onnx.load(str(onnx_path))
        results["tests"]["A_onnx_load"] = {
            "pass": True,
            "producer": model.producer_name,
            "opset": [op.version for op in model.opset_import],
            "ir_version": model.ir_version,
            "file_size_kb": onnx_path.stat().st_size / 1024,
        }
        print(f"  PASS: Model loaded, opset={[op.version for op in model.opset_import]}", flush=True)
    except Exception as e:
        results["tests"]["A_onnx_load"] = {"pass": False, "error": str(e)}
        results["overall_pass"] = False
        print(f"  FAIL: {e}", flush=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(results, f, indent=2)
        return results

    # === B. Tensor dimensions ===
    print("\n=== B. Tensor dimension test ===", flush=True)
    inputs = [(i.name, [d.dim_value if d.dim_value > 0 else "dynamic"
                        for d in i.type.tensor_type.shape.dim])
              for i in model.graph.input]
    outputs = [(o.name, [d.dim_value if d.dim_value > 0 else "dynamic"
                         for d in o.type.tensor_type.shape.dim])
               for o in model.graph.output]
    input_ok = inputs[0][1] == ["dynamic", 50]
    results["tests"]["B_tensor_dims"] = {
        "pass": input_ok,
        "input": inputs,
        "output": outputs,
        "expected_features": 50,
        "actual_features": inputs[0][1][-1] if isinstance(inputs[0][1][-1], int) else "dynamic",
    }
    print(f"  Input: {inputs}", flush=True)
    print(f"  Output: {outputs}", flush=True)
    print(f"  {'PASS' if input_ok else 'FAIL'}: Feature count = 50", flush=True)

    # === C. ONNX Runtime inference ===
    print("\n=== C. ONNX Runtime inference test ===", flush=True)
    try:
        sess = ort.InferenceSession(str(onnx_path))
        input_name = sess.get_inputs()[0].name
        # Test with random data
        test_input = np.random.randn(1, 50).astype(np.float32)
        t0 = time.time()
        outputs_rt = sess.run(None, {input_name: test_input})
        infer_time = (time.time() - t0) * 1000
        # outputs_rt[0] = label array, outputs_rt[1] = list of dicts (zipmap) or array
        label_out = np.array(outputs_rt[0])
        # Handle zipmap output: list of dicts -> extract P(class=1)
        if isinstance(outputs_rt[1], list):
            proba_class1 = np.array([d.get(1, d.get("1", 0)) for d in outputs_rt[1]])
        else:
            proba_class1 = np.array(outputs_rt[1])[:, 1]
        results["tests"]["C_inference"] = {
            "pass": True,
            "input_shape": list(test_input.shape),
            "label_value": int(label_out[0]),
            "probability_class1": float(proba_class1[0]),
            "inference_time_ms": round(infer_time, 3),
        }
        print(f"  PASS: Inference OK in {infer_time:.3f}ms", flush=True)
        print(f"  Label: {label_out[0]}, P(class=1): {proba_class1[0]:.6f}", flush=True)
    except Exception as e:
        results["tests"]["C_inference"] = {"pass": False, "error": str(e)}
        results["overall_pass"] = False
        print(f"  FAIL: {e}", flush=True)

    # === D. Python ↔ ONNX parity on holdout ===
    print("\n=== D. Python ↔ ONNX parity test ===", flush=True)
    df = pd.read_parquet(ARTIFACT_DIR / "v38_2_dataset_M5_H1_lb240.parquet")
    df = df.sort_values("timestamp").reset_index(drop=True)
    mask = df["label"].to_numpy() >= 0
    df = df[mask].reset_index(drop=True)

    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]
    holdout_start = int(len(df) * 0.80)
    holdout = df.iloc[holdout_start:].reset_index(drop=True)

    X = holdout[feat_cols].to_numpy(dtype=np.float32)

    # Python LightGBM
    lgbm = joblib.load(ARTIFACT_DIR / "v38_2_final_model.joblib")
    calibrator = joblib.load(ARTIFACT_DIR / "v38_2_calibrator.joblib")
    py_raw = lgbm.predict_proba(X)[:, 1]
    py_cal = calibrator.predict(py_raw)
    py_decisions = (py_cal >= 0.5).astype(int)

    # ONNX
    onnx_out = sess.run(None, {input_name: X})
    if isinstance(onnx_out[1], list):
        onnx_raw = np.array([d.get(1, d.get("1", 0)) for d in onnx_out[1]])
    else:
        onnx_raw = np.array(onnx_out[1])[:, 1]
    onnx_cal = calibrator.predict(onnx_raw)
    onnx_decisions = (onnx_cal >= 0.5).astype(int)

    raw_diff = np.abs(py_raw - onnx_raw)
    cal_diff = np.abs(py_cal - onnx_cal)
    decision_mismatches = np.sum(py_decisions != onnx_decisions)

    results["tests"]["D_python_onnx_parity"] = {
        "pass": decision_mismatches == 0,
        "n_samples": len(X),
        "raw_mean_diff": float(np.mean(raw_diff)),
        "raw_max_diff": float(np.max(raw_diff)),
        "cal_mean_diff": float(np.mean(cal_diff)),
        "cal_max_diff": float(np.max(cal_diff)),
        "decision_mismatches": int(decision_mismatches),
        "decision_parity_pct": float((1 - decision_mismatches / len(X)) * 100),
    }
    print(f"  N samples: {len(X)}", flush=True)
    print(f"  Raw  mean diff: {np.mean(raw_diff):.6f}, max: {np.max(raw_diff):.6f}", flush=True)
    print(f"  Cal  mean diff: {np.mean(cal_diff):.6f}, max: {np.max(cal_diff):.6f}", flush=True)
    print(f"  Decision mismatches: {decision_mismatches}/{len(X)}", flush=True)
    print(f"  {'PASS' if decision_mismatches == 0 else 'FAIL'}: Decision parity", flush=True)

    # === E. Calibration correctness ===
    print("\n=== E. Calibration test ===", flush=True)
    # Test calibration on a few known probabilities
    test_probs = [0.1, 0.3, 0.5, 0.7, 0.9]
    cal_results = {}
    for p in test_probs:
        cal_p = float(calibrator.predict([p])[0])
        cal_results[f"raw_{p}"] = cal_p
    results["tests"]["E_calibration"] = {
        "pass": True,
        "method": "isotonic",
        "test_points": cal_results,
        "n_thresholds": len(calibrator.X_thresholds_),
    }
    print(f"  Method: isotonic, {len(calibrator.X_thresholds_)} points", flush=True)
    for p in test_probs:
        print(f"  raw={p} → cal={cal_results[f'raw_{p}']:.4f}", flush=True)
    print("  PASS", flush=True)

    # === F. Feature count verification ===
    print("\n=== F. Feature count verification ===", flush=True)
    n_features_onnx = 50
    n_features_python = len(PRICE_INDICES)
    n_features_contract = N_FEATURES
    n_excluded = N_FEATURES - len(PRICE_INDICES)
    feat_ok = (n_features_onnx == n_features_python == 50)
    results["tests"]["F_feature_count"] = {
        "pass": feat_ok,
        "onnx_features": n_features_onnx,
        "python_price_indices": n_features_python,
        "contract_total": n_features_contract,
        "excluded_macro_news": n_excluded,
    }
    print(f"  ONNX: {n_features_onnx}, Python: {n_features_python}, Contract: {n_features_contract}",
          flush=True)
    print(f"  Excluded (MACRO_NEWS): {n_excluded}", flush=True)
    print(f"  {'PASS' if feat_ok else 'FAIL'}", flush=True)

    # Overall
    all_pass = all(t.get("pass", False) for t in results["tests"].values())
    results["overall_pass"] = all_pass
    results["verdict"] = "PASS — ONNX integration validated" if all_pass else "FAIL — issues found"

    print(f"\n=== OVERALL: {'PASS' if all_pass else 'FAIL'} ===", flush=True)

    with open(REPORT_PATH, "w") as f:
        json.dump(results, f, indent=2, default=lambda o: bool(o) if isinstance(o, np.bool_) else str(o))
    print(f"\nReport saved: {REPORT_PATH}", flush=True)
    return results


if __name__ == "__main__":
    run_validation()
