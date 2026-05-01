import os

def fix_dashboard():
    dashboard_path = 'its_dashboard.py'
    if not os.path.exists(dashboard_path):
        print("its_dashboard.py not found.")
        return

    with open(dashboard_path, 'rb') as f:
        content = f.read().decode('utf-8', 'ignore')

    # Locate the corrupted part again
    # Now it looks like: self._warn_frame = tk.Frame(p7.body, bg=PANEL)
    # but with bad indentation on the first line.
    
    start_point = content.find('        p7 = FloatingPanel(C, "Active Warnings", 20, 500, 340, top_color=AMBER)')
    if start_point == -1:
        print("Could not find p7 line.")
        return
    
    # Correct the entire block from p7 to the end of _poll_state
    
    end_marker = 'self._root.after(self.POLL_MS, self._poll_state)'
    end_point = content.find(end_marker, start_point)
    if end_point == -1:
        print("Could not find the end of _poll_state.")
        return
    
    # We want to keep everything until p7 line
    p7_line_end = content.find('\n', start_point) + 1
    
    # New block with correct 8-space indentation
    repaired_block = """        self._warn_frame = tk.Frame(p7.body, bg=PANEL)
        self._warn_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self._warn_labels = []

        #  Panel 8  Pipeline Log 
        p8 = FloatingPanel(C, "Pipeline Log", 360, 500, 480, top_color=ACCENT)
        self._log_text = tk.Text(p8.body, bg=PANEL, fg=TEXT, height=12,
                                 font=f_sm, state="disabled", borderwidth=0, padx=8, pady=8)
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)

        self._panels = [p1, p2, p3, p4, p5, p6, p7, p8]
        self._panel_names = ["BIAS", "SIGNAL", "TRADES", "IGOF", "ACCOUNT", "POSITIONS", "WARNINGS", "LOG"]

    def _poll_state(self):
        \"\"\"
        Robust state polling with Windows file-lock handling.
        \"\"\"
        state = None
        for attempt in range(3):
            try:
                if not os.path.exists(STATE_FILE):
                    break
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state: break
            except (json.JSONDecodeError, PermissionError):
                if attempt < 2:
                    import time
                    time.sleep(0.1)
                    continue
            except Exception as e:
                self._append_log(f"Polling Error: {e}")
                break

        if state:
            try:
                ts_str = state.get("timestamp", "")
                if ts_str:
                    try:
                        from datetime import datetime
                        ts = datetime.fromisoformat(ts_str)
                        if ts.tzinfo is None:
                            from datetime import timezone as _tz
                            ts = ts.replace(tzinfo=_tz.utc)
                        from datetime import timezone
                        age = (datetime.now(timezone.utc) - ts).total_seconds()
                        if age > self.STALE_SECS:
                            self._set_offline()
                            self._root.after(self.POLL_MS, self._poll_state)
                            return
                    except Exception:
                        pass
                self._state  = state
                self._online = True
                self._starting = False
                self._update_all_panels(state)
            except Exception as e:
                self._append_log(f"State Update Error: {e}")
                self._set_offline()
        else:
            if self._starting:
                self._status_var.set("CONNECTING")
                self._status_lbl.config(fg=AMBER)
            elif self._session.get("demo"):
                self._state  = _demo_state(self._session)
                self._online = True
                self._update_all_panels(self._state)
            else:
                self._set_offline()

        self._root.after(self.POLL_MS, self._poll_state)
"""

    actual_end_of_block = content.find('\n', end_point) + 1
    
    new_content = content[:p7_line_end] + repaired_block + content[actual_end_of_block:]

    with open(dashboard_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Repaired indentation and redundant poll_state.")

if __name__ == "__main__":
    fix_dashboard()
