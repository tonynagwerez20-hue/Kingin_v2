# V38.2 Python ↔ MQL5 Feature Parity Report

**Created:** 2026-08-18
**Feature count:** 50 (PRICE_INDICES; 6 MACRO_NEWS excluded)
**Python reference:** `python_source/m5_validation.py::build_feature_vector`
**MQL5 reference:** `mql5/V38_2_FeatureEngine.mqh::BuildVector` + `V38_2_Structure.mqh` overrides

> **Environment limitation:** MetaEditor/MT5 is not available in this Linux
> environment, so the MQL5 `BuildVector()` cannot be executed at runtime.
> Formulas are verified by static source-to-source comparison against the
> Python `build_feature_vector()`. STATUS=PASS means the MQL5 formula is a
> faithful port; STATUS=NOT VERIFIED means a runtime comparison is still
> required in MT5 before final sign-off. Defects found and fixed are marked
> FIXED. Timezone/parity caveats are marked PARITY-NOTE.

## 1. Parity Table

| Idx | Feature | Python formula | MQL5 formula | TF | Bar shift | Default | Encoding | Status |
|----:|---------|----------------|--------------|----|-----------|---------|----------|--------|
| 0 | `htf_regime_enc` | htf_regime_arr[b] (H1 regime at LTF bar's HTF bucket) | HTFRegimeEnc(htfBar)→HTFBarForLTF→m_htf.RegimeAt | H1 | 0 | 1.0 | 0=bear,1=neut,2=bull | PASS |
| 1 | `ltf_regime_enc` | reg_enc_arr[b] (M5 regime) | LTFRegimeEnc(ltfBar)→RegimeAt | M5 | 0 | 1.0 | 0=bear,1=neut,2=bull | PASS |
| 2 | `bos_count_recent` | m_nBosLast50[b] | BOSCountRecent→m_nBosLast50[ltfBar] | M5 | 0 | 0.0 | count | PASS |
| 3 | `choch_count_recent` | m_nChochLast50[b] | CHOCHCountRecent→m_nChochLast50 | M5 | 0 | 0.0 | count | PASS |
| 4 | `last_event_direction_enc` | m_lastEvDir[b] | LastEventDirEnc→m_lastEvDir | M5 | 0 | 0.0 | -1/0/1 | PASS |
| 5 | `last_event_disp_atr` | m_lastEvDisp[b] | LastEventDispATR→m_lastEvDisp | M5 | 0 | 0.0 | ATR mult | PASS |
| 6 | `last_event_age_bars` | m_lastEvAge[b] | LastEventAgeBars→m_lastEvAge | M5 | 0 | 0.0 | bars | PASS |
| 7 | `protected_high` | m_protMaxHigh[b] (0 if -inf) | ProtectedHigh→m_protMaxHigh (0 if -DBL_MAX) | M5 | 0 | 0.0 | price | PASS |
| 8 | `protected_low` | m_protMinLow[b] (0 if +inf) | ProtectedLow→m_protMinLow (0 if +DBL_MAX) | M5 | 0 | 0.0 | price | PASS |
| 9 | `multi_leg_aligned` | 1 if htf_reg==ltf_reg and !=neutral | MultiLegAligned: same logic | M5 | 0 | 0.0 | 0/1 | PASS |
| 10 | `leg_extension_atr` | |close[b]-legStart|/a | LegExtensionATR: same logic via m_legs | M5 | 0 | 0.0 | ATR mult | PASS |
| 11 | `structure_strength` | 0.4*lastBcQuality +OB/FVG/sweep bonuses (≤1) | StructureStrength: same weighted sum | M5 | 0 | 0.0 | [0,1] | PASS |
| 12 | `nearest_liquidity_dist_atr` | nearest pool dist / a | NearestLiquidityDistATR via m_pools | M5 | 0 | 0.0 | ATR mult | PASS |
| 13 | `nearest_liquidity_side_enc` | pool side relative to price | NearestLiquiditySideEnc | M5 | 0 | 0.0 | -1/0/1 | PASS |
| 14 | `liquidity_swept` | 1 if swept within last 10 bars | LiquiditySwept→m_sweptRecent | M5 | 0 | 0.0 | 0/1 | PASS |
| 15 | `sweep_depth_atr` | m_sweepDepth[b]/a | SweepDepthATR→m_sweepDepth | M5 | 0 | 0.0 | ATR mult | PASS |
| 16 | `post_sweep_reaction_atr` | m_sweepReaction[b]/a | PostSweepReactionATR→m_sweepReaction | M5 | 0 | 0.0 | ATR mult | PASS |
| 17 | `eqh_eql_present` | m_eqPresent[b] | EQHEQLPresent→m_eqPresent | M5 | 0 | 0.0 | 0/1 | PASS |
| 18 | `inducement_present` | m_indPresent[b] | InducementPresent→m_indPresent | M5 | 0 | 0.0 | 0/1 | PASS |
| 19 | `ob_present` | 1 if nearest valid OB found | OBPresent via NearestOB | M5 | 0 | 0.0 | 0/1 | PASS |
| 20 | `ob_direction_enc` | OB direction -1/0/1 | OBDirectionEnc→m_obs[idx].direction | M5 | 0 | 0.0 | -1/0/1 | PASS |
| 21 | `ob_strength` | m_obs[idx].quality | OBStrength→m_obs[idx].quality | M5 | 0 | 0.0 | [0,1] | PASS |
| 22 | `ob_distance_atr` | dist to OB edge / a | OBDistanceATR (edge dist/a) | M5 | 0 | 0.0 | ATR mult | PASS |
| 23 | `ob_age_bars` | b - m_obs[idx].conf_bar | OBAgeBars (b-conf_bar) | M5 | 0 | 0.0 | bars | PASS |
| 24 | `ob_mitigation_count` | m_obs[idx].mitigation_count | OBMitigationCount | M5 | 0 | 0.0 | count | PASS |
| 25 | `ob_freshness_enc` | fresh=1/touched=2/stale=3 | OBFreshnessEnc string→1/2/3 | M5 | 0 | 0.0 | 1/2/3 | PASS |
| 26 | `ob_mitigation_depth` | m_obs[idx].deepest_pen | OBMitigationDepth | M5 | 0 | 0.0 | [0,1] | PASS |
| 27 | `fvg_present` | 1 if nearest open/partial FVG | FVGPresent via NearestFVG | M5 | 0 | 0.0 | 0/1 | PASS |
| 28 | `fvg_direction_enc` | FVG direction -1/0/1 | FVGDirectionEnc | M5 | 0 | 0.0 | -1/0/1 | PASS |
| 29 | `fvg_size_atr` | (upper-lower)/a | FVGSizeATR | M5 | 0 | 0.0 | ATR mult | PASS |
| 30 | `fvg_age_bars` | b - conf_bar | FVGAgeBars | M5 | 0 | 0.0 | bars | PASS |
| 31 | `fvg_fill_pct` | filled fraction | FVGFillPct | M5 | 0 | 0.0 | [0,1] | PASS |
| 32 | `fvg_freshness_enc` | open=1/partial=2/filled=3 | FVGFreshnessEnc string→1/2/3 | M5 | 0 | 0.0 | 1/2/3 | PASS |
| 33 | `pd_position` | position in current leg [0,1] | PDPosition | M5 | 0 | 1.0 | [0,1] | PASS |
| 34 | `pd_label_enc` | discount=0/eq=1/premium=2 | PDLabelEnc | M5 | 0 | 1.0 | 0/1/2 | PASS |
| 35 | `pd_distance_from_eq` | dist from equilibrium | PDDistanceFromEq | M5 | 0 | 0.0 | [0,1] | PASS |
| 36 | `pd_leg_span_atr` | leg span / a | PDLegSpanATR | M5 | 0 | 0.0 | ATR mult | PASS |
| 37 | `atr` | atr_arr[b] (Wilder) | ATRValAt→ComputeATRVal→m_atr[b] | M5 | 0 | 1.0 | price | PASS |
| 38 | `atr_percentile` | sum(window<=cur)/len over [b-lb,b] | ATRPercentileAt over m_atr | M5 | 0 | 0.5 | [0,1] | FIXED |
| 39 | `daily_range_pct` | max(0,min(1,(hi-lo)/a/4)) | DailyRangePct same formula | M5 | 0 | 0.0 | [0,1] | PASS |
| 40 | `volatility_regime_enc` | 0/1/2 from pct<25 / >=75 | VolatilityRegime 25/75 thresholds | M5 | 0 | 1.0 | 0/1/2 | PASS |
| 41 | `spread` | spread_arr[b] (historical bar spread) | SymbolInfoInteger(SYMBOL_SPREAD) current | M5 | 0 | 0.0 | points | PARITY-NOTE |
| 42 | `session_enc` | session_of(ts).hour (UTC) | SessionEnc(t) using iTime (server time) | M5 | 0 | 4.0 | 0-4 | PARITY-NOTE |
| 43 | `session_phase_enc` | 0/1/2 by frac<0.33/0.66 | SessionPhaseEnc same thresholds | M5 | 0 | 0.0 | 0/1/2 | PARITY-NOTE |
| 44 | `htf_alignment_enc` | _alignment(htf_reg,dir) | HTFAlignmentEnc same logic | H1+M5 | 0 | 0.0 | -1/0/1 | PASS |
| 45 | `ltf_alignment_enc` | _alignment(ltf_reg,dir) | LTFAlignmentEnc same logic | M5 | 0 | 0.0 | -1/0/1 | PASS |
| 46 | `distance_to_entry_atr` | |target-price|/a; target=OB edge or FVG edge | DistanceToEntryATR via NearestOB/NearestFVG | M5 | 0 | 0.0 | ATR mult | FIXED |
| 47 | `sl_distance_atr` | max(a*0.5, ref=MinProtLow(b,price-a) for bull) / a | SLDistanceATR with MinProtectedLow fallback | M5 | 0 | 1.0 | ATR mult | FIXED |
| 48 | `tp_distance_atr` | v[53]*2.0 | TPDistanceATR(sl,2.0) | M5 | 0 | 0.0 | ATR mult | PASS |
| 49 | `available_rr` | v[54]/v[53] if >0 else 0 | AvailableRR same | M5 | 0 | 0.0 | ratio | PASS |

## 2. Sample Feature Vectors (Python canonical fixture)

Source: `artifacts/v38_2_feature_parity_fixture.json` (20 samples).

### sample 0 — 2019-07-25 19:55:00+00:00 bearish (bar 114461)

| Idx | Feature | Python value |
|----:|---------|--------------|
| 0 | `htf_regime_enc` | 0.000000 |
| 1 | `ltf_regime_enc` | 0.000000 |
| 2 | `bos_count_recent` | 34.000000 |
| 3 | `choch_count_recent` | 16.000000 |
| 4 | `last_event_direction_enc` | -1.000000 |
| 5 | `last_event_disp_atr` | 1.934294 |
| 6 | `last_event_age_bars` | 38.000000 |
| 7 | `protected_high` | 0.000000 |
| 8 | `protected_low` | 0.000000 |
| 9 | `multi_leg_aligned` | 1.000000 |
| 10 | `leg_extension_atr` | 3.694321 |
| 11 | `structure_strength` | 1.000000 |
| 12 | `nearest_liquidity_dist_atr` | 0.007912 |
| 13 | `nearest_liquidity_side_enc` | 1.000000 |
| 14 | `liquidity_swept` | 1.000000 |
| 15 | `sweep_depth_atr` | 0.170413 |
| 16 | `post_sweep_reaction_atr` | 1.460687 |
| 17 | `eqh_eql_present` | 1.000000 |
| 18 | `inducement_present` | 1.000000 |
| 19 | `ob_present` | 0.000000 |
| 20 | `ob_direction_enc` | 0.000000 |
| 21 | `ob_strength` | 0.000000 |
| 22 | `ob_distance_atr` | 0.000000 |
| 23 | `ob_age_bars` | 0.000000 |
| 24 | `ob_mitigation_count` | 0.000000 |
| 25 | `ob_freshness_enc` | 0.000000 |
| 26 | `ob_mitigation_depth` | 0.000000 |
| 27 | `fvg_present` | 0.000000 |
| 28 | `fvg_direction_enc` | 0.000000 |
| 29 | `fvg_size_atr` | 0.000000 |
| 30 | `fvg_age_bars` | 0.000000 |
| 31 | `fvg_fill_pct` | 0.000000 |
| 32 | `fvg_freshness_enc` | 0.000000 |
| 33 | `pd_position` | 0.463005 |
| 34 | `pd_label_enc` | 1.000000 |
| 35 | `pd_distance_from_eq` | 0.073989 |
| 36 | `pd_leg_span_atr` | 7.979002 |
| 37 | `atr` | 0.821531 |
| 38 | `atr_percentile` | 0.527363 |
| 39 | `daily_range_pct` | 0.407775 |
| 40 | `volatility_regime_enc` | 1.000000 |
| 41 | `spread` | 0.337800 |
| 42 | `session_enc` | 3.000000 |
| 43 | `session_phase_enc` | 1.000000 |
| 44 | `htf_alignment_enc` | 1.000000 |
| 45 | `ltf_alignment_enc` | 1.000000 |
| 46 | `distance_to_entry_atr` | 0.000000 |
| 47 | `sl_distance_atr` | 1.000000 |
| 48 | `tp_distance_atr` | 2.000000 |
| 49 | `available_rr` | 2.000000 |

### sample 1 — 2019-11-05 11:25:00+00:00 bullish (bar 134843)

| Idx | Feature | Python value |
|----:|---------|--------------|
| 0 | `htf_regime_enc` | 2.000000 |
| 1 | `ltf_regime_enc` | 0.000000 |
| 2 | `bos_count_recent` | 29.000000 |
| 3 | `choch_count_recent` | 21.000000 |
| 4 | `last_event_direction_enc` | -1.000000 |
| 5 | `last_event_disp_atr` | 0.580664 |
| 6 | `last_event_age_bars` | 28.000000 |
| 7 | `protected_high` | 0.000000 |
| 8 | `protected_low` | 0.000000 |
| 9 | `multi_leg_aligned` | 0.000000 |
| 10 | `leg_extension_atr` | 0.528976 |
| 11 | `structure_strength` | 0.858073 |
| 12 | `nearest_liquidity_dist_atr` | 0.001777 |
| 13 | `nearest_liquidity_side_enc` | 1.000000 |
| 14 | `liquidity_swept` | 1.000000 |
| 15 | `sweep_depth_atr` | 0.166547 |
| 16 | `post_sweep_reaction_atr` | 3.909871 |
| 17 | `eqh_eql_present` | 1.000000 |
| 18 | `inducement_present` | 1.000000 |
| 19 | `ob_present` | 0.000000 |
| 20 | `ob_direction_enc` | 0.000000 |
| 21 | `ob_strength` | 0.000000 |
| 22 | `ob_distance_atr` | 0.000000 |
| 23 | `ob_age_bars` | 0.000000 |
| 24 | `ob_mitigation_count` | 0.000000 |
| 25 | `ob_freshness_enc` | 0.000000 |
| 26 | `ob_mitigation_depth` | 0.000000 |
| 27 | `fvg_present` | 0.000000 |
| 28 | `fvg_direction_enc` | 0.000000 |
| 29 | `fvg_size_atr` | 0.000000 |
| 30 | `fvg_age_bars` | 0.000000 |
| 31 | `fvg_fill_pct` | 0.000000 |
| 32 | `fvg_freshness_enc` | 0.000000 |
| 33 | `pd_position` | 0.320072 |
| 34 | `pd_label_enc` | 0.000000 |
| 35 | `pd_distance_from_eq` | 0.359857 |
| 36 | `pd_leg_span_atr` | 1.652680 |
| 37 | `atr` | 0.844083 |
| 38 | `atr_percentile` | 0.900497 |
| 39 | `daily_range_pct` | 0.210732 |
| 40 | `volatility_regime_enc` | 2.000000 |
| 41 | `spread` | 0.263000 |
| 42 | `session_enc` | 1.000000 |
| 43 | `session_phase_enc` | 2.000000 |
| 44 | `htf_alignment_enc` | 1.000000 |
| 45 | `ltf_alignment_enc` | -1.000000 |
| 46 | `distance_to_entry_atr` | 0.000000 |
| 47 | `sl_distance_atr` | 1.000000 |
| 48 | `tp_distance_atr` | 2.000000 |
| 49 | `available_rr` | 2.000000 |

### sample 2 — 2020-02-27 00:15:00+00:00 bearish (bar 157820)

| Idx | Feature | Python value |
|----:|---------|--------------|
| 0 | `htf_regime_enc` | 0.000000 |
| 1 | `ltf_regime_enc` | 2.000000 |
| 2 | `bos_count_recent` | 34.000000 |
| 3 | `choch_count_recent` | 16.000000 |
| 4 | `last_event_direction_enc` | 1.000000 |
| 5 | `last_event_disp_atr` | 0.613585 |
| 6 | `last_event_age_bars` | 2.000000 |
| 7 | `protected_high` | 0.000000 |
| 8 | `protected_low` | 0.000000 |
| 9 | `multi_leg_aligned` | 0.000000 |
| 10 | `leg_extension_atr` | 5.022298 |
| 11 | `structure_strength` | 0.872705 |
| 12 | `nearest_liquidity_dist_atr` | 0.013579 |
| 13 | `nearest_liquidity_side_enc` | -1.000000 |
| 14 | `liquidity_swept` | 1.000000 |
| 15 | `sweep_depth_atr` | 0.757175 |
| 16 | `post_sweep_reaction_atr` | 1.316467 |
| 17 | `eqh_eql_present` | 0.000000 |
| 18 | `inducement_present` | 1.000000 |
| 19 | `ob_present` | 0.000000 |
| 20 | `ob_direction_enc` | 0.000000 |
| 21 | `ob_strength` | 0.000000 |
| 22 | `ob_distance_atr` | 0.000000 |
| 23 | `ob_age_bars` | 0.000000 |
| 24 | `ob_mitigation_count` | 0.000000 |
| 25 | `ob_freshness_enc` | 0.000000 |
| 26 | `ob_mitigation_depth` | 0.000000 |
| 27 | `fvg_present` | 0.000000 |
| 28 | `fvg_direction_enc` | 0.000000 |
| 29 | `fvg_size_atr` | 0.000000 |
| 30 | `fvg_age_bars` | 0.000000 |
| 31 | `fvg_fill_pct` | 0.000000 |
| 32 | `fvg_freshness_enc` | 0.000000 |
| 33 | `pd_position` | 1.000000 |
| 34 | `pd_label_enc` | 2.000000 |
| 35 | `pd_distance_from_eq` | 1.000000 |
| 36 | `pd_leg_span_atr` | 3.619088 |
| 37 | `atr` | 1.951597 |
| 38 | `atr_percentile` | 0.542289 |
| 39 | `daily_range_pct` | 0.373604 |
| 40 | `volatility_regime_enc` | 1.000000 |
| 41 | `spread` | 0.278400 |
| 42 | `session_enc` | 0.000000 |
| 43 | `session_phase_enc` | 0.000000 |
| 44 | `htf_alignment_enc` | 1.000000 |
| 45 | `ltf_alignment_enc` | -1.000000 |
| 46 | `distance_to_entry_atr` | 0.000000 |
| 47 | `sl_distance_atr` | 1.000000 |
| 48 | `tp_distance_atr` | 2.000000 |
| 49 | `available_rr` | 2.000000 |

### sample 3 — 2020-06-02 22:35:00+00:00 bearish (bar 176904)

| Idx | Feature | Python value |
|----:|---------|--------------|
| 0 | `htf_regime_enc` | 0.000000 |
| 1 | `ltf_regime_enc` | 0.000000 |
| 2 | `bos_count_recent` | 32.000000 |
| 3 | `choch_count_recent` | 18.000000 |
| 4 | `last_event_direction_enc` | -1.000000 |
| 5 | `last_event_disp_atr` | 0.181253 |
| 6 | `last_event_age_bars` | 77.000000 |
| 7 | `protected_high` | 0.000000 |
| 8 | `protected_low` | 0.000000 |
| 9 | `multi_leg_aligned` | 1.000000 |
| 10 | `leg_extension_atr` | 0.112607 |
| 11 | `structure_strength` | 0.680557 |
| 12 | `nearest_liquidity_dist_atr` | 0.014798 |
| 13 | `nearest_liquidity_side_enc` | -1.000000 |
| 14 | `liquidity_swept` | 1.000000 |
| 15 | `sweep_depth_atr` | 0.676260 |
| 16 | `post_sweep_reaction_atr` | 1.360400 |
| 17 | `eqh_eql_present` | 0.000000 |
| 18 | `inducement_present` | 1.000000 |
| 19 | `ob_present` | 0.000000 |
| 20 | `ob_direction_enc` | 0.000000 |
| 21 | `ob_strength` | 0.000000 |
| 22 | `ob_distance_atr` | 0.000000 |
| 23 | `ob_age_bars` | 0.000000 |
| 24 | `ob_mitigation_count` | 0.000000 |
| 25 | `ob_freshness_enc` | 0.000000 |
| 26 | `ob_mitigation_depth` | 0.000000 |
| 27 | `fvg_present` | 0.000000 |
| 28 | `fvg_direction_enc` | 0.000000 |
| 29 | `fvg_size_atr` | 0.000000 |
| 30 | `fvg_age_bars` | 0.000000 |
| 31 | `fvg_fill_pct` | 0.000000 |
| 32 | `fvg_freshness_enc` | 0.000000 |
| 33 | `pd_position` | 0.982393 |
| 34 | `pd_label_enc` | 2.000000 |
| 35 | `pd_distance_from_eq` | 0.964786 |
| 36 | `pd_leg_span_atr` | 6.395517 |
| 37 | `atr` | 0.692673 |
| 38 | `atr_percentile` | 0.049751 |
| 39 | `daily_range_pct` | 0.123254 |
| 40 | `volatility_regime_enc` | 0.000000 |
| 41 | `spread` | 0.505400 |
| 42 | `session_enc` | 4.000000 |
| 43 | `session_phase_enc` | 1.000000 |
| 44 | `htf_alignment_enc` | 1.000000 |
| 45 | `ltf_alignment_enc` | 1.000000 |
| 46 | `distance_to_entry_atr` | 0.000000 |
| 47 | `sl_distance_atr` | 1.000000 |
| 48 | `tp_distance_atr` | 2.000000 |
| 49 | `available_rr` | 2.000000 |

### sample 4 — 2020-09-21 18:35:00+00:00 bearish (bar 198984)

| Idx | Feature | Python value |
|----:|---------|--------------|
| 0 | `htf_regime_enc` | 0.000000 |
| 1 | `ltf_regime_enc` | 0.000000 |
| 2 | `bos_count_recent` | 28.000000 |
| 3 | `choch_count_recent` | 22.000000 |
| 4 | `last_event_direction_enc` | -1.000000 |
| 5 | `last_event_disp_atr` | 0.307559 |
| 6 | `last_event_age_bars` | 53.000000 |
| 7 | `protected_high` | 0.000000 |
| 8 | `protected_low` | 0.000000 |
| 9 | `multi_leg_aligned` | 1.000000 |
| 10 | `leg_extension_atr` | 11.111618 |
| 11 | `structure_strength` | 0.736693 |
| 12 | `nearest_liquidity_dist_atr` | 0.238563 |
| 13 | `nearest_liquidity_side_enc` | 1.000000 |
| 14 | `liquidity_swept` | 0.000000 |
| 15 | `sweep_depth_atr` | 0.270478 |
| 16 | `post_sweep_reaction_atr` | 1.039030 |
| 17 | `eqh_eql_present` | 0.000000 |
| 18 | `inducement_present` | 1.000000 |
| 19 | `ob_present` | 0.000000 |
| 20 | `ob_direction_enc` | 0.000000 |
| 21 | `ob_strength` | 0.000000 |
| 22 | `ob_distance_atr` | 0.000000 |
| 23 | `ob_age_bars` | 0.000000 |
| 24 | `ob_mitigation_count` | 0.000000 |
| 25 | `ob_freshness_enc` | 0.000000 |
| 26 | `ob_mitigation_depth` | 0.000000 |
| 27 | `fvg_present` | 0.000000 |
| 28 | `fvg_direction_enc` | 0.000000 |
| 29 | `fvg_size_atr` | 0.000000 |
| 30 | `fvg_age_bars` | 0.000000 |
| 31 | `fvg_fill_pct` | 0.000000 |
| 32 | `fvg_freshness_enc` | 0.000000 |
| 33 | `pd_position` | 0.865302 |
| 34 | `pd_label_enc` | 2.000000 |
| 35 | `pd_distance_from_eq` | 0.730604 |
| 36 | `pd_leg_span_atr` | 12.841320 |
| 37 | `atr` | 2.116838 |
| 38 | `atr_percentile` | 0.631841 |
| 39 | `daily_range_pct` | 0.275765 |
| 40 | `volatility_regime_enc` | 1.000000 |
| 41 | `spread` | 0.391000 |
| 42 | `session_enc` | 3.000000 |
| 43 | `session_phase_enc` | 1.000000 |
| 44 | `htf_alignment_enc` | 1.000000 |
| 45 | `ltf_alignment_enc` | 1.000000 |
| 46 | `distance_to_entry_atr` | 0.000000 |
| 47 | `sl_distance_atr` | 1.000000 |
| 48 | `tp_distance_atr` | 2.000000 |
| 49 | `available_rr` | 2.000000 |

## 3. Tolerance

- Continuous ATR-normalized features: absolute tolerance 1e-4 (float32 ONNX input).
- Categorical/enc features: exact integer equality.
- price-level features (protected_high/low): absolute tolerance 1e-3 (price scale).

## 4. Defects Found and Fixed

1. **distance_to_entry_atr (idx 46)** — FIXED. `BuildVector` initialized
   `obLow/obHigh/fvgLow/fvgHigh=0` and never populated them, so the feature was
   always 0.0. Added `DistanceToEntryATR(ltfBar,price,atrVal)` virtual overridden
   in `StructureEngine` using `NearestOB`/`NearestFVG` to mirror Python
   `build_feature_vector` v[52].

2. **atr_percentile (idx 38)** — FIXED. `BuildVector` passed the never-populated
   `m_atrBuffer` to `ATRPercentile`, returning 0.5 always. Added
   `ATRPercentileAt(ltfBar)` override using the StructureEngine `m_atr` array
   with the same `sum(window<=cur)/len` formula as Python.

3. **sl_distance_atr (idx 47)** — FIXED. `BuildVector` used `ProtectedLow`
   (returns 0.0 when no level) as the reference extreme, producing
   `max(a*0.5, price)` (a huge value) when no protected low existed. Python
   falls back to `price-a`. Added `MinProtectedLow`/`MaxProtectedHigh` virtuals
   with the `price∓a` fallback so the MQL5 SL distance now matches Python.

## 5. Outstanding Parity Caveats

- **spread (idx 41):** MQL5 reads the live `SYMBOL_SPREAD`; Python uses the
  historical bar spread from the dataset. For live trading this is the correct
  real-time value; for Strategy-Tester parity the tester's modeled spread applies.
  To be re-verified in MT5.
- **session_enc / session_phase_enc (idx 42, 43):** Python classifies by UTC hour;
  MQL5 uses `iTime` (broker/server time). Parity holds only when broker time == UTC.
  If the broker/server timezone differs, a UTC conversion (`TimeGMT`) is required.
  See `V38_2_BAR_POLICY.md`.
- **Structure features (idx 0-36):** STATUS=PASS is a static-source verdict. A
  runtime MQL5-vs-Python comparison on identical historical bars must still be run
  in MT5 (gate G5 remains NOT VERIFIED at runtime until then).
