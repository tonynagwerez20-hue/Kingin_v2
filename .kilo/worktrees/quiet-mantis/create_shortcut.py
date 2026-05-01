"""
create_shortcut.py — ITS Desktop Shortcut Creator
==================================================
Creates "Institutional Trading System.lnk" on the current user's Desktop.
Targets pythonw.exe (no console window) → launcher.py
Run once during install:  python create_shortcut.py
Requires: pip install pywin32
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_shortcut():
    try:
        import win32com.client
    except ImportError:
        print("ERROR: pywin32 not installed. Run: pip install pywin32")
        return

    # Locate pythonw.exe (same directory as current python.exe)
    python_dir  = os.path.dirname(sys.executable)
    pythonw_exe = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        # Try Scripts folder
        pythonw_exe = os.path.join(python_dir, "Scripts", "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        # Fallback to pyw.exe in Windows dir
        pythonw_exe = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "pyw.exe")

    launcher    = os.path.join(BASE_DIR, "launcher.py")
    icon_path   = os.path.join(BASE_DIR, "its_icon.ico")
    desktop     = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")
    lnk_path    = os.path.join(desktop, "Institutional Trading System.lnk")

    shell       = win32com.client.Dispatch("WScript.Shell")
    shortcut    = shell.CreateShortCut(lnk_path)
    shortcut.Targetpath      = pythonw_exe
    shortcut.Arguments       = f'"{launcher}"'
    shortcut.WorkingDirectory = BASE_DIR
    shortcut.IconLocation    = icon_path if os.path.exists(icon_path) else pythonw_exe
    shortcut.Description     = "Institutional Trading System"
    shortcut.save()

    print(f"[OK] Shortcut created: {lnk_path}")
    print(f"     Targets: {pythonw_exe} \"{launcher}\"")


if __name__ == "__main__":
    create_shortcut()
