# Content Collection Domain Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move content generation, collected-user/comment flows, DM claim/release flows, and collection read models into a focused content collection domain after device operations boundaries are mapped.

**Architecture:** Start with route and service characterization, then introduce `app.domains.content_collection` as a compatibility-preserving vertical slice. Reuse existing services as adapters before moving persistence or model ownership. Device-authenticated content endpoints must keep their `/api/device/*` paths through the `device_operations` bridge until this domain provides stable use cases and compatibility tests.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pytest, existing content, data, DM sequence, and task services.

---

## First Tasks

- [ ] Characterize content/data/DM routes and response shapes.
- [ ] Create `server/app/domains/content_collection`.
- [ ] Move route modules through compatibility aliases.
- [ ] Split read models from mutation use cases.
- [ ] Add cleanup gates and child tests for old import paths.

## File Map

### New Domain Files

- `server/app/domains/content_collection/__init__.py`
  - Exports `DOMAIN_NAME = "content_collection"` and route prefixes `("/api/content", "/api/data", "/api/dm-sequences")`.
- `server/app/domains/content_collection/README.md`
  - Facade register, device bridge contract, ownership rules, route snapshots, and cleanup gates.
- `server/app/domains/content_collection/content_router.py`
  - Owns `/api/content/*` route assembly after the compatibility move.
- `server/app/domains/content_collection/data_router.py`
  - Owns `/api/data/*` read/export route assembly after the compatibility move.
- `server/app/domains/content_collection/dm_sequences_router.py`
  - Owns `/api/dm-sequences/*` route assembly after the compatibility move.
- `server/app/domains/content_collection/schemas.py`
  - Owns request/response models currently embedded in `content.py`, `data.py`, `dm_sequences.py`, and device content handlers.
- `server/app/domains/content_collection/read_models.py`
  - Owns collected comment/user/conversation list and export payload shaping.
- `server/app/domains/content_collection/content_generation.py`
  - Owns content template generation, keyword generation, regex generation, clean-prompt generation, and device content generation use cases.
- `server/app/domains/content_collection/collection_reports.py`
  - Owns collected-user/comment report ingestion and dedupe/update behavior.
- `server/app/domains/content_collection/dm_claims.py`
  - Owns DM recipient claim, send report, release, and sequence-device sync use cases.
- `server/app/domains/content_collection/mutations.py`
  - Owns content template, sensitive-word, and DM sequence mutation orchestration.
- `server/app/domains/content_collection/realtime_events.py`
  - Owns websocket admin notification helpers for content and data mutations, preserving existing `pair_ws_manager.broadcast_to_admins` event payloads.
- `server/app/domains/content_collection/adapters.py`
  - Narrow adapter layer over `content_service`, `ai_generator`, task services, and current ORM/session access.

### Compatibility Facades To Modify In Future PRs

- `server/app/routers/content.py`
  - Becomes a compatibility alias to `app.domains.content_collection.content_router`.
- `server/app/routers/data.py`
  - Becomes a compatibility alias to `app.domains.content_collection.data_router`.
- `server/app/routers/dm_sequences.py`
  - Becomes a compatibility alias to `app.domains.content_collection.dm_sequences_router`.
- `server/app/domains/device_operations/content_bridge.py`
  - Delegates device-authenticated content, collection, comment, profile/avatar, and DM use cases to this domain after `device_operations` has mapped the route boundary.
- `server/app/main.py`
  - Keeps public route registration stable while imports migrate.

### New Tests

- `server/tests/test_content_collection_auth_parity.py`
  - Snapshots `/api/content/*`, `/api/data/*`, `/api/dm-sequences/*`, and device-authenticated content bridge dependencies.
- `server/tests/test_content_collection_domain_boundary.py`
  - Verifies package metadata, README facade register, app import smoke, and no behavior move in PR1.
- `server/tests/test_content_collection_router_facade.py`
  - Proves old router imports and new domain router imports resolve to the same module objects during migration.
- `server/tests/test_content_collection_read_models.py`
  - Covers comment, user, conversation, and export payload shaping.
- `server/tests/test_content_collection_mutations.py`
  - Covers content templates, sensitive words, DM sequence CRUD, generation, variants, and `content_changed` broadcasts.
- `server/tests/test_content_collection_device_bridge.py`
  - Covers `/api/device/collect-report`, `/api/device/dm-claim-recipient`, `/api/device/dm-send-report`, `/api/device/dm-release-recipient`, `/api/device/comment-ai-reply`, `/api/device/user-profile`, and `/api/device/user-avatar` compatibility through the device bridge.
- `server/tests/test_content_collection_realtime_broadcasts.py`
  - Patches/asserts `pair_ws_manager.broadcast_to_admins` for content mutations, collection reports, and DM claim/send/release flows, preserving `content_changed` and `data_changed` events with `comment`, `user`, and `conversation` types.

### Existing Tests To Keep Green

- `server/tests/test_content_api.py`
- `server/tests/test_content_service.py`
- `server/tests/test_collection_builder.py`
- `server/tests/test_data_export.py`
- `server/tests/test_dm_sequences_api.py`
- `server/tests/test_device_api.py`
- `server/tests/test_device_endpoints.py`
- `server/tests/test_tasks_api.py`

## PR Sequence

### PR1: Route, Service, And Device Bridge Characterization

- [ ] Add `/api/content/*`, `/api/data/*`, and `/api/dm-sequences/*` route/auth snapshots.
- [ ] Add response-shape tests for comment/user/conversation read models and export endpoints.
- [ ] Add device bridge characterization for content generation, collect report, comment AI reply, DM claim/send/release, profile, and avatar endpoints.
- [ ] Add realtime side-effect characterization that patches `pair_ws_manager.broadcast_to_admins` and asserts current `content_changed` and `data_changed` payloads.
- [ ] Confirm no domain package exists yet and no production behavior moves.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_auth_parity.py server/tests/test_content_collection_domain_boundary.py server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py -q
```

Expected before PR2: route/auth characterization passes; domain metadata and README tests fail until the skeleton exists.

### PR2: Domain Skeleton And Facade Register

- [ ] Create `server/app/domains/content_collection/__init__.py`.
- [ ] Create `server/app/domains/content_collection/README.md`.
- [ ] Document route ownership, device bridge ownership, and cleanup gates.
- [ ] Keep route behavior in legacy files.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_auth_parity.py server/tests/test_content_collection_domain_boundary.py -q
```

Expected after PR2: auth parity, domain metadata, README, and app import smoke pass.

### PR3: Route Module Compatibility Move

- [ ] Move current `content.py` behavior to `content_router.py`.
- [ ] Move current `data.py` behavior to `data_router.py`.
- [ ] Move current `dm_sequences.py` behavior to `dm_sequences_router.py`.
- [ ] Replace legacy route modules with compatibility aliases that preserve module identity.
- [ ] Add router facade tests before thinning modules.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_router_facade.py server/tests/test_content_api.py server/tests/test_data_export.py server/tests/test_dm_sequences_api.py -q
```

### PR4: Read Models And Mutation Use Cases

- [ ] Move comment/user/conversation list and export shaping to `read_models.py`.
- [ ] Move content template and sensitive-word mutations to `mutations.py`.
- [ ] Move content and prompt generation flows to `content_generation.py`.
- [ ] Preserve `pair_ws_manager.broadcast_to_admins` calls for `/api/content/*` mutations and assert `content_changed` payloads in `test_content_collection_realtime_broadcasts.py`.
- [ ] Keep persistence access behind adapters until ORM ownership is planned separately.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_read_models.py server/tests/test_content_collection_mutations.py server/tests/test_content_collection_realtime_broadcasts.py server/tests/test_content_api.py server/tests/test_collection_builder.py server/tests/test_data_export.py -q
```

### PR5: DM Claims And Device Bridge Handoff

- [ ] Move DM sequence device sync and DM claim/report/release use cases to `dm_claims.py`.
- [ ] Move collected-user/comment ingestion to `collection_reports.py`.
- [ ] Update `device_operations.content_bridge` to call `content_collection` use cases while preserving `/api/device/*` routes and device-secret auth.
- [ ] Preserve device-route realtime broadcasts: collection reports emit `data_changed` with `comment` or `user` types, and DM claim/send/release paths preserve `data_changed` with `conversation` type where current behavior emits it.
- [ ] Patch/assert `pair_ws_manager.broadcast_to_admins` in bridge tests so realtime side effects are not lost during the handoff.
- [ ] Add bridge tests for both domain paths and old device route paths.

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_dm_sequences_api.py -q
```

### PR6: Facade Cleanup Gates

- [ ] Inventory imports of `app.routers.content`, `app.routers.data`, and `app.routers.dm_sequences`.
- [ ] Move application wiring to domain imports only after compatibility tests prove route parity.
- [ ] Keep legacy router modules until old import path tests are intentionally removed in a cleanup commit.
- [ ] Update README gate status and handoff notes for device operations.

Run:

```powershell
rg -n "app\.routers\.(content|data|dm_sequences)|from app\.routers import (content|data|dm_sequences)" server/app server/tests
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_auth_parity.py server/tests/test_content_collection_router_facade.py server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py server/tests/test_content_api.py server/tests/test_data_export.py server/tests/test_dm_sequences_api.py -q
```

## Boundary And Compatibility Tests

- Route snapshot tests must cover all `/api/content/*`, `/api/data/*`, and `/api/dm-sequences/*` paths, methods, dependencies, and response model expectations.
- Device bridge tests must cover old `/api/device/*` paths that create or mutate collected content, comments, users, avatars, and DM claims.
- Realtime broadcast tests must patch/assert `pair_ws_manager.broadcast_to_admins` for content mutations, collection reports, and DM claim/send/release flows.
- Realtime event payload tests must preserve `content_changed` and `data_changed` events, including `comment`, `user`, and `conversation` types where the current routers emit them.
- Auth tests must distinguish admin-token routes from device-secret routes, especially `/api/dm-sequences/device/sync` and device bridge endpoints.
- Read model tests must assert current keys and pagination/export behavior for comments, users, conversations, and CSV/export responses.
- Facade tests must prove each legacy router module is the same module object as its domain router during the alias phase.
- App import smoke must prove `app.main.app` does not register duplicate content, data, or DM routes.
- Existing content, data, DM, device, and task tests listed in the file map remain compatibility gates for any PR that touches those behaviors.

## Facade Cleanup Gates

- [ ] `server/app/domains/content_collection/README.md` lists every active facade, target module, introduction PR, owner, and exit condition.
- [ ] No cleanup PR may remove `app.routers.content`, `app.routers.data`, or `app.routers.dm_sequences` while production imports still reference them.
- [ ] Device bridge cleanup requires `device_operations` tests to prove `/api/device/*` auth and response shape stay stable.
- [ ] Realtime cleanup requires `test_content_collection_realtime_broadcasts.py` to prove `content_changed` and `data_changed` payloads still reach `pair_ws_manager.broadcast_to_admins`.
- [ ] ORM or persistence class ownership must not move in this plan unless a separate graph/import plan exists.
- [ ] Export behavior must be tested before and after cleanup because stream/file responses are easy to regress.
- [ ] Final cleanup must include `rg` evidence showing only approved compatibility tests mention legacy router paths.

## Final Verification

Run from the repository root after the final PR in this child plan:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_collection_auth_parity.py server/tests/test_content_collection_domain_boundary.py server/tests/test_content_collection_router_facade.py server/tests/test_content_collection_read_models.py server/tests/test_content_collection_mutations.py server/tests/test_content_collection_device_bridge.py server/tests/test_content_collection_realtime_broadcasts.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_content_api.py server/tests/test_content_service.py server/tests/test_collection_builder.py server/tests/test_data_export.py server/tests/test_dm_sequences_api.py -q
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_device_api.py server/tests/test_device_endpoints.py server/tests/test_tasks_api.py -q
rg -n "app\.routers\.(content|data|dm_sequences)|from app\.routers import (content|data|dm_sequences)" server/app server/tests
rg -n "content_changed|data_changed|pair_ws_manager\.broadcast_to_admins" server/app/domains/content_collection server/app/domains/device_operations server/tests/test_content_collection_realtime_broadcasts.py
```

Expected:

- All new content collection tests pass.
- Existing content, data, DM, device bridge, and task smoke tests pass.
- Realtime tests prove `content_changed` and `data_changed` broadcasts still fire with the current event types.
- `rg` output contains only approved compatibility shims or tests until the explicit cleanup PR removes the shims.
- No `ai_video_series` source file is modified by this child domain implementation.

## GSTACK REVIEW REPORT

Status: PLANNED.
Date: 2026-06-18.
Scope: child implementation plan only; no content collection code is implemented by this document.

| Review | Status | Notes |
|---|---|---|
| CEO Review | INHERITED | Parent plan preserves this domain as a follow-up so content/collection/DM work does not get hidden inside `ai_video_series`. |
| Eng Review | REQUIRED BEFORE CODING | Future implementer should run engineering review after PR1 route and device bridge snapshots expose the true dependency graph. |
| Design Review | SKIPPED | No UI or product screen changes are planned. |
| DX Review | LIGHTWEIGHT | Plan includes executable PR phases, route surfaces, test files, and cleanup gates. |
| Codex Review | OPTIONAL | Recommended before moving DM claim/release behavior because auth and idempotency regressions are likely. |

Decision: proceed only after `device_operations` has mapped the device-authenticated bridge boundaries. This plan preserves the approved broad modularization scheme while keeping content collection outside the `ai_video_series` implementation chain.
