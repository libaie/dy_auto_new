# Image Creation Storage Domain Design

Date: 2026-06-20

## Goal

Move image upload/output storage helpers from `app.services.image_creation_storage`
into `app.domains.image_generation.image_creation_storage` without changing
image upload behavior, generated output persistence, public URL construction,
or legacy monkeypatch paths.

## Approved Approach

Move the current implementation to
`server/app/domains/image_generation/image_creation_storage.py`.

Keep `app.services.image_creation_storage` as a `sys.modules` compatibility
facade. Update clean domain callers, `image_generation.image_creation_router`
and `creative_library.reference_asset_service`, to import the domain helper
directly. Leave `image_creation_service` on the legacy path in this slice
because that file has unrelated WIP.

## Boundaries

- Preserve `IMAGE_CREATION_ROOT`, `ALLOWED_CONTENT_TYPES`,
  `MAX_UPLOAD_BYTES`, `ensure_storage_dirs`, `save_upload`,
  `save_output_bytes`, and `configured_public_base_url`.
- Preserve `server/app/static/image-creation` as the storage root after moving
  the file deeper under `app.domains`.
- Preserve upload/output hash filenames, suffix normalization, content type
  validation, size validation, returned payload keys, and legacy monkeypatch
  compatibility.
- Do not change image route paths, auth dependencies, response shapes,
  Pixelle proxy behavior, image task behavior, or reference asset generation.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, storage
  root, domain imports, approved WIP compatibility import, README ownership,
  and basic save behavior.
- Run image storage boundary tests and existing image upload API tests after
  migration.
