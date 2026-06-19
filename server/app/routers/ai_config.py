"""Compatibility facade for model configuration routes.

The implementation now lives in app.domains.model_configuration.ai_models_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.model_configuration import ai_models_router as _ai_models_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _ai_models_router
globals().update(_ai_models_router.__dict__)
