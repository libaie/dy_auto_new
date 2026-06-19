"""Compatibility facade for video production provider capability helpers.

The implementation now lives in app.domains.video_production.provider_capability_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import provider_capability_service as _provider_capability_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _provider_capability_service
globals().update(_provider_capability_service.__dict__)
