"""Compatibility facade for script pipeline routes.

The implementation now lives in app.domains.script_pipeline.pipeline_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.script_pipeline import pipeline_router as _pipeline_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _pipeline_router
globals().update(_pipeline_router.__dict__)
