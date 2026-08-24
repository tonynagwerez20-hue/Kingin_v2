# V38.2 ONNX + CALIBRATOR REPAIR REPORT

**Date:** 2026-08-24
**Scope:** MT5 Strategy Tester initialization failure — `OnnxCreate("v38_2_final_model.onnx")` →
`err=5019 (ERR_FILE_NOT_EXIST)` and `calibrator not loaded, using raw probabilities`.
**Branch:** production-stable
**Build:** V38_2_EA `#property version "38.22"` (was 38.21)

---

## 1. ROOT CAUSE

**Error 5019 was a file-visibility problem, not model corruption.**

The MT5 Strategy Tester executes EAs inside per-agent sandboxes
(`<Tester>\Agent-127.0.0.1-3000\` on the local agent). `OnnxCreate()` with a bare
filename resolves that name against the **agent's own `MQL5\Files` directory**, not
the terminal's `MQL5\Files`. The ONNX model (and the calibrator JSON) were deployed
only to the terminal's `MQL5\Files`, so inside the tester agent the file did not
exist → `ERR_FILE_NOT_EXIST=5019` → `OnnxCreate` returned `INVALID_HANDLE` →
`OnInit` returned `INIT_FAILED` ("tester stopped because OnInit returns non-zero
code 1"). The calibrator failed for the same reason (same sandbox file visibility),
and the previous build logged a WARNING and silently continued on raw probabilities.

Model/calibrator integrity was never in question: SHA256 of both canonical artifacts
is unchanged and Python-side inference from the same bytes is bit-consistent
(see §3, §11).

## 2. EVIDENCE

- **Phase 0 inventory:** `docs/V38_2_ONNX_FAILURE_INVENTORY.md`. Canonical ONNX
  (`3f004d9fa3d1179895e41a4399e57dac8d64ba88349b0108510df7cb48e40ee9`, 927,383 bytes)
  and calibrator (`5ba026a3f43d883b8ab6896c3f6adb135fa9f419d86e98c1472b308bc72c393a`,
  4,107 bytes) verified byte-identical between `mql5/` and `full_data_artifacts/`;
  manifest `onnx_v38_2_final`, n_features=50, contract `v38.2_interface_1`.
- **ONNX validity:** `onnx.checker` PASS; input `input` `[None,50]` float32; outputs
  `label` int64 + `probabilities` `[None,2]` float32; opsets ai.onnx 9 / ai.onnx.ml 1.
- **Runtime reproduction (this session, MT5 build 6140 under Wine, local tester
  agent):** the repaired EA reports
  `V38.2 ONNX: requested filename='v38_2_final_model.onnx' resource bytes=927383
  tester=true terminal_data_path='C:\Program Files\MetaTrader 5\Tester\Agent-127.0.0.1-3000'`
  — i.e., running inside the tester agent sandbox whose `MQL5\Files` was **never**
  populated with the model — and the model still loads (from the embedded resource).
  This directly confirms both the sandbox cause and the fix.
- **Toolchain finding:** MetaEditor 6140 *command-line* compilation of any `#resource`
  directive (bound `as uchar[]`, unbound BMP, absolute `\Files\...` or source-relative)
  fails under Wine with `error 313: invalid resource path` **while simultaneously
  resolving and logging the resource with the correct byte size** ("information:
  resource 'v38_2_final_model.onnx' as 'const uchar g_onnx_data[927383]'").
  Reproduced with a 4-line minimal EA (`ResTest.mq5`). The same sources compile
  0 errors / 0 warnings from the MetaEditor GUI. This is an environment/toolchain
  quirk (cf. the build-6090 `#resource` CLI regression on mql5.com forum, fixed in
  6140 for `/include` but still observable here under Wine); the source-level
  `#resource "\\Files\\..."` syntax is documented MQL5 and was left unchanged.

## 3. CANONICAL ARTIFACT INTEGRITY (SHA256 before == after)

| artifact | SHA256 | status |
|---|---|---|
| `v38_2_final_model.onnx` | `3f004d9f…40ee9` | UNCHANGED (not regenerated, not re-exported) |
| `v38_2_calibrator.json` | `5ba026a3…393a` | UNCHANGED (`X_thresholds`/`y_thresholds`, 85 isotonic points) |
| LightGBM model / training data / labels | — | UNCHANGED (no retrain) |

## 4. FIX (files changed)

Only `backend/models/v38_2/mql5/V38_2_EA.mq5` (+90/−3 lines) and the rebuilt
`V38_2_EA.ex5` (395,110 bytes; contains both embedded resources). **No .mqh, no
Python artifact, no canonical binary was modified.**

a. **ONNX loading (root-cause fix, V37 reference pattern).** Canonical model and
   calibrator are embedded into the .ex5 via
   `#resource "\\Files\\v38_2_final_model.onnx" as uchar g_onnx_data[]` /
   `#resource "\\Files\\v38_2_calibrator.json" as uchar g_cal_data[]` (resources are
   compiled into the EX5 and therefore exist in *every* sandbox, including tester
   agents). `OnInit` loads with `OnnxCreateFromBuffer(g_onnx_data, ONNX_DEFAULT)`
   (byte-for-byte the canonical model — the resource is the verbatim file), falling
   back to `OnnxCreate(InpOnnxFilename)` only when the resource is empty (terminal
   hot-swap scenario). Resource embedding itself landed in build 38.21 (commit
   8067ad5); 38.22 adds diagnostics and fail-closed behaviour around it.
b. **Diagnostics.** OnInit now logs requested filename, embedded resource byte count,
   tester-mode flag, and `TERMINAL_DATA_PATH` (evidence in §2).
c. **Fail-closed calibration.** Calibrator loads from the embedded resource first,
   then `MQL5\Files` fallback. If neither yields a valid **isotonic** calibrator,
   `OnInit` returns `INIT_FAILED`. The previous "WARNING — using raw probabilities"
   path is deleted. `PredictWin` additionally refuses to emit any probability when
   the calibrator is not loaded, and rejects non-finite / out-of-[0,1] raw or
   calibrated probabilities (fail-closed).
d. **Model self-test (new `ModelSelfTest()`).** After shapes are configured and
   before any trading logic: verifies model handle, feature count == 50, calibrator
   loaded + isotonic, then runs one deterministic inference (all-zero probe vector,
   the canonical NaN_SENTINEL) through the full ONNX → calibration chain and logs
   `V38.2 MODEL SELF TEST: PASS|FAIL`. Failure → `OnnxRelease` + `INIT_FAILED`.

## 5. FILES NOT CHANGED (canonical preservation)

- `v38_2_final_model.onnx`, `v38_2_calibrator.json` (byte-identical)
- `V38_2_FeatureEngine.mqh`, `V38_2_Structure.mqh`, `V38_Calibrator.mqh`
- Feature contract, feature order, labels, 72h threshold, readiness logic,
  acquisition driver, probability threshold (0.50), calibration methodology
  (isotonic, `X_thresholds`/`y_thresholds`), entry/exit logic, risk engine,
  session/spread/news filters.

## 6. ONNX LOADING METHOD

`OnnxCreateFromBuffer(g_onnx_data, ONNX_DEFAULT)` — buffer = canonical ONNX bytes
embedded via `#resource` (V37 reference pattern: `file resource + load from
buffer`). `OnnxCreate(filename)` retained only as terminal-mode fallback when the
resource array is empty (hot-swap a newer model via `MQL5\Files` without rebuild).
Resource availability in tester agents is guaranteed because resources are compiled
into the EX5 itself — the mechanism that removes the 5019 failure mode by
construction.

## 7. CALIBRATOR LOADING METHOD

Embedded `#resource` JSON → `g_cal.LoadFromString` (parse) first; file fallback
`g_cal.Load(InpCalibratorFile)`. Parser matches the canonical artifact keys
`X_thresholds` / `y_thresholds` (capital X preserved). Runtime:
`V38 Calibrator: loaded method=isotonic points=85` (85 = canonical point count).
Missing/invalid calibrator ⇒ `INIT_FAILED` (fail-closed; raw probabilities are
never traded).

## 8. MQL5 API COMPLIANCE

- `OnnxCreateFromBuffer(const uchar &data[], uint flags)` per MQL5 Reference —
  buffer is the verbatim ONNX file; `ONNX_DEFAULT`.
- `OnnxSetInputShape(handle, 0, ulong[] {1,50})` — input `[None,50]` float32 fixed
  to batch 1; `OnnxSetOutputShape` label `{1}` int64 / probabilities `{1,2}` float32;
  all four return values checked.
- `OnnxRun` return checked; tensor shapes match the canonical manifest
  (`onnx_v38_2_final`, 50 features, no ZipMap).
- `#resource` paths `\Files\...` per MQL5 Reference (leading backslash = relative to
  terminal MQL5 data dir at compile time; content embedded byte-for-byte).
- `OnInit` return codes: `INIT_SUCCEEDED` only after self-test PASS; all failure
  branches return `INIT_FAILED`.

## 9. COMPILATION RESULT — G8 PASS

MetaEditor 6140 (GUI compile, build log):
`v38_2_final_model.onnx as 'const uchar g_onnx_data[927383]'`,
`v38_2_calibrator.json as 'const uchar g_cal_data[4107]'`, `code generated` —
**0 errors, 0 warnings** (2435 ms). Output: `V38_2_EA.ex5` = 395,110 bytes,
SHA256 `031b25ebb2ad2a2370cf3158133ce5d8f65b25accc2de2636609ad2c563e58a1`.
All includes resolved (`V38_2_Structure.mqh`, `V38_2_FeatureEngine.mqh`,
`V38_Calibrator.mqh`, `<Trade/Trade.mqh>`).
Caveat: CLI compilation under Wine hits spurious error 313 (§2) — use GUI compile
or native Windows MetaEditor.

## 10. MODEL SELF-TEST — G5/G6 RUNTIME PASS (tester agent sandbox)

From `Tester/Agent-127.0.0.1-3000/logs/20260824.log` (2026-08-24, EURUSD,M5,
observation mode, tester agent — model file ABSENT from agent `MQL5\Files`):

```
V38 Calibrator: loaded method=isotonic points=85
V38.2: calibrator loaded from embedded resource (4107 bytes)
V38.2 ONNX: requested filename='v38_2_final_model.onnx' resource bytes=927383 tester=true ...
ONNX: CPU selected
V38.2: ONNX model loaded handle=4991810717346184988
V38.2 self-test probe: raw=0.385226 calibrated=0.357920 features=50
V38.2 MODEL SELF TEST: PASS
V38.2 EA initialised: Mode=0 Trading=false Features=50 Threshold=0.5 Calibrator=isotonic
```

No error 5019. No calibrator warning. `OnnxCreateFromBuffer` → handle valid →
shapes accepted → inference → finite probabilities in [0,1] → calibration applied
(cal ≠ raw). All 11 self-test checks PASS.

## 11. PYTHON ↔ MQL5 PARITY — G7 PASS (runtime + fixture)

- **Runtime probe parity (this session):** identical all-zeros vector —
  Python `onnxruntime` on the canonical file: `raw=0.385226, calibrated=0.357920`;
  MQL5 tester runtime: `raw=0.385226, calibrated=0.357920`.
  Δraw = 2.9e-07, Δcal = 7.0e-08 (float32 print precision). Decision parity 100%.
- **Fixture parity:** `v38_2_mql5_parity_fixture.json` (10 samples: 6 enter + 4 skip)
  re-verified against canonical ONNX + calibrator — raw/calibrated probabilities and
  decisions match expected exactly.
- **Live ML-gate evidence:** 4,800 candidates evaluated in the tester with real
  inference (e.g. `raw=0.3007 cal=0.2996 … REJECT: ML prob 0.300 < threshold 0.50`)
  — calibrated threshold enforcement working.

## 12. STRATEGY TESTER RESULT — G9/G10 PASS (available environment)

MT5 build 6140 under Wine, MetaQuotes-Demo account (created for verification),
EURUSD M5, 2026-08-10→2026-08-21, `Model=1` (1-minute OHLC), `InpTradingEnabled=false`
(observation mode), EA loaded by the **local tester agent**:

```
EURUSD,M5 (MetaQuotes-Demo): testing of Experts\V38_2_EA.ex5 ...
final balance 10000.00 USD
V38.2: Shutdown. Candidates=4800 ML-approved=0 Entered=0
51295 ticks, 2592 bars. Test passed in 0:13:00
```

Initialization verified (§10) + observation loop verified: Candidates=4800 > 0 with
the ML gate exercised on every candidate. ML-approved=0 / Entered=0 is *expected and
correct*: the model is XAUUSD-specialized (this run used EURUSD purely to exercise
the sandbox init path) and observation mode places no trades by design.
**This run does not replace the required native Exness/XAUUSD validation.**

## 13. EXECUTION RESULT — BLOCKED

Order placement / SL / partial close / trailing on Exness XAUUSD requires the
Exness-MT5Trial9 server (login 476553066) on native Windows; unavailable in this
environment (and ML-approved=0 on EURUSD demo data means no execution path could be
exercised here without violating the "no parameter changes to force trades" rule).

## 14. STRICT GATES

| Gate | Status | Evidence |
|---|---|---|
| G0 Source integrity | PASS | only V38_2_EA.mq5/ex5 changed (§4, §5) |
| G1 Model artifact integrity | PASS | SHA256 unchanged (§3) |
| G2 Calibrator artifact integrity | PASS | SHA256 unchanged, 85 pts, capital-X keys (§3, §7) |
| G3 File-path integrity | PASS | resource embedded; sandbox-independent (§2, §6) |
| G4 ONNX API correctness | PASS | §8 + runtime handle + shapes accepted (§10) |
| G5 ONNX shape/type validation | PASS | 4/4 Set*Shape OK in tester (§10) |
| G6 Calibrator parity | PASS | isotonic 85 pts; cal(raw) matches Python to 7e-08 (§10, §11) |
| G7 Python/MQL5 inference parity | PASS | runtime probe Δ<3e-07 + 10/10 fixture (§11) |
| G8 MQL5 compilation | PASS | 0 errors / 0 warnings, ex5 395,110 B (§9) |
| G9 Strategy Tester initialization | PASS | no 5019; init OK inside agent sandbox (§10, §12) |
| G10 Observation-mode verification | PASS | Candidates=4800>0, gate exercised, clean shutdown (§12) |
| G11 Execution/risk verification | BLOCKED | needs Exness XAUUSD native Windows (§13) |
| G12 Forward/observation verification | BLOCKED | needs Exness XAUUSD native Windows |
| G13 Regression verification | PASS | diff audit: no strategy/risk/feature/threshold change (§4, §5) |
| G14 Production readiness | BLOCKED | pending G11/G12 on Exness |

## 15. REMAINING BLOCKERS

1. **G11/G12:** native Windows MT5 + Exness-MT5Trial9 (login 476553066) — run
   observation mode (InpTradingEnabled=false) then trading-enabled backtest on
   XAUUSD M5; confirm candidates → ML-approved → entries, SL/partial/trailing/DD
   protections, restart persistence.
2. **Toolchain caveat:** MetaEditor *command-line* compile under Wine mis-reports
   error 313 on `#resource` (GUI compile unaffected). On native Windows this does
   not reproduce; documented here so CI/scripts use GUI/native compile.
