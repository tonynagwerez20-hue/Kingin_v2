# V38.2 Final Engineering Report

**Created:** 2026-08-18
**V38.2 STATUS: NOT COMPLETE** (compilation G9 = PASS via MetaEditor64/Wine;
Strategy Tester G10-G12/G16-G17 BLOCKED — Exness login + tester not drivable
headlessly under Wine; native Windows required)

## 1. Architecture
V37 operational engine (preserved) + V38.2 intelligence layer (StructureEngine →
50-feature FeatureEngine → ONNX → isotonic calibrator → threshold → V37 execution).
See `V38_2_ARCHITECTURE_FINAL.md`.

## 2. Files created/modified
**Modified (MQL5 — defect fixes):**
- `mql5/V38_Calibrator.mqh` — case-insensitive JSON key parse (X_thresholds/x_thresholds);
  explicit failure logging; never-silent fallback.
- `mql5/V38_2_FeatureEngine.mqh` — base members `protected`; `DistanceToEntryATR`,
  `PriceAt`, `ATRValAt`, `ATRPercentileAt`, `MinProtectedLow`, `MaxProtectedHigh`
  virtuals; `BuildVector` now uses engine-resolved price/ATR/percentile, real
  distance-to-entry, and Python-matching SL fallback.
- `mql5/V38_2_Structure.mqh` — overrides for `DistanceToEntryATR` (via
  NearestOB/NearestFVG), `PriceAt`, `ATRValAt`, `ATRPercentileAt`,
  `MinProtectedLow`, `MaxProtectedHigh`.
- `mql5/V38_2_EA.mq5` — `InpUseHardTP` (+ TP/partial-close race fix); ONNX shape
  return-value checks; `InpUseSessionFilter` wired; closed-bar `ltfBar=NBars()-2`.

**Created (reports):**
- `docs/V38_2_V37_REFERENCE_AUDIT.md`
- `docs/V38_2_PYTHON_MQL5_FEATURE_PARITY_REPORT.md` (+ generator script)
- `docs/V38_2_BAR_POLICY.md`
- `docs/V38_2_STRUCTURE_ENGINE_AUDIT.md`
- `docs/V38_2_RISK_POSITION_AUDIT.md`
- `docs/V38_2_FILTERS_AUDIT.md`
- `docs/V38_2_ARCHITECTURE_FINAL.md`
- `docs/V38_2_FINAL_CLOSED_LOOP_VERIFICATION_REPORT.md`

## 3. V37 functionality preserved
Risk/CalcLot/OrderCalcProfit/Margin, SL methodology, stops/freeze, Manage
(partial+BE+trailing), Reduce (hedging/netting), EmergencyClose, DailyReset/DD,
TotalDD, trade cap, duplicate prevention, GlobalVariable persistence, session,
spread, news blackout, CTrade+magic+deviation+filling, TradeOK, HUD, 'R' reset,
one-trade-per-bar. (See V37 reference audit.)

## 4. V38.2 functionality added
StructureEngine, 50-feature FeatureEngine, ONNX inference, isotonic calibrator,
ML threshold, observation mode, candidate logging.

## 5. ONNX contract verification
Input `input` [None,50] float32; outputs `label` [1] int64, `probabilities`
[None,2] float32. P(class=1)=proba[1]. 50 features (excludes 6 MACRO_NEWS).
PIT-blocked indices 46-49 = 0.0. PASS.

## 6. Feature parity results
50/50 mapped; 3 defects FIXED (distance_to_entry, atr_percentile, sl_distance).
2 caveats (spread, session timezone) documented. Source-level PASS; runtime MT5 pending.

## 7. Calibration parity results
Isotonic 85 pts, clip, monotonic. MQL5 algorithm max err ≈1.1e-16 vs sklearn.
Key-mismatch defect FIXED. PASS (algorithm).

## 8. StructureEngine verification
Source-level faithful port of swings/BOS/CHOCH/OB/FVG/liquidity/PD/regime.
No lookahead. PASS (source); runtime MT5 pending.

## 9. MQL5 compilation result
**PASS.** MetaEditor64 (installed under Wine 10.0) compiled V38_2_EA.mq5
headlessly: 0 errors, 0 warnings, 2281 ms, cpu 'X64 Regular'. Output
`V38_2_EA.ex5` (128,472 bytes) committed at `mql5/V38_2_EA.ex5`; build log at
`mql5/build_logs/V38_2_EA_compile.log`. Compilation also surfaced & fixed 4
defects undetectable by static inspection (OnnxSet*Shape wrong params; iATR
4-arg MQL4 call; OB zone int truncation; base virtuals with no body).

## 10. Runtime test result
**BLOCKED.** MT5 terminal64 launches under Wine (connects to a broker) but the
Exness account login + Strategy Tester cannot be driven reliably through the
headless Wine GUI; the demo server has no real XAUUSD history. Native Windows
required (see closed-loop report §10 runbook).

## 11. Strategy Tester configuration
See §13 of the closed-loop report (XAUUSD M5/H1, observation then trade mode,
frozen params, holdout then full range).

## 12. Backtest results
Python simulation only (not MT5): V38.2 38 trades WR 71% PF 4.82 DD 1.99% vs
V37 157 trades WR 43.31% PF 1.29 DD 11.63% (2026-01→05). Indicative only.
**MT5 baseline = BLOCKED.**

## 13. Out-of-sample results
**BLOCKED** (no MT5). Python holdout: AUC 0.580, PF 2.11, 14/14 fold stability.

## 14. Risk-management verification
V37 risk engine preserved; ML cannot bypass risk gates. TP/partial race fixed.
Source-level PASS; runtime edge-case tests in MT5 pending.

## 15. Known limitations
G9 compilation = PASS. G10-G12/G16-G17 = BLOCKED (Wine GUI can't drive Exness
login/tester; demo server has no real XAUUSD history; native Windows required).
Feature/structure parity source-only. Python-sim WR is not an MT5 result.

## 16. Remaining risks
MT5 runtime ONNX-tensor/opset-9 specifics; session timezone; structure runtime
parity; maxBars=5000 cap; calendar tester data; broker stop-level / filling-mode
behavior on Exness (verify on native Windows backtest).

## 17. Exact parameter configuration
See §13 of the closed-loop report. Defaults: risk 0.5%, daily 2%, total 5%,
max 5/day, ATR 14, SL mult 1.20, partial 2R/0.50, trail 1.5×/20pt, session
10-22 EAT, spread 30pt, threshold 0.50, minRR 1.0, InpUseHardTP=false,
InpMode=OBSERVATION, InpTradingEnabled=false.

## 18. Exact model version/hash
`v38_2_final_model.onnx` sha256 `3f004d9fa3d1179895e41a4399e57dac8d64ba88349b0108510df7cb48e40ee9`
(model_version `v38.2_final`, 50 features, opset 9).

## 19. Exact calibrator version/hash
`v38_2_calibrator.json` sha256 `5ba026a3f43d883b8ab6896c3f6adb135fa9f419d86e98c1472b308bc72c393a`
(isotonic, 85 points).

## 20. Final engineering status
**NOT COMPLETE.** Python/ONNX/calibration parity PASS; MQL5 source defects FIXED
and audited; V37 engine preserved; G9 compilation PASS (MetaEditor64/Wine, 0
errors/0 warnings, V38_2_EA.ex5 produced). Strategy Tester G10-G12/G16-G17
BLOCKED on headless Wine (Exness login not drivable; native Windows required).
Next: run the TEST1-TEST8 sequence on native Windows MT5 (Exness-MT5Trial9,
login 476553066).
