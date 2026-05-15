"""License module."""
from license.hardware_id import generate_hardware_id, get_hardware_id_safe
from license.validator import validate_license, validate_license_or_exit, get_license_info
__all__ = ["generate_hardware_id", "get_hardware_id_safe", "validate_license", "validate_license_or_exit", "get_license_info"]