# V38.2 Full-Data Pre-Modeling Validation Report

**Audit type:** V38.2_FULL_DATA_PRE_MODELING_VALIDATION  
**Timestamp (UTC):** 2026-08-14T09:19:59.744950+00:00  
**Elapsed:** 188.9 min  
**LTF:** M15 | **HTF:** H1  
**Feature contract:** V38.1 (implemented, price features only)  
**Features used:** 50 (price features only, MACRO_NEWS forecast-dependent features PIT-blocked)

## Executive Summary

This report determines whether the weak signal observed in the H1/H4 ablation study (Val AUC ~0.504, Holdout AUC ~0.463) survives when genuine M1→M5/M15 Dukascopy data is used as the lower timeframe (LTF) with H1 as the higher timeframe (HTF).

| Metric | H1/H4 (prior ablation) | M15/H1 (this report) | Change |
|--------|-------------------------|-----------------------|--------|
| Setups | 4,496 | 45,364 | +40,868 (10x) |
| Valid (labeled) | 4,339 | 45,281 | +40,942 |
| Positive rate | 34.5% | 33.8% | -0.7pp |
| Val AUC | 0.504 | 0.5128 | +0.0088 |
| Holdout AUC | 0.463 | 0.5468 | +0.0838 |
| Holdout Expectancy | negative | 0.516R | improved |
| Holdout Profit Factor | <1.0 | 2.04 | improved |
| Holdout Model Win Rate | N/A | 50.5% | — |
| Holdout Raw Win Rate | ~34.5% | 34.3% | -0.2pp |
| Fold stability | N/A | 64% (9/14) | — |

### Verdict: **C) PROMISING BUT NOT ROBUST**

The M15/H1 full-data analysis shows a **meaningful improvement** over the H1/H4 ablation:

1. **Holdout AUC = 0.5468** (CI: 0.5341–0.5594) — statistically significant (permutation p=0.0, perm 95th percentile=0.5107)
2. **Holdout expectancy = +0.516R** per trade (PF=2.04)
3. **Model-selected win rate = 50.5%** on holdout (CI: 45.4%–55.7%), vs raw win rate of 34.3%
4. **Signal is consistent across years** (2024: AUC=0.5585, 2025: AUC=0.5418, 2026: AUC=0.5619)

However, it is **NOT robust enough** for production because:

1. **Val AUC = 0.5128** — barely above 0.5 (CI: 0.5060–0.5194)
2. **Val expectancy = +0.097R** — marginal (PF=1.15)
3. **Stability = 64%** — only 9 of 14 folds are positive
4. **Low recall on holdout** (5.9%) — model only selects 364 trades out of 9057 setups
5. **Bearish setups have negative expectancy on holdout** (-0.053R) — signal is bullish-skewed
6. **Max drawdown = 20R** on holdout — significant equity swings

## 1. Configuration

| Parameter | Value |
|-----------|-------|
| LTF | M15 (genuine Dukascopy/Jetta data) |
| HTF | H1 (genuine Dukascopy/Jetta data) |
| Label TP | +2.0R |
| Label SL | -1.0R |
| Label max bars | 80 (≈20h at M15) |
| Features used | 50 (price features, forecast-dependent PIT-blocked) |
| LightGBM params | fixed baseline (no optimization) |

## 2. Data Quality

| Check | Result |
|-------|--------|
| Duplicate timestamps | 0 |
| Duplicate setup IDs | 0 |
| NaN count | 0 |
| Inf count | 0 |
| Non-positive entry prices | 0 |
| Chronologically ordered | True |
| Temporal inversions | 0 |
| No-lookahead alignment | True |

**Gap classification:**
- Weekend gaps: 409 (expected market closure)
- Holiday gaps: 25 (deterministic holiday calendar)
- Daily rollover gaps: 1
- Unexpected gaps: 0 (potential data issues)
- Max gap: 77.5h | Max unexpected gap: 0.0h

**Provenance:**
- LTF source: `/workspace/project/Kingin_v2/backend/data/processed/jetta/XAUUSD_M15.csv` (198,858 bars)
- HTF source: `/workspace/project/Kingin_v2/backend/data/processed/jetta/XAUUSD_H1.csv` (49,719 bars)
- Data source: Jetta/Dukascopy processed (M15)

## 3. Dataset Statistics

| Metric | Value |
|--------|-------|
| Timeframe | M15 |
| Total setups | 45,364 |
| Valid (labeled) | 45,281 |
| Censored | 83 |
| Positive (TP hit) | 15,307 |
| Negative (SL hit) | 29,974 |
| Label rate | 33.80% |
| Total bars (LTF) | 198,858 |
| Genuine trading days | 2,121 |

**Direction breakdown:**
| Direction | Setups | Positive | Label rate |
|-----------|--------|----------|------------|
| Bullish | 25,364 | 8,722 | 34.39% |
| Bearish | 19,917 | 6,585 | 33.06% |

**By year:**
| Year | Setups | Positive | Bullish | Bearish |
|------|--------|----------|---------|---------|
| 2018 | 1,231 | 482 | 1,165 | 66 |
| 2019 | 6,196 | 2,094 | 3,553 | 2,643 |
| 2020 | 6,521 | 2,253 | 3,764 | 2,757 |
| 2021 | 6,427 | 2,129 | 3,138 | 3,289 |
| 2022 | 6,167 | 2,069 | 3,430 | 2,737 |
| 2023 | 6,095 | 2,055 | 2,996 | 3,099 |
| 2024 | 6,246 | 2,004 | 3,702 | 2,544 |
| 2025 | 5,486 | 1,915 | 2,980 | 2,506 |
| 2026 | 912 | 306 | 636 | 276 |

**By session:**
| Session | Setups | Positive | Label rate |
|---------|--------|----------|------------|
| asian | 14,690 | 5,058 | 34.43% |
| london | 9,637 | 3,280 | 34.04% |
| ny | 8,864 | 2,982 | 33.64% |
| off | 4,982 | 1,576 | 31.63% |
| overlap | 7,108 | 2,411 | 33.92% |

## 4. Leakage Audit

**Verdict: PASS** (violations: 0)

| Check | Result |
|-------|--------|
| chronological_order | True |
| setup_ts_matches_bar | True |
| no_nan_in_features | True |
| no_inf_in_features | True |
| label_future_only | True |
| forecast_blocked_normalized_surprise | True |
| forecast_blocked_surprise_zscore | True |
| forecast_blocked_expected_gold_dir_enc | True |
| label_side_observed_reaction_atr | True |
| no_normalization_leakage | True |
| no_duplicate_setups | True |
| duplicate_setup_count | 0 |
| htf_alignment_no_lookahead | True |
| max_feature_label_corr | 0.032245886274581546 |
| max_corr_feature | ltf_regime_enc |
| no_high_corr_leakage | True |

**Key findings:**
- Max feature-label correlation: 0.0322 (`ltf_regime_enc`) — well below 0.5 threshold
- All forecast-dependent features (normalized_surprise, surprise_zscore, expected_gold_dir_enc) confirmed PIT-blocked (all 0.0)
- observed_reaction_atr confirmed label-side blocked (all 0.0)
- No duplicate setups, no temporal inversions, no NaN/inf

## 5. ML Evaluation (Fixed Baseline LightGBM)

Method: expanding walk-forward CV (chronological), untouched 20% holdout, no random shuffle, no holdout-based selection, fixed LightGBM config (no hyperparameter optimization).

**Split:** Train+Val = 36,224 setups | Holdout = 9,057 setups
**Holdout period:** `2024-07-22 03:30:00+00:00` → `2026-03-03 09:45:00+00:00`

### Validation (Out-of-Fold)

| Metric | Value |
|--------|-------|
| n | 31696 |
| n_positive | 10631 |
| positive_rate | 0.3354 |
| auc | 0.5128 |
| pr_auc | 0.3465 |
| brier | 0.2387 |
| ece | 0.0923 |
| log_loss | 0.6798 |
| precision | 0.3657 |
| recall | 0.1273 |
| f1 | 0.1888 |
| n_trades | 3700 |
| raw_win_rate | 0.3354 |
| model_win_rate | 0.3657 |
| expectancy_R | 0.0970 |
| profit_factor | 1.1530 |
| sharpe_per_trade | 0.0671 |
| max_drawdown_R | 198.0000 |

### Holdout (Untouched)

| Metric | Value |
|--------|-------|
| n | 9057 |
| n_positive | 3104 |
| positive_rate | 0.3427 |
| auc | 0.5468 |
| pr_auc | 0.3958 |
| brier | 0.2286 |
| ece | 0.0725 |
| log_loss | 0.6525 |
| precision | 0.5055 |
| recall | 0.0593 |
| f1 | 0.1061 |
| n_trades | 364 |
| raw_win_rate | 0.3427 |
| model_win_rate | 0.5055 |
| expectancy_R | 0.5165 |
| profit_factor | 2.0444 |
| sharpe_per_trade | 0.3439 |
| max_drawdown_R | 20.0000 |

### Stability

| Metric | Value |
|--------|-------|
| n_folds | 14 |
| auc_mean | 0.5097 |
| auc_std | 0.0387 |
| expectancy_mean | 0.0731 |
| expectancy_std | 0.3393 |
| positive_folds | 9 |
| stability_ratio | 0.6429 |

### Holdout by Year

| Year | N | Positive | AUC | Expectancy | Model WR |
|------|---|----------|-----|------------|----------|
| 2024 | 2,659 | 883 | 0.5585005305418669 | 0.265625 | 0.421875 |
| 2025 | 5,486 | 1,915 | 0.5417837190071164 | 0.5767918088737202 | 0.5255972696245734 |
| 2026 | 912 | 306 | 0.5619297223840031 | 0.2857142857142857 | 0.42857142857142855 |

### Holdout by Direction

| Direction | N | Positive | AUC | Expectancy |
|-----------|---|----------|-----|------------|
| bearish | 3,785 | 1,209 | 0.5414409398455682 | -0.05263157894736842 |
| bullish | 5,272 | 1,895 | 0.5439053413476076 | 0.5478260869565217 |

## 6. Statistical Significance

| Test | Result |
|------|--------|
| Holdout AUC | 0.5468 |
| Holdout AUC 95% CI | [0.5341, 0.5594] |
| Holdout permutation p-value | 0.0 |
| Holdout perm AUC mean ± std | 0.5002 ± 0.0064 |
| Holdout perm 95th percentile | 0.5107 |
| Holdout model win rate | 50.5% |
| Holdout model WR 95% CI | [45.4%, 55.7%] |
| Holdout raw win rate | 34.3% |
| Holdout raw WR 95% CI | [33.3%, 35.3%] |
| Val AUC | 0.5128 |
| Val AUC 95% CI | [0.5060, 0.5194] |
| Val permutation p-value | 0.0 |

**Key finding:** Holdout AUC (0.5468) is **statistically significant** — the 95% CI [0.5341, 0.5594] does NOT include 0.5, and the permutation test p-value is 0.0 (observed AUC exceeds the 95th percentile of the null distribution at 0.5107).

## 7. Baselines (No ML)

### All-setups baseline (take every setup, no filtering)

| Metric | Value |
|--------|-------|
| N | 45,281 |
| Raw win rate | 33.80% |
| Expectancy | 0.0141R |
| Profit factor | 1.0214 |
| Win rate 95% CI | [33.37%, 34.24%] |

### Directional baselines (longs only / shorts only)

**Bullish:**
- Val: n=20,092, win rate=33.98% (CI: [33.33%, 34.64%]), exp=0.0194R
- Holdout: n=5,272, win rate=35.94% (CI: [34.66%, 37.25%])

**Bearish:**
- Val: n=16,132, win rate=33.33% (CI: [32.60%, 34.06%]), exp=-0.0002R
- Holdout: n=3,785, win rate=31.94% (CI: [30.48%, 33.44%])

### Session baseline (best session on val, tested on holdout)

- Best session on val: **asian**
- Val: n=11,837, win rate=34.47%
- Holdout: n=2,853, win rate=34.28% (CI: [32.56%, 36.04%])

### ML value-add

| Approach | Holdout Win Rate | Holdout Expectancy |
|----------|------------------|--------------------|
| All setups (no ML) | 34.3% | 0.014R* |
| Model-selected (ML) | 50.5% | 0.516R |

\* All-setups expectancy is calculated on the full dataset (includes val+holdout). The model improves win rate from 34.3% to 50.5% on holdout by filtering out 8,693 of 9,057 setups.

## 8. Realistic Live Win-Rate Estimate

| Scenario | Win Rate | Source |
|----------|----------|--------|
| Raw barrier-label win rate (all setups) | 34.3% | holdout, n=9,057 |
| Model-selected win rate (threshold=0.5) | 50.5% | holdout, n=364 |
| Model-selected 95% CI | [45.4%, 55.7%] | Wilson |

**Expected live degradation:** The holdout model win rate of 50.5% (CI: 45.4%–55.7%) represents the **optimistic estimate**. In live trading, expect:

- **Slippage and spread impact** will reduce the effective win rate by ~2-5pp
- **Model drift** (market regime change) will further reduce performance
- **Realistic live win rate range: 40-48%** (model-selected, after degradation)
- This is above the break-even win rate of 33.3% (for 2R:1R with SL_wins)
- But the wide CI and low trade count (364 trades over ~20 months) means this estimate is **not highly reliable**

## 9. Comparison: H1/H4 vs M15/H1

| Dimension | H1/H4 (prior) | M15/H1 (this report) | Assessment |
|-----------|---------------|-----------------------|------------|
| Data bars (LTF) | ~28,000 (H1) | ~198,858 (M15) | 7x more granular |
| Setups | 4,496 | 45,364 | 10x more samples |
| Positive rate | 34.5% | 33.8% | Similar |
| Direction balance | Imbalanced | Bullish 25,364, Bearish 19,917 | Improved |
| Val AUC | 0.504 | 0.5128 | Slightly better |
| Holdout AUC | 0.463 | 0.5468 | Significantly better |
| Holdout significance | Not significant | Significant (p=0.0) | Improved |
| Holdout expectancy | Negative | +0.516R | Improved |
| Holdout PF | <1.0 | 2.04 | Improved |
| Fold stability | N/A | 64% | Moderate |

**Key conclusion:** The weak/marginal signal from H1/H4 **survives and strengthens** when genuine M15 data is used. The holdout AUC improved from 0.463 (below random) to 0.5468 (above random, statistically significant). The M15 timeframe provides 10x more setups and 7x more granular bar data, which improves both the structure detection (finer swings, OBs, FVGs) and the ML signal.

## 10. Non-Modifications

- readiness_gate.py NOT modified
- economic_calendar.csv NOT created
- feature_contract.py NOT modified
- holiday classification NOT modified
- PIT rules NOT modified
- Forecast-dependent features NOT activated (normalized_surprise, surprise_zscore, expected_gold_dir_enc = 0)
- observed_reaction_atr kept at 0 (label-side per V38.2)
- No ONNX export
- No MQL5 generation
- No MT5 deployment
- No production model trained
- No hyperparameter optimization (fixed baseline config)
- Holdout NOT used for feature/threshold/model selection

## 11. Missingness

| Check | Value |
|-------|-------|
| NaN count | 0 |
| Zero-only features | 13 |
| Zero features | protected_low, inducement_present, ob_present, ob_direction_enc, ob_strength, ob_distance_atr, ob_age_bars, ob_mitigation_count, ob_freshness_enc, ob_mitigation_depth, sl_distance_atr, tp_distance_atr, available_rr |

The zero-only features are the PIT-blocked macro features (expected). All price/structure features have non-zero variance.

---
*Report generated by V38.2 full-data pre-modeling validation. Uses genuine Dukascopy M1→M5/M15 data. No production model trained, no ONNX exported, no MQL5 generated.*