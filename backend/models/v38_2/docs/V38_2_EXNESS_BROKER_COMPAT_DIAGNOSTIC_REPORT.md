# V38.2 EXNESS XAUUSDm BROKER-COMPATIBILITY + NO-TRADE DIAGNOSTIC REPORT

Date: 2026-08-26. Branch: `diag/v38_2-exness-broker-compat`.
Scope: diagnose why the V38.2 EA does not trade on Exness XAUUSDm and apply
the minimum evidence-based correction. **Canonical ML chain unchanged.**

Upstream input: prior session's `V38_2_VETO_ROOT_CAUSE_AUDIT.md` (2026-08-25)
is extended here. This report supersedes its "root cause not yet proven"
verdict where the new evidence permits.

---

## 0. PRESERVED CANONICAL STATE (Phase 0)

Canonical production commit: `1923c40` (branch `production-stable`),
working tree clean at task start.

SHA-256 fingerprints recorded before modification:

| Artifact | sha256 (first 16) |
|---|---|
| V38_2_EA.mq5 | b441f2a94c0e2378 |
| V38_2_EA.ex5 (build 38.22) | 031b25ebb2ad2a23 |
| V38_2_FeatureEngine.mqh | fccecb2fc6112112 |
| V38_2_Structure.mqh | 2375a5a689145424 |
| V38_Calibrator.mqh | dddf0d21d9377533 |
| V38_2_GateDiagnostic.mq5 | ff4ac02ecd4db2e5 |
| v38_2_calibrator.json | 5ba026a3f43d883b |
| v38_2_final_model.onnx | 3f004d9fa3d11798 |

ML artifacts verified byte-identical between `artifacts/` and `mql5/`
(`ONNX identical`, `Calibrator identical`). A diagnostic branch
`diag/v38_2-exness-broker-compat` was created before any modification.

> **STALE BINARY NOTICE:** the committed `V38_2_EA.ex5` (395,110 bytes) is
> build 38.22, compiled from the pre-fix source. It no longer matches the
> edited source on this branch and **must be recompiled** (MetaEditor GUI —
> CLI under Wine spuriously fails #resource per prior toolchain note) before
> the fixes/diagnostics run. This environment has no Wine/MT5 (`which wine`
> empty, no apt lists), so compilation here is BLOCKED; the user-side native
> path listed in §8 is unaffected.
>
> Canonical ML artifacts (ONNX/calibrator) were NOT modified at any point.

---

## 1. COMPLETE CODE AUDIT — GATE DEPENDENCY MAP (Phase 1)

Audited files: V38_2_EA.mq5 (1,125→1,417 lines post-edit),
V38_2_FeatureEngine.mqh (458 lines), V38_2_Structure.mqh (1,977 lines),
V38_Calibrator.mqh (182 lines), V38_2_GateDiagnostic.mq5 (208 lines).

Actual implemented order in OnTick (unchanged by this patch):

```
OnTick
  ├─ Diagnostic pre-pass (symbol spec once; time source per new bar)
  ├─ DailyReset + Manage (position mgmt)
  ├─ DD/TOTAL/DAILY-LOCK        → "LOCK: DD LIMIT"          [VETO_DD_LOCK]
  ├─ SESSION (EAT 10-22)        → "VETO: SESSION"           [VETO_SESSION]
  ├─ Tick fetch                 → "VETO: NO TICK"           [VETO_NO_TICK]
  ├─ SPREAD (normalized price)  → "VETO: SPREAD"            [VETO_SPREAD]
  ├─ NEWS FILTER_ONLY pre+post  → "VETO: NEWS BLACKOUT"     [VETO_NEWS]
  ├─ NEWS other modes pre-only  → "VETO: NEWS PREWINDOW"    [VETO_NEWS]
  ├─ Duplicate position         → "POSITION ACTIVE"         [VETO_POSITION_ACTIVE]
  ├─ Max trades/day             → "VETO: TRADE CAP"         [VETO_TRADE_CAP]
  ├─ One trade per bar (silent skip)
  ├─ UpdateStructureData (new LTF bar feed)
  ├─ Warmup (ltfBar<50)         → "WARMING UP"              [VETO_WARMUP]
  ├─ for direction in {bullish, bearish}:
  │    ├─ IsCandidateSetup      → skip                     [VETO_NO_SETUP]
  │    ├─ BuildVector           → skip                     [VETO_FEATURES]
  │    ├─ PredictWin (ONNX+cal) → skip                     [VETO_ML]
  │    ├─ calProb<0.50          → REJECT                   [VETO_ML]
  │    └─ rr<InpMinRR           → REJECT                   [VETO_RR]
  ├─ !setupFound → "SCANNING: NO SMC" / "VETO: ML THRESHOLD"
  ├─ observation/disabled       → would ENTER log          [VETO_TRADE_DISABLED]
  └─ OpenTrade:
       ├─ SymbolInfoTick + stops/freeze + CalcLot
       │   (binary search OrderCalcProfit + OrderCalcMargin) → [VETO_RISK]
       └─ CTrade.PositionOpen → retcode                    [VETO_ORDER_CHECK/EXECUTION]
OnTradeTransaction: CTrade framework callback (no explicit handler).
```

Every early return is now counted in the veto matrix (§2). CalcLot is this
EA's compound risk+margin gate; there is **no separate public OrderCheck()
call** — `CTrade.PositionOpen` internally performs `OrderSend` with retcode
validation (`TradeOK` accepts DONE/DONE_PARTIAL/PLACED). Margin validation
(OrderCalcMargin) and retcode validation are **unbypassed and unchanged**.

Hard-coded values found in the audit (all frozen by the user's rules):
- session window `10 ≤ hour(EAT) < 22`, `EAT = TimeGMT() + 10800` — looked up
  in EA line 342-352; EAT hard-coded UTC+3 offset. Single conversion site.
- spread cap `InpMaxSpreadPoints = 30` (points), NOW normalized to a price cap
  `30 × InpMaxSpreadRefPoint (0.01)` = $0.30 — single code change (§4).
- labels TP_R=2.0/SL_R=1.0/240-bar horizon — untouched.
- ML threshold 0.50 — untouched. MinRR 1.0 — untouched.
- `_Point` used in: spread gate (§FIX), trailing step `InpTrailStepPoints*_Point`
  (position management scale factor — acceptable), OpenTrade min-stop/freeze
  buffer `MathMax(minStop, freeze) + 2*_Point` (risk buffer, unchanged).

---

## 2. VETO MATRIX IMPLEMENTATION (Phase 2)

Every gate is now counted. Counters (`GC` struct in V38_2_EA.mq5):
`ticks_processed, bars_processed, session_pass/fail, spread_pass/fail,
news_pass/fail, candidate_total, feature_pass/fail, ml_evaluations,
ml_approved, ml_rejected, risk_pass/fail, margin_pass/fail,
ordercheck_pass/fail, execution_attempts/success/fail`, plus a
`veto_hist[]` histogram over:

```
VETO_SESSION, VETO_SPREAD, VETO_NO_SETUP, VETO_FEATURES, VETO_ML, VETO_RR,
VETO_RISK, VETO_MARGIN, VETO_ORDER_CHECK, VETO_EXECUTION, VETO_MARKET_CLOSED,
VETO_TRADE_DISABLED, VETO_NEWS, VETO_TRADE_CAP, VETO_DD_LOCK, VETO_NO_TICK,
VETO_POSITION_ACTIVE, VETO_WARMUP
```

OnDeinit prints the full matrix (gate counters + nonzero histogram rows).
HUD single-status limitation is unchanged by design (HUD file), but every
early return now increments both a typed counter AND the primary-veto
histogram; shutdown shows the complete distribution, not just the last label.

---

## 3. BROKER SYMBOL INSPECTION (Phase 3)

`DumpSymbolSpec()` runs at OnInit AND once on the first tick (values can be
unresolved at init on some brokers). It prints, in explicit units:

- `_Digits`, `SYMBOL_POINT`, `SYMBOL_TRADE_TICK_SIZE`
- bid/ask, `spread_price($) = ask-bid`, `spread_points`, `spread_ticks`
- tick value (base/profit/loss), vol min/max/step, stops/freeze level
- `SYMBOL_SPREAD(int)` + `SYMBOL_SPREAD_FLOAT`
- TRADE_MODE / CALC_MODE / ORDER_MODE / FILLING_MODE / EXEMODE
- `[GATESPEC]` — spread cap in THREE units: ref-points, `cap_price($)`,
  `cap_native_points`, with live verdict.
- `DumpSessionSchedule()` — SymbolInfoSessionTrade slots for all 7 days.

This settles, on the user's terminal, the decisive fact (XAUUSDm digits) that
previous sessions could not capture.

---

## 4. SPREAD ENGINE AUDIT + NUMERICAL PROOF (Phase 4)

Original gate (`V38_2_EA.mq5` pre-fix):
`if((q.ask - q.bid) / _Point > InpMaxSpreadPoints)` — spread measured in
native `_Point` units, compared against 30.

- **On the dev/training symbol (MetaQuotes/Dukascopy XAUUSD, digits=2,
  _Point=0.01):** 30 points = $0.30 — correct and unit-correct.
- **On a 3-digit symbol (candidate: Exness XAUUSDm):** 30 points = $0.03 —
  veto on nearly every tick. The user's observation "InpMaxSpreadPoints=30.00,
  displayed ~300.0 points" matches a 3-digit reading exactly.
- **Hypothesis B (server timezone) is DISPROVEN at source; hypothesis A**
  (session veto intended outside the 10-22 EAT window) **remains possible for
  the SESSION line; the SPREAD line is the proven defect.**

**Feature-level parity proof (independent, decisive):**
Python training fixture `v38_2_feature_parity_fixture.json` stores f41
("SPREAD") in PRICE units: sample values 0.3378 / 0.263 / 0.2784 / 0.505 /
0.391 (i.e., $ spreads). The training dataset `v38_2_dataset_M5_H1_lb240`
f_spread: min=0.10, p50=0.36, p90=0.66, p99=1.53, max=11.47 — non-integer.
The old MQL5 fed `SYMBOL_SPREAD` (integer point count) into feature 41 —
a unit bug confirmed ON FIXTURE GROUND TRUTH. On the 20-sample fixture the
shift in calibrated probability was max |Δ|=0.071 / mean |Δ|=0.014 — enough
to flip borderline decisions around the 0.50 threshold.

**FIX (minimal):**
- Gate now: `spread_price = ask−bid` vs cap `InpMaxSpreadPoints ×
  InpMaxSpreadRefPoint`. Default ref point 0.01 makes the default cap $0.30
  — IDENTICAL semantics on 2-digit symbols (no regression on dev), canonical
  intent restored on 3-digit. NOT an arbitrary limit increase (rule 14):
  the same $0.30 canonical intent; the change is dimensionless-unit repair.
- Feature 41 now: `SYMBOL_SPREAD × SYMBOL_POINT` (price $) — training-parity
  restore (verified numerically above; does NOT touch the 50-feature
  contract, index order, labels, or threshold).

Decision once user runtime evidence lands (harness §8):
- `digits=2` + spread > $0.30 at veto times → spread gate was intended
  protection; fix harmless (same verdicts).
- `digits=3` → legacy verdict proven defective; normalized verdict governs.
The harness now prints `legacy` vs `norm` verdicts side by side so this is
decidable from the log alone.

---

## 5. SESSION ENGINE AUDIT (Phase 5)

One lookup site (`SessionEAT()`), `TimeGMT()+10800` → hour ∈ [10,22).
Findings:
- **Strategy Tester:** per the official MQL5 documentation
  ("Testing Trading Strategies", mql5.com/en/docs/runtime/testing):
  "During testing, the local time TimeLocal() is always equal to the server
  time TimeTradeServer(). In turn, the server time is always equal to the
  time corresponding to the GMT time - TimeGMT()." — in the tester all four
  clocks coincide with SIMULATED server time. Therefore the EAT conversion
  is deterministic and correct in the tester; SESSION vetoes there are
  outside-window behaviour only.
- **Live terminal:** TimeGMT() is PC-clock GMT (DST-adjusted per the
  PC's DST calendar) — possible 1-hour seasonal wobble of the EAT edge.
  Documented, NOT changed (frozen window); `DumpTimeSources()` logs all four
  clocks + computed EAT hour + verdict once per new bar, so the live wire is
  observable directly.
- Session enc features 42/43 use **the bar timestamp** (UTC-shifted hour
  bands matching Python `session_defs` in config.py) — they are
  time-DERIVED, not gate-relevant; verified identical to training.

No session-engine defect found; no change made to the gate.

---

## 6. SESSION LOGIC EDGE CASES (Phase 6) — truth table

| Case | SessionEAT semantics | Verdict path |
|---|---|---|
| Within-day (10≤start<h end 22) | h∈[10,22) → pass | deterministic |
| Midnight-crossing (start>end) | h≥start OR h<end | OR-branch exists (L350-351) |
| Start==End | filter bypassed (24h) | explicit guard |
| DST-sensitive | live PC-DST wobble ≤1h | logged by DumpTimeSources |
| Weekend / closed | no ticks → `VETO: NO TICK` counted | enum VETO_NO_TICK |
| Broker session slots | printed via SymbolInfoSessionTrade | harness `[SESSIONSCHEDULE]` |
| Tester | all clocks ≡ simulated | deterministic |
| Live | PC-GMT | deterministic (audit note) |

`InpUseSessionFilter=false` → session gate skipped, counted only when active.

---

## 7. DATA / MODELLING DATA AUDIT (Phase 7) — full feature classification

All 50 generator sites audited in FeatureEngine/Structure:

| Family | Indices | Class |
|---|---|---|
| Regime/structure events, protected levels, legs | 0-11 (12) | OHLC-derived |
| Liquidity pools/sweeps, EQH/EQL, inducement | 12-18 (7) | OHLC-derived |
| Order blocks | 19-26 (8) | OHLC-derived |
| FVG | 27-32 (6) | OHLC-derived |
| Premium/discount | 33-36 (4) | OHLC-derived |
| ATR, ATR-percentile, daily-range, vol-regime | 37-40 (4) | OHLC-derived |
| **SPREAD (41)** | **tick/spread-derived (unit-fixed §4)** |
| Session encode/phase (42,43) | time-derived (UTC hour bands) |
| HTF/LTF alignment (44,45) | OHLC + direction |
| distance-to-entry, SL/TP dist, RR (46-49) | OHLC-derived geometry |

No volume/tick-volume-derived feature exists (the engine feeds `SYMBOL_SPREAD`
per bar into `m_spread[]` but it is unread downstream — benign dead storage).
**Only feature 41 needs tick information; M1-OHLC tester modelling is
sufficient for 49/50 features but NOT sufficient as final validation** —
the spread gate itself is tick-level sensitive (§8).

---

## 8. EXNESS REAL-TICK TEST (Phase 8) — BLOCKED, user instructions

BLOCKED in this sandbox: no Wine/MT5 (`which wine` empty; no apt package
lists), and the previous environment's Exness authorization failed
("Invalid account", VETO_ROOT_CAUSE_AUDIT §7a) — an external credential
blocker, not tooling.

Exact minimal sequence for the user's native MT5 (required for closure):
1. MetaEditor GUI → compile `V38_2_EA.mq5` (0 errors expected; CLI under
   Wine spuriously fails #resource per prior note). Replaces stale ex5 38.22.
2. Strategy Tester → XAUUSDm, M5, **"Every tick based on real ticks"**,
   `InpTradingEnabled=false` observation. Collect the deinit VETO MATRIX.
3. Attach `V38_2_GateDiagnostic.mq5` or the EA (`InpBrokerDiagnostics=true`)
   to an XAUUSDm chart → capture `[SYMBOL]` (digits/point), `[TIME]`,
   `[SESSIONSCHEDULE]`, `[GATES] legacy vs norm` verdicts.
4. If `[SYMBOL] digits=2`: investigate real spread level at veto times.
   If `digits=3`: normalized gate is the resolution (already in 38.23).

Open Prices Only / M1-OHLC modes are explicitly inadequate for this final
validation (tick-sensitive spread gate).

---

## 9. FEATURE PIPELINE VALIDATION (Phase 9)

`V38_FEATURE_NAMES[50]` constant table in the EA pins names↔indices to the
frozen contract. `InpDumpFeatures=true` emits exactly ONE full
`[FEATURES]`/`[F00]-[F49]` dump per EA run (first evaluated candidate) with
value + index + name. The canonical fixture (20 samples) + the parquet
dataset were used to prove the f41 units; ONNX input shape [None,50]
re-verified in onnxruntime (inputs: float [None,50]; outputs label +
probabilities [N,2]).

---

## 10. FIXES APPLIED (evidence → change → verification)

| # | Defect (proven) | Change (minimal) | Evidence | Rollback |
|---|---|---|---|---|
| F1 | f41 unit mismatch (points vs $) | points×point → price $ | fixture values in $; dataset p50=0.36; Δcal max 0.071→0 | revert FeatureEngine L439-440 |
| F2 | spread gate unit ambiguity | price cap (identical on 2-digit) | audit §4; harness dual verdict | gate compares old points formula |
| F3 | single-veto HUD loses history | veto matrix + deinit summary | new counters; deinit block | non-behavioural; remove counter lines |

Non-modifications honoured: readiness_gate.py, feature_contract.py, PIT
rules, 72h/240-bar labels, threshold 0.50, session 10-22 EAT, risk controls,
ONNX/calibrator, 50-feature contract/order. No martingale/grid/recovery. No
bypass of margin/retcode checks.

---

## 11. STATUS

- **ROOT CAUSE (spread veto):** PROVEN defect class — `_Point`-dependent
  point-count unit mismatch (F1/F2) while session vetoes are intended
  behaviour. Decision of which digit-case XAUUSDm is lies with the user's
  first `[SYMBOL]` capture (one log line).
- **PRODUCTION READY: NO.** Compile + real-tick observation on native
  Windows required (§8); previous session's in-environment attempt reached
  equal status G10-PASS/G11,G12-BLOCKED. This session's in-sandbox gate
  upgrades are source-level; runtime verification remains BLOCKED here.
- **CANONICAL ML MODIFIED: NO.** **MODEL/ONNX/CALIBRATOR MODIFIED: NO.**
- Next gate: user's native MT5 sequence §8 → VETO MATRIX summary decides.

---

## 12. ADDENDUM — G9 RECOMPILE PASS, G10-G12 BLOCKED (2026-08-26, build 38.23)

Environment re-provisioned from scratch this session: Wine 10.0
(Debian 10.0~repack-6, win64), Xvfb, MT5 build 6140 installed via
`mt5setup.exe /auto` into a fresh prefix (`.tools/wineprefix`, portable
mode, install root `C:\Program Files\MetaTrader 5`).

**G9 — COMPILE: PASS (runtime evidence, not source audit).**
- First CLI attempt failed only because a bare prefix has no
  `MQL5\Include\Trade\Trade.mqh` (standard library absent): 1 error,
  `error 106: file 'Include\Trade\Trade.mqh' not found`. Launching
  `terminal64.exe` once self-updated the terminal and downloaded the full
  standard library (453 files updated, per terminal log).
- `MetaEditor64.exe /compile:"MQL5\Experts\V38_2\V38_2_EA.mq5" /log` then
  produced: **`Result: 0 errors, 0 warnings`**, 2412 ms. The earlier
  build-38.22 caveat ("CLI /compile spuriously fails #resource with
  error 313") did NOT reproduce — CLI compile with `#resource` works
  once the standard library is present.
- Embedded resources confirmed in the build log:
  `v38_2_final_model.onnx` as `g_onnx_data[927383]`,
  `v38_2_calibrator.json` as `g_cal_data[4107]`.
- Output: `V38_2_EA.ex5`, 408,114 bytes,
  sha256 `e65581435f3d23e69c659f02aa5ec2a34db8957c36adf2744af6ee2f14d2f2ce`.
  This binary replaces the stale build-38.22 ex5 in the repo. Build log:
  `backend/models/v38_2/mql5/build_logs/V38_2_EA_compile_38.23.log`.
- `V38_2_GateDiagnostic.mq5` also compiled: 0 errors, 0 warnings.
- Canonical artifact hashes re-verified unchanged before and after the
  compile step (ONNX `3f004d9f…`, calibrator `5ba026a3…`).

**G10-G12 — RUNTIME: BLOCKED in this sandbox (root cause: account auth).**
- `terminal64.exe /portable /config:v38_2_obs.ini` (Tester section:
  XAUUSD M5, Model=0 real ticks, observation inputs) exits with
  `tester not started because the account is not specified`
  (exit code -1000012353). The tester agent requires the terminal to be
  authorized on a trading account; the fresh prefix has none.
- MetaQuotes-Demo demo-account creation was attempted via the terminal
  GUI under Xvfb/xdotool. The registration form's Mobile Phone
  combobox cannot be satisfied under Wine: typed/pasted digits land
  inside the country-label parentheses (caret defect) and the control's
  validation (`Required`) never clears regardless of format
  (10/11 digits, with/without `+1`, country pre-selected). ~25 GUI
  attempts, all rejected; `Next >` stays disabled.
- Prior session's MetaQuotes-Demo logins (10012356505, 5054961853) have
  no recoverable passwords; Exness account 476553066 credentials are not
  in the repo/environment.

**Remaining verification path (unchanged, §8):** native Windows MT5 with
a valid demo/broker login → attach build-38.23 ex5 (this commit's binary)
→ observation run on XAUUSDm M5 "Every tick based on real ticks" →
collect `[SYMBOL]` digits line, dual-verdict `[GATES]` spread line, and
the deinit VETO MATRIX summary.
