"""V38 model robustness audit — produces a full diagnostic report.

No model changes, no parameter optimization against OOF results, no data
fabrication. Pure measurement of whether the 56-feature model contains a
stable, generalizable edge.

Run:
    PYTHONPATH=. python3 -m v38.audit.robustness
Writes:
    models/v38/v38_robustness_report.json
    models/v38/v38_robustness_report.md
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedShuffleSplit

from ..config import DEFAULT_CONFIG as CFG, ARTIFACT_DIR
from ..features.contract import FEATURE_NAMES, N_FEATURES
from .common import (FEAT_COLS, load_dataset, fold_boundaries, reconstruct_folds,
                     auc_score, pr_auc_score, brier_score, logloss_score, ece_score,
                     reliability_bins, expected_r, win_rate, profit_factor,
                     r_distribution, max_drawdown_r, summarize)

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(42)
TP_R = CFG.label_tp_r
THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def _calibrate(raw, y, method):
    if method == "none":
        return raw
    if method == "sigmoid":
        eps = 1e-6
        c = np.clip(raw, eps, 1 - eps)
        logit = np.log(c / (1 - c))
        lr = LogisticRegression(C=1e10).fit(logit.reshape(-1, 1), y)
        return lr.predict_proba(logit.reshape(-1, 1))[:, 1]
    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip").fit(raw, y)
        return iso.predict(raw)
    return raw


def task1_fold_analysis(df, folds):
    """Per-fold AUC, PR-AUC, Brier, ECE, expected R, trade count, positive rate."""
    y_all = df["label"].to_numpy(int)
    rows = []
    for i, f in enumerate(folds):
        idx = f["test_idx"]; p = f["proba"]; y = y_all[idx]
        er50, n50 = expected_r(p, y, 0.50, TP_R)
        rows.append({
            "fold": i, "train_size": int(f["tr_end"]), "test_size": int(f["te_end"] - f["tr_end"]),
            "test_start_ts": str(df["timestamp"].iloc[f["tr_end"]]),
            "auc": auc_score(y, p), "pr_auc": pr_auc_score(y, p),
            "brier": brier_score(y, p), "ece": ece_score(p, y),
            "expected_r_0.50": er50, "trade_count_0.50": n50,
            "positive_rate": float(y.mean()) if len(y) else 0.0,
        })
    aucs = [r["auc"] for r in rows if r["auc"] is not None]
    out = {
        "folds": rows,
        "n_folds": len(rows),
        "auc_summary": summarize(aucs),
        "pr_auc_summary": summarize([r["pr_auc"] for r in rows if r["pr_auc"] is not None]),
        "brier_summary": summarize([r["brier"] for r in rows]),
        "ece_summary": summarize([r["ece"] for r in rows]),
        "expected_r_summary": summarize([r["expected_r_0.50"] for r in rows]),
        "trade_count_summary": summarize([r["trade_count_0.50"] for r in rows]),
        "positive_rate_summary": summarize([r["positive_rate"] for r in rows]),
        "pct_folds_auc_gt_0.50": float(np.mean([a > 0.50 for a in aucs])) if aucs else None,
        "pct_folds_auc_gt_0.55": float(np.mean([a > 0.55 for a in aucs])) if aucs else None,
    }
    return out


def task2_feature_stability(df, folds):
    """Gain, permutation, SHAP importance + per-fold rank stability."""
    X = df[FEAT_COLS].to_numpy(np.float32)
    y = df["label"].to_numpy(int)

    # global gain importance (mean across folds, weighted by fold size)
    gain_per_fold = []
    for f in folds:
        g = f["model"].booster_.feature_importance(importance_type="gain")
        gain_per_fold.append(g)
    gain_arr = np.array(gain_per_fold)  # [n_folds, n_features]
    global_gain = gain_arr.mean(axis=0)
    global_gain_rank = np.argsort(np.argsort(-global_gain)) + 1  # rank 1..N

    # per-fold ranks + % folds in top 10
    fold_ranks = np.zeros_like(gain_arr)
    top10_counts = np.zeros(N_FEATURES)
    for i, g in enumerate(gain_per_fold):
        r = np.argsort(np.argsort(-g)) + 1
        fold_ranks[i] = r
        top10_counts[r <= 10] += 1
    pct_top10 = top10_counts / len(folds)

    # rank stability: 1 - normalized std of ranks (Kendall-style via CV of ranks)
    rank_cv = fold_ranks.std(axis=0) / N_FEATURES
    rank_stability = 1.0 - rank_cv

    # permutation importance (on final model, held-out last 30% time-ordered)
    final = lgb.LGBMClassifier(**CFG.lgbm_params).fit(X[:int(len(df)*0.7)], y[:int(len(df)*0.7)])
    te = slice(int(len(df)*0.7), len(df))
    perm = permutation_importance(final, X[te], y[te], n_repeats=5,
                                   random_state=42, scoring="roc_auc")
    perm_imp = perm.importances_mean
    perm_rank = np.argsort(np.argsort(-perm_imp)) + 1

    # SHAP (final model, subsample for speed)
    shap_imp = None
    try:
        import shap
        n_sub = min(1500, len(df))
        sub = RNG.choice(len(df), n_sub, replace=False)
        expl = shap.TreeExplainer(final)
        sv = expl.shap_values(X[sub])
        # binary LGBM: shap returns either list of 2 arrays or single array
        if isinstance(sv, list):
            sv = sv[1]
        shap_imp = np.abs(sv).mean(axis=0)
    except Exception as e:
        shap_imp = None
        print(f"SHAP skipped: {e}")

    # redundant/correlated features (|corr| > 0.85)
    corr = np.corrcoef(X, rowvar=False)
    red_pairs = []
    for i in range(N_FEATURES):
        for j in range(i + 1, N_FEATURES):
            c = corr[i, j]
            if not np.isnan(c) and abs(c) > 0.85:
                red_pairs.append({"a": FEATURE_NAMES[i], "b": FEATURE_NAMES[j],
                                  "corr": round(float(c), 3)})
    redundant = set()
    for pr in red_pairs:
        # mark the lower-importance member as redundant
        a, b = FEATURE_NAMES.index(pr["a"]), FEATURE_NAMES.index(pr["b"])
        redundant.add(pr["a"] if global_gain[a] < global_gain[b] else pr["b"])

    feat_rows = []
    for k, name in enumerate(FEATURE_NAMES):
        feat_rows.append({
            "feature": name, "global_gain": float(global_gain[k]),
            "gain_rank": int(global_gain_rank[k]),
            "permutation_importance": float(perm_imp[k]),
            "permutation_rank": int(perm_rank[k]),
            "shap_importance": float(shap_imp[k]) if shap_imp is not None else None,
            "shap_rank": int(np.argsort(np.argsort(-shap_imp))[k] + 1) if shap_imp is not None else None,
            "mean_fold_rank": float(fold_ranks[:, k].mean()),
            "rank_stability": float(rank_stability[k]),
            "pct_folds_top10": float(pct_top10[k]),
            "redundant": name in redundant,
        })
    feat_rows.sort(key=lambda r: -r["global_gain"])
    return {
        "features": feat_rows,
        "n_redundant": len(redundant),
        "redundant_pairs": red_pairs,
        "redundant_threshold_corr": 0.85,
        "shap_available": shap_imp is not None,
        "top10_by_gain": [r["feature"] for r in feat_rows[:10]],
        "top10_by_shap": [r["feature"] for r in sorted(feat_rows, key=lambda x: -(x["shap_importance"] or 0))[:10]] if shap_imp is not None else None,
        "top10_by_permutation": [r["feature"] for r in sorted(feat_rows, key=lambda x: -x["permutation_importance"])[:10]],
    }


def _regime_label(row):
    htf = row["f_htf_regime_enc"]; vol = row["f_volatility_regime_enc"]
    pdp = row["f_pd_position"]; atrp = row["f_atr_percentile"]
    # trend vs range from PD position proximity to equilibrium
    if abs(pdp - 0.5) < 0.15:
        trend = "ranging"
    elif htf >= 1.5:
        trend = "bullish_trend"
    elif htf <= 0.5:
        trend = "bearish_trend"
    else:
        trend = "ranging"
    volc = "high_vol" if atrp > 0.75 else ("low_vol" if atrp < 0.25 else "mid_vol")
    return trend, volc


def task3_regime_analysis(df, folds):
    oof_p = np.zeros(len(df)); oof_mask = np.zeros(len(df), bool)
    for f in folds:
        oof_p[f["test_idx"]] = f["proba"]; oof_mask[f["test_idx"]] = True
    df = df.copy()
    df["oof_p"] = oof_p
    df = df[oof_mask].reset_index(drop=True)
    trends = []; vols = []
    for _, r in df.iterrows():
        t, v = _regime_label(r); trends.append(t); vols.append(v)
    df["trend"] = trends; df["vol"] = vols
    sess_map = {0: "asian", 1: "london", 2: "overlap", 3: "ny", 4: "off"}
    df["sess"] = df["f_session_enc"].round().astype(int).map(sess_map)

    def block(sub):
        y = sub["label"].to_numpy(int); p = sub["oof_p"].to_numpy(float)
        er, n = expected_r(p, y, 0.50, TP_R)
        wr, _ = win_rate(p, y, 0.50)
        return {
            "n": int(len(sub)), "positive_rate": float(y.mean()) if len(y) else 0.0,
            "auc": auc_score(y, p), "pr_auc": pr_auc_score(y, p),
            "brier": brier_score(y, p), "ece": ece_score(p, y),
            "expected_r_0.50": er, "win_rate_0.50": wr, "trade_count_0.50": n,
        }

    out = {
        "trend": {g: block(df[df["trend"] == g]) for g in ["bullish_trend", "bearish_trend", "ranging"]},
        "volatility": {g: block(df[df["vol"] == g]) for g in ["high_vol", "low_vol", "mid_vol"]},
        "session": {g: block(df[df["sess"] == g]) for g in ["asian", "london", "overlap", "ny"] if (df["sess"] == g).any()},
    }
    return out


def task4_direction_analysis(df, folds):
    oof_p = np.zeros(len(df)); oof_mask = np.zeros(len(df), bool)
    for f in folds:
        oof_p[f["test_idx"]] = f["proba"]; oof_mask[f["test_idx"]] = True
    df = df.copy(); df["oof_p"] = oof_p
    df = df[oof_mask].reset_index(drop=True)

    def block(sub):
        y = sub["label"].to_numpy(int); p = sub["oof_p"].to_numpy(float)
        er, n = expected_r(p, y, 0.50, TP_R)
        wr, _ = win_rate(p, y, 0.50)
        return {
            "n": int(len(sub)), "positive_rate": float(y.mean()) if len(y) else 0.0,
            "auc": auc_score(y, p), "pr_auc": pr_auc_score(y, p),
            "brier": brier_score(y, p), "ece": ece_score(p, y),
            "expectancy_R": er, "win_rate": wr, "trade_count": n,
        }
    return {"bullish": block(df[df["direction"] == "bullish"]),
            "bearish": block(df[df["direction"] == "bearish"])}


def task5_baseline(df, folds):
    """A: no ML, B: V38 ML filter, C: shuffled scores — same setups/labels."""
    oof_p = np.zeros(len(df)); oof_mask = np.zeros(len(df), bool)
    for f in folds:
        oof_p[f["test_idx"]] = f["proba"]; oof_mask[f["test_idx"]] = True
    d = df.copy()
    d["oof_p"] = oof_p
    d = d[oof_mask].reset_index(drop=True)
    y = d["label"].to_numpy(int)
    shuffled = RNG.permutation(d["oof_p"].to_numpy(float))

    def block(p, threshold=0.50):
        return {
            "expectancy_R": expected_r(p, y, threshold, TP_R)[0],
            "profit_factor": profit_factor(p, y, threshold, TP_R),
            "win_rate": win_rate(p, y, threshold)[0],
            "trade_count": win_rate(p, y, threshold)[1],
            "max_drawdown_R": max_drawdown_r(p, y, threshold, TP_R),
            "r_distribution": r_distribution(p, y, threshold, TP_R),
            "auc": auc_score(y, p), "brier": brier_score(y, p),
        }

    # A: no ML = take ALL setups (threshold irrelevant, p set to >=threshold)
    allp = np.ones(len(y))  # everything trades
    a = block(allp, 0.50)
    # B: V38 ML filter at 0.50
    b = block(d["oof_p"].to_numpy(float), 0.50)
    # C: shuffled scores at 0.50
    c = block(shuffled, 0.50)
    # also report B at a higher threshold to show filtering effect
    b_06 = block(d["oof_p"].to_numpy(float), 0.60)
    return {"A_no_ml": a, "B_v38_ml_0.50": b, "B_v38_ml_0.60": b_06, "C_shuffled_0.50": c}


def task6_threshold_robustness(df, folds):
    oof_p = np.zeros(len(df)); oof_mask = np.zeros(len(df), bool)
    for f in folds:
        oof_p[f["test_idx"]] = f["proba"]; oof_mask[f["test_idx"]] = True
    d = df.copy()
    d["oof_p"] = oof_p
    d = d[oof_mask].reset_index(drop=True)
    y = d["label"].to_numpy(int); p = d["oof_p"].to_numpy(float)
    rows = []
    for t in THRESHOLDS:
        er, n = expected_r(p, y, t, TP_R)
        wr, _ = win_rate(p, y, t)
        rows.append({
            "threshold": t, "expectancy_R": er, "win_rate": wr, "trade_count": n,
            "profit_factor": profit_factor(p, y, t, TP_R),
            "max_drawdown_R": max_drawdown_r(p, y, t, TP_R),
            "auc": auc_score(y, p),  # AUC is threshold-independent
            "positive_rate_selected": float(y[(p >= t)].mean()) if (p >= t).sum() else 0.0,
        })
    return {"thresholds": rows, "note": "No threshold selected from this data as 'best'; all pre-specified."}


def task7_calibration_audit(df, folds):
    oof_p = np.zeros(len(df)); oof_mask = np.zeros(len(df), bool)
    for f in folds:
        oof_p[f["test_idx"]] = f["proba"]; oof_mask[f["test_idx"]] = True
    d = df.copy()
    d["oof_p"] = oof_p
    d = d[oof_mask].reset_index(drop=True)
    y = d["label"].to_numpy(int); raw = d["oof_p"].to_numpy(float)
    platt = _calibrate(raw, y, "sigmoid")
    iso = _calibrate(raw, y, "isotonic")

    def block(p, name):
        return {
            "method": name, "auc": auc_score(y, p), "brier": brier_score(y, p),
            "ece": ece_score(p, y), "log_loss": logloss_score(y, p),
            "reliability": reliability_bins(p, y),
        }
    return {
        "raw": block(raw, "raw"),
        "platt": block(platt, "sigmoid"),
        "isotonic": block(iso, "isotonic"),
        "note": "Calibration measures reliability of probabilities, NOT predictive power. AUC is discrimination.",
    }


def task8_overfitting_audit(t1, t3, t4, t2, t6):
    aucs = [f["auc"] for f in t1["folds"] if f["auc"] is not None]
    fold_stab = {
        "auc_mean": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
        "auc_min": float(np.min(aucs)), "auc_max": float(np.max(aucs)),
        "pct_folds_positive_er": float(np.mean([f["expected_r_0.50"] > 0 for f in t1["folds"]])),
        "pct_folds_auc_gt_0.50": t1["pct_folds_auc_gt_0.50"],
        "conclusion": "",
    }
    # regime stability
    reg_aucs = {k: v["auc"] for k, v in t3["trend"].items() if v["auc"] is not None}
    vol_aucs = {k: v["auc"] for k, v in t3["volatility"].items() if v["auc"] is not None}
    sess_aucs = {k: v["auc"] for k, v in t3["session"].items() if v["auc"] is not None}
    # direction stability
    dir_aucs = {k: v["auc"] for k, v in t4.items() if v["auc"] is not None}
    # feature stability
    top10_stab = [f["pct_folds_top10"] for f in t2["features"][:10]]
    feat_stab = {
        "top10_mean_pct_folds_in_top10": float(np.mean(top10_stab)) if top10_stab else 0.0,
        "n_features_top10_stable_50pct": int(np.sum([p >= 0.5 for p in top10_stab])),
    }
    # threshold stability
    th_ers = [r["expectancy_R"] for r in t6["thresholds"]]
    th_stab = {
        "expectancy_positive_at_all_thresholds": bool(all(e > 0 for e in th_ers)),
        "expectancy_min": float(min(th_ers)), "expectancy_max": float(max(th_ers)),
        "trade_count_at_0.50": next(r["trade_count"] for r in t6["thresholds"] if r["threshold"] == 0.50),
        "trade_count_at_0.90": next(r["trade_count"] for r in t6["thresholds"] if r["threshold"] == 0.90),
    }
    # verdict on whether AUC is consistently weak-but-real vs favorable-fold artifact
    weak_but_real = (
        fold_stab["pct_folds_auc_gt_0.50"] >= 0.55 and
        abs(fold_stab["auc_mean"] - 0.542) < 0.05 and
        fold_stab["auc_std"] < 0.12 and
        th_stab["expectancy_positive_at_all_thresholds"]
    )
    fold_stab["conclusion"] = ("weak_but_real" if weak_but_real else "favorable_fold_artifact_or_unstable")
    return {
        "fold_stability": fold_stab,
        "regime_stability": {
            "trend_aucs": reg_aucs, "volatility_aucs": vol_aucs, "session_aucs": sess_aucs,
            "trend_auc_spread": float(max(reg_aucs.values()) - min(reg_aucs.values())) if reg_aucs else None,
        },
        "direction_stability": {"aucs": dir_aucs,
            "spread": float(max(dir_aucs.values()) - min(dir_aucs.values())) if len(dir_aucs) > 1 else None},
        "feature_stability": feat_stab,
        "threshold_stability": th_stab,
        "overall": "weak_but_real" if weak_but_real else "unstable",
    }


def task9_data_needs(df):
    return {
        "rule": "No fabrication. No duplication, per-candle recording, synthetic labels, augmentation, or leakage.",
        "current": {"n_setups": int(len(df)), "period": f"{df['timestamp'].min()} -> {df['timestamp'].max()}",
                    "timeframes": sorted(df["timeframe"].unique().tolist())},
        "what_would_materially_help": (
            "Genuine M5 + M15 data over the same 2018-2026 window. Finer timeframes produce "
            "more genuine candidate setups per structural event (entry timing, OB/FVG formation, "
            "liquidity sweeps resolve on M5/M15, not H1). This is the only path to a larger "
            "genuine sample without fabrication. Additional macro calendar history (pre-2018) "
            "would marginally help macro features but is secondary to M5/M15 coverage. "
            "More years of H1/H4 alone would NOT materially help — the limiting factor is "
            "candidate resolution, not history length."
        ),
    }


def task10_verdict(audit):
    fs = audit["task8"]
    t5 = audit["task5"]
    ml = t5["B_v38_ml_0.50"]; noml = t5["A_no_ml"]; shuf = t5["C_shuffled_0.50"]
    overall = fs["overall"]
    # Does ML add value over SMC-only?
    ml_adds_value = (ml["expectancy_R"] > noml["expectancy_R"]) and (ml["expectancy_R"] > shuf["expectancy_R"])
    edge_real = (overall == "weak_but_real") and ml_adds_value and fs["fold_stability"]["pct_folds_auc_gt_0.50"] >= 0.55
    # decision tree
    if not edge_real:
        if not ml_adds_value:
            verdict = "F"  # ML doesn't add value
        elif fs["overall"] != "weak_but_real":
            verdict = "E"  # unstable -> need more data / different approach
        else:
            verdict = "D"
    else:
        # edge real but weak; check if features are bloated/unstable
        n_redundant = audit["task2"]["n_redundant"]
        if n_redundant >= 8 or audit["task2"]["features"][0]["pct_folds_top10"] < 0.4:
            verdict = "C"  # reduce feature set
        else:
            verdict = "A"  # retain
    return {
        "verdict": verdict,
        "options": {"A": "RETAIN CURRENT MODEL", "B": "RETRAIN WITH SAME FEATURES",
                    "C": "REDUCE FEATURE SET", "D": "REDESIGN FEATURES",
                    "E": "INCREASE DATA FIRST", "F": "ABANDON CURRENT ML APPROACH"},
        "ml_adds_value_over_smc": bool(ml_adds_value),
        "ml_expectancy_R": ml["expectancy_R"], "smc_only_expectancy_R": noml["expectancy_R"],
        "shuffled_expectancy_R": shuf["expectancy_R"],
        "edge_classification": "weak_but_real" if edge_real else "not_established",
        "caveats": [
            "No profitability claim is made.",
            "AUC > 0.50 alone does not establish an edge.",
            "Probability calibration does not prove predictive power.",
            "Verdict reflects measured stability, not backtest profit.",
        ],
        "proceed_to_mt5_validation": verdict in {"A", "C"},
    }


def run():
    df = load_dataset()
    folds = reconstruct_folds(df, CFG)
    audit = {}
    audit["task1"] = task1_fold_analysis(df, folds)
    print("task1 done")
    audit["task2"] = task2_feature_stability(df, folds)
    print("task2 done")
    audit["task3"] = task3_regime_analysis(df, folds)
    print("task3 done")
    audit["task4"] = task4_direction_analysis(df, folds)
    print("task4 done")
    audit["task5"] = task5_baseline(df, folds)
    print("task5 done")
    audit["task6"] = task6_threshold_robustness(df, folds)
    print("task6 done")
    audit["task7"] = task7_calibration_audit(df, folds)
    print("task7 done")
    audit["task8"] = task8_overfitting_audit(audit["task1"], audit["task3"], audit["task4"], audit["task2"], audit["task6"])
    print("task8 done")
    audit["task9"] = task9_data_needs(df)
    audit["task10"] = task10_verdict(audit)
    audit["metadata"] = {
        "n_features": N_FEATURES, "n_setups": int(len(df)),
        "n_folds": len(folds), "tp_r": TP_R,
        "thresholds": THRESHOLDS, "seed": 42, "deterministic": True,
    }
    out_json = ARTIFACT_DIR / "v38_robustness_report.json"
    out_json.write_text(json.dumps(audit, indent=2, default=str))
    print("wrote", out_json)
    return audit


if __name__ == "__main__":
    run()
