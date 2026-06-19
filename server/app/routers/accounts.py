"""Compatibility facade for account management routes.

The implementation now lives in app.domains.account_operations.accounts_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.account_operations import accounts_router as _accounts_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _accounts_router
globals().update(_accounts_router.__dict__)
