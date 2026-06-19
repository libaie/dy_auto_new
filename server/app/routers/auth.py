"""Compatibility facade for identity access routes.

The implementation now lives in app.domains.identity_access.auth_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.identity_access import auth_router as _auth_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _auth_router
globals().update(_auth_router.__dict__)
