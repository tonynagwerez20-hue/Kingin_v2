"""Anti-Tampering Detection."""
import sys
import ctypes
from typing import Tuple

def check_debugger_present() -> bool:
    try:
        if sys.platform == "win32":
            return ctypes.windll.kernel32.IsDebuggerPresent()
    except:
        pass
    return False

def check_virtual_machine() -> bool:
    try:
        with open("/proc/self/cgroup", "rb") as f:
            content = f.read()
            for sig in [b"VirtualBox", b"VBox", b"VMware", b"QEMU"]:
                if sig in content:
                    return True
    except:
        pass
    return False

def anti_tamper_check() -> Tuple[bool, str]:
    if check_debugger_present():
        return False, "DEBUGGER_DETECTED"
    if check_virtual_machine():
        return False, "VIRTUAL_MACHINE_DETECTED"
    return True, ""

def anti_tamper_or_exit():
    valid, reason = anti_tamper_check()
    if not valid:
        print(f"[ANTI-TAMPER] Detection: {reason}")
        sys.exit(1)