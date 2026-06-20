"""Compatibility facade for selector management services."""

import sys

from app.domains.selector_management import selector_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
