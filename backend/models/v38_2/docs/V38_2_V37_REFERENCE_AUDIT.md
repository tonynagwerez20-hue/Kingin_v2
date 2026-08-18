# V38.2 V37 Reference Audit

**Created:** 2026-08-18
**Purpose:** Source-to-source mapping of V37 → V38.2 before any architectural change.
**V37 reference source:** `IGOF_SMC_MASTER_V37_PRODUCTION.mq5` (full source supplied by user).
**V38.2 EA source:** `mql5/V38_2_EA.mq5`.

> This audit was produced by reading the complete V37 source and mapping every
> major V37 component to its V38.2 counterpart. No architectural change was made
> before this table existed (per Section 31 of the engineering prompt).

## 1. V37 Operational Flow ( OnInit → OnTick → OnChartEvent )

| Step | V37 Function | V38.2 Counterpart | Action | Reason |
|---|---|---|---|---|
| Init | `OnInit` | `OnInit` | PRESERVE + EXTEND | ATR handle, GV prefix, TotalRef, DailyReset preserved; structure/calibrator/ONNX added |
| Deinit | `OnDeinit` | `OnDeinit` | PRESERVE + EXTEND | OnnxRelease/IndicatorRelease/Comment preserved; stats print added |
| Tick | `OnTick` | `OnTick` | PRESERVE flow | Same 18-step ordering preserved (see §2) |
| Event | `OnChartEvent` (R reset) | `OnChartEvent` | PRESERVE | Manual daily-state reset on 'R' key preserved |

## 2. OnTick Step-by-Step Mapping

| # | V37 step | V38.2 step | Action |
|---|---|---|---|
| 1 | `DailyReset()` | `DailyReset()` | PRESERVE |
| 2 | `Manage()` (partial+trailing) | `Manage()` | PRESERVE (see §5 defect note on TP/partial race) |
| 3 | DailyDD/TotalDD/DailyLock → `EmergencyClose()` | same | PRESERVE |
| 4 | `SessionEAT()` | `SessionEAT()` | PRESERVE |
| 5 | Spread filter | Spread filter | PRESERVE |
| 6 | `NewsBias()` | (removed) | REPLACE — V38.2 uses PIT-blocked MACRO_NEWS=0; news engine kept for FILTER_ONLY blackout |
| 7 | News blackout (FILTER_ONLY) | News blackout (FILTER_ONLY) | PRESERVE |
| 8 | Pre-news window block | Pre-news window block | PRESERVE |
| 9 | `OurPositionExists()` | `OurPositionExists()` | PRESERVE |
| 10 | `TradesToday() >= MaxTradesPerDay` | same | PRESERVE |
| 11 | New-bar check (`bar == LastTradeBar`) | same | PRESERVE |
| 12 | `HTFBias()` (H1 breakout) | `g_ltf.RegimeStrAt(ltfBar)` | REPLACE — V38.2 regime tracking via StructureEngine |
| 13 | `BullSetup()/BearSetup()` (FVG+displacement) | `g_ltf.IsCandidateSetup(ltfBar, dir)` | REPLACE — V38.2 candidate detection |
| 14 | News-mode validation (TRADE/HYBRID) | (removed for default OBS) | REPLACE — V38.2 default OBSERVATION; news modes preserved as inputs |
| 15 | `AI(bias)` 8-feature ONNX | `PredictWin(feat)` 50-feature ONNX + calibrator | REPLACE — V38.2 intelligence layer |
| 16 | AI threshold 0.72 | `InpProbThreshold` 0.50 (calibrated) | REPLACE |
| 17 | `OpenTrade()` | `OpenTrade()` | PRESERVE (see §4) |
| 18 | `HUD()` | `HUD()` | EXTEND (adds ML info) |

## 3. Component Mapping Table

| V37 Component | V37 Function | V38.2 Action | Reason |
|---------------|--------------|---------------|--------|
| Risk engine | `CalcLot`, risk=`equity*risk%` | PRESERVE | Binary search + OrderCalcProfit is broker-accurate; no defect |
| Position sizing | `CalcLot` (40-iter binary search) | PRESERVE | Margin validation via OrderCalcMargin preserved |
| VolDown | `VolDown` (step/min/max) | PRESERVE | Broker volume normalization unchanged |
| Position management | `Manage`, `Reduce` | PRESERVE | Partial + break-even + trailing logic intact |
| Partial close | `Reduce` (hedging `PositionClosePartial`, netting manual `OrderSend`) | PRESERVE | Hedging/netting handling intact |
| Trailing | `Manage` trailing block | PRESERVE | ATR*mult + step + stops-level checks intact |
| Emergency close | `EmergencyClose` (3-pass) | PRESERVE | Magic-filtered close intact |
| Daily DD | `DailyDD`, `DailyReset`, `EATDayStart` | PRESERVE | EAT=UTC+3 day boundary intact |
| Total DD | `TotalDD`, `TotalRef` GV | PRESERVE | Persistent total reference equity intact |
| Trade cap | `TradesToday`, `TradeCount` GV | PRESERVE | Daily count persistence intact |
| Duplicate prevention | `OurPosition`/`OurPositionExists` | PRESERVE | Magic+symbol filter intact |
| Session filter | `SessionEAT` | PRESERVE | EAT hour window intact |
| Spread filter | `(ask-bid)/_Point > MaxSpread` | PRESERVE | Points-based check intact |
| News engine | `LatestNews`, `UpcomingNews`, `RecentHighImpactNews`, `ReactionOK`, `GoldDirection` | PRESERVE (FILTER_ONLY path) | Calendar API + high-impact filter preserved; PIT-safe |
| ATR | `ATR()` via `iATR` handle | PRESERVE (V37 `ATR()`) + V38.2 `g_ltf.ATRAtIdx` | V37 ATR() preserved for risk/SL; V38.2 structure ATR used for features |
| SL calc | `OpenTrade` SL = `max(ATR*mult, stops+freeze+2pt)` | PRESERVE | Broker stops/freeze respected |
| TP | `OpenTrade` tp=0 (no hard TP) | **DEFECT — see §5** | V38.2 added hard TP=2R creating race with partial@2R |
| Persistent state | GlobalVariables `K()`, `G()`, `P()` | PRESERVE | Prefix, R_<id>, P_<id>, DailyLock, TradeCount, DailyRef, TotalRef intact |
| HUD | `HUD`/`Comment` | EXTEND | V37 fields + ML prob/candidates counts |
| Magic isolation | `InpMagic`, `Trade.SetExpertMagicNumber` | PRESERVE | 382001 magic distinct from V37 |
| Deviation | `InpDeviationPoints` | PRESERVE | 50 points preserved |
| Filling mode | `Trade.SetTypeFillingBySymbol` | PRESERVE | Symbol-aware filling intact |
| Trade retcode | `TradeOK` (DONE/DONE_PARTIAL/PLACED) | PRESERVE | Retcode validation intact |
| SMC setup | `BullSetup`/`BearSetup` (FVG+displacement) | REPLACE | V38.2 StructureEngine supersedes simple FVG |
| HTF bias | `HTFBias` (H1 2-bar breakout) | REPLACE | V38.2 regime tracking (bearish/neutral/bullish) |
| AI filter | `AI` 8-feature ONNX (resource buffer) | REPLACE | V38.2 50-feature ONNX (file) + isotonic calibrator |
| AI threshold | `InpAIThreshold=0.72` raw | REPLACE | `InpProbThreshold=0.50` calibrated |

## 4. OpenTrade Comparison (V37 vs V38.2)

| Element | V37 | V38.2 | Status |
|---|---|---|---|
| Price source | `SymbolInfoTick` ask/bid | same | PRESERVE |
| SL distance | `max(ATR*mult, max(stops,freeze)+2pt)` | `max(slDistPrice, max(stops,freeze)+2pt)` | PRESERVE (slDistPrice may be feature-derived if `InpUseATR_SL_FromFeatures`) |
| SL price | `NormalizeDouble(price±dist)` | same | PRESERVE |
| TP price | `0` (no TP) | `price±2*dist` | **CHANGED — defect, see §5** |
| Lot | `CalcLot` | `CalcLot` | PRESERVE |
| Open call | `Trade.PositionOpen(_Symbol,type,lot,0,sl,0,"IGOF_V37")` | `Trade.PositionOpen(_Symbol,type,lot,0,sl,tp,"V38_2")` | PRESERVE signature; TP arg differs (§5) |
| Retcode | `TradeOK` | `TradeOK` | PRESERVE |
| State store | `P(K("R_"..id),dist)`, `P(K("P_"..id),0)` | same | PRESERVE |

## 5. TP / Partial-Close Race — DEFECT

**V37 behavior (authoritative):** `OpenTrade` opens with **tp=0** (no hard take-profit).
Exit is managed entirely by `Manage()`:
- partial close 50% at +2R (`InpPartialRR=2.0`)
- move SL to break-even (`op`) after partial
- trail by `ATR*1.5` with 20-point step

**V38.2 current behavior (defect):** `OpenTrade` sets **tp = price ± 2*dist** (hard TP at +2R)
**AND** `Manage()` still attempts partial close at +2R. Because the broker's hard TP
fires at +2R before `Manage()` can run the partial close, the break-even + trailing
management path is **never reached**. This both contradicts V37 and wastes the validated
management logic.

**Correction (chosen, documented):**
- Add input `InpUseHardTP` (default `false`).
- **MODE A — `InpUseHardTP=false` (CANONICAL, V37-faithful):** open with `tp=0`,
  let partial-close + break-even + trailing manage the exit. This is the V37 behavior
  and is the default so the validated management engine is exercised.
- **MODE B — `InpUseHardTP=true`:** open with hard TP=2R; in this mode the partial
  close at +2R is skipped (it would never fire anyway) and break-even/trailing only
  apply after a manual partial at a different level is configured.

Canonical = MODE A, because the prompt mandates preserving the V37 execution/management
engine and the partial-close+trailing is part of that engine. MODE A also matches the
V38.2 label semantics (label is a *prediction target*, not a broker order).

## 6. V37 Preservation Verdict

V38.2 preserves the V37 operational engine **substantially intact**:
risk sizing, position management, persistent state, drawdown protection, session/spread
filters, news blackout, emergency close, duplicate prevention, trade cap, ATR/SL
methodology, magic isolation, and HUD are all preserved.

The only intentional replacements are the **signal-generation layer**
(V37 8-feature ONNX + simple SMC + H1 breakout → V38.2 50-feature ONNX + StructureEngine
+ regime tracking + isotonic calibration). This is exactly the architecture mandated by
Section 30: V37 risk/execution/management PRESERVED + V38.2 intelligence ADDED.

The single regression to fix is the TP/partial-close race (§5), which is a V38.2
introduction error, not a V37 behavior.
