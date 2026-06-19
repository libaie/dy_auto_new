"""Compatibility facade for system health routes.

The implementation now lives in
app.domains.system_operations.system_health_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.system_operations import system_health_router as _system_health_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _system_health_router
globals().update(_system_health_router.__dict__)
