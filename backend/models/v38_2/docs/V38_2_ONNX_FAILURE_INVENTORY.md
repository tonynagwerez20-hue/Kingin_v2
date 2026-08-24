# V38.2 ONNX Initialization Failure — Phase 0 Inventory

Date: 2026-08-24
Scope: Diagnose/repair MT5 Strategy Tester init failure —
`FAILED to load ONNX model v38_2_final_model.onnx err=5019` +
`calibrator not loaded, using raw probabilities`, EA `V38_2_EA.mq5`,
XAUUSD M5, Exness MT5.

No canonical artifacts were modified during this phase.

## 1. Located artifacts

| Item | Path | Status |
|---|---|---|
| EA source | `backend/models/v38_2/mql5/V38_2_EA.mq5` (39,625 B, version "38.21") | present |
| Compiled EA | `backend/models/v38_2/mql5/V38_2_EA.ex5` (392,170 B) | present |
| Structure engine | `backend/models/v38_2/mql5/V38_2_Structure.mqh` (70,545 B) | present |
| Feature engine | `backend/models/v38_2/mql5/V38_2_FeatureEngine.mqh` (21,779 B; `V38_2_N_FEATURES=50`) | present |
| Calibrator class | `backend/models/v38_2/mql5/V38_Calibrator.mqh` (6,835 B) | present |
| V37 reference | `backend/models/v38_2/mql5/V37_REFERENCE.mq5` | present |
| ONNX model (deploy copy) | `backend/models/v38_2/mql5/v38_2_final_model.onnx` (927,383 B) | present |
| ONNX model (canonical) | `backend/models/v38_2/artifacts/v38_2_final_model.onnx` | SHA256-identical to deploy copy |
| Calibrator JSON (deploy copy) | `backend/models/v38_2/mql5/v38_2_calibrator.json` (4,107 B) | present |
| Calibrator JSON (canonical) | `backend/models/v38_2/artifacts/v38_2_calibrator.json` | SHA256-identical to deploy copy |
| Calibrator source (Python) | `backend/models/v38_2/artifacts/v38_2_calibrator.joblib` + `python_source/ml/` | present |
| ONNX manifest | `backend/models/v38_2/artifacts/v38_2_onnx_manifest.json` | present |
| ONNX export code | `backend/models/v38_2/python_source/export_onnx.py`, `python_source/onnx/export.py` | present |
| Python inference/parity | `python_tests/test_mql5_parity.py`, `test_onnx_validation.py`, `test_feature_parity.py`, `test_ea_backtest.py` | present |
| Parity fixtures | `artifacts/v38_2_mql5_parity_fixture.json` (10 samples), `v38_2_feature_parity_fixture.json` (20 samples) | present |
| Freeze report | `artifacts/V38_2_FINAL_MODEL_FREEZE_REPORT.json` | present |
| Architecture report | `docs/V38_2_ARCHITECTURE_FINAL.md` | present |
| Prior closed-loop reports | `docs/V38_2_FINAL_CLOSED_LOOP_VERIFICATION_REPORT.md` + 8 audit docs | present |
| Existing build logs | `mql5/build_logs/` | NOT present (empty/absent after env reset) |
| Tester configuration | none committed to repo (`.set`/`.ini` not found) | absent |
| AGENTS.md instructions | repo-root AGENTS.md context (V38.2 sections) | present |

## 2. Artifact integrity (G0/G1/G2)

```
SHA256 v38_2_final_model.onnx  (mql5/ and artifacts/ identical):
3f004d9fa3d1179895e41a4399e57dac8d64ba88349b0108510df7cb48e40ee9
SHA256 v38_2_calibrator.json   (mql5/ and artifacts/ identical):
5ba026a3f43d883b8ab6896c3f6adb135fa9f419d86e98c1472b308bc72c393a
```

Canonical calibrator JSON keys: `X_thresholds` (capital X), `y_thresholds`,
`out_of_bounds="clip"`, `n_points=85`. Keys were NOT changed.

## 3. ONNX graph validation vs frozen manifest (Python `onnx` 1.22.0)

- `onnx.checker.check_model`: PASS
- ir_version 8; opsets: ai.onnx=9, ai.onnx.ml=1 → matches manifest `actual_opset=[9,1]`
- nodes: TreeEnsembleClassifier, Identity, Identity, Cast, Mul → matches manifest
- input `input`: float32, shape ['', 50] (dynamic batch) → matches manifest (n_features=50)
- output `label`: int64 [1]; output `probabilities`: float32 ['', 2] (no ZipMap) → matches manifest
- Because batch dims are dynamic, MQL5 REQUIRES `OnnxSetInputShape`/`OnnxSetOutputShape`
  before `OnnxRun` — the EA does this ([1,50] / [1] / [1,2]).

## 4. EA ONNX/calibrator loading code (HEAD = commit 8067ad5, build 38.21)

- `#resource "\\Files\\v38_2_final_model.onnx" as uchar g_onnx_data[]`
- `#resource "\\Files\\v38_2_calibrator.json"  as uchar g_cal_data[]`
- Load order in OnInit: calibrator (resource → file fallback) THEN ONNX
  (`OnnxCreateFromBuffer(g_onnx_data, ONNX_DEFAULT)` → `OnnxCreate(filename)` fallback).
- ONNX failure already returns `INIT_FAILED` (fail-closed for the model).

## 5. Observed-failure log vs HEAD source

Observed (2026-08-18 17:24:46):
- `V38.2: WARNING — calibrator not loaded, using raw probabilities`
- `V38.2: FAILED to load ONNX model v38_2_final_model.onnx err=5019`

HEAD build 38.21 prints different strings ("calibrator not loaded from file OR
resource…", "FAILED to load ONNX model (resource AND file)…"). Conclusion: the
failing tester run used a PRE-38.21 build that loaded both artifacts by bare
filename only (OnnxCreate + FileOpen). See repair report for root-cause detail.

## 6. Error 5019 — official meaning (verified against MQL5 Reference, not memory)

MQL5 Reference → Constants, Enumerations and Structures → Codes of Errors and
Warnings → Runtime Errors: **ERR_FILE_NOT_EXIST = 5019 "File does not exist"**
(https://www.mql5.com/en/docs/constants/errorswarnings/errorcodes)

## 7. Environment capabilities (2026-08-24)

- Python 3 with onnx 1.22.0 / onnxruntime 1.29.0 / sklearn 1.9.0 / lightgbm 4.7.0: AVAILABLE
- Wine / MetaEditor64: NOT present at session start (prior 2026-08-18 install was
  lost on environment reset); reinstall attempted in-session for Phase 8.
- Native Windows MT5 + Exness login 476553066: NOT available → Strategy Tester
  runtime gates remain BLOCKED per AGENTS.md (2026-08-18 bridge notes).
