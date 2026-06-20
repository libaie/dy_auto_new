# Visual Style Domain Import Design

Date: 2026-06-20

## Goal

Remove the domain-owned import of the legacy
`app.services.visual_style_inference_service` facade.

## Design

`app.domains.ai_video_series.style_lock` should import visual style helpers
directly from
`app.domains.creative_library.visual_style_inference_service`.

Keep `app.services.visual_style_inference_service` as a compatibility facade
for service modules whose owning domains have not moved yet.

## Verification

Add one boundary test that proves `style_lock.py` uses the direct domain import
and the legacy facade still resolves to the same module object as the creative
library implementation.
