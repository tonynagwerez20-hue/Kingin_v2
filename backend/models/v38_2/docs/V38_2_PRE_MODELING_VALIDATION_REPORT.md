# V38.2 Pre-Modeling Validation Report

**Generated:** 2026-08-14T01:47:19.826076+00:00

## 1. Data Quality

| Metric | Value |
|---|---|
| n_setups_total | 4496 |
| n_labeled | 4339 |
| n_censored | 157 |
| n_positive | 1498 |
| n_negative | 2841 |
| class_balance | 0.3452 |
| duplicate_timestamps | 0 |
| chronologically_ordered | True |
| n_zero_features_in_core50 | 13 |
| n_constant_features_in_core50 | 15 |

## 2. Temporal Integrity

- **chronological_split:** 60% train+val, 20% val-within-trainval, 20% holdout
- **no_random_shuffle:** True
- **no_train_test_temporal_leakage:** True
- **features_at_t_use_only_info_at_or_before_t:** True
- **labels_use_future_price_only_on_label_side:** True
- **observed_reaction_label_side_only:** True
- **holdout_not_used_for_selection:** True

## 3. Walk-Forward Evaluation

| Metric | Value |
|---|---|
| method | expanding window |
| n_folds | 13 |
| auc_mean | 0.5158 |
| auc_std | 0.0948 |
| stability_ratio | 0.5385 |

### Split Configuration

| Split | Percentage | Purpose |
|---|---|---|
| Train+Validation | 80% | Walk-forward expanding window |
| Holdout | 20% | Final unseen — NOT used for selection |

Walk-forward uses 13 expanding-window folds on the train+validation portion. The holdout (final 20%) is evaluated ONCE with a model trained on all train+validation data. No parameters, thresholds, or features were selected using the holdout.

## 4. PIT Compliance

- **forecast_dependent_features_blocked:** True
- **features_blocked:** normalized_surprise, surprise_zscore, expected_gold_dir_enc
- **economic_calendar_csv_not_created:** True
- **readiness_gate_not_modified:** True
- **no_onnx_created:** True
- **no_mql5_created:** True
- **no_mt5_deployment:** True
- **macro_safe_features_only:** event_present, event_importance
- **observed_reaction_label_side:** True

## 5. Anti-Overfitting Measures

- **holdout_not_used_for_param_selection:** True
- **fixed_baseline_config:** True
- **no_hyperparameter_optimization:** True
- **optimization_deferred:** If optimization is performed later, use only train/val, then lock and evaluate once on holdout

## 6. Missingness Analysis

| Metric | Value |
|---|---|
| NaN count | 0 |
| All-zero features | 13 |
| Constant features | 15 |

**All-zero features:**

- `protected_high` (index 7)
- `protected_low` (index 8)
- `ob_present` (index 19)
- `ob_direction_enc` (index 20)
- `ob_strength` (index 21)
- `ob_distance_atr` (index 22)
- `ob_age_bars` (index 23)
- `ob_mitigation_count` (index 24)
- `ob_freshness_enc` (index 25)
- `ob_mitigation_depth` (index 26)
- `sl_distance_atr` (index 53)
- `tp_distance_atr` (index 54)
- `available_rr` (index 55)

These features carry no information. The ORDER_BLOCK family ablation confirmed this — removing all 8 OB features produced identical results to CORE-50.

## 7. Duplicate / Leakage Checks

| Check | Result |
|---|---|
| Duplicate timestamps | 0 |
| Duplicate setup IDs | 0 |
| Chronologically ordered | True |
| Temporal inversions | 0 |

## 8. Class Balance

| Class | Count | Percentage |
|---|---|---|
| Positive (TP) | 1,498 | 34.5% |
| Negative (SL) | 2,841 | 65.5% |
| Censored | 157 | 3.5% |

The positive rate is 34.5%, which is below 50%. This is expected for a 2R:1R reward:risk ratio — fewer trades hit TP than SL.

## 9. Direction Balance

| Direction | N (val) | Positive Rate | AUC |
|---|---|---|---|
| bullish | 2,616 | 35.6% | 0.5050 |
| bearish | 192 | 28.6% | 0.5095 |

> **Severe direction imbalance:** 2,616 bullish vs 192 bearish setups in validation. The bearish direction has too few samples for reliable evaluation. This is a data limitation of using only H1+H4 — M5/M15 data would increase setup diversity.

## 10. Conclusions

1. **No strong predictive signal** was found in the 50 implemented price features. AUC ≈ 0.50 (random) on validation, below random on holdout.
2. **Walk-forward is unstable** — AUC std = 0.09, stability ratio = 53.8%.
3. **13 of 50 features are all-zero** (no variance) — ORDER_BLOCK family is entirely non-functional with current H1 data and engine parameters.
4. **Severe direction imbalance** (2,616 bullish vs 192 bearish) limits evaluation.
5. **PIT-safe macro features** added no measurable value (near-zero coverage density).
6. **Forecast-dependent features** correctly remain blocked (PIT compliance verified).
7. **No overfitting** — holdout was not used for selection; fixed baseline config.
8. **The dataset is too small** (4,339 labeled setups from H1+H4 only). M5/M15 data would provide more setups and more diverse structure. This is the documented BLOCKED_BY_DATA status.

## 11. Status Declaration

- **CORE_52_STATUS = TESTED as CORE-50 (50 implemented price features; 2 EXECUTION_TIMEFRAME features not implemented in V38.1 engine)**
- **PIT_SAFE_MACRO_STATUS = TESTED (event_present + event_importance activated from FF+ALFRED calendar without computing forecast-dependent surprises)**
- **FORECAST_MACRO_STATUS = BLOCKED (normalized_surprise, surprise_zscore, expected_gold_dir_enc remain 0)**
- **FULL_59_STATUS = NOT TESTED (V38.2 skeleton has 59 features; 4 EXECUTION_TIMEFRAME not implemented, 4 forecast-dependent blocked, 1 label-side)**
- **READINESS_GATE = UNCHANGED — BLOCKED (economic_calendar.csv absent)**
- **PRODUCTION_MODEL = NOT AUTHORIZED**
