# Creative Library Domain Implementation Plan

Date: 2026-06-20

## Goal

Create `app.domains.creative_library` and move character, scene, and reference
data route ownership behind compatibility-preserving domain modules.

## PR1: Boundary And Route Snapshot

- Add `server/tests/test_creative_library_auth_parity.py`.
- Add `server/tests/test_creative_library_domain_boundary.py`.
- Add `server/tests/test_creative_library_router_facade.py`.
- Snapshot path, method, function name, endpoint module, and auth dependencies
  for `/api/characters/*`, `/api/scenes/*`, `/api/reference-categories/*`, and
  `/api/reference-data/*`.

## PR2: Domain Skeleton And Facade Register

- Add `server/app/domains/creative_library/__init__.py`.
- Add `server/app/domains/creative_library/README.md`.
- Document owned routes, boundaries, non-goals, test commands, and cleanup gates.

## PR3: Router Move With Compatibility Facades

- Copy `server/app/routers/characters.py` to
  `server/app/domains/creative_library/characters_router.py`.
- Copy `server/app/routers/scenes.py` to
  `server/app/domains/creative_library/scenes_router.py`.
- Copy `server/app/routers/reference_data.py` to
  `server/app/domains/creative_library/reference_data_router.py`.
- Replace legacy router files with `sys.modules` compatibility facades.
- Keep `app.routers.characters`, `app.routers.scenes`, and
  `app.routers.reference_data` import-compatible with the new domain router
  modules.

## PR4: Direct App Wiring

- Wire `app.main` to `app.domains.creative_library` routers.
- Keep legacy facades for old imports and tests.
- Use an isolated index if `server/app/main.py` has unrelated WIP.

## Later Service Splits

- Move reference image generation orchestration only after a service-split plan
  proves existing monkeypatch and API tests keep passing.
- Move asset lifecycle and AI rewrite helpers only after route ownership is
  stable.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_auth_parity.py server/tests/test_creative_library_domain_boundary.py server/tests/test_creative_library_router_facade.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py server/tests/test_asset_archive_api.py server/tests/test_asset_ai_rewrite_service.py server/tests/test_reference_asset_service.py -q
```
