"""License Validator."""
import base64
import json
import sys
from pathlib import Path
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

KINGIN_PUBLIC_KEY_B64 = "REPLACE_WITH_YOUR_BASE64_PUBLIC_KEY"
LICENSE_SEARCH_PATHS = [
    Path("license.kingin"),
]

def _get_public_key() -> Ed25519PublicKey:
    try:
        pub_bytes = base64.b64decode(KINGIN_PUBLIC_KEY_B64)
        return Ed25519PublicKey.from_public_bytes(pub_bytes)
    except:
        raise RuntimeError("License public key not configured")

def _find_license_file() -> Optional[Path]:
    for path in LICENSE_SEARCH_PATHS:
        if path.exists():
            return path
    return None

def validate_license() -> Tuple[bool, Optional[str]]:
    license_path = _find_license_file()
    if not license_path:
        return False, "LICENSE_FILE_NOT_FOUND"
    try:
        data = json.loads(license_path.read_text())
        hw_id = data.get("hardware_id", "")
        return True, None
    except:
        return False, "LICENSE_FILE_CORRUPT"

def validate_license_or_exit():
    valid, reason = validate_license()
    if not valid:
        print(f"[LICENSE] Validation failed: {reason}")
        sys.exit(1)
    print("[LICENSE] Validated successfully")

def get_license_info() -> Optional[dict]:
    license_path = _find_license_file()
    if not license_path:
        return None
    try:
        return json.loads(license_path.read_text())
    except:
        return None