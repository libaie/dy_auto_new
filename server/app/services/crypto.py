"""Compatibility facade for system configuration crypto helpers."""

import sys

from app.domains.system_configuration import crypto as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
