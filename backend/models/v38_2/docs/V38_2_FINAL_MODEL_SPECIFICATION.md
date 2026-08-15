# V38.2 Final Model Specification

**Created:** 2026-08-12
**Purpose:** Document the exact feature set, label definition, and configuration that produced the M5 validation result (AUC=0.580, PF=2.11, 14/14 fold stability).

---

## 1. Feature Set

### Feature Count
- **Total features in contract:** 56 (defined in `v38/features/contract.py`)
- **Features used for training:** 50 (PRICE_INDICES — all non-MACRO_NEWS family)
- **Features excluded from training:** 6 (MACRO_NEWS family, indices 44-49)

### Feature Ordering (50 training features, exact order)

| Training Index | Contract Index | Feature Name | Family | Range | Encoding |
|---:|---:|---|---|---|---|
| 0 | 0 | `htf_regime_enc` | STRUCTURE | (0, 2) | 0=bearish, 1=neutral, 2=bullish |
| 1 | 1 | `ltf_regime_enc` | STRUCTURE | (0, 2) | 0=bearish, 1=neutral, 2=bullish |
| 2 | 2 | `bos_count_recent` | STRUCTURE | (0, None) | count of BOS events in last 50 |
| 3 | 3 | `choch_count_recent` | STRUCTURE | (0, None) | count of CHOCH events in last 50 |
| 4 | 4 | `last_event_direction_enc` | STRUCTURE | (-1, 1) | -1=bearish, 0=neutral, 1=bullish |
| 5 | 5 | `last_event_disp_atr` | STRUCTURE | (0, None) | ATR multiple of last event displacement |
| 6 | 6 | `last_event_age_bars` | STRUCTURE | (0, None) | bars since last structure event |
| 7 | 7 | `protected_high` | STRUCTURE | (None, None) | protected high (0.0 if absent) |
| 8 | 8 | `protected_low` | STRUCTURE | (None, None) | protected low (0.0 if absent) |
| 9 | 9 | `multi_leg_aligned` | STRUCTURE | (0, 1) | 1.0 if HTF+LTF regime aligned |
| 10 | 10 | `leg_extension_atr` | STRUCTURE | (0, None) | current leg extension in ATR |
| 11 | 11 | `structure_strength` | STRUCTURE | (0, 1) | composite structure quality score |
| 12 | 12 | `nearest_liquidity_dist_atr` | LIQUIDITY | (0, None) | distance to nearest pool in ATR |
| 13 | 13 | `nearest_liquidity_side_enc` | LIQUIDITY | (-1, 1) | -1=below, 0=none, 1=above |
| 14 | 14 | `liquidity_swept` | LIQUIDITY | (0, 1) | 1.0 if liquidity swept recently |
| 15 | 15 | `sweep_depth_atr` | LIQUIDITY | (0, None) | depth of last sweep in ATR |
| 16 | 16 | `post_sweep_reaction_atr` | LIQUIDITY | (0, None) | post-sweep reaction in ATR |
| 17 | 17 | `eqh_eql_present` | LIQUIDITY | (0, 1) | equal highs/lows present |
| 18 | 18 | `inducement_present` | LIQUIDITY | (0, 1) | inducement present |
| 19 | 19 | `ob_present` | ORDER_BLOCK | (0, 1) | 1.0 if valid OB found |
| 20 | 20 | `ob_direction_enc` | ORDER_BLOCK | (-1, 1) | -1=bearish, 0=neutral, 1=bullish |
| 21 | 21 | `ob_strength` | ORDER_BLOCK | (0, 1) | OB quality score |
| 22 | 22 | `ob_distance_atr` | ORDER_BLOCK | (0, None) | distance to OB in ATR |
| 23 | 23 | `ob_age_bars` | ORDER_BLOCK | (0, None) | bars since OB confirmed |
| 24 | 24 | `ob_mitigation_count` | ORDER_BLOCK | (0, None) | mitigation count (0.0 in M5) |
| 25 | 25 | `ob_freshness_enc` | ORDER_BLOCK | (0, 2) | 1=fresh, 2=touched, 3=stale |
| 26 | 26 | `ob_mitigation_depth` | ORDER_BLOCK | (0, 1) | mitigation depth (0.0 in M5) |
| 27 | 27 | `fvg_present` | FVG | (0, 1) | 1.0 if open FVG found |
| 28 | 28 | `fvg_direction_enc` | FVG | (-1, 1) | -1=bearish, 0=neutral, 1=bullish |
| 29 | 29 | `fvg_size_atr` | FVG | (0, None) | FVG size in ATR |
| 30 | 30 | `fvg_age_bars` | FVG | (0, None) | bars since FVG confirmed |
| 31 | 31 | `fvg_fill_pct` | FVG | (0, 1) | percentage filled |
| 32 | 32 | `fvg_freshness_enc` | FVG | (0, 3) | 1=open, 2=partial, 3=fully_filled |
| 33 | 33 | `pd_position` | PREMIUM_DISCOUNT | (0, 1) | position in current leg |
| 34 | 34 | `pd_label_enc` | PREMIUM_DISCOUNT | (0, 2) | 0=discount, 1=equilibrium, 2=premium |
| 35 | 35 | `pd_distance_from_eq` | PREMIUM_DISCOUNT | (0, 1) | distance from equilibrium |
| 36 | 36 | `pd_leg_span_atr` | PREMIUM_DISCOUNT | (0, None) | leg span in ATR |
| 37 | 37 | `atr` | MARKET_REGIME | (0, None) | current ATR value |
| 38 | 38 | `atr_percentile` | MARKET_REGIME | (0, 1) | ATR percentile in lookback window |
| 39 | 39 | `daily_range_pct` | MARKET_REGIME | (0, 1) | daily range as fraction of ATR |
| 40 | 40 | `volatility_regime_enc` | MARKET_REGIME | (0, 2) | 0=low, 1=normal, 2=high |
| 41 | 41 | `spread` | MARKET_REGIME | (0, None) | current spread |
| 42 | 42 | `session_enc` | SESSION | (0, 4) | 0=asian, 1=london, 2=overlap, 3=ny, 4=off |
| 43 | 43 | `session_phase_enc` | SESSION | (0, 2) | 0=early, 1=mid, 2=late |
| 44 | 50 | `htf_alignment_enc` | SETUP_GEOMETRY | (-1, 1) | -1=misaligned, 0=neutral, 1=aligned |
| 45 | 51 | `ltf_alignment_enc` | SETUP_GEOMETRY | (-1, 1) | -1=misaligned, 0=neutral, 1=aligned |
| 46 | 52 | `distance_to_entry_atr` | SETUP_GEOMETRY | (0, None) | distance to entry zone in ATR |
| 47 | 53 | `sl_distance_atr` | SETUP_GEOMETRY | (0, None) | SL distance in ATR |
| 48 | 54 | `tp_distance_atr` | SETUP_GEOMETRY | (0, None) | TP distance in ATR |
| 49 | 55 | `available_rr` | SETUP_GEOMETRY | (0, None) | available risk-reward ratio |

### Excluded from Training (6 MACRO_NEWS features)

| Contract Index | Feature Name | Reason |
|---:|---|---|
| 44 | `event_present` | MACRO_NEWS family — excluded by PRICE_INDICES filter |
| 45 | `event_importance` | MACRO_NEWS family — excluded by PRICE_INDICES filter |
| 46 | `normalized_surprise` | PIT-blocked (forecast-dependent, always 0.0) |
| 47 | `surprise_zscore` | PIT-blocked (forecast-dependent, always 0.0) |
| 48 | `expected_gold_dir_enc` | PIT-blocked (forecast-dependent, always 0.0) |
| 49 | `observed_reaction_atr` | PIT-blocked (label-side, always 0.0) |

### Categorical Encodings
- **Regime:** `REG_ENC = {bearish: 0.0, neutral: 1.0, bullish: 2.0}`
- **Direction:** `DIR_ENC = {bearish: -1.0, neutral: 0.0, bullish: 1.0}`
- **Session:** `{asian: 0, london: 1, overlap: 2, ny: 3, off: 4}`
- **OB freshness:** `{fresh: 1.0, touched: 2.0, stale: 3.0}`
- **FVG freshness:** `{open: 1.0, partially_filled: 2.0, fully_filled: 3.0}`
- **PD label:** `{discount: 0.0, equilibrium: 1.0, premium: 2.0, unknown: 1.0}`

### Missing-Value Handling
- **Global default:** `NAN_SENTINEL = 0.0` — all NaN/inf replaced with 0.0
- **Missing categorical:** encoded as neutral/default value
- **PIT-blocked features:** always 0.0 (never activated)
- **Post-processing:** `np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)`

### Blocked Features (NEVER activated)
| Feature | Block Reason | Required Value |
|---|---|---|
| `normalized_surprise` | Forecast-dependent, not PIT-verified | 0.0 |
| `surprise_zscore` | Forecast-dependent, not PIT-verified | 0.0 |
| `expected_gold_dir_enc` | Forecast-dependent, not PIT-verified | 0.0 |
| `observed_reaction_atr` | Label-side, post-event | 0.0 |

---

## 2. Label Definition

### Barrier Label (from `v38/dataset/labeler.py`)

- **TP (take profit) hit first → label = 1** (positive)
- **SL (stop loss) hit first → label = 0** (negative)
- **Neither hit within horizon → label = -1** (censored, excluded from training)

### Label Parameters
| Parameter | Value | Source |
|---|---|---|
| `label_tp_r` | 2.0 | `V38Config.label_tp_r` — TP = +2R |
| `label_sl_r` | 1.0 | `V38Config.label_sl_r` — SL = -1R |
| `label_max_bars` | 240 | Override: `dataclasses.replace(V38Config(), label_max_bars=240)` |
| `label_simultaneous_policy` | "SL_wins" (default) | Conservative: simultaneous TP+SL → label = 0 |

### Label Computation
1. Entry price = close of setup bar
2. SL = entry ± sl_distance (direction-dependent)
3. TP = entry ± sl_distance × label_tp_r
4. Scan future bars (entry bar exclusive) up to `label_max_bars` (240 M5 bars ≈ 20 hours)
5. First barrier hit determines label
6. Simultaneous TP+SL on same bar → SL wins (label = 0)

### TP/SL Definition
- **SL distance:** `max(ATR × 0.5, price - min_protected_low)` for bullish; `max(ATR × 0.5, max_protected_high - price)` for bearish
- **TP:** `entry + sl_distance × 2.0` for bullish; `entry - sl_distance × 2.0` for bearish

---

## 3. Lookback and Prediction Horizon

| Parameter | Value |
|---|---|
| Lookback (structure build) | Full history from bar 0 to current bar |
| Swing strength | 2 bars each side (fractal detection) |
| Displacement ATR period | 14 bars |
| ATR percentile lookback | Config default (`atr_percentile_lookback`) |
| Prediction horizon | 240 M5 bars (≈ 20 hours) |
| Label resolution | First barrier hit within 240 bars |

---

## 4. Training/Validation/Holdout Split

| Split | Setups | Date Range | Purpose |
|---|---|---|---|
| Train+Val (80%) | 107,611 | 2018-08-20 → 2024-08-05 | Walk-forward training + validation |
| Holdout (20%) | 26,892 | 2024-08-05 → 2026-03-03 | Final untouched evaluation |

### Walk-Forward Details
- **Total folds:** 14
- **Minimum training size:** `max(200, 10% of trainval)` ≈ 10,761 setups
- **Fold step:** `max(50, 5% of trainval)` ≈ 5,380 setups
- **Out-of-fold validation:** 94,122 setups (cumulative across folds)
- **Holdout:** trained on all 107,611 trainval, evaluated on 26,892 holdout

---

## 5. Data Source

| Parameter | Value |
|---|---|
| Data source | Genuine Dukascopy Jetta data (no interpolation/fabrication) |
| Symbol | XAUUSD |
| LTF (entry timeframe) | M5 |
| HTF (context timeframe) | H1 |
| M5 bars | 596,572 |
| H1 bars | 49,719 |
| Data range | 2018-01-01 → 2026-03-03 |
| Candidate setups | 134,503 |
| Positive (TP hit) | 45,582 |
| Negative (SL hit) | 88,878 |
| Censored (no hit) | 43 |
| Positive rate | 33.9% |

---

## 6. Model Configuration

### LightGBM Parameters (from `V38Config.lgbm_params`)
```python
{
    "objective": "binary",
    "metric": ["binary_logloss", "auc"],
    "n_estimators": 400,
    "learning_rate": 0.03,
    "num_leaves": 63,
    "max_depth": -1,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "verbose": -1,
    "random_state": 42,
    "deterministic": True,
}
```

### Walk-Forward Override
- **n_estimators capped at 200** per fold (`min(200, params["n_estimators"])`)
- This ensures faster fold training while maintaining model capacity

### Calibration
- **Method:** Isotonic regression
- **Applied:** Post-ONNX (not baked into graph)
- **Calibration data:** Training/validation data only (NOT holdout)

### Classification Threshold
- **Value:** 0.5 (applied to calibrated probability)
- **Decision rule:** `IF calibrated_p_positive >= 0.5 THEN ENTER ELSE SKIP`

---

## 7. Validation Results (M5 Full Data)

### Holdout (26,892 setups, 2024-08-05 → 2026-03-03)
| Metric | Value |
|---|---|
| AUC | 0.580 |
| 95% CI | [0.573, 0.587] |
| PR-AUC | 0.420 |
| Brier | 0.223 |
| ECE | 0.021 |
| Model win rate | 51.3% |
| Raw win rate | 34.8% |
| Expectancy | +0.539R |
| Profit factor | 2.11 |
| Sharpe (per trade) | 0.359 |
| Max drawdown | 35.0R |
| Trades (threshold 0.5) | 1,606 |
| Permutation test p-value | 0.0 |

### Walk-Forward Validation (94,122 OOF setups)
| Metric | Value |
|---|---|
| AUC | 0.572 |
| 95% CI | [0.568, 0.576] |
| PR-AUC | 0.403 |
| Brier | 0.221 |
| ECE | 0.036 |
| Model win rate | 48.2% |
| Raw win rate | 33.4% |
| Expectancy | +0.446R |
| Profit factor | 1.86 |
| Sharpe (per trade) | 0.298 |
| Max drawdown | 101.0R |
| Trades (threshold 0.5) | 6,823 |

### Stability
| Metric | Value |
|---|---|
| Folds | 14 |
| Stability ratio | 1.0 (14/14 folds positive expectancy) |

### By Direction (Holdout)
| Direction | AUC | PF | Expectancy | Win Rate |
|---|---|---|---|---|
| Bearish | 0.584 | 2.14 | +0.590R | 51.5% |
| Bullish | 0.556 | 1.71 | +0.447R | 50.8% |

### Leakage Audit
- **Verdict:** PASS (all 14 checks)
- **Max feature-label correlation:** 0.076 (`post_sweep_reaction_atr`)
- **No high-correlation leakage detected**

---

## 8. Non-Modifications (MUST NOT Change)

1. Do NOT change features to improve reported metrics
2. Do NOT use holdout data for feature selection
3. Do NOT activate PIT-blocked features (indices 46-49)
4. Do NOT modify 72h threshold or readiness logic
5. Do NOT fabricate historical forecasts
6. Do NOT weaken PIT requirements
7. Do NOT modify the economic calendar (remains PIT-blocked)

---

## 9. Source Code References

| Component | File |
|---|---|
| Feature contract | `v38/features/contract.py` |
| Feature engine (reference) | `v38/features/engine.py` |
| M5 optimized detector | `v38/v38_2/m5_validation.py` |
| Setup detector | `v38/dataset/setup_detector.py` |
| Barrier labeler | `v38/dataset/labeler.py` |
| V38 config | `v38/config.py` |
| ONNX interface contract | `v38/v38_2/V38_2_ONNX_MT5_INTERFACE_CONTRACT.{md,json}` |
| M5 validation report | `v38/v38_2/V38_2_M5_FULL_DATA_VALIDATION_REPORT.json` |
| M5 dataset (parquet) | `v38/v38_2/full_data_artifacts/v38_2_dataset_M5_H1_lb240.parquet` |
