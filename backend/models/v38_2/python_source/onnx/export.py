"""ONNX conversion — REAL LightGBM ensemble -> ONNX.

The trained LightGBM model is exported directly via skl2onnx as a real tree
ensemble (TreeEnsembleClassifier). The calibrator is exported separately as
coefficients/thresholds and applied as a post-processing step in both the
Python inference wrapper and the MQL5 EA. This keeps the ONNX graph a genuine
ensemble while making calibration reproducible cross-platform.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import joblib
import onnx
import onnxruntime as ort
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

from ..config import V38Config, ARTIFACT_DIR, ONNX_VERSION
from ..features.contract import FEATURE_NAMES, N_FEATURES


def convert_to_onnx(model, calibrator=None, calibrator_method="none",
                    out_dir: Path = None, cfg: V38Config = None) -> dict:
    out_dir = Path(out_dir or ARTIFACT_DIR)
    cfg = cfg or V38Config()
    initial_types = [("input", FloatTensorType([None, N_FEATURES]))]
    onx = onnxmltools.convert_lightgbm(model, initial_types=initial_types,
                                       target_opset=15, zipmap=False)
    onx.ir_version = 8
    onx_path = out_dir / "v38_model.onnx"
    onnx.save(onx, str(onx_path))

    # export calibrator separately for cross-platform post-processing
    cal_meta = {"method": calibrator_method}
    if calibrator is not None and calibrator_method == "isotonic":
        cal_meta["x_thresholds"] = [float(v) for v in np.asarray(calibrator.X_thresholds_)]
        cal_meta["y_thresholds"] = [float(v) for v in np.asarray(calibrator.y_thresholds_)]
    elif calibrator is not None and calibrator_method == "sigmoid":
        cal_meta["coef"] = [float(c) for c in calibrator.coef_.ravel()]
        cal_meta["intercept"] = [float(i) for i in calibrator.intercept_.ravel()]
    joblib.dump({"method": calibrator_method, "calibrator": calibrator},
                out_dir / "v38_calibrator.joblib")
    with open(out_dir / "v38_calibrator_meta.json", "w") as f:
        json.dump(cal_meta, f, indent=2, default=str)

    meta = {
        "onnx_version": ONNX_VERSION,
        "n_features": N_FEATURES,
        "feature_names": FEATURE_NAMES,
        "input_name": "input",
        "output_name": "output_probability",
        "calibrator_method": calibrator_method,
        "calibrator_applied_in": "MQL5_and_Python_inference_wrapper (post-ONNX)",
        "opset": 15,
        "path": str(onx_path),
    }
    with open(out_dir / "v38_onnx_manifest.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)
    return meta


def apply_calibrator(proba: np.ndarray, cal_path: str) -> np.ndarray:
    """Apply the exported calibrator to raw probabilities (Python inference)."""
    obj = joblib.load(cal_path)
    cal = obj["calibrator"]
    method = obj["method"]
    if cal is None or method == "none":
        return proba
    if method == "isotonic":
        return cal.predict(proba)
    eps = 1e-6
    logit = np.log(np.clip(proba, eps, 1 - eps) / (1 - np.clip(proba, eps, 1 - eps)))
    return cal.predict_proba(logit.reshape(-1, 1))[:, 1]


def equivalence_test(model, onnx_path: str, cfg: V38Config = None,
                     n_samples: int = None, cal_path: str = None) -> dict:
    cfg = cfg or V38Config()
    n_samples = n_samples or cfg.equivalence_n_samples
    rng = np.random.default_rng(42)
    X_rand = rng.uniform(-2, 5, size=(n_samples, N_FEATURES)).astype(np.float32)
    edges = [
        np.zeros((1, N_FEATURES), dtype=np.float32),
        np.ones((1, N_FEATURES), dtype=np.float32),
        np.full((1, N_FEATURES), -1e6, dtype=np.float32),
        np.full((1, N_FEATURES), 1e6, dtype=np.float32),
        np.full((1, N_FEATURES), 1e-9, dtype=np.float32),
        rng.uniform(0, 1, size=(50, N_FEATURES)).astype(np.float32),
    ]
    X_edge = np.vstack(edges).astype(np.float32)
    X_all = np.vstack([X_rand, X_edge]).astype(np.float32)

    # Python path (base model raw proba, then calibrator if present)
    py_proba = model.predict_proba(X_all)[:, 1]
    if cal_path:
        py_proba = apply_calibrator(py_proba, cal_path)

    # ONNX path
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    out = sess.run(None, {input_name: X_all})
    if len(out) == 2:
        onnx_proba = out[1][:, 1]
    elif out[0].ndim == 2 and out[0].shape[1] == 2:
        onnx_proba = out[0][:, 1]
    else:
        onnx_proba = out[0].ravel()
    if cal_path:
        onnx_proba = apply_calibrator(onnx_proba, cal_path)

    diffs = np.abs(py_proba - onnx_proba)
    report = {
        "n_samples": int(len(X_all)),
        "n_random": int(n_samples),
        "n_edge": int(len(X_edge)),
        "max_abs_diff": float(diffs.max()),
        "mean_abs_diff": float(diffs.mean()),
        "tolerance": float(cfg.onnx_tolerance),
        "pass": bool(diffs.max() <= cfg.onnx_tolerance),
        "calibrator_applied": bool(cal_path),
    }
    out_dir = Path(onnx_path).parent
    with open(out_dir / "v38_equivalence_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    return report
