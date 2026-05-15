"""Hardware ID Module."""
import hashlib
import platform
import uuid
from typing import Optional

def _get_cpu_id() -> str:
    if platform.system() != "Windows":
        return "LINUX_CPU"
    return "WINDOWS_CPU"

def _get_mac_address() -> str:
    try:
        mac = uuid.getnode()
        return format(mac, '012x').upper()
    except:
        return "UNKNOWN_MAC"

def generate_hardware_id() -> str:
    components = [_get_cpu_id(), _get_mac_address()]
    fingerprint_str = "|".join(components)
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:32]

def get_hardware_id_safe() -> Optional[str]:
    try:
        return generate_hardware_id()
    except:
        return None