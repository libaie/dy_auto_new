"""Compatibility facade for prompt template routes.

The implementation now lives in
app.domains.prompt_management.prompt_templates_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.prompt_management import prompt_templates_router as _prompt_templates_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _prompt_templates_router
globals().update(_prompt_templates_router.__dict__)
