# AGENTS.md — Kingin V38 Backend

## Project Overview
XAUUSD trading system backend. V38 is the current model generation; V38.2 is the
full-data pre-modeling validation phase using genuine Dukascopy/Jetta M1/M5/M15 data.

## Key Commands
- Run V38 contract + v38_2 data tests (87 tests): `PYTHONPATH=backend python3 -m pytest tests/test_v38_2_data.py tests/test_v38_contract.py --capture=no -p no:cacheprovider -q`
- Full pytest suite has capture issues with some non-test files in tests/; use `--capture=no` and run test files individually if needed.

## V38.2 Phase Status (as of 2026-08-14)
- **M5/H1 validation COMPLETE: AUC=0.58, PF=2.11, Stability=1.0 (14/14 folds positive)**
- M5/H1 full-data analysis: 134,503 setups (45,582 positive, 88,878 negative, 43 censored)
- Holdout AUC=0.580 (CI: 0.573-0.587), p=0.0 (permutation test), Val AUC=0.572
- Holdout expectancy=+0.539R, PF=2.11, model win rate=51.3% vs raw 34.8%
- Stability=1.0 (14/14 folds positive) — ROBUST
- Bearish holdout: AUC=0.584, PF=2.14; Bullish holdout: AUC=0.556, PF=1.71
- Detection speed: 38K bars/s (596K bars in 15.8s), structure build ~380s
- Dataset cached: v38/v38_2/full_data_artifacts/v38_2_dataset_M5_H1_lb240.parquet
- Report: v38/v38_2/V38_2_M5_FULL_DATA_VALIDATION_REPORT.json
- Leakage audit: PASS (all 14 checks pass, max feature-label corr=0.076)
- Optimized detector: v38/v38_2/m5_validation.py → StructureIndex class (O(1) per-bar queries)
- Key optimization: pre-computed numpy arrays for all StructureIndex methods (pools, OBs, FVGs, events, protected levels, legs, equals, inducements)
- build_feature_vector accepts pre-computed arrays (high, low, spread, session) — avoids per-setup DataFrame access (10,000x speedup: 945ms → 0.086ms per call)

### M15/H1 (earlier phase, for reference)
- M15/H1 full-data analysis: 45,364 setups (10x H1/H4's 4,496)
- Holdout AUC=0.547, Val AUC=0.513 (marginal), PF=2.04, Stability=64%
- Superseded by M5/H1 results above

## Critical Non-Modifications
- Do NOT modify: readiness_gate.py, economic_calendar.csv, feature_contract.py, holiday classification, PIT rules, 72h threshold
- Forecast-dependent features (indices 46,47,48) MUST stay PIT-blocked at 0.0
- observed_reaction_atr (index 49) MUST stay 0.0 (label-side blocked)

## ONNX Interface
- 56 features, input shape [None, 56] float32, outputs: label [1] int64, probabilities [None, 2] float32
- Calibration: isotonic, applied post-ONNX (not baked into graph)
- Threshold: 0.5 on calibrated probability
- Contract docs: v38/v38_2/V38_2_ONNX_MT5_INTERFACE_CONTRACT.{md,json}
- Production ONNX NOT yet exported (interface contract only)

## V38.2 ONNX → MQL5 EA Integration (COMPLETE as of 2026-08-12)
- **Final model FROZEN:** LightGBM trained on 107,568 train+val, isotonic calibrator on OOF
- **Holdout (calibrated): AUC=0.579, PF=2.28, expectancy=+0.599R, 14/14 fold stability**
- **ONNX exported:** v38_2_final_model.onnx (50 features, opset 9, 906KB)
- **Python/ONNX parity: 100% decision parity (0 mismatches on 26,892 holdout samples)**
- Calibrator exported: v38_2_calibrator.json (85 isotonic points)
- MQL5 EA built: V38_2_EA.mq5 + V38_2_FeatureEngine.mqh (50 features, observation mode)
- Parity fixture: v38_2_mql5_parity_fixture.json (10 samples: 6 enter + 4 skip)
- Artifacts: v38/v38_2/full_data_artifacts/
- Docs: V38_2_FINAL_MODEL_SPECIFICATION.md, V38_2_ONNX_ARTIFACT_RECONCILIATION.md,
        V38_2_ONNX_MQL5_INTEGRATION.md, V38_2_FINAL_SYSTEM_STATUS.md
- **PENDING:** V38_2_Structure.mqh (SMC structure detection module for MQL5)
- **PENDING:** MT5 backtest of the EA
- The M5 validation used 50 PRICE_INDICES (excludes 6 MACRO_NEWS at indices 44-49)
- The ONNX model uses 50 features (NOT 56) — legacy V38.1 ONNX used 56

## V38.2 FINAL EA BUILD — V37 EVOLUTION (2026-08-12)
- **V37 source studied:** IGOF_SMC_MASTER_V37_PRODUCTION.mq5 — architecture map created
- **V37 operational engine PRESERVED EXACTLY:** CalcLot (binary search), persistent GlobalVariables, partial close +2R (50%) + break-even, trailing stop ATR*1.5, emergency close, daily/total DD protection, session filter (EAT), spread filter, news blackout, HUD, CTrade, manual 'R' reset
- **V37 8-feature AI REPLACED:** V38.2 50-feature ONNX + StructureEngine + isotonic calibration
- **ONNX re-exported without ZipMap:** Clean float[N,2] array output for MQL5 OnnxRun (0 decision mismatches on 134,460 samples)
- **V38_2_EA.mq5:** V37 OnTick flow preserved + V38.2 intelligence layer (StructureEngine → FeatureEngine → ONNX → calibration → threshold)
- **ONNX integration: ALL 6 TESTS PASS** (load, dims, inference, parity, calibration, feature count)
- **Python backtest (2026-01-01→2026-05-31, V37-matching risk 0.5%):**
  - V38.2: 38 trades, WR=71%, PF=4.82, Net=$1190, DD=1.99%
  - V37:    157 trades, WR=43.31%, PF=1.29, Net=$633, DD=11.63%
- **STATUS: B. BACKTEST PROMISING — DEMO VALIDATION REQUIRED**
- **BLOCKED:** MT5 compilation + Strategy Tester (no MT5 terminal in environment)
- PIT-blocked forecast features remain 0.0 (6 MACRO_NEWS excluded)
- No holdout contamination (threshold=0.50, no optimization)
- Feature parity fixture: v38_2_feature_parity_fixture.json (20 samples)
- Build report: V38_2_EA_BUILD_REPORT.md

## Data
- Jetta processed CSVs: data/processed/jetta/XAUUSD_{M1,M5,M15,H1,H4}.csv
- M5=596,572 bars, M15=198,858 bars, M1=500,000 bars, H1=49,719 bars
- Range: 2018-01-01 → 2026-03-03
- Full-data M15 dataset cached: v38/v38_2/full_data_artifacts/v38_2_dataset_M15_H1_lb80.parquet
