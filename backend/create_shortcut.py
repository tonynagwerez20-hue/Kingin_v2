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

    # Target the Tauri executable instead of pythonw.exe + launcher.py
    tauri_exe = os.path.join(BASE_DIR, "src-tauri", "target", "release", "institutional-trading-system.exe")
    if not os.path.exists(tauri_exe):
        print(f"[WARNING] Tauri executable not found at {tauri_exe}")
        print("          Please run SETUP_TAURI.bat to build it!")
        print("          Shortcut will point to it anyway.")

    icon_path = os.path.join(BASE_DIR, "its_icon.ico")
    user_desktop = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")
    public_desktop = os.path.join(os.environ.get("PUBLIC", os.path.join(os.environ.get("SYSTEMDRIVE", "C:"), "Users", "Public")), "Desktop")
    desktops = [user_desktop]
    if public_desktop not in desktops:
        desktops.append(public_desktop)

    old_shortcuts = []
    for desktop in desktops:
        old_shortcuts.extend([
            os.path.join(desktop, "kingin.lnk"),
            os.path.join(desktop, "Institutional Trading System.lnk"),
        ])

    for old_path in old_shortcuts:
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                print(f"[WARNING] Could not remove old shortcut: {old_path}")

    shell = win32com.client.Dispatch("WScript.Shell")
    for desktop in desktops:
        lnk_path = os.path.join(desktop, "Institutional Trading System.lnk")
        shortcut = shell.CreateShortCut(lnk_path)
        shortcut.TargetPath = tauri_exe
        shortcut.WorkingDirectory = BASE_DIR
        shortcut.IconLocation = icon_path if os.path.exists(icon_path) else tauri_exe
        shortcut.Description = "Institutional Trading System"
        try:
            shortcut.save()
            print(f"[OK] Shortcut created: {lnk_path}")
            print(f"     Targets: {tauri_exe}")
        except Exception as exc:
            print(f"[WARNING] Unable to save shortcut: {lnk_path}")
            print(f"          {exc}")


if __name__ == "__main__":
    create_shortcut()
