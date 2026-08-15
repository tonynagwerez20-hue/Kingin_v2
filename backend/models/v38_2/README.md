# V38.2 — Complete EA Build (V37 Evolution)

Production V38.2 XAUUSD SMC trading EA — evolution of V37 with validated 50-feature ML intelligence.

## Status: B. BACKTEST PROMISING — DEMO VALIDATION REQUIRED

---

## Folder Structure

```
models/v38_2/
├── mql5/                    # MQL5 EA source code
│   ├── V38_2_EA.mq5         # Main EA (935 lines) — V37 evolution
│   ├── V38_2_FeatureEngine.mqh  # 50-feature pipeline
│   ├── V38_2_Structure.mqh  # SMC structure engine (1913 lines)
│   ├── V38_Calibrator.mqh   # Isotonic calibration loader
│   └── V37_REFERENCE.mq5    # V37 reference (architecture map)
│
├── artifacts/               # Frozen model + data + reports
│   ├── v38_2_final_model.onnx       # ONNX model (50 features, 906KB)
│   ├── v38_2_final_model.joblib     # Python LightGBM model
│   ├── v38_2_calibrator.json        # Isotonic calibrator (85 points)
│   ├── v38_2_calibrator.joblib      # Python calibrator
│   ├── v38_2_dataset_M5_H1_lb240.parquet   # M5 training dataset (15MB)
│   ├── v38_2_dataset_M15_H1_lb80.parquet   # M15 dataset (5.9MB)
│   ├── v38_2_onnx_manifest.json     # ONNX model manifest
│   ├── v38_2_feature_parity_fixture.json   # Python↔MQL5 parity fixture
│   ├── v38_2_mql5_parity_fixture.json      # MQL5 parity fixture (10 samples)
│   ├── V38_2_ONNX_INTEGRATION_REPORT.json  # ONNX validation (6 tests PASS)
│   ├── V38_2_EA_BACKTEST_REPORT.json       # Backtest report
│   ├── V38_2_EA_BACKTEST_TRADES.csv        # Trade-by-trade CSV
│   ├── V38_2_FINAL_MODEL_FREEZE_REPORT.json
│   └── V38_2_ONNX_PARITY_REPORT.json
│
├── python_source/           # Complete Python V38.2 source
│   ├── structure/           # SMC engines (swing, BOS/CHOCH, OB, FVG, liquidity, PD)
│   ├── features/            # Feature contract + engine
│   ├── dataset/             # Labeler, setup detector, leakage audit
│   ├── ml/                  # Trainer, calibration
│   ├── audit/               # Robustness, rendering
│   ├── macro/               # Macro news engine
│   ├── risk/                # Risk engine
│   ├── onnx/                # ONNX export
│   ├── data/                # Data acquisition, readiness gate
│   ├── m5_validation.py     # M5 full-data validation
│   ├── export_onnx.py       # ONNX export script
│   └── ...                  # All V38.2 pipeline scripts
│
├── python_tests/            # Validation test scripts
│   ├── test_onnx_validation.py    # ONNX integration (6 tests)
│   ├── test_feature_parity.py     # Python↔MQL5 feature parity
│   ├── test_ea_backtest.py        # EA backtest simulation
│   ├── test_mql5_parity.py        # MQL5 parity fixture generator
│   └── export_onnx.py             # ONNX export
│
└── docs/                    # Documentation
    ├── V38_2_EA_BUILD_REPORT.md          # Final build report + V37 comparison
    ├── V38_2_ONNX_MT5_INTERFACE_CONTRACT.md   # Feature contract (authoritative)
    ├── V38_2_ONNX_MT5_INTERFACE_CONTRACT.json
    ├── V38_2_FINAL_MODEL_SPECIFICATION.md
    ├── V38_2_FINAL_SYSTEM_STATUS.md
    ├── V38_2_ONNX_MQL5_INTEGRATION.md
    ├── V38_2_ONNX_ARTIFACT_RECONCILIATION.md
    ├── V38_2_FULL_DATA_PRE_MODELING_REPORT.md
    ├── V38_2_PRE_MODELING_VALIDATION_REPORT.md
    ├── V38_2_ABLATION_RESULTS.md
    └── V38_2_FEATURE_FAMILY_CONTRIBUTION.md
```

---

## Architecture

```
V37 OPERATIONAL ENGINE (preserved exactly)
    ├─ Risk management (daily/total DD, trade cap)
    ├─ Position sizing (binary search + OrderCalcProfit)
    ├─ SL with stops-level respect
    ├─ Partial close at +2R + break-even
    ├─ Trailing stop after partial close
    ├─ Session filter (EAT)
    ├─ Spread filter
    ├─ Duplicate position prevention
    ├─ Emergency close
    ├─ Persistent state (GlobalVariables)
    ├─ News blackout (FILTER_ONLY mode)
    └─ HUD/Comment status display
            │
    V38.2 INTELLIGENCE LAYER (replaces V37 8-feature AI)
    ├─ StructureEngine (swing/BOS/CHOCH/OB/FVG/PD)
    ├─ Setup detection (candidate checks)
    ├─ 50-feature FeatureEngine
    ├─ v38_2_final_model.onnx (50 features)
    ├─ Isotonic calibration
    ├─ ML probability threshold (0.50)
    └─ Debug/audit logging
            │
    V37 risk/execution engine → TRADE
```

---

## Key Metrics

### Frozen Model (holdout)
- AUC: 0.579
- Profit Factor: 2.28
- Expectancy: +0.599R
- 14/14 fold stability

### ONNX Integration
- 100% Python↔ONNX decision parity (0 mismatches on 134,460 samples)
- 50 features (excludes 6 MACRO_NEWS — PIT-blocked)
- Isotonic calibration (85 points, ECE=0.014)

### V37 vs V38.2 Backtest (2026-01-01 → 2026-05-31)

| Metric | V37 | V38.2 |
|---|---|---|
| Trades | 157 | 38 |
| Win Rate | 43.31% | 71.05% |
| Profit Factor | 1.29 | 4.82 |
| Net Profit | $633 | $1,190 |
| Max Drawdown | 11.63% | 1.99% |

---

## Usage

### MT5 Deployment
1. Copy `mql5/V38_2_EA.mq5` and all `.mqh` files to `MQL5/Experts/`
2. Copy `artifacts/v38_2_final_model.onnx` to `MQL5/Files/`
3. Copy `artifacts/v38_2_calibrator.json` to `MQL5/Files/`
4. Compile in MetaEditor
5. Attach to XAUUSD M5 chart
6. Set `InpTradingEnabled = false` for observation mode
7. Run Strategy Tester for backtest validation

### Python Validation
```bash
cd backend
PYTHONPATH=. python -m v38.v38_2.test_onnx_validation
PYTHONPATH=. python -m v38.v38_2.test_feature_parity
PYTHONPATH=. python -m v38.v38_2.test_ea_backtest
```

---

## Constraints

- ✅ Canonical V38.2 ONNX model (not legacy 8-feature)
- ✅ PIT-blocked forecast features remain 0.0
- ✅ No holdout contamination (threshold=0.50)
- ✅ V37 operational engine preserved exactly
- ✅ No modifications to readiness_gate.py, 72h threshold, or acquisition driver
