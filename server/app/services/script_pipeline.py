"""Compatibility facade for script pipeline domain services.

The implementation now lives in app.domains.script_pipeline.script_pipeline_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.script_pipeline import script_pipeline_service as _script_pipeline_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _script_pipeline_service
globals().update(_script_pipeline_service.__dict__)
