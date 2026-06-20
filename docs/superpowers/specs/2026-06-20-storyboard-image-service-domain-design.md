# Storyboard Image Service Domain Design

Date: 2026-06-20

## Goal

Move storyboard image task business logic out of `app.services` and into the
`storyboard_images` domain without changing API behavior.

## Design

- Move the implementation from `server/app/services/storyboard_image_service.py`
  to `server/app/domains/storyboard_images/storyboard_image_service.py`.
- Update `storyboard_images_router.py` to import the domain service directly.
- Keep `app.services.storyboard_image_service` as a module alias to the domain
  module so existing imports and monkeypatches keep working.
- Import already-migrated image helpers from `app.domains.image_generation`.
- Keep the remaining dependency on `app.services.image_creation_service`
  explicit in the domain-service import inventory until that service migrates.

## Non-Goals

- Do not migrate `image_creation_service.py` in this slice.
- Do not change route paths, request models, response shapes, or auth behavior.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_domain_service_import_inventory.py server/tests/test_service_implementation_inventory.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```
