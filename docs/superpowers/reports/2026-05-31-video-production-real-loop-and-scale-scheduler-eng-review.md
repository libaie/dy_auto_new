# Video Production Real Loop And Scale Scheduler Engineering Review

Review target: `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`

Review date: 2026-05-31

Reviewer mode: engineering plan review

## Result

Status: approved after engineering hardening.

The plan is technically feasible if it stays on the existing video production control plane. I revised the spec to make the
hard parts explicit: `run_type` must be a real column, readiness must come from one shared service, final AI audit must not
auto-complete a run, mock scale execution must exercise the queue lifecycle, and real-short invalid duration must fail
before database mutation.

Implementation can proceed after these revisions. The risky parts are now visible enough to test.

## Step 0 Scope Challenge

Existing code already covers most of the sub-problems:

- one-sentence creation: `server/app/services/one_sentence_video_service.py`
- linked production runs: `server/app/services/production_run_service.py`
- stage execution and final writeback: `server/app/services/video_production_service.py`
- gate checks: `server/app/services/video_production_state.py`
- queue leasing/retry/pause/resume: `server/app/services/production_queue_service.py`
- production tree pagination: `server/app/services/production_tree_service.py`
- bulk review: `server/app/services/production_review_service.py`
- monitor and review UI: `web/src/views/VideoProductionMonitorPage.vue`, `web/src/views/AIVideoReviewPage.vue`

Minimum viable implementation:

1. Add run-type persistence and guards.
2. Add readiness service and payload exposure.
3. Harden the real-short path and final human gate.
4. Add mock scheduler driver on top of existing plan/queue/asset/review tables.
5. Patch existing frontend pages instead of adding a new dashboard.

Complexity check: this will touch more than 8 files, but that is expected because it crosses DB model, routes, services,
tests, and three UI surfaces. It is not a rewrite; the revised plan still reuses the current production stack.

No project todo file was found.

## Architecture Review

### Finding A1

[P1] (confidence: 9/10) `server/app/db_models.py:944` and `server/app/db_models.py:958` - `VideoProductionRun` currently has
no explicit `run_type`; relying on `model_trace_json` for enforcement would make real/mock safety dependent on optional
JSON.

Decision: fixed in the spec. `VideoProductionRun.run_type` is now required, indexed, and exposed in every payload. JSON is
only a legacy fallback.

### Finding A2

[P1] (confidence: 9/10) `server/app/services/video_production_service.py:1132` - current final AI audit can call
`complete_final_video`, which writes `Episode.video_url`, marks the run `completed`, and creates `GeneratedVideo` without a
human final approval.

Decision: fixed in the spec. AI final audit is recommendation-only; `assert_can_complete_final` must require latest final
asset plus human approval.

### Finding A3

[P1] (confidence: 9/10) `server/app/routers/video_production.py:51` and
`server/app/services/one_sentence_video_service.py:190` - current one-sentence route accepts up to 14400 seconds and then
normalizes to at least 5 seconds. A real-short entry could create database rows before realizing it is outside 60-90
seconds.

Decision: fixed in the spec. Real-short invalid duration must fail before any `Series`, `Episode`, `ProductionPlan`, or run
is created.

### Finding A4

[P2] (confidence: 8/10) `server/app/services/production_queue_service.py:72`, `:117`, and `:128` - queue primitives cover
claim, lease release, and failure, but there is no queue completion primitive. A mock scheduler would be tempted to update
`ProductionJob.status` directly.

Decision: fixed in the spec. Add `mark_job_completed` and use it from the mock-scale driver.

### Finding A5

[P2] (confidence: 8/10) `server/app/services/production_review_service.py:23` - bulk review currently knows asset ids and
asset types, but not run type. That is not enough to separate selected real approvals from mock full-series shortcuts.

Decision: fixed in the spec. Mock bulk actions require `run_type = mock_series_scale`; real bulk approval is selected latest
assets only.

## Code Quality Review

The plan should stay boring and explicit:

- one run-type helper module or section, not scattered `model_trace_json` reads
- one readiness service, not duplicated route-specific readiness builders
- one mock-scale driver, not mock branches inside every provider function
- no new review table, media table, provider client, or frontend shell

Technical debt to avoid:

1. Inferring production mode from route path or UI tab.
2. Letting frontend disabled buttons be the only gate enforcement.
3. Returning different readiness shapes from different mutation routes.
4. Generating mock assets with normal version allocation only, which can duplicate assets after resume.
5. Keeping old English/garbled UI test assertions when the production UI is being localized.

## Test Review

Detected test infrastructure:

- backend: `server/pytest.ini`, pytest with `asyncio_mode = auto`
- frontend: `web/vitest.config.js`, Vitest with jsdom

Coverage diagram:

```text
CODE PATHS
[TESTED] existing image/video/compose gates
  - server/tests/test_video_production_state_machine.py
  - server/tests/test_video_production_compose.py

[TESTED] existing bulk review latest-asset behavior
  - server/tests/test_production_bulk_review.py
  - server/tests/test_video_production_tree_api.py

[TESTED] existing queue claim/retry/lease release
  - server/tests/test_production_queue_service.py

[GAP] run_type column migration and payload exposure
[GAP] real_short_e2e rejects >90 seconds before DB mutation
[GAP] readiness endpoint and consistent readiness in mutation responses
[GAP] AI final audit cannot complete without human final approval
[GAP] assert_can_complete_final rejects mock final markers
[GAP] mock scale enqueue -> claim -> complete via queue primitive
[GAP] mock driver never calls provider clients
[GAP] mock resume creates no duplicate mock assets
[GAP] bulk mock shortcuts reject real runs
[GAP] selected real bulk approval rejects stale/unselected full-run approval

USER FLOWS
[GAP] one sentence -> real 60-90s -> image review -> video review -> final human review -> library
[GAP] one sentence real mode rejects long request with no partial rows
[GAP] 40 x 6 minute mock scale run with deterministic 5 percent failures
[GAP] monitor shows aggregate health without loading all 1440 segments
[GAP] review center separates image, video segment, and final queues
```

The revised spec now adds these gaps to the required test strategy.

## Performance Review

Main performance risk is the mock-scale monitor. `server/app/services/production_tree_service.py:72` paginates segments, but
the monitor also needs top-level aggregate counts for queue state, review state, failure state, and stage bottlenecks. Do
not calculate these by loading all segment rows into the Vue page.

Recommended backend shape:

```text
GET /runs/{run_id}/readiness
GET /runs/{run_id}/tree?page=&page_size=&episode_id=&stage=&status=
GET /runs/{run_id}/costs
```

The tree endpoint should stay paginated. The readiness/aggregate payload should remain bounded regardless of whether the
mock plan has 1440 segments or more.

## Required Engineering Changes Added To Spec

- explicit `VideoProductionRun.run_type` column and helpers
- `legacy_episode_run` compatibility value
- shared readiness service contract
- mutation responses return readiness
- final AI audit cannot complete the run
- `assert_can_complete_final` contract
- real-short invalid duration fails before DB writes
- mock queue completion primitive
- idempotent mock asset creation key
- backend cost preflight in stage guards
- no provider task id on preflight failure
- implementation sequence
- expanded backend, frontend, and mocked E2E tests

## Verdict

Engineering review passes after the spec hardening. There are no unresolved architecture decisions. The implementation
plan should start with run type + readiness before any frontend mode switch or mock scheduler work.
