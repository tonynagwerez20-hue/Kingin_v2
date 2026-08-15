"""Canonical V38 feature contract (single source of truth).

FEATURE_CONTRACT_VERSION = "V38.1"

Each feature is declared once here with full metadata. The feature engine
computes a vector from a leakage-safe MarketStructure snapshot; the dataset
generator stores the same vector; the LightGBM model consumes it; the ONNX
model's input order matches `FEATURE_NAMES`; and the MQL5 implementation
mirrors the same definitions.

Feature families (9):
  STRUCTURE, LIQUIDITY, ORDER_BLOCK, FVG, PREMIUM_DISCOUNT,
  MARKET_REGIME, SESSION, MACRO_NEWS, SETUP_GEOMETRY

Every feature carries:
  name, index, dtype, range, family, definition, available_at (leakage note),
  python_impl, mql5_impl.

Ranges are documented allowed ranges (used for sanity checks and clipping at
inference time only when the source is bounded; raw continuous features are
not clipped except where the definition bounds them).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

FEATURE_CONTRACT_VERSION = "V38.1"

# ---------------------------------------------------------------------------
# Feature declaration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureSpec:
    name: str
    index: int
    dtype: str            # "float32" | "int32" | "bool"
    family: str
    range: tuple          # (min, max); (None, None) = unbounded
    definition: str
    available_at: str     # leakage note: when this becomes usable
    python_impl: str      # reference to the function/object that computes it
    mql5_impl: str        # the MQL5 function/identifier
    unit: str = ""


def _fs(*, name, idx, family, allowed_range, definition, available_at,
        python_impl, mql5_impl, dtype="float32", unit=""):
    return FeatureSpec(name=name, index=idx, dtype=dtype, family=family,
                       range=allowed_range, definition=definition, available_at=available_at,
                       python_impl=python_impl, mql5_impl=mql5_impl, unit=unit)


FEATURE_SPECS: List[FeatureSpec] = [
    # ---------------- STRUCTURE (12) ----------------
    _fs(name="htf_regime_enc", idx=0, family="STRUCTURE", allowed_range=(0, 2),
        definition="HTF (H4) regime as of bar: 0 bearish,1 neutral,2 bullish.",
        available_at="after H4 confirmation_bar <= entry",
        python_impl="FeatureEngine._htf_regime_enc", mql5_impl="GetHTFRegimeEnc",
        dtype="float32"),
    _fs(name="ltf_regime_enc", idx=1, family="STRUCTURE", allowed_range=(0, 2),
        definition="LTF (H1) regime as of bar.",
        available_at="after H1 confirmation_bar <= entry",
        python_impl="FeatureEngine._ltf_regime_enc", mql5_impl="GetLTFRegimeEnc",
        dtype="float32"),
    _fs(name="bos_count_recent", idx=2, family="STRUCTURE", allowed_range=(0, None),
        definition="Number of BOS events in last 50 confirmed bars.",
        available_at="event confirmation_bar <= entry",
        python_impl="FeatureEngine._bos_recent", mql5_impl="BOSCountRecent"),
    _fs(name="choch_count_recent", idx=3, family="STRUCTURE", allowed_range=(0, None),
        definition="Number of CHOCH events in last 50 confirmed bars.",
        available_at="event confirmation_bar <= entry",
        python_impl="FeatureEngine._choch_recent", mql5_impl="CHOCHCountRecent"),
    _fs(name="last_event_direction_enc", idx=4, family="STRUCTURE", allowed_range=(-1, 1),
        definition="Direction of last confirmed event: -1 bearish,0 none,1 bullish.",
        available_at="event confirmation_bar <= entry",
        python_impl="FeatureEngine._last_event_dir", mql5_impl="LastEventDirEnc",
        dtype="float32"),
    _fs(name="last_event_disp_atr", idx=5, family="STRUCTURE", allowed_range=(0, None),
        definition="ATR-normalized displacement of last confirmed event.",
        available_at="event confirmation_bar <= entry",
        python_impl="FeatureEngine._last_event_disp_atr", mql5_impl="LastEventDispATR"),
    _fs(name="last_event_age_bars", idx=6, family="STRUCTURE", allowed_range=(0, None),
        definition="Bars since last confirmed event (-1 if none).",
        available_at="event confirmation_bar <= entry",
        python_impl="FeatureEngine._last_event_age", mql5_impl="LastEventAgeBars"),
    _fs(name="protected_high", idx=7, family="STRUCTURE", allowed_range=(None, None),
        definition="Most recent active protected high price as of entry.",
        available_at="protected level confirmation_bar <= entry",
        python_impl="FeatureEngine._protected_high", mql5_impl="GetProtectedHigh"),
    _fs(name="protected_low", idx=8, family="STRUCTURE", allowed_range=(None, None),
        definition="Most recent active protected low price as of entry.",
        available_at="protected level confirmation_bar <= entry",
        python_impl="FeatureEngine._protected_low", mql5_impl="GetProtectedLow"),
    _fs(name="multi_leg_aligned", idx=9, family="STRUCTURE", allowed_range=(0, 1),
        definition="1 if HTF and LTF regime agree in direction, else 0.",
        available_at="both regime series <= entry",
        python_impl="FeatureEngine._multi_leg_aligned", mql5_impl="MultiLegAligned",
        dtype="float32"),
    _fs(name="leg_extension_atr", idx=10, family="STRUCTURE", allowed_range=(0, None),
        definition="Extension of current H1 leg in ATR units.",
        available_at="leg confirmation_bar <= entry",
        python_impl="FeatureEngine._leg_extension_atr", mql5_impl="LegExtensionATR"),
    _fs(name="structure_strength", idx=11, family="STRUCTURE", allowed_range=(0, 1),
        definition="0..1 quality of the most recent event (disp/disp_threshold).",
        available_at="event confirmation_bar <= entry",
        python_impl="FeatureEngine._structure_strength", mql5_impl="StructureStrength"),

    # ---------------- LIQUIDITY (7) ----------------
    _fs(name="nearest_liquidity_dist_atr", idx=12, family="LIQUIDITY", allowed_range=(0, None),
        definition="Distance to nearest active liquidity pool in ATR units.",
        available_at="pool confirmation_bar <= entry",
        python_impl="FeatureEngine._nearest_liq_dist", mql5_impl="NearestLiqDistATR"),
    _fs(name="nearest_liquidity_side_enc", idx=13, family="LIQUIDITY", allowed_range=(-1, 1),
        definition="Side of nearest pool vs price: -1 below,1 above,0 none.",
        available_at="pool confirmation_bar <= entry",
        python_impl="FeatureEngine._nearest_liq_side", mql5_impl="NearestLiqSideEnc",
        dtype="float32"),
    _fs(name="liquidity_swept", idx=14, family="LIQUIDITY", allowed_range=(0, 1),
        definition="1 if a pool was swept within last 10 bars, else 0.",
        available_at="sweep_bar <= entry",
        python_impl="FeatureEngine._liquidity_swept", mql5_impl="LiquiditySwept",
        dtype="float32"),
    _fs(name="sweep_depth_atr", idx=15, family="LIQUIDITY", allowed_range=(0, None),
        definition="Depth of most recent sweep in ATR units (0 if none).",
        available_at="sweep_bar <= entry",
        python_impl="FeatureEngine._sweep_depth", mql5_impl="SweepDepthATR"),
    _fs(name="post_sweep_reaction_atr", idx=16, family="LIQUIDITY", allowed_range=(0, None),
        definition="Post-sweep MFE in ATR units (0 if none).",
        available_at="reaction measured <= entry",
        python_impl="FeatureEngine._post_sweep_reaction", mql5_impl="PostSweepReactionATR"),
    _fs(name="eqh_eql_present", idx=17, family="LIQUIDITY", allowed_range=(0, 1),
        definition="1 if an EQH or EQL confirmed within last 100 bars.",
        available_at="equal-level confirmation_bar <= entry",
        python_impl="FeatureEngine._eqh_eql_present", mql5_impl="EQHEQLPresent",
        dtype="float32"),
    _fs(name="inducement_present", idx=18, family="LIQUIDITY", allowed_range=(0, 1),
        definition="1 if an inducement confirmed within last 50 bars.",
        available_at="inducement confirmation_bar <= entry",
        python_impl="FeatureEngine._inducement_present", mql5_impl="InducementPresent",
        dtype="float32"),

    # ---------------- ORDER BLOCK (8) ----------------
    _fs(name="ob_present", idx=19, family="ORDER_BLOCK", allowed_range=(0, 1),
        definition="1 if a fresh/touched OB exists as of entry.",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_present", mql5_impl="OBPresent",
        dtype="float32"),
    _fs(name="ob_direction_enc", idx=20, family="ORDER_BLOCK", allowed_range=(-1, 1),
        definition="Direction of nearest valid OB: -1 bearish,0 none,1 bullish.",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_dir", mql5_impl="OBDirectionEnc",
        dtype="float32"),
    _fs(name="ob_strength", idx=21, family="ORDER_BLOCK", allowed_range=(0, 1),
        definition="Quality score of nearest valid OB (0..1).",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_strength", mql5_impl="OBStrength"),
    _fs(name="ob_distance_atr", idx=22, family="ORDER_BLOCK", allowed_range=(0, None),
        definition="Distance to nearest valid OB zone in ATR units.",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_distance", mql5_impl="OBDistanceATR"),
    _fs(name="ob_age_bars", idx=23, family="ORDER_BLOCK", allowed_range=(0, None),
        definition="Age of nearest valid OB in bars.",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_age", mql5_impl="OBAgeBars"),
    _fs(name="ob_mitigation_count", idx=24, family="ORDER_BLOCK", allowed_range=(0, None),
        definition="Mitigation count of nearest valid OB.",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_mit_count", mql5_impl="OBMitigationCount"),
    _fs(name="ob_freshness_enc", idx=25, family="ORDER_BLOCK", allowed_range=(0, 2),
        definition="Freshness: 0 none,1 fresh,2 touched,3 stale.",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_freshness_enc", mql5_impl="OBFreshnessEnc",
        dtype="float32"),
    _fs(name="ob_mitigation_depth", idx=26, family="ORDER_BLOCK", allowed_range=(0, 1),
        definition="Deepest penetration pct of nearest valid OB (0..1).",
        available_at="OB confirmation_bar <= entry",
        python_impl="FeatureEngine._ob_mit_depth", mql5_impl="OBMitigationDepth"),

    # ---------------- FVG (6) ----------------
    _fs(name="fvg_present", idx=27, family="FVG", allowed_range=(0, 1),
        definition="1 if an open/partial FVG exists as of entry.",
        available_at="FVG confirmation_bar <= entry",
        python_impl="FeatureEngine._fvg_present", mql5_impl="FVGPresent",
        dtype="float32"),
    _fs(name="fvg_direction_enc", idx=28, family="FVG", allowed_range=(-1, 1),
        definition="Direction of nearest open FVG: -1 bearish,0 none,1 bullish.",
        available_at="FVG confirmation_bar <= entry",
        python_impl="FeatureEngine._fvg_dir", mql5_impl="FVGDirectionEnc",
        dtype="float32"),
    _fs(name="fvg_size_atr", idx=29, family="FVG", allowed_range=(0, None),
        definition="Size of nearest open FVG in ATR units.",
        available_at="FVG confirmation_bar <= entry",
        python_impl="FeatureEngine._fvg_size", mql5_impl="FVGSizeATR"),
    _fs(name="fvg_age_bars", idx=30, family="FVG", allowed_range=(0, None),
        definition="Age of nearest open FVG in bars.",
        available_at="FVG confirmation_bar <= entry",
        python_impl="FeatureEngine._fvg_age", mql5_impl="FVGAgeBars"),
    _fs(name="fvg_fill_pct", idx=31, family="FVG", allowed_range=(0, 1),
        definition="Fill percentage of nearest open FVG (0..1).",
        available_at="FVG confirmation_bar <= entry",
        python_impl="FeatureEngine._fvg_fill", mql5_impl="FVGFillPct"),
    _fs(name="fvg_freshness_enc", idx=32, family="FVG", allowed_range=(0, 3),
        definition="0 none,1 open,2 partially_filled,3 fully_filled.",
        available_at="FVG confirmation_bar <= entry",
        python_impl="FeatureEngine._fvg_freshness", mql5_impl="FVGFreshnessEnc",
        dtype="float32"),

    # ---------------- PREMIUM / DISCOUNT (4) ----------------
    _fs(name="pd_position", idx=33, family="PREMIUM_DISCOUNT", allowed_range=(0, 1),
        definition="Position within structural leg: (price-low)/(high-low).",
        available_at="leg confirmation_bar <= entry",
        python_impl="FeatureEngine._pd_position", mql5_impl="PDPosition"),
    _fs(name="pd_label_enc", idx=34, family="PREMIUM_DISCOUNT", allowed_range=(0, 2),
        definition="0 discount,1 equilibrium,2 premium.",
        available_at="leg confirmation_bar <= entry",
        python_impl="FeatureEngine._pd_label_enc", mql5_impl="PDLabelEnc",
        dtype="float32"),
    _fs(name="pd_distance_from_eq", idx=35, family="PREMIUM_DISCOUNT", allowed_range=(0, 1),
        definition="Normalized distance from equilibrium (0..1).",
        available_at="leg confirmation_bar <= entry",
        python_impl="FeatureEngine._pd_dist_eq", mql5_impl="PDDistanceFromEq"),
    _fs(name="pd_leg_span_atr", idx=36, family="PREMIUM_DISCOUNT", allowed_range=(0, None),
        definition="Current structural leg span in ATR units.",
        available_at="leg confirmation_bar <= entry",
        python_impl="FeatureEngine._pd_leg_span", mql5_impl="PDLegSpanATR"),

    # ---------------- MARKET REGIME (5) ----------------
    _fs(name="atr", idx=37, family="MARKET_REGIME", allowed_range=(0, None),
        definition="ATR(14) at entry bar.",
        available_at="entry bar only (backward-looking)",
        python_impl="FeatureEngine._atr", mql5_impl="GetATR"),
    _fs(name="atr_percentile", idx=38, family="MARKET_REGIME", allowed_range=(0, 1),
        definition="ATR percentile over lookback (0..1).",
        available_at="lookback bars <= entry",
        python_impl="FeatureEngine._atr_pct", mql5_impl="ATRPercentile"),
    _fs(name="daily_range_pct", idx=39, family="MARKET_REGIME", allowed_range=(0, 1),
        definition="Daily range / ATR ratio clipped to [0,1].",
        available_at="daily bar <= entry",
        python_impl="FeatureEngine._daily_range_pct", mql5_impl="DailyRangePct"),
    _fs(name="volatility_regime_enc", idx=40, family="MARKET_REGIME", allowed_range=(0, 2),
        definition="0 low,1 mid,2 high volatility regime.",
        available_at="percentile computed <= entry",
        python_impl="FeatureEngine._vol_regime", mql5_impl="VolatilityRegimeEnc",
        dtype="float32"),
    _fs(name="spread", idx=41, family="MARKET_REGIME", allowed_range=(0, None),
        definition="Spread at entry bar (points).",
        available_at="entry bar only",
        python_impl="FeatureEngine._spread", mql5_impl="GetSpread"),

    # ---------------- SESSION (2) ----------------
    _fs(name="session_enc", idx=42, family="SESSION", allowed_range=(0, 4),
        definition="0 asian,1 london,2 overlap,3 ny,4 off.",
        available_at="entry bar only",
        python_impl="FeatureEngine._session_enc", mql5_impl="GetSessionEnc",
        dtype="float32"),
    _fs(name="session_phase_enc", idx=43, family="SESSION", allowed_range=(0, 2),
        definition="0 open,1 mid,2 close within session.",
        available_at="entry bar only",
        python_impl="FeatureEngine._session_phase_enc", mql5_impl="GetSessionPhaseEnc",
        dtype="float32"),

    # ---------------- MACRO / NEWS (6) ----------------
    _fs(name="event_present", idx=44, family="MACRO_NEWS", allowed_range=(0, 1),
        definition="1 if a high-impact event active/upcoming within window.",
        available_at="event ts <= entry",
        python_impl="FeatureEngine._event_present", mql5_impl="EventPresent",
        dtype="float32"),
    _fs(name="event_importance", idx=45, family="MACRO_NEWS", allowed_range=(0, 3),
        definition="Importance 0..3 of nearest event.",
        available_at="event ts <= entry",
        python_impl="FeatureEngine._event_importance", mql5_impl="EventImportance",
        dtype="float32"),
    _fs(name="normalized_surprise", idx=46, family="MACRO_NEWS", allowed_range=(-1, 1),
        definition="Normalized surprise of nearest released event.",
        available_at="event release ts <= entry",
        python_impl="FeatureEngine._normalized_surprise", mql5_impl="NormalizedSurprise"),
    _fs(name="surprise_zscore", idx=47, family="MACRO_NEWS", allowed_range=(None, None),
        definition="Historical surprise z-score (0 if unavailable).",
        available_at="event release ts <= entry",
        python_impl="FeatureEngine._surprise_z", mql5_impl="SurpriseZScore"),
    _fs(name="expected_gold_dir_enc", idx=48, family="MACRO_NEWS", allowed_range=(-1, 1),
        definition="Expected gold implication: -1 bearish,0 neutral,1 bullish.",
        available_at="event release ts <= entry",
        python_impl="FeatureEngine._expected_gold_dir", mql5_impl="ExpectedGoldDirEnc",
        dtype="float32"),
    _fs(name="observed_reaction_atr", idx=49, family="MACRO_NEWS", allowed_range=(None, None),
        definition="Observed gold 5-min reaction in ATR units (0 if none).",
        available_at="reaction horizon <= entry",
        python_impl="FeatureEngine._observed_reaction", mql5_impl="ObservedReactionATR"),

    # ---------------- SETUP GEOMETRY (6) ----------------
    _fs(name="htf_alignment_enc", idx=50, family="SETUP_GEOMETRY", allowed_range=(-1, 1),
        definition="HTF alignment with trade direction: -1,0,1.",
        available_at="HTF regime <= entry",
        python_impl="FeatureEngine._htf_alignment", mql5_impl="HTFAlignmentEnc",
        dtype="float32"),
    _fs(name="ltf_alignment_enc", idx=51, family="SETUP_GEOMETRY", allowed_range=(-1, 1),
        definition="LTF alignment with trade direction.",
        available_at="LTF regime <= entry",
        python_impl="FeatureEngine._ltf_alignment", mql5_impl="LTFAlignmentEnc",
        dtype="float32"),
    _fs(name="distance_to_entry_atr", idx=52, family="SETUP_GEOMETRY", allowed_range=(0, None),
        definition="Distance from current price to ideal entry in ATR units.",
        available_at="entry bar only",
        python_impl="FeatureEngine._dist_to_entry", mql5_impl="DistanceToEntryATR"),
    _fs(name="sl_distance_atr", idx=53, family="SETUP_GEOMETRY", allowed_range=(0, None),
        definition="SL distance in ATR units.",
        available_at="entry bar only",
        python_impl="FeatureEngine._sl_distance", mql5_impl="SLDistanceATR"),
    _fs(name="tp_distance_atr", idx=54, family="SETUP_GEOMETRY", allowed_range=(0, None),
        definition="TP distance in ATR units.",
        available_at="entry bar only",
        python_impl="FeatureEngine._tp_distance", mql5_impl="TPDistanceATR"),
    _fs(name="available_rr", idx=55, family="SETUP_GEOMETRY", allowed_range=(0, None),
        definition="Available reward:risk (tp_dist/sl_dist).",
        available_at="entry bar only",
        python_impl="FeatureEngine._available_rr", mql5_impl="AvailableRR"),
]

FEATURE_NAMES: List[str] = [f.name for f in FEATURE_SPECS]
FEATURE_INDICES = {f.name: f.index for f in FEATURE_SPECS}
N_FEATURES = len(FEATURE_SPECS)


def contract_summary() -> dict:
    families = {}
    for f in FEATURE_SPECS:
        families.setdefault(f.family, 0)
        families[f.family] += 1
    return {
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "n_features": N_FEATURES,
        "families": families,
        "feature_names": FEATURE_NAMES,
    }
