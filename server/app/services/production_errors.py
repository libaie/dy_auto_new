"""Compatibility facade for video production error helpers.

The implementation now lives in app.domains.video_production.production_errors.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_errors as _production_errors

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_errors
globals().update(_production_errors.__dict__)
