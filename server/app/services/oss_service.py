"""Compatibility facade for system operations OSS upload helpers."""

import sys

from app.domains.system_operations import oss_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
