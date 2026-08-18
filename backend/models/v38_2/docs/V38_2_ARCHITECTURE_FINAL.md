# V38.2 Architecture Final

**Created:** 2026-08-18

## 1. V37 baseline architecture

V37 (`IGOF_SMC_MASTER_V37_PRODUCTION.mq5`) operational engine:
- Risk: `CalcLot` binary search via `OrderCalcProfit`, `OrderCalcMargin` margin
  check, `VolDown` broker volume normalization.
- SL: `max(ATR*mult, max(stops,freeze)+2pt)`, `NormalizeDouble`.
- Position management: partial close 50% at +2R, break-even (`PositionModify` to
  `op`), ATR*1.5 trailing with 20-pt step (after partial).
- Drawdown: daily (EAT midnight) + total, `EmergencyClose` 3-pass.
- Trade cap, duplicate prevention (magic+symbol), one-trade-per-bar.
- Session EAT (UTC+3), spread (points), news blackout (FILTER_ONLY).
- Persistent state via `GlobalVariable` (`R_<id>`, `P_<id>`, `DailyRef`,
  `TotalRef`, `DailyLock`, `TradeCount`, `Day`).
- Signal: H1 breakout `HTFBias` + M5 FVG/displacement `Bull/BearSetup` + 8-feat
  ONNX (resource buffer) threshold 0.72.
- HUD/Comment status; 'R' manual reset.

## 2. V38.2 additions (intelligence layer)

- `CV38_2StructureEngine` (`V38_2_Structure.mqh`): swings/BOS/CHOCH/OB/FVG/
  liquidity/protected-levels/PD/regime with O(1) per-bar precomputed query arrays.
- `CV38_2FeatureEngine` (`V38_2_FeatureEngine.mqh`): `BuildVector` assembles the
  canonical 50-feature float32 vector (PRICE_INDICES, excludes 6 MACRO_NEWS).
- ONNX: `v38_2_final_model.onnx` (50 feats, TreeEnsemble, opset 9) loaded via
  `OnnxCreate`; `OnnxRun` → `label[1]` + `proba[2]`; raw P(class=1) = `proba[1]`.
- `CV38Calibrator` (`V38_Calibrator.mqh`): isotonic post-ONNX mapping (85 points,
  clip boundaries, linear interp), JSON keys case-insensitive.
- ML threshold 0.50 on calibrated probability; `InpProbThreshold`, `InpMinRR`,
  `InpUseATR_SL_FromFeatures`, `InpUseHardTP` inputs.

## 3. V37 components PRESERVED (unchanged)

Risk engine, CalcLot, VolDown, OrderCalcProfit/Margin, SL methodology, stops/
freeze levels, Manage (partial + break-even + trailing), Reduce (hedging/netting),
EmergencyClose, DailyReset, DailyDD, TotalDD, EATDayStart, SessionEAT, spread
filter, news engine (FILTER_ONLY), OurPosition, TradesToday, GlobalVariable
persistence, CTrade + magic + deviation + filling, TradeOK retcode check, HUD,
OnChartEvent 'R' reset, one-trade-per-bar. See `V38_2_V37_REFERENCE_AUDIT.md`.

## 4. V37 components MODIFIED (documented)

| Component | Change | Reason |
|---|---|---|
| OpenTrade TP | `tp=2R` → configurable `InpUseHardTP` (default `false` → `tp=0`) | Fixed TP/partial-close race (§5 of V37 audit); default restores V37 managed exit |
| Manage partial-close | gated by `!InpUseHardTP` | Avoid race with hard TP at same +2R level |
| Session filter | gated by `InpUseSessionFilter` | Made configurable (default true = V37) |

## 5. V37 components REPLACED (signal layer only)

| V37 | V38.2 | Reason |
|---|---|---|
| 8-feature ONNX (resource buffer, [1,8]→[1,1]) | 50-feature ONNX (file, [1,50]→label+proba) + isotonic calibrator | Validated V38.2 ML model supersedes V37 hand-built AI |
| `HTFBias` H1 2-bar breakout | `RegimeStrAt` (regime tracking) | V38.2 StructureEngine regime |
| `Bull/BearSetup` FVG+displacement | `IsCandidateSetup` (alignment+confluence+PD+liquidity+quality) | V38.2 candidate detection |
| `AI(bias)` threshold 0.72 (raw) | `PredictWin(feat)` threshold 0.50 (calibrated) | V38.2 intelligence layer |

## 6. Why each modification occurred

1. **TP/partial-close race:** V37 used `tp=0` (managed exit); the prior V38.2
   draft added `tp=2R` *and* kept partial-close@2R, so the broker TP would fire
   before `Manage()` could run — contradicting V37 and wasting validated
   management. Fix: make hard-TP optional (default off = V37).
2. **`InpUseSessionFilter`:** V37 always filtered; exposing the toggle is a
   non-behavioral change (default true) enabling controlled experiments.
No other operational behavior was changed.

## 7. Feature pipeline
`market data → StructureEngine → IsCandidateSetup → BuildVector (50 feats) → ONNX`

## 8. ONNX pipeline
`50 float32 → OnnxRun → label[1] int64 + proba[2] float32 → raw P = proba[1]`

## 9. Calibration pipeline
`raw P → IsotonicMap (case-insensitive JSON keys, clip boundaries) → calibrated P`

## 10. Risk pipeline
`equity*risk% → CalcLot binary search → OrderCalcProfit/Margin → stops/freeze → lot`

## 11. Execution pipeline
`ML approve → OpenTrade (SL, optional TP) → Manage (partial@2R + BE + trail)`

## 12. Position-management pipeline
`PositionGetTicket → R/P GV → partial close → break-even → trailing → emergency`

## 13. Error-handling pipeline
Every ONNX/SymbolInfo/OrderCalc/Calendar/File API call checked; failures logged
via `Print` + `S.status`, fail safe (no trade).

## 14. Verification results

See `V38_2_FINAL_CLOSED_LOOP_VERIFICATION_REPORT.md` (G1-G20). Summary:
- Python/ONNX/calibration parity: PASS (runtime).
- Feature/structure/bar/risk/filters parity: PASS at source level.
- MQL5 compile + Strategy Tester: BLOCKED (no MT5 in env).

**V38.2 did NOT unnecessarily redesign V37.** Only the signal-generation layer
was replaced (as mandated); the operational engine is preserved intact, with the
single documented TP/partial-close fix and the configurable session toggle.
