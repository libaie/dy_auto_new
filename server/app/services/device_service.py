"""Compatibility facade for device operation services."""

import sys

from app.domains.device_operations import device_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
