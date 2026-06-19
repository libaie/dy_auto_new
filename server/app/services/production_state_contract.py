"""Compatibility facade for video production state contract helpers.

The implementation now lives in app.domains.video_production.production_state_contract.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_state_contract as _production_state_contract

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_state_contract
globals().update(_production_state_contract.__dict__)
