"""Compatibility facade for staged video production orchestration."""

from __future__ import annotations

import sys

from app.domains.video_production import video_production_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
