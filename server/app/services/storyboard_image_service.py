from __future__ import annotations

import sys

from app.domains.storyboard_images import storyboard_image_service as _impl

sys.modules[__name__] = _impl
