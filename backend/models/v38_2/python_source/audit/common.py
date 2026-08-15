"""Shared metrics + fold reconstruction for the V38 robustness audit.

The walk-forward in `ml/trainer.py` is deterministic (seed=42, deterministic=True),
so re-running the same fold boundaries reproduces the exact per-fold models and
predictions. This module exposes those boundaries and the per-fold models so the
audit can attribute every OOF prediction to its fold.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import lightgbm as lgb

from ..config import V38Config, ARTIFACT_DIR
from ..features.contract import FEATURE_NAMES, N_FEATURES

FEAT_COLS = [f"f_{n}" for n in FEATURE_NAMES]


def load_dataset() -> pd.DataFrame:
    df = pd.read_parquet(ARTIFACT_DIR / "v38_dataset.parquet")
    df = df[df["label"].isin([0, 1])].sort_values("timestamp").reset_index(drop=True)
    return df


def fold_boundaries(n: int, cfg: V38Config) -> List[Tuple[int, int]]:
    """Reproduce the trainer's walk-forward (tr_end, te_end) pairs."""
    tr_size = max(200, int(cfg.wf_train_bars * 0.05))
    te_size = max(50, int(cfg.wf_test_bars * 0.05))
    st_size = max(20, int(cfg.wf_step_bars * 0.05))
    bounds = []
    start = tr_size
    while start + te_size <= n:
        bounds.append((start, min(n, start + te_size)))
        start += st_size
    return bounds


def reconstruct_folds(df: pd.DataFrame, cfg: V38Config):
    """Re-fit each fold model deterministically; return per-fold model + proba.
    Mirrors trainer.walk_forward_train exactly."""
    X = df[FEAT_COLS].to_numpy(dtype=np.float32)
    y = df["label"].to_numpy(dtype=np.int32)
    bounds = fold_boundaries(len(df), cfg)
    folds = []
    for tr_end, te_end in bounds:
        model = lgb.LGBMClassifier(**cfg.lgbm_params)
        model.fit(X[:tr_end], y[:tr_end])
        proba = model.predict_proba(X[tr_end:te_end])[:, 1]
        folds.append({
            "model": model, "tr_end": tr_end, "te_end": te_end,
            "test_idx": np.arange(tr_end, te_end), "proba": proba,
        })
    return folds


def auc_score(y, p):
    y = np.asarray(y, int); p = np.asarray(p, float)
    if len(set(y)) < 2:
        return None
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p))


def pr_auc_score(y, p):
    y = np.asarray(y, int); p = np.asarray(p, float)
    if len(set(y)) < 2 or int(y.sum()) == 0:
        return None
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, p))


def brier_score(y, p):
    from sklearn.metrics import brier_score_loss
    return float(brier_score_loss(np.asarray(y, int), np.asarray(p, float)))


def logloss_score(y, p):
    from sklearn.metrics import log_loss
    return float(log_loss(np.asarray(y, int), np.asarray(p, float), labels=[0, 1]))


def ece_score(p, y, n_bins=10):
    p = np.asarray(p, float); y = np.asarray(y, int)
    bins = np.linspace(0, 1, n_bins + 1); ece = 0.0; n = len(y)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (p >= lo) & (p <= hi) if i == n_bins - 1 else (p >= lo) & (p < hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y[mask].mean() - p[mask].mean())
    return float(ece)


def reliability_bins(p, y, n_bins=10):
    p = np.asarray(p, float); y = np.asarray(y, int)
    bins = np.linspace(0, 1, n_bins + 1); rows = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (p >= lo) & (p <= hi) if i == n_bins - 1 else (p >= lo) & (p < hi)
        cnt = int(mask.sum())
        rows.append({
            "bin_lo": round(float(lo), 3), "bin_hi": round(float(hi), 3),
            "count": cnt, "frac": round(cnt / len(y), 4) if len(y) else 0.0,
            "mean_pred": round(float(p[mask].mean()), 4) if cnt else 0.0,
            "mean_actual": round(float(y[mask].mean()), 4) if cnt else 0.0,
        })
    return rows


def expected_r(p, y, threshold, tp_r=2.0):
    preds = (np.asarray(p) >= threshold).astype(int)
    y = np.asarray(y, int)
    if preds.sum() == 0:
        return 0.0, 0
    wins = int(((preds == 1) & (y == 1)).sum())
    losses = int(((preds == 1) & (y == 0)).sum())
    return float((wins * tp_r - losses) / max(1, preds.sum())), int(preds.sum())


def win_rate(p, y, threshold):
    preds = (np.asarray(p) >= threshold).astype(int)
    y = np.asarray(y, int)
    if preds.sum() == 0:
        return 0.0, 0
    wins = int(((preds == 1) & (y == 1)).sum())
    return float(wins / preds.sum()), int(preds.sum())


def profit_factor(p, y, threshold, tp_r=2.0):
    preds = (np.asarray(p) >= threshold).astype(int)
    y = np.asarray(y, int)
    gains = float(((preds == 1) & (y == 1)).sum() * tp_r)
    losses = float(((preds == 1) & (y == 0)).sum())
    return float(gains / losses) if losses > 0 else (float("inf") if gains > 0 else 0.0)


def r_distribution(p, y, threshold, tp_r=2.0):
    preds = (np.asarray(p) >= threshold).astype(int)
    y = np.asarray(y, int)
    rs = np.where((preds == 1) & (y == 1), tp_r,
         np.where((preds == 1) & (y == 0), -1.0, 0.0))
    rs = rs[rs != 0]
    if len(rs) == 0:
        return {"n": 0}
    return {
        "n": int(len(rs)), "mean": float(rs.mean()), "median": float(np.median(rs)),
        "std": float(rs.std()), "min": float(rs.min()), "max": float(rs.max()),
        "p10": float(np.percentile(rs, 10)), "p90": float(np.percentile(rs, 90)),
    }


def max_drawdown_r(p, y, threshold, tp_r=2.0):
    preds = (np.asarray(p) >= threshold).astype(int)
    y = np.asarray(y, int)
    rs = np.where((preds == 1) & (y == 1), tp_r,
         np.where((preds == 1) & (y == 0), -1.0, 0.0))
    eq = np.cumsum(rs)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    return float(dd.max()) if len(dd) else 0.0


def summarize(vals):
    arr = np.asarray([v for v in vals if v is not None], dtype=float)
    if len(arr) == 0:
        return {"n": 0}
    return {
        "n": int(len(arr)), "mean": float(arr.mean()), "median": float(np.median(arr)),
        "std": float(arr.std()), "min": float(arr.min()), "max": float(arr.max()),
    }
