"""Compatibility facade for prompt template management services."""

import sys

from app.domains.prompt_management import prompt_template_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
