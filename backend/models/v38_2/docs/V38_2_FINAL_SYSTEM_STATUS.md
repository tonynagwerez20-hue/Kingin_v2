# V38.2 Final System Status

**Created:** 2026-08-12
**Phase:** V38.2 — ONNX → MQL5 EA integration COMPLETE (Python side)
**Verdict:** ✅ Model frozen, ONNX exported, MQL5 EA built. Structure module pending for live trading.

---

## Executive Summary

The V38.2 trading system has been validated, frozen, and exported to production ONNX. The model demonstrates a genuine statistical edge on 1.5 years of untouched holdout data (2024-08-05 → 2026-03-03):

- **Holdout AUC:** 0.579 (calibrated), 95% CI [0.573, 0.587]
- **Profit factor:** 2.28 (calibrated), 2.11 (raw)
- **Expectancy:** +0.599R per trade (calibrated)
- **Win rate:** 53.3% (model) vs 34.8% (raw baseline)
- **Fold stability:** 14/14 positive expectancy (100%)

The ONNX model achieves **100% decision parity** with the Python LightGBM model (0 mismatches on 26,892 holdout samples). The MQL5 EA is built and runs in observation mode; live trading requires the structure detection module.

---

## What Was Done

### Phase 0: Artifact Reconciliation
- Identified two legacy ONNX lineages:
  - **8-feature model** (`lgbm_signal_filter_20y.onnx`): V38.1-era, hand-built graph, unrelated to V38.2
  - **56-feature V38.1 model** (`v38_model.onnx`): trained on 4,496 setups, superseded by V38.2
- Confirmed the M5 validation used the 56-feature V38.2 contract (50 PRICE_INDICES for training)
- Documented in `V38_2_ONNX_ARTIFACT_RECONCILIATION.md`

### Phase 1: Final Model Specification
- Documented exact 50-feature set (PRICE_INDICES), encodings, label definition
- Documented train/val/holdout split: 107,568 train+val, 26,892 holdout
- Documented LightGBM params, calibration method, threshold
- Documented in `V38_2_FINAL_MODEL_SPECIFICATION.md`

### Phase 2: Final Model Freeze
- Trained LightGBM on full train+val (107,568 setups) with walk-forward OOF
- Fitted isotonic calibrator on OOF probabilities (no holdout data used)
- Evaluated ONCE on untouched holdout
- Saved model + calibrator as joblib artifacts
- Report: `V38_2_FINAL_MODEL_FREEZE_REPORT.json`

### Phase 3: Production ONNX Export
- Converted LightGBM to ONNX via onnxmltools (opset 9, IR v8)
- Input: `[None, 50]` float32, Output: `label` + `probabilities`
- Exported isotonic calibrator to JSON (85 points)
- Verified Python vs ONNX Runtime parity:
  - Mean proba diff: 1e-6
  - **Decision parity: 100% (0 mismatches on 26,892 samples)**
- Report: `V38_2_ONNX_PARITY_REPORT.json`

### Phase 4: MQL5 EA
- Built `V38_2_FeatureEngine.mqh` (50-feature pipeline, mirrors Python)
- Built `V38_2_EA.mq5` (ONNX inference + risk engine + order execution)
- Reused `V38_Calibrator.mqh` (isotonic calibrator loader)
- Master safety switch (`InpTradingEnabled = false`)
- Full risk gates: probability, RR, daily loss, drawdown, consecutive losses, trades/day

### Phase 5: Python/MQL5 Parity Test
- Generated test fixture with 10 holdout samples (6 enter + 4 skip decisions)
- Fixture includes expected feature vectors, raw/calibrated probabilities, decisions
- MQL5 EA can load this fixture to verify feature engine parity
- Fixture: `v38_2_mql5_parity_fixture.json`

---

## Production Artifacts

### Python (Frozen Model)
| Artifact | Path | Size |
|---|---|---|
| LightGBM model | `full_data_artifacts/v38_2_final_model.joblib` | ~XX KB |
| Isotonic calibrator | `full_data_artifacts/v38_2_calibrator.joblib` | ~1 KB |
| ONNX model | `full_data_artifacts/v38_2_final_model.onnx` | 906 KB |
| Calibrator JSON | `full_data_artifacts/v38_2_calibrator.json` | ~3 KB |
| ONNX manifest | `full_data_artifacts/v38_2_onnx_manifest.json` | ~2 KB |
| Parity fixture | `full_data_artifacts/v38_2_mql5_parity_fixture.json` | ~10 KB |
| Freeze report | `full_data_artifacts/V38_2_FINAL_MODEL_FREEZE_REPORT.json` | ~50 KB |
| ONNX parity report | `full_data_artifacts/V38_2_ONNX_PARITY_REPORT.json` | ~1 KB |

### MQL5 (EA)
| File | Path |
|---|---|
| Main EA | `v38/mql5/V38_2_EA.mq5` |
| Feature engine | `v38/mql5/V38_2_FeatureEngine.mqh` |
| Calibrator | `v38/mql5/V38_Calibrator.mqh` (shared with V38.1) |

### Documentation
| Document | Path |
|---|---|
| Artifact reconciliation | `v38/v38_2/V38_2_ONNX_ARTIFACT_RECONCILIATION.md` |
| Model specification | `v38/v38_2/V38_2_FINAL_MODEL_SPECIFICATION.md` |
| MQL5 integration guide | `v38/v38_2/V38_2_ONNX_MQL5_INTEGRATION.md` |
| Final system status | `v38/v38_2/V38_2_FINAL_SYSTEM_STATUS.md` |

---

## Model Performance Summary

### Holdout (26,892 setups, 2024-08-05 → 2026-03-03, calibrated)

| Metric | Value |
|---|---|
| AUC | 0.579 |
| PR-AUC | 0.415 |
| Brier | 0.223 |
| ECE | 0.014 |
| Win rate (model) | 53.3% |
| Win rate (raw) | 34.8% |
| Expectancy | +0.599R |
| Profit factor | 2.28 |
| Trades | 302 |
| TP | 161 |
| FP | 141 |

### Walk-Forward Stability (14 folds)
| Metric | Value |
|---|---|
| Folds | 14 |
| AUC mean | 0.574 |
| AUC std | 0.022 |
| Expectancy mean | +0.499R |
| Expectancy std | 0.226R |
| Positive folds | 14/14 (100%) |

### ONNX Parity (26,892 holdout samples)
| Metric | Value |
|---|---|
| Mean raw proba diff | 1e-6 |
| Mean cal proba diff | 1e-6 |
| Decision mismatches | 0 |
| Decision parity | 100% |

---

## What Remains (Honest Assessment)

### BLOCKING for live trading
1. **`V38_2_Structure.mqh`** — SMC structure detection module
   - Must reimplement Python `StructureIndex` in MQL5
   - Swing detection, BOS/CHOCH, OB, FVG, liquidity, PD, regime
   - ~400 lines of numpy → MQL5 port
   - Must produce bit-identical features to Python pipeline

2. **MT5 backtest** — Run the EA in MT5 Strategy Tester
   - Load historical M5/H1 data
   - Verify EA decisions match Python predictions
   - Confirm backtest metrics match holdout results

3. **Python/MQL5 feature parity** — Verify on real MT5 data
   - Load parity fixture in MQL5
   - Compare BuildVector() output to expected feature_vector
   - Must match within float32 tolerance

### NON-BLOCKING (improvements)
4. Forward test on demo account (1-3 months)
5. Production deployment with reduced risk
6. Monitor and log live performance

---

## What Was NOT Done (And Why)

### Did NOT modify any of these (per user constraints):
- ❌ 72h threshold
- ❌ Readiness logic
- ❌ Acquisition driver
- ❌ PIT-blocked features (still all 0.0)
- ❌ Label definition (TP=2R, SL=1R, horizon=240 M5 bars)
- ❌ Feature contract (50 PRICE_INDICES, same encodings)

### Did NOT optimize on holdout:
- The holdout was evaluated exactly ONCE after model freeze
- No feature selection, threshold tuning, or hyperparameter search on holdout
- Calibration fitted on OOF (train+val) only

### Did NOT fabricate data:
- Used genuine Dukascopy Jetta M5/H1 data (596,572 M5 bars)
- No interpolation, no synthetic data, no forward-fill of gaps

---

## Technical Architecture

```
[V38.2 Production Pipeline]

Python (Training/Validation):
  v38/v38_2/m5_validation.py     → StructureIndex + build_feature_vector
  v38/v38_2/freeze_final_model.py → LightGBM + isotonic calibration
  v38/v38_2/export_onnx.py       → ONNX export + parity verification
  v38/v38_2/test_mql5_parity.py  → Parity fixture generation

MQL5 (Live Trading):
  V38_2_EA.mq5                   → Main EA (ONNX + risk + orders)
  V38_2_FeatureEngine.mqh        → 50-feature pipeline
  V38_Calibrator.mqh             → Isotonic calibrator
  V38_2_Structure.mqh            → PENDING: SMC structure detection

Frozen Artifacts:
  v38_2_final_model.onnx         → LightGBM tree ensemble (50 features)
  v38_2_calibrator.json          → Isotonic regression (85 points)
```

---

## Conclusion

The V38.2 model is **frozen and production-ready on the Python side**. The ONNX export achieves 100% decision parity with the Python model. The MQL5 EA is built with full risk management, running in observation mode by default.

**The model has a genuine edge:** AUC=0.579, PF=2.28, +0.599R expectancy per trade, 14/14 fold stability, on 1.5 years of untouched holdout data. This is not a fluke — it is a reproducible, validated statistical signal.

**The remaining work is engineering, not research:** The structure detection module (`V38_2_Structure.mqh`) must be ported from Python to MQL5 to enable live trading. Until then, the EA runs in observation mode, logging what it would trade.

**Recommended next step:** Implement `V38_2_Structure.mqh` by porting the `StructureIndex` class from `m5_validation.py` to MQL5, then run the MT5 Strategy Tester to verify end-to-end parity.
