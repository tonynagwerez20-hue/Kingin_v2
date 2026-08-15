# V38.2 ONNX Artifact Reconciliation Report

**Created:** 2026-08-12
**Purpose:** Determine which ONNX artifacts are legacy vs production before training/exporting the V38.2 final model.

---

## 1. Artifacts Inspected

| # | Artifact | Location | Feature Count | Opset | Status |
|---|---|---|---|---|---|
| A | `lgbm_signal_filter_20y.onnx` | `backend/models/` | 8 | 13 | Legacy |
| B | `lgbm_signal_filter_20y.json` | `backend/models/` | 8 | — | Legacy |
| C | `v38_model.onnx` | `backend/models/v38/` | 56 | [9,1] | Legacy |
| D | `v38_onnx_manifest.json` | `backend/models/v38/` | 56 | 15 (manifest) | Legacy |
| E | `V38_2_ONNX_MT5_INTERFACE_CONTRACT.json` | `backend/v38/v38_2/` | 56 | 15 | Production spec |
| F | `ONNX_DOCUMENTATION.md` | `backend/models/` | 8 | — | Documents artifact A |
| G | `onnx_mql5_integration.mq5` | `backend/models/` | 8 | — | Legacy EA |
| H | `v38_2_dataset_M5_H1_lb240.parquet` | `backend/v38/v38_2/full_data_artifacts/` | 56 | — | M5 validation dataset |

---

## 2. Artifact A — Legacy 8-Feature ONNX (`lgbm_signal_filter_20y.onnx`)

**Verdict: LEGACY — V38.1-era, unrelated to V38.2.**

### Details
- **Producer:** `MLSignalFilterConverter`
- **Graph type:** Hand-built ONNX graph (NOT a real LightGBM tree model)
- **Opset:** 13, IR version 8
- **Input:** `input` FLOAT `[1, 8]` — fixed batch size 1
- **Output:** `output` FLOAT `[1]` — single confidence value
- **Nodes:** 8 (Sub→Sub→Div→Clip→MatMul→Flatten→Div→Clip)
- **8 features:** `ob_strength, fvg_present, bos_aligned, liquidity_swept, adr_pct, pips_to_liquidity, session, htf_bias`
- **Weight semantics:** LightGBM feature importances used as weights (non-negative), NOT model coefficients
- **Only 4 of 8 weights non-zero:** `ob_strength=9066, session=2165, htf_bias=1459, fvg_present=156`
- **Training data:** 7,104 samples from `data/backtest_20y/real_signals_20y.json`
- **Threshold:** 0.65
- **Trained at:** 2026-05-04

### Why Legacy
- Feature set is completely different from V38.2's 56-feature contract
- Hand-built graph uses feature importances as weights, not an actual LightGBM model
- Training data predates V38.2 (7K samples vs 134K)
- No SMC structure features (BOS/CHOCH/liquidity/OB/FVG/premium-discount)
- Documented only in `models/ONNX_DOCUMENTATION.md` (artifact F)

---

## 3. Artifact C — Legacy V38.1 56-Feature ONNX (`v38_model.onnx`)

**Verdict: LEGACY — V38.1 model trained on old 4,496-setup dataset, NOT the V38.2 M5 model.**

### Details
- **Producer:** `OnnxMLTools` (onnxmltools conversion)
- **Graph type:** Real LightGBM `TreeEnsembleClassifier` (5 nodes)
- **Opset:** [9, 1], IR version 8
- **Input:** `input` FLOAT `[null, 56]` — dynamic batch
- **Outputs:** `label` INT64 `[1]`, `probabilities` FLOAT `[null, 2]`
- **56 features:** Same order as V38.2 contract (see artifact E)
- **Training data:** 4,496 setups (H1/H4), holdout split at 2025-07-17
- **Conversion:** via onnxmltools (not hand-built)
- **Manifest:** `models/v38/v38_onnx_manifest.json`

### Why Legacy
- Trained on old 4,496-setup H1/H4 dataset, not the 134,503-setup M5 dataset
- Opset 9 (V38.2 contract specifies opset 15)
- Manifest says `onnx_version: onnx_v38_1`
- Was the V38.1 production model attempt, superseded by V38.2 M5 validation
- Feature order matches V38.2 contract, but model weights are from old training

---

## 4. Artifact E — V38.2 Interface Contract (Production Specification)

**Verdict: PRODUCTION SPECIFICATION — defines the intended V38.2 ONNX interface.**

### Details
- **Contract version:** `v38.2_interface_1`
- **Status:** `INTERFACE_SPECIFICATION_ONLY`
- **Warning (from contract):** "This contract defines the interface ONLY. The production ONNX model is NOT exported."
- **Feature count:** 56
- **Opset:** 15, IR version 8
- **Input:** `input` FLOAT `[null, 56]` — dynamic batch
- **Outputs:** `label` INT64 `[1]`, `probabilities` FLOAT `[null, 2]`
- **Calibration:** Isotonic, applied post-ONNX (not baked into graph)
- **Threshold:** 0.5 on calibrated probability
- **PIT-blocked features (4):** `normalized_surprise, surprise_zscore, expected_gold_dir_enc, observed_reaction_atr` — MUST be 0.0

### Feature Order (56 features)
```
[ 0] htf_regime_enc          [28] fvg_direction_enc
[ 1] ltf_regime_enc          [29] fvg_size_atr
[ 2] bos_count_recent        [30] fvg_age_bars
[ 3] choch_count_recent      [31] fvg_fill_pct
[ 4] last_event_direction_enc [32] fvg_freshness_enc
[ 5] last_event_disp_atr     [33] pd_position
[ 6] last_event_age_bars     [34] pd_label_enc
[ 7] protected_high           [35] pd_distance_from_eq
[ 8] protected_low            [36] pd_leg_span_atr
[ 9] multi_leg_aligned        [37] atr
[10] leg_extension_atr        [38] atr_percentile
[11] structure_strength       [39] daily_range_pct
[12] nearest_liquidity_dist   [40] volatility_regime_enc
[13] nearest_liquidity_side   [41] spread
[14] liquidity_swept          [42] session_enc
[15] sweep_depth_atr          [43] session_phase_enc
[16] post_sweep_reaction      [44] event_present
[17] eqh_eql_present          [45] event_importance
[18] inducement_present       [46] normalized_surprise [PIT]
[19] ob_present               [47] surprise_zscore      [PIT]
[20] ob_direction_enc         [48] expected_gold_dir_enc [PIT]
[21] ob_strength              [49] observed_reaction_atr [PIT]
[22] ob_distance_atr          [50] htf_alignment_enc
[23] ob_age_bars              [51] ltf_alignment_enc
[24] ob_mitigation_count      [52] distance_to_entry_atr
[25] ob_freshness_enc         [53] sl_distance_atr
[26] ob_mitigation_depth      [54] tp_distance_atr
[27] fvg_present              [55] available_rr
```

---

## 5. M5 Validation Feature Set (Artifact H)

**Verdict: The M5 validation used the 56-feature V38.2 contract — 50 features for training (PRICE_INDICES), 6 MACRO_NEWS features excluded.**

### Details
- **Dataset:** `v38_2_dataset_M5_H1_lb240.parquet`
- **Total setups:** 134,503 (45,582 positive, 88,878 negative, 43 censored)
- **Feature columns:** 56 (prefixed `f_` in parquet)
- **Features used for training:** 50 (PRICE_INDICES — all non-MACRO_NEWS family)
- **Features excluded from training:** 6 (MACRO_NEWS family)
  - Indices 44-49: `event_present, event_importance, normalized_surprise, surprise_zscore, expected_gold_dir_enc, observed_reaction_atr`
- **PIT-blocked features (confirmed all-zero in dataset):** 4
  - `normalized_surprise, surprise_zscore, expected_gold_dir_enc, observed_reaction_atr`
- **Feature contract:** `V38.1 (implemented, price features only)` — same 56-feature spec, using only the 50 non-macro features for training

### All-zero features in M5 dataset (10 total)
| Index | Feature | Reason |
|---|---|---|
| 7 | `protected_high` | Not populated by StructureIndex (returns 0.0) |
| 8 | `protected_low` | Not populated by StructureIndex (returns 0.0) |
| 24 | `ob_mitigation_count` | Not populated in M5 detector |
| 26 | `ob_mitigation_depth` | Not populated in M5 detector |
| 44 | `event_present` | MACRO_NEWS family — excluded from training |
| 45 | `event_importance` | MACRO_NEWS family — excluded from training |
| 46 | `normalized_surprise` | PIT-blocked (forecast-dependent) |
| 47 | `surprise_zscore` | PIT-blocked (forecast-dependent) |
| 48 | `expected_gold_dir_enc` | PIT-blocked (forecast-dependent) |
| 49 | `observed_reaction_atr` | PIT-blocked (label-side) |

### Training/Validation/Holdout Split
- **Total:** 134,503 setups
- **Train+Val (80%):** 107,611 setups, 2018-08-20 → 2024-08-05
  - Walk-forward validation: 94,122 setups (14 folds)
- **Holdout (20%):** 26,892 setups, 2024-08-05 → 2026-03-03

---

## 6. Files Referencing Legacy 8-Feature Model

The following files reference the legacy 8-feature model (artifact A) and are NOT part of the V38.2 pipeline:

| File | Role |
|---|---|
| `models/ONNX_DOCUMENTATION.md` | Documents artifact A (legacy) |
| `models/convert_to_onnx.py` | Builds artifact A from JSON |
| `models/onnx_mql5_integration.mq5` | Legacy EA for artifact A (8 features) |
| `ml_filter.py` | Python runtime for 8-feature model |
| `train_ml_20years.py` | Trains 8-feature model |
| `Engine/igof/layers/ml_layer.py` | IGOF layer wrapping 8-feature model |
| `delta_learner.py` | References 8-feature model |
| `mc_ml_integration.py` | References 8-feature model |
| `mc_signal_labeler.py` | References 8-feature model |
| `mc_signal_scorer.py` | References 8-feature model |
| `process_and_train_ml.py` | References 8-feature model |
| `real_data_labeler_20y.py` | References 8-feature model |
| `train_ml_filter.py` | References 8-feature model |
| `unified_smc_ml.py` | References 8-feature model |
| `TWENTY_YEAR_ML_RESULTS.md` | Documents 8-feature model results |

These are all V38.1-era files. The V38.2 pipeline (`v38/v38_2/`) does NOT reference the 8-feature model.

---

## 7. Training Scripts Referencing Old Models

| Script | Model Referenced | Status |
|---|---|---|
| `train_ml_20years.py` | 8-feature (artifact A) | Legacy — produces `lgbm_signal_filter_20y.json` |
| `v38/v38_2/m5_validation.py` | 56-feature (V38.2 contract) | **Current** — produced the M5 validation result |
| `v38/v38_2/full_data_pre_modeling.py` | 56-feature (V38.2 contract) | Earlier phase — M15/H1 validation |
| `v38/v38_2/generate_onnx_contract.py` | 56-feature (V38.2 contract) | Generated the interface contract |

**No current V38.2 training script references the old 8-feature model.**

---

## 8. Conclusion

### Legacy Artifacts (NOT to be used for V38.2 production)
1. **`models/lgbm_signal_filter_20y.onnx`** — 8-feature hand-built graph, V38.1-era
2. **`models/lgbm_signal_filter_20y.json`** — 8-feature weights, V38.1-era
3. **`models/v38/v38_model.onnx`** — 56-feature V38.1 model trained on 4,496 setups
4. **`models/v38/v38_onnx_manifest.json`** — manifest for V38.1 model
5. **`models/onnx_mql5_integration.mq5`** — EA for 8-feature model
6. **`models/ONNX_DOCUMENTATION.md`** — documents the 8-feature legacy model

### Production Specification
- **`v38/v38_2/V38_2_ONNX_MT5_INTERFACE_CONTRACT.{md,json}`** — 56-feature V38.2 interface, opset 15

### M5 Validation Used
- **56-feature V38.2 contract** (50 PRICE_INDICES for training, 6 MACRO_NEWS excluded)
- The M5 validation did NOT use the 8-feature model
- The M5 validation did NOT use the V38.1 ONNX (artifact C)
- The M5 validation trained LightGBM on 134,503 setups using 50 features

### Required Actions
1. **DO NOT** overwrite or delete legacy artifacts A-F
2. **DO NOT** export the 8-feature model as V38.2 production
3. **DO** train the final V38.2 model on the 56-feature M5 dataset (50 features used)
4. **DO** export to ONNX with opset 15, input `[null, 56]`, outputs `label` + `probabilities`
5. **DO** build a NEW MQL5 EA that uses the 56-feature ONNX (NOT the legacy 8-feature EA)
6. **DO** verify the MQL5 EA implements the same 56-feature pipeline as the Python validation

### The successful M5 validation (AUC=0.580, PF=2.11, 14/14 stability) was produced by:
- **Feature engine:** `v38/v38_2/m5_validation.py` → `StructureIndex` + `build_feature_vector()`
- **Feature contract:** `v38/features/contract.py` (56 features, V38.1 contract version)
- **Model:** LightGBM walk-forward (14 folds), 50 PRICE_INDICES features
- **Data:** Genuine Dukascopy M5 bars (596,572 bars, 134,503 setups)

**The production ONNX must correspond to this 56-feature model, NOT the legacy 8-feature artifact.**
