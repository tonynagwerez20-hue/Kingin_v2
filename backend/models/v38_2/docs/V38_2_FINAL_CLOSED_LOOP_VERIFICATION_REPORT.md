# V38.2 Final Closed-Loop Verification Report

**Created:** 2026-08-18
**Status:** NOT COMPLETE
**Reason:** Compilation (G9) is now PASS (MetaEditor64 via Wine). Strategy Tester
backtest (G10-G12, G16-G17) and runtime feature/structure parity (G5/G6 runtime)
remain BLOCKED: the MT5 terminal launches under Wine but the Exness account login
and Strategy Tester cannot be driven reliably through the headless Wine GUI, and the
auto-connected demo server provides no real XAUUSD history. These gates are BLOCKED,
not silently passed — see section 10 for the exact blocker and the native-Windows runbook.

## 1. Architecture

V38.2 = V37 operational engine (PRESERVED) + V38.2 intelligence layer (ADDED):

```
V37 risk/execution/management (PRESERVE)
        ▲
V38.2 StructureEngine → 50-feature FeatureEngine → ONNX → isotonic calibrator
        → threshold 0.50 → V37 execution → TRADE
```

See `V38_2_ARCHITECTURE_FINAL.md` and `V38_2_V37_REFERENCE_AUDIT.md`.

## 2. Canonical artifacts (G1)

| Artifact | Path | sha256 |
|---|---|---|
| ONNX model | `artifacts/v38_2_final_model.onnx` | `3f004d9f…40ee9` |
| Calibrator JSON | `artifacts/v38_2_calibrator.json` | `5ba026a3…c393a` |
| Calibrator joblib | `artifacts/v38_2_calibrator.joblib` | `e61fb0ab…7a5f1` |
| Final model joblib | `artifacts/v38_2_final_model.joblib` | `a7b3c647…8c23fa` |
| M5 dataset | `artifacts/v38_2_dataset_M5_H1_lb240.parquet` | (cached) |
| Feature parity fixture | `artifacts/v38_2_feature_parity_fixture.json` | — |
| MQL5 parity fixture | `artifacts/v38_2_mql5_parity_fixture.json` | — |

**G1 = PASS.** All canonical artifacts exist and load. Model immutable (not retrained).

## 3. Feature contract

- 56 contract features; 50 PRICE_INDICES used (6 MACRO_NEWS indices 44-49 excluded).
- ONNX input `input` shape `[None,50]` float32; outputs `label` [1] int64,
  `probabilities` [None,2] float32 (column 1 = P(TP before SL)).
- PIT-blocked features (46-49) remain 0.0. No normalization/scaling.
- Threshold 0.50 on calibrated probability.

## 4. Python model + ONNX parity (G2, G3)

Run: `python_tests/test_onnx_validation.py` → **OVERALL: PASS**
- ONNX load, opset [9,1]: PASS
- Tensor dims (input 50, label [1], proba [N,2]): PASS
- ONNX Runtime inference: PASS
- LightGBM ↔ ONNX parity: 0 decision mismatches / 26,892 holdout samples
  (raw mean diff 1e-6, cal mean diff 1e-6)

**G2 = PASS. G3 = PASS (Python/ONNX runtime side).**

## 5. Calibration parity (G4)

- Method: isotonic, 85 points, `out_of_bounds=clip`, monotonic.
- Canonical JSON keys: `X_thresholds` (capital X), `y_thresholds`.
- **MQL5 algorithm parity:** port of `IsotonicMap` (clip boundaries + binary-search
  linear interp) verified vs sklearn `IsotonicRegression.predict` on
  {0, 0.01, 0.1, 0.25, 0.3, 0.5, 0.7, 0.9, 0.99, 1, threshold-region points} +
  5000 random samples → **max abs error ≈ 1.1e-16, monotonic.** Algorithm correct.
- **MQL5 defect FIXED:** `ParseArray` searched lowercase `"x_thresholds"` → never
  matched canonical `X_thresholds` → arrays empty → calibration silently returned
  raw probability. Fixed to case-insensitive key search accepting both spellings,
  with explicit failure logging and `m_method="none"` fallback (never silent).

**G4 = PASS (algorithm + defect fixed).** Runtime MQL5 calibration output must
still be confirmed in MT5 (the JSON-key fix is a source fix awaiting compile).

## 6. Python/MQL5 feature parity (G5)

See `V38_2_PYTHON_MQL5_FEATURE_PARITY_REPORT.md`.

- 50/50 features have a documented Python↔MQL5 formula mapping.
- 3 defects FIXED: `distance_to_entry_atr` (always 0.0), `atr_percentile`
  (always 0.5 via empty buffer), `sl_distance_atr` (wrong fallback when no
  protected level).
- 2 parity caveats remain: `spread` (live vs historical), `session` (UTC vs
  broker time) — documented, require MT5 confirmation.

**G5 = PASS at source level; runtime bar-by-bar comparison in MT5 = NOT VERIFIED.**

## 7. Structure engine + lookahead (G6, G7)

See `V38_2_STRUCTURE_ENGINE_AUDIT.md`.

- All structure components (swings/BOS/CHOCH/OB/FVG/liquidity/PD/regime) are
  faithful static ports. No lookahead detected: every query bounded by
  `conf_bar <= b` / event time `<= ts[b]`.

**G6 = PASS at source level; runtime = NOT VERIFIED. G7 = PASS at source level.**

## 8. Bar / forming-bar policy (G8)

See `V38_2_BAR_POLICY.md`. **FIXED:** `ltfBar = NBars()-2` (last closed bar) to
match Python's closed-bar decision convention.

**G8 = PASS at source level; runtime confirmation in MT5 pending.**

## 9. MQL5 compilation (G9)

**G9 = PASS.** MetaEditor64 (`C:\Program Files\MetaTrader 5\MetaEditor64.exe`)
was installed under Wine 10.0 and used to compile the EA headlessly:

```
wine MetaEditor64.exe /compile:"MQL5\Experts\V38_2_EA.mq5" /log
Result: 0 errors, 0 warnings, 2281 ms elapsed, cpu='X64 Regular'
```

Output: `V38_2_EA.ex5` (128,472 bytes) committed at `mql5/V38_2_EA.ex5`.
Build log: `mql5/build_logs/V38_2_EA_compile.log`.

Compilation surfaced and fixed four additional defects not detectable by static
inspection (these prove the original source never compiled):
1. `OnnxSetInputShape/OutputShape` wrong-parameters-count — called variadic
   (MQL4 style). MQL5 signature is `(long handle, long index, const ulong &shape[])`.
   Fixed to pass `ulong[]` shape arrays.
2. `iATR(symbol,tf,period,shift)` 4-arg MQL4 call in `ATRAt()` warmup. MQL5 `iATR`
   is handle-based (no shift arg). Replaced with manual true-range simple-average.
3. OB zone `zoneHigh`/`zoneLow` declared `int` from `double` price fields
   (warning 43) — latent parity bug truncating XAUUSD fractional prices. → `double`.
4. Structure-feature virtuals (`HTFRegimeEnc`, `ProtectedHigh`, `OBDistanceATR`,
   …~38 fns) declared `virtual` in base with no body. MQL5 has no pure-virtual
   (`=0`) → "must have a body" error. Added neutral default bodies (Python
   NaN_SENTINEL=0.0 / neutral-enc defaults), overridden by CV38_2StructureEngine.

Source-level checks (retained): braces balanced; include guards present
(`__V38_2_STRUCTURE_MQH__`, `__V38_2_FEATURE_ENGINE_MQH__`, `__V38_CALIBRATOR_MQH__`);
base private→protected; virtual override signatures consistent; ONNX shape APIs
checked.

## 10. Initialization + observation + Strategy Tester (G10-G12, G16)

**G10-G12, G16 = BLOCKED.** MT5 terminal64.exe launches under Wine 10.0 and
connects to a broker (MetaQuotes demo; live prices render under Xvfb), so the
terminal itself works. The blocker is the Exness account + Strategy Tester flow:

- The auto-connected demo server does NOT provide real XAUUSD history (the
  visible "XAUUSD" row is priced ~0.68 — not gold), so a real XAUUSD backtest
  cannot use it.
- Automating the Exness-MT5Trial9 account login (account 476553066) via the
  headless Wine GUI is not reliable: MT5 dropdown menus and the Navigator
  right-click context menu do not render or register reliably under Xvfb, so the
  "Open an Account" / server-search dialog cannot be driven. MT5 terminal does
  not accept login/password as command-line arguments.

The EA is fully prepared for a native-Windows run:
- `InpMode=MODE_OBSERVATION` default (calculates + logs, no trades).
- `InpTradingEnabled=false` master switch.
- `InpDebugMode=true` logs every candidate (dir, raw/cal prob, threshold, ATR,
  SL dist, RR, decision, reason) to `Print` and optional CSV.
- Exact tester settings provided in 13.

**Native-Windows runbook to clear G10-G17:**
1. Install MT5 on Windows, connect to Exness-MT5Trial9, login 476553066.
2. Copy `V38_2_EA.ex5` (+ V38_2_Structure/FeatureEngine via the .mq5, the onnx,
   calibrator.json) into the MT5 data folders, or recompile the .mq5.
3. Attach to an XAUUSD M5 chart → confirm OnInit logs "model loaded" +
   "calibrator loaded" (G10 init).
4. Observation mode: `InpTradingEnabled=false`, run Strategy Tester
   2024-01-01→2026-03-03, M5, model "Every tick based on real ticks" (G11).
5. Trade backtest: `InpTradingEnabled=true` (G12, G16 baseline).
6. Out-of-sample: last 6 months, frozen parameters (G17).
7. Restart test: re-init the EA on an open position; confirm GlobalVariable
   `R_<id>` / `P_<id>` restore and break-even/trailing resume (G18 persistence).

## 11. Risk / position management (G13, G14)

See `V38_2_RISK_POSITION_AUDIT.md`. V37 risk engine, CalcLot, partial-close,
break-even, trailing, drawdown, trade-cap, duplicate prevention, persistence,
emergency close all PRESERVED. TP/partial-close race FIXED via `InpUseHardTP`
(default false = V37 managed exit). ML cannot bypass risk gates.

**G13 = PASS at source level; runtime edge-case tests in MT5 pending.**
**G14 = PASS at source level; runtime + restart tests in MT5 pending.**

## 12. News/session/spread filters (G15)

See `V38_2_FILTERS_AUDIT.md`. Session (EAT=UTC+3), spread (points), news
(FILTER_ONLY blackout) all PRESERVED. `InpUseSessionFilter` now wired. Calendar
fail-open behavior documented.

**G15 = PASS at source level; runtime calendar-data confirmation in MT5 pending.**

## 13. Strategy Tester configuration (for Windows MT5)

```
Symbol:        XAUUSD
Timeframe:     M5 (LTF), H1 (HTF)
Model:         "Every tick based on real ticks" (preferred) or "1 minute OHLC"
Spread:        Current / fixed 30 points (InpMaxSpreadPoints=30)
Period:        2024-08-05 → 2026-03-03 (holdout, out-of-sample) then full range
Initial dep:   5000 USD
Leverage:      1:100 (or broker default)
Inputs:
  InpMode                = MODE_OBSERVATION   (TEST 3: observation)
  InpTradingEnabled      = false              (TEST 3); true (TEST 5)
  InpUseHardTP           = false              (V37 managed exit — canonical)
  InpProbThreshold       = 0.50
  InpRiskPerTradePct     = 0.5
  InpDailyLimitPct       = 2.0
  InpTotalLimitPct       = 5.0
  InpMaxTradesPerDay     = 5
  InpATRPeriod           = 14
  InpATR_SL_Mult         = 1.20
  InpPartialRR           = 2.0
  InpPartialFraction     = 0.50
  InpUseTrailing         = true
  InpTrailATRmult        = 1.50
  InpTrailStepPoints     = 20.0
  InpStartHourEAT        = 10
  InpEndHourEAT          = 22
  InpNewsMode            = NEWS_FILTER_ONLY
  InpOnnxFilename        = v38_2_final_model.onnx   (place in MQL5/Files/)
  InpCalibratorFile      = v38_2_calibrator.json    (place in MQL5/Files/)
  InpDebugMode           = true
  InpLogToFile           = true
```

Test sequence: TEST1 compile → TEST2 init → TEST3 observation (no trades, verify
logs match Python parity fixtures) → TEST4 strategy tester runs → TEST5 trade-
enabled backtest (holdout) → TEST6 forward/OOS → TEST7 restart/persistence →
TEST8 edge-case risk.

## 14. Backtest results

The only existing backtest is a **Python simulation** (not MT5), documented in
`artifacts/V38_2_EA_BACKTEST_REPORT.json`:
- V38.2 (Python sim, 2026-01-01→2026-05-31): 38 trades, WR 71%, PF 4.82, Net $1190, DD 1.99%
- V37 (Python sim, same period): 157 trades, WR 43.31%, PF 1.29, Net $633, DD 11.63%

**This is NOT an MT5 Strategy Tester result.** It assumes close-price execution
with no slippage. It is indicative only. Gate G16 (real MT5 baseline backtest) =
BLOCKED.

## 15. Out-of-sample (G17)

**G17 = BLOCKED** (no MT5). The model's holdout (26,892 setups, 2024-08-05→2026-03-03)
was already evaluated in Python (AUC 0.580, PF 2.11, 14/14 fold stability). EA-level
OOS requires MT5 Strategy Tester.

## 16. Regression (G18)

Source-level regression: changes to `FeatureEngine`/`Structure` are additive
virtuals + overrides; V37 operational code in `V38_2_EA.mq5` (CalcLot, Manage,
Reduce, DailyReset, news, session, spread, EmergencyClose) is unchanged except
the documented TP/partial-close policy + session toggle. Python tests re-run
clean (ONNX parity still 0 mismatches).

**G18 = PASS at source level; runtime regression in MT5 pending.**

## 17. No win-rate marketing

ML classification holdout WR ≈ 51.3–53.3%. This is NOT the EA live/backtest WR.
The Python-simulation 71% WR is NOT an MT5 result. EA WR must come from MT5
Strategy Tester and forward testing. No live WR claim is made.

## 18. Gate-by-gate status (G1-G20)

| Gate | Description | Status |
|---|---|---|
| G1 | canonical artifacts verified | **PASS** |
| G2 | Python model verified | **PASS** |
| G3 | ONNX parity verified | **PASS** (re-verified 2026-08-18: input [None,50] f32; outputs label[int64]+probabilities[N,2] f32; EA binds out0=label,out1=proba, reads proba[1]=P(class=1)) |
| G4 | calibration parity verified | **PASS** (re-verified: canonical JSON key `X_thresholds`; EA handles both `X_thresholds`/`x_thresholds` case-insensitively; 85 isotonic points) |
| G5 | 50-feature Python/MQL5 parity | PASS (source); **runtime NOT VERIFIED** |
| G6 | structure-engine parity | PASS (source); **runtime NOT VERIFIED** |
| G7 | no-lookahead audit | **PASS** (source) |
| G8 | closed/forming-bar policy | **PASS** (source) |
| G9 | MQL5 compilation | **PASS** (MetaEditor64 via Wine 10.0; 0 errors/0 warnings; V38_2_EA.ex5 128,472 B; committed 3b2efde) |
| G10 | initialization test | **BLOCKED** — FBS account 28763853 authenticates then drops immediately & reproducibly under Wine (`connection to fbs.com lost` at 13:42 and 14:07 after restart+re-login); terminal falls back to MetaQuotes demo. FBS real-account connection cannot be maintained under Wine. |
| G11 | observation-mode test | **BLOCKED** — requires XAUUSD M5 history, which has no available source in this environment (see 18.1) |
| G12 | Strategy Tester execution | **BLOCKED** — no XAUUSD M5 history; Strategy Tester panel open + config written but cannot run |
| G13 | risk engine verified | PASS (source); runtime pending |
| G14 | position-management verified | PASS (source); runtime pending |
| G15 | news/session/spread filters | PASS (source); runtime pending |
| G16 | baseline backtest | **BLOCKED** — requires G10-G12 + XAUUSD M5 history; environmentally unavailable |
| G17 | forward/out-of-sample | **BLOCKED** — requires G16 |
| G18 | no unexplained critical discrepancies | **PASS** (source) |
| G19 | all artifacts documented | **PASS** |
| G20 | final audit report generated | **PASS** |

### 18.1 Why the M5 backtest is environmentally blocked (verified 2026-08-18)

A genuine M5 Strategy-Tester backtest needs a continuous XAUUSD M5 OHLC series.
No such source exists in this Linux/Wine environment:

1. **FBS live download — connection lost every attempt.** Account 28763853
   authenticates against the FBS server then drops immediately, reproducibly,
   under Wine 10.0 — confirmed twice (journal `connection to fbs.com lost` at
   13:42 and again at 14:07 after a clean terminal restart + explicit
   re-login). The real-account trading-server connection cannot be maintained
   under Wine (handshake/IP-validation/protocol mismatch), so no fresh XAUUSD
   history can be pulled. Adding the symbol to Market Watch also failed
   repeatedly (GUI coordinate drift under Wine).
2. **No raw M5 CSV in the repo.** `data/processed/jetta/XAUUSD_M5.csv` (cited in
   AGENTS.md) is absent from this clone; the only XAUUSD OHLC CSV present is
   H1 (`backend/data/XAUUSDm_H1_*.csv`), which is the HTF, not the M5 execution
   timeframe.
3. **M5 dataset parquet is sparse.** `v38_2_dataset_M5_H1_lb240.parquet` holds
   134,503 setup rows (entry/sl/tp/mfe/mae + features), not a continuous 596,572-bar
   M5 series — unusable as a tester history.
4. **M1 acquisition explicitly blocked.** `XAUUSDm_M1_audit.json` records
   `BLOCKED_BY_ENVIRONMENT` ("MetaTrader5 package not importable — Linux"),
   `total_m1_bars: 0` — confirming raw sub-H1 bars were never acquired.

A custom-symbol + CSV import workaround is not viable without a continuous M5
source. The H1 CSV alone is insufficient: the EA's ATR handle and StructureEngine
are M5-based (`iATR(_Symbol, PERIOD_M5, …)`, `InpLTF=PERIOD_M5`), so an H1-only
test would not exercise the canonical V38.2 pipeline.

**Resolution requires a native Windows MT5 terminal** with (a) a stable FBS
connection for live history, or (b) a pre-exported continuous XAUUSD M5 ticks/bars
file imported into a custom symbol.

## 19. Remaining risks

1. ~~MT5 compilation may reveal MQL5-specific errors~~ — **resolved 2026-08-18**:
   `V38_2_EA.mq5` compiles cleanly via MetaEditor64 (Wine 10.0), 0 errors / 0
   warnings, `V38_2_EA.ex5` produced. The `long label[1]` + `float proba[2]`
   OnnxRun ordering and opset-9 output binding are confirmed by the
   Python/ONNX re-verification (G3).
2. ~~ONNX/calibrator file load fails in Strategy Tester (err 5019)~~ — **resolved
   2026-08-18 (build 38.21)**: the EA previously used `OnnxCreate(filename)` and
   `FileOpen(filename)` with a bare filename. In the Strategy Tester, the agent
   runs in `Tester\<hash>\Agent-127.0.0.1-3000\` whose `MQL5\Files` is empty, so
   both failed with **ERR_FILE_NOT_EXIST=5019** and `OnInit` aborted (code 1).
   **Fix:** the canonical ONNX model and calibrator JSON are now embedded
   directly into `V38_2_EA.ex5` via `#resource "\\Files\\v38_2_final_model.onnx"
   as uchar g_onnx_data[]` and `#resource "\\Files\\v38_2_calibrator.json" as
   uchar g_cal_data[]` (byte-for-byte: 927,383 B + 4,107 B, confirmed in the
   compile log). `OnInit` now loads via `OnnxCreateFromBuffer(g_onnx_data,
   ONNX_DEFAULT)` and `g_cal.LoadFromString(CharArrayToString(g_cal_data))`,
   with the old file path retained as a fallback for terminal hot-swap.
   Diagnostic logging (resource size, file-existence check, error codes) added
   before each load. This mirrors the V37 reference, which used
   `#resource` + `OnnxCreateFromBuffer`.
3. **Session timezone:** broker time vs UTC must be confirmed/converted at
   runtime (source-level handling present).
4. **Structure runtime parity:** the static port needs bar-by-bar validation
   against the Python fixture in MT5 — blocked on a Strategy-Tester run
   (now unblocked once the user re-runs the tester with build 38.21).
5. **maxBars=5000** cap may affect long-span structure features — runtime TBD.
6. **Calendar data** availability in the Strategy Tester — runtime TBD.
7. **FBS connection stability** under Wine is unproven (connection drops
   reproducibly); native Windows is required for a stable trading-server
   connection — but the user IS running the tester on native Windows, so this
   no longer blocks the EA-load/backtest path.

## 20. Known limitations

- MetaEditor/MT5 run under Wine 10.0, so G9 (compilation) PASSED, but the
  trading-server connection (FBS) is unstable and no continuous XAUUSD M5
  history is available -> G10-G12, G16-G17 remain BLOCKED in this environment.
- Feature/structure parity is source-level only until an MT5 runtime test runs
  on real XAUUSD M5 history.
- The 71% WR is a Python simulation, not an MT5 backtest; no live/EA WR claim.

## 21. Next actions

1. ~~Compile `V38_2_EA.mq5` (+ `.mqh` includes) in MetaEditor~~ -- DONE
   (0 errors / 0 warnings, `V38_2_EA.ex5` built).
2. ~~Place `v38_2_final_model.onnx` + `v38_2_calibrator.json` in `MQL5/Files/`~~
   -- DONE (artifacts deployed to the Wine MT5 install: Experts, Include, Files).
3. **Obtain a continuous XAUUSD M5 history** -- the current hard blocker:
   - re-establish a stable FBS connection (or run on native Windows), OR
   - export XAUUSD M5 ticks/bars from a Windows MT5 terminal and import into a
     custom symbol here.
4. Add XAUUSD (or the custom symbol) to Market Watch and let M5 history load.
5. Run TEST3 (observation) on the parity-fixture period; confirm the EA's
   logged feature vectors + calibrated probabilities match the Python fixtures
   (G5/G6 runtime).
6. Run TEST5 (trade-enabled) on the holdout; compare to the Python-sim baseline
   (G16).
7. Run TEST7 (restart/persistence) to confirm GlobalVariable state survives
   (G14 runtime).
8. Only after G10-G12 + G5/G6 runtime pass -> declare V38.2 engineering-complete.

**V38.2 STATUS: NOT COMPLETE.**
