"""Compatibility facade for task operation services."""

import sys

from app.domains.task_operations import task_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
