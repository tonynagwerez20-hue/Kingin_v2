"""V38 configuration and version metadata (single source of truth)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Versioning — every artifact carries these so lineage is auditable.
# ---------------------------------------------------------------------------
DATASET_VERSION = "dataset_v38_2026_08"
FEATURE_CONTRACT_VERSION = "V38.1"
TRAINING_VERSION = "lgbm_v38_1"
MODEL_VERSION = "v38.1"
ONNX_VERSION = "onnx_v38_1"

# Repository-root-relative paths.
BACKEND_DIR = Path(__file__).resolve().parent.parent          # .../backend
V38_DIR = Path(__file__).resolve().parent                      # .../backend/v38
DATA_DIR = BACKEND_DIR / "data"
ARTIFACT_DIR = BACKEND_DIR / "models" / "v38"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# Raw price data shipped with the repository (XAUUSD).
H1_8Y_CSV = DATA_DIR / "XAUUSDm_H1_8 years data.csv"
H1_2024_CSV = DATA_DIR / "XAUUSDm_H1_202401012300_202603032000.csv"
H4_20Y_CSV = DATA_DIR / "backtest_20y" / "XAUUSD_H4_20y.csv"


@dataclass(frozen=True)
class V38Config:
    symbol: str = "XAUUSD"

    # --- swing engine ------------------------------------------------------
    swing_strength: int = 2          # fractal: k bars each side strictly lower/higher
    swing_min_spacing: int = 1      # min bars between adjacent pivots of same type

    # --- structure / BOS / CHOCH ------------------------------------------
    bos_close_required: bool = False  # True => close-based break; False => wick-based
    bos_min_atr_mult: float = 0.10   # min displacement (ATR-normalized) for a valid BOS
    choch_min_atr_mult: float = 0.30  # larger displacement required for character change
    displacement_atr_period: int = 14

    # --- order block -------------------------------------------------------
    ob_max_age_bars: int = 200       # OB invalidated if untouched longer than this
    ob_close_through_invalidates: bool = True

    # --- FVG ---------------------------------------------------------------
    fvg_min_size_atr: float = 0.05   # gaps smaller than this are noise

    # --- liquidity / EQH-EQL ----------------------------------------------
    eqh_eql_atr_tol: float = 0.15    # equal-level tolerance in ATR units
    liquidity_cluster_atr: float = 0.25

    # --- premium/discount -------------------------------------------------
    pd_equilibrium_band: float = 0.10  # ±10% around 0.5 counts as "equilibrium"

    # --- volatility regime -------------------------------------------------
    atr_period: int = 14
    atr_percentile_lookback: int = 200
    vol_regime_low_pct: float = 25.0
    vol_regime_high_pct: float = 75.0

    # --- sessions (server time, UTC assumed for CSV data) -----------------
    session_defs: Dict[str, tuple] = field(default_factory=lambda: {
        "asian":   (0, 7),
        "london":  (7, 12),
        "overlap": (12, 16),
        "ny":      (16, 21),
        "off":     (21, 24),
    })

    # --- labeling (barrier method) ----------------------------------------
    label_tp_r: float = 2.0          # TP = +2R
    label_sl_r: float = 1.0         # SL = -1R
    label_max_bars: int = 20         # horizon for H1 (≈20h); rescaled per TF
    label_simultaneous_policy: str = "SL_wins"  # documented tie-break

    # --- dataset -----------------------------------------------------------
    min_setup_quality: float = 0.30
    target_setups: int = 100_000

    # --- macro / news ------------------------------------------------------
    news_mode: str = "NEWS_FILTER_ONLY"   # one of NEWS_* constants
    news_reaction_horizons: List[int] = field(
        default_factory=lambda: [1, 5, 15, 30, 60, 240, 1440])
    news_silence_before_event_min: int = 0

    # --- risk --------------------------------------------------------------
    risk_pct_account: float = 0.01    # 1% monetary risk per trade
    max_daily_loss_pct: float = 0.03
    max_total_drawdown_pct: float = 0.10
    max_consecutive_losses: int = 5
    max_trades_per_day: int = 10

    # --- ML ----------------------------------------------------------------
    lgbm_params: Dict = field(default_factory=lambda: {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "n_estimators": 400,
        "learning_rate": 0.03,
        "num_leaves": 63,
        "max_depth": -1,
        "min_child_samples": 50,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
        "random_state": 42,
        "deterministic": True,
    })
    calibration_method: str = "auto"   # "isotonic" | "sigmoid" | "auto" | "none"
    onnx_tolerance: float = 1e-4       # max abs diff LightGBM vs ONNX proba
    # 1e-4 (not 1e-5): tree-ensemble ONNX uses float32 leaf-delta accumulation
    # which differs from LightGBM's float64 path by ~1e-5..1e-4; this is the
    # standard, expected equivalence tolerance for gradient-boosted trees.
    equivalence_n_samples: int = 1000

    # --- walk-forward ------------------------------------------------------
    wf_train_bars: int = 4000
    wf_test_bars: int = 800
    wf_step_bars: int = 800


# News mode constants — the mode actually changes behaviour.
NEWS_OFF = "NEWS_OFF"
NEWS_FILTER_ONLY = "NEWS_FILTER_ONLY"
NEWS_REACTIVE = "NEWS_REACTIVE"
NEWS_DIRECTIONAL = "NEWS_DIRECTIONAL"
NEWS_HYBRID = "NEWS_HYBRID"
NEWS_MODES = (NEWS_OFF, NEWS_FILTER_ONLY, NEWS_REACTIVE,
              NEWS_DIRECTIONAL, NEWS_HYBRID)

DEFAULT_CONFIG = V38Config()
