# Video Production Collection Service Domain Design

## Context

`server/app/services/production_collection_service.py` still owns collection
creation for approved episode videos. It is video production control-plane
behavior and has one production caller in the video production router.

## Decision

Move `create_collection_from_approved_episodes` to
`app.domains.video_production.production_collection_service`. Keep
`app.services.production_collection_service` as a compatibility facade and make
the video production router import the domain helper directly.

## Scope

- Preserve current behavior, including the existing empty-deliverable guard that
  raises `ValueError("没有可打包剧集：请先完成至少一集并生成视频。")`.
- Add the domain module under `server/app/domains/video_production/`.
- Replace the legacy service module with a module alias facade.
- Document the module and facade in the video production README.
- Add a focused boundary test for the move.

## Non-Goals

- Do not redesign collection creation.
- Do not change collection payloads, route paths, or database models.
- Do not edit existing collection behavior tests in this slice.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_collection_service_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_collection_builder.py -q
```
