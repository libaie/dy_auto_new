"""Compatibility facade for creative library asset lifecycle services."""

import sys

from app.domains.creative_library import asset_lifecycle_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
