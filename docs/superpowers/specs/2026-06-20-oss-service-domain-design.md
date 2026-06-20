# OSS Service Domain Design

## Context

`server/app/services/oss_service.py` still owns OSS/CDN upload behavior in the
legacy services folder. The helper is small and currently has no production
callers, which makes it a low-risk next slice for the server business
modularization effort.

## Decision

Move the upload helper to `app.domains.system_operations.oss_service` because it
is operational infrastructure rather than episode, image, or collection business
logic. Keep `app.services.oss_service` as a thin compatibility facade that
aliases the domain module object.

## Scope

- Create `server/app/domains/system_operations/oss_service.py` with the current
  `upload_to_oss` behavior.
- Replace `server/app/services/oss_service.py` with a module alias facade.
- Document the new module and legacy facade in
  `server/app/domains/system_operations/README.md`.
- Add a focused boundary test that proves the domain path, legacy path, local
  provider behavior, and missing-file error behavior.

## Non-Goals

- Do not change MinIO or Aliyun OSS behavior.
- Do not add new providers or configuration.
- Do not update unrelated imports, because there are no active callers to
  migrate in this slice.

## Verification

Run the focused OSS facade test and a FastAPI import smoke check:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_operations_oss_service_facade.py -q
Push-Location server; ..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"; Pop-Location
```
