"""Compatibility facade for video production provider stage task helpers.

The implementation now lives in app.domains.video_production.provider_stage_task_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import provider_stage_task_service as _provider_stage_task_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _provider_stage_task_service
globals().update(_provider_stage_task_service.__dict__)
