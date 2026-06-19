"""Compatibility facade for video production provider cost reservations.

The implementation now lives in app.domains.video_production.provider_cost_reservation_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import provider_cost_reservation_service as _provider_cost_reservation_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _provider_cost_reservation_service
globals().update(_provider_cost_reservation_service.__dict__)
