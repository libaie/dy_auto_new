"""Compatibility facade for account group routes.

The implementation now lives in app.domains.account_operations.account_groups_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.account_operations import account_groups_router as _account_groups_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _account_groups_router
globals().update(_account_groups_router.__dict__)
