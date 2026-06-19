"""Compatibility facade for selector management routes.

The implementation now lives in
app.domains.selector_management.selectors_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.selector_management import selectors_router as _selectors_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _selectors_router
globals().update(_selectors_router.__dict__)
