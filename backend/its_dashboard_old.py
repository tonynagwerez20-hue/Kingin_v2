"""
its_dashboard.py — ITS Live Trading Dashboard  v4.0 (Grid Aesthetic Edition)
=============================================================================
Redesign goals:
  - True full-bleed grid: zero dead space, every panel fills its cell
  - Rich panel headers with colored left-border accent stripe + dot indicator
  - Badge/chip components for bias, signal, layer status with background colors
  - Consistent spacing scale: 6 / 10 / 16 px
  - StatTiles with per-metric top accent stripes
  - Color-coded position rows (BUY=green, SELL=red)
  - Warning rows with left accent bar
  - Styled scrollbar on log panel
  - Hover effects on all buttons
  - Trade History header pre-built
  - Demo mode auto-loads so UI is never empty
"""

import json
import math
import os
import time
import subprocess
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime, timezone
from collections import deque

# ── Path anchor ───────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "engine_state.json")

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = "#0d1117"
PANEL     = "#161b27"
PANEL2    = "#1e2535"
PANEL3    = "#252d3d"
BORDER    = "#252d3d"
BORDER2   = "#2f3a52"
BORDER3   = "#3d4f6e"

ACCENT    = "#3b82f6"
ACCENT2   = "#1d4ed8"
ACCENT_DIM= "#1e3a6e"

GREEN     = "#10b981"
GREEN2    = "#059669"
GREEN_BG  = "#052e1c"
GREEN_DIM = "#0a3d2b"

RED       = "#f43f5e"
RED2      = "#be123c"
RED_BG    = "#2d0a14"

AMBER     = "#f59e0b"
AMBER2    = "#b45309"
AMBER_BG  = "#2d1c03"

PURPLE    = "#a855f7"
PURPLE_BG = "#1e0a35"

CYAN      = "#06b6d4"
CYAN_BG   = "#031a20"

TEXT      = "#e2e8f0"
SUBTEXT   = "#64748b"
DIMTEXT   = "#334155"
WHITE     = "#f8fafc"
HEADER_BG = "#0f1623"

# ── Fonts ─────────────────────────────────────────────────────────────────────
_UI_CANDIDATES   = ["Segoe UI", "Trebuchet MS", "Verdana", "Tahoma", "Arial"]
_MONO_CANDIDATES = ["IBM Plex Mono", "Consolas", "Lucida Console", "Courier New"]

def _best_font(candidates):
    available = tkfont.families()
    for f in candidates:
        if f in available:
            return f
    return candidates[-1]

UI_FONT   = None
MONO_FONT = None

# ── Layer names ───────────────────────────────────────────────────────────────
LAYER_NAMES = [
    "KillzoneFilterLayer", "MechanicalStructureLayer", "LiquiditySweepLayer",
    "DisplacementLayer",   "FVGDiscountLayer",         "MicroMSSLayer",
    "NewsEventLayer",
]
LAYER_SHORT = {
    "KillzoneFilterLayer":      "Killzone",
    "MechanicalStructureLayer": "Structure",
    "LiquiditySweepLayer":      "Liq Sweep",
    "DisplacementLayer":        "Displace",
    "FVGDiscountLayer":         "FVG/IFVG",
    "MicroMSSLayer":            "Micro MSS",
    "NewsEventLayer":           "News",
}

# ── Demo state ────────────────────────────────────────────────────────────────
def _demo_state(session: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp": now, "symbol": "XAUUSD", "bias": "BULLISH",
        "current_price": 3125.50, "signal_action": "LONG",
        "entry_price": 3125.50, "stop_loss": 3120.00, "take_profit": 3135.00,
        "lot_size": 0.01, "execution_type": "MARKET", "confluence_score": 6.0,
        "killzone_name": "London Open", "session_time": "08:00-11:00 UTC",
        "rr_ratio": "1:1.91",
        "layers": [
            {"name": n, "passed": i < 6, "score": 1.0 if i < 6 else 0.0,
             "reason": "DEMO"} for i, n in enumerate(LAYER_NAMES)
        ],
        "last_trade": {
            "action": "LONG", "symbol": "XAUUSD", "price": 3115.00,
            "sl": 3110.00, "tp": 3125.00, "lots": 0.01,
            "bias": "BULLISH", "execution_type": "MARKET",
            "confluence_score": 5.75, "timestamp": now,
        },
        "account_equity":  session.get("equity",  88.50),
        "account_balance": session.get("balance", 86.80),
        "floating_pnl": 1.70, "open_trades_count": 1,
        "risk_tier": "Standard",
        "open_positions": [{
            "symbol": "XAUUSD", "type": "BUY", "lots": 0.01,
            "open_price": 3110.00, "current_price": 3112.50,
            "sl": 3105.00, "tp": 3120.00, "floating_pnl": 0.55,
            "open_time": now,
        }],
        "active_warnings": ["DEMO MODE  -  engine_state.json not found"],
        "pipeline_logs":   ["[DEMO] Engine ready", "[DEMO] Waiting for signal"],
    }

# ── ITS Logo ─────────────────────────────────────────────────────────────────
def draw_its_logo(canvas: tk.Canvas, x: int, y: int, size: int = 18) -> None:
    pts, pts2 = [], []
    for i in range(6):
        a = math.radians(60 * i - 30)
        pts.extend([x + size * math.cos(a), y + size * math.sin(a)])
        s2 = size * 0.72
        pts2.extend([x + s2 * math.cos(a), y + s2 * math.sin(a)])
    canvas.create_polygon(pts,  fill=PANEL3,  outline=ACCENT,  width=2)
    canvas.create_polygon(pts2, fill="",      outline=ACCENT2, width=1)
    canvas.create_text(x, y, text="ITS", fill=ACCENT,
                       font=(UI_FONT, int(size * 0.5), "bold"))

# ══════════════════════════════════════════════════════════════════════════════
# Component library
# ══════════════════════════════════════════════════════════════════════════════

def hsep(parent, color=BORDER2, padx=10, pady=4):
    tk.Frame(parent, bg=color, height=1).pack(fill="x", padx=padx, pady=pady)

def section_label(parent, text):
    f = tk.Frame(parent, bg=PANEL2)
    f.pack(fill="x")
    tk.Label(f, text=f"  {text.upper()}",
             bg=PANEL2, fg=SUBTEXT,
             font=(UI_FONT, 7, "bold"),
             anchor="w").pack(side="left", pady=5)

def kv_row(parent, label_text, label_fg=SUBTEXT, value_fg=TEXT,
           label_font=None, value_font=None, pady=3, padx=14):
    f = tk.Frame(parent, bg=PANEL)
    f.pack(fill="x", padx=padx, pady=pady)
    tk.Label(f, text=label_text, bg=PANEL, fg=label_fg,
             font=label_font or (UI_FONT, 8), anchor="w").pack(side="left")
    var = tk.StringVar(value="--")
    lbl = tk.Label(f, textvariable=var, bg=PANEL, fg=value_fg,
                   font=value_font or (MONO_FONT, 9, "bold"), anchor="e")
    lbl.pack(side="right")
    return var, lbl


class StatTile:
    """Metric tile with per-metric top accent stripe."""
    def __init__(self, parent, label, color, row, col):
        f = tk.Frame(parent, bg=PANEL3, padx=12, pady=2)
        f.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        tk.Frame(f, bg=color, height=3).pack(fill="x", pady=(0, 8))
        tk.Label(f, text=label.upper(), bg=PANEL3, fg=SUBTEXT,
                 font=(UI_FONT, 7)).pack(anchor="w")
        self.var = tk.StringVar(value="--")
        self.lbl = tk.Label(f, textvariable=self.var,
                            bg=PANEL3, fg=color,
                            font=(MONO_FONT, 15, "bold"))
        self.lbl.pack(anchor="w", pady=(3, 4))


class GridPanel:
    """
    Full-bleed panel for a grid cell.
    Visual features:
      - 1 px outer border (BORDER2)
      - Panel header: PANEL2 bg, 4px left accent bar, dot indicator, bold title
      - 1 px separator below header
      - Expandable body
    """
    def __init__(self, parent: tk.Frame, title: str,
                 accent: str = ACCENT, icon: str = "",
                 row: int = 0, col: int = 0,
                 rowspan: int = 1, colspan: int = 1):
        self._accent = accent

        # Outer border frame
        self.frame = tk.Frame(parent, bg=BORDER2, highlightthickness=0)
        self.frame.grid(row=row, column=col,
                        rowspan=rowspan, columnspan=colspan,
                        padx=2, pady=2, sticky="nsew")

        # Inner container
        inner = tk.Frame(self.frame, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # Header row
        hdr = tk.Frame(inner, bg=PANEL2)
        hdr.pack(fill="x")

        # Left accent bar (4 px)
        tk.Frame(hdr, bg=accent, width=4).pack(side="left", fill="y")

        # Dot indicator
        dot_c = tk.Canvas(hdr, bg=PANEL2, width=10, height=10,
                          highlightthickness=0)
        dot_c.pack(side="left", padx=(8, 4), pady=9)
        dot_c.create_oval(1, 1, 9, 9, fill=accent, outline="")

        # Title
        full_title = (icon + "  " + title) if icon else title
        tk.Label(hdr, text=full_title.upper(),
                 bg=PANEL2, fg=TEXT,
                 font=(UI_FONT, 8, "bold"),
                 anchor="w").pack(side="left", pady=9)

        # Separator
        tk.Frame(inner, bg=BORDER2, height=1).pack(fill="x")

        # Body
        self.body = tk.Frame(inner, bg=PANEL)
        self.body.pack(fill="both", expand=True)

    def toggle_visibility(self) -> bool:
        if self.frame.winfo_ismapped():
            self.frame.grid_remove(); return False
        else:
            self.frame.grid(); return True


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════
class DashboardApp:
    VERSION    = "4.0"
    POLL_MS    = 2000

    def __init__(self, root: tk.Tk, session: dict):
        global UI_FONT, MONO_FONT
        self._root     = root
        self._session  = session
        self._online   = False
        self._start_ts = time.time()
        self._seen_log_msgs   = set()
        self._pos_row_vars    = []
        self._pos_row_lbls    = []
        self._warn_vars       = []
        self._warn_lbls       = []

        UI_FONT   = _best_font(_UI_CANDIDATES)
        MONO_FONT = _best_font(_MONO_CANDIDATES)

        self._setup_window()
        self._build_header()
        self._build_engine_bar()
        self._build_grid()
        self._build_panels()
        self._build_toggle_bar()
        self._root.after(150, self._poll_state)
        self._root.after(150, self._update_clock)

    # ── Window ────────────────────────────────────────────────────────────────
    def _setup_window(self):
        self._root.title(
            f"ITS  v{self.VERSION}  |  XAUUSD  |  "
            f"{self._session.get('account','DEMO')}")
        self._root.configure(bg=BG)
        self._root.state("zoomed")
        self._root.protocol("WM_DELETE_WINDOW", self._on_shutdown)

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self._root, bg=HEADER_BG, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Bottom accent line
        tk.Frame(hdr, bg=ACCENT, height=2).place(
            relx=0, rely=1.0, anchor="sw", relwidth=1.0)

        # Logo
        logo_c = tk.Canvas(hdr, bg=HEADER_BG, width=44, height=44,
                            highlightthickness=0)
        logo_c.pack(side="left", padx=(12, 0))
        self._root.after_idle(
            lambda: draw_its_logo(logo_c, 22, 22, size=18))

        # Brand
        lf = tk.Frame(hdr, bg=HEADER_BG)
        lf.pack(side="left", padx=(8, 0))
        tk.Label(lf, text="INSTITUTIONAL TRADING SYSTEM",
                 bg=HEADER_BG, fg=WHITE,
                 font=(UI_FONT, 10, "bold")).pack(anchor="w")
        tk.Label(lf, text=f"ITS ENGINE  v{self.VERSION}",
                 bg=HEADER_BG, fg=SUBTEXT,
                 font=(UI_FONT, 7)).pack(anchor="w")

        # Divider
        tk.Frame(hdr, bg=BORDER3, width=1).pack(
            side="left", fill="y", padx=14, pady=8)

        # Symbol + price
        cf = tk.Frame(hdr, bg=HEADER_BG)
        cf.pack(side="left")
        self._sym_var   = tk.StringVar(value="XAUUSD")
        self._price_var = tk.StringVar(value="----.--")
        tk.Label(cf, textvariable=self._sym_var,
                 bg=HEADER_BG, fg=SUBTEXT,
                 font=(UI_FONT, 8)).pack(anchor="w")
        tk.Label(cf, textvariable=self._price_var,
                 bg=HEADER_BG, fg=WHITE,
                 font=(MONO_FONT, 22, "bold")).pack(anchor="w")

        # Right cluster
        rf = tk.Frame(hdr, bg=HEADER_BG)
        rf.pack(side="right", padx=16)

        self._clock_var = tk.StringVar(value="--:--:-- UTC")
        tk.Label(rf, textvariable=self._clock_var,
                 bg=HEADER_BG, fg=SUBTEXT,
                 font=(MONO_FONT, 10)).pack(side="right", padx=(16, 0))

        self._status_var = tk.StringVar(value=" CONNECTING ")
        self._status_lbl = tk.Label(rf, textvariable=self._status_var,
                                    bg=AMBER_BG, fg=AMBER,
                                    font=(UI_FONT, 8, "bold"),
                                    padx=10, pady=2)
        self._status_lbl.pack(side="right", padx=10)

        self._ms_dot = tk.Label(rf, text="●", bg=HEADER_BG, fg=SUBTEXT,
                                font=(UI_FONT, 13))
        self._ms_dot.pack(side="right", padx=(0, 2))
        self._ms_lbl = tk.Label(rf, text="ENGINE", bg=HEADER_BG, fg=SUBTEXT,
                                font=(UI_FONT, 7, "bold"))
        self._ms_lbl.pack(side="right", padx=(0, 8))

    # ── Engine bar ────────────────────────────────────────────────────────────
    def _build_engine_bar(self):
        bar = tk.Frame(self._root, bg=PANEL2, height=34)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        def pill(parent, text, bg_c, fg_c, cmd, hover_c):
            b = tk.Button(parent, text=text, bg=bg_c, fg=fg_c,
                          font=(UI_FONT, 8, "bold"),
                          relief="flat", cursor="hand2",
                          command=cmd, padx=14, pady=0, bd=0,
                          activebackground=hover_c,
                          activeforeground=WHITE)
            b.pack(side="left", padx=(6, 2), pady=4)
            b.bind("<Enter>", lambda e: b.config(bg=hover_c))
            b.bind("<Leave>", lambda e: b.config(bg=bg_c))

        pill(bar, "  START ENGINE", GREEN2, WHITE, self._engine_start, GREEN)
        pill(bar, "  STOP ENGINE",  RED2,  WHITE, self._engine_stop,  RED)

        tk.Frame(bar, bg=BORDER3, width=1).pack(
            side="left", fill="y", padx=10, pady=6)

        self._uptime_var      = tk.StringVar(value="Uptime: 00:00:00")
        self._signals_var     = tk.StringVar(value="Signals: 0")
        self._trades_sent_var = tk.StringVar(value="Trades: 0")
        self._last_sig_var    = tk.StringVar(value="Last Signal: --")

        for v, col in [(self._uptime_var,      SUBTEXT),
                       (self._signals_var,     ACCENT),
                       (self._trades_sent_var, GREEN),
                       (self._last_sig_var,    SUBTEXT)]:
            tk.Label(bar, textvariable=v, bg=PANEL2, fg=col,
                     font=(MONO_FONT, 8)).pack(side="left", padx=14)

    # ── Grid ──────────────────────────────────────────────────────────────────
    def _build_grid(self):
        self._grid = tk.Frame(self._root, bg=BG)
        self._grid.pack(fill="both", expand=True, padx=3, pady=3)

        # Row weights: top panels slightly larger
        self._grid.rowconfigure(0, weight=32)
        self._grid.rowconfigure(1, weight=22)
        self._grid.rowconfigure(2, weight=22)

        # Col weights: col0 narrower (status panels), cols 1-3 wider
        self._grid.columnconfigure(0, weight=18)
        self._grid.columnconfigure(1, weight=27)
        self._grid.columnconfigure(2, weight=27)
        self._grid.columnconfigure(3, weight=28)

    # ── Panels ────────────────────────────────────────────────────────────────
    def _build_panels(self):
        G = self._grid

        # ══════════════════════════════════════════════════════════════════════
        # ROW 0 — Bias | Signal | Last Trade | 7-Layer
        # ══════════════════════════════════════════════════════════════════════

        # P1: Market Bias
        p1 = GridPanel(G, "Market Bias", GREEN, icon="◆", row=0, col=0)

        bias_wrap = tk.Frame(p1.body, bg=PANEL)
        bias_wrap.pack(fill="x", padx=14, pady=(16, 0))
        self._bias_chip_bg = tk.Frame(bias_wrap, bg=GREEN_BG, padx=0, pady=10)
        self._bias_chip_bg.pack(fill="x")
        self._bias_lbl = tk.Label(self._bias_chip_bg, text="--",
                                  bg=GREEN_BG, fg=GREEN,
                                  font=(UI_FONT, 24, "bold"))
        self._bias_lbl.pack()

        kz_row = tk.Frame(p1.body, bg=PANEL)
        kz_row.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(kz_row, text="SESSION", bg=PANEL, fg=SUBTEXT,
                 font=(UI_FONT, 7, "bold")).pack(side="left")
        self._kz_lbl = tk.Label(kz_row, text="--",
                                bg=PANEL, fg=ACCENT,
                                font=(UI_FONT, 9, "bold"))
        self._kz_lbl.pack(side="right")

        self._sess_lbl = tk.Label(p1.body, text="--",
                                  bg=PANEL, fg=DIMTEXT,
                                  font=(UI_FONT, 8))
        self._sess_lbl.pack(padx=14)

        hsep(p1.body, padx=10, pady=8)

        score_row = tk.Frame(p1.body, bg=PANEL)
        score_row.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(score_row, text="CONFLUENCE", bg=PANEL, fg=SUBTEXT,
                 font=(UI_FONT, 7, "bold")).pack(side="left")
        self._conf_lbl = tk.Label(score_row, text="-- / 7",
                                  bg=PANEL, fg=AMBER,
                                  font=(MONO_FONT, 12, "bold"))
        self._conf_lbl.pack(side="right")

        # P2: Active Signal
        p2 = GridPanel(G, "Active Signal", GREEN, icon="▲", row=0, col=1)

        sig_outer = tk.Frame(p2.body, bg=PANEL)
        sig_outer.pack(fill="x", padx=12, pady=(14, 10))
        self._sig_chip = tk.Label(sig_outer, text="WAITING",
                                  bg=PANEL3, fg=SUBTEXT,
                                  font=(MONO_FONT, 18, "bold"),
                                  pady=10, anchor="center")
        self._sig_chip.pack(fill="x")

        self._sig_vars = {}
        section_label(p2.body, "Order Details")
        for k, l, fg in [("entry", "Entry Price", TEXT),
                          ("sl",   "Stop Loss",   RED),
                          ("tp",   "Take Profit", GREEN),
                          ("lots", "Lot Size",    TEXT),
                          ("rr",   "R:R Ratio",   AMBER)]:
            v, _ = kv_row(p2.body, l, value_fg=fg)
            self._sig_vars[k] = v

        # P3: Last Trade → EA
        p3 = GridPanel(G, "Last Trade to EA", ACCENT, icon="↗", row=0, col=2)
        self._lt_vars = {}
        section_label(p3.body, "Execution Details")
        for k, l, fg in [("action", "Direction",   TEXT),
                          ("symbol", "Symbol",      TEXT),
                          ("price",  "Fill Price",  WHITE),
                          ("sl",     "Stop Loss",   RED),
                          ("tp",     "Take Profit", GREEN),
                          ("lots",   "Lot Size",    TEXT)]:
            v, _ = kv_row(p3.body, l, value_fg=fg)
            self._lt_vars[k] = v

        # P4: 7-Layer Confluence
        p4 = GridPanel(G, "7-Layer Confluence", ACCENT, icon="=", row=0, col=3)
        self._layer_rows = []

        tbl_hdr = tk.Frame(p4.body, bg=PANEL3)
        tbl_hdr.pack(fill="x")
        for col_text, col_w in [("LAYER", 14), ("STATUS", 9),
                                 ("SCORE", 7),  ("REASON", 0)]:
            kw = dict(bg=PANEL3, fg=DIMTEXT,
                      font=(UI_FONT, 7, "bold"), anchor="w", pady=6)
            if col_w:
                kw["width"] = col_w
            tk.Label(tbl_hdr, text=col_text, **kw).pack(
                side="left",
                padx=(10 if col_text == "LAYER" else 2, 0))
        tk.Frame(p4.body, bg=BORDER2, height=1).pack(fill="x")

        for i, name in enumerate(LAYER_NAMES):
            row_bg = PANEL if i % 2 == 0 else PANEL2
            rf = tk.Frame(p4.body, bg=row_bg)
            rf.pack(fill="x")
            tk.Label(rf, text=LAYER_SHORT.get(name, name),
                     bg=row_bg, fg=TEXT,
                     font=(UI_FONT, 9), width=14, anchor="w").pack(
                side="left", padx=(10, 0), pady=5)
            sv  = tk.StringVar(value="--")
            scv = tk.StringVar(value="0.0")
            rv  = tk.StringVar(value="--")
            slbl = tk.Label(rf, textvariable=sv,
                            bg=row_bg, fg=SUBTEXT,
                            font=(MONO_FONT, 8, "bold"), width=9,
                            anchor="center")
            slbl.pack(side="left")
            tk.Label(rf, textvariable=scv, bg=row_bg, fg=SUBTEXT,
                     font=(MONO_FONT, 8), width=7,
                     anchor="center").pack(side="left")
            tk.Label(rf, textvariable=rv, bg=row_bg, fg=DIMTEXT,
                     font=(UI_FONT, 8), anchor="w").pack(side="left", padx=4)
            self._layer_rows.append((name, sv, slbl, scv, rv))

        self._all_pass_lbl = tk.Label(p4.body, text="",
                                      bg=PANEL, fg=GREEN,
                                      font=(UI_FONT, 8, "bold"))
        self._all_pass_lbl.pack(pady=6)

        # ══════════════════════════════════════════════════════════════════════
        # ROW 1 — Account | Open Positions (x3 cols)
        # ══════════════════════════════════════════════════════════════════════

        # P5: Account Overview
        p5 = GridPanel(G, "Account Overview", ACCENT, icon="$", row=1, col=0)

        facc = tk.Frame(p5.body, bg=PANEL)
        facc.pack(fill="both", expand=True, padx=10, pady=10)
        facc.columnconfigure(0, weight=1)
        facc.columnconfigure(1, weight=1)
        self._acc_vars = {}
        for k, l, c, r, cl in [
            ("equity",  "Equity",    WHITE,  0, 0),
            ("pnl",     "Float P&L", AMBER,  0, 1),
            ("balance", "Balance",   GREEN,  1, 0),
            ("trades",  "Trades",    ACCENT, 1, 1),
        ]:
            st = StatTile(facc, l, c, r, cl)
            self._acc_vars[k] = st.var

        hsep(p5.body, padx=10, pady=4)
        tier_row = tk.Frame(p5.body, bg=PANEL)
        tier_row.pack(fill="x", padx=14, pady=(2, 10))
        tk.Label(tier_row, text="SMC RISK TIER", bg=PANEL, fg=SUBTEXT,
                 font=(UI_FONT, 7, "bold")).pack(side="left")
        self._tier_var = tk.StringVar(value="--")
        tk.Label(tier_row, textvariable=self._tier_var,
                 bg=PANEL, fg=AMBER,
                 font=(MONO_FONT, 9, "bold")).pack(side="right")

        # P6: Open Positions (cols 1-3)
        p6 = GridPanel(G, "Open Positions", AMBER, icon="*",
                       row=1, col=1, colspan=3)

        tbl_f = tk.Frame(p6.body, bg=PANEL)
        tbl_f.pack(fill="both", expand=True)
        pos_cols = ["Symbol", "Type", "Lots", "Open", "Current", "SL", "TP", "PnL"]
        hdr_row = tk.Frame(tbl_f, bg=PANEL3)
        hdr_row.pack(fill="x")
        for col in pos_cols:
            tk.Label(hdr_row, text=col.upper(), bg=PANEL3, fg=SUBTEXT,
                     font=(UI_FONT, 7, "bold"), width=10,
                     anchor="w").pack(side="left", padx=(10, 0), pady=6)
        tk.Frame(tbl_f, bg=BORDER2, height=1).pack(fill="x")

        for r in range(1, 11):
            row_bg = PANEL if r % 2 == 0 else PANEL2
            rf2 = tk.Frame(tbl_f, bg=row_bg)
            rf2.pack(fill="x")
            rvs, rls = [], []
            for c in range(len(pos_cols)):
                v = tk.StringVar()
                l = tk.Label(rf2, textvariable=v, bg=row_bg, fg=TEXT,
                             font=(MONO_FONT, 9), width=10, anchor="w")
                l.pack(side="left", padx=(10, 0), pady=4)
                rvs.append(v)
                rls.append(l)
            self._pos_row_vars.append(rvs)
            self._pos_row_lbls.append(rls)

        # ══════════════════════════════════════════════════════════════════════
        # ROW 2 — Warnings | Pipeline Log | Trade History (x2 cols)
        # ══════════════════════════════════════════════════════════════════════

        # P7: Active Warnings
        p7 = GridPanel(G, "Active Warnings", AMBER, icon="!", row=2, col=0)
        for _ in range(6):
            row_f = tk.Frame(p7.body, bg=PANEL)
            row_f.pack(fill="x", padx=0, pady=1)
            tk.Frame(row_f, bg=AMBER, width=3).pack(side="left", fill="y")
            v = tk.StringVar()
            l = tk.Label(row_f, textvariable=v, bg=PANEL, fg=AMBER,
                         font=(UI_FONT, 8), wraplength=300,
                         justify="left", anchor="w")
            l.pack(side="left", fill="x", padx=10, pady=5)
            self._warn_vars.append(v)
            self._warn_lbls.append(l)

        # P8: Pipeline Log
        p8 = GridPanel(G, "Pipeline Log", CYAN, icon=">", row=2, col=1)
        log_wrap = tk.Frame(p8.body, bg=BG)
        log_wrap.pack(fill="both", expand=True, padx=6, pady=6)
        self._log_text = tk.Text(
            log_wrap, bg=BG, fg=CYAN,
            font=(MONO_FONT, 8), state="disabled",
            relief="flat", wrap="word",
            insertbackground=CYAN,
            selectbackground=PANEL3)
        log_sb = tk.Scrollbar(log_wrap, orient="vertical",
                              command=self._log_text.yview,
                              bg=PANEL2, troughcolor=BG,
                              activebackground=BORDER3, width=8)
        log_sb.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=log_sb.set)
        self._log_text.pack(fill="both", expand=True)

        # P9: Trade History (cols 2-3)
        p9 = GridPanel(G, "Trade History", PURPLE, icon="#",
                       row=2, col=2, colspan=2)
        hist_hdr = tk.Frame(p9.body, bg=PANEL3)
        hist_hdr.pack(fill="x")
        for h in ["Time", "Symbol", "Dir", "Price", "SL", "TP", "Lots", "Score"]:
            tk.Label(hist_hdr, text=h.upper(), bg=PANEL3, fg=SUBTEXT,
                     font=(UI_FONT, 7, "bold"), width=10,
                     anchor="w").pack(side="left", padx=(10, 0), pady=6)
        tk.Frame(p9.body, bg=BORDER2, height=1).pack(fill="x")
        self._th_inner = tk.Frame(p9.body, bg=PANEL)
        self._th_inner.pack(fill="both", expand=True)

        self._panels      = [p1, p2, p3, p4, p5, p6, p7, p8, p9]
        self._panel_names = ["Bias", "Signal", "Last", "Layer",
                             "Acc", "Pos", "Warn", "Log", "Hist"]

    # ── Toggle bar ────────────────────────────────────────────────────────────
    def _build_toggle_bar(self):
        bar = tk.Frame(self._root, bg=PANEL2, height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        tk.Label(bar, text="PANELS", bg=PANEL2, fg=DIMTEXT,
                 font=(UI_FONT, 7, "bold")).pack(side="left", padx=(12, 6))

        for i, n in enumerate(self._panel_names):
            b = tk.Button(bar, text=n,
                          bg=PANEL3, fg=SUBTEXT,
                          font=(UI_FONT, 7, "bold"),
                          relief="flat", cursor="hand2",
                          padx=10, pady=0, bd=0,
                          activebackground=ACCENT2,
                          activeforeground=WHITE,
                          command=lambda idx=i: self._panels[idx].toggle_visibility())
            b.pack(side="left", padx=2, pady=5)
            b.bind("<Enter>", lambda e, btn=b: btn.config(bg=ACCENT2, fg=WHITE))
            b.bind("<Leave>", lambda e, btn=b: btn.config(bg=PANEL3, fg=SUBTEXT))

    # ── Polling ───────────────────────────────────────────────────────────────
    def _poll_state(self):
        try:
            with open(STATE_FILE, "r") as f:
                s = json.load(f)
            self._online = True
            self._update_all_panels(s)
        except Exception:
            s = _demo_state(self._session)
            self._online = False
            self._update_all_panels(s)
            self._set_offline()
        self._root.after(self.POLL_MS, self._poll_state)

    def _set_offline(self):
        self._status_var.set(" DEMO ")
        self._status_lbl.config(bg=AMBER_BG, fg=AMBER)
        self._ms_dot.config(fg=AMBER)
        self._ms_lbl.config(text="DEMO", fg=AMBER)

    def _update_all_panels(self, s):
        self._update_header(s)
        self._update_bias(s)
        self._update_signal(s)
        self._update_last_trade(s)
        self._update_layers(s)
        self._update_account(s)
        self._update_positions(s)
        self._update_warnings(s)
        self._update_pipeline_logs(s)

    def _update_header(self, s):
        self._price_var.set(f"{s.get('current_price', 0):.2f}")
        self._sym_var.set(s.get("symbol", "XAUUSD").split("[")[0].strip())
        ms = s.get("master_switch", True)
        self._ms_dot.config(fg=GREEN if ms else RED)
        self._ms_lbl.config(text="ENGINE ON" if ms else "ENGINE OFF",
                            fg=GREEN if ms else RED)
        if self._online:
            self._status_var.set(" LIVE ")
            self._status_lbl.config(bg=GREEN_BG, fg=GREEN)

    def _update_bias(self, s):
        b = s.get("bias", "NEUTRAL").upper()
        if b == "BULLISH":
            fg, bg_c = GREEN, GREEN_BG
        elif b == "BEARISH":
            fg, bg_c = RED, RED_BG
        else:
            fg, bg_c = TEXT, PANEL3
        self._bias_lbl.config(text=b, fg=fg, bg=bg_c)
        self._bias_chip_bg.config(bg=bg_c)
        self._kz_lbl.config(text=s.get("killzone_name", "--"))
        self._sess_lbl.config(text=s.get("session_time", ""))
        score = s.get("confluence_score", 0)
        self._conf_lbl.config(
            text=f"{score:.1f} / 7",
            fg=GREEN if score >= 5 else AMBER if score >= 3 else RED)

    def _update_signal(self, s):
        a = s.get("signal_action", "NONE").upper()
        if a == "LONG":
            fg, bg_c = GREEN, GREEN_BG
        elif a == "SHORT":
            fg, bg_c = RED, RED_BG
        else:
            fg, bg_c = SUBTEXT, PANEL3
        self._sig_chip.config(text=a, fg=fg, bg=bg_c)
        self._sig_vars["entry"].set(f"{s.get('entry_price', 0):.2f}")
        self._sig_vars["sl"].set(f"{s.get('stop_loss', 0):.2f}")
        self._sig_vars["tp"].set(f"{s.get('take_profit', 0):.2f}")
        self._sig_vars["lots"].set(f"{s.get('lot_size', 0):.2f}")
        self._sig_vars["rr"].set(s.get("rr_ratio", "--"))

    def _update_last_trade(self, s):
        lt = s.get("last_trade", {})
        self._lt_vars["action"].set(lt.get("action", "--"))
        self._lt_vars["symbol"].set(lt.get("symbol", "--"))
        self._lt_vars["price"].set(f"{lt.get('price', 0):.2f}")
        self._lt_vars["sl"].set(f"{lt.get('sl', 0):.2f}")
        self._lt_vars["tp"].set(f"{lt.get('tp', 0):.2f}")
        self._lt_vars["lots"].set(f"{lt.get('lots', 0):.2f}")

    def _update_layers(self, s):
        ls   = s.get("layers", [])
        lmap = {l["name"]: l for l in ls}
        all_pass = True
        for (name, sv, slbl, scv, rv) in self._layer_rows:
            d = lmap.get(name, {})
            p = d.get("passed", False)
            if not p:
                all_pass = False
            sv.set("PASS" if p else "FAIL")
            slbl.config(fg=GREEN if p else RED)
            scv.set(f"{d.get('score', 0.0):.1f}")
            rv.set(d.get("reason", "")[:22])
        self._all_pass_lbl.config(
            text="ALL LAYERS PASSED" if all_pass else "")

    def _update_account(self, s):
        self._acc_vars["equity"].set(f"${s.get('account_equity',  0):,.2f}")
        self._acc_vars["balance"].set(f"${s.get('account_balance', 0):,.2f}")
        pnl = s.get("floating_pnl", 0)
        self._acc_vars["pnl"].set(f"${pnl:+,.2f}")
        self._acc_vars["trades"].set(str(s.get("open_trades_count", 0)))
        self._tier_var.set(s.get("risk_tier", "Standard"))

    def _update_positions(self, s):
        ps = s.get("open_positions", [])
        for r in range(len(self._pos_row_vars)):
            if r < len(ps):
                p = ps[r]
                vals = [p["symbol"], p["type"],
                        f"{p['lots']:.2f}", f"{p['open_price']:.2f}",
                        f"{p['current_price']:.2f}",
                        f"{p['sl']:.2f}", f"{p['tp']:.2f}",
                        f"{p['floating_pnl']:+.2f}"]
                for c, v in enumerate(self._pos_row_vars[r]):
                    v.set(vals[c])
                pnl_v = p["floating_pnl"]
                self._pos_row_lbls[r][7].config(fg=GREEN if pnl_v >= 0 else RED)
                self._pos_row_lbls[r][1].config(
                    fg=GREEN if p["type"] == "BUY" else RED)
            else:
                for v in self._pos_row_vars[r]:
                    v.set("")

    def _update_warnings(self, s):
        ws = s.get("active_warnings", [])
        for i, (v, l) in enumerate(zip(self._warn_vars, self._warn_lbls)):
            if i < len(ws):
                v.set(ws[i])
                l.config(fg=AMBER)
            else:
                v.set("")

    def _update_pipeline_logs(self, s):
        for entry in s.get("pipeline_logs", []):
            if entry not in self._seen_log_msgs:
                self._seen_log_msgs.add(entry)
                self._log_text.config(state="normal")
                ts = datetime.now().strftime("%H:%M:%S")
                self._log_text.insert("end", f"[{ts}] {entry}\n")
                self._log_text.see("end")
                self._log_text.config(state="disabled")

    def _update_clock(self):
        self._clock_var.set(
            datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))
        elapsed = int(time.time() - self._start_ts)
        h, r = divmod(elapsed, 3600)
        m, sec = divmod(r, 60)
        self._uptime_var.set(f"Uptime: {h:02d}:{m:02d}:{sec:02d}")
        self._root.after(1000, self._update_clock)

    def _engine_start(self):
        subprocess.Popen(["cmd.exe", "/c", "START_ALL.bat"],
                         cwd=BASE_DIR, creationflags=0x00000010)

    def _engine_stop(self):
        subprocess.Popen(["cmd.exe", "/c", "SYSTEM_OFF.bat"],
                         cwd=BASE_DIR, creationflags=0x00000010)

    def _on_shutdown(self):
        self._root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    DashboardApp(root, {"account": "LIVE", "demo": True})
    root.mainloop()
