"""Compatibility facade for DM sequence routes.

The implementation now lives in app.domains.content_collection.dm_sequences_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.content_collection import dm_sequences_router as _dm_sequences_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _dm_sequences_router
globals().update(_dm_sequences_router.__dict__)
