# Review Findings Repair Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Track each independently testable task and its review.

**Goal:** Repair the fifteen audited correctness and authorization findings and make the repository test baseline reliable.

**Architecture:** Keep existing service boundaries. Use conditional database updates for claims, explicit owner/role checks for access, and small shared timeout/cancellation helpers. Independent file ownership permits parallel implementation; the coordinator integrates and commits changes sequentially.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Vue 3/Vitest, AutoJS6/Rhino ES5.1.

**Spec:** `docs/superpowers/specs/2026-11-05-review-fixes-design.md`

## Global Constraints

- 设备端保持 AutoJS6 / Rhino ES5.1：只能使用 var、function 和回调，不引入 Promise、箭头函数或 ES6 模块。
- 服务端继续使用 `bj_now()` 的 UTC+8 naive datetime。
- 保留已发布的迁移历史，以新增合并迁移收敛分支。
- 不调用真实付费模型服务，不修改线上数据库，不直接合并 main。
- 权限变更允许管理员管理全局资源，普通用户只能访问和操作其所有的资源。
- 修复后保持公开 API 的现有响应结构；明确错误情况可以返回 403/404/409。
- Only edit the files assigned to your task. Coordinate any shared interface changes first. Workers leave changes uncommitted; coordinator commits exact file sets sequentially and owns full-suite integration.

## Review Focus

- Mixed-owner bulk deletion must reject before deleting any owned item (Task 1).
- Old cancellation acknowledgements must not detach newly assigned channel work (Task 2).
- A worker returning after lease recovery must not overwrite the new claimant (Task 3).
- Existing fallback-created SQLite schema must not be destroyed by startup failure handling (Task 4).
- Queue flush recursion and permanent first-item errors must not lose later valid reports (Task 5).

### Task 1: Authorization and event isolation

**Files:** `server/app/deps.py`, `server/app/routers/tasks.py`, `server/app/routers/devices.py`, `server/app/routers/device.py`, `server/app/ws_manager.py`; new `server/tests/test_review_authorization.py` and directly relevant existing auth/WS tests.

**Interfaces:** Preserve service signatures from Task 2. Route ownership checks can query DB Task/Device/Account. `register_admin` may accept role with a backwards-compatible admin default for existing internal callers, but the real route must pass the actual role. Default unscoped broadcasts must reach administrators only; user-scoped task progress/results must reach the owner plus administrators. Preserve ordinary-user updates for their resources.

- [ ] Add behavior regressions for two ordinary users and admin: task detail/cancel/delete/bulk, pair request approval of another user's device, and owner/admin WS delivery with no cross-user delivery.
- [ ] Observe expected failures with `/tmp/dy-review-venv/bin/python -m pytest tests/test_review_authorization.py -q`.
- [ ] Centralize owner checks, enforce appropriate role/ownership for pairing, and scope task/result notifications without leaking unrelated events.
- [ ] Run new and existing relevant auth/device/WS tests, write the report with exact commands/results and any outstanding concerns.
- [ ] Coordinator reviews and commits this file set.

### Task 2: Task lifecycle and dispatch

**Files:** `server/app/services/task_service.py`, `server/app/services/channel_service.py`, `server/app/main.py`; optional new `server/app/services/task_deadline.py`; `server/tests/test_task_service.py`, `server/tests/test_channel_service.py`, new `server/tests/test_review_task_lifecycle.py` and task-local fixtures. Do not edit routers, db_models.py or shared conftest.py.

**Interfaces:** Existing public service signatures remain compatible. Keep the device timeout contract: `max(10 minutes, requested nurture duration + 2 minutes)`; server configured `TASK_STALE_MINUTES` remains a minimum, not a cap for legitimate long tasks. The coordinator applies the same rule on device. If a new helper is needed expose a synchronous checker or service function for behavior tests rather than reproducing the checker logic in tests.

- [ ] Reproduce pause/resume/reclaim, healthy 30-minute nurture at minute 11, expired direct task retry, eligible eleventh task, risk-controlled account, StatsEvent FK deletion, and five stale channel recoveries with a bounded retry counter.
- [ ] Run the failing regressions before editing production code.
- [ ] Preserve pending items on pause, restore interrupted work safely, use task-aware deadlines, fairly scan direct candidates, check active accounts, clean dependent stats events for hard deletion, and persist channel retry budgets across replacement Task rows.
- [ ] Cover late cancellation acknowledgements and retry exhaustion using the actual service/checker functions and FK-enabled test DBs.
- [ ] Run targeted task/channel suites; report exact results. Coordinator reviews and commits this file set.

### Task 3: Production worker recovery and image claim idempotency

**Files:** `server/app/services/production_queue_service.py`, `server/app/services/production_worker_service.py`, `server/app/services/image_creation_service.py`; optional directly necessary production helpers; new `server/tests/test_review_production_recovery.py` and related queue/image tests. Coordinate schema changes; do not edit db_models.py or migration files without the coordinator.

**Interfaces:** Preserve API contracts. Use existing lease/status fields where possible. A submitting image must have a durable claim before any awaited upstream call; no temporary local transaction may hold a write lock through a network call. A stable external_task_id is retained on ambiguous network outcomes. Old worker results cannot clobber a new lease.

- [ ] Reproduce expired `leased` job through `run_real_worker_step`, and two concurrent image dispatches with independent sessions and a controlled async provider.
- [ ] Observe failure, then wire expiry recovery into actual worker consumption and add lease fencing to terminal writes where needed.
- [ ] Atomically acquire image submission rights before await; make concurrent loser return a controlled conflict; preserve submission identity and handle failure/late response consistently.
- [ ] Test active lease is not stolen, expired lease recovers, already-submitted provider IDs are reused, stale result writes fail, and exactly one network submission occurs for concurrent requests.
- [ ] Run targeted production/image tests; report commands/results. Coordinator reviews and commits.

### Task 4: Database initialization, migration graph and test dependencies

**Files:** `server/app/database.py`, `server/alembic/versions/<new_merge>.py`, `server/requirements.txt`, database/migration tests and confirmed stale backend contract tests. Coordinator owns this task and shared test fixture decisions.

- [ ] Add regressions: one migration head, upgrade empty SQLite and each former head, migration exceptions propagated, SQLite-only connection initialization.
- [ ] Observe failures; create a merge revision without rewriting published ancestors, make startup migration failure explicit, and condition SQLite PRAGMAs by dialect.
- [ ] Add the missing jsonschema test dependency in the existing dependency pattern; review and update the three stale backend assertions only when justified by current intended behavior.
- [ ] Run migrations including a pre-existing fallback-created schema, then relevant backend tests.
- [ ] Review and commit database/dependency work.

### Task 5: Device execution, offline results and frontend evidence

**Files:** `device/core/task-executor.js`, `device/core/task-timeout.js`, `device/core/api-client.js`, optional `device/core/task-state.js`, cancellation consumers under `device/handlers`, device Node regressions; `web/src/components/agency/agencyExpertLabels.js`, related Vitest tests and the seven stale agency API mocks. Coordinator owns this task.

- [ ] Capture failing actual-module regressions for cyclic imports, a successful 60-minute nurture returning after 31 minutes, full search count -1, and offline queue containing deleted then valid task reports.
- [ ] Decouple cancellation state, reuse task-timeout.js in executor, define full-search iteration until cancellation/exhaustion/deadline, and drain offline queues without recursion or permanent-item blockage.
- [ ] Preserve evidence strings including `shot-001` and unknown English; repair API mocks using the real exported API contract.
- [ ] Run all device Node tests, full Vitest and production build; document Android validation limits.
- [ ] Review and commit this file set.

### Task 6: Integration, independent review and delivery

- [ ] Read all task reports and scope-specific diffs; review spec compliance and code quality for each task.
- [ ] Run full backend pytest, frontend Vitest/build, all device Node regressions, and migration checks with external paid APIs disabled.
- [ ] Hand a full-branch diff file and exact validation evidence to an independent reviewer; resolve material findings and rerun only affected validation plus required gates.
- [ ] Commit and publish the repair branch with a draft pull request if repository write access permits; do not merge main. Provide exact verification results and environment limitations to the user.
