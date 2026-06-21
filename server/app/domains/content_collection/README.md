# Content Collection Domain

This domain will own content templates, sensitive words, collected comment/user
read models, data exports, DM sequence templates, and collection/DM use cases.

## Ownership Rules

- `app.domains.content_collection` owns the target migration boundary for `/api/content/*`, `/api/data/*`, and `/api/dm-sequences/*`.
- `app.domains.content_collection.read_models` owns collected comment/user/conversation list and export payload shaping.
- `app.domains.content_collection.content_service` owns `ContentService` template CRUD, sensitive-word CRUD/matching, variable substitution, and content-generation helpers.
- `app.db.models.content_collection` owns the `ContentTemplate`,
  `SensitiveWord`, `RepliedComment`, `DMSequence`, `CollectedComment`,
  `CollectedUser`, and `Conversation` ORM class bodies.
- `app.domains.content_collection.mutations` owns content template, sensitive-word, and DM sequence mutation orchestration.
- `app.domains.content_collection.content_generation` owns content, keyword, regex, and clean-prompt generation calls.
- `app.domains.content_collection.industry_profile_service` owns `load_profile`, `list_industries`, and DM industry compliance profile JSON loading from `server/app/data/industry_profiles`.
- `app.domains.content_collection.collection_reports` owns collected comment/user ingestion, comment AI reply, user profile, and avatar use cases.
- `app.domains.content_collection.dm_claims` owns DM recipient claim, send report, and release use cases.
- `app.domains.content_collection.dm_sequence_visibility` owns `get_device_visible_dm_sequences` and DM sequence visibility rules for device sync and polling payload inclusion.
- `app.domains.content_collection.realtime_events` owns content collection websocket broadcast helpers.
- `app.domains.device_operations.content_bridge` remains the device-authenticated route boundary for `/api/device/*` content, collection, DM, profile, and avatar paths until this domain provides handoff use cases.
- `content_collection` must preserve `content_changed` and `data_changed` websocket payloads when logic moves.
- Domain non-router use-case modules must avoid FastAPI imports unless they are route assembly modules.

## Canonical Imports

The retired router, service, and ORM import packages have been removed. Runtime code, tests, scripts, and new docs must import domain modules directly and use `app.db.models` / `app.db.models.<domain>` for ORM models.

## Test Commands

Run the PR1/PR2 boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_auth_parity.py server/tests/test_content_collection_domain_boundary.py server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py -q
```


```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_api.py server/tests/test_content_service.py server/tests/test_collection_builder.py server/tests/test_data_export.py server/tests/test_dm_sequences_api.py server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_tasks_api.py -q
```

Run the read model extraction checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_read_models.py server/tests/test_data_export.py -q
```

Run the content mutation and realtime checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_mutations.py server/tests/test_content_collection_realtime_broadcasts.py server/tests/test_content_api.py server/tests/test_dm_sequences_api.py -q
```

Run the device bridge handoff checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_dm_sequences_api.py -q
```

## Legacy Import Guard

The cleanup gate is complete. Keep the retired import-path and AST inventory tests passing so removed paths stay unavailable.
