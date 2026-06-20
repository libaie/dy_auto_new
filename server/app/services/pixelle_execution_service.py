"""Compatibility facade for Pixelle execution payload mapping."""

import sys

from app.domains.pixelle_integration import pixelle_execution_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
