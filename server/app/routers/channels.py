"""Compatibility facade for channel management routes.

The implementation now lives in app.domains.account_operations.channels_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.account_operations import channels_router as _channels_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _channels_router
globals().update(_channels_router.__dict__)
