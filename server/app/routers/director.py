"""Compatibility facade for director planning routes.

The implementation now lives in app.domains.director_planning.director_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.director_planning import director_router as _director_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _director_router
globals().update(_director_router.__dict__)
