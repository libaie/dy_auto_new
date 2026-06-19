"""Compatibility facade for the device-facing API router.

The implementation now lives in app.domains.device_operations.device_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.device_operations import device_router as _device_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _device_router
globals().update(_device_router.__dict__)
