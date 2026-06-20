# One-Sentence Video Service Domain Design

## Context

`server/app/services/one_sentence_video_service.py` orchestrates the
one-sentence-to-video path: placeholder episode creation, style and storyboard
agency review, reference generation scheduling, text artifact writes, and
handoff into linked video production runs. This belongs in the video production
domain.

## Decision

Move the implementation to
`app.domains.video_production.one_sentence_video_service`. Keep
`app.services.one_sentence_video_service` as a compatibility facade while app
startup, video production router, dirty services, and tests still import the old
path.

Most dependencies should import from their domains. The retained service
dependencies in this slice are `app.services.video_agency_team` and
`app.services.video_production_service`, because those modules have not moved
yet.

## Scope

- Preserve `create_one_sentence_video`,
  `complete_one_sentence_reference_generation`, timeout constants, reference
  generation status handling, and run startup behavior.
- Preserve current staged behavior for agency reviews, placeholders, text
  artifacts, visual style inference, and mock-scale handoff.
- Remove `one_sentence_video_service.py` from the service implementation
  inventory.
- Add retained legacy imports to the domain service import inventory.
- Register the domain module and legacy facade in the video production README.

## Non-Goals

- Do not migrate `video_agency_team.py` or `video_production_service.py` in this
  slice.
- Do not change one-sentence API response shapes, timeout values, or review
  semantics.
- Do not remove the legacy service import path until downstream callers move.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py server/tests/test_one_sentence_video.py server/tests/test_one_sentence_video_run_types.py server/tests/test_video_production_real_short_mocked_e2e.py server/tests/test_mock_scale_scheduler_service.py -q
```
