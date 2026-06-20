# Agency Creative Patch Service Domain Design

Date: 2026-06-20

## Goal

Move creative patch mutation logic into the `agency_operations` domain and stop
committed domain modules from depending on a service file that is not part of
the committed tree.

## Design

- Move `server/app/services/agency_creative_patch_service.py` to
  `server/app/domains/agency_operations/agency_creative_patch_service.py`.
- Update `agency_persistence.py` and `agency_router.py` to import the domain
  implementation directly.
- Keep `app.services.agency_creative_patch_service` as a module alias to the
  domain module for existing tests and legacy imports.
- Import creative patch contracts from
  `app.domains.agency_operations.agency_creative_patch_contracts`.
- Keep `agency_debate_audit.py` out of the committed implementation inventory
  until that staged work is committed or migrated separately.

## Non-Goals

- Do not migrate unrelated agency services in this slice.
- Do not change creative patch API behavior, database writes, or event payloads.

## Verification

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_service_implementation_inventory.py server/tests/test_domain_service_import_inventory.py server/tests/test_agency_creative_patch_service.py server/tests/test_agency_creative_patch_api.py -q
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```
