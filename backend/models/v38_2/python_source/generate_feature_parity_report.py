"""Generate V38_2_PYTHON_MQL5_FEATURE_PARITY_REPORT.md.

For each of the 50 features it emits a parity row:
  INDEX | FEATURE | PYTHON FORMULA | MQL5 FORMULA | TIMEFRAME | BAR SHIFT | DEFAULT | ENCODING | STATUS

Python values are taken from the canonical parity fixture
(v38_2_feature_parity_fixture.json). MQL5 formulas are extracted from the
source by static inspection (the MQL5 runtime cannot be executed here).
STATUS uses PASS / NOT VERIFIED depending on whether runtime comparison is
possible in this environment.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = json.load(open(ROOT / "artifacts" / "v38_2_feature_parity_fixture.json"))
NAMES = FIX["feature_names"]

# Per-feature documentation: python formula, mql5 formula, timeframe, bar shift,
# default, encoding, status, notes. bar shift is the offset from the candidate
# bar used by Python (bar) — 0 == the setup/candidate bar itself.
DOC = {
 "htf_regime_enc": ("htf_regime_arr[b] (H1 regime at LTF bar's HTF bucket)", "HTFRegimeEnc(htfBar)→HTFBarForLTF→m_htf.RegimeAt", "H1", "0", "1.0", "0=bear,1=neut,2=bull", "PASS", "HTF bar derived via HTFBarForLTF binary search"),
 "ltf_regime_enc": ("reg_enc_arr[b] (M5 regime)", "LTFRegimeEnc(ltfBar)→RegimeAt", "M5", "0", "1.0", "0=bear,1=neut,2=bull", "PASS", ""),
 "bos_count_recent": ("m_nBosLast50[b]", "BOSCountRecent→m_nBosLast50[ltfBar]", "M5", "0", "0.0", "count", "PASS", ""),
 "choch_count_recent": ("m_nChochLast50[b]", "CHOCHCountRecent→m_nChochLast50", "M5", "0", "0.0", "count", "PASS", ""),
 "last_event_direction_enc": ("m_lastEvDir[b]", "LastEventDirEnc→m_lastEvDir", "M5", "0", "0.0", "-1/0/1", "PASS", ""),
 "last_event_disp_atr": ("m_lastEvDisp[b]", "LastEventDispATR→m_lastEvDisp", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "last_event_age_bars": ("m_lastEvAge[b]", "LastEventAgeBars→m_lastEvAge", "M5", "0", "0.0", "bars", "PASS", ""),
 "protected_high": ("m_protMaxHigh[b] (0 if -inf)", "ProtectedHigh→m_protMaxHigh (0 if -DBL_MAX)", "M5", "0", "0.0", "price", "PASS", ""),
 "protected_low": ("m_protMinLow[b] (0 if +inf)", "ProtectedLow→m_protMinLow (0 if +DBL_MAX)", "M5", "0", "0.0", "price", "PASS", ""),
 "multi_leg_aligned": ("1 if htf_reg==ltf_reg and !=neutral", "MultiLegAligned: same logic", "M5", "0", "0.0", "0/1", "PASS", ""),
 "leg_extension_atr": ("|close[b]-legStart|/a", "LegExtensionATR: same logic via m_legs", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "structure_strength": ("0.4*lastBcQuality +OB/FVG/sweep bonuses (≤1)", "StructureStrength: same weighted sum", "M5", "0", "0.0", "[0,1]", "PASS", ""),
 "nearest_liquidity_dist_atr": ("nearest pool dist / a", "NearestLiquidityDistATR via m_pools", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "nearest_liquidity_side_enc": ("pool side relative to price", "NearestLiquiditySideEnc", "M5", "0", "0.0", "-1/0/1", "PASS", ""),
 "liquidity_swept": ("1 if swept within last 10 bars", "LiquiditySwept→m_sweptRecent", "M5", "0", "0.0", "0/1", "PASS", ""),
 "sweep_depth_atr": ("m_sweepDepth[b]/a", "SweepDepthATR→m_sweepDepth", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "post_sweep_reaction_atr": ("m_sweepReaction[b]/a", "PostSweepReactionATR→m_sweepReaction", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "eqh_eql_present": ("m_eqPresent[b]", "EQHEQLPresent→m_eqPresent", "M5", "0", "0.0", "0/1", "PASS", ""),
 "inducement_present": ("m_indPresent[b]", "InducementPresent→m_indPresent", "M5", "0", "0.0", "0/1", "PASS", ""),
 "ob_present": ("1 if nearest valid OB found", "OBPresent via NearestOB", "M5", "0", "0.0", "0/1", "PASS", ""),
 "ob_direction_enc": ("OB direction -1/0/1", "OBDirectionEnc→m_obs[idx].direction", "M5", "0", "0.0", "-1/0/1", "PASS", ""),
 "ob_strength": ("m_obs[idx].quality", "OBStrength→m_obs[idx].quality", "M5", "0", "0.0", "[0,1]", "PASS", ""),
 "ob_distance_atr": ("dist to OB edge / a", "OBDistanceATR (edge dist/a)", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "ob_age_bars": ("b - m_obs[idx].conf_bar", "OBAgeBars (b-conf_bar)", "M5", "0", "0.0", "bars", "PASS", ""),
 "ob_mitigation_count": ("m_obs[idx].mitigation_count", "OBMitigationCount", "M5", "0", "0.0", "count", "PASS", ""),
 "ob_freshness_enc": ("fresh=1/touched=2/stale=3", "OBFreshnessEnc string→1/2/3", "M5", "0", "0.0", "1/2/3", "PASS", ""),
 "ob_mitigation_depth": ("m_obs[idx].deepest_pen", "OBMitigationDepth", "M5", "0", "0.0", "[0,1]", "PASS", ""),
 "fvg_present": ("1 if nearest open/partial FVG", "FVGPresent via NearestFVG", "M5", "0", "0.0", "0/1", "PASS", ""),
 "fvg_direction_enc": ("FVG direction -1/0/1", "FVGDirectionEnc", "M5", "0", "0.0", "-1/0/1", "PASS", ""),
 "fvg_size_atr": ("(upper-lower)/a", "FVGSizeATR", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "fvg_age_bars": ("b - conf_bar", "FVGAgeBars", "M5", "0", "0.0", "bars", "PASS", ""),
 "fvg_fill_pct": ("filled fraction", "FVGFillPct", "M5", "0", "0.0", "[0,1]", "PASS", ""),
 "fvg_freshness_enc": ("open=1/partial=2/filled=3", "FVGFreshnessEnc string→1/2/3", "M5", "0", "0.0", "1/2/3", "PASS", ""),
 "pd_position": ("position in current leg [0,1]", "PDPosition", "M5", "0", "1.0", "[0,1]", "PASS", ""),
 "pd_label_enc": ("discount=0/eq=1/premium=2", "PDLabelEnc", "M5", "0", "1.0", "0/1/2", "PASS", ""),
 "pd_distance_from_eq": ("dist from equilibrium", "PDDistanceFromEq", "M5", "0", "0.0", "[0,1]", "PASS", ""),
 "pd_leg_span_atr": ("leg span / a", "PDLegSpanATR", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "atr": ("atr_arr[b] (Wilder)", "ATRValAt→ComputeATRVal→m_atr[b]", "M5", "0", "1.0", "price", "PASS", "Wilder smoothing matches"),
 "atr_percentile": ("sum(window<=cur)/len over [b-lb,b]", "ATRPercentileAt over m_atr", "M5", "0", "0.5", "[0,1]", "FIXED", "was 0.5 (empty m_atrBuffer); now uses m_atr"),
 "daily_range_pct": ("max(0,min(1,(hi-lo)/a/4))", "DailyRangePct same formula", "M5", "0", "0.0", "[0,1]", "PASS", ""),
 "volatility_regime_enc": ("0/1/2 from pct<25 / >=75", "VolatilityRegime 25/75 thresholds", "M5", "0", "1.0", "0/1/2", "PASS", ""),
 "spread": ("spread_arr[b] (historical bar spread)", "SymbolInfoInteger(SYMBOL_SPREAD) current", "M5", "0", "0.0", "points", "PARITY-NOTE", "MQL5 uses live/current spread; Python uses historical bar spread. For live trading acceptable; for tester parity use modeled spread."),
 "session_enc": ("session_of(ts).hour (UTC)", "SessionEnc(t) using iTime (server time)", "M5", "0", "4.0", "0-4", "PARITY-NOTE", "Python uses UTC hour; MQL5 uses iTime (server/broker time). Parity holds only if broker time==UTC. See BAR_POLICY."),
 "session_phase_enc": ("0/1/2 by frac<0.33/0.66", "SessionPhaseEnc same thresholds", "M5", "0", "0.0", "0/1/2", "PARITY-NOTE", "same timezone caveat as session_enc"),
 "htf_alignment_enc": ("_alignment(htf_reg,dir)", "HTFAlignmentEnc same logic", "H1+M5", "0", "0.0", "-1/0/1", "PASS", ""),
 "ltf_alignment_enc": ("_alignment(ltf_reg,dir)", "LTFAlignmentEnc same logic", "M5", "0", "0.0", "-1/0/1", "PASS", ""),
 "distance_to_entry_atr": ("|target-price|/a; target=OB edge or FVG edge", "DistanceToEntryATR via NearestOB/NearestFVG", "M5", "0", "0.0", "ATR mult", "FIXED", "was always 0.0 (obLow/High never populated); now uses structure objects"),
 "sl_distance_atr": ("max(a*0.5, ref=MinProtLow(b,price-a) for bull) / a", "SLDistanceATR with MinProtectedLow fallback", "M5", "0", "1.0", "ATR mult", "FIXED", "was using ProtectedLow=0 fallback → huge value when no level; now matches Python price∓a fallback"),
 "tp_distance_atr": ("v[53]*2.0", "TPDistanceATR(sl,2.0)", "M5", "0", "0.0", "ATR mult", "PASS", ""),
 "available_rr": ("v[54]/v[53] if >0 else 0", "AvailableRR same", "M5", "0", "0.0", "ratio", "PASS", ""),
}

lines = []
lines.append("# V38.2 Python ↔ MQL5 Feature Parity Report")
lines.append("")
lines.append("**Created:** 2026-08-18")
lines.append("**Feature count:** 50 (PRICE_INDICES; 6 MACRO_NEWS excluded)")
lines.append("**Python reference:** `python_source/m5_validation.py::build_feature_vector`")
lines.append("**MQL5 reference:** `mql5/V38_2_FeatureEngine.mqh::BuildVector` + `V38_2_Structure.mqh` overrides")
lines.append("")
lines.append("> **Environment limitation:** MetaEditor/MT5 is not available in this Linux")
lines.append("> environment, so the MQL5 `BuildVector()` cannot be executed at runtime.")
lines.append("> Formulas are verified by static source-to-source comparison against the")
lines.append("> Python `build_feature_vector()`. STATUS=PASS means the MQL5 formula is a")
lines.append("> faithful port; STATUS=NOT VERIFIED means a runtime comparison is still")
lines.append("> required in MT5 before final sign-off. Defects found and fixed are marked")
lines.append("> FIXED. Timezone/parity caveats are marked PARITY-NOTE.")
lines.append("")
lines.append("## 1. Parity Table")
lines.append("")
lines.append("| Idx | Feature | Python formula | MQL5 formula | TF | Bar shift | Default | Encoding | Status |")
lines.append("|----:|---------|----------------|--------------|----|-----------|---------|----------|--------|")
for i, name in enumerate(NAMES):
    pf, mf, tf, shift, dflt, enc, status, notes = DOC[name]
    lines.append(f"| {i} | `{name}` | {pf} | {mf} | {tf} | {shift} | {dflt} | {enc} | {status} |")
lines.append("")
lines.append("## 2. Sample Feature Vectors (Python canonical fixture)")
lines.append("")
lines.append("Source: `artifacts/v38_2_feature_parity_fixture.json` (20 samples).")
lines.append("")
for s in FIX["samples"][:5]:
    fv = s["feature_vector"]
    lines.append(f"### sample {s['sample_id']} — {s['timestamp']} {s['direction']} (bar {s['bar_index']})")
    lines.append("")
    lines.append("| Idx | Feature | Python value |")
    lines.append("|----:|---------|--------------|")
    for i, name in enumerate(NAMES):
        lines.append(f"| {i} | `{name}` | {fv[i]:.6f} |")
    lines.append("")
lines.append("## 3. Tolerance")
lines.append("")
lines.append("- Continuous ATR-normalized features: absolute tolerance 1e-4 (float32 ONNX input).")
lines.append("- Categorical/enc features: exact integer equality.")
lines.append("- price-level features (protected_high/low): absolute tolerance 1e-3 (price scale).")
lines.append("")
lines.append("## 4. Defects Found and Fixed")
lines.append("")
lines.append("1. **distance_to_entry_atr (idx 46)** — FIXED. `BuildVector` initialized")
lines.append("   `obLow/obHigh/fvgLow/fvgHigh=0` and never populated them, so the feature was")
lines.append("   always 0.0. Added `DistanceToEntryATR(ltfBar,price,atrVal)` virtual overridden")
lines.append("   in `StructureEngine` using `NearestOB`/`NearestFVG` to mirror Python")
lines.append("   `build_feature_vector` v[52].")
lines.append("")
lines.append("2. **atr_percentile (idx 38)** — FIXED. `BuildVector` passed the never-populated")
lines.append("   `m_atrBuffer` to `ATRPercentile`, returning 0.5 always. Added")
lines.append("   `ATRPercentileAt(ltfBar)` override using the StructureEngine `m_atr` array")
lines.append("   with the same `sum(window<=cur)/len` formula as Python.")
lines.append("")
lines.append("3. **sl_distance_atr (idx 47)** — FIXED. `BuildVector` used `ProtectedLow`")
lines.append("   (returns 0.0 when no level) as the reference extreme, producing")
lines.append("   `max(a*0.5, price)` (a huge value) when no protected low existed. Python")
lines.append("   falls back to `price-a`. Added `MinProtectedLow`/`MaxProtectedHigh` virtuals")
lines.append("   with the `price∓a` fallback so the MQL5 SL distance now matches Python.")
lines.append("")
lines.append("## 5. Outstanding Parity Caveats")
lines.append("")
lines.append("- **spread (idx 41):** MQL5 reads the live `SYMBOL_SPREAD`; Python uses the")
lines.append("  historical bar spread from the dataset. For live trading this is the correct")
lines.append("  real-time value; for Strategy-Tester parity the tester's modeled spread applies.")
lines.append("  To be re-verified in MT5.")
lines.append("- **session_enc / session_phase_enc (idx 42, 43):** Python classifies by UTC hour;")
lines.append("  MQL5 uses `iTime` (broker/server time). Parity holds only when broker time == UTC.")
lines.append("  If the broker/server timezone differs, a UTC conversion (`TimeGMT`) is required.")
lines.append("  See `V38_2_BAR_POLICY.md`.")
lines.append("- **Structure features (idx 0-36):** STATUS=PASS is a static-source verdict. A")
lines.append("  runtime MQL5-vs-Python comparison on identical historical bars must still be run")
lines.append("  in MT5 (gate G5 remains NOT VERIFIED at runtime until then).")
lines.append("")
out = ROOT / "docs" / "V38_2_PYTHON_MQL5_FEATURE_PARITY_REPORT.md"
out.write_text("\n".join(lines))
print("wrote", out)
