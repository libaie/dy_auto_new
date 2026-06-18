"""Compatibility facade for the AI video series domain router.

Do not add business logic here. Importing `app.routers.series` must return the
same module object as `app.domains.ai_video_series.router` so legacy monkeypatch
paths keep changing the real domain module globals during migration.
"""

import sys

from app.domains.ai_video_series import router as _domain_router_module

sys.modules[__name__] = _domain_router_module
