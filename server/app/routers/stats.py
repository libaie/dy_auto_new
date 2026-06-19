"""Compatibility facade for reporting routes.

The implementation now lives in app.domains.reporting.stats_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.reporting import stats_router as _stats_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _stats_router
globals().update(_stats_router.__dict__)
