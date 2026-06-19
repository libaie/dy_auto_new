"""Compatibility facade for chain template and instance routes.

The implementation now lives in app.domains.account_operations.chains_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.account_operations import chains_router as _chains_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _chains_router
globals().update(_chains_router.__dict__)
