"""Compatibility facade for the admin device management router.

The implementation now lives in app.domains.device_operations.admin_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.device_operations import admin_router as _admin_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _admin_router
globals().update(_admin_router.__dict__)
