"""Compatibility facade for agency manifest helpers."""

import sys

from app.domains.agency_operations import agency_manifest as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
