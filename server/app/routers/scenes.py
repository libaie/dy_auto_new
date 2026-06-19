"""Compatibility facade for scene routes.

The implementation now lives in app.domains.creative_library.scenes_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.creative_library import scenes_router as _scenes_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _scenes_router
globals().update(_scenes_router.__dict__)
