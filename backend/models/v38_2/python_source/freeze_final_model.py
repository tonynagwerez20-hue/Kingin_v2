"""V38.2 Final Model Freeze.

Trains the final LightGBM model on the full M5 train+validation set,
calibrates using OOF probabilities (no holdout), evaluates ONCE on the
untouched holdout, and saves all artifacts.

This script does NOT optimize on holdout. It freezes the exact model
configuration that produced AUC=0.580, PF=2.11, 14/14 fold stability.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
from sklearn.isotonic import IsotonicRegression

from v38.config import V38Config
from v38.features.contract import FEATURE_NAMES, N_FEATURES

PRICE_INDICES = [i for i in range(N_FEATURES)
                 if FEATURE_NAMES[i] != "event_present"
                 and FEATURE_NAMES[i] != "event_importance"
                 and FEATURE_NAMES[i] != "normalized_surprise"
                 and FEATURE_NAMES[i] != "surprise_zscore"
                 and FEATURE_NAMES[i] != "expected_gold_dir_enc"
                 and FEATURE_NAMES[i] != "observed_reaction_atr"]

# V38.2 contract uses 50 PRICE features (excludes 6 MACRO_NEWS at indices 44-49)
from v38.features.contract import FEATURE_SPECS
PRICE_INDICES = [i for i in range(N_FEATURES) if FEATURE_SPECS[i].family != "MACRO_NEWS"]

DATASET_PATH = Path(__file__).parent / "full_data_artifacts" / "v38_2_dataset_M5_H1_lb240.parquet"
ARTIFACT_DIR = Path(__file__).parent / "full_data_artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)


def _ece(proba, y, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (proba >= lo) & (proba < hi) if i < n_bins - 1 else (proba >= lo) & (proba <= hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y[mask].mean() - proba[mask].mean())
    return float(ece)


def _metrics(proba, y, threshold=0.5, tp_r=2.0, sl_r=1.0):
    y = np.asarray(y).astype(int)
    proba = np.asarray(proba, dtype=float)
    n = len(y)
    if n == 0:
        return {"n": 0}
    pred = (proba >= threshold).astype(int)
    tp = int(np.sum((pred == 1) & (y == 1)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    tn = int(np.sum((pred == 0) & (y == 0)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    n_trades = tp + fp
    wins = tp
    losses = fp
    win_rate = wins / n_trades if n_trades > 0 else 0.0
    avg_win = tp_r
    avg_loss = sl_r
    expectancy = (win_rate * avg_win - (1 - win_rate) * avg_loss) if n_trades > 0 else 0.0
    gross_profit = wins * avg_win
    gross_loss = losses * avg_loss
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
    auc = roc_auc_score(y, proba) if len(set(y)) > 1 else 0.5
    pr_auc = average_precision_score(y, proba) if len(set(y)) > 1 else 0.0
    brier = brier_score_loss(y, proba)
    ece = _ece(proba, y)
    return {
        "n": n, "n_positive": int(np.sum(y == 1)), "n_negative": int(np.sum(y == 0)),
        "raw_win_rate": float(np.mean(y == 1)),
        "model_win_rate": float(win_rate),
        "precision": float(win_rate),
        "n_trades": n_trades,
        "avg_win_R": float(avg_win), "avg_loss_R": float(-avg_loss),
        "expectancy_R": float(expectancy),
        "profit_factor": float(pf),
        "auc": float(auc), "pr_auc": float(pr_auc),
        "brier": float(brier), "ece": float(ece),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


def freeze_final_model():
    cfg = V38Config()
    print("Loading M5 dataset...", flush=True)
    df = pd.read_parquet(DATASET_PATH)
    df = df.sort_values("timestamp").reset_index(drop=True)
    n = len(df)

    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]
    X = df[feat_cols].to_numpy(dtype=np.float32)
    y = df["label"].to_numpy(dtype=int)
    ts = df["timestamp"].to_numpy()
    directions = df["direction"].to_numpy()

    # Filter censored (label == -1)
    mask = y >= 0
    X = X[mask]
    y = y[mask]
    ts = ts[mask]
    directions = directions[mask]
    n = len(y)
    print(f"  Loaded {n} labeled setups ({len(PRICE_INDICES)} features)", flush=True)

    holdout_start = int(n * 0.80)
    X_trval = X[:holdout_start]
    y_trval = y[:holdout_start]
    X_hold = X[holdout_start:]
    y_hold = y[holdout_start:]
    d_hold = directions[holdout_start:]

    print(f"  Train+Val: {len(y_trval)} setups, up to {pd.Timestamp(ts[holdout_start-1])}", flush=True)
    print(f"  Holdout:    {len(y_hold)} setups, from {pd.Timestamp(ts[holdout_start])}", flush=True)

    # --- Walk-forward OOF for calibration (NO holdout data) ---
    print("\nRunning walk-forward for OOF probabilities...", flush=True)
    min_train = max(200, int(n * 0.10))
    step = max(50, int(n * 0.05))
    oof_p = np.zeros(holdout_start)
    oof_m = np.zeros(holdout_start, dtype=bool)
    folds = []
    start = min_train
    while start + step <= holdout_start:
        te_end = min(holdout_start, start + step)
        Xtr, ytr = X_trval[:start], y_trval[:start]
        Xte, yte = X_trval[start:te_end], y_trval[start:te_end]
        if len(set(ytr)) < 2 or len(yte) == 0:
            start += step
            continue
        params = dict(cfg.lgbm_params)
        params["n_estimators"] = min(200, params.get("n_estimators", 400))
        model = lgb.LGBMClassifier(**params)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(Xtr, ytr)
        proba = model.predict_proba(Xte)[:, 1]
        oof_p[start:te_end] = proba
        oof_m[start:te_end] = True
        fm = _metrics(proba, yte, 0.5, cfg.label_tp_r, cfg.label_sl_r)
        fm["train_size"] = int(start)
        fm["test_size"] = int(te_end - start)
        folds.append(fm)
        start += step
    oof_y = y_trval[oof_m]
    oof_proba = oof_p[oof_m]
    val_m = _metrics(oof_proba, oof_y, 0.5, cfg.label_tp_r, cfg.label_sl_r)
    print(f"  Val: AUC={val_m['auc']:.4f}, PF={val_m['profit_factor']:.2f}, "
          f"ECE={val_m['ece']:.4f}, folds={len(folds)}", flush=True)

    # --- Calibrate on OOF (isotonic) ---
    print("\nFitting isotonic calibrator on OOF...", flush=True)
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(oof_proba, oof_y)
    oof_cal = iso.predict(oof_proba)
    val_cal_m = _metrics(oof_cal, oof_y, 0.5, cfg.label_tp_r, cfg.label_sl_r)
    print(f"  Val (calibrated): AUC={val_cal_m['auc']:.4f}, "
          f"ECE={val_cal_m['ece']:.4f}", flush=True)

    # --- Train FINAL model on ALL train+val data ---
    print("\nTraining FINAL model on all train+val data...", flush=True)
    params = dict(cfg.lgbm_params)
    params["n_estimators"] = min(200, params.get("n_estimators", 400))
    final_model = lgb.LGBMClassifier(**params)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        final_model.fit(X_trval, y_trval)
    print("  Final model trained.", flush=True)

    # --- Evaluate ONCE on holdout ---
    print("\nEvaluating on untouched holdout...", flush=True)
    hp_raw = final_model.predict_proba(X_hold)[:, 1]
    hp_cal = iso.predict(hp_raw)
    hold_m_raw = _metrics(hp_raw, y_hold, 0.5, cfg.label_tp_r, cfg.label_sl_r)
    hold_m_cal = _metrics(hp_cal, y_hold, 0.5, cfg.label_tp_r, cfg.label_sl_r)

    # By direction
    hold_by_dir = {}
    for d in ["bullish", "bearish"]:
        dmask = d_hold == d
        if dmask.sum() > 0:
            hold_by_dir[d] = _metrics(hp_cal[dmask], y_hold[dmask], 0.5,
                                       cfg.label_tp_r, cfg.label_sl_r)

    print(f"\n  Holdout (raw):    AUC={hold_m_raw['auc']:.4f}, PF={hold_m_raw['profit_factor']:.2f}", flush=True)
    print(f"  Holdout (cal):    AUC={hold_m_cal['auc']:.4f}, PF={hold_m_cal['profit_factor']:.2f}", flush=True)
    print(f"  Holdout trades:   {hold_m_cal['n_trades']}", flush=True)
    print(f"  Holdout WR:       {hold_m_cal['model_win_rate']:.1%} (raw {hold_m_cal['raw_win_rate']:.1%})", flush=True)
    print(f"  Holdout expectancy: {hold_m_cal['expectancy_R']:+.3f}R", flush=True)

    # --- Save artifacts ---
    print("\nSaving artifacts...", flush=True)
    model_path = ARTIFACT_DIR / "v38_2_final_model.joblib"
    calibrator_path = ARTIFACT_DIR / "v38_2_calibrator.joblib"
    joblib.dump(final_model, model_path)
    joblib.dump(iso, calibrator_path)
    print(f"  Model: {model_path}", flush=True)
    print(f"  Calibrator: {calibrator_path}", flush=True)

    # --- Save report ---
    fold_aucs = [f["auc"] for f in folds if f.get("auc") is not None]
    fold_exps = [f["expectancy_R"] for f in folds]
    report = {
        "audit_type": "V38_2_FINAL_MODEL_FREEZE",
        "timestamp_utc": pd.Timestamp.utcnow().isoformat(),
        "dataset": str(DATASET_PATH),
        "n_setups_total": int(n),
        "n_trainval": int(len(y_trval)),
        "n_holdout": int(len(y_hold)),
        "feature_indices": PRICE_INDICES,
        "feature_names": [FEATURE_NAMES[i] for i in PRICE_INDICES],
        "n_features": len(PRICE_INDICES),
        "lgbm_params": params,
        "label_tp_r": cfg.label_tp_r,
        "label_sl_r": cfg.label_sl_r,
        "label_max_bars": 240,
        "calibration_method": "isotonic",
        "calibration_data": "OOF (train+val only, no holdout)",
        "val_metrics_raw": val_m,
        "val_metrics_calibrated": val_cal_m,
        "holdout_metrics_raw": hold_m_raw,
        "holdout_metrics_calibrated": hold_m_cal,
        "holdout_by_direction_calibrated": hold_by_dir,
        "stability": {
            "n_folds": len(folds),
            "auc_mean": float(np.mean(fold_aucs)) if fold_aucs else None,
            "auc_std": float(np.std(fold_aucs)) if fold_aucs else None,
            "expectancy_mean": float(np.mean(fold_exps)) if fold_exps else None,
            "expectancy_std": float(np.std(fold_exps)) if fold_exps else None,
            "positive_folds": int(sum(1 for e in fold_exps if e > 0)),
            "stability_ratio": float(sum(1 for e in fold_exps if e > 0) / len(folds)) if folds else 0,
        },
        "folds": folds,
        "split": {
            "trainval_end_ts": str(ts[holdout_start - 1]),
            "holdout_start_ts": str(ts[holdout_start]),
            "holdout_end_ts": str(ts[-1]),
        },
        "artifacts": {
            "model": str(model_path),
            "calibrator": str(calibrator_path),
        },
    }
    report_path = ARTIFACT_DIR / "V38_2_FINAL_MODEL_FREEZE_REPORT.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Report: {report_path}", flush=True)

    print("\n=== FINAL MODEL FROZEN ===", flush=True)
    print(f"Holdout (calibrated): AUC={hold_m_cal['auc']:.4f}, "
          f"PF={hold_m_cal['profit_factor']:.2f}, "
          f"Stability={report['stability']['stability_ratio']:.1f}", flush=True)

    return report


if __name__ == "__main__":
    freeze_final_model()
