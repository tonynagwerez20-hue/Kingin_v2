"""
launcher.py — ITS Desktop Shortcut Target
==========================================
This is the entry point launched by the Desktop shortcut (via pythonw.exe).
It shows an animated boot splash, then opens the secure login screen.

Shortcut target:
    pythonw.exe "C:\\...\\kingin-master\\launcher.py"
Working directory:
    C:\\...\\kingin-master\\

Requires only stdlib + tkinter (no pip packages needed at launch time).
"""

# ── MUST be first — sets taskbar icon correctly on Windows ───────────────────
import ctypes
import sys
import os

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "ITS.TradingSystem.1.0"
    )
except Exception:
    pass

# ── Path anchor ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import tkinter as tk
from tkinter import font as tkfont, messagebox
import threading
import time

# ── Theme ─────────────────────────────────────────────────────────────────────
BG      = "#000000"
PANEL   = "#0a0a0a"
ACCENT  = "#00c8f0"
GREEN   = "#00e87a"
AMBER   = "#ffaa00"
TEXT    = "#b8ccd8"
SUBTEXT = "#445566"
FONT    = "Consolas"

BOOT_LINES = [
    "Initializing SMC engine core...",
    "Loading filtration layers (7/7)...",
    "Connecting MT5 data provider...",
    "Starting ZMQBridge connection to HedgeEA...",
    "Loading trading_params_lite.json...",
    "Attaching UltraLowAccountRiskRule...",
    "Dashboard ready — launching login screen...",
]


class SplashScreen:
    """
    Full-screen animated boot splash.
    Destroys itself when boot completes, then calls on_complete().
    """

    def __init__(self, root: tk.Tk, on_complete):
        self._root       = root
        self._on_complete = on_complete

        root.title("Institutional Trading System")
        root.configure(bg=BG)
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)

        # ── Set window icon if available ──────────────────────────────────────
        ico = os.path.join(BASE_DIR, "its_icon.ico")
        if os.path.exists(ico):
            try:
                root.iconbitmap(ico)
            except Exception:
                pass

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_ui()
        self._line_index = 0

        # Kick off boot sequence after first frame renders
        root.after(200, self._next_line)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        wrap = tk.Frame(self._root, bg=BG)
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        # Logo
        tk.Label(wrap, text="ITS", bg=BG, fg=ACCENT,
                 font=tkfont.Font(family=FONT, size=72, weight="bold")).pack()
        tk.Label(wrap, text="INSTITUTIONAL TRADING SYSTEM", bg=BG, fg=SUBTEXT,
                 font=tkfont.Font(family=FONT, size=14)).pack(pady=(0, 4))
        tk.Label(wrap, text="v2.0  |  SMC Engine  |  MT5 + ZMQBridge",
                 bg=BG, fg=SUBTEXT,
                 font=tkfont.Font(family=FONT, size=10)).pack(pady=(0, 30))

        # Boot log canvas
        log_frame = tk.Frame(wrap, bg=PANEL, width=600,
                             highlightthickness=1, highlightbackground="#1a1a1a")
        log_frame.pack()
        log_frame.pack_propagate(False)
        log_frame.configure(height=len(BOOT_LINES) * 24 + 16)

        self._log_text = tk.Text(
            log_frame, bg=PANEL, fg=ACCENT,
            font=tkfont.Font(family=FONT, size=10),
            state="disabled", relief="flat", bd=0,
            width=72, height=len(BOOT_LINES) + 1,
            cursor="arrow"
        )
        self._log_text.pack(fill="both", expand=True, padx=10, pady=8)

        # Progress bar track
        bar_frame = tk.Frame(wrap, bg=PANEL, pady=12)
        bar_frame.pack(fill="x", pady=(10, 0))
        self._bar_track = tk.Canvas(
            bar_frame, bg="#111111", height=6,
            highlightthickness=0, width=600
        )
        self._bar_track.pack()
        self._bar_fill = self._bar_track.create_rectangle(
            0, 0, 0, 6, fill=ACCENT, outline=""
        )

        tk.Label(wrap, text="Loading, please wait...", bg=BG, fg=SUBTEXT,
                 font=tkfont.Font(family=FONT, size=9)).pack(pady=(8, 0))

    # ── Boot sequence ─────────────────────────────────────────────────────────

    def _next_line(self):
        if self._line_index >= len(BOOT_LINES):
            self._on_complete()
            return

        line = BOOT_LINES[self._line_index]
        self._line_index += 1

        # Append line to log widget
        self._log_text.config(state="normal")
        self._log_text.insert("end", f"> {line}\n")
        self._log_text.config(state="disabled")
        self._log_text.see("end")

        # Update progress bar
        progress = self._line_index / len(BOOT_LINES)
        self._bar_track.coords(
            self._bar_fill,
            0, 0, int(600 * progress), 6
        )

        self._root.after(320, self._next_line)


# ── Main entry ────────────────────────────────────────────────────────────────

def launch():
    root = tk.Tk()

    def on_boot_complete():
        """Called after ALL boot lines displayed — open login screen."""
        root.attributes("-fullscreen", False)
        root.withdraw()          # hide splash (don't destroy yet — login needs root alive)
        root.after(50, open_login)

    def open_login():
        try:
            from login import LoginScreen
            LoginScreen(root)
        except Exception as exc:
            messagebox.showerror(
                "ITS — Startup Error",
                f"Failed to load login screen:\n\n{exc}\n\n"
                "Ensure all files are present in the ITS directory."
            )
            root.destroy()
            sys.exit(1)

    splash = SplashScreen(root, on_boot_complete)
    root.mainloop()


if __name__ == "__main__":
    try:
        launch()
    except Exception as exc:
        # Last-resort error dialog so the app never dies silently
        try:
            import tkinter.messagebox as mb
            mb.showerror("ITS — Fatal Error", f"Unhandled exception:\n\n{exc}")
        except Exception:
            pass
        sys.exit(1)
