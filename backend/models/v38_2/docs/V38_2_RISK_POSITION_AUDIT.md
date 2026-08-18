# V38.2 Risk Engine + Position Management Audit

**Created:** 2026-08-18
**V37 reference:** `IGOF_SMC_MASTER_V37_PRODUCTION.mq5` (full source)
**V38.2 EA:** `mql5/V38_2_EA.mq5`

## 1. Risk engine — V37 preserved

| Mechanism | V37 | V38.2 | Status |
|---|---|---|---|
| Risk money | `equity * InpRiskPerTradePct/100` | same | PRESERVE |
| Lot sizing | `CalcLot` 40-iter binary search via `OrderCalcProfit` | identical | PRESERVE |
| Volume normalization | `VolDown` (step/min/max floor) | identical | PRESERVE |
| Margin validation | `OrderCalcMargin` ≤ `free margin * 0.95` | identical | PRESERVE |
| Risk overshoot guard | `abs(loss) > risk*1.001` → reject | identical | PRESERVE |
| SL distance | `max(ATR*mult, max(stops,freeze)+2pt)` | identical (`InpUseATR_SL_FromFeatures=false` default → V37 path) | PRESERVE |
| Stops level | `SYMBOL_TRADE_STOPS_LEVEL` | identical | PRESERVE |
| Freeze level | `SYMBOL_TRADE_FREEZE_LEVEL` | identical | PRESERVE |
| Price normalization | `NormalizeDouble(_, _Digits)` | identical | PRESERVE |

## 2. Position management — V37 preserved

| Mechanism | V37 | V38.2 | Status |
|---|---|---|---|
| Partial close | at `+InpPartialRR` (2R), fraction `InpPartialFraction` (0.50) | identical, gated by `!InpUseHardTP` | PRESERVE (+ TP-race fix) |
| Break-even | `PositionModify(t, op, 0)` after partial | identical | PRESERVE |
| Trailing | `ATR*InpTrailATRmult` (1.5), step `InpTrailStepPoints` (20) | identical | PRESERVE |
| Trailing gate | after partial (`part` flag) | identical | PRESERVE |
| Trailing stops check | `cp-target >= minStop` | identical | PRESERVE |
| Reduce (hedging) | `Trade.PositionClosePartial` | identical | PRESERVE |
| Reduce (netting) | manual `OrderSend` IOC opposite deal | identical | PRESERVE |
| Persistent R | `GlobalVariable R_<id>` | identical | PRESERVE |
| Persistent partial flag | `GlobalVariable P_<id>` | identical | PRESERVE |
| R recovery on restart | `r = abs(op - sl0)` if GV missing | identical | PRESERVE |
| Emergency close | 3-pass magic-filtered `PositionClose` | identical | PRESERVE |
| Duplicate prevention | `OurPosition` magic+symbol | identical | PRESERVE |

## 3. Drawdown protection — V37 preserved

| Mechanism | V37 | V38.2 | Status |
|---|---|---|---|
| Daily reference equity | `DailyStartEquity` from GV `DailyRef` | identical | PRESERVE |
| Day boundary | `EATDayStart` (UTC+3 midnight) | identical | PRESERVE |
| Daily DD | `max(0,(start-equity)/start*100)` | identical | PRESERVE |
| Total reference | `TotalReferenceEquity` from GV `TotalRef` | identical | PRESERVE |
| Total DD | `max(0,(total-equity)/total*100)` | identical | PRESERVE |
| Daily lock | `DailyLock` GV; `EmergencyClose` if `InpCloseOnDailyLimit` | identical | PRESERVE |
| Trade cap | `TradesToday` (GV `TradeCount`) `>= InpMaxTradesPerDay` | identical | PRESERVE |
| Manual reset | 'R' key clears daily state | identical | PRESERVE |

## 4. Edge cases (must be exercised in MT5 Strategy Tester)

| Case | Expected behavior |
|---|---|
| Very small account / min lot | `CalcLot` returns `VolDown(step)`; `abs(loss) > risk*1.001` → reject (no trade) |
| Insufficient margin | `OrderCalcMargin` > `free*0.95` → reject |
| Huge ATR | SL distance large → lot small → trade allowed if margin OK |
| Tiny ATR | `max(ATR*mult, stops+2pt)` keeps SL ≥ broker min |
| Large spread | `(ask-bid)/_Point > MaxSpread` → VETO |
| Large stops level | `MathMax(minStop, freeze)+2pt` enforced |
| Missing R GV (restart) | recovered from `abs(op-sl0)` |
| Netting vs hedging | `Reduce` branches on `ACCOUNT_MARGIN_MODE` |

Gate G13 (risk) = PASS at source level; runtime edge-case tests pending in MT5.
Gate G14 (position management) = PASS at source level; runtime + restart tests
pending in MT5.

## 5. No-ML-bypasses-risk check

The ML layer (`PredictWin` + threshold) runs **before** `OpenTrade` and only
sets `S.status`/`bestCalProb`; it never touches `CalcLot`, `OrderCalcMargin`,
drawdown, session, spread, trade-cap, or emergency-close. Risk controls are
evaluated in `OnTick` **before** the candidate loop and again inside
`OpenTrade`/`Manage`. ML approval cannot bypass any risk gate. (Section 13 ✓)
