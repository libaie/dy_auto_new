# AI Video Series Domain

This domain will own the multi-episode AI video series business flow.

## PR1 allowed

- Create `server/app/domains/__init__.py`.
- Create `server/app/domains/ai_video_series/__init__.py`.
- Create this README.
- Add architecture, auth parity, and app import smoke tests.
- Document the facade register and migration checklist.

## PR1 not allowed

- Do not move route behavior in PR1.
- Do not split `server/app/db_models.py` in PR1.
- Do not change `/api/series/*` paths, methods, auth dependencies, or response shape.
- Do not change production run behavior.
- Do not change frontend UI.

## Ownership Rules

- New `/api/series/*` business logic belongs in `app.domains.ai_video_series`.
- `app.routers.series` is a compatibility entrypoint during migration.
- Domain rules and read models must not import FastAPI.
- Domain code may use existing services as adapters while migration is in progress.
- Use `ProductionAuditEvent` and `record_production_event` for production audit trails.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.series` | `app.domains.ai_video_series.router` | PR2 | All imports and monkeypatches use domain paths or explicit compatibility exports. |
| `app.db_models` series ORM names | `app.db.models.ai_video_series` | PR4 | All production code imports series/video-series ORM names through `app.db.models.ai_video_series`; tests still prove legacy imports. |

## Migration Checklist

1. Add skeleton and tests without behavior changes.
2. Move the existing series route module into the domain package with legacy module identity preserved.
3. Split schemas, read models, artifact helpers, story planning, style lock, and worker logic into focused modules.
4. Add the ORM import boundary while preserving one SQLAlchemy `Base`.
5. Add the production status read model with batched evidence loading.
6. Remove facades only after compatibility tests prove no old callers remain.

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
