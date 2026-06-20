# Device Pair Request ORM Boundary Design

## Context

`server/app/db_models.py` still owns all ORM class bodies. The safest next
step is to move one standalone model class first instead of extracting a
relationship graph.

## Decision

Move `DevicePairRequest` into `app.db.models.device_operations` and re-export it
from `app.db_models`. Leave `Device`, `Account`, and `Task` in `app.db_models`
because their relationships need a separate graph extraction pass.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_operations_orm_boundary.py server/tests/test_device_operations_pairing.py server/tests/test_devices_api.py -q
```
