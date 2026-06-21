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

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Boundaries

- Preserve helper names because existing tests monkeypatch them through the
- Preserve the `/api/system/health` response shape.

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
