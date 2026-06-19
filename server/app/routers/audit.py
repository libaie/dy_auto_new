"""Compatibility facade for quality audit routes.

The implementation now lives in app.domains.quality_audit.audit_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.quality_audit import audit_router as _audit_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _audit_router
globals().update(_audit_router.__dict__)
