from __future__ import annotations

import sys

from app.domains.video_production import production_queue_service as _impl

sys.modules[__name__] = _impl
