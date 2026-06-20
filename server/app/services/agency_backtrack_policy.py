"""Compatibility facade for agency backtrack policy."""

import sys

from app.domains.agency_operations import agency_backtrack_policy as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
