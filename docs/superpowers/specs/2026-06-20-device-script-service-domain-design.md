# Device Script Service Domain Design

Date: 2026-06-20

## Goal

Move device script package version, upload, and download helpers from
`app.services.script_service` into
`app.domains.device_operations.script_service` without changing `/api/device`
script asset behavior or legacy test monkeypatch paths.

## Approved Approach

Move the current implementation to
`server/app/domains/device_operations/script_service.py`.

Keep `app.services.script_service` as a `sys.modules` compatibility facade.
Update `device_operations.script_assets` to import the domain helper directly.
Keep script package storage under `SERVER_DIR / "scripts"`.

## Boundaries

- Preserve `ScriptService`, `script_service`, `get_version`,
  `upload_script`, and `download_script`.
- Preserve default version `0.0.0`, patch-version bumping, zip bytes storage,
  missing-package `None` return, and existing monkeypatch compatibility.
- Do not change `/api/device/script-version`, `/api/device/script-download`,
  `/api/device/script-upload`, auth dependencies, upload size/type checks,
  response shapes, or storage paths.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, direct
  script asset imports, README ownership, and basic upload/download behavior.
- Run script service and device script asset tests after migration.
