# V38.2 ONNX-to-MT5 Interface Contract

**Contract version:** v38.2_interface_1  
**Created (UTC):** 2026-08-14T04:48:26.851080+00:00  
**Status:** INTERFACE_SPECIFICATION_ONLY

> **WARNING:** This contract defines the interface ONLY. The production ONNX model is NOT exported. MQL5 code is NOT generated. Both will be produced separately after the V38.2 readiness gate passes and full-data training is authorized.

## 1. Model Metadata

| Field | Value |
|-------|-------|
| Model version | `v38.1` |
| ONNX version | `onnx_v38_1` |
| Training version | `lgbm_v38_1` |
| Dataset version | `dataset_v38_2026_08` |
| Feature contract | `V38.1` |
| Symbol | `XAUUSD` |
| Task | `binary_classification` |
| Model type | LightGBM gradient-boosted decision trees |
| Framework | LightGBM -> ONNX (via onnxmltools, opset 15) |

**Calibration:** isotonic (applied post-ONNX (Python inference wrapper + MQL5 EA))  
> Calibration is applied AFTER ONNX inference, not baked into the graph

## 2. Training-Data Timestamp Cutoff

- **Last setup timestamp:** `2026-03-03 09:00:00+00:00`
- **First setup timestamp:** `2018-11-18 00:00:00+00:00`
- **Last setup timestamp:** `2026-03-03 09:00:00+00:00`
- **Number of setups:** 4496
- **Holdout split (80%) timestamp:** `2025-07-17 04:00:00+00:00`
- The model was trained on data up to the holdout split (80% chronological). The last 20% is untouched holdout. The production model (when exported) will be trained on ALL available data up to the training cutoff.

## 3. Input Tensor

| Property | Value |
|----------|-------|
| Name | `input` |
| Dtype | `float32` |
| Shape | `[None, 56]` |
| Layout | row-major (C order) |
| N features | 56 |
| Meaning | [batch_size, n_features]. batch_size=1 for single-setup inference. |

## 4. Output Tensor

The ONNX model produces two outputs:

### `label`
- **Dtype:** `int64`
- **Shape:** `[1]`
- **Meaning:** predicted class label (0 = negative/skip, 1 = positive/enter)
- **Note:** This is the argmax of probabilities. For trading decisions, use the calibrated probability and threshold instead.

### `probabilities`
- **Dtype:** `float32`
- **Shape:** `[None, 2]`
- **Meaning:** [P(class=0), P(class=1)] per sample. Column 1 = P(setup succeeds / TP hit).
- **Note:** These are RAW (uncalibrated) probabilities. Apply isotonic calibration post-ONNX.

**Primary output:** `probabilities[0][1]`  
**Meaning:** Raw P(setup succeeds — TP barrier hit before SL barrier)

## 5. Output Probability Meaning

- **Raw P(positive):** Raw (uncalibrated) probability from the LightGBM ensemble that the setup will succeed (TP=+2R hit before SL=-1R within the barrier horizon).
- **Calibrated P(positive):** Isotonic-calibrated probability. This is the value used for the trading decision.
- **Label=1 definition:** Label=1 means: within label_max_bars bars, price reached +2R (TP) before -1R (SL). Label=0 means: price reached -1R (SL) before +2R (TP), or neither barrier was hit within the horizon (censored, excluded from training).
- **Label max bars (default):** 20
- **TP:** +2.0R | **SL:** -1.0R | **Tie-break:** SL_wins

## 6. Classification Threshold

- **Threshold:** 0.5
- **Applied to:** calibrated probability (post-isotonic)
- **Decision rule:** `IF calibrated_p_positive >= 0.5 THEN ENTER ELSE SKIP`
- 0.5 is the default threshold. It may be tuned later, but any change MUST be validated on out-of-sample data. Do NOT tune on holdout.

## 7. Exact Feature Names and Order

The 56 features MUST be provided in this EXACT order:

| Index | Name |
|-------|------|
| 0 | `htf_regime_enc` |
| 1 | `ltf_regime_enc` |
| 2 | `bos_count_recent` |
| 3 | `choch_count_recent` |
| 4 | `last_event_direction_enc` |
| 5 | `last_event_disp_atr` |
| 6 | `last_event_age_bars` |
| 7 | `protected_high` |
| 8 | `protected_low` |
| 9 | `multi_leg_aligned` |
| 10 | `leg_extension_atr` |
| 11 | `structure_strength` |
| 12 | `nearest_liquidity_dist_atr` |
| 13 | `nearest_liquidity_side_enc` |
| 14 | `liquidity_swept` |
| 15 | `sweep_depth_atr` |
| 16 | `post_sweep_reaction_atr` |
| 17 | `eqh_eql_present` |
| 18 | `inducement_present` |
| 19 | `ob_present` |
| 20 | `ob_direction_enc` |
| 21 | `ob_strength` |
| 22 | `ob_distance_atr` |
| 23 | `ob_age_bars` |
| 24 | `ob_mitigation_count` |
| 25 | `ob_freshness_enc` |
| 26 | `ob_mitigation_depth` |
| 27 | `fvg_present` |
| 28 | `fvg_direction_enc` |
| 29 | `fvg_size_atr` |
| 30 | `fvg_age_bars` |
| 31 | `fvg_fill_pct` |
| 32 | `fvg_freshness_enc` |
| 33 | `pd_position` |
| 34 | `pd_label_enc` |
| 35 | `pd_distance_from_eq` |
| 36 | `pd_leg_span_atr` |
| 37 | `atr` |
| 38 | `atr_percentile` |
| 39 | `daily_range_pct` |
| 40 | `volatility_regime_enc` |
| 41 | `spread` |
| 42 | `session_enc` |
| 43 | `session_phase_enc` |
| 44 | `event_present` |
| 45 | `event_importance` |
| 46 | `normalized_surprise` |
| 47 | `surprise_zscore` |
| 48 | `expected_gold_dir_enc` |
| 49 | `observed_reaction_atr` |
| 50 | `htf_alignment_enc` |
| 51 | `ltf_alignment_enc` |
| 52 | `distance_to_entry_atr` |
| 53 | `sl_distance_atr` |
| 54 | `tp_distance_atr` |
| 55 | `available_rr` |

## 8. Datatype

- **All features:** `float32`
- **Input tensor:** `float32`
- ALL 56 features are float32. Categorical features are ordinal-encoded integers stored as float32. No string inputs.

## 9. Normalization / Scaling

- **Method:** none
- Features are raw, unnormalized values. No StandardScaler, MinMaxScaler, or any fitted normalization is applied. The LightGBM model handles feature scaling internally via tree splits. The EA must send the EXACT raw values as specified in feature_table.
- **ATR-normalized features:** Many features are already ATR-normalized (e.g., *_atr suffix), meaning they are divided by the ATR at the setup bar. These are dimensionless ratios.
- **Price features:** protected_high and protected_low are absolute price levels (float32, no scaling).

## 10. Missing-Value Behavior

**Global default:** 0.0  
**Rationale:** The V38.1 feature engine returns 0.0 for all absent structure objects (no OB, no FVG, no liquidity pool, etc.). The EA MUST replicate this exactly.

**Categorical absent:** For categorical (_enc) features, send the 'absent/none/neutral' sentinel from the encoding map (usually 0.0, but check encoding_map per feature).

**PIT-blocked:** normalized_surprise, surprise_zscore, expected_gold_dir_enc, observed_reaction_atr MUST be 0.0 (PIT-blocked until calendar authorized).

Per-feature missing-value behavior:

| Index | Name | Default | Behavior |
|-------|------|---------|----------|
| 0 | `htf_regime_enc` | 1.0 | categorical_absent_sentinel |
| 1 | `ltf_regime_enc` | 1.0 | categorical_absent_sentinel |
| 2 | `bos_count_recent` | 0.0 | zero_when_absent |
| 3 | `choch_count_recent` | 0.0 | zero_when_absent |
| 4 | `last_event_direction_enc` | 0.0 | categorical_absent_sentinel |
| 5 | `last_event_disp_atr` | 0.0 | zero_when_absent |
| 6 | `last_event_age_bars` | 0.0 | zero_when_absent |
| 7 | `protected_high` | 0.0 | zero_when_absent |
| 8 | `protected_low` | 0.0 | zero_when_absent |
| 9 | `multi_leg_aligned` | 0.0 | zero_when_absent |
| 10 | `leg_extension_atr` | 0.0 | zero_when_absent |
| 11 | `structure_strength` | 0.0 | zero_when_absent |
| 12 | `nearest_liquidity_dist_atr` | 0.0 | zero_when_absent |
| 13 | `nearest_liquidity_side_enc` | 0.0 | categorical_absent_sentinel |
| 14 | `liquidity_swept` | 0.0 | zero_when_absent |
| 15 | `sweep_depth_atr` | 0.0 | zero_when_absent |
| 16 | `post_sweep_reaction_atr` | 0.0 | zero_when_absent |
| 17 | `eqh_eql_present` | 0.0 | zero_when_absent |
| 18 | `inducement_present` | 0.0 | zero_when_absent |
| 19 | `ob_present` | 0.0 | zero_when_absent |
| 20 | `ob_direction_enc` | 0.0 | categorical_absent_sentinel |
| 21 | `ob_strength` | 0.0 | zero_when_absent |
| 22 | `ob_distance_atr` | 0.0 | zero_when_absent |
| 23 | `ob_age_bars` | 0.0 | zero_when_absent |
| 24 | `ob_mitigation_count` | 0.0 | zero_when_absent |
| 25 | `ob_freshness_enc` | 0.0 | categorical_absent_sentinel |
| 26 | `ob_mitigation_depth` | 0.0 | zero_when_absent |
| 27 | `fvg_present` | 0.0 | zero_when_absent |
| 28 | `fvg_direction_enc` | 0.0 | categorical_absent_sentinel |
| 29 | `fvg_size_atr` | 0.0 | zero_when_absent |
| 30 | `fvg_age_bars` | 0.0 | zero_when_absent |
| 31 | `fvg_fill_pct` | 0.0 | zero_when_absent |
| 32 | `fvg_freshness_enc` | 0.0 | categorical_absent_sentinel |
| 33 | `pd_position` | 0.0 | zero_when_absent |
| 34 | `pd_label_enc` | 0.0 | categorical_absent_sentinel |
| 35 | `pd_distance_from_eq` | 0.0 | zero_when_absent |
| 36 | `pd_leg_span_atr` | 0.0 | zero_when_absent |
| 37 | `atr` | 0.0 | zero_when_absent |
| 38 | `atr_percentile` | 0.0 | zero_when_absent |
| 39 | `daily_range_pct` | 0.0 | zero_when_absent |
| 40 | `volatility_regime_enc` | 0.0 | categorical_absent_sentinel |
| 41 | `spread` | 0.0 | zero_when_absent |
| 42 | `session_enc` | 0.0 | categorical_absent_sentinel |
| 43 | `session_phase_enc` | 0.0 | categorical_absent_sentinel |
| 44 | `event_present` | 0.0 | zero_when_absent |
| 45 | `event_importance` | 0.0 | zero_when_absent |
| 46 | `normalized_surprise` | 0.0 | zero_when_absent |
| 47 | `surprise_zscore` | 0.0 | zero_when_no_calendar_or_no_event |
| 48 | `expected_gold_dir_enc` | 0.0 | categorical_absent_sentinel |
| 49 | `observed_reaction_atr` | 0.0 | zero_when_no_calendar_or_no_event |
| 50 | `htf_alignment_enc` | 0.0 | categorical_absent_sentinel |
| 51 | `ltf_alignment_enc` | 0.0 | categorical_absent_sentinel |
| 52 | `distance_to_entry_atr` | 0.0 | zero_when_absent |
| 53 | `sl_distance_atr` | 0.0 | zero_when_absent |
| 54 | `tp_distance_atr` | 0.0 | zero_when_absent |
| 55 | `available_rr` | 0.0 | zero_when_absent |

## 11. Categorical Encoding

- **Method:** ordinal_integer_encoding_as_float32
- **Note:** Each categorical feature maps a string category to a float32 integer. The MQL5 EA must reproduce these EXACT mappings. No one-hot encoding, no hashing.
- **Critical:** The encoding values are small integers (0, 1, 2, 3, 4 or -1, 0, 1). They are NOT arbitrary floats.

**Encoding maps (MUST be reproduced exactly in MQL5):**

### `htf_regime_enc`
| Category | Encoded value |
|----------|-------------|
| bearish | 0.0 |
| neutral | 1.0 |
| bullish | 2.0 |

### `ltf_regime_enc`
| Category | Encoded value |
|----------|-------------|
| bearish | 0.0 |
| neutral | 1.0 |
| bullish | 2.0 |

### `last_event_direction_enc`
| Category | Encoded value |
|----------|-------------|
| bearish | -1.0 |
| neutral | 0.0 |
| bullish | 1.0 |

### `nearest_liquidity_side_enc`
| Category | Encoded value |
|----------|-------------|
| above | -1.0 |
| none | 0.0 |
| below | 1.0 |

### `ob_direction_enc`
| Category | Encoded value |
|----------|-------------|
| bearish | -1.0 |
| neutral | 0.0 |
| bullish | 1.0 |

### `ob_freshness_enc`
| Category | Encoded value |
|----------|-------------|
| none | 0.0 |
| fresh | 1.0 |
| touched | 2.0 |
| stale | 3.0 |

### `fvg_direction_enc`
| Category | Encoded value |
|----------|-------------|
| bearish | -1.0 |
| neutral | 0.0 |
| bullish | 1.0 |

### `fvg_freshness_enc`
| Category | Encoded value |
|----------|-------------|
| none | 0.0 |
| open | 1.0 |
| partially_filled | 2.0 |
| fully_filled | 3.0 |

### `pd_label_enc`
| Category | Encoded value |
|----------|-------------|
| discount | 0.0 |
| equilibrium | 1.0 |
| premium | 2.0 |

### `volatility_regime_enc`
| Category | Encoded value |
|----------|-------------|
| low | 0.0 |
| normal | 1.0 |
| high | 2.0 |

### `session_enc`
| Category | Encoded value |
|----------|-------------|
| asian | 0.0 |
| london | 1.0 |
| overlap | 2.0 |
| ny | 3.0 |
| off | 4.0 |

### `session_phase_enc`
| Category | Encoded value |
|----------|-------------|
| early | 0.0 |
| mid | 1.0 |
| late | 2.0 |

### `expected_gold_dir_enc`
| Category | Encoded value |
|----------|-------------|
| bearish | -1.0 |
| neutral | 0.0 |
| bullish | 1.0 |

### `htf_alignment_enc`
| Category | Encoded value |
|----------|-------------|
| against | -1.0 |
| neutral | 0.0 |
| aligned | 1.0 |

### `ltf_alignment_enc`
| Category | Encoded value |
|----------|-------------|
| against | -1.0 |
| neutral | 0.0 |
| aligned | 1.0 |

## 12. PIT-Blocked Features (Forecast-Dependent)

- **Features:** `normalized_surprise`, `surprise_zscore`, `expected_gold_dir_enc`, `observed_reaction_atr`
- **Status:** BLOCKED_PIT_FORECAST
- **Required value:** 0.0
- **Reason:** These features depend on economic calendar forecasts or post-event reactions. Forecasts are NOT PIT-verified. They MUST be sent as 0.0 until the economic calendar is loaded and PIT-verified.
- **Never modify:** True

## 13. Full Feature Table

| Index | Name | Family | Dtype | Range | Categorical | PIT-blocked |
|-------|------|--------|-------|-------|-------------|-------------|
| 0 | `htf_regime_enc` | STRUCTURE | `float32` | [0, 2] | True | False |
| 1 | `ltf_regime_enc` | STRUCTURE | `float32` | [0, 2] | True | False |
| 2 | `bos_count_recent` | STRUCTURE | `float32` | [0, None] | False | False |
| 3 | `choch_count_recent` | STRUCTURE | `float32` | [0, None] | False | False |
| 4 | `last_event_direction_enc` | STRUCTURE | `float32` | [-1, 1] | True | False |
| 5 | `last_event_disp_atr` | STRUCTURE | `float32` | [0, None] | False | False |
| 6 | `last_event_age_bars` | STRUCTURE | `float32` | [0, None] | False | False |
| 7 | `protected_high` | STRUCTURE | `float32` | [None, None] | False | False |
| 8 | `protected_low` | STRUCTURE | `float32` | [None, None] | False | False |
| 9 | `multi_leg_aligned` | STRUCTURE | `float32` | [0, 1] | False | False |
| 10 | `leg_extension_atr` | STRUCTURE | `float32` | [0, None] | False | False |
| 11 | `structure_strength` | STRUCTURE | `float32` | [0, 1] | False | False |
| 12 | `nearest_liquidity_dist_atr` | LIQUIDITY | `float32` | [0, None] | False | False |
| 13 | `nearest_liquidity_side_enc` | LIQUIDITY | `float32` | [-1, 1] | True | False |
| 14 | `liquidity_swept` | LIQUIDITY | `float32` | [0, 1] | False | False |
| 15 | `sweep_depth_atr` | LIQUIDITY | `float32` | [0, None] | False | False |
| 16 | `post_sweep_reaction_atr` | LIQUIDITY | `float32` | [0, None] | False | False |
| 17 | `eqh_eql_present` | LIQUIDITY | `float32` | [0, 1] | False | False |
| 18 | `inducement_present` | LIQUIDITY | `float32` | [0, 1] | False | False |
| 19 | `ob_present` | ORDER_BLOCK | `float32` | [0, 1] | False | False |
| 20 | `ob_direction_enc` | ORDER_BLOCK | `float32` | [-1, 1] | True | False |
| 21 | `ob_strength` | ORDER_BLOCK | `float32` | [0, 1] | False | False |
| 22 | `ob_distance_atr` | ORDER_BLOCK | `float32` | [0, None] | False | False |
| 23 | `ob_age_bars` | ORDER_BLOCK | `float32` | [0, None] | False | False |
| 24 | `ob_mitigation_count` | ORDER_BLOCK | `float32` | [0, None] | False | False |
| 25 | `ob_freshness_enc` | ORDER_BLOCK | `float32` | [0, 2] | True | False |
| 26 | `ob_mitigation_depth` | ORDER_BLOCK | `float32` | [0, 1] | False | False |
| 27 | `fvg_present` | FVG | `float32` | [0, 1] | False | False |
| 28 | `fvg_direction_enc` | FVG | `float32` | [-1, 1] | True | False |
| 29 | `fvg_size_atr` | FVG | `float32` | [0, None] | False | False |
| 30 | `fvg_age_bars` | FVG | `float32` | [0, None] | False | False |
| 31 | `fvg_fill_pct` | FVG | `float32` | [0, 1] | False | False |
| 32 | `fvg_freshness_enc` | FVG | `float32` | [0, 3] | True | False |
| 33 | `pd_position` | PREMIUM_DISCOUNT | `float32` | [0, 1] | False | False |
| 34 | `pd_label_enc` | PREMIUM_DISCOUNT | `float32` | [0, 2] | True | False |
| 35 | `pd_distance_from_eq` | PREMIUM_DISCOUNT | `float32` | [0, 1] | False | False |
| 36 | `pd_leg_span_atr` | PREMIUM_DISCOUNT | `float32` | [0, None] | False | False |
| 37 | `atr` | MARKET_REGIME | `float32` | [0, None] | False | False |
| 38 | `atr_percentile` | MARKET_REGIME | `float32` | [0, 1] | False | False |
| 39 | `daily_range_pct` | MARKET_REGIME | `float32` | [0, 1] | False | False |
| 40 | `volatility_regime_enc` | MARKET_REGIME | `float32` | [0, 2] | True | False |
| 41 | `spread` | MARKET_REGIME | `float32` | [0, None] | False | False |
| 42 | `session_enc` | SESSION | `float32` | [0, 4] | True | False |
| 43 | `session_phase_enc` | SESSION | `float32` | [0, 2] | True | False |
| 44 | `event_present` | MACRO_NEWS | `float32` | [0, 1] | False | False |
| 45 | `event_importance` | MACRO_NEWS | `float32` | [0, 3] | False | False |
| 46 | `normalized_surprise` | MACRO_NEWS | `float32` | [-1, 1] | False | True |
| 47 | `surprise_zscore` | MACRO_NEWS | `float32` | [None, None] | False | True |
| 48 | `expected_gold_dir_enc` | MACRO_NEWS | `float32` | [-1, 1] | True | True |
| 49 | `observed_reaction_atr` | MACRO_NEWS | `float32` | [None, None] | False | True |
| 50 | `htf_alignment_enc` | SETUP_GEOMETRY | `float32` | [-1, 1] | True | False |
| 51 | `ltf_alignment_enc` | SETUP_GEOMETRY | `float32` | [-1, 1] | True | False |
| 52 | `distance_to_entry_atr` | SETUP_GEOMETRY | `float32` | [0, None] | False | False |
| 53 | `sl_distance_atr` | SETUP_GEOMETRY | `float32` | [0, None] | False | False |
| 54 | `tp_distance_atr` | SETUP_GEOMETRY | `float32` | [0, None] | False | False |
| 55 | `available_rr` | SETUP_GEOMETRY | `float32` | [0, None] | False | False |

## 14. Python Reference Inference

```python
import numpy as np
import onnxruntime as ort
import joblib

# 1. Build the 56-feature vector in EXACT order (see feature_order below)
feature_vector = np.array([
    # ... 56 float32 values in contract order ...
], dtype=np.float32).reshape(1, 56)

# 2. Load ONNX model
sess = ort.InferenceSession("v38_model.onnx", providers=["CPUExecutionProvider"])
input_name = sess.get_inputs()[0].name  # "input"

# 3. Run inference (raw probabilities, BEFORE calibration)
results = sess.run(None, {input_name: feature_vector})
labels = results[0]       # shape [1], int64 — predicted class (0 or 1)
raw_probs = results[1]   # shape [1, 2], float32 — [P(class=0), P(class=1)]
raw_p_positive = float(raw_probs[0][1])  # raw P(setup succeeds)

# 4. Apply isotonic calibration (post-ONNX, same as MQL5)
cal_obj = joblib.load("v38_calibrator.joblib")
calibrator = cal_obj["calibrator"]
method = cal_obj["method"]
if method == "isotonic":
    calibrated_p = float(calibrator.predict(np.array([raw_p_positive])))
elif method == "sigmoid":
    eps = 1e-6
    p_clipped = np.clip(raw_p_positive, eps, 1 - eps)
    logit = np.log(p_clipped / (1 - p_clipped))
    calibrated_p = float(calibrator.predict_proba(np.array([[logit]]))[0][1])
else:
    calibrated_p = raw_p_positive

# 5. Trading decision
THRESHOLD = 0.5
if calibrated_p >= THRESHOLD:
    decision = "ENTER"   # take the setup
else:
    decision = "SKIP"    # do not enter

```

**Note:** This is the reference implementation. The MQL5 EA must reproduce this exact sequence: build features -> ONNX infer -> calibrate -> threshold.

## 15. ONNX Runtime Inference Test

**Status:** PASSED
**ONNX Runtime version:** 1.28.0
**Model path:** `/workspace/project/Kingin_v2/backend/models/v38/v38_model.onnx`

> This test uses the existing placeholder ONNX model (H1/H4 data, weak signal) to validate I/O shapes and contract. The production ONNX model is NOT exported until readiness gate passes.

**Inputs:**

- `input`: shape=[None, 56], type=tensor(float)

**Outputs:**

- `label`: shape=[1], type=tensor(int64)
- `probabilities`: shape=[None, 2], type=tensor(float)

## 16. Expected Sample Input/Output

### all_zeros_input

**Input (56 float32 values):**
```
[0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000]
```
**Label (int64):** 0
**Probabilities [P(0), P(1)]:** [0.7865387201309204, 0.2134612798690796]
**P(positive) = P(1):** 0.213461

### all_ones_input

**Input (56 float32 values):**
```
[1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000, 1.000000]
```
**Label (int64):** 0
**Probabilities [P(0), P(1)]:** [0.6827818155288696, 0.31721818447113037]
**P(positive) = P(1):** 0.317218

### real_sample_input

**Meta:** {'source': 'dataset', 'row': 8, 'true_label': 1, 'direction': 'bullish'}

**Input (56 float32 values):**
```
[2.000000, 0.000000, 3.000000, 3.000000, -1.000000, 0.967825, 13.000000, 0.000000, 0.000000, 0.000000, 3.296402, 1.000000, 0.023835, -1.000000, 1.000000, 0.302842, 1.460741, 1.000000, 1.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 1.000000, 1.000000, 1.798022, 39.000000, 0.927801, 2.000000, 0.079341, 0.000000, 0.841317, 3.580482, 8.768652, 0.083969, 0.379391, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 1.000000, -1.000000, 0.000000, 0.000000, 0.000000, 0.000000]
```
**Label (int64):** 1
**Probabilities [P(0), P(1)]:** [0.08077645301818848, 0.9192235469818115]
**P(positive) = P(1):** 0.919224

## 17. MQL5 Notes (No Code)

**Status:** NOT_GENERATED
**Note:** MQL5 EA code is NOT part of this contract. It will be implemented separately by the MQL5 team using this contract as the specification.

**Key implementation points:**
- Load v38_model.onnx via OnnxRun() in MQL5
- Build the 56-feature float32 array in EXACT feature_order
- Call ONNX inference to get raw probabilities [P(0), P(1)]
- Apply isotonic calibration to raw_p_positive (load calibrator coefficients)
- Compare calibrated probability to 0.5 threshold
- If >= threshold: execute trade with TP=+2R, SL=-1R
- If < threshold: skip the setup
- PIT-blocked features (indices 46,47,48,49) MUST be 0.0

## 18. Non-Modifications

- Forecast-dependent macro features NOT changed (remain PIT-blocked at 0.0)
- Feature contract NOT modified (V38.1, 56 features, 9 families)
- readiness_gate.py NOT modified
- economic_calendar.csv NOT created
- PIT rules NOT modified
- holiday classification NOT modified
- No production ONNX model exported (interface contract only)
- No MQL5 code generated
- No MT5 connection

---
*This contract was generated by the V38.2 pre-modeling validation phase. It defines the interface only — no production model is exported and no MQL5 code is generated.*