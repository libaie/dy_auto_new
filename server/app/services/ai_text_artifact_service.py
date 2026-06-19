"""Compatibility facade for AI text artifact domain services.

The implementation now lives in app.domains.ai_text_artifacts.ai_text_artifact_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_text_artifacts import ai_text_artifact_service as _ai_text_artifact_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _ai_text_artifact_service
globals().update(_ai_text_artifact_service.__dict__)
