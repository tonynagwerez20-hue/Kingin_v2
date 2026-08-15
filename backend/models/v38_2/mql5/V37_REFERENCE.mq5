//+------------------------------------------------------------------+
//|              IGOF_SMC_MASTER_V37_PRODUCTION.mq5                  |
//|  V37 REFERENCE SOURCE — DO NOT COMPILE OR MODIFY                 |
//|  This is the operational baseline for V38.2 evolution.           |
//|  Preserved here for architecture reference only.                 |
//+------------------------------------------------------------------+
// The full V37 source is preserved in this file as the reference
// baseline. V38_2_EA.mq5 is the evolution of this code.
//
// V37 ARCHITECTURE MAP:
//
// OnInit:
//   - CTrade + magic number
//   - ATR handle (iATR M5 period 14)
//   - GlobalVariable prefix for persistent state
//   - TotalReferenceEquity from GV (persistent)
//   - DailyReset()
//   - ONNX from #resource buffer (lgbm_signal_filter_20y.onnx)
//   - Input shape [1,8], output [1,1]
//
// OnTick flow (exact order):
//   1. DailyReset()
//   2. Manage() — partial close + trailing
//   3. DailyDD / TotalDD / DailyLock check → EmergencyClose()
//   4. SessionEAT() filter
//   5. Spread filter
//   6. NewsBias() computation
//   7. News blackout (NEWS_FILTER_ONLY)
//   8. Pre-news window block
//   9. OurPositionExists() — duplicate prevention
//   10. TradesToday() >= MaxTradesPerDay
//   11. New bar check (one trade per bar)
//   12. HTFBias() — H1 simple breakout
//   13. BullSetup()/BearSetup() — M5 FVG + displacement
//   14. News mode validation
//   15. AI(bias) — 8-feature ONNX
//   16. AI threshold check (0.72)
//   17. OpenTrade()
//   18. HUD()
//
// Key V37 components to PRESERVE in V38.2:
//   - CalcLot: binary search + OrderCalcProfit (robust lot sizing)
//   - Persistent state via GlobalVariables
//   - Partial close at +2R (50%) + break-even
//   - Trailing stop after partial close
//   - Daily/total drawdown with EmergencyClose
//   - Session filter (EAT)
//   - Spread filter
//   - Duplicate position prevention
//   - Max trades per day
//   - One trade per bar
//   - HUD/Comment status
//   - News blackout (NEWS_FILTER_ONLY)
//   - SL with stops level respect
//
// Key V37 components to REPLACE in V38.2:
//   - 8-feature ONNX → 50-feature V38.2 ONNX
//   - Simple SMC (FVG+displacement) → V38.2 StructureEngine
//   - HTFBias (H1 breakout) → V38.2 regime tracking
//   - AI threshold 0.72 → calibrated 0.50
//   - 8 hardcoded features → 50 computed features
//   - AI(bias) → V38.2 PredictWin(feat[])
//
// This file is NOT compiled. It is the reference.
// The actual V38.2 EA is in V38_2_EA.mq5.
#property strict
#property version   "37.00"
#property copyright "SMC Gold Edition — REFERENCE ONLY"

// This file intentionally contains only the architecture map.
// The full V37 source was provided by the user and is preserved
// in the project documentation for reference.
// V38_2_EA.mq5 is the production evolution.
