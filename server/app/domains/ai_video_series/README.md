# AI Video Series Domain

This domain will own the multi-episode AI video series business flow.

## Ownership Rules

- New `/api/series/*` business logic belongs in `app.domains.ai_video_series`.
- Domain rules and read models must not import FastAPI.
- Domain code may use existing services as adapters while migration is in progress.
- Use `ProductionAuditEvent` and `record_production_event` for production audit trails.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Series Episode ORM Boundary

- `app.db.models.ai_video_series` owns `Series`, `Episode`, `series_characters`, and `series_scenes`.

## Test Commands

Run the PR1 skeleton and migration boundary checks:

Immediately after the PR1 skeleton, auth parity, domain import, README, and app import smoke checks should pass. The router-thinning and domain-router migration gates stay red until PR2 moves and thins the router.

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_series_auth_parity.py server/tests/test_ai_video_series_domain_boundary.py -q
```

Run the existing series route contract tests:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_series_style_lock_pipeline.py server/tests/test_style_lock_background_worker.py server/tests/test_series_auto_generate_assets.py -q
```

Run the production contract tests touched by this domain:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py server/tests/test_video_production_readiness.py server/tests/test_video_production_observability_events.py -q
```

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
