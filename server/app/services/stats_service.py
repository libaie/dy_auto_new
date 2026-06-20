"""Compatibility facade for reporting stats service."""

import sys

from app.domains.reporting import stats_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
