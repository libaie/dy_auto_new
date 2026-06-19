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
| `app.services.series_planning_service` | `app.domains.ai_video_series.series_planning_service` | PR5 | Production code and tests import the domain service path directly, except explicit compatibility tests. |
| `app.services.episode_asset_scope_service` | `app.domains.ai_video_series.episode_asset_scope_service` | PR5 | Production code and tests import the domain service path directly, except explicit compatibility tests. |
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

## Compatibility Cleanup Gates

Do not remove `app.routers.series` until all of these are true:

- `rg "app\.routers\.series|from app\.routers import series" server/app server/tests` returns only this README and compatibility tests.
- `server/tests/test_ai_video_series_router_facade.py` has been replaced with tests for the new public import path.
- `app.main` imports worker functions from `app.domains.ai_video_series`.
- Release notes mention the import-path migration.

Do not remove `app.services.series_planning_service` until all of these are true:

- `rg "app\.services\.series_planning_service|from app\.services import series_planning_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_ai_video_series_planning_service_facade.py` has been replaced with tests for direct domain imports.
- Production orchestration services import `app.domains.ai_video_series.series_planning_service` directly.

Do not remove `app.services.episode_asset_scope_service` until all of these are true:

- `rg "app\.services\.episode_asset_scope_service" server/app server/tests` returns only compatibility tests and migration docs.
- `test_ai_video_series_episode_asset_scope_service_facade.py` has been replaced with tests for direct domain imports.
- Series planning code imports `app.domains.ai_video_series.episode_asset_scope_service` directly.

Do not remove `app.db_models` re-exports until all of these are true:

- For every public name exported by `app.db.models.ai_video_series.__all__` (`Base`, `series_characters`, `series_scenes`, `AITextArtifact`, `AITextArtifactConsumer`, `Episode`, `EpisodeScript`, `ProductionAuditEvent`, `ProductionEpisode`, `ProductionJob`, `ProductionPlan`, `ProductionPlanVersion`, `ProductionScene`, `ProductionSegment`, `ProductionShot`, `Series`, `VideoProductionRun`), `rg "from app\.db_models import" server/app server/tests` returns only compatibility tests.
- `server/tests/conftest.py` imports series/video-series ORM names through `app.db.models.ai_video_series` or an explicit shared test fixture module.
- Alembic environment imports all model modules through `app.db.models`.
