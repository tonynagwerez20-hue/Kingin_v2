# V38.2 Controlled Ablation / Pre-Modeling Results

**Generated:** 2026-08-14T01:47:19.826076+00:00
**Elapsed:** 282.7s
**Feature contract:** V38.1 (implemented) (56 implemented features, 9 families)
**Model:** LightGBM (fixed baseline config, no hyperparameter optimization)
**Label:** Barrier method — TP=+2.0R, SL=-1.0R, max 20 bars, SL_wins tie-break

## 1. Non-Modifications

- readiness_gate.py NOT modified
- economic_calendar.csv NOT created
- Forecast-dependent features NOT activated (normalized_surprise, surprise_zscore, expected_gold_dir_enc = 0)
- observed_reaction_atr kept at 0 (label-side per V38.2)
- No ONNX export
- No MQL5 generation
- No MT5 deployment
- No production model trained
- No hyperparameter optimization (fixed baseline config)
- Holdout NOT used for feature/threshold/model selection

## 2. Dataset Summary

| Metric | Value |
|---|---|
| Total setups | 4,496 |
| Positive (TP reached) | 1,498 |
| Negative (SL reached) | 2,841 |
| Censored | 157 |
| Date range | 2018-11-18 00:00:00+00:00 to 2026-03-03 09:00:00+00:00 |
| Timeframe | H1 (LTF) + H4 (HTF) |
| Class balance | 34.5% positive |
| Calendar loaded (macro-safe) | True |
| Surprises computed | False (forecast-dependent features stay 0) |
| Forecasts activated | False |

## 3. Ablation Results Table

| Experiment | Features | Setup Count | Win Rate | ROC-AUC | PR-AUC | Expectancy | PF | Max DD | Stability |
|---|---|---|---|---|---|---|---|---|---|
| CORE-50 | 50 | 4,496 | 31.8% | 0.5041 | 0.3550 | -0.0467R | 0.932 | 52.0R | 53.8% |
| CORE-50 minus STRUCTURE | 38 | 4,496 | 39.2% | 0.4946 | 0.3673 | 0.1759R | 1.289 | 36.0R | 69.2% |
| CORE-50 minus LIQUIDITY | 43 | 4,496 | 34.9% | 0.5066 | 0.3654 | 0.0484R | 1.074 | 56.0R | 38.5% |
| CORE-50 minus ORDER_BLOCK | 42 | 4,496 | 31.8% | 0.5041 | 0.3550 | -0.0467R | 0.932 | 52.0R | 53.8% |
| CORE-50 minus FVG | 44 | 4,496 | 34.0% | 0.4939 | 0.3495 | 0.0187R | 1.028 | 59.0R | 53.8% |
| CORE-50 minus PREMIUM_DISCOUNT | 46 | 4,496 | 35.2% | 0.5021 | 0.3545 | 0.0550R | 1.085 | 46.0R | 53.8% |
| CORE-50 minus MARKET_REGIME | 45 | 4,496 | 34.2% | 0.5127 | 0.3619 | 0.0251R | 1.038 | 50.0R | 30.8% |
| CORE-50 minus SESSION | 48 | 4,496 | 28.8% | 0.4984 | 0.3479 | -0.1353R | 0.810 | 70.0R | 46.2% |
| CORE-50 minus SETUP_GEOMETRY | 44 | 4,496 | 34.5% | 0.5090 | 0.3567 | 0.0350R | 1.053 | 63.0R | 46.2% |
| CORE-50 + PIT-safe macro | 52 | 4,496 | 31.3% | 0.4992 | 0.3511 | -0.0619R | 0.910 | 52.0R | 46.2% |

### Holdout (Unseen 20%) Results

| Experiment | Setup Count | Win Rate | ROC-AUC | PR-AUC | Expectancy | PF | Max DD |
|---|---|---|---|---|---|---|---|
| CORE-50 | 868 | 32.1% | 0.4631 | 0.3482 | -0.0380R | 0.944 | 54.0R |
| CORE-50 minus STRUCTURE | 868 | 35.7% | 0.4832 | 0.3550 | 0.0714R | 1.111 | 41.0R |
| CORE-50 minus LIQUIDITY | 868 | 31.4% | 0.4439 | 0.3341 | -0.0580R | 0.915 | 69.0R |
| CORE-50 minus ORDER_BLOCK | 868 | 32.1% | 0.4631 | 0.3482 | -0.0380R | 0.944 | 54.0R |
| CORE-50 minus FVG | 868 | 31.3% | 0.4921 | 0.3545 | -0.0606R | 0.912 | 63.0R |
| CORE-50 minus PREMIUM_DISCOUNT | 868 | 24.7% | 0.4266 | 0.3128 | -0.2590R | 0.656 | 68.0R |
| CORE-50 minus MARKET_REGIME | 868 | 36.9% | 0.4794 | 0.3690 | 0.1059R | 1.168 | 51.0R |
| CORE-50 minus SESSION | 868 | 37.0% | 0.4551 | 0.3388 | 0.1087R | 1.172 | 45.0R |
| CORE-50 minus SETUP_GEOMETRY | 868 | 33.5% | 0.4630 | 0.3534 | 0.0063R | 1.010 | 36.0R |
| CORE-50 + PIT-safe macro | 868 | 33.5% | 0.4682 | 0.3424 | 0.0055R | 1.008 | 47.0R |

## 4. Validation Metrics (CORE-50)

### Validation (Walk-Forward OOF)

| Metric | Value |
|---|---|
| n | 2808 |
| n_positive | 987 |
| n_negative | 1821 |
| positive_rate | 0.3515 |
| win_rate | 0.3178 |
| precision | 0.3178 |
| recall | 0.1033 |
| f1 | 0.1560 |
| auc | 0.5041 |
| pr_auc | 0.3550 |
| brier | 0.2667 |
| ece | 0.1751 |
| log_loss | 0.7714 |
| n_trades | 321 |
| expectancy_R | -0.0467 |
| profit_factor | 0.9315 |
| max_drawdown_R | 52.0000 |

### By Direction (Validation)

| Direction | N | Win Rate | AUC | Expectancy | PF |
|---|---|---|---|---|---|
| bullish | 2616 | 34.3% | 0.5050 | 0.0303R | 1.046 |
| bearish | 192 | 0.0% | 0.5095 | -1.0000R | 0.000 |

### By Market Regime (Validation)

| Regime | N | Win Rate | AUC | Expectancy | PF |
|---|---|---|---|---|---|
| low | 831 | 31.9% | 0.5320 | -0.0440R | 0.935 |
| mid | 1325 | 31.1% | 0.4762 | -0.0671R | 0.903 |
| high | 652 | 33.3% | 0.5246 | 0.0000R | 1.000 |

### Holdout (Final Unseen 20%)

| Metric | Value |
|---|---|
| n | 868 |
| n_positive | 316 |
| n_negative | 552 |
| positive_rate | 0.3641 |
| win_rate | 0.3207 |
| precision | 0.3207 |
| recall | 0.1867 |
| f1 | 0.2360 |
| auc | 0.4631 |
| pr_auc | 0.3482 |
| brier | 0.2740 |
| ece | 0.1745 |
| log_loss | 0.7704 |
| n_trades | 184 |
| expectancy_R | -0.0380 |
| profit_factor | 0.9440 |
| max_drawdown_R | 54.0000 |
| holdout_start_ts | 2025-07-17 04:00:00+00:00 |
| holdout_end_ts | 2026-03-03 09:00:00+00:00 |

### By Direction (Holdout)

| Direction | N | Win Rate | AUC | Expectancy | PF |
|---|---|---|---|---|---|
| bullish | 573 | 44.4% | 0.5210 | 0.3333R | 1.600 |
| bearish | 295 | 22.3% | 0.3555 | -0.3301R | 0.575 |

### By Market Regime (Holdout)

| Regime | N | Win Rate | AUC | Expectancy | PF |
|---|---|---|---|---|---|
| low | 334 | 21.4% | 0.3227 | -0.3571R | 0.545 |
| mid | 327 | 40.6% | 0.5625 | 0.2188R | 1.368 |
| high | 207 | 54.5% | 0.5482 | 0.6364R | 2.400 |

## 5. Walk-Forward Stability (CORE-50)

| Metric | Value |
|---|---|
| n_folds | 13 |
| auc_mean | 0.5158 |
| auc_std | 0.0948 |
| expectancy_mean | -0.0278 |
| expectancy_std | 0.5368 |
| positive_fold_count | 7 |
| stability_ratio | 0.5385 |

### Per-Fold Details (CORE-50)

| Fold | Train Size | Test Size | AUC | Expectancy | PF |
|---|---|---|---|---|---|
| 1 | 650 | 216 | 0.5895 | 0.4400R | 1.846 |
| 2 | 866 | 216 | 0.6635 | 0.3125R | 1.556 |
| 3 | 1082 | 216 | 0.5296 | -0.5000R | 0.400 |
| 4 | 1298 | 216 | 0.3347 | -0.7209R | 0.205 |
| 5 | 1514 | 216 | 0.4121 | -0.2727R | 0.640 |
| 6 | 1730 | 216 | 0.7147 | 1.0571R | 4.364 |
| 7 | 1946 | 216 | 0.4853 | 0.1250R | 1.200 |
| 8 | 2162 | 216 | 0.5163 | 0.2162R | 1.364 |
| 9 | 2378 | 216 | 0.4828 | -0.4194R | 0.480 |
| 10 | 2594 | 216 | 0.5118 | -0.6250R | 0.286 |
| 11 | 2810 | 216 | 0.5140 | 0.2692R | 1.467 |
| 12 | 3026 | 216 | 0.4536 | -0.7429R | 0.188 |
| 13 | 3242 | 216 | 0.4971 | 0.5000R | 2.000 |

## 6. Missingness Analysis

| Metric | Value |
|---|---|
| NaN count | 0 |
| All-zero features | 13 |
| Constant features | 15 |

**All-zero features (no variance in dataset):**

- `protected_high`
- `protected_low`
- `ob_present`
- `ob_direction_enc`
- `ob_strength`
- `ob_distance_atr`
- `ob_age_bars`
- `ob_mitigation_count`
- `ob_freshness_enc`
- `ob_mitigation_depth`
- `sl_distance_atr`
- `tp_distance_atr`
- `available_rr`

> These features contribute no information. The ORDER_BLOCK family ablation showed identical results to CORE-50, confirming the OB features are all-zero.

## 7. Key Findings

### Signal Detection

- **CORE-50 validation AUC: 0.5041** — close to random (0.5).
- **CORE-50 holdout AUC: 0.4631** — below random.
- **CORE-50 validation expectancy: -0.0467R** — negative.
- **CORE-50 holdout expectancy: -0.0380R** — negative.
- **Walk-forward stability ratio: 53.8%** (7/13 folds with positive expectancy).
- **AUC std across folds: 0.0948** — high variance, unstable.

The 50 implemented price features do NOT contain strong predictive signal with the current H1+H4 data and fixed baseline LightGBM configuration. AUC values hover around 0.50 (random), and expectancies are slightly negative. This is an HONEST result — no overfitting or data leakage was used to inflate metrics.

### Family Contributions

Most family ablations show marginal changes (|ΔAUC| < 0.01), indicating no single family provides strong independent signal. Notable observations:

- **STRUCTURE removal** improved val expectancy (+0.22R) and reduced drawdown (-16R), suggesting structure features may be adding noise rather than signal.
- **ORDER_BLOCK removal** had zero effect — all OB features are zero (no active OBs detected in H1 data with current engine parameters).
- **SESSION removal** worsened val expectancy (-0.09R), suggesting session timing contains a small amount of useful information.
- **MARKET_REGIME removal** slightly improved AUC, suggesting regime features may be slightly noisy at this data resolution.

### PIT-Safe Macro Features

- Added: `event_present` + `event_importance` (from FF+ALFRED calendar, no surprises computed)
- ΔAUC (val): -0.0048 — negligible change
- ΔExpectancy (val): -0.0152R — negligible
- ΔAUC (holdout): 0.0051 — negligible
- ΔExpectancy (holdout): 0.0435R — negligible

The PIT-safe macro features added no measurable value. This is expected: only ~4 of 4,339 setups have a high-impact event within 60 minutes of entry, so the features are almost entirely zero. The features are PIT-safe and correctly blocked from forecast contamination, but they lack coverage density on H1 data.

### Forecast-Dependent Features

- `normalized_surprise`, `surprise_zscore`, `expected_gold_dir_enc` remain **0** (BLOCKED) in all experiments.
- FF forecasts are FORECAST_PIT_UNVERIFIED (0/1264 verified).
- No forecasts were fabricated, inferred, reconstructed, substituted, or current-revised.
- These features are RETAINED in the V38.2 design but NOT activated.

## 8. Status Summary

- **CORE_52_STATUS:** TESTED as CORE-50 (50 implemented price features; 2 EXECUTION_TIMEFRAME features not implemented in V38.1 engine)
- **PIT_SAFE_MACRO_STATUS:** TESTED (event_present + event_importance activated from FF+ALFRED calendar without computing forecast-dependent surprises)
- **FORECAST_MACRO_STATUS:** BLOCKED (normalized_surprise, surprise_zscore, expected_gold_dir_enc remain 0)
- **FULL_59_STATUS:** NOT TESTED (V38.2 skeleton has 59 features; 4 EXECUTION_TIMEFRAME not implemented, 4 forecast-dependent blocked, 1 label-side)
- **READINESS_GATE:** UNCHANGED — BLOCKED (economic_calendar.csv absent)
- **PRODUCTION_MODEL:** NOT AUTHORIZED
