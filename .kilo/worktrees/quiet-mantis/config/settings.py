import os
from pathlib import Path

# --- PROJECT PATHS ---
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR      = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# --- NETWORK CONFIG ---
API_URL      = os.getenv("API_URL",      "http://localhost:8000")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", 3000))   # React lite dashboard
DTC_HOST     = os.getenv("DTC_HOST",     "127.0.0.1")
DTC_PORT_LIVE = int(os.getenv("DTC_PORT_LIVE", 11099))
DTC_PORT_HIST = int(os.getenv("DTC_PORT_HIST", 11098))

# --- TRADING CONFIG ---
DEFAULT_ACCOUNT_BALANCE  = 10000.0
PIP_VALUE                = 10.0
PIP_SIZE                 = 0.01
BALANCE_REFRESH_INTERVAL = 60
LOOP_INTERVAL            = 1

# --- GOLD SPREAD CONFIG ---
# MT5 returns spread in POINTS (integer). Gold: 10 points = 1 pip.
# CRORules.max_spread_pips is in PIPS — the controller converts automatically.
MAX_SPREAD_POINTS = 50    # 50 pts = 5 pips on Gold — block above this
MAX_SPREAD_PIPS   = 5.0   # used by CRORules

# --- SYSTEM FLAGS ---
ENABLE_CLEANUP   = False
ENABLE_IGOF      = True   # Active filtration enabled

# --- NEWS LAYER ---
ENABLE_NEWS_LAYER  = True
ENABLE_NEWS_SCALP  = False  # set True to enable post-news scalp trades
FINNHUB_API_KEY    = os.getenv("FINNHUB_API_KEY", "")

# --- REGIME THRESHOLDS (calibrated for Gold M15) ---
REGIME_VOLATILE_PCT_THRESHOLD = 0.0008   # 0.08% pct-return std-dev on M15
REGIME_RANGING_ADR_RATIO      = 0.25     # today < 25% of ADR = ranging

# --- SYMBOLS ---
DEFAULT_SYMBOLS = ["XAUUSD", "GC", "ZN", "6E", "ES"]
