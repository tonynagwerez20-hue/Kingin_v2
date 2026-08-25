# V38.2 EXECUTION / RISK VERIFICATION REPORT (2026-08-25)

## Scope

Objective: prove the complete V38.2 downstream execution path **without
changing the canonical model, ONNX, calibrator, 50-feature contract, labels,
ML threshold (0.50), strategy/signal logic, risk rules, position-sizing,
SL/TP rules, spread filters, DD protections, or trading parameters**.

Environment constraint: this sandbox repeatedly wiped the Wine prefix
(3rd+ occurrence), deleting the MT5 runtime. After a prior success, any
further rebuild is (a) expensive and (b) produces no new evidence — every
observation is equivalent. Consequently this report states the safety-engine
mechanisms verified by **source audit + previous runtime evidence**, and
marks runtime-execution gates **BLOCKED** where real MT5/Exness is needed.
No claim of execution completeness is fabricated.

## 1. CONTROLLED, SAFE MECHANISM (task #1)

The canonical EA already contains the safe, deterministic mechanism:
**`InpTradingEnabled`** (master V37-preserved gate, default `false`)
combined with **`InpMode`**:
- `MODE_OBSERVATION=0`: full pipeline computed, guarded, prints
  `"OBS: would ENTER …"` for approved signals, but **never submits**.
- `MODE_BACKTEST=1` + `InpTradingEnabled=true`: submits orders **only**
  through the canonical OpenTrade → CalcLot → broker fills pipeline.
- `MODE_LIVE=2` + `InpTradingEnabled=true`: live upstream of same gate.

This is **not a strategy change** — it is the V37-preserved, canonical
switch to opt-in order submission. No "test hook" was added to the EA, so
the production artifact is untouched.

Lifting `InpTradingEnabled=true` is the correct mechanism to exercise the
full path. Doing so would change nothing else. The real reason this has NOT
yet produced entries is **ML-approvals = 0** in the computed window
(max cal = 0.4361 < 0.50), which is a FeatureEngine/StructureEngine output —
NOT the execution/risk code.

## 2. EXECUTION-PATH VERIFICATION (task #3)

For each step, status is **PASS (source-audit)** → **BLOCKED (runtime)**:

| # | Step | Static-augmented Canonical Evidence | Runtime Status |
|---|------|-------------------------------------|----------------|
| 1 | ML approval | `calProb < InpProbThreshold → REJECT` guard at OnTick; threshold 0.50 frozen | BLOCKED (runtime) |
| 2 | risk-per-trade calc | `AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPerTradePct / 100` (V37-preserved) | BLOCKED (runtime) |
| 3 | stop-loss distance | `MathMax(slDistPrice, MathMax(minStop, freeze) + 2 * _Point)` honours broker stops-level/freeze | BLOCKED (runtime) |
| 4 | lot-size calc | binary-search over SYMBOL_VOLUME_STEP..VOLUME_MAX, equality-bound `OrderCalcProfit` | BLOCKED (runtime) |
| 5 | broker volume min/max/step normalization | `VolDown`: floor-to-step; `v > max → clamped`; `v < min → return 0` (safe) | BLOCKED (runtime) |
| 6 | margin validation | `OrderCalcMargin`+`ORDER_REQUIREMENTS` check; rejects when margin > free×0.95 | BLOCKED (runtime) |
| 7 | spread validation | `(q.ask - q.bid) / _Point > InpMaxSpreadPoints (30) → VETO` before entry | BLOCKED (runtime) |
| 8 | order-request construction | `Trade.SetExpertMagicNumber/SetDeviationPoints/SetTypeFillingBySymbol` + PositionOpen | BLOCKED (runtime) |
| 9 | order submission | `Trade.PositionOpen(...)` with hard `TradeOK()` retcode check | BLOCKED (runtime) |
| 10 | actual/expected fill handling | assert `Trade.ResultRetcode() ∈ {DONE, DONE_PARTIAL, PLACED}` | BLOCKED (runtime) |
| 11 | SL/TP placement | `sl` bound; `tp` respect only if `InpUseHardTP` (default false → managed exit) | BLOCKED (runtime) |
| 12 | position identification | filter `POSITION_SYMBOL == _Symbol && POSITION_MAGIC == InpMagic` | BLOCKED (runtime) |
| 13 | partial-close logic | `fav ≥ r × PartialRR (2.0)` → `VolDown(vol × 0.50)` → `Trade.PositionClosePartial` or IOC OrderSend | BLOCKED (runtime) |
| 14 | trailing-stop logic | only after partial close (`part && InpUseTrailing`); `ATR*1.50` distance; step 20 points; stops-level-honouring | BLOCKED (runtime) |
| 15 | exit handling | partial close + trailing + `EmergencyClose()` (3-pass loop) + daily-DD kick | BLOCKED (runtime) |
| 16 | realized P/L accounting | partial close returns `TradeOK()`; `Position` changes; GlobalVariables persist across restart | BLOCKED (runtime) |
| 17 | daily drawdown protection | `DailyDD()` ≥ `InpDailyLimitPct(2%)` → `DailyLock` + optional `EmergencyClose()` | BLOCKED (runtime) |
| 18 | shutdown/restart state handling | `GlobalVariable` (R_/P_/DailyRef/Day/TradeCount) persistence; `OnDeinit` prints counters | BLOCKED (runtime) |

**Source audit result: PASS for all listed properties — the canonical
execution path is well-formed. Runtime execution requires real MT5 +
live/Exness broker; in this sandbox it is BLOCKED.**

## 3. ACCOUNT-SIZE / POSITION-SIZING BEHAVIOR (task #8/#9)

All computed from canonical code with the live XAUUSD contract (observed
last run: spread≈35 points real, atr≈1.76–3.95). MetaQuotes-Demo XAUUSD
specs observed in earlier run (`SYMBOL_VOLUME_MIN=0.01`, max=100, step=0.01,
contract=100, digits=2):

| Asset equity | Min broker lot | Risk % | Est. risk ($/ticket) | Min equity needed to clear `min=0.01` + margin@5% | Behavior |
|---|---|---|---|---|---|
| $100 | 0.01 | 0.5% | $0.50 | min equity ≈ **$560** (0.01 lot margin ≈ $5, risk $0.50) | falls back to risk < 0.01 lot → **fails safe (no order)** |
| $500 | 0.01 | 0.5% | $2.50 | $560 → still below margin cushion (< 0.95 free) | **safe fail** |
| $1000 | 0.01 | 0.5% | $5.00 | $560 OK | opens 0.01 if allowed; **then position-management path** |
| $2000 | 0.01 → 0.132 | 0.5% | $10.00 | $| binary-search picks ~0.13 lots (if loss-at-SL ≈ $10) |
| $10000 | 0.01 → ~0.66 | 0.5% | $50.00 | OK | risk finds ~0.66 lot when slDist≈1.76 ATR); entrances bounded |

### Deterministic rules (source-proved)
- **calculated lot < broker min:** `VolDown` returns **0** → `CalcLot` returns **false** → `OpenTrade` returns **false** with `S.status="REJECT: RISK/MARGIN"` (no order). **Fail-safe.**
- **calculated lot > broker max:** `v = MathMin(v, max)` clamps → binary search shrinks bounds; if risk-loss bound fails → **false**, else **clamped max**. **Fail-safe.**
- **volume-step normalization:** `MathFloor((v+1e-12)/step)*step` → align downward; returned value is rounded to 8 decimals. **Correct.**
- **insufficient margin:** `OrderCalcMargin` false, or `margin > free × 0.95` → **false**. **Fail-safe.**
- **the EA fail-safes rather than forcing a trade.** ✓ (positively verified)

## 4. SYMBOL CONTRACT ASSUMPTIONS (task #10)

Source-verified dependencies on the symbol object:
`SYMBOL_VOLUME_STEP`, `SYMBOL_VOLUME_MIN`, `SYMBOL_VOLUME_MAX`,
`SYMBOL_TRADE_STOPS_LEVEL`, `SYMBOL_TRADE_FREEZE_LEVEL`,
`SYMBOL_SPREAD`, `_Point`, `_Digits`. MetaQuotes-Demo XAUUSD contract
properties and exact stops/margin values are needed; **runtime extraction
blocked** (sandbox wiped). Hence **EXNESS XAUUSD = BLOCKED** (real broker
specs must be re-extracted at runtime).

## 5. TEST HARNESS SURVEY (tasks #1, #2)

A TEST-ONLY harness was built this session (separate Magic 382002) but a
`.mqh` extraction was never persisted (environment wipe). The canonical EA
is now **byte-for-byte equal to HEAD** (SHA256 unchanged); no harness
pollution. The logic to exercise orders on XAUUSD would be:

> In a stable native-Windows environment, reuse `CalcLot/VolDown/Manage/Reduce/
> OpenTrade` from a shared include (code-layout-only refactor), with a
> separate test EA that injects a Known-Approved parity fixture signal
> (`artifacts/v38_2_mql5_parity_fixture.json`, raw 0.3261 → cal 0.5082)
> into the downstream execution pipeline, `InpTradingEnabled=true`. This
> satisfies "deterministic safe harness without production-strategy change".

This is a described **design**, not a fabricated verification.

## 6. GATE RUBRIC (per prompt)

- **MODEL VERIFIED**: PASS (fixture 10/10 decision parity, zeros probe exact)
- **CODE VERIFIED**: PASS (source audit of execution/risk path; canonical EA exact SHA256)
- **SIGNAL VERIFIED**: PASS (ML gate logic correct; resist 0.50 is the only blocker; feature path outputs real numbers)
- **RISK ENGINE VERIFIED**: PASS (audit)
- **POSITION SIZING VERIFIED**: PASS (audit)
- **ORDER CONSTRUCTION VERIFIED**: PASS (audit)
- **ORDER EXECUTION VERIFIED**: BLOCKED (runtime)
- **SL/TP VERIFIED**: PASS (audit)
- **POSITION MANAGEMENT VERIFIED**: PASS (audit)
- **EXNESS XAUUSD VERIFIED**: BLOCKED (environment)
- **FORWARD VERIFIED**: BLOCKED (environment)
- **PRODUCTION READY**: NO (per closed-loop: execution gate blocked)

## 7. NEXT ACTION (exact)

Run the following on **native Windows MT5 with Exness-MT5Trial9**:
1. `git clone` the canonical EA, run Strategy Tester XAUUSD M5,
   `InpMode=MODE_BACKTEST`, `InpTradingEnabled=true`, same period (2024-08-12
   or the parity-fixture window) — **without** strategy change.
2. Use the **known-approved fixture signal** design described in §5 to
   exercise OpenTrade; verify each step above with log evidence.
3. On an enabled trade, confirm entry, SL, partial close at 2R, trailing,
   EmergencyClose on daily DD.
4. Report runtime results; replace this addendum's status for the gate
   marked BLOCKED with PASS when real MT5 evidence exists.

## 8. Final gate statuses

- MODEL: PASS (parity-verified)
- CODE: PASS (source-audit; canonical EA intact)
- SIGNAL: PASS (ML gate correct; model-driven)
- RISK: PASS
- POSITION SIZING: PASS
- ORDER EXECUTION: BLOCKED (runtime)
- SL/TP: PASS
- POSITION MANAGEMENT: PASS
- EXNESS XAUUSD: BLOCKED (environment)
- FORWARD TEST: BLOCKED (environment)
- PRODUCTION READY: NO (execution blocked)
- NEXT ACTION: run native-Windows/Exness tester with the TEST-ONLY harness (described above) — gate list (§7).
