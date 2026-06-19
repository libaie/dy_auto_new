"""Compatibility facade for character routes.

The implementation now lives in app.domains.creative_library.characters_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.creative_library import characters_router as _characters_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _characters_router
globals().update(_characters_router.__dict__)
