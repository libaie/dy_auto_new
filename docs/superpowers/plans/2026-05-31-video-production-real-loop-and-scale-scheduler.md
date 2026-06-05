<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260531-011629.md -->
# Video Production Real Loop And Scale Scheduler Implementation Plan

> **For agentic workers:** Implement this task-by-task using the checklist below. Prefer `superpowers:subagent-driven-development` or `superpowers:executing-plans` when that workflow is available; otherwise execute inline from this plan without changing scope. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reliable one-sentence video production loop with explicit human review gates, plus a mock long-form scheduler that validates queue, retry, resume, and monitoring stability without spending real provider credits.

**Architecture:** Add an explicit `VideoProductionRun.run_type` boundary and route every real or mock path through that persisted value. Real short runs execute the existing staged provider pipeline and stop at human review gates; mock scale runs reuse production plan, segment, queue, and monitor structures while preventing real provider calls. Frontend changes expose the two modes, run readiness, review gates, and scheduler state without adding a visual editor or resuming 3D expert-console work.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, Vue 3, Vitest, existing dy_auto video production services, existing production tree and queue tables.

---

## Source Material

- Spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`
- Autoplan review: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\reports\2026-05-31-video-production-real-loop-and-scale-scheduler-autoplan-final-review.md`
- Autoplan plan review: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\reports\2026-05-31-video-production-real-loop-and-scale-scheduler-autoplan-plan-review.md`
- Engineering review: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\reports\2026-05-31-video-production-real-loop-and-scale-scheduler-eng-review.md`
- Existing backend router: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\video_production.py`
- Existing staged production service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py`
- Existing one-sentence service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\one_sentence_video_service.py`
- Existing production run service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\production_run_service.py`
- Existing queue service: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\production_queue_service.py`
- Existing frontend API client: `D:\devWorkspace\jsProjects\dy_auto\web\src\api\videoProduction.js`
- Existing one-sentence page: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\OneSentenceVideoPage.vue`
- Existing monitor page: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\VideoProductionMonitorPage.vue`
- Existing review page: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue`

## Scope

Build in this phase:

- Explicit run type persistence: `real_short_e2e`, `mock_series_scale`, `legacy_episode_run`.
- Strict real short duration guard: real one-sentence provider execution only supports 60 to 90 seconds in this phase.
- Mock scale scheduling path that can model 240 minutes and larger workloads without calling real image, video, audit, or compose providers. First-phase default is 240 minutes; the mock-only API must accept at least 480 minutes for stress testing.
- Human review gates for image assets, video segment assets, and final video assets.
- Final video writeback only after human final approval.
- Queue completion primitive and deterministic mock scheduler steps.
- Readiness payloads, named error payloads, run type badges, and stage-specific review UI.
- Chinese visible copy on the one-sentence page, review page, and production monitor areas touched by this work.
- Focused backend and frontend tests, plus a mocked E2E and a provider-smoke command that is opt-in.

Do not build in this phase:

- 3D expert console enhancements.
- Douyin publishing.
- Visual timeline editing.
- Automatic final approval.
- Real provider execution for 240-minute runs.
- A separate scheduling product outside the existing video production route family.

## File Structure

### Backend

- Modify: `server/app/db_models.py`
  - Add `VideoProductionRun.run_type`.
  - Add an index for run type filtering.
- Create: `server/alembic/versions/4d5e6f708192_add_video_production_run_type.py`
  - Add and roll back the `run_type` column and index.
- Create: `server/app/services/video_production_run_types.py`
  - Centralize run type constants, allowed values, getters, setters, and assertions.
- Create: `server/app/services/video_production_readiness.py`
  - Build run readiness payloads used by API and UI.
- Modify: `server/app/services/production_errors.py`
  - Align error detail fields with the plan: `code`, `message`, `cause`, `repair_action`, `repair_route`, `affected_ids`, `retryable`.
- Modify: `server/app/services/video_production_service.py`
  - Set and enforce run type on run creation, provider stages, final audit, final human approval, and event recording.
- Modify: `server/app/services/production_run_service.py`
  - Pass run type through linked run creation.
  - Reject invalid real short durations before DB mutation.
- Modify: `server/app/services/one_sentence_video_service.py`
  - Accept run type, validate real short duration, dispatch mock scale mode to the mock service.
- Modify: `server/app/services/production_queue_service.py`
  - Add `mark_job_completed`.
- Create: `server/app/services/mock_scale_scheduler_service.py`
  - Create mock series/episodes/storyboards/production plans.
  - Enqueue deterministic mock jobs.
  - Advance mock jobs without real provider calls.
- Modify: `server/app/services/production_review_service.py`
  - Restrict bulk mock approvals to mock scale runs.
  - Keep final video bulk approval rejected.
- Modify: `server/app/routers/video_production.py`
  - Add `run_type` request fields, run payload fields, readiness route, mock scheduler route, and structured error responses.
- Modify: existing backend tests listed in each task.
- Create focused backend tests listed in each task.

### Frontend

- Modify: `web/src/api/videoProduction.js`
  - Add run type request fields, readiness API, and mock scheduler API.
- Modify: `web/src/views/OneSentenceVideoPage.vue`
  - Replace mojibake and English stage copy with Chinese.
  - Add two-mode control: `真实短片` and `模拟长剧调度`.
  - Clamp real short UI to 60 to 90 seconds.
  - Show visible next gate and repair action.
- Modify: `web/src/views/VideoProductionMonitorPage.vue`
  - Show run type, readiness, queue counters, review gate cards, and next allowed action.
  - Keep developer controls but label them as explicit manual operations.
- Modify: `web/src/views/AIVideoReviewPage.vue`
  - Show stage-specific review queues.
  - Show human final approval as a distinct action.
  - Keep bulk approval off for final video.
- Modify: `web/src/__tests__/one-sentence-video-page.test.js`
- Modify: `web/src/__tests__/video-production-monitor-page.test.js`
- Modify: `web/src/__tests__/ai-video-review-page.test.js`
- Create: `web/src/__tests__/video-production-run-type-api.test.js`

## Global Execution Rules

- Do not edit unrelated feature areas.
- Keep new one-sentence real provider calls behind `run_type == "real_short_e2e"`. `legacy_episode_run` remains allowed only for existing episode-production compatibility and must be listed in the run-type action matrix.
- Keep every mock scale path provider-free.
- Do not let AI audit approval call `complete_final_video`.
- Use Chinese for visible copy in touched pages.
- Keep backend commands in PowerShell form.
- Commit after each task if tests for that task pass.

## Design Review Addendum

Design review status: completed on 2026-05-31.

Initial design completeness: 6/10. The backend and flow boundaries are strong, but the first version of this plan left too much room for a generic stacked-card UI, missed state coverage, and did not define mobile or accessibility behavior tightly enough.

Final design completeness after this addendum: 8.5/10. Remaining gap: there is no project-level `DESIGN.md`, and the local gstack designer binary is not installed, so no approved visual mockups are attached to this plan. Implementation must follow the concrete UI rules below, then run visual QA after code lands.

### What Already Exists

- `web/src/views/OneSentenceVideoPage.vue` already uses a dark operational surface, compact form controls, a step rail, and direct links to monitor and review.
- `web/src/views/VideoProductionMonitorPage.vue` already has a run health strip, stage timeline, exception queue, production tree, segment preview, action rail, and mobile bottom action bar.
- `web/src/views/AIVideoReviewPage.vue` already has a queue list, selected asset preview, AI review details, model trace details, and human decision buttons.
- `web/src/components/ui/AppButton.vue`, `AppInput.vue`, `AppSelect.vue`, `AppBadge.vue`, and `AppDialog.vue` exist and should be reused when the touched pages need reusable controls.
- `web/src/components/EmptyState.vue`, `StatusBadge.vue`, and `PageContainer.vue` exist and should be reused when they fit the page.
- No `DESIGN.md` exists. Do not invent a new decorative visual identity in this phase. Use the existing dark operator-console vocabulary and tighten hierarchy, spacing, states, and copy.

### Not In Scope

- 3D expert console redesign: explicitly paused by product direction.
- Marketing landing page treatment: these screens are operator tools, not public acquisition pages.
- Visual timeline editor: the user asked for one-click closure and review gates first.
- Decorative hero, carousel, illustration, or card-grid storytelling: these would slow down the control-plane workflow.
- New design system migration: there is no `DESIGN.md`; this phase may define local rules for touched pages only.

### Design Classification

This is APP UI. Apply calm workspace hierarchy, dense but readable surfaces, utility copy, visible gates, and minimal chrome. Do not use marketing page patterns.

Hard rejection patterns to avoid:

- Generic SaaS card grid as the first impression.
- Dashboard made only of equal-weight cards.
- Purple, violet, or blue-to-purple dominant gradients.
- Decorative icon circles, blobs, hero panels, or mood copy.
- Hover-only discoverability.
- Placeholder-as-label forms.
- Small low-contrast body text.

### Information Architecture

Primary user promise: "I always know where production is, what is blocking it, and what I can safely do next."

One-sentence page hierarchy:

```text
PAGE: 一句话成片
  1. Mode bar: 真实短片 | 模拟长剧调度
  2. Primary input: 故事一句话 + title + duration + budget
  3. Primary action: 生成并启动生产
  4. Production steps: visible stage rail
  5. Current result: run type, status, next gate, monitor/review links
```

Production monitor hierarchy:

```text
PAGE: AI 视频生产监控
  1. Run identity: title, run id, run type badge
  2. Readiness strip: status, current stage, next action, cost, segment count
  3. Stage timeline: storyboard -> image -> image review -> video -> video review -> compose -> final review
  4. Current gate block: why production stopped and where to repair it
  5. Main workspace:
     left: production tree
     center: selected segment preview and linked assets
     right: allowed manual actions
  6. Developer controls: collapsed by default or visually secondary
```

Review center hierarchy:

```text
PAGE: AI 视频人工审查
  1. Gate tabs: 图像审查 | 视频片段审查 | 最终审查
  2. Queue filters: run id, asset type, status, failed/rejected
  3. Queue list: thumbnail/type/version/status
  4. Selected asset preview: image/video player first
  5. Evidence panels: storyboard, AI 审查, model trace
  6. Decision rail: 通过当前版本 | 拒绝 | 重绘/重生 | 同步重生结果
  7. Final gate copy: "终审通过并入库", never "批量通过"
```

If only three items can be shown above the fold, they must be:

- `run_type` badge.
- `next_action.label`.
- the blocking review gate message with a repair route.

### Interaction State Matrix

Every touched page must specify what the user sees in each state. Do not ship generic "No data" strings.

| Feature | Loading | Empty | Error | Success | Partial |
|---------|---------|-------|-------|---------|---------|
| One-sentence submit | Button text `正在创建...`, form remains visible | Prompt is empty: primary button disabled and helper copy says `先输入故事核心` | Inline error shows `message` and `repair_action`; keep input text | Show run card with `run_type`, route buttons, and stage rail | If provider starts but first sync is pending, show `已启动画面生成，等待供应商结果` |
| Mode switch | No loading state; switch is local | Default to `真实短片` | If mode payload rejected, show structured error from backend | Selected mode has solid accent and description | Switching from mock to real clamps duration to 60-90 and shows a one-line notice |
| Monitor run load | Skeleton rows for health strip, stage rail, and tree | No production tree: show `还没有生成分段计划` with route back to series or one-sentence page | Error block shows `code`, `message`, `repair_action`, `repair_route` | Show health strip, timeline, gate block, tree, preview, action rail | If readiness loads but tree fails, keep readiness visible and show tree-specific retry |
| Review queue | Queue column skeleton and preview placeholder | Warm empty state: `当前闸门没有待审资产` plus `返回监控` action | Error block with retry button and raw `code` in small text | Selected asset preview and decision rail visible | If queue loads but selected asset media fails, keep evidence panels and show media-specific fallback |
| Mock scheduler | Worker button disabled while stepping | `没有待执行模拟任务` with status `mock_scale_completed` if complete | Show failed job count and retry route | Show completed/remaining counters and latest job ids | If some jobs complete and some fail, show both counts, not a single ambiguous status |

### User Journey Storyboard

| Step | User does | User feels | Plan must support |
|------|-----------|------------|-------------------|
| 1 | Opens 一句话成片 | Wants a safe first action | Mode labels explain real spend vs mock scheduling before submit |
| 2 | Enters story and duration | Needs confidence they will not accidentally spend on a long run | Real mode clamps 60-90 seconds; mock mode says it will not call providers |
| 3 | Starts production | Wants visible progress | Stage rail changes immediately and monitor link is visible |
| 4 | Hits image review gate | Needs to know the system stopped intentionally | Gate block says images need human review before video generation |
| 5 | Reviews an asset | Needs evidence, not blind approval | Preview, storyboard prompt, references, AI score, and model trace are visible |
| 6 | Approves all image/video segments | Wants the next stage to be obvious | Monitor primary action changes to video generation or compose |
| 7 | Final video appears | Needs extra confidence before library writeback | Final review uses distinct copy: `终审通过并入库` |
| 8 | Runs mock scale | Wants stability evidence, not fake video | Monitor shows queue completion, retries, leases, remaining jobs, and provider calls = 0 |

Time horizon:

- First 5 seconds: user sees mode, duration, budget, and that real vs mock is not ambiguous.
- First 5 minutes: user can create a run, reach a gate, open the right review queue, and understand why production paused.
- Long-term trust: every run preserves audit evidence, review history, model traces, and explicit human final approval.

### Visual And Copy Rules

- Use the existing dark operations palette: slate surfaces, emerald for allowed/complete, amber for review/waiting, rose for failure/reject, sky/cyan for running/provider sync.
- Keep panels functional. A panel is allowed only when it frames an interactive work area, a selected asset preview, a queue, or a state block.
- Border radius should stay at 8px or less unless an existing component already uses a different token.
- Body copy must be at least 14px. Primary decision text and form labels should be at least 16px on mobile. Contrast for body text must meet 4.5:1.
- Visible labels are required for every form control. Placeholder text may provide examples but cannot be the only label.
- Replace all English visible strings in touched pages with Chinese, except literal API ids, run ids, status enum values shown as diagnostic metadata, and model/provider ids.
- Do not center the whole page. This is a task workspace; left-align operational copy and controls.
- Do not add decorative gradients, decorative icon circles, or illustration-only empty states.
- Use `StatusBadge` or equivalent consistent badge treatment for run type and asset status.

### Responsive And Accessibility Requirements

Desktop, 1280px and wider:

- One-sentence page: prompt/editor area left, mode and production controls right, steps and result below.
- Monitor: three-column workspace is allowed: tree, preview, actions.
- Review center: queue column left, preview and evidence center/right.

Tablet, 768px to 1279px:

- Monitor becomes two-column: tree above or left, preview primary, actions below preview.
- Review center keeps queue above preview if horizontal space is tight.
- Developer controls must wrap and remain secondary.

Mobile, 375px to 767px:

- One-sentence page is single-column. Mode segmented control stays first after title.
- Monitor shows health strip, stage rail, gate block, then selected segment. Tree can collapse behind `查看分段`.
- Review center shows queue first, then selected preview. Decision buttons become a sticky bottom action bar.
- Touch targets must be at least 44px high.

Keyboard and screen reader:

- Stage rail and gate tabs must be keyboard reachable.
- Queue rows must expose selected state with `aria-current` or `aria-selected`.
- Gate blocks must use `aria-live="polite"` when readiness changes.
- Video/image preview must have descriptive labels based on frame id and asset type.
- Primary actions must not be disabled without nearby text explaining why.

### Unresolved Design Decisions

No blocker remains for implementation. The following decisions are explicitly made by this review:

- The first screen is an app workspace, not a landing page.
- Real and mock mode selection is shown before duration and before submit.
- The monitor's first viewport is status and next action, not the production tree.
- Final review has distinct language and no bulk approval.
- Mock scale UI reports scheduler evidence and never pretends to show a real generated video.

---

## Engineering Review Addendum

Engineering review status: completed on 2026-05-31.

Initial engineering completeness: 7/10. The plan reused the right existing production stack, but a few implementation snippets left race and transaction risks in the mock scheduler path.

Final engineering completeness after this addendum: 9/10. Remaining gap: this is still an implementation plan, not verified shipped code. During execution, every task must keep its failing-test-first step and run the command listed in that task before committing.

### Scope Challenge Result

Scope is held, not expanded. The plan touches more than eight files, but the breadth is justified because the goal crosses DB persistence, route contracts, provider guards, review gates, queue primitives, monitoring, and frontend state. The minimum complete version still needs those surfaces.

Existing code that must be reused:

- `VideoProductionRun`, `ProductionPlan`, `ProductionEpisode`, `ProductionScene`, `ProductionShot`, `ProductionSegment`, `ProductionJob`, `VideoProductionAsset`, and `VideoProductionReview`.
- `production_run_service.py` for linked run creation.
- `video_production_service.py` for real staged provider execution and final writeback.
- `production_queue_service.py` for leasing, retries, pause, resume, and now completion.
- `production_review_service.py` for human review actions.
- Existing one-sentence, monitor, and review Vue pages.

Still not in scope:

- Redis, Celery, APScheduler, or another scheduler runtime.
- Real 240-minute provider execution.
- A new review table or a new media asset table.
- Visual timeline editing, Douyin publishing, or more 3D expert console work.

### Engineering Corrections Applied To This Plan

- `claim_next_job` must accept an optional `plan_id` filter so mock scheduler steps cannot lease work from another active production plan.
- `enqueue_job` must accept `commit: bool = True` so `create_mock_scale_run` can build the series, episode, plan, segments, jobs, and run inside one outer transaction.
- `mock_scale_scheduler_service.py` must import `ProductionJob` because `run_mock_scheduler_step` queries remaining jobs.
- Provider stage guard examples must import `LEGACY_EPISODE_RUN` together with `REAL_SHORT_E2E`.
- Queue tests must cover the new `commit=False` and `plan_id` behaviors, not only `mark_job_completed`.
- Unknown `run_type` values must be rejected at the API/service boundary before DB mutation. Missing/null legacy rows may fall back to `legacy_episode_run`; malformed persisted values must not silently become legacy.
- Review UI must expose explicit gate tabs and must hide bulk approval when the active gate is final or the selected queue contains any `final_video` asset.
- Mock scale tests must prove retry, resume, lease recovery, partial completion, and provider-free behavior, not only happy-path queue completion.

### Run-Type Action Matrix

| Action | `real_short_e2e` | `mock_series_scale` | `legacy_episode_run` |
|--------|------------------|---------------------|----------------------|
| One-sentence real provider start | allowed, 60-90 seconds only | denied | denied |
| Existing episode provider stages | allowed | denied | allowed for backward compatibility |
| Mock worker step | denied | allowed | denied |
| AI final audit recommendation | allowed | denied | allowed only for existing legacy runs |
| Final human approval writeback | allowed | denied | allowed only for existing legacy runs with a real final asset |
| Bulk image/video segment approval | selected latest assets only | allowed for mock image/video segment assets | selected latest assets only |
| Final video bulk approval | denied | denied | denied |

### Data Flow

Real short path:

```text
POST one-sentence
  -> validate run_type = real_short_e2e
  -> validate duration 60-90 and budget before DB mutation
  -> create series, episode, production plan, run
  -> image provider stage
  -> image human review gate
  -> video provider stage
  -> video human review gate
  -> compose stage
  -> final AI audit recommendation only
  -> final human approval
  -> Episode.video_url + GeneratedVideo writeback
```

Mock scale path:

```text
POST one-sentence run_type = mock_series_scale
  -> create mock series, episode, storyboard, production plan, segments
  -> enqueue mock jobs with commit=False
  -> create VideoProductionRun
  -> single outer commit
  -> POST mock-worker-step
  -> claim_next_job(plan_id=run.production_plan_id)
  -> mark segment completed
  -> mark_job_completed
  -> readiness and monitor aggregate update
```

### Failure Mode Matrix

| Risk | Required guard | Required test |
|------|----------------|---------------|
| Real short duration creates partial rows before failing | Validate before `Series` insert | `test_real_short_rejects_duration_over_90_before_db_mutation` |
| Zero or negative real budget starts provider flow | Validate before DB mutation | `test_real_short_rejects_zero_budget_before_db_mutation` |
| Mock scheduler leases another plan's queued job | `claim_next_job(plan_id=...)` | `test_claim_next_job_can_scope_to_plan` |
| Mock run creation commits partial jobs before run exists | `enqueue_job(commit=False)` plus one outer commit | `test_enqueue_job_can_defer_commit_for_outer_transaction` |
| AI final audit writes library output without human approval | AI final audit cannot call `complete_final_video` | final human gate tests in Task 4 and Task 12 |
| Mock run reaches real provider calls | provider stage `assert_run_type` guards | Task 7 mock route and provider guard tests |
| Final video bulk approval bypasses review gate | final bulk approval rejected for every run type | `test_bulk_review_rejects_final_video` |
| Long mock monitor loads every segment | readiness returns bounded aggregates, tree stays paginated | frontend monitor partial and mock scheduler tests |

### Parallelization Lanes

- Lane A, backend safety foundation: Tasks 1 through 5 in order. Do not start mock scheduler until run type, readiness, final gate, and queue completion are in place.
- Lane B, mock scale driver: Task 6 after Task 5. This lane depends on plan-scoped queue claiming and deferred enqueue commits.
- Lane C, API and UI: Tasks 7 through 11 after the relevant backend contracts from Lane A are available. Frontend may mock API payloads while backend tests land.
- Lane D, end-to-end and provider smoke: Tasks 12 and 13 after all backend and frontend slices pass.

---

## Autoplan Review Addendum

Autoplan review status: completed on 2026-05-31 against this implementation plan.

Review mode: CEO -> Design -> Engineering -> DX, with intermediate choices auto-decided using completeness, reuse, explicitness, and dirty-worktree safety. External Codex voice ran in read-only mode and found eight plan-level risks; all were either fixed directly in this plan or converted into required tests.

### CEO Review

Premises accepted:

- The immediate product priority is real one-click short-video closure, review gates, and long-video scheduling stability.
- 3D expert console work remains out of scope for this phase.
- Mock long-form scheduling must prove control-plane stability without spending provider credits.
- Real 240-minute provider execution is out of scope.

Scope corrections:

- Mock scale no longer means only "up to 240 minutes." The plan now requires a 240-minute default and at least a 480-minute mock stress case through API/UI/tests.
- The implementation handoff no longer hard-blocks on subagent/skill availability. The checklist remains executable inline in a normal repo-only workflow.

### Design Review

Design corrections:

- Review center now requires visible gate tabs for `图像审查`, `视频片段审查`, and `最终审查`.
- Gate tabs must show counts and sync active gate state to route query parameters.
- Bulk approval must be hidden when the active gate is final or any loaded queue item is `final_video`.
- Frontend test instructions now require updating existing imports/mocks instead of blindly appending duplicate Vitest declarations.

### Engineering Review

Engineering corrections:

- Unknown `run_type` values must reject before DB mutation; malformed persisted values must not silently fall back to legacy.
- A run-type action matrix now resolves the previous contradiction between `real_short_e2e` and `legacy_episode_run` provider compatibility.
- Mock scheduler tests must cover expired leases, retry-wait jobs, pause/resume, partial completion, and provider-call count remaining zero.
- Plan-added routes must return the structured error shape instead of plain-string `HTTPException` details.

### DX Review

DX corrections:

- Final staging command now lists exact files instead of `git add server/app server/tests web/src`, preventing unrelated dirty work from being swept into this feature.
- The review item payload now includes `gate_counts`, so the UI can show gate status without extra guesswork.
- The test plan keeps provider smoke opt-in and dry-run capable.

### Dual Voice Summary

| Phase | Codex voice | Subagent voice | Consensus |
|-------|-------------|----------------|-----------|
| CEO | Found long-form promise mismatch and execution-handoff friction | Not run; current tool policy did not permit spawning without explicit subagent request | Codex findings accepted where they improved scope clarity |
| Design | Found missing gate tabs and weak final bulk-approval guard | Not run | Findings accepted and converted into UI/test requirements |
| Engineering | Found P0 unknown `run_type` bypass plus queue/provider policy gaps | Not run | Findings accepted and converted into helper, route, and test requirements |
| DX | Found duplicate frontend mock risk and broad dirty-repo staging risk | Not run | Findings accepted and converted into test-edit and exact-staging rules |

---

### Task 1: Persist Run Type And Add Central Helpers

**Files:**
- Modify: `server/app/db_models.py`
- Create: `server/alembic/versions/4d5e6f708192_add_video_production_run_type.py`
- Create: `server/app/services/video_production_run_types.py`
- Create: `server/tests/test_video_production_run_type.py`

- [ ] **Step 1: Write the failing run type tests**

Create `server/tests/test_video_production_run_type.py`:

```python
import pytest

from app.db_models import Episode, Series, VideoProductionRun
from app.services.video_production_run_types import (
    LEGACY_EPISODE_RUN,
    MOCK_SERIES_SCALE,
    REAL_SHORT_E2E,
    assert_run_type,
    get_run_type,
    set_run_type,
    validate_run_type,
)


def _run(db):
    series = Series(title="Run Type", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_video_production_run_defaults_to_legacy_run_type(db):
    run = _run(db)

    assert run.run_type == LEGACY_EPISODE_RUN
    assert get_run_type(run) == LEGACY_EPISODE_RUN


def test_set_run_type_rejects_unknown_value(db):
    run = _run(db)

    with pytest.raises(ValueError, match="Unsupported video production run type"):
        set_run_type(run, "unknown")


def test_validate_run_type_rejects_unknown_api_value():
    with pytest.raises(ValueError, match="Unsupported video production run type"):
        validate_run_type("typo_real_short")


def test_assert_run_type_accepts_allowed_type(db):
    run = _run(db)
    set_run_type(run, REAL_SHORT_E2E)

    assert_run_type(run, {REAL_SHORT_E2E})


def test_assert_run_type_rejects_wrong_type(db):
    run = _run(db)
    set_run_type(run, MOCK_SERIES_SCALE)

    with pytest.raises(ValueError, match="Run type mock_series_scale cannot perform this action"):
        assert_run_type(run, {REAL_SHORT_E2E})


def test_get_run_type_rejects_malformed_persisted_value(db):
    run = _run(db)
    run.run_type = "typo_real_short"

    with pytest.raises(ValueError, match="Unsupported video production run type"):
        get_run_type(run)
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_run_type.py -q
```

Expected: FAIL because `VideoProductionRun.run_type` and `video_production_run_types.py` do not exist.

- [ ] **Step 3: Add the model column**

In `server/app/db_models.py`, add this column after `production_link_status`:

```python
    run_type = Column(String(40), nullable=False, default="legacy_episode_run")
```

In the `VideoProductionRun.__table_args__` tuple, add this index:

```python
        Index("idx_video_production_runs_type", "run_type"),
```

- [ ] **Step 4: Add the Alembic migration**

Create `server/alembic/versions/4d5e6f708192_add_video_production_run_type.py`:

```python
"""add video production run type

Revision ID: 4d5e6f708192
Revises: 3c4d5e6f7081
Create Date: 2026-05-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d5e6f708192"
down_revision: Union[str, Sequence[str], None] = "3c4d5e6f7081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.add_column(
            sa.Column(
                "run_type",
                sa.String(length=40),
                nullable=False,
                server_default="legacy_episode_run",
            )
        )
        batch.create_index("idx_video_production_runs_type", ["run_type"])


def downgrade() -> None:
    with op.batch_alter_table("video_production_runs", reflect_kwargs={"resolve_fks": False}) as batch:
        batch.drop_index("idx_video_production_runs_type")
        batch.drop_column("run_type")
```

- [ ] **Step 5: Add run type helper service**

Create `server/app/services/video_production_run_types.py`:

```python
from collections.abc import Iterable

REAL_SHORT_E2E = "real_short_e2e"
MOCK_SERIES_SCALE = "mock_series_scale"
LEGACY_EPISODE_RUN = "legacy_episode_run"

ALLOWED_RUN_TYPES = {REAL_SHORT_E2E, MOCK_SERIES_SCALE, LEGACY_EPISODE_RUN}
REAL_PROVIDER_RUN_TYPES = {REAL_SHORT_E2E}
MOCK_RUN_TYPES = {MOCK_SERIES_SCALE}


def validate_run_type(run_type: str | None) -> str:
    value = run_type or LEGACY_EPISODE_RUN
    if value not in ALLOWED_RUN_TYPES:
        raise ValueError(f"Unsupported video production run type: {value}")
    return value


def get_run_type(run) -> str:
    return validate_run_type(getattr(run, "run_type", None))


def set_run_type(run, run_type: str) -> None:
    run.run_type = validate_run_type(run_type)


def assert_run_type(run, allowed: Iterable[str]) -> None:
    allowed_set = set(allowed)
    current = get_run_type(run)
    if current not in allowed_set:
        allowed_text = ", ".join(sorted(allowed_set))
        raise ValueError(f"Run type {current} cannot perform this action. Allowed: {allowed_text}")


def is_real_provider_run(run) -> bool:
    return get_run_type(run) in REAL_PROVIDER_RUN_TYPES


def is_mock_scale_run(run) -> bool:
    return get_run_type(run) in MOCK_RUN_TYPES
```

- [ ] **Step 6: Run the run type tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_run_type.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/app/db_models.py server/alembic/versions/4d5e6f708192_add_video_production_run_type.py server/app/services/video_production_run_types.py server/tests/test_video_production_run_type.py
git commit -m "feat: persist video production run type"
```

---

### Task 2: Add Readiness Contract And Named Error Shape

**Files:**
- Modify: `server/app/services/production_errors.py`
- Create: `server/app/services/video_production_readiness.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_video_production_readiness.py`
- Modify: `server/tests/test_video_production_named_errors.py`

- [ ] **Step 1: Write readiness tests**

Create `server/tests/test_video_production_readiness.py`:

```python
from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_readiness import build_run_readiness
from app.services.video_production_run_types import REAL_SHORT_E2E, validate_run_type


def _run(db, status="storyboard_ready"):
    series = Series(title="Readiness", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=REAL_SHORT_E2E,
        status=status,
        current_stage="storyboard_ready",
        storyboard_json={"frames": [{"frame_id": "frame-001"}]},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_readiness_exposes_run_type_and_next_action(db):
    run = _run(db)

    payload = build_run_readiness(db, run)

    assert payload["run_id"] == run.id
    assert payload["run_type"] == REAL_SHORT_E2E
    assert payload["can_start_images"] is True
    assert payload["next_action"]["key"] == "start_images"
    assert payload["blocks"] == []


def test_readiness_blocks_video_until_images_are_approved(db):
    run = _run(db, status="image_review_pending")
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        status="review_pending",
        version=1,
    ))
    db.commit()

    payload = build_run_readiness(db, run)

    assert payload["can_start_videos"] is False
    assert payload["blocks"][0]["code"] == "IMAGE_REVIEW_REQUIRED"
    assert payload["blocks"][0]["repair_route"] == f"/ai-video-review?run_id={run.id}"
```

- [ ] **Step 2: Run readiness tests and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_readiness.py -q
```

Expected: FAIL because the readiness service does not exist.

- [ ] **Step 3: Extend named error fields**

In `server/app/services/production_errors.py`, update the dataclass and serializer:

```python
class ProductionErrorCode(str, Enum):
    INVALID_RUN_TYPE = "INVALID_RUN_TYPE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    # keep existing codes


@dataclass
class ProductionRepairableError(ValueError):
    code: ProductionErrorCode
    message: str
    repair_action: str
    repair_route: str | None = None
    retryable: bool = False
    affected_ids: list[str] = field(default_factory=list)
    cause: str | None = None


def to_http_detail(error: ProductionRepairableError) -> dict:
    return {
        "code": error.code.value,
        "error_code": error.code.value,
        "message": error.message,
        "cause": error.cause,
        "repair_action": error.repair_action,
        "repair_route": error.repair_route,
        "retryable": error.retryable,
        "affected_ids": error.affected_ids,
    }
```

- [ ] **Step 4: Add readiness service**

Create `server/app/services/video_production_readiness.py`:

```python
from sqlalchemy.orm import Session

from app.db_models import VideoProductionAsset, VideoProductionRun
from app.services.video_production_run_types import get_run_type


REVIEW_STATUSES = {
    "image_review_pending",
    "image_human_review_required",
    "video_review_pending",
    "video_human_review_required",
    "final_review_pending",
}


def _block(code: str, message: str, repair_action: str, repair_route: str, affected_ids: list[str] | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "cause": message,
        "repair_action": repair_action,
        "repair_route": repair_route,
        "affected_ids": affected_ids or [],
        "retryable": True,
    }


def _asset_counts(db: Session, run: VideoProductionRun) -> dict:
    rows = db.query(VideoProductionAsset).filter(VideoProductionAsset.run_id == run.id).all()
    counts = {
        "image": {"total": 0, "approved": 0, "pending": 0, "failed": 0},
        "video_segment": {"total": 0, "approved": 0, "pending": 0, "failed": 0},
        "final_video": {"total": 0, "approved": 0, "pending": 0, "failed": 0},
    }
    for asset in rows:
        bucket = counts.setdefault(asset.asset_type, {"total": 0, "approved": 0, "pending": 0, "failed": 0})
        bucket["total"] += 1
        if asset.status == "approved":
            bucket["approved"] += 1
        elif asset.status == "failed":
            bucket["failed"] += 1
        else:
            bucket["pending"] += 1
    return counts


def _next_action(run: VideoProductionRun) -> dict:
    status = run.status
    if status in {"draft", "storyboard_ready"}:
        return {"key": "start_images", "label": "启动画面生成"}
    if status == "image_approved":
        return {"key": "start_videos", "label": "启动视频片段生成"}
    if status == "video_segments_approved":
        return {"key": "compose", "label": "合成最终视频"}
    if status in REVIEW_STATUSES:
        return {"key": "open_review", "label": "进入人工审查"}
    if status in {"image_batch_running", "video_batch_running", "composing"}:
        return {"key": "sync_provider", "label": "同步供应商结果"}
    if status == "completed":
        return {"key": "completed", "label": "已完成"}
    return {"key": "inspect", "label": "查看状态"}


def build_run_readiness(db: Session, run: VideoProductionRun) -> dict:
    blocks: list[dict] = []
    if run.status in {"image_review_pending", "image_human_review_required"}:
        blocks.append(_block(
            "IMAGE_REVIEW_REQUIRED",
            "图像资产需要人工审查后才能进入图生视频阶段。",
            "打开图像审查队列",
            f"/ai-video-review?run_id={run.id}&asset_type=image",
            [run.id],
        ))
    if run.status in {"video_review_pending", "video_human_review_required"}:
        blocks.append(_block(
            "VIDEO_REVIEW_REQUIRED",
            "视频片段需要人工审查后才能进入最终合成。",
            "打开视频片段审查队列",
            f"/ai-video-review?run_id={run.id}&asset_type=video_segment",
            [run.id],
        ))
    if run.status == "final_review_pending":
        blocks.append(_block(
            "FINAL_REVIEW_REQUIRED",
            "最终视频需要人工终审后才能写回剧集和视频库。",
            "打开终审队列",
            f"/ai-video-review?run_id={run.id}&asset_type=final_video",
            [run.id],
        ))

    return {
        "run_id": run.id,
        "run_type": get_run_type(run),
        "status": run.status,
        "current_stage": run.current_stage,
        "can_start_images": run.status in {"draft", "storyboard_ready"},
        "can_start_videos": run.status == "image_approved",
        "can_compose": run.status == "video_segments_approved",
        "can_complete_final": run.status == "final_review_pending",
        "needs_review": run.status in REVIEW_STATUSES,
        "next_action": _next_action(run),
        "asset_counts": _asset_counts(db, run),
        "blocks": blocks,
    }
```

- [ ] **Step 5: Add readiness route and payload field**

In `server/app/routers/video_production.py`, import the new functions:

```python
from app.services.video_production_readiness import build_run_readiness
from app.services.video_production_run_types import get_run_type
```

Add `run_type` to `_run_payload`:

```python
        "run_type": get_run_type(run),
```

Add this route after `get_run`:

```python
@router.get("/runs/{run_id}/readiness")
def get_run_readiness(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise HTTPException(
            404,
            to_http_detail(ProductionRepairableError(
                code=ProductionErrorCode.RUN_NOT_FOUND,
                message="没有找到对应的视频生产任务。",
                repair_action="返回生产列表后重新选择任务。",
                repair_route="/video-production",
                retryable=False,
                affected_ids=[run_id],
            )),
        )
    return {"ok": True, "readiness": build_run_readiness(db, run)}
```

- [ ] **Step 6: Run focused backend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_readiness.py tests/test_video_production_named_errors.py -q
```

Expected: PASS. If `test_video_production_named_errors.py` expects only `error_code`, update it to assert both `code` and `error_code` equal the same value.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/production_errors.py server/app/services/video_production_readiness.py server/app/routers/video_production.py server/tests/test_video_production_readiness.py server/tests/test_video_production_named_errors.py
git commit -m "feat: expose video production readiness"
```

---

### Task 3: Enforce Real Short One-Sentence Boundary

**Files:**
- Modify: `server/app/routers/video_production.py`
- Modify: `server/app/services/one_sentence_video_service.py`
- Modify: `server/app/services/production_run_service.py`
- Modify: `server/app/services/video_production_service.py`
- Create: `server/tests/test_one_sentence_video_run_types.py`

- [ ] **Step 1: Write route tests for real short duration guard**

Create `server/tests/test_one_sentence_video_run_types.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Series, VideoProductionRun
from app.main import app
from app.services.video_production_run_types import REAL_SHORT_E2E

client = TestClient(app)


def test_real_short_rejects_duration_over_90_before_db_mutation(db):
    response = client.post("/api/video-production/one-sentence", json={
        "prompt": "一个青年在雨夜发现会发光的地图，并追踪地下城市的秘密。",
        "title": "雨夜地图",
        "target_duration_seconds": 120,
        "run_type": REAL_SHORT_E2E,
        "autostart_images": False,
    })

    assert response.status_code == 400
    assert "60 到 90 秒" in str(response.json()["detail"])
    assert db.query(Series).count() == 0
    assert db.query(VideoProductionRun).count() == 0


def test_real_short_response_exposes_run_type(db, monkeypatch):
    async def fake_start_episode_production(db, **kwargs):
        from app.services.video_production_service import create_run_from_episode
        return create_run_from_episode(
            db,
            kwargs["series_id"],
            kwargs["episode_id"],
            run_type=kwargs["run_type"],
        )

    monkeypatch.setattr(
        "app.services.one_sentence_video_service.production_run_service.start_episode_production",
        fake_start_episode_production,
    )

    response = client.post("/api/video-production/one-sentence", json={
        "prompt": "一名导演用一分钟讲完一场危险救援。",
        "title": "一分钟救援",
        "target_duration_seconds": 60,
        "run_type": REAL_SHORT_E2E,
        "autostart_images": False,
    })

    assert response.status_code == 200
    assert response.json()["run"]["run_type"] == REAL_SHORT_E2E


def test_unknown_run_type_rejects_before_db_mutation(db):
    response = client.post("/api/video-production/one-sentence", json={
        "prompt": "一个错误模式不应该进入生产。",
        "title": "错误模式",
        "target_duration_seconds": 60,
        "run_type": "typo_real_short",
        "autostart_images": False,
    })

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_RUN_TYPE"
    assert db.query(Series).count() == 0
    assert db.query(VideoProductionRun).count() == 0


```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_one_sentence_video_run_types.py -q
```

Expected: FAIL because the request model and services do not accept `run_type`.

- [ ] **Step 3: Add request fields**

In `server/app/routers/video_production.py`, import constants:

```python
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError, to_http_detail
from app.services.video_production_run_types import REAL_SHORT_E2E, get_run_type, validate_run_type
```

Add `run_type` to `StartRunRequest` and `OneSentenceVideoRequest`:

```python
    run_type: str = REAL_SHORT_E2E
```

Change `OneSentenceVideoRequest.target_duration_seconds` to keep API compatibility while service enforces run type:

```python
    target_duration_seconds: int = Field(60, ge=5, le=86400)
```

Add a small route-level validator helper so invalid values return the same structured 400 shape as other production errors instead of FastAPI's generic 422:

```python
def _validate_request_run_type(value: str) -> str:
    try:
        return validate_run_type(value)
    except ValueError as exc:
        raise HTTPException(
            400,
            to_http_detail(ProductionRepairableError(
                code=ProductionErrorCode.INVALID_RUN_TYPE,
                message=str(exc),
                repair_action="选择真实短片、模拟长剧调度或历史剧集生产中的一种运行类型。",
                retryable=False,
            )),
        ) from exc
```

Call `_validate_request_run_type(body.run_type)` before any service call that can create rows.

Pass `run_type` into both service calls:

```python
            run_type=body.run_type,
```

- [ ] **Step 4: Add validation and pass-through in services**

In `server/app/services/one_sentence_video_service.py`, import constants:

```python
from app.services.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E, validate_run_type
```

Add this function near `_clean_prompt`:

```python
def _validate_real_short_duration(target_duration_seconds: int) -> None:
    if target_duration_seconds < 60 or target_duration_seconds > 90:
        raise VideoProductionError("真实短片模式当前只允许 60 到 90 秒，长视频请使用模拟长剧调度。")
```

Update `create_one_sentence_video` signature:

```python
async def create_one_sentence_video(
    db: Session,
    *,
    prompt: str,
    title: str | None = None,
    genre: str = "drama",
    target_duration_seconds: int = DEFAULT_TARGET_SECONDS,
    budget_limit: float | None = None,
    autostart_images: bool = True,
    run_type: str = REAL_SHORT_E2E,
) -> dict[str, Any]:
```

After normalizing `target_duration_seconds`, add:

```python
    run_type = validate_run_type(run_type)
    if run_type == REAL_SHORT_E2E:
        _validate_real_short_duration(target_duration_seconds)
    if run_type == MOCK_SERIES_SCALE:
        from app.services.mock_scale_scheduler_service import create_mock_scale_run

        return create_mock_scale_run(
            db,
            prompt=prompt,
            title=title,
            genre=genre,
            target_duration_seconds=target_duration_seconds,
            budget_limit=budget_limit,
        )
```

When calling `production_run_service.start_episode_production`, pass:

```python
        run_type=run_type,
```

In `server/app/services/production_run_service.py`, update `start_episode_production` signature:

```python
    run_type: str = REAL_SHORT_E2E,
```

Before reading series, add:

```python
    if run_type == REAL_SHORT_E2E and target_duration_seconds is not None:
        if target_duration_seconds < 60 or target_duration_seconds > 90:
            raise ProductionRepairableError(
                code=ProductionErrorCode.STORYBOARD_MISSING,
                message="真实短片模式当前只允许 60 到 90 秒。",
                cause="REAL_SHORT_DURATION_OUT_OF_RANGE",
                repair_action="将时长改为 60 到 90 秒，或切换为模拟长剧调度",
                retryable=True,
            )
```

When calling `create_linked_run`, pass:

```python
    run = create_linked_run(db, series_id, episode_id, production_plan_id=plan.id, run_type=run_type)
```

Update `create_linked_run` signature:

```python
    run_type: str = REAL_SHORT_E2E,
```

When calling `create_run_from_episode`, pass:

```python
    run = create_run_from_episode(db, series_id, episode_id, commit=False, run_type=run_type)
```

In `server/app/services/video_production_service.py`, update `create_run_from_episode` signature:

```python
def create_run_from_episode(
    db: Session,
    series_id: str,
    episode_id: str,
    commit: bool = True,
    run_type: str = LEGACY_EPISODE_RUN,
) -> VideoProductionRun:
```

Set the field in the `VideoProductionRun` constructor:

```python
        run_type=run_type,
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_one_sentence_video_run_types.py tests/test_video_production_start_flow_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/routers/video_production.py server/app/services/one_sentence_video_service.py server/app/services/production_run_service.py server/app/services/video_production_service.py server/tests/test_one_sentence_video_run_types.py
git commit -m "feat: enforce real short video run boundary"
```

---

### Task 4: Make Final Video Completion Human-Only

**Files:**
- Modify: `server/app/services/video_production_state.py`
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/production_review_service.py`
- Modify: `server/tests/test_video_production_compose.py`
- Create: `server/tests/test_video_production_final_gate.py`

- [ ] **Step 1: Write final gate tests**

Create `server/tests/test_video_production_final_gate.py`:

```python
from app.db_models import Episode, GeneratedVideo, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import approve_asset, run_final_audit_for_asset
from app.services.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E


def _final_asset(db, run_type=REAL_SHORT_E2E):
    series = Series(title="Final Gate", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=run_type,
        status="final_review_pending",
        current_stage="final_review",
        storyboard_json={"frames": [{"frame_id": "frame-001"}]},
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url="final.mp4",
        local_path="output/final.mp4",
        status="review_pending",
        version=1,
        is_latest=True,
    )
    db.add(asset)
    db.commit()
    db.refresh(run)
    db.refresh(asset)
    return run, asset, episode


def test_ai_final_audit_does_not_complete_video(db, monkeypatch):
    run, asset, episode = _final_asset(db)
    monkeypatch.setattr(
        "app.routers.audit._do_audit",
        lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []},
    )
    monkeypatch.setattr(
        "app.services.video_production_service.resolve_runtime_model_config",
        lambda db, scene: {"provider": "mock", "model_name": "audit"},
    )

    updated = run_final_audit_for_asset(db, run, asset)

    assert updated.status == "review_pending"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "final_review_pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_final_approval_completes_video(db):
    run, asset, episode = _final_asset(db)

    approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="终审通过")

    db.refresh(run)
    db.refresh(episode)
    assert run.status == "completed"
    assert episode.video_url == "final.mp4"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 1


def test_mock_scale_final_approval_is_rejected(db):
    run, asset, episode = _final_asset(db, run_type=MOCK_SERIES_SCALE)

    try:
        approve_asset(db, asset.id, reviewer_user_id="reviewer-1", comment="mock final")
    except ValueError as exc:
        assert "mock_series_scale" in str(exc)
    else:
        raise AssertionError("Mock scale final video approval must be rejected")

    db.refresh(run)
    db.refresh(episode)
    assert run.status == "final_review_pending"
    assert episode.video_url is None
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_final_gate.py -q
```

Expected: FAIL because AI final audit currently completes the final video.

- [ ] **Step 3: Add final completion assertion**

In `server/app/services/video_production_state.py`, import run type helpers:

```python
from app.services.video_production_run_types import MOCK_SERIES_SCALE, REAL_SHORT_E2E, assert_run_type
```

Add this function:

```python
def assert_can_complete_final(db: Session, run: VideoProductionRun, final_asset: VideoProductionAsset) -> None:
    assert_run_type(run, {REAL_SHORT_E2E})
    if final_asset.asset_type != "final_video":
        raise ValueError("Only final video assets can complete a production run")
    if final_asset.status != "approved":
        raise ValueError("Final video requires human approval before completion")
    latest = latest_assets_by_frame(db, run.id, "final_video").get(final_asset.frame_id)
    if not latest or latest.id != final_asset.id:
        raise ValueError("Final video asset is not the latest version")
```

- [ ] **Step 4: Stop AI final audit from completing**

In `server/app/services/video_production_service.py`, import `assert_can_complete_final`:

```python
from app.services.video_production_state import assert_can_complete_final
```

In `run_final_audit_for_asset`, replace the AI-approved branch:

```python
    if gate["gate_status"] == "approved":
        asset.status = "review_pending"
        run.status = "final_review_pending"
        run.current_stage = "final_review"
        db.commit()
        return asset
```

In `approve_final_video_asset`, set status before completion and call assertion:

```python
    asset.status = "approved"
    assert_can_complete_final(db, run, asset)
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        comment=comment,
        reviewer_user_id=reviewer_user_id,
        **_review_snapshot(asset),
    ))
    return complete_final_video(db, run, asset)
```

Keep the stale asset check already present in the function.

- [ ] **Step 5: Keep bulk approval away from final video**

In `server/app/services/production_review_service.py`, keep this branch and add run type validation in the next task:

```python
        if asset.asset_type == "final_video":
            raise ValueError("Bulk review cannot approve final video assets")
```

- [ ] **Step 6: Run final gate and compose tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_final_gate.py tests/test_video_production_compose.py tests/test_video_production_full_mocked_e2e.py -q
```

Expected: PASS after updating full mocked E2E to explicitly approve the final video asset after syncing compose.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/video_production_state.py server/app/services/video_production_service.py server/app/services/production_review_service.py server/tests/test_video_production_final_gate.py server/tests/test_video_production_compose.py server/tests/test_video_production_full_mocked_e2e.py
git commit -m "feat: require human final video approval"
```

---

### Task 5: Add Queue Completion Primitive

**Files:**
- Modify: `server/app/services/production_queue_service.py`
- Modify: `server/tests/test_production_queue_service.py`

- [ ] **Step 1: Add failing queue completion tests**

Append to `server/tests/test_production_queue_service.py`:

```python
from app.services.production_queue_service import claim_next_job, mark_job_completed


def test_mark_job_completed_sets_terminal_fields(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")
    job.status = "leased"
    job.lease_id = "worker-a"
    job.provider_task_id = "provider-old"
    db.commit()

    completed = mark_job_completed(db, job.id, provider_task_id="provider-new")

    assert completed.status == "completed"
    assert completed.provider_task_id == "provider-new"
    assert completed.lease_id is None
    assert completed.leased_until is None
    assert completed.completed_at is not None


def test_mark_job_completed_is_idempotent(db):
    plan = _plan(db)
    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1")

    first = mark_job_completed(db, job.id, provider_task_id="provider-a")
    second = mark_job_completed(db, job.id, provider_task_id="provider-b")

    assert first.id == second.id
    assert second.status == "completed"
    assert second.provider_task_id == "provider-a"


def test_enqueue_job_can_defer_commit_for_outer_transaction(db, monkeypatch):
    plan = _plan(db)
    calls = {"commit": 0}
    original_commit = db.commit

    def counted_commit():
        calls["commit"] += 1
        return original_commit()

    monkeypatch.setattr(db, "commit", counted_commit)

    job = enqueue_job(db, plan.id, "segment", "seg-1", "image_generation", "seg-1:image:v1", commit=False)

    assert job.id is not None
    assert job.status == "queued"
    assert calls["commit"] == 0


def test_claim_next_job_can_scope_to_plan(db):
    first_plan = _plan(db)
    second_plan = _plan(db)
    first_job = enqueue_job(db, first_plan.id, "segment", "seg-1", "image_generation", "plan-a:v1", priority=1)
    second_job = enqueue_job(db, second_plan.id, "segment", "seg-2", "image_generation", "plan-b:v1", priority=2)

    claimed = claim_next_job(db, lease_id="worker-b", lease_seconds=30, plan_id=second_plan.id)

    assert claimed is not None
    assert claimed.id == second_job.id
    db.refresh(first_job)
    assert first_job.status == "queued"
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest `
  tests/test_production_queue_service.py::test_mark_job_completed_sets_terminal_fields `
  tests/test_production_queue_service.py::test_mark_job_completed_is_idempotent `
  tests/test_production_queue_service.py::test_enqueue_job_can_defer_commit_for_outer_transaction `
  tests/test_production_queue_service.py::test_claim_next_job_can_scope_to_plan `
  -q
```

Expected: FAIL because `mark_job_completed`, `enqueue_job(commit=False)`, and `claim_next_job(plan_id=...)` do not exist.

- [ ] **Step 3: Implement queue completion**

In `server/app/services/production_queue_service.py`, import the status:

```python
    JOB_COMPLETED,
```

Add this function after `fail_job`:

```python
def mark_job_completed(db: Session, job_id: str, provider_task_id: str | None = None) -> ProductionJob:
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise ValueError("Production job not found")

    if job.status == JOB_COMPLETED:
        return job

    now = bj_now()
    job.status = JOB_COMPLETED
    if provider_task_id and not job.provider_task_id:
        job.provider_task_id = provider_task_id
    job.lease_id = None
    job.leased_until = None
    job.retry_after = None
    job.error_code = None
    job.error_message = None
    job.retryable = False
    job.completed_at = now
    job.updated_at = now
    db.commit()
    db.refresh(job)
    return job
```

Update `enqueue_job` so existing callers keep the same default behavior, while mock run creation can defer the commit to its outer transaction:

```python
def enqueue_job(
    db: Session,
    plan_id: str,
    target_type: str,
    target_id: str,
    stage: str,
    idempotency_key: str,
    priority: int = 100,
    max_attempts: int = 3,
    commit: bool = True,
) -> ProductionJob:
    existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
    if existing:
        return existing
    _ensure_plan_accepts_jobs(db, plan_id)

    job = ProductionJob(
        plan_id=plan_id,
        target_type=target_type,
        target_id=target_id,
        stage=stage,
        status=JOB_QUEUED,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
    db.add(job)
    try:
        if commit:
            db.commit()
            db.refresh(job)
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
        if existing:
            return existing
        raise
    return job
```

Update `claim_next_job` to keep global worker behavior by default and add an opt-in plan filter for deterministic mock scheduler steps:

```python
def claim_next_job(
    db: Session,
    lease_id: str,
    lease_seconds: int = 300,
    plan_id: str | None = None,
) -> ProductionJob | None:
    skipped_ids: set[str] = set()
    while True:
        now = bj_now()
        query = (
            db.query(ProductionJob)
            .filter(ProductionJob.plan_id.in_(_active_plan_ids_query()))
            .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
            .filter((ProductionJob.retry_after.is_(None)) | (ProductionJob.retry_after <= now))
            .filter(ProductionJob.scheduled_at <= now)
        )
        if plan_id:
            query = query.filter(ProductionJob.plan_id == plan_id)
        if skipped_ids:
            query = query.filter(~ProductionJob.id.in_(skipped_ids))
        job = query.order_by(
            ProductionJob.priority.asc(), ProductionJob.scheduled_at.asc(), ProductionJob.created_at.asc()
        ).first()
        if not job:
            return None

        update_query = (
            db.query(ProductionJob)
            .filter(ProductionJob.id == job.id)
            .filter(ProductionJob.plan_id.in_(_active_plan_ids_query()))
            .filter(ProductionJob.status.in_([JOB_QUEUED, JOB_RETRY_WAIT]))
            .filter((ProductionJob.retry_after.is_(None)) | (ProductionJob.retry_after <= now))
            .filter(ProductionJob.scheduled_at <= now)
        )
        if plan_id:
            update_query = update_query.filter(ProductionJob.plan_id == plan_id)
        updated = update_query.update(
            {
                "status": JOB_LEASED,
                "lease_id": lease_id,
                "leased_until": now + timedelta(seconds=lease_seconds),
                "updated_at": now,
            },
            synchronize_session=False,
        )
        db.commit()
        if not updated:
            skipped_ids.add(job.id)
            continue

        db.refresh(job)
        return job
```

- [ ] **Step 4: Run queue tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_production_queue_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/production_queue_service.py server/tests/test_production_queue_service.py
git commit -m "feat: complete production queue jobs"
```

---

### Task 6: Build Mock Scale Scheduler Service

**Files:**
- Create: `server/app/services/mock_scale_scheduler_service.py`
- Modify: `server/app/services/production_review_service.py`
- Create: `server/tests/test_mock_scale_scheduler_service.py`

- [ ] **Step 1: Write mock scheduler tests**

Create `server/tests/test_mock_scale_scheduler_service.py`:

```python
from datetime import timedelta

from app.config import bj_now
from app.db_models import ProductionJob, ProductionPlan, ProductionSegment, VideoProductionRun
from app.services.mock_scale_scheduler_service import create_mock_scale_run, run_mock_scheduler_step
from app.services.production_queue_service import pause_plan_jobs, release_expired_leases, resume_plan_jobs
from app.services.video_production_run_types import MOCK_SERIES_SCALE


def test_create_mock_scale_run_builds_provider_free_plan(db):
    result = create_mock_scale_run(
        db,
        prompt="一个漫剧主角穿越多个城市寻找失踪的记忆。",
        title="记忆城市",
        genre="drama",
        target_duration_seconds=64,
        budget_limit=0,
    )

    run = result["run"]
    plan = db.query(ProductionPlan).filter_by(id=run.production_plan_id).one()
    segments = db.query(ProductionSegment).all()
    jobs = db.query(ProductionJob).all()

    assert run.run_type == MOCK_SERIES_SCALE
    assert run.status == "mock_scale_ready"
    assert plan.target_total_duration_seconds == 64
    assert len(segments) == 8
    assert len(jobs) == 8
    assert all(job.stage == "mock_segment" for job in jobs)
    assert result["steps"][0]["label"] == "已创建模拟长剧调度"


def test_mock_scheduler_step_completes_one_job_and_segment(db):
    result = create_mock_scale_run(
        db,
        prompt="测试长剧调度",
        title="调度测试",
        genre="drama",
        target_duration_seconds=16,
        budget_limit=0,
    )
    run = result["run"]

    step = run_mock_scheduler_step(db, run.id, lease_id="test-worker")

    assert step["completed"] == 1
    assert db.query(ProductionJob).filter_by(status="completed").count() == 1
    assert db.query(ProductionSegment).filter_by(status="completed").count() == 1


def test_mock_scheduler_resumes_expired_lease_without_provider_calls(db):
    result = create_mock_scale_run(
        db,
        prompt="测试过期租约恢复",
        title="租约恢复",
        genre="drama",
        target_duration_seconds=8,
        budget_limit=0,
    )
    run = result["run"]
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    job.status = "leased"
    job.lease_id = "stale-worker"
    job.leased_until = bj_now() - timedelta(seconds=5)
    db.commit()

    assert release_expired_leases(db) == 1
    step = run_mock_scheduler_step(db, run.id, lease_id="fresh-worker")

    assert step["completed"] == 1
    assert run.model_trace_json["mock_series_scale"]["provider_calls"] == 0


def test_mock_scheduler_completes_retry_wait_job_when_due(db):
    result = create_mock_scale_run(
        db,
        prompt="测试重试等待恢复",
        title="重试恢复",
        genre="drama",
        target_duration_seconds=8,
        budget_limit=0,
    )
    run = result["run"]
    job = db.query(ProductionJob).filter_by(plan_id=run.production_plan_id).one()
    job.status = "retry_wait"
    job.retry_after = bj_now() - timedelta(seconds=1)
    db.commit()

    step = run_mock_scheduler_step(db, run.id, lease_id="retry-worker")

    assert step["completed"] == 1
    assert db.query(ProductionJob).filter_by(status="completed").count() == 1


def test_mock_scheduler_respects_pause_and_resume(db):
    result = create_mock_scale_run(
        db,
        prompt="测试暂停恢复",
        title="暂停恢复",
        genre="drama",
        target_duration_seconds=8,
        budget_limit=0,
    )
    run = result["run"]

    assert pause_plan_jobs(db, run.production_plan_id, reason="operator_pause") == 1
    paused_step = run_mock_scheduler_step(db, run.id, lease_id="paused-worker")
    assert paused_step["completed"] == 0

    assert resume_plan_jobs(db, run.production_plan_id) == 1
    resumed_step = run_mock_scheduler_step(db, run.id, lease_id="resumed-worker")
    assert resumed_step["completed"] == 1


def test_mock_scheduler_step_refuses_real_run(db):
    result = create_mock_scale_run(
        db,
        prompt="测试长剧调度",
        title="调度测试",
        genre="drama",
        target_duration_seconds=8,
        budget_limit=0,
    )
    run = result["run"]
    run.run_type = "real_short_e2e"
    db.commit()

    try:
        run_mock_scheduler_step(db, run.id, lease_id="test-worker")
    except ValueError as exc:
        assert "real_short_e2e" in str(exc)
    else:
        raise AssertionError("Real runs must not enter mock scheduler")
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_mock_scale_scheduler_service.py -q
```

Expected: FAIL because the mock scheduler service does not exist.

- [ ] **Step 3: Create mock scheduler service**

Create `server/app/services/mock_scale_scheduler_service.py`:

```python
from math import ceil
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import (
    Episode,
    ProductionJob,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)
from app.services.production_observability import record_production_event
from app.services.production_queue_service import claim_next_job, enqueue_job, mark_job_completed
from app.services.production_status import PLAN_READY, SEGMENT_COMPLETED, SEGMENT_PLANNED
from app.services.video_production_run_types import MOCK_SERIES_SCALE, assert_run_type

MAX_MOCK_SEGMENT_SECONDS = 8
MAX_MOCK_SCALE_SECONDS = 86400


def _title(prompt: str, title: str | None) -> str:
    if title and title.strip():
        return title.strip()
    cleaned = " ".join(prompt.split())
    return cleaned[:24] or "模拟长剧"


def _segment_count(target_duration_seconds: int) -> int:
    return max(1, ceil(target_duration_seconds / MAX_MOCK_SEGMENT_SECONDS))


def _mock_storyboard_frame(index: int, duration: int) -> dict[str, Any]:
    return {
        "frame_id": f"mock-shot-{index:04d}",
        "scene_id": f"mock-scene-{((index - 1) // 12) + 1:03d}",
        "character_ids": ["mock-hero"],
        "image_prompt": f"统一角色锚定的模拟画面 {index}",
        "video_prompt": f"模拟镜头 {index}，保持角色、服装、光影一致",
        "narration": f"第 {index} 个模拟片段",
        "duration": duration,
        "reference_urls": ["mock://character-anchor-1", "mock://style-anchor-1"],
        "continuity_mode": "narrative_cut",
    }


def create_mock_scale_run(
    db: Session,
    *,
    prompt: str,
    title: str | None,
    genre: str,
    target_duration_seconds: int,
    budget_limit: float | None,
) -> dict[str, Any]:
    if target_duration_seconds < MAX_MOCK_SEGMENT_SECONDS or target_duration_seconds > MAX_MOCK_SCALE_SECONDS:
        raise ValueError("Mock scale duration must be between 8 and 86400 seconds")
    count = _segment_count(target_duration_seconds)
    duration = min(MAX_MOCK_SEGMENT_SECONDS, target_duration_seconds)
    series = Series(
        title=_title(prompt, title),
        logline=prompt,
        genre=genre,
        target_duration=target_duration_seconds,
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "visual_style": {"reference_urls": ["mock://style-anchor-1"]},
                "characters": [{"id": "mock-hero", "reference_urls": ["mock://character-anchor-1"]}],
            }
        },
    )
    db.add(series)
    db.flush()

    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title=f"{series.title} 调度样片",
        storyboard_json={
            "source": "mock_series_scale",
            "total_duration": target_duration_seconds,
            "frame_count": count,
            "frames": [_mock_storyboard_frame(index, duration) for index in range(1, count + 1)],
        },
        status="planning",
    )
    db.add(episode)
    db.flush()

    plan = ProductionPlan(
        series_id=series.id,
        status=PLAN_READY,
        target_total_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
        current_cost=0.0,
    )
    db.add(plan)
    db.flush()

    production_episode = ProductionEpisode(
        plan_id=plan.id,
        episode_id=episode.id,
        order_index=1,
        status=PLAN_READY,
        target_duration_seconds=target_duration_seconds,
    )
    db.add(production_episode)
    db.flush()

    scenes: dict[str, ProductionScene] = {}
    previous_segment = None
    for index, frame in enumerate(episode.storyboard_json["frames"], start=1):
        scene_id = frame["scene_id"]
        scene = scenes.get(scene_id)
        if scene is None:
            scene = ProductionScene(
                episode_plan_id=production_episode.id,
                scene_id=scene_id,
                order_index=len(scenes) + 1,
                status=PLAN_READY,
                location_summary=scene_id,
            )
            db.add(scene)
            db.flush()
            scenes[scene_id] = scene

        shot = ProductionShot(
            scene_plan_id=scene.id,
            shot_id=frame["frame_id"],
            order_index=index,
            status=PLAN_READY,
            character_ids=frame["character_ids"],
            action=frame["video_prompt"],
            emotion="steady",
            shot_type="medium",
            duration_seconds=frame["duration"],
        )
        db.add(shot)
        db.flush()

        segment = ProductionSegment(
            shot_plan_id=shot.id,
            previous_segment_id=previous_segment.id if previous_segment else None,
            segment_id=f"{frame['frame_id']}-seg-01",
            order_index=1,
            status=SEGMENT_PLANNED,
            duration_seconds=frame["duration"],
            continuity_mode="narrative_cut",
            version=1,
            image_prompt=frame["image_prompt"],
            video_prompt=frame["video_prompt"],
            narration=frame["narration"],
            reference_roles_json=[
                {"role": "character_anchor", "url": "mock://character-anchor-1", "priority": 1},
                {"role": "style_anchor", "url": "mock://style-anchor-1", "priority": 2},
            ],
        )
        db.add(segment)
        db.flush()
        previous_segment = segment
        enqueue_job(
            db,
            plan.id,
            "segment",
            segment.id,
            "mock_segment",
            f"mock:{plan.id}:{segment.id}:v1",
            priority=index,
            commit=False,
        )

    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        run_type=MOCK_SERIES_SCALE,
        status="mock_scale_ready",
        current_stage="mock_scheduler",
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        production_link_status="linked",
        storyboard_json=episode.storyboard_json,
        model_trace_json={"mock_series_scale": {"provider_calls": 0, "segment_count": count}},
    )
    db.add(run)
    db.flush()
    record_production_event(
        db,
        event_type="run_type.assigned",
        run_id=run.id,
        production_plan_id=plan.id,
        production_episode_id=production_episode.id,
        payload={"run_type": MOCK_SERIES_SCALE, "provider_calls": 0},
    )
    db.commit()
    db.refresh(run)

    return {
        "series": series,
        "episode": episode,
        "run": run,
        "steps": [
            {"key": "mock_plan", "label": "已创建模拟长剧调度", "status": "done", "segment_count": count},
            {"key": "mock_queue", "label": "已写入模拟队列", "status": "ready", "segment_count": count},
        ],
        "agency_trace_status": "mocked",
        "agency_trace": {},
    }


def run_mock_scheduler_step(db: Session, run_id: str, lease_id: str, batch_size: int = 1) -> dict[str, Any]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    assert_run_type(run, {MOCK_SERIES_SCALE})
    if not run.production_plan_id:
        raise ValueError("Mock scale run is missing production plan link")

    completed = 0
    job_ids: list[str] = []
    for _ in range(max(1, batch_size)):
        job = claim_next_job(db, lease_id=lease_id, lease_seconds=60, plan_id=run.production_plan_id)
        if not job:
            break
        segment = db.query(ProductionSegment).filter(ProductionSegment.id == job.target_id).first()
        if segment:
            segment.status = SEGMENT_COMPLETED
        mark_job_completed(db, job.id, provider_task_id=f"mock-provider-{job.id}")
        completed += 1
        job_ids.append(job.id)

    remaining = db.query(ProductionJob).filter(
        ProductionJob.plan_id == run.production_plan_id,
        ProductionJob.status.in_(["queued", "retry_wait", "leased", "running"]),
    ).count()
    if completed:
        run.status = "mock_scale_running" if remaining else "mock_scale_completed"
        run.current_stage = "mock_scheduler"
        db.commit()
    return {"completed": completed, "remaining": remaining, "job_ids": job_ids}
```

- [ ] **Step 4: Run mock scheduler tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_mock_scale_scheduler_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/mock_scale_scheduler_service.py server/tests/test_mock_scale_scheduler_service.py
git commit -m "feat: add mock long video scheduler"
```

---

### Task 7: Wire Mock Scale API And Run Type Guards

**Files:**
- Modify: `server/app/routers/video_production.py`
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/production_review_service.py`
- Create: `server/tests/test_video_production_mock_scale_api.py`
- Modify: `server/tests/test_production_bulk_review.py`

- [ ] **Step 1: Write mock scale API tests**

Create `server/tests/test_video_production_mock_scale_api.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import ProductionJob, VideoProductionRun
from app.main import app
from app.services.video_production_run_types import MOCK_SERIES_SCALE

client = TestClient(app)


def test_one_sentence_mock_scale_creates_mock_run(db):
    response = client.post("/api/video-production/one-sentence", json={
        "prompt": "一个长篇漫剧主角横跨多个城市调查记忆芯片。",
        "title": "记忆芯片",
        "genre": "drama",
        "target_duration_seconds": 64,
        "run_type": MOCK_SERIES_SCALE,
        "autostart_images": False,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["run"]["run_type"] == MOCK_SERIES_SCALE
    assert data["run"]["status"] == "mock_scale_ready"
    assert db.query(ProductionJob).count() == 8


def test_mock_worker_step_route_advances_queue(db):
    created = client.post("/api/video-production/one-sentence", json={
        "prompt": "模拟调度",
        "title": "模拟调度",
        "target_duration_seconds": 16,
        "run_type": MOCK_SERIES_SCALE,
        "autostart_images": False,
    }).json()
    run_id = created["run"]["id"]

    response = client.post(f"/api/video-production/runs/{run_id}/mock-worker-step", json={
        "lease_id": "api-worker",
        "batch_size": 2,
    })

    assert response.status_code == 200
    assert response.json()["result"]["completed"] == 2
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    assert run.status == "mock_scale_completed"


def test_one_sentence_mock_scale_accepts_more_than_240_minutes(db):
    response = client.post("/api/video-production/one-sentence", json={
        "prompt": "一个超长漫剧主角跨越多座城市完成长期任务。",
        "title": "超长调度",
        "target_duration_seconds": 28800,
        "run_type": MOCK_SERIES_SCALE,
        "autostart_images": False,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["run"]["run_type"] == MOCK_SERIES_SCALE
    assert db.query(ProductionJob).count() == 3600
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_mock_scale_api.py -q
```

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Add router request and route**

In `server/app/routers/video_production.py`, add:

```python
class MockWorkerStepRequest(BaseModel):
    lease_id: str = "manual-worker"
    batch_size: int = Field(1, ge=1, le=100)
```

Import:

```python
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError, to_http_detail
from app.services.mock_scale_scheduler_service import run_mock_scheduler_step
```

Add route after the sync routes:

```python
@router.post("/runs/{run_id}/mock-worker-step")
def mock_worker_step(
    run_id: str,
    body: MockWorkerStepRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        result = run_mock_scheduler_step(db, run_id, lease_id=body.lease_id, batch_size=body.batch_size)
    except ValueError as exc:
        raise HTTPException(
            400,
            to_http_detail(ProductionRepairableError(
                code=ProductionErrorCode.RUN_NOT_FOUND if "not found" in str(exc).lower() else ProductionErrorCode.INVALID_RUN_TYPE,
                message=str(exc),
                repair_action="检查运行类型和任务编号，只能对模拟长剧调度任务执行模拟 worker。",
                repair_route=f"/video-production/runs/{run_id}",
                retryable=False,
                affected_ids=[run_id],
            )),
        ) from exc
    return {"ok": True, "result": result}
```

- [ ] **Step 4: Guard real provider stages**

In `server/app/services/video_production_service.py`, import:

```python
from app.services.video_production_run_types import LEGACY_EPISODE_RUN, REAL_SHORT_E2E, assert_run_type
```

At the top of `start_image_stage`, after loading the run and before agency/provider resolution, add:

```python
    assert_run_type(run, {REAL_SHORT_E2E, LEGACY_EPISODE_RUN})
```

At the top of `start_video_stage`, add the same assertion.

At the top of `start_compose_stage`, add the same assertion.

This guard keeps existing legacy episode runs compatible while blocking mock scale runs from provider stages.

- [ ] **Step 5: Restrict bulk mock approvals**

In `server/app/services/production_review_service.py`, load the run once per asset group and add:

```python
from app.db_models import VideoProductionRun
from app.services.video_production_run_types import MOCK_SERIES_SCALE, get_run_type
```

Inside `apply_bulk_review_action`, after confirming the asset type is not `final_video`, add:

```python
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
        if run and get_run_type(run) == MOCK_SERIES_SCALE and asset.asset_type not in {"image", "video_segment"}:
            raise ValueError("Mock scale bulk review supports image and video segment assets only")
```

This keeps final video bulk approval rejected for every run type.

- [ ] **Step 6: Add review gate counts to review item payload**

In `server/app/routers/video_production.py`, when `review_items` is called with a `run_id`, include bounded counts for the three human gates:

```python
from sqlalchemy import func


def _gate_counts(db: Session, run_id: str) -> dict[str, int]:
    rows = (
        db.query(VideoProductionAsset.asset_type, func.count(VideoProductionAsset.id))
        .filter(VideoProductionAsset.run_id == run_id)
        .filter(VideoProductionAsset.status.in_(DEFAULT_REVIEW_ITEM_STATUSES))
        .filter(VideoProductionAsset.asset_type.in_(["image", "video_segment", "final_video"]))
        .group_by(VideoProductionAsset.asset_type)
        .all()
    )
    counts = {"image": 0, "video_segment": 0, "final_video": 0}
    counts.update({asset_type: count for asset_type, count in rows})
    return counts
```

Return:

```python
return {
    "ok": True,
    "items": [_asset_payload(item, db=db, run=runs_by_id.get(item.run_id)) for item in items],
    "gate_counts": _gate_counts(db, run_id) if run_id else {"image": 0, "video_segment": 0, "final_video": 0},
}
```

Add a backend test that creates pending `image`, `video_segment`, and `final_video` assets for one run and asserts `/api/video-production/review-items?run_id=...` returns all three gate counts.

- [ ] **Step 7: Run API and review tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_mock_scale_api.py tests/test_production_bulk_review.py tests/test_video_production_provider_config.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/app/routers/video_production.py server/app/services/video_production_service.py server/app/services/production_review_service.py server/tests/test_video_production_mock_scale_api.py server/tests/test_production_bulk_review.py
git commit -m "feat: wire mock scale production API"
```

---

### Task 8: Add Observability And Cost Safety Checks

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/production_run_service.py`
- Modify: `server/app/services/mock_scale_scheduler_service.py`
- Modify: `server/tests/test_video_production_observability_events.py`
- Create: `server/tests/test_video_production_cost_safety.py`

- [ ] **Step 1: Write cost safety tests**

Create `server/tests/test_video_production_cost_safety.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Series, VideoProductionRun
from app.main import app
from app.services.video_production_run_types import REAL_SHORT_E2E

client = TestClient(app)


def test_real_short_rejects_zero_budget_before_db_mutation(db):
    response = client.post("/api/video-production/one-sentence", json={
        "prompt": "一段一分钟的真实短片。",
        "title": "预算测试",
        "target_duration_seconds": 60,
        "run_type": REAL_SHORT_E2E,
        "budget_limit": 0,
        "autostart_images": False,
    })

    assert response.status_code in {400, 409}
    assert db.query(Series).count() == 0
    assert db.query(VideoProductionRun).count() == 0
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_cost_safety.py -q
```

Expected: FAIL if zero-budget real provider runs are accepted.

- [ ] **Step 3: Add preflight cost guard**

In `server/app/services/one_sentence_video_service.py`, before creating rows for `REAL_SHORT_E2E`, add:

```python
    if run_type == REAL_SHORT_E2E and budget_limit is not None and budget_limit <= 0:
        raise VideoProductionError("真实短片模式需要大于 0 的预算上限，避免误触发真实供应商调用。")
```

In `server/app/services/production_run_service.py`, add the same guard before reading or mutating rows:

```python
    if run_type == REAL_SHORT_E2E and budget_limit is not None and budget_limit <= 0:
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_EXCEEDED,
            message="真实短片模式需要大于 0 的预算上限。",
            cause="REAL_PROVIDER_BUDGET_NOT_CONFIRMED",
            repair_action="设置大于 0 的预算上限后重试",
            retryable=True,
        )
```

- [ ] **Step 4: Add required audit events**

In `server/app/services/video_production_service.py`, confirm these event types are recorded:

```python
"run_type.assigned"
"provider_config.image_stage.blocked"
"provider_config.video_stage.blocked"
"provider_config.compose.blocked"
"image_stage.submitted"
"image_stage.asset_registered"
"video_stage.submitted"
"video_stage.asset_registered"
"compose_stage.submitted"
"final_video.completed"
```

Add `run_type` to payloads where a `run` object is available:

```python
payload={"stage": "image_generation", "run_type": get_run_type(run)}
```

In `server/app/services/mock_scale_scheduler_service.py`, record each mock worker step:

```python
    record_production_event(
        db,
        event_type="mock_scheduler.step_completed",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        payload={"completed": completed, "remaining": remaining, "job_ids": job_ids},
    )
    db.commit()
```

- [ ] **Step 5: Run safety and observability tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_cost_safety.py tests/test_video_production_observability_events.py tests/test_mock_scale_scheduler_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/app/services/video_production_service.py server/app/services/production_run_service.py server/app/services/one_sentence_video_service.py server/app/services/mock_scale_scheduler_service.py server/tests/test_video_production_cost_safety.py server/tests/test_video_production_observability_events.py server/tests/test_mock_scale_scheduler_service.py
git commit -m "feat: add video production safety observability"
```

---

### Task 9: Update Frontend API Client

**Files:**
- Modify: `web/src/api/videoProduction.js`
- Create: `web/src/__tests__/video-production-run-type-api.test.js`

- [ ] **Step 1: Write API client tests**

Create `web/src/__tests__/video-production-run-type-api.test.js`:

```javascript
import { describe, expect, it, vi } from 'vitest'
import client from '../api/client.js'
import {
  createOneSentenceVideo,
  getRunReadiness,
  runMockSchedulerStep,
  startEpisodeProduction,
} from '../api/videoProduction.js'

vi.mock('../api/client.js', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

describe('video production run type api', () => {
  it('passes run_type to one sentence creation', () => {
    createOneSentenceVideo({
      prompt: '测试',
      title: '标题',
      genre: 'drama',
      target_duration_seconds: 60,
      budget_limit: 10,
      autostart_images: true,
      run_type: 'real_short_e2e',
    })

    expect(client.post).toHaveBeenCalledWith('/video-production/one-sentence', {
      prompt: '测试',
      title: '标题',
      genre: 'drama',
      target_duration_seconds: 60,
      budget_limit: 10,
      autostart_images: true,
      run_type: 'real_short_e2e',
    })
  })

  it('passes run_type to linked episode start', () => {
    startEpisodeProduction({
      series_id: 'series-1',
      episode_id: 'episode-1',
      target_duration_seconds: 60,
      budget_limit: 10,
      autostart_images: false,
      run_type: 'real_short_e2e',
    })

    expect(client.post).toHaveBeenCalledWith('/video-production/runs/start', {
      series_id: 'series-1',
      episode_id: 'episode-1',
      target_duration_seconds: 60,
      budget_limit: 10,
      autostart_images: false,
      run_type: 'real_short_e2e',
    })
  })

  it('reads readiness and runs mock worker step', () => {
    getRunReadiness('run-1')
    runMockSchedulerStep('run-1', { lease_id: 'ui-worker', batch_size: 5 })

    expect(client.get).toHaveBeenCalledWith('/video-production/runs/run-1/readiness')
    expect(client.post).toHaveBeenCalledWith('/video-production/runs/run-1/mock-worker-step', {
      lease_id: 'ui-worker',
      batch_size: 5,
    })
  })
})
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/video-production-run-type-api.test.js
```

Expected: FAIL because the API functions do not exist or do not pass `run_type`.

- [ ] **Step 3: Modify API client**

In `web/src/api/videoProduction.js`, add `run_type` to both creation functions:

```javascript
export function startEpisodeProduction({
  series_id,
  episode_id,
  target_duration_seconds,
  budget_limit,
  autostart_images = true,
  run_type = 'real_short_e2e',
}) {
  return client.post('/video-production/runs/start', {
    series_id,
    episode_id,
    target_duration_seconds,
    budget_limit,
    autostart_images,
    run_type,
  })
}

export function createOneSentenceVideo({
  prompt,
  title,
  genre,
  target_duration_seconds = 60,
  budget_limit,
  autostart_images = true,
  run_type = 'real_short_e2e',
}) {
  return client.post('/video-production/one-sentence', {
    prompt,
    title,
    genre,
    target_duration_seconds,
    budget_limit,
    autostart_images,
    run_type,
  })
}
```

Add new functions:

```javascript
export function getRunReadiness(runId) {
  return client.get(`/video-production/runs/${runId}/readiness`)
}

export function runMockSchedulerStep(runId, payload = {}) {
  return client.post(`/video-production/runs/${runId}/mock-worker-step`, {
    lease_id: payload.lease_id || 'ui-worker',
    batch_size: payload.batch_size || 1,
  })
}
```

- [ ] **Step 4: Run API tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/video-production-run-type-api.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add web/src/api/videoProduction.js web/src/__tests__/video-production-run-type-api.test.js
git commit -m "feat: add video production run type client"
```

---

### Task 10: Rebuild One-Sentence Page As Two-Mode Chinese Control

**Files:**
- Modify: `web/src/views/OneSentenceVideoPage.vue`
- Modify: `web/src/__tests__/one-sentence-video-page.test.js`

- [ ] **Step 1: Add frontend tests for mode and copy**

Update existing imports and mocks in `web/src/__tests__/one-sentence-video-page.test.js`; do not append duplicate `describe`, `mount`, or `vi.mock` declarations if the file already has them. Add these cases inside the existing one-sentence page suite:

```javascript
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import OneSentenceVideoPage from '../views/OneSentenceVideoPage.vue'
import * as api from '../api/videoProduction.js'

vi.mock('../api/videoProduction.js', async () => {
  const actual = await vi.importActual('../api/videoProduction.js')
  return {
    ...actual,
    createOneSentenceVideo: vi.fn(),
    getVideoProductionRun: vi.fn(),
  }
})

function wrapper() {
  return mount(OneSentenceVideoPage, {
    global: {
      mocks: {
        $router: { push: vi.fn() },
      },
    },
  })
}

describe('one sentence video page run modes', () => {
  it('renders Chinese copy without mojibake markers', () => {
    const w = wrapper()

    expect(w.text()).toContain('一句话成片')
    expect(w.text()).toContain('真实短片')
    expect(w.text()).toContain('模拟长剧调度')
    expect(w.text()).not.toContain('鐪')
    expect(w.text()).not.toContain('瀹')
  })

  it('submits real short run type', async () => {
    api.createOneSentenceVideo.mockResolvedValue({
      data: {
        route: '/video-production/run-1',
        run: { id: 'run-1', status: 'storyboard_ready', run_type: 'real_short_e2e' },
        steps: [],
      },
    })
    const w = wrapper()
    await w.find('[data-test="one-sentence-prompt"]').setValue('一个一分钟的救援短片')
    await w.find('[data-test="submit-one-sentence"]').trigger('click')

    expect(api.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      run_type: 'real_short_e2e',
      target_duration_seconds: 60,
    }))
  })

  it('switches to mock scale mode and allows long duration', async () => {
    api.createOneSentenceVideo.mockResolvedValue({
      data: {
        route: '/video-production/run-2',
        run: { id: 'run-2', status: 'mock_scale_ready', run_type: 'mock_series_scale' },
        steps: [],
      },
    })
    const w = wrapper()
    await w.find('[data-test="mode-mock-series-scale"]').trigger('click')
    await w.find('[data-test="target-duration"]').setValue(28800)
    await w.find('[data-test="one-sentence-prompt"]').setValue('一个八小时漫剧调度测试')
    await w.find('[data-test="submit-one-sentence"]').trigger('click')

    expect(api.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      run_type: 'mock_series_scale',
      target_duration_seconds: 28800,
    }))
  })
})
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/one-sentence-video-page.test.js
```

Expected: FAIL until the page copy, data-test hooks, and run type submit logic are updated.

- [ ] **Step 3: Update page state**

In `web/src/views/OneSentenceVideoPage.vue`, set form state:

```javascript
const form = reactive({
  prompt: '',
  title: '',
  genre: 'drama',
  target_duration_seconds: 60,
  budget_limit: 10,
  autostart_images: true,
  run_type: 'real_short_e2e',
})

const runModes = [
  { key: 'real_short_e2e', label: '真实短片', description: '调用真实模型，60-90 秒，必须经过人工审查闸门。' },
  { key: 'mock_series_scale', label: '模拟长剧调度', description: '不调用真实模型，默认 240 分钟，并支持至少 480 分钟的调度稳定性验证。' },
]
```

Add a mode switch function:

```javascript
function selectRunMode(mode) {
  form.run_type = mode
  if (mode === 'real_short_e2e') {
    form.target_duration_seconds = Math.min(90, Math.max(60, Number(form.target_duration_seconds) || 60))
    form.autostart_images = true
  } else {
    form.target_duration_seconds = Math.max(14400, Number(form.target_duration_seconds) || 14400)
    form.autostart_images = false
  }
}
```

Update submit payload:

```javascript
    const { data } = await createOneSentenceVideo({
      prompt: form.prompt,
      title: form.title || undefined,
      genre: form.genre,
      target_duration_seconds: form.target_duration_seconds,
      budget_limit: form.run_type === 'real_short_e2e' ? form.budget_limit : 0,
      autostart_images: form.run_type === 'real_short_e2e' ? form.autostart_images : false,
      run_type: form.run_type,
    })
```

- [ ] **Step 4: Replace visible copy**

Replace all mojibake and English visible strings in the touched template area with Chinese equivalents:

```vue
<h1 class="text-2xl font-bold">一句话成片</h1>
<p class="mt-1 text-sm text-slate-400">
  输入故事核心后，系统会创建系列、锁定基础风格、生成分镜，并启动可审查的生产流程。
</p>
```

Use these labels in the step list:

```javascript
const fallbackSteps = [
  { key: 'prompt', label: '已接收故事', status: 'waiting' },
  { key: 'series', label: '已创建系列和剧集', status: 'waiting' },
  { key: 'style_lock', label: '已锁定基础风格', status: 'waiting' },
  { key: 'storyboard', label: '已生成分镜', status: 'waiting' },
  { key: 'production_plan', label: '已关联生产计划', status: 'waiting' },
  { key: 'image_generation', label: '画面生成', status: 'waiting' },
  { key: 'image_review', label: '图像人工审查', status: 'waiting' },
  { key: 'video_generation', label: '视频片段生成', status: 'waiting' },
  { key: 'video_review', label: '视频片段人工审查', status: 'waiting' },
  { key: 'compose', label: '最终合成', status: 'waiting' },
  { key: 'final_review', label: '最终人工审查', status: 'waiting' },
  { key: 'completed', label: '成片完成', status: 'waiting' },
]
```

Add data-test hooks:

```vue
<textarea data-test="one-sentence-prompt" ... />
<input data-test="target-duration" ... />
<button data-test="mode-real-short" ...>真实短片</button>
<button data-test="mode-mock-series-scale" ...>模拟长剧调度</button>
<button data-test="submit-one-sentence" ...>生成并启动生产</button>
```

- [ ] **Step 5: Run page tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/one-sentence-video-page.test.js src/__tests__/video-production-run-type-api.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/views/OneSentenceVideoPage.vue web/src/__tests__/one-sentence-video-page.test.js
git commit -m "feat: add one sentence production modes"
```

---

### Task 11: Upgrade Monitor And Review Center Visibility

**Files:**
- Modify: `web/src/views/VideoProductionMonitorPage.vue`
- Modify: `web/src/views/AIVideoReviewPage.vue`
- Modify: `web/src/__tests__/video-production-monitor-page.test.js`
- Modify: `web/src/__tests__/ai-video-review-page.test.js`

- [ ] **Step 1: Add monitor tests**

Update existing imports and mocks in `web/src/__tests__/video-production-monitor-page.test.js`; do not append duplicate `describe`, `mount`, or `vi.mock` declarations if the file already has them. Add this case inside the existing monitor suite:

```javascript
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VideoProductionMonitorPage from '../views/VideoProductionMonitorPage.vue'
import * as api from '../api/videoProduction.js'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { runId: 'run-1' } }),
}))

vi.mock('../api/videoProduction.js', async () => {
  const actual = await vi.importActual('../api/videoProduction.js')
  return {
    ...actual,
    getVideoProductionRun: vi.fn(),
    getRunReadiness: vi.fn(),
    getRunProductionTree: vi.fn(),
    getRunCosts: vi.fn(),
    getSegmentDetail: vi.fn(),
  }
})

describe('video production monitor run type visibility', () => {
  it('shows run type and readiness action in Chinese', async () => {
    api.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'image_review_pending', current_stage: 'image_review', run_type: 'real_short_e2e' },
        assets: [],
      },
    })
    api.getRunReadiness.mockResolvedValue({
      data: {
        ok: true,
        readiness: {
          run_type: 'real_short_e2e',
          needs_review: true,
          next_action: { key: 'open_review', label: '进入人工审查' },
          blocks: [{ code: 'IMAGE_REVIEW_REQUIRED', message: '图像资产需要人工审查后才能进入图生视频阶段。' }],
          asset_counts: {},
        },
      },
    })
    api.getRunProductionTree.mockResolvedValue({ data: { episodes: [], total_segments: 0 } })
    api.getRunCosts.mockResolvedValue({ data: { actual_cost: 0 } })

    const w = mount(VideoProductionMonitorPage, {
      global: { mocks: { $router: { push: vi.fn() } } },
    })
    await Promise.resolve()
    await Promise.resolve()

    expect(w.text()).toContain('真实短片')
    expect(w.text()).toContain('进入人工审查')
    expect(w.text()).toContain('图像资产需要人工审查')
  })
})
```

- [ ] **Step 2: Add review page tests**

Update existing imports and mocks in `web/src/__tests__/ai-video-review-page.test.js`; do not append duplicate `describe`, `mount`, or `vi.mock` declarations if the file already has them. Add these cases inside the existing review suite:

```javascript
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AIVideoReviewPage from '../views/AIVideoReviewPage.vue'
import * as api from '../api/videoProduction.js'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { run_id: 'run-1', asset_type: 'final_video' } }),
}))

vi.mock('../api/videoProduction.js', async () => {
  const actual = await vi.importActual('../api/videoProduction.js')
  return {
    ...actual,
    getVideoProductionRun: vi.fn(),
    listReviewItems: vi.fn(),
    reviewAsset: vi.fn(),
  }
})

describe('ai video review final gate', () => {
  it('shows final review as human-only and hides bulk approve for final video', async () => {
    api.getVideoProductionRun.mockResolvedValue({
      data: { ok: true, run: { id: 'run-1', status: 'final_review_pending', run_type: 'real_short_e2e' } },
    })
    api.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-1',
          run_id: 'run-1',
          frame_id: 'final',
          asset_type: 'final_video',
          stage: 'composition',
          status: 'review_pending',
          version: 1,
          url: 'final.mp4',
        }],
      },
    })

    const w = mount(AIVideoReviewPage)
    await Promise.resolve()
    await Promise.resolve()

    expect(w.text()).toContain('最终人工审查')
    expect(w.text()).toContain('终审通过并入库')
    expect(w.find('[data-test="bulk-approve"]').exists()).toBe(false)
  })

  it('renders gate tabs with queue counts and keeps active gate in the route', async () => {
    api.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        gate_counts: { image: 2, video_segment: 1, final_video: 1 },
        items: [],
      },
    })

    const w = mount(AIVideoReviewPage)
    await Promise.resolve()
    await Promise.resolve()

    expect(w.find('[data-test="gate-tab-image"]').text()).toContain('图像审查')
    expect(w.find('[data-test="gate-tab-video-segment"]').text()).toContain('视频片段审查')
    expect(w.find('[data-test="gate-tab-final-video"]').text()).toContain('最终审查')
  })

  it('hides bulk approve when selected queue contains any final video asset', async () => {
    api.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [
          { id: 'asset-image', asset_type: 'image', status: 'review_pending', frame_id: 'frame-1' },
          { id: 'asset-final', asset_type: 'final_video', status: 'review_pending', frame_id: 'final' },
        ],
      },
    })

    const w = mount(AIVideoReviewPage)
    await Promise.resolve()
    await Promise.resolve()

    expect(w.find('[data-test="bulk-approve"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 3: Run and confirm failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/video-production-monitor-page.test.js src/__tests__/ai-video-review-page.test.js
```

Expected: FAIL until monitor and review page are updated.

- [ ] **Step 4: Update monitor**

In `web/src/views/VideoProductionMonitorPage.vue`, import `getRunReadiness`:

```javascript
  getRunReadiness,
```

Add state:

```javascript
const readiness = ref(null)
```

During `load()`, fetch readiness with run and costs:

```javascript
    const [runResponse, costsResponse, readinessResponse] = await Promise.all([
      getVideoProductionRun(runId),
      getRunCosts(runId).catch(() => ({ data: null })),
      getRunReadiness(runId).catch(() => ({ data: null })),
    ])
    run.value = runResponse.data.run
    assets.value = runResponse.data.assets || []
    costs.value = costsResponse.data
    readiness.value = readinessResponse.data && readinessResponse.data.readiness ? readinessResponse.data.readiness : null
```

Add helpers:

```javascript
function runTypeLabel(value) {
  if (value === 'real_short_e2e') return '真实短片'
  if (value === 'mock_series_scale') return '模拟长剧调度'
  return '历史剧集生产'
}
```

Show this in the health strip:

```vue
<div>
  <div class="text-xs uppercase text-slate-500">运行类型</div>
  <div class="mt-1 text-sm text-slate-100">{{ runTypeLabel(run?.run_type) }}</div>
</div>
<div>
  <div class="text-xs uppercase text-slate-500">下一步</div>
  <div class="mt-1 text-sm text-slate-100">{{ readiness?.next_action?.label || '查看状态' }}</div>
</div>
```

Show readiness blocks under the timeline:

```vue
<section v-if="readiness?.blocks?.length" data-test="readiness-blocks" class="mb-4 rounded border border-amber-500/40 bg-amber-950/30 p-4">
  <div class="mb-2 text-sm font-semibold text-amber-200">当前闸门</div>
  <div v-for="block in readiness.blocks" :key="block.code" class="text-sm text-amber-100">
    {{ block.message }}
  </div>
</section>
```

- [ ] **Step 5: Update review center**

In `web/src/views/AIVideoReviewPage.vue`, replace English page title and actions with Chinese:

```vue
<h1 class="text-2xl font-bold text-slate-100">AI 视频人工审查</h1>
<p class="mt-1 text-sm text-slate-500">按阶段处理图像、视频片段和最终成片，后台不会越过人工闸门。</p>
```

Compute final mode:

```javascript
const isFinalReview = computed(() => selected.value && selected.value.asset_type === 'final_video')
const gateCounts = ref({ image: 0, video_segment: 0, final_video: 0 })
const activeGate = computed(() => route.query.asset_type || 'image')
const containsFinalVideo = computed(() => reviewItems.value.some((item) => item.asset_type === 'final_video'))
const canBulkApprove = computed(() => activeGate.value !== 'final_video' && !containsFinalVideo.value)
```

Add gate tabs above the queue. Each tab must show the gate label, count, selected state, and update the route query instead of relying on hidden backend filtering:

```vue
<nav class="mb-4 grid grid-cols-3 gap-2" aria-label="审查闸门">
  <button data-test="gate-tab-image" :aria-current="activeGate === 'image' ? 'page' : undefined">图像审查 {{ gateCounts.image || 0 }}</button>
  <button data-test="gate-tab-video-segment" :aria-current="activeGate === 'video_segment' ? 'page' : undefined">视频片段审查 {{ gateCounts.video_segment || 0 }}</button>
  <button data-test="gate-tab-final-video" :aria-current="activeGate === 'final_video' ? 'page' : undefined">最终审查 {{ gateCounts.final_video || 0 }}</button>
</nav>
```

Hide bulk approval when the active gate is final or the loaded queue contains any final video asset:

```vue
<button
  v-if="canBulkApprove"
  data-test="bulk-approve"
  ...
>
  批量通过
</button>
```

Change approve label:

```vue
{{ isFinalReview ? '终审通过并入库' : '通过当前版本' }}
```

Set list filter to keep gate-specific route parameters:

```javascript
const { data } = await listReviewItems({
  run_id: route.query.run_id || undefined,
  asset_type: route.query.asset_type || undefined,
  stage: route.query.stage || undefined,
  statuses: route.query.statuses || route.query.status || defaultReviewStatuses,
})
gateCounts.value = data.gate_counts || gateCounts.value
```

- [ ] **Step 6: Run frontend focused tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/video-production-monitor-page.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/one-sentence-video-page.test.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/views/VideoProductionMonitorPage.vue web/src/views/AIVideoReviewPage.vue web/src/__tests__/video-production-monitor-page.test.js web/src/__tests__/ai-video-review-page.test.js
git commit -m "feat: show production gates in UI"
```

---

### Task 12: Add Mocked E2E And Provider Smoke Command

**Files:**
- Modify: `server/tests/test_video_production_full_mocked_e2e.py`
- Create: `server/tests/test_video_production_real_short_mocked_e2e.py`
- Create: `server/scripts/smoke_seedance_short_video.py`
- Modify: `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`

- [ ] **Step 1: Write real short mocked E2E**

Create `server/tests/test_video_production_real_short_mocked_e2e.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import GeneratedVideo, VideoProductionAsset, VideoProductionRun
from app.main import app
from app.services.video_production_run_types import REAL_SHORT_E2E

client = TestClient(app)


async def _agency_pass(*args, **kwargs):
    return {"stage_status": "passed", "invocation_ids": ["agency-ok"], "invocations": []}


def test_real_short_requires_human_gates_until_final_library_writeback(db, monkeypatch):
    submitted = {"stage": None}

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        submitted["stage"] = "image"
        return {"ok": True, "stage_task_id": "image-task"}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        submitted["stage"] = "video"
        return {"ok": True, "stage_task_id": "video-task"}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        submitted["stage"] = "compose"
        return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id == "image-task":
            return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001-seg-01", "asset_type": "image", "url": "image.png"}]}
        if stage_task_id == "video-task":
            return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001-seg-01", "asset_type": "video_segment", "url": "segment.mp4"}]}
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "final", "asset_type": "final_video", "url": "final.mp4", "local_path": "output/final.mp4", "metadata": {"duration": 60}}]}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service._guard_provider_stage", _agency_pass)
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []})

    created = client.post("/api/video-production/one-sentence", json={
        "prompt": "一个一分钟救援短片，角色和光影保持一致。",
        "title": "救援短片",
        "target_duration_seconds": 60,
        "run_type": REAL_SHORT_E2E,
        "budget_limit": 10,
        "autostart_images": True,
    })
    assert created.status_code == 200
    run_id = created.json()["run"]["id"]

    assert client.post(f"/api/video-production/runs/{run_id}/sync-image-results").status_code == 200
    images = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="image").all()
    assert images
    assert client.post("/api/video-production/reviews/bulk-action", json={"asset_ids": [asset.id for asset in images], "action": "approve"}).status_code == 200

    assert client.post(f"/api/video-production/runs/{run_id}/start-videos").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-video-results").status_code == 200
    videos = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="video_segment").all()
    assert videos
    assert client.post("/api/video-production/reviews/bulk-action", json={"asset_ids": [asset.id for asset in videos], "action": "approve"}).status_code == 200

    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-compose-results").status_code == 200
    run = db.query(VideoProductionRun).filter_by(id=run_id).one()
    assert run.status == "final_review_pending"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 0

    final_asset = db.query(VideoProductionAsset).filter_by(run_id=run_id, asset_type="final_video").one()
    assert client.post(f"/api/video-production/assets/{final_asset.id}/review", json={"action": "approve", "comment": "终审通过"}).status_code == 200
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 1
```

- [ ] **Step 2: Add provider smoke script**

Create `server/scripts/smoke_seedance_short_video.py`:

```python
"""Opt-in smoke test for configured real providers.

This script intentionally does not run in pytest. It should be executed only when the operator has confirmed provider
keys, budget, and endpoint configuration.
"""

import argparse
import asyncio

from app.database import SessionLocal
from app.services.one_sentence_video_service import create_one_sentence_video
from app.services.video_production_run_types import REAL_SHORT_E2E


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--title", default="Seedance smoke")
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = await create_one_sentence_video(
            db,
            prompt=args.prompt,
            title=args.title,
            genre="smoke",
            target_duration_seconds=args.duration,
            budget_limit=args.budget,
            autostart_images=True,
            run_type=REAL_SHORT_E2E,
        )
        print({"run_id": result["run"].id, "route": f"/video-production/{result['run'].id}"})
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Add spec command references**

In `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`, under Developer Experience Requirements, add these exact commands:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_real_short_mocked_e2e.py tests/test_video_production_mock_scale_api.py -q

cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/one-sentence-video-page.test.js src/__tests__/video-production-monitor-page.test.js src/__tests__/ai-video-review-page.test.js

cd D:\devWorkspace\jsProjects\dy_auto\server
python scripts/smoke_seedance_short_video.py --prompt "一个一分钟救援短片，角色和光影保持一致。" --title "真实供应商烟测" --duration 60 --budget 10
```

- [ ] **Step 4: Run E2E tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_real_short_mocked_e2e.py tests/test_video_production_mock_scale_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/tests/test_video_production_real_short_mocked_e2e.py server/tests/test_video_production_full_mocked_e2e.py server/scripts/smoke_seedance_short_video.py docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md
git commit -m "test: cover real short production loop"
```

---

### Task 13: Final Verification

**Files:**
- All files changed by Tasks 1-12.

- [ ] **Step 1: Run backend focused suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest `
  tests/test_video_production_run_type.py `
  tests/test_video_production_readiness.py `
  tests/test_one_sentence_video_run_types.py `
  tests/test_video_production_final_gate.py `
  tests/test_production_queue_service.py `
  tests/test_mock_scale_scheduler_service.py `
  tests/test_video_production_mock_scale_api.py `
  tests/test_video_production_cost_safety.py `
  tests/test_video_production_real_short_mocked_e2e.py `
  tests/test_video_production_full_mocked_e2e.py `
  -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run `
  src/__tests__/video-production-run-type-api.test.js `
  src/__tests__/one-sentence-video-page.test.js `
  src/__tests__/video-production-monitor-page.test.js `
  src/__tests__/ai-video-review-page.test.js
```

Expected: PASS.

- [ ] **Step 3: Run migration check**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
alembic upgrade head
alembic downgrade 3c4d5e6f7081
alembic upgrade head
```

Expected: each command exits with code 0.

- [ ] **Step 4: Scan visible copy and plan artifacts**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
rg -n "鐪|瀹|妯|嫙|皟|绉|€||垮|湡|澶|煡|闃|涓" web/src/views/OneSentenceVideoPage.vue web/src/views/AIVideoReviewPage.vue web/src/views/VideoProductionMonitorPage.vue
$pattern = "T" + "BD|TO" + "DO|FIX" + "ME|PLACE" + "HOLDER|待" + "定|占" + "位"
rg -n $pattern docs/superpowers/plans/2026-05-31-video-production-real-loop-and-scale-scheduler.md
```

Expected: both commands return no matches.

- [ ] **Step 5: Run full regression slices**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_provider_config.py tests/test_video_production_regeneration.py tests/test_video_production_tree_api.py tests/test_image_creation_mocked_e2e.py -q

cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/image-creation-page.test.js src/__tests__/production-control-room-autopilot.test.js src/__tests__/agency-console-page.test.js
```

Expected: PASS. These protect Seedance/image workbench, production monitor, and expert console from accidental breakage.

- [ ] **Step 6: Final commit**

```powershell
git status --short
git add `
  server/app/db_models.py `
  server/alembic/versions/4d5e6f708192_add_video_production_run_type.py `
  server/app/services/video_production_run_types.py `
  server/app/services/video_production_readiness.py `
  server/app/services/production_errors.py `
  server/app/services/video_production_service.py `
  server/app/services/production_run_service.py `
  server/app/services/one_sentence_video_service.py `
  server/app/services/production_queue_service.py `
  server/app/services/mock_scale_scheduler_service.py `
  server/app/services/production_review_service.py `
  server/app/routers/video_production.py `
  server/tests/test_video_production_run_type.py `
  server/tests/test_video_production_readiness.py `
  server/tests/test_video_production_named_errors.py `
  server/tests/test_one_sentence_video_run_types.py `
  server/tests/test_video_production_final_gate.py `
  server/tests/test_production_queue_service.py `
  server/tests/test_mock_scale_scheduler_service.py `
  server/tests/test_video_production_mock_scale_api.py `
  server/tests/test_production_bulk_review.py `
  server/tests/test_video_production_cost_safety.py `
  server/tests/test_video_production_observability_events.py `
  server/tests/test_video_production_real_short_mocked_e2e.py `
  server/tests/test_video_production_full_mocked_e2e.py `
  server/scripts/smoke_seedance_short_video.py `
  web/src/api/videoProduction.js `
  web/src/views/OneSentenceVideoPage.vue `
  web/src/views/VideoProductionMonitorPage.vue `
  web/src/views/AIVideoReviewPage.vue `
  web/src/__tests__/video-production-run-type-api.test.js `
  web/src/__tests__/one-sentence-video-page.test.js `
  web/src/__tests__/video-production-monitor-page.test.js `
  web/src/__tests__/ai-video-review-page.test.js `
  docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md
git commit -m "feat: complete real video loop and scale scheduler"
```

## Self-Review

Spec coverage:

- Real one-click sample video: Tasks 3, 4, 8, and 12.
- Stage review gates: Tasks 2, 4, 7, 10, and 11.
- Long-form scheduling stability: Tasks 5, 6, 7, and 12.
- Explicit run type separation: Tasks 1, 3, 7, 9, 10, and 11.
- Operational observability: Tasks 2, 8, and 11.
- Developer experience commands: Task 12 and Task 13.
- No 3D expert console scope: preserved by file structure and task list.
- No real 240-minute provider execution: enforced by mock run type and provider stage guards.

Type consistency:

- `real_short_e2e`, `mock_series_scale`, and `legacy_episode_run` are defined once in `video_production_run_types.py`.
- Readiness payload always uses `run_type`, `next_action`, `blocks`, and `asset_counts`.
- Error payload always uses `code`, `error_code`, `message`, `cause`, `repair_action`, `repair_route`, `affected_ids`, and `retryable`.
- Mock scheduler uses existing `ProductionPlan`, `ProductionEpisode`, `ProductionScene`, `ProductionShot`, `ProductionSegment`, and `ProductionJob`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-31-video-production-real-loop-and-scale-scheduler.md`.

Execution options:

1. Skill-assisted execution: use `superpowers:subagent-driven-development` or `superpowers:executing-plans` when explicitly invoked and available.
2. Inline execution: execute the same task checklist in this session with review checkpoints.

Default for this repository state: inline execution is acceptable because the plan now owns exact files and the worktree is already dirty.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | Keep this phase focused on real short closure, review gates, and mock scale scheduler | Mechanical | Focus + completeness | Matches the user's latest boundary and avoids reopening 3D expert-console scope | Expand into 3D UI, publishing, or real 240-minute provider generation |
| 2 | CEO | Support 240-minute default plus at least 480-minute mock stress case | Taste | Completeness | Preserves "larger than 240 minutes" promise without spending provider credits or adding scheduler infrastructure | Cap all mock scheduling at 240 minutes |
| 3 | Engineering | Reject unknown `run_type` before DB mutation | Mechanical | Explicit over clever | Silent fallback to legacy can bypass duration, budget, and provider guards | Treat unknown run types as legacy |
| 4 | Engineering | Preserve `legacy_episode_run` only for existing episode-provider compatibility | Mechanical | Backward compatibility | Existing runs should not break, but new one-sentence provider entry must stay explicit | Allow legacy as a generic escape hatch |
| 5 | Engineering | Require mock queue lease, retry-wait, pause/resume, and provider-free tests | Mechanical | Completeness | The stated scheduler goal is stability, not only happy-path completion | Test only one completed mock job |
| 6 | Design | Add visible review gate tabs with counts and route sync | Mechanical | Hierarchy as service | Users must see which gate is blocking production without guessing from filters | Hidden query-param-only gate selection |
| 7 | Design | Hide bulk approval whenever final assets are in scope | Mechanical | Trust and safety | Final approval is the last human writeback gate and must never be bulk-approved accidentally | Hide only when `route.query.asset_type === "final_video"` |
| 8 | DX | Replace broad final `git add` with exact owned file list | Mechanical | Dirty-worktree safety | This repo has many unrelated changes; broad staging would mix scopes | `git add server/app server/tests web/src` |
| 9 | DX | Update existing frontend test mocks in place instead of blind append | Mechanical | Pragmatic | Duplicate Vitest imports/mocks can break hoisting and create false failures | Append full test boilerplate into existing files |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Autoplan | `/autoplan` | Full review pipeline | 1 | ISSUES ADDRESSED | Added restore point, decision audit trail, Codex independent findings, and plan corrections. |
| CEO Review | `/plan-ceo-review` | Scope & strategy | 2 | ISSUES ADDRESSED | Scope held while clarifying 240+ minute mock stress promise and execution handoff. |
| Codex Review | `codex exec` | Independent 2nd opinion | 1 | ISSUES ADDRESSED | Found 8 plan-level issues including P0 unknown run type bypass; all incorporated. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 3 | ISSUES ADDRESSED | Added run-type validation, action matrix, queue plan scoping, deferred enqueue commits, and scheduler stability tests. |
| Design Review | `/plan-design-review` | UI/UX gaps | 2 | ISSUES ADDRESSED | Added explicit review gate tabs, gate counts, safer final bulk approval behavior, states, responsive and a11y specs. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 2 | ISSUES ADDRESSED | Replaced broad staging with exact file list and clarified frontend test edit strategy. |

- **UNRESOLVED:** 0 implementation-blocking design, engineering, or DX decisions. Visual mockups were not generated because the local gstack designer binary is unavailable.
- **VERDICT:** CEO + ENG + DESIGN + DX reviewed through `/autoplan`. Ready for implementation execution; run visual QA and the eng test plan after implementation.
