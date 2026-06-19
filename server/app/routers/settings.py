"""Compatibility facade for system configuration routes.

The implementation now lives in app.domains.system_configuration.settings_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.system_configuration import settings_router as _settings_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _settings_router
globals().update(_settings_router.__dict__)
