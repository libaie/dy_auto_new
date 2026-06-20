"""Compatibility facade for agency operation contract models."""

import sys

from app.domains.agency_operations import agency_contracts as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
