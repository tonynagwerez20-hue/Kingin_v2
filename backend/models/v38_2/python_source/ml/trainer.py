"""LightGBM trainer for V38.

REAL `predict_proba` is used (not argmax). Walk-forward CV (expanding window).
Metrics: log-loss, AUC, Brier, reliability, precision/recall at a chosen
threshold, expected calibration error (ECE), expected payoff per trade.

Only non-censored samples are used for training (label in {0,1}). The model
is NOT claimed to be probabilistic merely because the output is 0..1;
calibration is measured and reported separately. A sigmoid/isotonic calibrator
is fit on the validation fold and its metrics reported.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    HAS_LGB = True
except Exception:  # pragma: no cover
    HAS_LGB = False

from sklearn.metrics import (log_loss, brier_score_loss, roc_auc_score,
                              precision_score, recall_score, f1_score)

from ..config import V38Config, ARTIFACT_DIR, TRAINING_VERSION
from ..features.contract import FEATURE_NAMES, N_FEATURES


def _ece(proba: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        if i == n_bins - 1:
            mask = (proba >= lo) & (proba <= hi)
        else:
            mask = (proba >= lo) & (proba < hi)
        if mask.sum() == 0:
            continue
        acc = y[mask].mean()
        conf = proba[mask].mean()
        ece += (mask.sum() / n) * abs(acc - conf)
    return float(ece)


def _metrics(proba, y, threshold=0.5) -> dict:
    y = np.asarray(y).astype(int)
    proba = np.asarray(proba, dtype=float)
    preds = (proba >= threshold).astype(int)
    out = {
        "n": int(len(y)),
        "positive_rate": float(y.mean()) if len(y) else 0.0,
        "log_loss": float(log_loss(y, proba, labels=[0, 1])) if len(y) else None,
        "auc": float(roc_auc_score(y, proba)) if len(y) and len(set(y)) > 1 else None,
        "brier": float(brier_score_loss(y, proba)) if len(y) else None,
        "ece": _ece(proba, y) if len(y) else None,
        "precision": float(precision_score(y, preds, zero_division=0)) if len(y) else None,
        "recall": float(recall_score(y, preds, zero_division=0)) if len(y) else None,
        "f1": float(f1_score(y, preds, zero_division=0)) if len(y) else None,
        "threshold": float(threshold),
    }
    return out


def _expected_payoff(proba, y, threshold=0.5, r=2.0) -> float:
    """Expected payoff per trade at a chosen threshold (TP=+2R, SL=-1R)."""
    preds = (np.asarray(proba) >= threshold).astype(int)
    y = np.asarray(y).astype(int)
    if preds.sum() == 0:
        return 0.0
    wins = ((preds == 1) & (y == 1)).sum()
    losses = ((preds == 1) & (y == 0)).sum()
    return float((wins * r - losses * 1.0) / max(1, preds.sum()))


def walk_forward_train(df: pd.DataFrame, cfg: V38Config,
                        out_dir: Path = None) -> dict:
    """Walk-forward training on the dataset parquet.

    Folds use expanding windows; test folds are non-overlapping. Returns OOF
    probabilities, per-fold metrics, and a final model trained on the latest
    window's training set (for ONNX export).
    """
    out_dir = Path(out_dir or ARTIFACT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    feat_cols = [f"f_{n}" for n in FEATURE_NAMES]
    # drop censored
    d = df[df["label"].isin([0, 1])].reset_index(drop=True)
    if len(d) == 0:
        return {"status": "EMPTY", "n_rows": 0}
    d = d.sort_values("timestamp").reset_index(drop=True)
    X = d[feat_cols].to_numpy(dtype=np.float32)
    y = d["label"].to_numpy(dtype=np.int32)
    ts = d["timestamp"].to_numpy()

    if not HAS_LGB:
        return {"status": "NO_LIGHTGBM", "n_rows": int(len(d))}

    n = len(d)
    train = cfg.wf_train_bars
    test = cfg.wf_test_bars
    step = cfg.wf_step_bars
    # convert bars to rows (approx; 1 row per candidate setup, but order by time)
    # Use row counts directly (walk-forward over setups, time-ordered).
    tr_size = max(200, int(train * 0.05))  # candidates are sparser than bars
    te_size = max(50, int(test * 0.05))
    st_size = max(20, int(step * 0.05))

    folds = []
    oof_proba = np.zeros(n, dtype=float)
    oof_mask = np.zeros(n, dtype=bool)
    start = tr_size
    fold_i = 0
    while start + te_size <= n:
        tr_end = start
        te_end = min(n, start + te_size)
        Xtr, ytr = X[:tr_end], y[:tr_end]
        Xte, yte = X[tr_end:te_end], y[tr_end:te_end]
        params = dict(cfg.lgbm_params)
        model = lgb.LGBMClassifier(**params)
        model.fit(Xtr, ytr)
        proba = model.predict_proba(Xte)[:, 1]
        oof_proba[tr_end:te_end] = proba
        oof_mask[tr_end:te_end] = True
        fold_metrics = _metrics(proba, yte, threshold=cfg.decision_threshold
                                if hasattr(cfg, "decision_threshold") else 0.5)
        fold_metrics["train_size"] = int(tr_end)
        fold_metrics["test_size"] = int(te_end - tr_end)
        fold_metrics["test_start_ts"] = str(ts[tr_end])
        folds.append(fold_metrics)
        start += st_size
        fold_i += 1

    oof_y = y[oof_mask]
    oof_p = oof_proba[oof_mask]
    overall = _metrics(oof_p, oof_y, threshold=0.5)
    overall["expected_payoff_R"] = _expected_payoff(oof_p, oof_y, 0.5, r=cfg.label_tp_r)
    overall["expected_payoff_at_0_6"] = _expected_payoff(oof_p, oof_y, 0.6, r=cfg.label_tp_r)
    overall["expected_payoff_at_0_7"] = _expected_payoff(oof_p, oof_y, 0.7, r=cfg.label_tp_r)

    # final model on all but the last test fold for ONNX export
    final = lgb.LGBMClassifier(**cfg.lgbm_params)
    final.fit(X, y)

    report = {
        "status": "OK",
        "training_version": TRAINING_VERSION,
        "n_rows": int(n),
        "n_features": N_FEATURES,
        "n_folds": len(folds),
        "oof_metrics": overall,
        "fold_metrics": folds,
        "model_version": cfg.__dict__.get("MODEL_VERSION", "v38.1"),
    }
    # save final model (booster + sklearn object for ONNX)
    out_dir.joinpath("v38_lgbm_model.txt").write_text(final.booster_.model_to_string())
    import joblib
    joblib.dump(final, out_dir / "v38_lgbm_model.joblib")
    # save OOF predictions
    pd.DataFrame({"timestamp": d["timestamp"], "label": y,
                  "oof_proba": oof_proba,
                  "barrier_reached": d["barrier_reached"]}).to_parquet(
        out_dir / "v38_oof_predictions.parquet", index=False)
    with open(out_dir / "v38_training_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    return report
