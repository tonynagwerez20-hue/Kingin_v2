"""
login.py — ITS Secure MT5 Login Screen
========================================
Presents a centered, dark-themed Tkinter login form.
Reads / writes C:<repo>/credentials.json (no password stored).
On success: launches dashboard.py via DashboardApp.
On MT5 import failure: runs in DEMO MODE automatically.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import font as tkfont
import binascii

# ── Path anchor so sibling modules resolve correctly ─────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")

# ── Colour palette ────────────────────────────────────────────────────────────
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

# ── MT5 availability ──────────────────────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


class LoginScreen:
    """
    Secure MT5 credential form.
    Call LoginScreen(parent_root) — it creates a Toplevel.
    parent_root is destroyed before the dashboard opens.
    """

    def __init__(self, root: tk.Tk):
        self._root = root           # splash/boot root passed from launcher
        self._win  = tk.Toplevel(root)
        self._win.title("ITS — Secure Login")
        self._win.resizable(False, False)
        self._win.configure(bg=BG)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center window
        W, H = 600, 500
        self._win.geometry(f"{W}x{H}")
        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x  = (sw - W) // 2
        y  = (sh - H) // 2
        self._win.geometry(f"{W}x{H}+{x}+{y}")
        self._win.lift()
        self._win.focus_force()

        # Initialize MT5 in background thread
        self._mt5_initialized = False
        self._mt5_initializing = False
        if MT5_AVAILABLE:
            self._init_mt5_background()

        self._build_ui()
        self._load_credentials()

    def _init_mt5_background(self):
        """Initialize MT5 in background thread to avoid blocking UI."""
        if self._mt5_initializing or self._mt5_initialized:
            return

        self._mt5_initializing = True

        def init_worker():
            try:
                self._set_status("Initializing MT5 connection...", ACCENT)
                mt5.initialize()
                self._mt5_initialized = True
                self._mt5_initializing = False
                self._set_status("MT5 ready for authentication", GREEN)
            except Exception as exc:
                self._mt5_initializing = False
                self._set_status(f"MT5 initialization failed: {exc}", RED)

        # Start background initialization
        import threading
        thread = threading.Thread(target=init_worker, daemon=True)
        thread.start()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        f_title  = tkfont.Font(family=FONT, size=18, weight="bold")
        f_label  = tkfont.Font(family=FONT, size=10)
        f_entry  = tkfont.Font(family=FONT, size=11)
        f_btn    = tkfont.Font(family=FONT, size=12, weight="bold")
        f_status = tkfont.Font(family=FONT, size=9)

        # ── Top bar ──────────────────────────────────────────────────────────
        bar = tk.Frame(self._win, bg=ACCENT, height=3)
        bar.pack(fill="x")

        # ── Logo area ────────────────────────────────────────────────────────
        logo_frame = tk.Frame(self._win, bg=BG, pady=20)
        logo_frame.pack(fill="x")
        tk.Label(logo_frame, text="ITS", bg=BG, fg=ACCENT,
                 font=tkfont.Font(family=FONT, size=36, weight="bold")).pack()
        tk.Label(logo_frame, text="INSTITUTIONAL TRADING SYSTEM", bg=BG, fg=SUBTEXT,
                 font=f_label).pack()
        tk.Label(logo_frame, text="SECURE LOGIN", bg=BG, fg=ACCENT,
                 font=tkfont.Font(family=FONT, size=12, weight="bold")).pack(pady=(5, 0))

        # ── Form panel ───────────────────────────────────────────────────────
        panel = tk.Frame(self._win, bg=PANEL, bd=0,
                         highlightthickness=1, highlightbackground=BORDER)
        panel.pack(fill="both", expand=True, padx=40, pady=(10, 0))

        def add_field(parent, label_text, show=""):
            row = tk.Frame(parent, bg=PANEL, pady=6)
            row.pack(fill="x", padx=20)
            tk.Label(row, text=label_text, bg=PANEL, fg=SUBTEXT,
                     font=f_label, anchor="w").pack(fill="x")
            var = tk.StringVar()
            ent = tk.Entry(row, textvariable=var, show=show,
                           font=f_entry, bg=BORDER, fg=TEXT,
                           insertbackground=ACCENT, relief="flat",
                           highlightthickness=1, highlightcolor=ACCENT,
                           highlightbackground=BORDER)
            ent.pack(fill="x", ipady=6)
            return var, ent

        self._account_var, self._account_ent = add_field(panel, "MT5 Account (integer)")
        self._password_var, _               = add_field(panel, "Password", show="●")
        self._server_var,   _               = add_field(panel, "Server")

        # Remember checkbox
        chk_row = tk.Frame(panel, bg=PANEL, pady=4)
        chk_row.pack(fill="x", padx=20)
        self._save_var = tk.BooleanVar(value=False)
        tk.Checkbutton(chk_row, text="Save password (encrypted locally)",
                       variable=self._save_var,
                       bg=PANEL, fg=SUBTEXT, selectcolor=PANEL,
                       activebackground=PANEL, activeforeground=TEXT,
                       font=f_status).pack(anchor="w")

        # Connect button
        btn_row = tk.Frame(panel, bg=PANEL, pady=10)
        btn_row.pack(fill="x", padx=20)
        self._connect_btn = tk.Button(
            btn_row, text="CONNECT & LAUNCH",
            command=self._on_connect,
            bg=GREEN, fg="#000000", activebackground="#00ff8a",
            font=f_btn, relief="flat", cursor="hand2",
            pady=10
        )
        self._connect_btn.pack(fill="x")

        # Status label
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(
            self._win, textvariable=self._status_var,
            bg=BG, fg=AMBER, font=f_status, wraplength=520
        )
        self._status_lbl.pack(pady=(6, 10))

        # Demo mode notice
        if not MT5_AVAILABLE:
            self._status_var.set("⚠  DEMO MODE — MetaTrader5 not installed. Any credentials accepted.")
            self._status_lbl.config(fg=AMBER)
        elif MT5_AVAILABLE and not self._mt5_initialized and not self._mt5_initializing:
            self._status_var.set("Ready to connect. Click CONNECT & LAUNCH to begin authentication.")
            self._status_lbl.config(fg=GREEN)
        elif self._mt5_initializing:
            self._status_var.set("Initializing MT5 connection in background...")
            self._status_lbl.config(fg=ACCENT)

        # Bind Enter key
        self._win.bind("<Return>", lambda e: self._on_connect())

    # ── Credential persistence (DPAPI) ────────────────────────────────────────

    def _load_credentials(self):
        try:
            if os.path.exists(CREDS_FILE):
                with open(CREDS_FILE, "r") as f:
                    creds = json.load(f)
                self._account_var.set(str(creds.get("login", "")))
                self._server_var.set(creds.get("server", ""))
                self._save_var.set(creds.get("save_password", False))
                
                # Decrypt password via DPAPI if present
                enc_pw = creds.get("encrypted_password", "")
                if enc_pw and self._save_var.get():
                    try:
                        import win32crypt
                        raw_bytes = binascii.unhexlify(enc_pw)
                        _, dec_bytes = win32crypt.CryptUnprotectData(raw_bytes, None, None, None, 0)
                        self._password_var.set(dec_bytes.decode("utf-8"))
                    except ImportError:
                        pass # pywin32 not installed, can't decrypt
                    except Exception:
                        self._password_var.set("") # Decryption failed
                        
        except Exception:
            pass

    def _save_credentials(self, account: str, password: str, server: str):
        try:
            data = {"login": int(account), "server": server, "save_password": self._save_var.get()}
            
            # Encrypt password via DPAPI if user opted to save it
            if self._save_var.get() and password:
                try:
                    import win32crypt
                    enc_bytes = win32crypt.CryptProtectData(password.encode("utf-8"), "ITS_MT5_Creds", None, None, None, 0)
                    data["encrypted_password"] = binascii.hexlify(enc_bytes).decode("ascii")
                except ImportError:
                    pass # Silently fail to save password if win32crypt is missing
                except Exception:
                    pass
            else:
                data["encrypted_password"] = ""
                
            with open(CREDS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ── Connection logic ──────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = AMBER):
        self._status_var.set(msg)
        self._status_lbl.config(fg=color)
        self._win.update_idletasks()

    def _on_connect(self):
        account  = self._account_var.get().strip()
        password = self._password_var.get().strip()
        server   = self._server_var.get().strip()

        # Validate
        if not account:
            self._set_status("Account number is required.", RED); return
        try:
            account_int = int(account)
        except ValueError:
            self._set_status("Account must be a whole number (e.g. 298686191).", RED); return
        if not password:
            self._set_status("Password is required.", RED); return
        if not server:
            self._set_status("Server is required (e.g. Exness-MT5Trial9).", RED); return

        self._set_status("Connecting to MT5...", ACCENT)
        self._connect_btn.config(state="disabled")
        self._win.update_idletasks()

        session = {
            "account": account_int,
            "server":  server,
            "demo":    not MT5_AVAILABLE,
        }

        if not MT5_AVAILABLE:
            # DEMO MODE — accept any creds
            session["demo_reason"] = "MetaTrader5 not installed"
            self._set_status("[DEMO] Launching dashboard in simulation mode...", AMBER)
            self._win.after(600, lambda: self._launch_dashboard(session))
            return

        # Real MT5 login
        try:
            if not self._mt5_initialized:
                if self._mt5_initializing:
                    self._set_status("MT5 still initializing, please wait...", AMBER)
                    self._connect_btn.config(state="normal")
                    return
                else:
                    # Fallback: initialize now
                    self._set_status("Initializing MT5...", ACCENT)
                    mt5.initialize()
                    self._mt5_initialized = True

            self._set_status("Authenticating with MT5...", ACCENT)
            authorized = mt5.login(account_int, password=password, server=server)
            if authorized:
                info = mt5.account_info()
                session["balance"] = info.balance if info else 0.0
                session["equity"]  = info.equity  if info else 0.0
                self._save_credentials(account, password, server)
                self._write_runtime_creds(account_int, password, server)
                self._set_status("Authenticated. Launching dashboard...", GREEN)
                self._win.after(400, lambda: self._launch_dashboard(session))
            else:
                err = mt5.last_error()
                self._set_status(f"Authentication failed: {err[1] if err else 'Unknown error'}", RED)
                self._connect_btn.config(state="normal")
        except Exception as exc:
            self._set_status(f"Connection error: {exc}", RED)
            self._connect_btn.config(state="normal")

    def _write_runtime_creds(self, account: int, password: str, server: str):
        """
        Write runtime_credentials.json — gitignored, never committed.
        Password lives only in this local file + RAM during the session.
        The engine reads this file on startup to get the live password.
        """
        import stat
        rt_path = os.path.join(BASE_DIR, "runtime_credentials.json")
        try:
            with open(rt_path, "w") as f:
                json.dump({"login": account, "password": password,
                           "server": server}, f, indent=2)
            try:
                os.chmod(rt_path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass
        except Exception:
            pass


    def _launch_dashboard(self, session: dict):
        """Destroy login + root, then open standalone dashboard window."""
        try:
            from its_dashboard import DashboardApp
            self._win.destroy()
            self._root.destroy()
            root2 = tk.Tk()
            DashboardApp(root2, session)
            root2.mainloop()
        except Exception as exc:
            # Fallback: show error in a new window
            err_root = tk.Tk()
            err_root.title("ITS — Launch Error")
            err_root.configure(bg=BG)
            tk.Label(err_root, text=f"Dashboard failed to load:\n{exc}",
                     bg=BG, fg=RED, font=(FONT, 10), padx=20, pady=20).pack()
            err_root.mainloop()

    def _on_close(self):
        try:
            self._root.destroy()
        except Exception:
            pass
        sys.exit(0)
