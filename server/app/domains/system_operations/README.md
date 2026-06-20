# System Operations Domain

This domain owns server operational health routes.

## Owned Routes

- `/api/system/*`

## Not Owned

- Root `/health` stays in `app.main`.
- Admin stats stay in the stats route until a separate reporting domain is
  approved.

## Current Modules

- `system_health_router.py` owns migration schema checks, provider capability
  checks, worker runtime checks, scene readiness checks, and
  `/api/system/health`.
- `oss_service.py` owns `upload_to_oss` OSS/CDN upload helper behavior for
  local, MinIO, and Aliyun OSS providers.

## Facade Register

| Facade | Target | Exit condition |
|---|---|---|
| `app.routers.system_health` | `app.domains.system_operations.system_health_router` | Direct app wiring and import inventory prove only approved compatibility references remain. |
| `app.services.oss_service` | `app.domains.system_operations.oss_service` | Import inventory proves no production or test imports use the legacy service path. |

## Boundaries

- Keep provider capability service bodies in `app.services.*`.
- Keep ORM models in `app.db_models`.
- Preserve helper names because existing tests monkeypatch them through the
  legacy router path.
- Preserve the `/api/system/health` response shape.

## Compatibility Cleanup Gates

Do not remove the legacy router facade until all of these are true:

- `app.main` imports the system health router from `app.domains.system_operations`.
- Route/auth snapshots pass against the domain endpoint module.
- Legacy and domain imports resolve to the same module object during the alias
  phase.
- Existing system health page contract tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.system_health`.
