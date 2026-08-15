"""V38.2 feature contract SKELETON.

NOT finalized. Feature definitions are placeholders until genuine M5/M15 data
allow a data-driven feature audit (redundancy, permutation importance, stability,
ablation). The final feature count is NOT predetermined — it is determined by
economic/SMC meaning, leakage safety, data availability, redundancy analysis,
permutation importance, walk-forward stability, and ablation testing.

Families (10) — adds EXECUTION_TIMEFRAME over V38.1's 9 families:

  STRUCTURE, LIQUIDITY, ORDER_BLOCK, FVG, PREMIUM_DISCOUNT, MARKET_REGIME,
  SESSION, MACRO_NEWS, SETUP_GEOMETRY, EXECUTION_TIMEFRAME

Each finalized feature MUST carry: name, index, dtype, valid_range, definition,
source, timestamp_semantics (available_at <= entry), python_impl, mql5_impl,
leakage_status, test_case.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

FEATURE_CONTRACT_VERSION = "V38.2_SKELETON"

FAMILIES = (
    "STRUCTURE", "LIQUIDITY", "ORDER_BLOCK", "FVG", "PREMIUM_DISCOUNT",
    "MARKET_REGIME", "SESSION", "MACRO_NEWS", "SETUP_GEOMETRY",
    "EXECUTION_TIMEFRAME",
)


@dataclass(frozen=True)
class FeatureSpecSkeleton:
    name: str
    family: str
    definition: str
    source: str
    timestamp_semantics: str
    leakage_status: str = "PENDING_VALIDATION"
    status: str = "SKELETON"     # SKELETON -> CANDIDATE -> VALIDATED -> FINAL
    available_at: str = ""
    python_impl: str = ""
    mql5_impl: str = ""
    test_case: str = ""
    # Phase E: explicit data dependency + point-in-time status + missingness
    # semantics. A blocked feature MUST NOT silently become 0.
    data_dependency: str = ""        # the genuine data this feature requires
    pit_status: str = "PENDING"      # see PIT_* constants below
    missingness_treatment: str = ""  # defined semantic when data absent


# Point-in-time statuses for feature audit.
PIT_REQUIRED = "PIT_REQUIRED"               # look-ahead-contaminated unless PIT
PIT_NOT_REQUIRED = "PIT_NOT_REQUIRED"       # uses no future/revised values
PIT_PREFERRED = "PIT_PREFERRED"              # PIT improves integrity, not mandatory
PIT_BLOCKED_NO_SOURCE = "PIT_BLOCKED_NO_SOURCE"  # needs PIT data with no free source
PIT_PENDING = "PENDING"

# Missingness semantics — a blocked feature is ABSENT (NaN + flag), NEVER zero.
MISS_ABSENT_NAN = "ABSENT (NaN + macro_data_blocked flag); never 0"
MISS_ZERO_SENTINEL = "zero sentinel ONLY where 0 is the genuine value (e.g. no event)"
MISS_EXCLUDE_ROW = "row excluded from training when feature required but absent"


def macro_features_blocked_without_pit_forecast() -> list:
    """Forecast-dependent macro features that MUST stay blocked until genuine
    point-in-time historical forecast consensus is supplied. These must not
    be substituted with current/revised forecasts and must not silently become 0.
    Per the V38.2 macro decision (Option B), these features are RETAINED in the
    design — they are NOT removed, weakened, replaced, or approximated.
    """
    return ["surprise", "surprise_pct", "surprise_zscore", "macro_direction"]


# Skeleton placeholders grouped by family. These are NOT the final features —
# they document the *dimensions* that the data-driven audit will evaluate. The
# audit may add, remove, or merge candidates. Final indices are assigned only
# when a feature reaches VALIDATED status.

SKELETON: List[FeatureSpecSkeleton] = [
    # STRUCTURE
    FeatureSpecSkeleton("htf_regime", "STRUCTURE", "H4 BOS/CHOCH regime bias at entry.",
                        "structure_engine", "H4 confirmation_bar <= entry bar"),
    FeatureSpecSkeleton("bos_count_recent", "STRUCTURE", "Recent BOS count at entry.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("choch_count_recent", "STRUCTURE", "Recent CHOCH count at entry.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("last_event_direction", "STRUCTURE", "Direction of last BOS/CHOCH.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("last_event_disp_atr", "STRUCTURE", "Displacement (ATR) of last structure event.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("last_event_age_bars", "STRUCTURE", "Bars since last structure event.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("protected_high", "STRUCTURE", "Protected high level at entry.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("protected_low", "STRUCTURE", "Protected low level at entry.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("multi_leg_aligned", "STRUCTURE", "Multi-leg structure alignment.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("structure_strength", "STRUCTURE", "Composite structure strength score.",
                        "structure_engine", "confirmation_bar <= entry"),
    # LIQUIDITY
    FeatureSpecSkeleton("nearest_liquidity_dist_atr", "LIQUIDITY", "ATR-distance to nearest liquidity pool.",
                        "liquidity_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("liquidity_type", "LIQUIDITY", "Type of nearest liquidity (swing/session/EQH/EQL).",
                        "liquidity_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("liquidity_swept", "LIQUIDITY", "Whether nearest liquidity was swept pre-entry.",
                        "liquidity_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("sweep_depth_atr", "LIQUIDITY", "Depth of latest sweep in ATR.",
                        "liquidity_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("post_sweep_reaction_atr", "LIQUIDITY", "Reaction magnitude after latest sweep.",
                        "liquidity_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("eqh_eql_present", "LIQUIDITY", "EQH/EQL present in recent window.",
                        "liquidity_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("inducement_present", "LIQUIDITY", "Inducement liquidity present.",
                        "liquidity_engine", "confirmation_bar <= entry"),
    # ORDER_BLOCK
    FeatureSpecSkeleton("ob_present", "ORDER_BLOCK", "Active OB present at entry.",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_strength", "ORDER_BLOCK", "OB quality/strength score.",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_width_atr", "ORDER_BLOCK", "OB width in ATR.",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_age_bars", "ORDER_BLOCK", "Bars since OB creation.",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_mitigation_pct", "ORDER_BLOCK", "OB mitigation percentage.",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_lifecycle_state", "ORDER_BLOCK", "OB lifecycle state (DETECTED..EXPIRED).",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_distance_to_entry_atr", "ORDER_BLOCK", "ATR-distance from entry to OB.",
                        "ob_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("ob_reaction_after_mitigation", "ORDER_BLOCK", "Reaction after OB mitigation.",
                        "ob_engine", "confirmation_bar <= entry"),
    # FVG
    FeatureSpecSkeleton("fvg_present", "FVG", "Active FVG present at entry.",
                        "fvg_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("fvg_direction", "FVG", "Direction of nearest FVG.",
                        "fvg_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("fvg_size_atr", "FVG", "FVG size in ATR.",
                        "fvg_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("fvg_age_bars", "FVG", "Bars since FVG creation.",
                        "fvg_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("fvg_fill_pct", "FVG", "FVG fill percentage.",
                        "fvg_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("fvg_lifecycle_state", "FVG", "FVG lifecycle state.",
                        "fvg_engine", "confirmation_bar <= entry"),
    # PREMIUM_DISCOUNT
    FeatureSpecSkeleton("pd_position", "PREMIUM_DISCOUNT", "Position within premium/discount array (0..1).",
                        "pd_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("pd_distance_from_eq", "PREMIUM_DISCOUNT", "Distance from equilibrium.",
                        "pd_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("pd_leg_span_atr", "PREMIUM_DISCOUNT", "PD leg span in ATR.",
                        "pd_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("pd_label", "PREMIUM_DISCOUNT", "Premium/discount label.",
                        "pd_engine", "confirmation_bar <= entry"),
    # MARKET_REGIME
    FeatureSpecSkeleton("atr", "MARKET_REGIME", "Current ATR value.",
                        "bars", "close_bar <= entry"),
    FeatureSpecSkeleton("atr_percentile", "MARKET_REGIME", "ATR percentile in recent window.",
                        "bars", "close_bar <= entry"),
    FeatureSpecSkeleton("volatility_regime", "MARKET_REGIME", "Volatility regime label.",
                        "bars", "close_bar <= entry"),
    FeatureSpecSkeleton("daily_range_pct", "MARKET_REGIME", "Daily range percentage.",
                        "bars", "close_bar <= entry"),
    FeatureSpecSkeleton("session_range_pct", "MARKET_REGIME", "Session range percentage.",
                        "bars", "close_bar <= entry"),
    # SESSION
    FeatureSpecSkeleton("session", "SESSION", "Trading session at entry.",
                        "bars", "close_bar <= entry"),
    FeatureSpecSkeleton("session_phase", "SESSION", "Phase within session.",
                        "bars", "close_bar <= entry"),
    # MACRO_NEWS
    # Phase E: forecast-dependent features are PIT_BLOCKED_NO_SOURCE until a
    # genuine point-in-time historical forecast consensus is supplied. They must
    # NOT be substituted with current/revised forecasts and MUST NOT silently
    # become 0 — missingness is ABSENT (NaN + macro_data_blocked flag).
    FeatureSpecSkeleton("latest_event_importance", "MACRO_NEWS", "Importance of latest relevant macro event.",
                        "macro_engine", "event_ts <= entry (DATA-BLOCKED until calendar supplied)",
                        data_dependency="genuine event ts + importance (calendar; importance is a stable label, not forecast)",
                        pit_status=PIT_NOT_REQUIRED,
                        missingness_treatment=MISS_ABSENT_NAN),
    FeatureSpecSkeleton("surprise", "MACRO_NEWS", "Raw surprise of latest event (actual - forecast).",
                        "macro_engine", "event_ts <= entry (DATA-BLOCKED; PIT forecast required)",
                        data_dependency="PIT actual + PIT historical forecast consensus (survey)",
                        pit_status=PIT_BLOCKED_NO_SOURCE,
                        missingness_treatment=MISS_ABSENT_NAN),
    FeatureSpecSkeleton("surprise_pct", "MACRO_NEWS", "Surprise normalized: (actual - forecast) / max(|previous|, |forecast|, eps).",
                        "macro_engine", "event_ts <= entry (DATA-BLOCKED; PIT forecast + PIT previous required)",
                        data_dependency="PIT actual + PIT forecast + PIT previous (previous-as-known-at-T)",
                        pit_status=PIT_BLOCKED_NO_SOURCE,
                        missingness_treatment=MISS_ABSENT_NAN),
    FeatureSpecSkeleton("surprise_zscore", "MACRO_NEWS", "Z-scored surprise (>=30 prior PIT surprises per currency x category).",
                        "macro_engine", "event_ts <= entry (DATA-BLOCKED; PIT forecast required)",
                        data_dependency=">=30 prior PIT surprises (actual+forecast history) per (currency,category)",
                        pit_status=PIT_BLOCKED_NO_SOURCE,
                        missingness_treatment=MISS_ABSENT_NAN),
    FeatureSpecSkeleton("macro_direction", "MACRO_NEWS", "Directional macro pressure (expected gold implication from PIT surprise).",
                        "macro_engine", "event_ts <= entry (DATA-BLOCKED; PIT forecast required)",
                        data_dependency="PIT actual + PIT forecast + category + directionality",
                        pit_status=PIT_BLOCKED_NO_SOURCE,
                        missingness_treatment=MISS_ABSENT_NAN),
    FeatureSpecSkeleton("time_since_event", "MACRO_NEWS", "Time since latest event.",
                        "macro_engine", "event_ts <= entry (DATA-BLOCKED until calendar supplied)",
                        data_dependency="genuine event release ts (PIT-safe; release time is known, not forecast)",
                        pit_status=PIT_NOT_REQUIRED,
                        missingness_treatment=MISS_ABSENT_NAN),
    FeatureSpecSkeleton("observed_reaction_state", "MACRO_NEWS", "Post-event reaction state (LABEL-side only, never a feature). Measured from price after event; must NOT use price after the candidate setup timestamp.",
                        "macro_engine", "reaction horizon completes <= entry (DATA-BLOCKED until calendar supplied)",
                        data_dependency="genuine event ts + price bars after event (price-measured, leakage-safe by construction)",
                        pit_status=PIT_NOT_REQUIRED,
                        missingness_treatment=MISS_ABSENT_NAN),
    # SETUP_GEOMETRY
    FeatureSpecSkeleton("distance_to_entry_atr", "SETUP_GEOMETRY", "ATR-distance to entry reference price.",
                        "setup_detector", "computed at entry"),
    FeatureSpecSkeleton("leg_extension_atr", "SETUP_GEOMETRY", "Impulse leg extension in ATR.",
                        "structure_engine", "confirmation_bar <= entry"),
    FeatureSpecSkeleton("rr", "SETUP_GEOMETRY", "Planned risk:reward.",
                        "setup_detector", "computed at entry"),
    FeatureSpecSkeleton("sl_distance_atr", "SETUP_GEOMETRY", "Stop distance in ATR.",
                        "setup_detector", "computed at entry"),
    FeatureSpecSkeleton("target_distance_atr", "SETUP_GEOMETRY", "Target distance in ATR.",
                        "setup_detector", "computed at entry"),
    FeatureSpecSkeleton("entry_precision_score", "SETUP_GEOMETRY", "Entry precision quality.",
                        "setup_detector", "computed at entry"),
    # EXECUTION_TIMEFRAME (NEW in V38.2 — requires M5; undefined until data present)
    FeatureSpecSkeleton("m5_ob_formation_bars", "EXECUTION_TIMEFRAME",
                        "Bars since M5 OB formed at entry. UNDEFINED until M5 data present.",
                        "ob_engine (M5)", "M5 confirmation_bar <= entry (DATA-BLOCKED)"),
    FeatureSpecSkeleton("m5_fvg_fill_progression", "EXECUTION_TIMEFRAME",
                        "M5 FVG fill progression at entry. UNDEFINED until M5 data present.",
                        "fvg_engine (M5)", "M5 confirmation_bar <= entry (DATA-BLOCKED)"),
    FeatureSpecSkeleton("m5_liquidity_sweep_micro", "EXECUTION_TIMEFRAME",
                        "M5 liquidity sweep micro-structure. UNDEFINED until M5 data present.",
                        "liquidity_engine (M5)", "M5 confirmation_bar <= entry (DATA-BLOCKED)"),
    FeatureSpecSkeleton("m5_entry_precision", "EXECUTION_TIMEFRAME",
                        "M5 entry-precision geometry. UNDEFINED until M5 data present.",
                        "setup_detector (M5)", "computed at entry (DATA-BLOCKED)"),
]


def skeleton_summary() -> dict:
    from collections import Counter
    fams = Counter(f.family for f in SKELETON)
    return {
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "n_skeleton_features": len(SKELETON),
        "families": dict(fams),
        "status": "SKELETON — not finalized; final count determined by data-driven audit",
        "final_count_NOT_predetermined": True,
        "note": ("No feature is FINAL until it passes redundancy analysis, permutation "
                 "importance, walk-forward stability, and ablation on genuine M5/M15 data."),
    }
