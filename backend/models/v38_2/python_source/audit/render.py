"""Render the V38 robustness JSON report into the human-readable markdown report."""
import json
from pathlib import Path
from ..config import ARTIFACT_DIR


def _r(x, n=4):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{n}f}"
    return str(x)


def render():
    a = json.loads((ARTIFACT_DIR / "v38_robustness_report.json").read_text())
    t1, t2, t3, t4, t5, t6, t7, t8 = (a["task1"], a["task2"], a["task3"],
        a["task4"], a["task5"], a["task6"], a["task7"], a["task8"])
    t9, t10 = a["task9"], a["task10"]
    L = []
    w = L.append

    w("# V38.1 — Model Robustness Audit Report\n")
    w("**Purpose:** determine whether the current 56-feature model contains a stable, "
      "generalizable edge. No model changes, no parameter optimization against OOF results, "
      "no data fabrication. All metrics are out-of-fold (walk-forward, 103 folds, deterministic seed 42).\n")
    w(f"- Setups: {a['metadata']['n_setups']} | Features: {a['metadata']['n_features']} | "
      f"Folds: {a['metadata']['n_folds']} | TP:R = {a['metadata']['tp_r']}:1\n")
    w("**No profitability claim is made. AUC > 0.50 alone does not establish an edge. "
      "Probability calibration does not prove predictive power.**\n")

    # ---- TASK 1 ----
    w("## Task 1 — Fold-by-fold analysis (103 folds)\n")
    s = t1["auc_summary"]
    w("| Metric | n | mean | median | std | min | max |")
    w("|--------|---|------|--------|-----|-----|-----|")
    for key, label in [("auc_summary", "AUC"), ("pr_auc_summary", "PR-AUC"),
                       ("brier_summary", "Brier"), ("ece_summary", "ECE"),
                       ("expected_r_summary", "Expected R (th=0.50)"),
                       ("trade_count_summary", "Trade count (th=0.50)"),
                       ("positive_rate_summary", "Positive rate")]:
        v = t1[key]
        w(f"| {label} | {v['n']} | {_r(v['mean'])} | {_r(v['median'])} | "
          f"{_r(v['std'])} | {_r(v['min'])} | {_r(v['max'])} |")
    w(f"\n- % folds AUC > 0.50: **{_r(t1['pct_folds_auc_gt_0.50'])}**")
    w(f"- % folds AUC > 0.55: **{_r(t1['pct_folds_auc_gt_0.55'])}**")
    w(f"- % folds with positive expected R: **{_r(t8['fold_stability']['pct_folds_positive_er'])}**\n")
    w("**Observation:** Mean fold AUC 0.554 is only marginally above 0.50, with a very high "
      "standard deviation (0.177) and a range of 0.124–0.987. The median expected R per fold "
      f"is {_r(t1['expected_r_summary']['median'])} — half the folds produce zero or negative "
      "per-trade expectancy at the 0.50 threshold. Discrimination is weak and fold-dependent.\n")

    # ---- TASK 2 ----
    w("## Task 2 — Feature importance stability\n")
    w(f"- SHAP available: **{t2['shap_available']}**")
    w(f"- Redundant feature pairs (|corr| > 0.85): **{t2['n_redundant']}** (no automatic deletion)\n")
    w("**Top 12 features (by gain) with all importance views + stability:**\n")
    w("| Feature | Gain | Gain rank | Permutation | Perm rank | SHAP | SHAP rank | Rank stability | % folds top-10 | Redundant |")
    w("|---------|------|------------|-------------|-----------|------|-----------|-----------------|----------------|------------|")
    for r in t2["features"][:12]:
        w(f"| {r['feature']} | {_r(r['global_gain'],1)} | {r['gain_rank']} | "
          f"{_r(r['permutation_importance'])} | {r['permutation_rank']} | "
          f"{_r(r['shap_importance'])} | {r['shap_rank'] or '-'} | "
          f"{_r(r['rank_stability'],3)} | {_r(r['pct_folds_top10'],2)} | {r['redundant']} |")
    w("\n**Redundant pairs:**\n")
    for p in t2["redundant_pairs"]:
        w(f"- `{p['a']}` ↔ `{p['b']}` (corr = {p['corr']})")
    w("\n**Top-10 by method:**")
    w(f"- Gain: {', '.join(t2['top10_by_gain'])}")
    w(f"- SHAP: {', '.join(t2['top10_by_shap'])}")
    w(f"- Permutation: {', '.join(t2['top10_by_permutation'])}\n")
    w("**Key finding:** Gain/SHAP importance is high and stable across folds for the top "
      "features (rank stability > 0.95, % folds in top-10 up to 1.00). **However, permutation "
      "importance is near-zero and frequently negative** for the highest-gain features "
      "(`distance_to_entry_atr` perm = -0.031, `atr` = -0.0085). This is the most important "
      "diagnostic in the audit: the model relies on features whose contribution does not "
      "generalize when shuffled — a hallmark of split-fitting rather than a learnable structural "
      "relationship. Five redundant pairs exist (two at corr = 1.0), indicating the contract "
      "carries duplicate information that the tree can arbitrarily split across.\n")

    # ---- TASK 3 ----
    w("## Task 3 — Regime analysis\n")
    w("All regime labels use only information available before each setup (HTF regime, ATR "
      "percentile, PD position, session enc — all confirmed at or before entry).\n")
    for cat, title in [("trend", "Trend"), ("volatility", "Volatility"), ("session", "Session")]:
        w(f"\n**{title}**\n")
        w("| Regime | n | positive rate | AUC | PR-AUC | Brier | ECE | Exp R | Win rate | Trades |")
        w("|--------|---|---------------|-----|--------|-------|-----|-------|----------|--------|")
        for g, b in t3[cat].items():
            w(f"| {g} | {b['n']} | {_r(b['positive_rate'],3)} | {_r(b['auc'])} | "
              f"{_r(b['pr_auc'])} | {_r(b['brier'])} | {_r(b['ece'])} | "
              f"{_r(b['expected_r_0.50'])} | {_r(b['win_rate_0.50'])} | {b['trade_count_0.50']} |")
    w("\n**Observation:** AUC is flat across regimes (0.53–0.56), but expectancy diverges: "
      "Asian session is **negative (-0.169 R)**; NY (+0.356) and London/NY overlap (+0.302) "
      "are the only strongly positive sessions. Bearish-trend expectancy is slightly negative "
      "(-0.095). The edge, where it exists, is concentrated in liquid western sessions and "
      "higher-volatility conditions — not a broad, regime-robust signal.\n")

    # ---- TASK 4 ----
    w("## Task 4 — Direction analysis\n")
    w("| Direction | n | positive rate | AUC | PR-AUC | Brier | ECE | Expectancy R | Win rate | Trades |")
    w("|-----------|---|---------------|-----|--------|-------|-----|--------------|----------|--------|")
    for g, b in t4.items():
        w(f"| {g} | {b['n']} | {_r(b['positive_rate'],3)} | {_r(b['auc'])} | "
          f"{_r(b['pr_auc'])} | {_r(b['brier'])} | {_r(b['ece'])} | "
          f"{_r(b['expectancy_R'])} | {_r(b['win_rate'])} | {b['trade_count']} |")
    w("\n**Observation:** Bearish setups (n=500, 12% of data) are essentially unlearnable: "
      "AUC 0.510 (random) and **negative expectancy (-0.106 R)**. The model's entire positive "
      "expectancy comes from bullish setups (AUC 0.547, +0.214 R). This is the bullish gold "
      "uptrend bias surfacing — the model has not learned a bearish edge, it has learned that "
      "bullish setups during an uptrend tend to resolve TP.\n")

    # ---- TASK 5 ----
    w("## Task 5 — Baseline comparison (same setups, same labels)\n")
    w("| Variant | Expectancy R | Profit factor | Win rate | Trades | Max DD R | AUC |")
    w("|---------|--------------|---------------|----------|--------|----------|-----|")
    for k, label in [("A_no_ml", "A. SMC setups (no ML)"),
                     ("B_v38_ml_0.50", "B. V38 ML @ 0.50"),
                     ("B_v38_ml_0.60", "B. V38 ML @ 0.60"),
                     ("C_shuffled_0.50", "C. Shuffled scores @ 0.50")]:
        b = t5[k]
        w(f"| {label} | {_r(b['expectancy_R'])} | {_r(b['profit_factor'],3)} | "
          f"{_r(b['win_rate'])} | {b['trade_count']} | {_r(b['max_drawdown_R'])} | "
          f"{_r(b['auc'])} |")
    w(f"\n**R-distribution (V38 ML @ 0.50):** mean {_r(t5['B_v38_ml_0.50']['r_distribution']['mean'])}, "
      f"median {_r(t5['B_v38_ml_0.50']['r_distribution']['median'])}, "
      f"std {_r(t5['B_v38_ml_0.50']['r_distribution']['std'])}, "
      f"p10 {_r(t5['B_v38_ml_0.50']['r_distribution']['p10'])}, "
      f"p90 {_r(t5['B_v38_ml_0.50']['r_distribution']['p90'])}\n")
    w("**Observation:** ML does add value over the raw SMC candidate stream "
      f"(+{_r(t5['B_v38_ml_0.50']['expectancy_R'])} R vs +{_r(t5['A_no_ml']['expectancy_R'])} R "
      f"for no-ML vs +{_r(t5['C_shuffled_0.50']['expectancy_R'])} R for shuffled). The shuffled "
      "baseline (+0.055 R) is itself positive because the underlying SMC setups are slightly "
      "tilted favorable and TP:SL = 2:1. The ML layer roughly triples expectancy, but the "
      "absolute edge is small and — per Tasks 1, 2, 6 — not reliably attributable to "
      "generalizable feature signal.\n")

    # ---- TASK 6 ----
    w("## Task 6 — Threshold robustness (pre-specified thresholds)\n")
    w("No threshold was selected from this data as 'best'; all thresholds were pre-specified.\n")
    w("| Threshold | Expectancy R | Win rate | Trades | Profit factor | Max DD R | Selected positive rate |")
    w("|-----------|--------------|----------|--------|----------------|----------|------------------------|")
    for r in t6["thresholds"]:
        w(f"| {r['threshold']} | {_r(r['expectancy_R'])} | {_r(r['win_rate'])} | "
          f"{r['trade_count']} | {_r(r['profit_factor'],3)} | {_r(r['max_drawdown_R'])} | "
          f"{_r(r['positive_rate_selected'],3)} |")
    w("\n**Observation — failed robustness:** Expectancy is **monotone-decreasing** as the "
      "threshold rises (0.165 → 0.143 → ... → -0.032 at 0.90), and the win rate of selected "
      "trades **falls** with higher confidence (0.388 at 0.50 → 0.323 at 0.90). A well-"
      "discriminating model should show the opposite: higher-confidence predictions should be "
      "more accurate. Here the model's most-confident calls are its worst. This is strong "
      "evidence that the raw probability ranking is unreliable at the top of the distribution "
      "and that the modest OOF AUC does not translate into a usable confidence gradient.\n")

    # ---- TASK 7 ----
    w("## Task 7 — Calibration audit (calibration kept separate from discrimination)\n")
    w("| Method | AUC (discrimination) | Brier | ECE | Log-loss |")
    w("|--------|----------------------|-------|-----|----------|")
    for k, label in [("raw", "Raw LightGBM"), ("platt", "Platt (sigmoid)"),
                     ("isotonic", "Isotonic")]:
        c = t7[k]
        w(f"| {label} | {_r(c['auc'])} | {_r(c['brier'])} | {_r(c['ece'])} | {_r(c['log_loss'])} |")
    w("\n**Reliability bins (isotonic):**\n")
    w("| Bin | Count | Frac | Mean pred | Mean actual |")
    w("|-----|-------|------|-----------|-------------|")
    for rb in t7["isotonic"]["reliability"]:
        w(f"| [{rb['bin_lo']}-{rb['bin_hi']}) | {rb['count']} | {_r(rb['frac'])} | "
          f"{_r(rb['mean_pred'])} | {_r(rb['mean_actual'])} |")
    w("\n**Observation:** Calibration improves Brier (0.277 → 0.227) and ECE (0.186 → 0.0) "
      "without changing AUC (discrimination is rank-preserving). **Important caveat:** the "
      "isotonic ECE of 0.0 is computed on the same OOF data the calibrator was fit on — it is "
      "an in-sample fit statistic, not a generalization measure. Calibration corrects the "
      "probability *values* so they match empirical frequencies; it does **not** improve the "
      "model's ability to separate winners from losers. The weak AUC (0.542) is unchanged by "
      "calibration, confirming calibration ≠ predictive power.\n")

    # ---- TASK 8 ----
    w("## Task 8 — Overfitting audit\n")
    fs = t8["fold_stability"]
    w(f"- **Fold stability:** AUC mean {_r(fs['auc_mean'])}, std {_r(fs['auc_std'])} "
      f"(min {_r(fs['auc_min'])}, max {_r(fs['auc_max'])}). {fs['pct_folds_auc_gt_0.50']*100:.1f}% "
      f"of folds beat 0.50; only {fs['pct_folds_positive_er']*100:.1f}% have positive expectancy.")
    w(f"- **Regime stability:** trend AUC spread "
      f"{_r(t8['regime_stability']['trend_auc_spread'])} (bull {_r(t3['trend']['bullish_trend']['auc'])} / "
      f"bear {_r(t3['trend']['bearish_trend']['auc'])} / range {_r(t3['trend']['ranging']['auc'])}); "
      f"volatility spread {_r(max(t3['volatility']['high_vol']['auc'],t3['volatility']['low_vol']['auc'],t3['volatility']['mid_vol']['auc'])-min(t3['volatility']['high_vol']['auc'],t3['volatility']['low_vol']['auc'],t3['volatility']['mid_vol']['auc']))}; "
      f"session AUCs range {_r(min(t3['session']['asian']['auc'], t3['session']['london']['auc'], t3['session']['overlap']['auc'], t3['session']['ny']['auc']))}–"
      f"{_r(max(t3['session']['asian']['auc'], t3['session']['london']['auc'], t3['session']['overlap']['auc'], t3['session']['ny']['auc']))}.")
    w(f"- **Direction stability:** AUC spread {_r(t8['direction_stability']['spread'])} "
      f"(bullish {_r(t4['bullish']['auc'])} vs bearish {_r(t4['bearish']['auc'])}). "
      "Bearish is at random.")
    w(f"- **Feature stability:** top-10 features appear in the top-10 of "
      f"{_r(t8['feature_stability']['top10_mean_pct_folds_in_top10'],2)} of folds on average; "
      f"{t8['feature_stability']['n_features_top10_stable_50pct']} of 10 are stable in ≥50% of folds. "
      "Gain ranks are stable — but permutation importance is near-zero/negative, so stable "
      "*ranking* of non-generalizing features is not evidence of a real edge.")
    w(f"- **Threshold stability:** expectancy is NOT positive at all thresholds "
      f"(fails at 0.90; range {_r(t8['threshold_stability']['expectancy_min'])} to "
      f"{_r(t8['threshold_stability']['expectancy_max'])}). Trade count collapses from "
      f"{t8['threshold_stability']['trade_count_at_0.50']} at 0.50 to "
      f"{t8['threshold_stability']['trade_count_at_0.90']} at 0.90 without improving quality.\n")
    w(f"**Overall classification: `{t8['overall']}`.** The ~0.542 OOF AUC is not consistently "
      "weak-but-real. It is the average of a high-variance fold distribution where barely half "
      "the folds are positive, the most-confident predictions are the worst, the bearish class "
      "is unlearnable, and the top features show negative permutation importance. This pattern "
      "is more consistent with a small-sample artifact than a stable generalizable edge.\n")

    # ---- TASK 9 ----
    w("## Task 9 — Data integrity (no fabrication)\n")
    w(f"- Rule: {t9['rule']}")
    w(f"- Current: {t9['current']['n_setups']} setups, "
      f"{t9['current']['period']}, timeframes {t9['current']['timeframes']}")
    w(f"- What would materially help: {t9['what_would_materially_help']}\n")

    # ---- TASK 10 ----
    w("## Task 10 — Final verdict\n")
    v = t10["verdict"]
    w(f"### **Verdict: {v} — {t10['options'][v]}**\n")
    w(f"- ML adds value over SMC-only: **{t10['ml_adds_value_over_smc']}** "
      f"(ML {_r(t10['ml_expectancy_R'])} R vs SMC-only {_r(t10['smc_only_expectancy_R'])} R "
      f"vs shuffled {_r(t10['shuffled_expectancy_R'])} R)")
    w(f"- Edge classification: **{t10['edge_classification']}**")
    w(f"- Proceed to MT5 validation: **{t10['proceed_to_mt5_validation']}**\n")
    w("**Reasoning:** ML does extract a small positive expectancy from the SMC candidate stream "
      "(+0.165 R vs +0.065 R unfiltered), so the approach is not without signal. However the "
      "audit establishes that this signal is **not stable enough to validate**:")
    w("1. Fold AUC is high-variance (std 0.177) and only 57% of folds beat random.")
    w("2. Permutation importance is near-zero/negative for the top-gain features — the model "
      "is not learning generalizable structure from its most-used inputs.")
    w("3. Threshold robustness fails: higher confidence yields *worse* win rates, the opposite "
      "of a discriminative model.")
    w("4. The bearish class (12% of data) is at random and negative expectancy.")
    w("5. The positive expectancy is concentrated in NY/overlap sessions and bullish setups — "
      "largely a reflection of the gold uptrend, not an SMC edge the model has learned.")
    w("6. Isotonic ECE=0 is an in-sample fit artifact, not generalization.\n")
    w("The binding constraint is data: 4,496 genuine H1/H4 setups (only 500 bearish) cannot "
      "support a stable 56-feature tree ensemble. Increasing genuine data — specifically M5/M15 "
      "over the same window — is the prerequisite before any feature redesign or retrain would "
      "be interpretable. The current model should be retained as a documented baseline only; it "
      "should not be deployed to live MT5 validation as a trading filter.\n")
    for c in t10["caveats"]:
        w(f"- {c}")

    out = ARTIFACT_DIR / "v38_robustness_report.md"
    out.write_text("\n".join(L) + "\n")
    print("wrote", out)
    return out


if __name__ == "__main__":
    render()
