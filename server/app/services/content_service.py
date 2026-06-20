"""Compatibility facade for content collection services."""

import sys

from app.domains.content_collection import content_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
