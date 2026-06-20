"""Compatibility facade for content collection industry profiles."""

import sys

from app.domains.content_collection import industry_profile_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
