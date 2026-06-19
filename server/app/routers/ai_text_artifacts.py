"""Compatibility facade for AI text artifact routes.

The implementation now lives in app.domains.ai_text_artifacts.ai_text_artifacts_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_text_artifacts import ai_text_artifacts_router as _ai_text_artifacts_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _ai_text_artifacts_router
globals().update(_ai_text_artifacts_router.__dict__)
