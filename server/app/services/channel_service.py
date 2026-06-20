"""Compatibility facade for account operation channel services."""

import sys

from app.domains.account_operations import channel_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
