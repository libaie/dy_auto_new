# Content Collection Domain

This domain will own content templates, sensitive words, collected comment/user
read models, data exports, DM sequence templates, and collection/DM use cases.

Device-authenticated `/api/device/*` routes stay in `device_operations` until
this domain provides stable use cases and compatibility tests for that handoff.

## PR2 Allowed

- Create `server/app/domains/content_collection/__init__.py`.
- Create this README.
- Expose `DOMAIN_NAME = "content_collection"`.
- Expose `PUBLIC_ROUTE_PREFIXES = ("/api/content", "/api/data", "/api/dm-sequences")`.
- Document route ownership, device bridge boundaries, facade register, and cleanup gates.

## PR2 Not Allowed

- Do not move route behavior in PR2.
- Do not create `content_router.py`, `data_router.py`, or `dm_sequences_router.py` in PR2.
- Do not change `/api/content/*`, `/api/data/*`, `/api/dm-sequences/*`, or `/api/device/*` paths, methods, auth dependencies, response shapes, or realtime payloads.
- Do not move ORM model ownership or persistence class bodies.
- Do not modify frontend code.

## PR3 Allowed

- Create `content_router.py` from the current `app.routers.content` behavior.
- Create `data_router.py` from the current `app.routers.data` behavior.
- Create `dm_sequences_router.py` from the current `app.routers.dm_sequences` behavior.
- Replace legacy router files with compatibility facades.
- Keep route paths, methods, auth dependencies, response shapes, export streams, and realtime payloads unchanged.

## PR3 Not Allowed

- Do not split handler internals yet.
- Do not move device bridge use cases yet.
- Do not change application wiring away from legacy imports yet.
- Do not move ORM model ownership or persistence class bodies.

## PR4a Allowed

- Move `/api/data/*` comment, user, conversation, and export payload shaping to `read_models.py`.
- Keep `data_router.py` as the FastAPI route and dependency boundary.
- Preserve pagination, filtering, sorting, XLSX streaming, and export headers.

## PR4a Not Allowed

- Do not move content template or sensitive-word mutations yet.
- Do not move DM sequence mutation or generation behavior yet.
- Do not move device bridge use cases yet.
- Do not move ORM model ownership or persistence class bodies.

## PR4b Allowed

- Move content template and sensitive-word mutation orchestration to `mutations.py`.
- Move content, keyword, regex, and clean-prompt generation calls to `content_generation.py`.
- Move DM sequence CRUD, generation, variants, and device sync use cases to `mutations.py`.
- Move content websocket broadcast helper to `realtime_events.py`.
- Keep `content_router.py` as the FastAPI route and HTTP error mapping boundary.
- Keep `dm_sequences_router.py` as the FastAPI schema, route, dependency, and StreamingResponse boundary.

## PR4b Not Allowed

- Do not move device bridge use cases yet.
- Do not change `content_changed` or `data_changed` realtime payload shapes.
- Do not move ORM model ownership or persistence class bodies.

## PR5 Allowed

- Move device content generation calls through `content_generation.py`.
- Move collected comment/user ingestion, comment AI reply, user profile, and avatar use cases to `collection_reports.py`.
- Move DM recipient claim, send report, and release use cases to `dm_claims.py`.
- Keep `/api/device/*` route paths and device-secret auth in `device_operations.content_bridge`.
- Preserve `data_changed` realtime payloads for comment, user, and conversation events.

## PR5 Not Allowed

- Do not move the `/api/device/*` route declarations out of `device_operations`.
- Do not move AI proxy behavior yet.
- Do not change device auth, response shapes, avatar file paths, or DM idempotency semantics.
- Do not move ORM model ownership or persistence class bodies.

## PR6 Allowed

- Inventory production imports of `app.routers.content`, `app.routers.data`, and `app.routers.dm_sequences`.
- Move `server/app/main.py` route wiring to `app.domains.content_collection.content_router`, `data_router`, and `dm_sequences_router`.
- Keep `app.routers.content`, `app.routers.data`, and `app.routers.dm_sequences` as compatibility facades for old import paths.
- Keep all public paths, methods, auth dependencies, response shapes, export streams, and realtime payloads unchanged.

## PR6 Not Allowed

- Do not delete `server/app/routers/content.py`, `server/app/routers/data.py`, or `server/app/routers/dm_sequences.py`.
- Do not remove router facade tests yet.
- Do not move ORM model ownership or persistence class bodies.

## Ownership Rules

- `app.domains.content_collection` owns the target migration boundary for `/api/content/*`, `/api/data/*`, and `/api/dm-sequences/*`.
- `app.routers.content` remains the compatibility import path for `/api/content/*` callers outside app wiring.
- `app.routers.data` remains the compatibility import path for `/api/data/*` callers outside app wiring.
- `app.routers.dm_sequences` remains the compatibility import path for `/api/dm-sequences/*` callers outside app wiring.
- `app.domains.content_collection.read_models` owns collected comment/user/conversation list and export payload shaping.
- `app.domains.content_collection.mutations` owns content template, sensitive-word, and DM sequence mutation orchestration.
- `app.domains.content_collection.content_generation` owns content, keyword, regex, and clean-prompt generation calls.
- `app.domains.content_collection.collection_reports` owns collected comment/user ingestion, comment AI reply, user profile, and avatar use cases.
- `app.domains.content_collection.dm_claims` owns DM recipient claim, send report, and release use cases.
- `app.domains.content_collection.realtime_events` owns content collection websocket broadcast helpers.
- `app.domains.device_operations.content_bridge` remains the device-authenticated route boundary for `/api/device/*` content, collection, DM, profile, and avatar paths until this domain provides handoff use cases.
- `content_collection` must preserve `content_changed` and `data_changed` websocket payloads when logic moves.
- Domain non-router use-case modules must avoid FastAPI imports unless they are route assembly modules.

## Facade Register

| Facade | Target | Introduced | Exit condition |
|---|---|---|---|
| `app.routers.content` | `app.domains.content_collection.content_router` | PR3 | Route/auth snapshots and existing content API tests pass with the domain router and all callers have an explicit compatibility path. |
| `app.routers.data` | `app.domains.content_collection.data_router` | PR3 | Data read/export snapshots pass with the domain router and streaming export behavior is unchanged. |
| `app.routers.dm_sequences` | `app.domains.content_collection.dm_sequences_router` | PR3 | DM sequence CRUD, generation, variant, and device-sync tests pass with the domain router. |
| `app.domains.device_operations.content_bridge` | `app.domains.content_collection` use cases | Planned PR5 | Device bridge tests prove `/api/device/*` auth, response shape, and realtime events are unchanged. |

## Migration Checklist

1. Characterize current route/auth snapshots, device bridge responses, and realtime events.
2. Add this metadata-only domain skeleton.
3. Move legacy route behavior behind domain routers with compatibility facades.
4. Split read models, mutations, content generation, and realtime event helpers into focused modules.
5. Move collection report and DM claim use cases behind content collection while keeping device route ownership stable.
6. Move app route wiring to domain router imports while keeping legacy facades.
7. Remove compatibility facades only after import inventories and route snapshots prove no behavior drift.

## Test Commands

Run the PR1/PR2 boundary checks:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_auth_parity.py server/tests/test_content_collection_domain_boundary.py server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py -q
```

Run the current compatibility checks:

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

## Compatibility Cleanup Gates

Do not remove `app.routers.content`, `app.routers.data`, or `app.routers.dm_sequences` until all of these are true:

- `rg "app\.routers\.(content|data|dm_sequences)|from app\.routers import (content|data|dm_sequences)" server/app server/tests` returns only approved compatibility shims, README entries, and cleanup tests.
- `server/tests/test_content_collection_auth_parity.py` passes against the domain routers.
- `server/tests/test_content_collection_router_facade.py` proves old and new router import paths expose the same route objects during the alias phase.
- `server/tests/test_content_collection_realtime_broadcasts.py` proves `content_changed` and `data_changed` payloads still reach `pair_ws_manager.broadcast_to_admins`.
- `server/tests/test_content_collection_device_bridge.py` proves the device bridge handoff keeps `/api/device/*` auth and response shapes stable.
- `app.main` imports content collection routers from `app.domains.content_collection`.
- Release notes mention the import-path migration.

Do not move ORM model ownership or persistence class bodies until a separate graph/import plan exists.
