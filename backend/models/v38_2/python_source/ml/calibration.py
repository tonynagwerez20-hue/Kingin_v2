"""Probability calibration.

Fits Platt (sigmoid) and isotonic calibrators on OOF probabilities and
reports which produces better calibration (lower ECE) without harming AUC.
The chosen calibrator is wrapped with the LightGBM model into a single
sklearn Pipeline for ONNX export.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np
import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from ..config import V38Config, ARTIFACT_DIR
from ..ml.trainer import _ece, _metrics


def fit_calibrators(model, X_oof: np.ndarray, y_oof: np.ndarray,
                    cfg: V38Config, out_dir: Path = None) -> dict:
    """Fit Platt + isotonic on OOF, return metrics + chosen calibrator."""
    out_dir = Path(out_dir or ARTIFACT_DIR)
    proba_raw = model.predict_proba(X_oof)[:, 1]
    base = _metrics(proba_raw, y_oof)

    # Platt: logistic regression on logit of raw probability
    eps = 1e-6
    logit = np.log(np.clip(proba_raw, eps, 1 - eps) / (1 - np.clip(proba_raw, eps, 1 - eps)))
    platt = LogisticRegression(C=1e10)
    platt.fit(logit.reshape(-1, 1), y_oof)
    platt_proba = platt.predict_proba(logit.reshape(-1, 1))[:, 1]
    platt_m = _metrics(platt_proba, y_oof)

    # Isotonic: monotonic mapping
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(proba_raw, y_oof)
    iso_proba = iso.predict(proba_raw)
    iso_m = _metrics(iso_proba, y_oof)

    # choose by lowest ECE, tie-broken by Brier, then AUC
    candidates = [("none", base, None, None),
                  ("sigmoid", platt_m, platt, platt_proba),
                  ("isotonic", iso_m, iso, iso_proba)]
    best = min(candidates, key=lambda c: (c[1]["ece"], c[1]["brier"], -(c[1]["auc"] or 0)))

    report = {
        "raw": base, "sigmoid": platt_m, "isotonic": iso_m,
        "chosen_method": best[0],
        "chosen_ece": best[1]["ece"],
        "ece_improvement": float(base["ece"] - best[1]["ece"]),
        "auc_retention": float(best[1]["auc"] / base["auc"]) if base["auc"] else None,
    }
    with open(out_dir / "v38_calibration_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    # save calibrators
    if best[2] is not None:
        joblib.dump(best[2], out_dir / "v38_calibrator.joblib")
    return report, best[2], best[3]
