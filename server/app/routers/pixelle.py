"""Compatibility facade for Pixelle integration routes.

The implementation now lives in app.domains.pixelle_integration.pixelle_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.pixelle_integration import pixelle_router as _pixelle_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _pixelle_router
globals().update(_pixelle_router.__dict__)
