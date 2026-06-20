"""Compatibility facade for device script package service."""

import sys

from app.domains.device_operations import script_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
