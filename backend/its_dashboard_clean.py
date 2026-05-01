"""
dashboard.py  ITS Live Trading Dashboard
==========================================
Launched by login.py after successful MT5 auth (or DEMO MODE).
8 draggable, minimisable floating panels on a dark canvas.
Polls engine_state.json every 2 seconds  NO threads in UI.

Usage (internal  called by login.py):
    from dashboard import DashboardApp
    DashboardApp(root, session)
    root.mainloop()
"""

import json
import os
import sys
import time
import subprocess
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime, timezone

#  Path anchor 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "engine_state.json")

#  Palette 
BG      = "#000000"
PANEL   = "#0a0a0a"
BORDER  = "#1a1a1a"
ACCENT  = "#00c8f0"
GREEN   = "#00e87a"
RED     = "#ff2d4e"
AMBER   = "#ffaa00"
TEXT    = "#b8ccd8"
SUBTEXT = "#445566"
FONT    = "Consolas"

#  Layer display names (matches engine class names) 
LAYER_NAMES = [
    "KillzoneFilterLayer",
    "MechanicalStructureLayer",
    "LiquiditySweepLayer",
    "DisplacementLayer",
    "FVGDiscountLayer",
    "MicroMSSLayer",
    "NewsEventLayer",
]

LAYER_SHORT = {
    "KillzoneFilterLayer":     "Killzone",
    "MechanicalStructureLayer":"Structure",
    "LiquiditySweepLayer":     "LiqSweep",
    "DisplacementLayer":       "Displace",
    "FVGDiscountLayer":        "FVG",
    "MicroMSSLayer":           "MicroMSS",
    "NewsEventLayer":          "News",
}

#  Demo state used when engine_state.json is missing / stale 
def _demo_state(session: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp":        now,
        "symbol":           "XAUUSD [DEMO]",
        "bias":             "BULLISH",
        "current_price":    3125.50,
        "signal_action":    "LONG",
        "entry_price":      3125.50,
        "stop_loss":        3120.00,
        "take_profit":      3135.00,
        "lot_size":         0.01,
        "execution_type":   "MARKET",
        "confluence_score": 6.0,
        "killzone_name":    "London Open",
        "session_time":     "08:0011:00 UTC",
        "rr_ratio":         "1:1.91",
        "layers": [
            {"name": n, "passed": i < 6, "score": 1.0 if i < 6 else 0.0,
             "reason": "DEMO"} for i, n in enumerate(LAYER_NAMES)
        ],
        "last_trade": {
            "action": "LONG", "symbol": "XAUUSD", "price": 3120.00,
            "sl": 3115.00, "tp": 3130.00, "lots": 0.01,
            "bias": "BULLISH", "execution_type": "MARKET",
            "confluence_score": 5.75, "timestamp": now,
        },
        "account_equity":    session.get("equity",   88.50),
        "account_balance":   session.get("balance",  86.80),
        "floating_pnl":      1.70,
        "open_trades_count": 1,
        "open_positions": [{
            "symbol": "XAUUSD", "type": "BUY", "lots": 0.01,
            "open_price": 3120.00, "current_price": 3125.50,
            "sl": 3115.00, "tp": 3130.00, "floating_pnl": 0.55,
            "open_time": now,
        }],
        "active_warnings": ["DEMO MODE  engine_state.json not found"],
    }


#  Draggable Panel 

class FloatingPanel:
    """
    A moveable, minimisable dark panel placed on a Canvas.
    top_color controls the 2-px accent bar at the top.
    """

    def __init__(self, canvas: tk.Canvas, title: str,
                 x: int, y: int, width: int,
                 top_color: str = ACCENT):
        self._canvas     = canvas
        self._title      = title
        self._x          = x
        self._y          = y
        self._width      = width
        self._minimised  = False
        self._drag_x     = 0
        self._drag_y     = 0

        # Outer frame
        self.frame = tk.Frame(canvas, bg=PANEL,
                              highlightthickness=1, highlightbackground=BORDER)

        # Top accent bar
        tk.Frame(self.frame, bg=top_color, height=2).pack(fill="x")

        # Title bar (drag handle)
        self._title_bar = tk.Frame(self.frame, bg=PANEL)
        self._title_bar.pack(fill="x", padx=0, pady=0)

        tk.Label(self._title_bar, text=title.upper(),
                 bg=PANEL, fg=ACCENT,
                 font=tkfont.Font(family=FONT, size=9, weight="bold"),
                 anchor="w").pack(side="left", padx=6, pady=4)

        self._min_btn = tk.Button(
            self._title_bar, text="", bg=PANEL, fg=SUBTEXT,
            relief="flat", font=tkfont.Font(family=FONT, size=9),
            bd=0, cursor="hand2",
            command=self._toggle_minimise
        )
        self._min_btn.pack(side="right", padx=4)

        # Body frame  all panel content goes here
        self.body = tk.Frame(self.frame, bg=PANEL)
        self.body.pack(fill="both", expand=True)

        # Place on canvas
        self._window = canvas.create_window(x, y, window=self.frame, anchor="nw")

        # Drag bindings
        for w in (self._title_bar,):
            w.bind("<ButtonPress-1>",   self._start_drag)
            w.bind("<B1-Motion>",       self._do_drag)
        # Click anywhere on frame  bring to front
        self.frame.bind("<ButtonPress-1>", lambda e: self._to_front())
        self._title_bar.bind("<ButtonPress-1>", self._start_drag)

    #  Drag 

    def _start_drag(self, event):
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        self._to_front()

    def _do_drag(self, event):
        dx = event.x_root - self._drag_x
        dy = event.y_root - self._drag_y
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        self._x += dx
        self._y += dy
        self._canvas.coords(self._window, self._x, self._y)

    def _to_front(self):
        self._canvas.tag_raise(self._window)

    #  Minimise 

    def _toggle_minimise(self):
        self._minimised = not self._minimised
        if self._minimised:
            self.body.pack_forget()
            self._min_btn.config(text="+")
        else:
            self.body.pack(fill="both", expand=True)
            self._min_btn.config(text="")

    #  Show / Hide 

    def show(self):
        self._canvas.itemconfigure(self._window, state="normal")

    def hide(self):
        self._canvas.itemconfigure(self._window, state="hidden")

    def toggle_visibility(self) -> bool:
        """Returns True if now visible."""
        state = self._canvas.itemcget(self._window, "state")
        if state == "hidden":
            self.show(); return True
        else:
            self.hide(); return False


#  Dashboard Application 

class DashboardApp:
    """
    Main ITS trading dashboard.
    Receives: root (tk.Tk), session (dict from login.py)
    """

    VERSION     = "2.0"
    POLL_MS     = 2000      # engine_state.json poll interval
    CLOCK_MS    = 1000      # UTC clock update
    STALE_SECS  = 30        # treat JSON older than this as OFFLINE


    def __init__(self, root: tk.Tk, session: dict):
        self._root     = root
        self._session  = session
        self._state    = {}
        self._online   = False
        self._start_ts = time.time()
        self._pipeline_log: list[str] = []
        self._starting = False  # Track if engine is in boot phase
        self._warn_labels: list[tk.Label] = []


        # MT5 availability
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            self._mt5 = None

        self._setup_window()
        self._build_header()
        self._build_engine_bar()
        self._build_canvas()
        self._build_panels()
        self._build_toggle_bar()

        # Start loops
        self._root.after(100,            self._poll_state)
        self._root.after(100,            self._update_clock)

    #  Window 

    def _setup_window(self):
        acct = self._session.get("account", "DEMO")
        self._root.title(f"Institutional Trading System  XAUUSD  {acct}")
        self._root.configure(bg=BG)
        self._root.state("zoomed")

        ico = os.path.join(BASE_DIR, "its_icon.ico")
        if os.path.exists(ico):
            try:
                self._root.iconbitmap(ico)
            except Exception:
                pass

        self._root.protocol("WM_DELETE_WINDOW", self._on_shutdown)

    #  Header bar 

    def _build_header(self):
        hdr = tk.Frame(self._root, bg=PANEL,
                       highlightthickness=1, highlightbackground=BORDER)
        hdr.pack(fill="x")

        # Left: system name + account
        lf = tk.Frame(hdr, bg=PANEL)
        lf.pack(side="left", padx=10, pady=5)
        tk.Label(lf, text="ITS", bg=PANEL, fg=ACCENT,
                 font=tkfont.Font(family=FONT, size=13, weight="bold")).pack(side="left")
        tk.Label(lf, text=f"  Acct: {self._session.get('account','DEMO')}",
                 bg=PANEL, fg=SUBTEXT,
                 font=tkfont.Font(family=FONT, size=9)).pack(side="left")

        # Centre: symbol + price
        cf = tk.Frame(hdr, bg=PANEL)
        cf.pack(side="left", expand=True)
        self._sym_var   = tk.StringVar(value="XAUUSD")
        self._price_var = tk.StringVar(value="")
        tk.Label(cf, textvariable=self._sym_var,
                 bg=PANEL, fg=TEXT,
                 font=tkfont.Font(family=FONT, size=12, weight="bold")).pack(side="left")
        tk.Label(cf, text="  ", bg=PANEL).pack(side="left")
        self._price_lbl = tk.Label(cf, textvariable=self._price_var,
                                   bg=PANEL, fg=ACCENT,
                                   font=tkfont.Font(family=FONT, size=12, weight="bold"))
        self._price_lbl.pack(side="left")

        # Right: status + clock
        rf = tk.Frame(hdr, bg=PANEL)
        rf.pack(side="right", padx=10, pady=5)
        self._status_var = tk.StringVar(value="CONNECTING")
        self._status_lbl = tk.Label(rf, textvariable=self._status_var,
                                    bg=PANEL, fg=AMBER,
                                    font=tkfont.Font(family=FONT, size=10, weight="bold"))
        self._status_lbl.pack(side="left", padx=(0, 12))
        self._clock_var = tk.StringVar(value="--:--:-- UTC")
        tk.Label(rf, textvariable=self._clock_var,
                 bg=PANEL, fg=SUBTEXT,
                 font=tkfont.Font(family=FONT, size=9)).pack(side="left")

    #  Engine control bar 

    def _build_engine_bar(self):
        bar = tk.Frame(self._root, bg=PANEL,
                       highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill="x")

        def pill(parent, text, color, cmd):
            btn = tk.Button(parent, text=text, bg=color, fg="#000000",
                            font=tkfont.Font(family=FONT, size=9, weight="bold"),
                            relief="flat", cursor="hand2", command=cmd,
                            padx=10, pady=2)
            btn.pack(side="left", padx=4, pady=4)
            return btn

        pill(bar, " START",   GREEN, self._engine_start)
        pill(bar, " STOP",    RED,   self._engine_stop)
        pill(bar, " RESTART", AMBER, self._engine_restart)
        pill(bar, " SHUTDOWN",RED,   self._on_shutdown)

        # Stats
        self._uptime_var     = tk.StringVar(value="Uptime: 00:00:00")
        self._last_sig_var   = tk.StringVar(value="Last Signal: ")
        self._trades_var     = tk.StringVar(value="Sent: 0")

        for v in (self._uptime_var, self._last_sig_var, self._trades_var):
            tk.Label(bar, textvariable=v, bg=PANEL, fg=SUBTEXT,
                     font=tkfont.Font(family=FONT, size=9)).pack(side="left", padx=12)

    def _engine_start(self):
        self._append_log("Engine START requested via dashboard.")
        try:
            env = os.environ.copy()
            # Force the batch script to use the exact python.exe we are currently using
            py_exe = sys.executable.replace("pythonw.exe", "python.exe")
            env["ITS_PYTHON_EXE"] = py_exe

            subprocess.Popen(
                ["cmd.exe", "/c", "START_ALL.bat"],
                cwd=BASE_DIR,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                env=env
            )
            self._append_log("START_ALL.bat executed in background.")
            # Immediate feedback for user
            self._starting = True
            self._status_var.set("CONNECTING")
            self._status_lbl.config(fg=AMBER)
            self._append_log("Dashboard status: CONNECTING...")
        except Exception as e:
            self._append_log(f"Failed to start engine: {e}")


    def _engine_stop(self):
        self._append_log("Engine STOP requested via dashboard.")
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "SYSTEM_OFF.bat"],
                cwd=BASE_DIR,
                creationflags=0x08000000
            )
            self._starting = False  # Explicit reset
            self._set_offline()
            self._append_log("SYSTEM_OFF.bat executed in background.")

        except Exception as e:
            self._append_log(f"Failed to stop engine: {e}")

    def _engine_restart(self):
        self._append_log("Engine RESTART requested via dashboard.")
        self._engine_stop()
        self._root.after(1500, self._engine_start)

    #  Scrollable canvas 

    def _build_canvas(self):
        frame = tk.Frame(self._root, bg=BG)
        frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(frame, bg=BG, width=1400, height=1000,
                                 highlightthickness=0,
                                 scrollregion=(0, 0, 1400, 1000))

        sb_y = tk.Scrollbar(frame, orient="vertical",
                            command=self._canvas.yview,
                            bg=BORDER, troughcolor=BG)
        sb_x = tk.Scrollbar(frame, orient="horizontal",
                            command=self._canvas.xview,
                            bg=BORDER, troughcolor=BG)
        self._canvas.configure(yscrollcommand=sb_y.set,
                               xscrollcommand=sb_x.set)

        sb_y.pack(side="right",  fill="y")
        sb_x.pack(side="bottom", fill="x")
        self._canvas.pack(fill="both", expand=True)

        # Mouse wheel scroll
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1*(e.delta//120),"units"))

    #  Panels 

    def _build_panels(self):
        C = self._canvas
        f_h   = tkfont.Font(family=FONT, size=10, weight="bold")
        f_val = tkfont.Font(family=FONT, size=11, weight="bold")
        f_sm  = tkfont.Font(family=FONT, size=9)
        f_sub = tkfont.Font(family=FONT, size=8)

        #  Panel 1  Market Bias 
        p1 = FloatingPanel(C, "Market Bias", 20, 20, 230, top_color=GREEN)
        self._bias_lbl = tk.Label(p1.body, text="", bg=PANEL, fg=TEXT,
                                  font=tkfont.Font(family=FONT, size=22, weight="bold"))
        self._bias_lbl.pack(pady=(8, 2))
        self._kz_lbl   = tk.Label(p1.body, text="", bg=PANEL, fg=SUBTEXT, font=f_sm)
        self._kz_lbl.pack()
        self._sess_lbl = tk.Label(p1.body, text="", bg=PANEL, fg=SUBTEXT, font=f_sub)
        self._sess_lbl.pack()
        self._conf_lbl = tk.Label(p1.body, text="Score: /7", bg=PANEL, fg=ACCENT, font=f_sm)
        self._conf_lbl.pack(pady=(4, 6))

        #  Panel 2  Active Signal 
        p2 = FloatingPanel(C, "Active Signal", 270, 20, 240, top_color=GREEN)
        self._sig_chip = tk.Label(p2.body, text="WAITING", bg="#141414",
                                  fg=SUBTEXT,
                                  font=tkfont.Font(family=FONT, size=14, weight="bold"),
                                  padx=12, pady=4)
        self._sig_chip.pack(pady=(8, 4))
        self._sig_grid = tk.Frame(p2.body, bg=PANEL)
        self._sig_grid.pack(fill="x", padx=8, pady=(0, 8))
        self._sig_vars = {}
        for row, (key, label) in enumerate([
            ("entry", "Entry"), ("sl", "Stop Loss"), ("tp", "Take Profit"),
            ("lots", "Lot Size"), ("exec", "Exec Type"), ("rr", "R:R"),
        ]):
            tk.Label(self._sig_grid, text=label, bg=PANEL, fg=SUBTEXT,
                     font=f_sub, anchor="w").grid(row=row, column=0, sticky="w", padx=4)
            var = tk.StringVar(value="")
            self._sig_vars[key] = var
            fg = RED if key == "sl" else GREEN if key == "tp" else TEXT
            tk.Label(self._sig_grid, textvariable=var, bg=PANEL, fg=fg,
                     font=f_sm, anchor="e").grid(row=row, column=1, sticky="e", padx=4)
        self._sig_grid.columnconfigure(1, weight=1)

        #  Panel 3  Last Trade 
        p3 = FloatingPanel(C, "Last Trade  HedgeEA", 530, 20, 230, top_color=ACCENT)
        self._lt_grid = tk.Frame(p3.body, bg=PANEL)
        self._lt_grid.pack(fill="x", padx=8, pady=6)
        self._lt_vars = {}
        for row, (key, label) in enumerate([
            ("action","Action"),("symbol","Symbol"),("price","Price"),
            ("sl","SL"),("tp","TP"),("lots","Lots"),("bias","Bias"),("ts","Time"),
        ]):
            tk.Label(self._lt_grid, text=label, bg=PANEL, fg=SUBTEXT,
                     font=f_sub, anchor="w").grid(row=row, column=0, sticky="w", padx=4)
            var = tk.StringVar(value="")
            self._lt_vars[key] = var
            tk.Label(self._lt_grid, textvariable=var, bg=PANEL, fg=TEXT,
                     font=f_sm, anchor="e").grid(row=row, column=1, sticky="e", padx=4)
        self._lt_grid.columnconfigure(1, weight=1)

        #  Panel 4  7-Layer Confluence 
        p4 = FloatingPanel(C, "7-Layer Confluence", 780, 20, 320, top_color=ACCENT)
        self._layer_rows = []
        hdr_f = tk.Frame(p4.body, bg=PANEL)
        hdr_f.pack(fill="x", padx=6)
        for c, (txt, w) in enumerate([("Layer",14),("Status",6),("Score",5),("Reason",20)]):
            tk.Label(hdr_f, text=txt, bg=PANEL, fg=SUBTEXT, font=f_sub,
                     width=w, anchor="w").grid(row=0, column=c, padx=2)
        for i, name in enumerate(LAYER_NAMES):
            row_f = tk.Frame(p4.body, bg=PANEL)
            row_f.pack(fill="x", padx=6)
            n_lbl = tk.Label(row_f, text=LAYER_SHORT.get(name, name),
                             bg=PANEL, fg=TEXT, font=f_sub, width=14, anchor="w")
            n_lbl.grid(row=0, column=0, padx=2)
            s_var = tk.StringVar(value="")
            s_lbl = tk.Label(row_f, textvariable=s_var,
                             bg=PANEL, fg=SUBTEXT, font=f_sub, width=6, anchor="center")
            s_lbl.grid(row=0, column=1, padx=2)
            sc_var = tk.StringVar(value="")
            sc_lbl = tk.Label(row_f, textvariable=sc_var,
                              bg=PANEL, fg=SUBTEXT, font=f_sub, width=5, anchor="e")
            sc_lbl.grid(row=0, column=2, padx=2)
            r_var = tk.StringVar(value="")
            r_lbl = tk.Label(row_f, textvariable=r_var,
                             bg=PANEL, fg=SUBTEXT, font=f_sub, width=20, anchor="w")
            r_lbl.grid(row=0, column=3, padx=2)
            self._layer_rows.append((name, s_var, s_lbl, sc_var, r_var))

        self._all_pass_lbl = tk.Label(p4.body, text="", bg=PANEL, fg=GREEN,
                                       font=tkfont.Font(family=FONT, size=9, weight="bold"))
        self._all_pass_lbl.pack(pady=4)

        #  Panel 5  Account Overview 
        p5 = FloatingPanel(C, "Account Overview", 20, 300, 320, top_color=ACCENT)
        tile_frame = tk.Frame(p5.body, bg=PANEL)
        tile_frame.pack(fill="both", expand=True, padx=8, pady=6)
        self._acc_vars = {}
        tiles = [
            ("equity",   "Account Equity", ACCENT),
            ("pnl",      "Floating PnL",   AMBER),
            ("trades",   "Open Trades",    SUBTEXT),
            ("balance",  "Balance",        GREEN),
        ]
        for i, (key, label, color) in enumerate(tiles):
            tf = tk.Frame(tile_frame, bg=BORDER, padx=6, pady=6)
            tf.grid(row=i//2, column=i%2, padx=4, pady=4, sticky="nsew")
            tile_frame.columnconfigure(i%2, weight=1)
            tile_frame.rowconfigure(i//2, weight=1)
            tk.Label(tf, text=label, bg=BORDER, fg=SUBTEXT, font=f_sub).pack(anchor="w")
            var = tk.StringVar(value="")
            self._acc_vars[key] = var
            tk.Label(tf, textvariable=var, bg=BORDER, fg=color,
                     font=tkfont.Font(family=FONT, size=12, weight="bold")).pack(anchor="w")

        #  Panel 6  Open Trades 
        p6 = FloatingPanel(C, "Current Open Trades", 360, 300, 480, top_color=AMBER)
        cols = ["Symbol","Type","Lots","Open","Current","SL","TP","PnL","Time"]
        tbl_frame = tk.Frame(p6.body, bg=PANEL)
        tbl_frame.pack(fill="both", expand=True, padx=4, pady=4)
        for c, col in enumerate(cols):
            tk.Label(tbl_frame, text=col, bg=PANEL, fg=SUBTEXT,
                     font=f_sub, width=8, anchor="center").grid(row=0, column=c, padx=1)
        self._trades_frame = tbl_frame
        self._trades_col_count = len(cols)
        self._trade_row_widgets: list = []

        #  Panel 7  Active Warnings 
        p7 = FloatingPanel(C, "Active Warnings", 20, 500, 340, top_color=AMBER)
        self._warn_frame = tk.Frame(p7.body, bg=PANEL)
        self._warn_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self._warn_labels: list[tk.Label] = []

        #  Panel 8  Pipeline Log 
        p8 = FloatingPanel(C, "Pipeline Log", 380, 500, 600, top_color=ACCENT)
        log_frame = tk.Frame(p8.body, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=6, pady=6)
        scrollbar = tk.Scrollbar(log_frame, bg=BORDER, troughcolor=PANEL)
        scrollbar.pack(side="right", fill="y")
        self._log_text = tk.Text(
            log_frame, bg="#0a0a0a", fg=TEXT,
            font=tkfont.Font(family=FONT, size=8),
            wrap="word", state="disabled",
            yscrollcommand=scrollbar.set
        )
        self._log_text.pack(fill="both", expand=True)
        scrollbar.config(command=self._log_text.yview)

        # Store panels for toggle bar
        self._panels = [p1, p2, p3, p4, p5, p6, p7, p8]
        self._panel_names = ["Bias", "Signal", "Last Trade", "Layers", "Account", "Trades", "Warnings", "Pipeline"]


    def _build_toggle_bar(self):
        bar = tk.Frame(self._root, bg=PANEL,
                       highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill="x", side="bottom")
        self._toggle_btns = []
        for i, name in enumerate(self._panel_names):
            btn = tk.Button(
                bar, text=name,
                bg=ACCENT, fg="#000000",
                font=tkfont.Font(family=FONT, size=8, weight="bold"),
                relief="flat", cursor="hand2",
                padx=10, pady=4,
                command=lambda idx=i: self._toggle_panel(idx)
            )
            btn.pack(side="left", padx=3, pady=3)
            self._toggle_btns.append(btn)

    def _toggle_panel(self, idx: int):
        visible = self._panels[idx].toggle_visibility()
        self._toggle_btns[idx].config(
            bg=ACCENT if visible else BORDER,
            fg="#000000" if visible else SUBTEXT,
        )

    #  State polling (no threads  after() only) 

    def _poll_state(self):
        state = None
        # Retry loop to handle Windows file lock race conditions
        for attempt in range(3):
            try:
                if not os.path.exists(STATE_FILE):
                    break
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state: break
            except (json.JSONDecodeError, PermissionError) as e:
                if attempt < 2:
                    time.sleep(0.1)
                    continue
                self._append_log(f"File Read Error (Attempt {attempt+1}): {e}")
            except Exception as e:
                self._append_log(f"Polling Error: {e}")
                break

        if state:
            try:
                # Check staleness
                ts_str = state.get("timestamp", "")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if ts.tzinfo is None:
                            from datetime import timezone as _tz
                            ts = ts.replace(tzinfo=_tz.utc)
                        age = (datetime.now(timezone.utc) - ts).total_seconds()
                        if age > self.STALE_SECS:
                            self._set_offline()
                            self._root.after(self.POLL_MS, self._poll_state)
                            return
                    except Exception:
                        pass
                self._state  = state
                self._online = True
                self._starting = False  # Once we get a fresh timestamp, we are no longer "starting"
                self._update_all_panels(state)
            except Exception as e:
                self._append_log(f"State Update Error: {e}")
                self._set_offline()
        else:
            # No valid state found in this poll
            if self._starting:
                # Keep showing CONNECTING while waiting for first boot update
                self._status_var.set("CONNECTING")
                self._status_lbl.config(fg=AMBER)
            elif self._session.get("demo"):
                self._state  = _demo_state(self._session)
                self._online = True
                self._update_all_panels(self._state)
            else:
                self._set_offline()

        self._root.after(self.POLL_MS, self._poll_state)
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Check staleness
            ts_str = state.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        from datetime import timezone as _tz
                        ts = ts.replace(tzinfo=_tz.utc)
                    age = (datetime.now(timezone.utc) - ts).total_seconds()
                    if age > self.STALE_SECS:
                        self._set_offline()
                        self._root.after(self.POLL_MS, self._poll_state)
                        return
                except Exception:
                    pass
            self._state  = state
            self._online = True
            self._starting = False  # Once we get a fresh timestamp, we are no longer "starting"
            self._update_all_panels(state)

        except FileNotFoundError:
            # No state file yet  use demo data if session is DEMO
            if self._session.get("demo"):
                self._state  = _demo_state(self._session)
                self._online = True
                self._update_all_panels(self._state)
            else:
                self._set_offline()
        except Exception:
            self._set_offline()

        self._root.after(self.POLL_MS, self._poll_state)

    def _set_offline(self):
        self._online = False
        # Only show OFFLINE if we aren't currently waiting for a boot
        if not self._starting:
            self._status_var.set("OFFLINE")
            self._status_lbl.config(fg=RED)
            self._price_var.set("")
        else:
            self._status_var.set("CONNECTING")
            self._status_lbl.config(fg=AMBER)


    #  Panel update helpers 

    def _update_all_panels(self, s: dict):
        self._update_header(s)
        self._update_bias(s)
        self._update_signal(s)
        self._update_last_trade(s)
        self._update_layers(s)
        self._update_account(s)
        self._update_trades(s)
        self._update_warnings(s)
        self._update_pipeline(s)
        self._update_uptime()

    def _update_header(self, s: dict):
        sym   = s.get("symbol", "XAUUSD")
        price = s.get("current_price", 0.0)
        self._sym_var.set(sym)
        self._price_var.set(f"{price:.2f}")
        self._status_var.set("LIVE" if self._online else "OFFLINE")
        self._status_lbl.config(fg=GREEN if self._online else RED)

    def _update_bias(self, s: dict):
        bias = s.get("bias", "NEUTRAL").upper()
        col  = GREEN if bias == "BULLISH" else RED if bias == "BEARISH" else TEXT
        self._bias_lbl.config(text=bias, fg=col)
        self._kz_lbl.config(text=s.get("killzone_name", ""))
        self._sess_lbl.config(text=s.get("session_time", ""))
        self._conf_lbl.config(text=f"Score: {s.get('confluence_score',0):.1f}/7")

    def _update_signal(self, s: dict):
        action = s.get("signal_action", "NONE").upper()
        if action == "LONG":
            self._sig_chip.config(text="LONG ", bg="#001a0a", fg=GREEN)
        elif action == "SHORT":
            self._sig_chip.config(text="SHORT ", bg="#1a000a", fg=RED)
        else:
            self._sig_chip.config(text="WAITING", bg="#141414", fg=SUBTEXT)
        self._sig_vars["entry"].set(f"{s.get('entry_price',0):.2f}")
        self._sig_vars["sl"].set(f"{s.get('stop_loss',0):.2f}")
        self._sig_vars["tp"].set(f"{s.get('take_profit',0):.2f}")
        self._sig_vars["lots"].set(f"{s.get('lot_size',0):.2f}")
        self._sig_vars["exec"].set(s.get("execution_type",""))
        self._sig_vars["rr"].set(s.get("rr_ratio",""))

    def _update_last_trade(self, s: dict):
        lt = s.get("last_trade", {})
        self._lt_vars["action"].set(lt.get("action",""))
        self._lt_vars["symbol"].set(lt.get("symbol",""))
        self._lt_vars["price"].set(f"{lt.get('price',0):.2f}")
        self._lt_vars["sl"].set(f"{lt.get('sl',0):.2f}")
        self._lt_vars["tp"].set(f"{lt.get('tp',0):.2f}")
        self._lt_vars["lots"].set(f"{lt.get('lots',0):.2f}")
        self._lt_vars["bias"].set(lt.get("bias",""))
        ts = lt.get("timestamp","")
        self._lt_vars["ts"].set(ts[:19].replace("T"," ") if ts else "")

    def _update_layers(self, s: dict):
        layers   = s.get("layers", [])
        lmap     = {l.get("name",""):l for l in layers}
        all_pass = True
        for (name, s_var, s_lbl, sc_var, r_var) in self._layer_rows:
            data   = lmap.get(name, {})
            passed = data.get("passed", False)
            score  = data.get("score", 0.0)
            reason = data.get("reason","")[:22]
            if not passed:
                all_pass = False
            s_var.set("PASS" if passed else "FAIL")
            s_lbl.config(fg=GREEN if passed else RED)
            sc_var.set(f"{score:.2f}")
            r_var.set(reason)
        
        if all_pass and layers:
            self._all_pass_lbl.config(
                text=" ALL 7 LAYERS PASSED  TRADE ALLOWED",
                fg=GREEN
            )
        else:
            self._all_pass_lbl.config(text="")

    def _update_account(self, s: dict):
        eq   = s.get("account_equity",   0.0)
        bal  = s.get("account_balance",  0.0)
        pnl  = s.get("floating_pnl",     0.0)
        cnt  = s.get("open_trades_count", 0)
        self._acc_vars["equity"].set(f"${eq:,.2f}")
        self._acc_vars["balance"].set(f"${bal:,.2f}")
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        self._acc_vars["pnl"].set(pnl_str)
        self._acc_vars["trades"].set(str(cnt))

    def _update_trades(self, s: dict):
        # Clear old rows
        for w in self._trade_row_widgets:
            w.destroy()
        self._trade_row_widgets.clear()

        positions = s.get("open_positions", [])
        for r, pos in enumerate(positions[:10], start=1):
            ptype  = pos.get("type","").upper()
            fpnl   = pos.get("floating_pnl", 0.0)
            row_fg = GREEN if ptype == "BUY" else RED
            vals   = [
                pos.get("symbol",""),
                ptype,
                f"{pos.get('lots',0):.2f}",
                f"{pos.get('open_price',0):.2f}",
                f"{pos.get('current_price',0):.2f}",
                f"{pos.get('sl',0):.2f}",
                f"{pos.get('tp',0):.2f}",
                f"+{fpnl:.2f}" if fpnl >= 0 else f"{fpnl:.2f}",
                (pos.get("open_time","")[:16].replace("T"," ")),
            ]
            fg_pnl = GREEN if fpnl >= 0 else RED
            for c, val in enumerate(vals):
                col = fg_pnl if c == 7 else row_fg if c == 1 else TEXT
                lbl = tk.Label(self._trades_frame, text=val,
                               bg=PANEL, fg=col,
                               font=tkfont.Font(family=FONT, size=8),
                               width=8, anchor="center")
                lbl.grid(row=r, column=c, padx=1)
                self._trade_row_widgets.append(lbl)

    def _update_warnings(self, s: dict):
        for lbl in self._warn_labels:
            lbl.destroy()
        self._warn_labels.clear()
        warnings = s.get("active_warnings", [])
        if not warnings:
            lbl = tk.Label(self._warn_frame, text="No active warnings",
                           bg=PANEL, fg=SUBTEXT,
                           font=tkfont.Font(family=FONT, size=8))
            lbl.pack(anchor="w")
            self._warn_labels.append(lbl)
        else:
            for w in warnings:
                ts  = datetime.now().strftime("%H:%M:%S")
                lbl = tk.Label(self._warn_frame, text=f"[{ts}] {w}",
                               bg=PANEL, fg=AMBER,
                               font=tkfont.Font(family=FONT, size=8),
                               anchor="w", wraplength=300)
                lbl.pack(anchor="w", fill="x")
                self._warn_labels.append(lbl)

    def _update_pipeline(self, s: dict):
        pipeline_log = s.get("pipeline_log", [])
        if pipeline_log:
            self._log_text.config(state="normal")
            self._log_text.delete("1.0", "end")
            for line in pipeline_log[-200:]:  # Keep last 200 lines
                self._log_text.insert("end", line + "\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")

    def _append_log(self, msg: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self._pipeline_log.append(line)
        if len(self._pipeline_log) > 200:
            self._pipeline_log = self._pipeline_log[-100:]
        self._log_text.config(state="normal")
        self._log_text.insert("end", line)
        if len(self._pipeline_log) > 150:
            self._log_text.delete("1.0", "50.end+1c")
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    #  Clock 

    def _update_clock(self):
        now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        self._clock_var.set(now)
        self._root.after(self.CLOCK_MS, self._update_clock)

    def _update_uptime(self):
        elapsed = int(time.time() - self._start_ts)
        h, rem  = divmod(elapsed, 3600)
        m, sec  = divmod(rem, 60)
        self._uptime_var.set(f"Uptime: {h:02d}:{m:02d}:{sec:02d}")

    #  Shutdown 

    def _on_shutdown(self):
        try:
            if self._mt5:
                self._mt5.shutdown()
        except Exception:
            pass
        self._root.destroy()


#  Standalone launch (for testing without login screen) 
if __name__ == "__main__":
    root = tk.Tk()
    session = {"account": "TEST", "demo": True}
    DashboardApp(root, session)
    root.mainloop()
