# Agency Auto Repair Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the transparent “expert finding -> automatic repair -> re-review -> human gate” loop for AI video production, without allowing silent paid provider calls or automatic final approval.

**Architecture:** Reuse the existing `ProductionJob` queue instead of adding a new repair table. Store repair task snapshots in `ProductionJob.blocked_reason` and an in-memory/API projection from existing `AgencyExpertInvocation`, `ProductionAuditEvent`, and job fields; write durable repair detail into `AgencyExpertInvocation.output_summary_json.repair_tasks`, asset meta fields, and `ProductionAuditEvent.payload_json`. Route repair execution through existing style-lock, storyboard, image/video retry, provider sync, budget, and worker boundaries.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vitest, existing dy_auto production queue/services.

---

## Scope Guard

This plan implements the first version only:

- Included: structured repair task classification, `ProductionJob.stage = "agency_auto_repair"` jobs, auto-repair policy validation, visible repair summaries, manual action routes, aggregated long-video UI, re-review handoff, tests.
- Excluded: new `ProductionRepairTask` table, visual timeline editor, external multi-agent runtime, auto final approval, Douyin publishing, changing provider billing internals beyond using existing cost boundaries.
- Hard rule: automatic repair may fix deterministic structure, but it may only advance to the next review gate. It must never mark final assets as approved.

## Design Review Corrections

Design review result: the plan is implementable, but the frontend must not become another dense log surface. The UX standard for this feature is: users can answer four questions in under 10 seconds:

1. 系统发现了什么问题？
2. 系统正在自动补什么？
3. 这次自动补齐会不会继续花钱？
4. 哪些地方仍然必须我来确认？

Required corrections for implementation:

- **Information hierarchy:** repair information is a secondary strip inside existing production surfaces, not a new dominant page. The main flow remains series/style lock, review center, and production monitor.
- **Policy confirmation:** the auto-repair policy block must be compact, explicit, and action-bound. The primary start button copy must make authorization visible, for example `启动生产并应用返修策略`.
- **Cost trust:** estimated and spent repair cost must be shown beside repair counts when cost is non-zero. If the repair budget is `0` or disabled, show `仅记录建议，不自动付费返修`.
- **Manual action:** every `manual_required` item must render a concrete button-style action using `repair_action_label`; plain status text is not enough.
- **Long-video density:** production monitor defaults to aggregate chips by stage and status. Detailed repair rows stay in a drawer or collapsible panel opened by the user.
- **Language:** all user-facing labels must be Chinese. Provider/model/internal fields may appear only inside developer/debug affordances, not the default UI.
- **Visual restraint:** reuse existing dashboard density and table/list patterns. Avoid nested cards, hero-style blocks, decorative gradients, and large instructional copy.

## Engineering Review Corrections

Engineering review result: the plan is viable only after the following corrections are applied during implementation:

- **No `ProductionJob.payload_json`:** the current `ProductionJob` model has no `payload_json` column. Repair detail must live in `AgencyExpertInvocation.output_summary_json.repair_tasks` and `ProductionAuditEvent.payload_json`; `ProductionJob.blocked_reason` may contain only a short user-readable reason.
- **Caller-owned transactions:** new repair classifier/orchestrator helpers must not call `db.commit()` internally. They may `db.flush()` when they need ids. Existing entrypoints such as `finalize_invocation_and_audit`, API routes, and worker processing own commits.
- **Model-compatible tests:** `ProductionPlan` has no `title` column, and `Character` has no `avatar_url` column. Tests must construct these models only with existing fields.
- **Reference generation is async:** existing reference helpers are `generate_character_reference_images` and `generate_scene_reference_images`, both async. The repair executor must be async and the worker must `await` it.
- **Action result signature:** `ProductionActionResult.success()` takes `message` first and `data` second. Do not pass the result data as the first positional argument.
- **Repair job dedupe:** return an explicit `(job, created)` tuple from the enqueue helper instead of inferring dedupe from timestamps.

## CEO Review Corrections

CEO review result: the plan should hold scope, but it must add explicit trust guardrails so the automatic repair loop does not reintroduce opaque or unreadable output.

- **Chinese readability gate:** every user-facing field emitted by the repair loop must be readable Chinese, not mojibake. This applies to `reason`, `expected_result`, `repair_action_label`, `blocked_reason`, button labels, empty states, toast messages, and test fixtures.
- **Mojibake regression tests:** backend and frontend tests must fail if user-facing repair text contains common mojibake patterns such as `鍘`, `鑰`, `鎺`, `瑙`, `闇`, `鐢`, `琛`, `鈥`, `渆`, or `�`.
- **No generic expert filler:** if the expert output is empty, English, malformed, or only contains generic text such as `已记录审查发现`, the classifier must produce a manual-required item with a specific fallback reason: `专家审查结果缺少可执行结论，需要人工确认`.
- **Trust first:** the UI must show the original expert finding, the planned repair action, cost impact, and the next human gate in the same visible repair block. A repair task that cannot explain these four fields is not eligible for automatic execution.
- **Repair completion is not approval:** successful automatic repair must create `agency_repair_recheck_required`, set the repaired target metadata to `repair_recheck_pending`, and surface `待复审` in the UI. It must never mark any asset, stage, or final video as `approved`; only the existing review gate may do that.
- **Budget is cumulative:** paid automatic repair authorization is a run/plan-level repair budget, not a per-task limit. Before enqueueing a paid repair job, calculate previously reserved/spent repair cost plus costs reserved earlier in the current enqueue call; anything exceeding `auto_repair_policy.budget_limit` must become manual-required with reason `自动返修预算不足，需要人工确认是否继续付费返修`.
- **Provider cost boundary still applies:** the repair executor may not call a paid model through a shortcut path. Any paid reference/image/video repair must reuse the existing provider cost reservation and settlement path (`ProviderCostReservation`, provider stage task cost data, and `ProductionPlan.current_cost`). Check both boundaries: repair budget against repair-only reserved/spent estimates, and production plan budget against `ProductionPlan.current_cost + active_reserved_cost(...) + estimated_cost`. If either boundary is unavailable or exceeded, the task must be manual-required instead of auto-executed.
- **Scale-safe projections:** repair APIs and monitor projections must never scan all `ProductionAuditEvent` rows. Always filter by `production_plan_id`, `run_id`, or current-page `job_id` candidates before reading payloads. Add indexes for `ProductionJob(plan_id, stage, status)` and `ProductionJob(stage, created_at)` so long-video repair summaries stay bounded.
- **Executor must not commit:** automatic repair execution must not call `db.commit()` or `db.rollback()` internally. The worker/API entrypoint owns transaction commit/rollback so asset metadata, repair events, job status, and cost settlement succeed or fail as one unit. If an existing helper commits internally, do not call it from the executor; route the task to manual-required until a caller-owned transaction path exists.

## File Structure

### Backend

- Create `server/app/services/agency_repair_contracts.py`
  - Pydantic models and constants for `RepairTask`, `AutoRepairPolicy`, repair types, status labels, and manual action fields.
- Create `server/app/services/agency_repair_classifier.py`
  - Converts `AgencyExpertInvocation.output_summary_json` into safe structured repair tasks using fixed whitelists.
- Create `server/app/services/agency_repair_orchestrator.py`
  - Validates policy, deduplicates tasks, enqueues `ProductionJob` repair jobs, writes audit events.
- Create `server/app/services/agency_repair_executor.py`
  - Executes deterministic repair actions and records manual-required fallbacks.
- Modify `server/app/services/agency_persistence.py`
  - Runs the classifier after successful expert invocation persistence and stores `repair_tasks`.
- Modify `server/app/services/production_worker_service.py`
  - Dispatches `agency_auto_repair` jobs to the repair executor before normal provider execution.
- Modify `server/app/services/agency_console.py`
  - Adds `repair_summary` to the series agency console projection.
- Modify `server/app/services/production_tree_service.py`
  - Adds aggregated repair nodes to production tree output.
- Modify `server/app/routers/agency.py`
  - Adds `GET /api/agency/repair-tasks` and manual retry route for failed repair jobs.
- Modify `server/app/routers/video_production.py`
  - Accepts and persists `auto_repair_policy` snapshot for both `/runs/start` and `/one-sentence`.
- Add Alembic migration
  - Adds scale-safe repair query indexes on `production_jobs`.

### Frontend

- Modify `web/src/api/agency.js`
  - Adds repair task API helpers.
- Modify `web/src/api/videoProduction.js`
  - Sends `auto_repair_policy` with start payload.
- Modify `web/src/components/agency/AgencyDecisionLog.vue`
  - Displays repair task status, manual action, cost, and re-review status.
- Modify `web/src/views/SeriesDetailPage.vue`
  - Shows style-lock/asset repair progress and disables duplicate lock while repair is active.
- Modify `web/src/views/VideoProductionMonitorPage.vue`
  - Shows aggregated repair node and detail drawer.
- Modify `web/src/views/OneSentenceVideoPage.vue`
  - Adds automatic repair policy confirmation card before starting production.
- Create `web/src/components/agency/AutoRepairSummaryStrip.vue`
  - Reusable compact strip for repair totals, budget state, and manual-required counts.
- Create `web/src/components/agency/AutoRepairPolicyPanel.vue`
  - Reusable compact policy confirmation panel used by one-sentence production and future batch production entry points.

### Tests

- Create `server/tests/test_agency_repair_classifier.py`
- Create `server/tests/test_agency_repair_orchestrator.py`
- Create `server/tests/test_agency_repair_executor.py`
- Create `server/tests/test_agency_repair_api.py`
- Create `server/tests/test_agency_repair_query_scale.py`
- Create `server/tests/test_agency_repair_worker.py`
- Create `web/src/__tests__/agency-auto-repair-log.test.js`
- Create `web/src/__tests__/one-sentence-auto-repair-policy.test.js`
- Create `web/src/__tests__/video-production-repair-node.test.js`
- Create `web/src/__tests__/auto-repair-summary-strip.test.js`

---

### Task 1: Repair Contracts and Classifier

**Files:**
- Create: `server/app/services/agency_repair_contracts.py`
- Create: `server/app/services/agency_repair_classifier.py`
- Create: `server/tests/test_agency_repair_classifier.py`
- Modify: `server/app/services/agency_persistence.py`

- [ ] **Step 1: Write classifier tests**

Create `server/tests/test_agency_repair_classifier.py`:

```python
from app.services.agency_repair_classifier import classify_repair_tasks
from app.services.agency_repair_contracts import REPAIR_TYPE_MANUAL_ONLY


def test_structured_missing_character_reference_becomes_auto_task():
    output = {
        "decision": "有警告",
        "repair_tasks": [
            {
                "type": "missing_character_reference",
                "stage": "style_lock",
                "target_type": "character",
                "target_id": "char-1",
                "series_id": "series-1",
                "reason": "角色缺少侧面参考图",
                "expected_result": "生成并写回角色侧面参考图",
            }
        ],
    }

    result = classify_repair_tasks(output, stage="style_lock", series_id="series-1")

    assert result.repairable is True
    assert len(result.repair_tasks) == 1
    task = result.repair_tasks[0]
    assert task.type == "missing_character_reference"
    assert task.auto_execute is True
    assert task.manual_gate_after_repair is True
    assert task.repair_action_label == "去角色资产补参考图"
    assert task.repair_route == "/characters/char-1"
    assert task.affected_ids == ["char-1"]


def test_subjective_quality_issue_is_manual_only():
    output = {
        "decision": "阻断",
        "findings": ["角色不像，真人现实质感不足"],
        "required_changes": ["请人工确认是否重绘"],
    }

    result = classify_repair_tasks(output, stage="image_review", series_id="series-1")

    assert result.repairable is False
    assert result.manual_gate_required is True
    assert len(result.repair_tasks) == 1
    task = result.repair_tasks[0]
    assert task.type in REPAIR_TYPE_MANUAL_ONLY
    assert task.auto_execute is False
    assert task.repair_action_label == "去审查中心处理"
    assert task.repair_route == "/review-center"


def test_missing_target_never_auto_executes():
    output = {
        "repair_tasks": [
            {
                "type": "missing_scene_reference",
                "stage": "style_lock",
                "target_type": "scene",
                "target_id": "",
                "series_id": "series-1",
                "reason": "场景缺少参考图",
                "expected_result": "补齐场景参考图",
            }
        ]
    }

    result = classify_repair_tasks(output, stage="style_lock", series_id="series-1")

    assert result.repairable is False
    assert result.repair_tasks[0].auto_execute is False
    assert result.repair_tasks[0].status == "manual_required"


def test_unreadable_or_generic_finding_requires_manual_confirmation():
    output = {
        "decision": "warning",
        "findings": ["已记录审查发现", "鍘昏鑹茶祫浜цˉ鍙傝€冨浘"],
        "required_changes": [],
    }

    result = classify_repair_tasks(output, stage="style_lock", series_id="series-1")

    assert result.repairable is False
    assert result.manual_gate_required is True
    task = result.repair_tasks[0]
    assert task.auto_execute is False
    assert task.reason == "专家审查结果缺少可执行结论，需要人工确认"
    assert not any(token in task.reason for token in ["鍘", "鑰", "鎺", "瑙", "闇", "鐢", "琛", "鈥", "渆", "�"])
```

- [ ] **Step 2: Run classifier tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_agency_repair_classifier.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.agency_repair_classifier'`.

- [ ] **Step 3: Implement repair contracts**

Create `server/app/services/agency_repair_contracts.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


AUTO_REPAIR_STAGE = "agency_auto_repair"
MAX_AUTO_REPAIR_ROUNDS = 2

REPAIR_TYPE_AUTO_EXECUTABLE = {
    "missing_character_reference",
    "missing_scene_reference",
    "storyboard_missing_fields",
    "storyboard_missing_references",
    "image_generation_failed",
    "image_generation_timeout",
    "image_missing_approved_asset",
    "video_segment_failed",
    "video_segment_timeout",
    "compose_missing_approved_segments",
}

REPAIR_TYPE_MANUAL_ONLY = {
    "subjective_style_drift",
    "character_identity_not_convincing",
    "medical_or_health_compliance_risk",
    "realistic_quality_not_enough",
    "final_story_not_acceptable",
    "unsafe_or_policy_risk",
}

DEFAULT_AUTO_REPAIR_POLICY = {
    "enabled": False,
    "max_rounds": 2,
    "budget_limit": 0.0,
    "currency": "CNY",
    "allowed_stages": ["style_lock", "storyboard", "image_stage", "video_stage", "compose"],
    "allowed_types": [
        "missing_character_reference",
        "missing_scene_reference",
        "storyboard_missing_references",
        "image_generation_timeout",
        "video_segment_timeout",
    ],
    "requires_human_gate_after_repair": True,
}


class AutoRepairPolicy(BaseModel):
    enabled: bool = False
    max_rounds: int = Field(default=2, ge=0, le=MAX_AUTO_REPAIR_ROUNDS)
    budget_limit: float = Field(default=0.0, ge=0.0)
    currency: str = "CNY"
    allowed_stages: list[str] = Field(default_factory=list)
    allowed_types: list[str] = Field(default_factory=list)
    requires_human_gate_after_repair: bool = True


class RepairTask(BaseModel):
    type: str
    stage: str
    target_type: str
    target_id: str | None = None
    series_id: str
    episode_id: str | None = None
    asset_id: str | None = None
    priority: str = "normal"
    status: str = "suggested"
    auto_execute: bool = False
    requires_paid_provider: bool = False
    budget_authorized: bool = False
    estimated_cost: float = 0.0
    reason: str
    expected_result: str
    repair_action_label: str
    repair_route: str
    affected_ids: list[str] = Field(default_factory=list)
    manual_gate_after_repair: bool = True
    source_invocation_id: str | None = None
    round: int = 1


class RepairClassificationResult(BaseModel):
    repairable: bool
    manual_gate_required: bool
    blocked_reason: str | None = None
    repair_tasks: list[RepairTask] = Field(default_factory=list)


def action_for_task(task_type: str, target_type: str, target_id: str | None) -> tuple[str, str]:
    if task_type == "missing_character_reference":
        return "去角色资产补参考图", f"/characters/{target_id}" if target_id else "/characters"
    if task_type == "missing_scene_reference":
        return "去场景资产补参考图", f"/scenes/{target_id}" if target_id else "/scenes"
    if task_type.startswith("storyboard_"):
        return "去分镜脚本处理", "/series"
    if task_type.startswith("image_"):
        return "去审查中心处理", "/review-center"
    if task_type.startswith("video_") or task_type.startswith("compose_"):
        return "去生产监控处理", "/video-production"
    return "联系人工处理", "/"
```

- [ ] **Step 4: Implement classifier**

Create `server/app/services/agency_repair_classifier.py`:

```python
from __future__ import annotations

from typing import Any

from app.services.agency_repair_contracts import (
    REPAIR_TYPE_AUTO_EXECUTABLE,
    REPAIR_TYPE_MANUAL_ONLY,
    RepairClassificationResult,
    RepairTask,
    action_for_task,
)


def classify_repair_tasks(output_summary: dict[str, Any] | None, *, stage: str, series_id: str) -> RepairClassificationResult:
    output = output_summary or {}
    tasks: list[RepairTask] = []
    for raw in output.get("repair_tasks") or []:
        if not isinstance(raw, dict):
            continue
        task = _task_from_structured(raw, stage=stage, series_id=series_id)
        tasks.append(task)

    if not tasks:
        tasks.extend(_manual_tasks_from_findings(output, stage=stage, series_id=series_id))

    auto_tasks = [task for task in tasks if task.auto_execute]
    return RepairClassificationResult(
        repairable=bool(auto_tasks),
        manual_gate_required=bool(tasks),
        blocked_reason=None if auto_tasks else "需要人工确认或处理",
        repair_tasks=tasks,
    )


def _task_from_structured(raw: dict[str, Any], *, stage: str, series_id: str) -> RepairTask:
    task_type = str(raw.get("type") or "").strip()
    target_type = str(raw.get("target_type") or "").strip() or "unknown"
    target_id = str(raw.get("target_id") or "").strip() or None
    action_label, route = action_for_task(task_type, target_type, target_id)
    auto_allowed = task_type in REPAIR_TYPE_AUTO_EXECUTABLE and bool(target_id)
    return RepairTask(
        type=task_type if task_type else "manual_incomplete_repair_task",
        stage=str(raw.get("stage") or stage),
        target_type=target_type,
        target_id=target_id,
        series_id=str(raw.get("series_id") or series_id),
        episode_id=raw.get("episode_id"),
        asset_id=raw.get("asset_id"),
        priority=str(raw.get("priority") or "normal"),
        status="suggested" if auto_allowed else "manual_required",
        auto_execute=auto_allowed,
        requires_paid_provider=bool(raw.get("requires_paid_provider", task_type in {"missing_character_reference", "missing_scene_reference", "image_generation_failed", "image_generation_timeout", "video_segment_failed", "video_segment_timeout"})),
        budget_authorized=bool(raw.get("budget_authorized", False)),
        estimated_cost=float(raw.get("estimated_cost") or 0.0),
        reason=str(raw.get("reason") or "专家发现需要处理的结构性问题"),
        expected_result=str(raw.get("expected_result") or "完成对应生产资料补齐"),
        repair_action_label=str(raw.get("repair_action_label") or action_label),
        repair_route=str(raw.get("repair_route") or route),
        affected_ids=list(raw.get("affected_ids") or ([target_id] if target_id else [])),
        manual_gate_after_repair=bool(raw.get("manual_gate_after_repair", True)),
        source_invocation_id=raw.get("source_invocation_id"),
        round=int(raw.get("round") or 1),
    )


def _manual_tasks_from_findings(output: dict[str, Any], *, stage: str, series_id: str) -> list[RepairTask]:
    text = " ".join(str(item) for key in ("findings", "required_changes", "recommendations") for item in output.get(key, []) if item)
    if _looks_unreadable_or_generic(text):
        text = "专家审查结果缺少可执行结论，需要人工确认"
    lowered = text.lower()
    if "合规" in text or "医疗" in text or "控糖" in text:
        task_type = "medical_or_health_compliance_risk"
    elif "不像" in text or "走样" in text:
        task_type = "character_identity_not_convincing"
    elif "质感" in text or "realistic" in lowered:
        task_type = "realistic_quality_not_enough"
    elif text:
        task_type = "subjective_style_drift"
    else:
        return []
    action_label, route = action_for_task(task_type, "manual", None)
    return [
        RepairTask(
            type=task_type if task_type in REPAIR_TYPE_MANUAL_ONLY else "subjective_style_drift",
            stage=stage,
            target_type="manual",
            target_id=None,
            series_id=series_id,
            status="manual_required",
            auto_execute=False,
            reason=text or "专家发现需要人工确认的问题",
            expected_result="由人工确认处理方式",
            repair_action_label=action_label,
            repair_route=route,
            affected_ids=[],
        )
    ]


def _looks_unreadable_or_generic(text: str) -> bool:
    if not text.strip():
        return True
    mojibake_tokens = ("鍘", "鑰", "鎺", "瑙", "闇", "鐢", "琛", "鈥", "渆", "�")
    if any(token in text for token in mojibake_tokens):
        return True
    generic_phrases = ("已记录审查发现", "已记录异常结论", "等待下一步处理")
    return any(phrase in text for phrase in generic_phrases) and len(text.strip()) < 40
```

- [ ] **Step 5: Store repair tasks when invocations are persisted**

Modify the successful persistence path in `server/app/services/agency_persistence.py` after `AgencyExpertInvocation` is created and before commit:

```python
from app.services.agency_repair_classifier import classify_repair_tasks
```

Add:

```python
classification = classify_repair_tasks(
    invocation.output_summary_json or {},
    stage=invocation.stage,
    series_id=invocation.series_id,
)
output = dict(invocation.output_summary_json or {})
output["repairable"] = classification.repairable
output["manual_gate_required"] = classification.manual_gate_required
output["repair_tasks"] = [task.model_dump() for task in classification.repair_tasks]
invocation.output_summary_json = output
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd server
pytest tests/test_agency_repair_classifier.py tests/test_agency_persistence.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/agency_repair_contracts.py server/app/services/agency_repair_classifier.py server/app/services/agency_persistence.py server/tests/test_agency_repair_classifier.py
git commit -m "feat: classify agency repair tasks"
```

---

### Task 2: Repair Policy and Orchestrator

**Files:**
- Create: `server/app/services/agency_repair_orchestrator.py`
- Create: `server/tests/test_agency_repair_orchestrator.py`
- Modify: `server/app/routers/video_production.py`
- Modify: `server/app/services/one_sentence_video_service.py`

- [ ] **Step 1: Write orchestrator tests**

Create `server/tests/test_agency_repair_orchestrator.py`:

```python
from app.db_models import AgencyExpertInvocation, ProductionJob, ProductionPlan, Series
from app.services.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation
from app.services.production_status import JOB_QUEUED


def _series(db):
    series = Series(title="老李控糖", description="控糖系列")
    db.add(series)
    db.commit()
    db.refresh(series)
    return series


def _plan(db, series):
    plan = ProductionPlan(series_id=series.id, status="ready", budget_limit=5.0, current_cost=0.0)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _invocation(db, series, plan, task):
    row = AgencyExpertInvocation(
        idempotency_key=f"invocation:{task['type']}",
        series_id=series.id,
        production_plan_id=plan.id,
        stage=task["stage"],
        expert_id="style_lock_quality_reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={"repair_tasks": [task]},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_enabled_policy_enqueues_one_repair_job(db):
    series = _series(db)
    plan = _plan(db, series)
    task = {
        "type": "missing_character_reference",
        "stage": "style_lock",
        "target_type": "character",
        "target_id": "char-1",
        "series_id": series.id,
        "auto_execute": True,
        "requires_paid_provider": True,
        "estimated_cost": 0.2,
        "reason": "缺少角色参考图",
        "expected_result": "补齐角色参考图",
        "repair_action_label": "去角色资产补参考图",
        "repair_route": "/characters/char-1",
        "affected_ids": ["char-1"],
    }
    invocation = _invocation(db, series, plan, task)
    policy = {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 1.0,
        "currency": "CNY",
        "allowed_stages": ["style_lock"],
        "allowed_types": ["missing_character_reference"],
        "requires_human_gate_after_repair": True,
    }

    result = enqueue_repair_tasks_for_invocation(db, invocation, policy)

    assert result["created"] == 1
    job = db.query(ProductionJob).filter_by(stage="agency_auto_repair:missing_character_reference").one()
    assert job.status == JOB_QUEUED
    assert job.idempotency_key.startswith("repair:")
    assert job.target_type == "character"
    assert job.target_id == "char-1"


def test_disabled_policy_does_not_enqueue_paid_job(db):
    series = _series(db)
    plan = _plan(db, series)
    task = {
        "type": "missing_character_reference",
        "stage": "style_lock",
        "target_type": "character",
        "target_id": "char-1",
        "series_id": series.id,
        "auto_execute": True,
        "requires_paid_provider": True,
        "estimated_cost": 0.2,
        "reason": "缺少角色参考图",
        "expected_result": "补齐角色参考图",
        "repair_action_label": "去角色资产补参考图",
        "repair_route": "/characters/char-1",
        "affected_ids": ["char-1"],
    }
    invocation = _invocation(db, series, plan, task)

    result = enqueue_repair_tasks_for_invocation(db, invocation, {"enabled": False})

    assert result["created"] == 0
    assert result["manual_required"] == 1
    assert db.query(ProductionJob).count() == 0


def test_cumulative_budget_blocks_tasks_after_limit(db):
    series = _series(db)
    plan = _plan(db, series)
    task_a = {
        "type": "missing_character_reference",
        "stage": "style_lock",
        "target_type": "character",
        "target_id": "char-1",
        "series_id": series.id,
        "auto_execute": True,
        "requires_paid_provider": True,
        "estimated_cost": 0.6,
        "reason": "缺少角色正面参考图",
        "expected_result": "补齐角色正面参考图",
        "repair_action_label": "去角色资产补参考图",
        "repair_route": "/characters/char-1",
        "affected_ids": ["char-1"],
    }
    task_b = {**task_a, "target_id": "char-2", "reason": "缺少角色侧面参考图", "affected_ids": ["char-2"]}
    invocation = _invocation(db, series, plan, task_a)
    output = dict(invocation.output_summary_json)
    output["repair_tasks"] = [task_a, task_b]
    invocation.output_summary_json = output
    db.commit()

    result = enqueue_repair_tasks_for_invocation(db, invocation, {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 1.0,
        "currency": "CNY",
        "allowed_stages": ["style_lock"],
        "allowed_types": ["missing_character_reference"],
        "requires_human_gate_after_repair": True,
    })

    assert result["created"] == 1
    assert result["manual_required"] == 1
    assert db.query(ProductionJob).count() == 1


def test_provider_plan_budget_blocks_paid_repair(db):
    series = _series(db)
    plan = _plan(db, series)
    plan.current_cost = 4.95
    db.commit()
    task = {
        "type": "missing_character_reference",
        "stage": "style_lock",
        "target_type": "character",
        "target_id": "char-1",
        "series_id": series.id,
        "auto_execute": True,
        "requires_paid_provider": True,
        "estimated_cost": 0.2,
        "reason": "缺少角色参考图",
        "expected_result": "补齐角色参考图",
        "repair_action_label": "去角色资产补参考图",
        "repair_route": "/characters/char-1",
        "affected_ids": ["char-1"],
    }
    invocation = _invocation(db, series, plan, task)

    result = enqueue_repair_tasks_for_invocation(db, invocation, {
        "enabled": True,
        "max_rounds": 2,
        "budget_limit": 1.0,
        "currency": "CNY",
        "allowed_stages": ["style_lock"],
        "allowed_types": ["missing_character_reference"],
        "requires_human_gate_after_repair": True,
    })

    assert result["created"] == 0
    assert result["manual_required"] == 1
    assert db.query(ProductionJob).count() == 0
```

- [ ] **Step 2: Run orchestrator tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_agency_repair_orchestrator.py -q
```

Expected: fail with missing `agency_repair_orchestrator`.

- [ ] **Step 3: Implement orchestrator**

Create `server/app/services/agency_repair_orchestrator.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_models import AgencyExpertInvocation, ProductionAuditEvent, ProductionJob, ProductionPlan
from app.services.agency_repair_contracts import (
    AUTO_REPAIR_STAGE,
    MAX_AUTO_REPAIR_ROUNDS,
    AutoRepairPolicy,
    RepairTask,
)
from app.services.provider_cost_reservation_service import active_reserved_cost
from app.services.production_status import JOB_QUEUED


def enqueue_repair_tasks_for_invocation(
    db: Session,
    invocation: AgencyExpertInvocation,
    policy_snapshot: dict[str, Any] | None,
) -> dict[str, int | float]:
    policy = AutoRepairPolicy.model_validate(policy_snapshot or {})
    output = invocation.output_summary_json or {}
    tasks = [RepairTask.model_validate(item) for item in output.get("repair_tasks") or [] if isinstance(item, dict)]
    result = {"created": 0, "deduped": 0, "manual_required": 0, "budget_reserved": 0.0}
    repair_budget_used = _repair_budget_used(db, invocation)
    reserved_this_call = 0.0
    for task in tasks:
        task.source_invocation_id = invocation.id
        allowed, reason = _can_auto_execute(db, invocation, task, policy, repair_budget_used + reserved_this_call)
        if not allowed:
            _record_manual_required(db, invocation, task, reason)
            result["manual_required"] += 1
            continue
        _job, created = _enqueue_repair_job(db, invocation, task)
        result["created" if created else "deduped"] += 1
        if created and task.requires_paid_provider:
            reserved_this_call += task.estimated_cost
            result["budget_reserved"] = round(result["budget_reserved"] + task.estimated_cost, 4)
    return result


def _can_auto_execute(db: Session, invocation: AgencyExpertInvocation, task: RepairTask, policy: AutoRepairPolicy, repair_budget_used: float) -> tuple[bool, str]:
    if not task.auto_execute:
        return False, "该问题需要人工处理"
    if not policy.enabled:
        return False, "自动返修策略未启用"
    if task.stage not in set(policy.allowed_stages):
        return False, "当前阶段未授权自动返修"
    if task.type not in set(policy.allowed_types):
        return False, "当前返修类型未授权自动执行"
    if task.round > min(policy.max_rounds, MAX_AUTO_REPAIR_ROUNDS):
        return False, "自动返修轮数已达上限"
    if task.requires_paid_provider and repair_budget_used + task.estimated_cost > policy.budget_limit:
        return False, "自动返修预算不足，需要人工确认是否继续付费返修"
    if task.requires_paid_provider and not _provider_budget_available(db, invocation.production_plan_id, task.estimated_cost):
        return False, "生产预算不足，需要人工确认是否继续付费返修"
    if not task.target_id:
        return False, "无法定位需要返修的对象"
    return True, ""


def _repair_budget_used(db: Session, invocation: AgencyExpertInvocation) -> float:
    rows = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.event_type == "agency_repair_task_created")
        .filter(ProductionAuditEvent.production_plan_id == invocation.production_plan_id)
        .all()
    )
    total = 0.0
    for row in rows:
        if invocation.run_id and row.run_id and row.run_id != invocation.run_id:
            continue
        task = ((row.payload_json or {}).get("repair_task") or {})
        if task.get("requires_paid_provider"):
            total += float(task.get("estimated_cost") or 0.0)
    return total


def _provider_budget_available(db: Session, plan_id: str | None, estimated_cost: float) -> bool:
    if not plan_id:
        return False
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).first()
    if not plan or plan.budget_limit is None:
        return False
    current = float(plan.current_cost or 0.0)
    reserved = active_reserved_cost(db, plan_id)
    return current + reserved + float(estimated_cost or 0.0) <= float(plan.budget_limit)


def _enqueue_repair_job(db: Session, invocation: AgencyExpertInvocation, task: RepairTask) -> tuple[ProductionJob, bool]:
    idempotency_key = _idempotency_key(invocation, task)
    existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
    if existing:
        return existing, False
    job = ProductionJob(
        plan_id=invocation.production_plan_id,
        target_type=task.target_type,
        target_id=task.target_id or invocation.series_id,
        stage=f"{AUTO_REPAIR_STAGE}:{task.type}",
        status=JOB_QUEUED,
        priority=10 if task.priority == "high" else 50,
        max_attempts=2,
        idempotency_key=idempotency_key,
        blocked_reason=task.reason[:120],
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(ProductionJob).filter(ProductionJob.idempotency_key == idempotency_key).first()
        if existing:
            return existing, False
        raise
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload_json={
            "invocation_id": invocation.id,
            "repair_task": task.model_dump(),
            "job_id": job.id,
        },
    ))
    return job, True


def _record_manual_required(db: Session, invocation: AgencyExpertInvocation, task: RepairTask, reason: str) -> None:
    db.add(ProductionAuditEvent(
        event_type="agency_repair_manual_required",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload_json={
            "invocation_id": invocation.id,
            "reason": reason,
            "repair_task": task.model_dump(),
            "repair_action_label": task.repair_action_label or "联系人工处理",
            "repair_route": task.repair_route or "/",
            "affected_ids": task.affected_ids,
        },
    ))


def _idempotency_key(invocation: AgencyExpertInvocation, task: RepairTask) -> str:
    target = task.target_id or "missing-target"
    return f"repair:{invocation.production_plan_id}:{task.stage}:{task.type}:{target}:{invocation.id}:{task.round}"
```

- [ ] **Step 4: Persist policy snapshot from production start**

In `server/app/routers/video_production.py`, extend both production start request models with:

```python
auto_repair_policy: dict | None = None
```

When calling `start_episode_production(...)` and `create_one_sentence_video(...)`, pass:

```python
auto_repair_policy=body.auto_repair_policy,
```

Where `VideoProductionRun.model_trace_json` is initialized or updated for `/api/video-production/runs/start` and `/api/video-production/one-sentence`, merge:

```python
trace = dict(run.model_trace_json or {})
trace["auto_repair_policy"] = body.auto_repair_policy or {
    "enabled": False,
    "max_rounds": 2,
    "budget_limit": 0.0,
    "currency": "CNY",
    "allowed_stages": [],
    "allowed_types": [],
    "requires_human_gate_after_repair": True,
}
run.model_trace_json = trace
```

If the snapshot is persisted inside service helpers such as `start_episode_production` or `create_one_sentence_video`, those helpers must accept `auto_repair_policy: dict | None = None` and write the snapshot before their existing caller-owned commit.

- [ ] **Step 5: Invoke orchestrator after persistence**

In `server/app/services/agency_persistence.py`, after repair tasks are added to `output_summary_json`, call:

```python
from app.db_models import VideoProductionRun
from app.services.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation

policy_snapshot = {}
if invocation.run_id:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == invocation.run_id).first()
    policy_snapshot = (run.model_trace_json or {}).get("auto_repair_policy") if run else {}
enqueue_repair_tasks_for_invocation(db, invocation, policy_snapshot or {})
```

Keep this call after the invocation is flushed so it has an `id`. If the existing persistence helper commits internally, place it before the final commit and do not add a second hidden commit.

- [ ] **Step 6: Run tests**

Run:

```powershell
cd server
pytest tests/test_agency_repair_orchestrator.py tests/test_video_production_start_flow_contract.py tests/test_agency_persistence.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/agency_repair_orchestrator.py server/app/routers/video_production.py server/app/services/one_sentence_video_service.py server/app/services/agency_persistence.py server/tests/test_agency_repair_orchestrator.py
git commit -m "feat: enqueue authorized agency repair jobs"
```

---

### Task 3: Repair Executor and Worker Dispatch

**Files:**
- Create: `server/app/services/agency_repair_executor.py`
- Create: `server/tests/test_agency_repair_executor.py`
- Create: `server/tests/test_agency_repair_worker.py`
- Modify: `server/app/services/production_worker_service.py`

- [ ] **Step 1: Write executor tests**

Create `server/tests/test_agency_repair_executor.py`:

```python
import pytest

from app.db_models import Character, ProductionAuditEvent, ProductionJob, ProductionPlan, Series
from app.services.agency_repair_executor import execute_repair_job
from app.services.production_status import JOB_BLOCKED, JOB_COMPLETED


@pytest.mark.asyncio
async def test_missing_character_reference_updates_progress(db, monkeypatch):
    series = Series(title="老李控糖")
    character = Character(name="老李")
    series.characters.append(character)
    db.add(series)
    db.commit()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id=character.id,
        stage="agency_auto_repair:missing_character_reference",
        idempotency_key="repair:test",
    )
    db.add(job)
    db.commit()

    async def fake_generate_character_reference_assets(db, character_id):
        return {"ok": True, "urls": ["http://asset.local/char-front.png"]}

    monkeypatch.setattr(
        "app.services.agency_repair_executor.generate_character_reference_assets",
        fake_generate_character_reference_assets,
    )

    result = await execute_repair_job(db, job)

    assert result.status == "success"
    refreshed = db.query(Character).filter_by(id=character.id).one()
    assert refreshed.meta_json["reference_generation"]["status"] == "completed"
    assert refreshed.meta_json["repair_review_gate"]["status"] == "repair_recheck_pending"
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_completed").count() == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").count() == 1


@pytest.mark.asyncio
async def test_unknown_repair_type_blocks_with_manual_action(db):
    series = Series(title="老李控糖")
    db.add(series)
    db.commit()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="series",
        target_id=series.id,
        stage="agency_auto_repair:unsafe_or_policy_risk",
        idempotency_key="repair:manual",
    )
    db.add(job)
    db.commit()

    result = await execute_repair_job(db, job)

    assert result.status == "blocked"
    assert result.repair_action == "去审查中心处理"
    assert result.repair_route == "/review-center"


@pytest.mark.asyncio
async def test_execute_repair_job_does_not_commit_internally(db, monkeypatch):
    series = Series(title="老李控糖")
    character = Character(name="老李")
    series.characters.append(character)
    db.add(series)
    db.commit()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id=character.id,
        stage="agency_auto_repair:missing_character_reference",
        idempotency_key="repair:no-hidden-commit",
    )
    db.add(job)
    db.commit()

    async def fake_generate_character_reference_assets(db, character_id):
        return {"ok": True, "urls": ["http://asset.local/char-front.png"]}

    def fail_commit():
        raise AssertionError("execute_repair_job must leave commit ownership to the caller")

    monkeypatch.setattr(
        "app.services.agency_repair_executor.generate_character_reference_assets",
        fake_generate_character_reference_assets,
    )
    monkeypatch.setattr(db, "commit", fail_commit)

    result = await execute_repair_job(db, job)

    assert result.status == "success"
```

- [ ] **Step 2: Run executor tests and verify they fail**

Run:

```powershell
cd server
pytest tests/test_agency_repair_executor.py -q
```

Expected: fail with missing `agency_repair_executor`.

- [ ] **Step 3: Implement executor**

Create `server/app/services/agency_repair_executor.py`:

Before implementing any repair branch that may call a paid provider, verify that the invoked service goes through the existing cost reservation/settlement path and does not commit internally. For reference-image repairs, prefer existing service helpers only if they already preserve provider cost accounting and caller-owned transactions. If a helper cannot provide both guarantees, return `_manual_block(job, "去审查中心确认付费返修", "/review-center")` instead of calling the provider.

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db_models import Character, ProductionAuditEvent, ProductionJob, Scene
from app.services.production_action_result import ProductionActionResult


async def generate_character_reference_assets(db: Session, character_id: str) -> dict:
    from app.services.reference_asset_service import generate_character_reference_images

    return await generate_character_reference_images(db, character_id)


async def generate_scene_reference_assets(db: Session, scene_id: str) -> dict:
    from app.services.reference_asset_service import generate_scene_reference_images

    return await generate_scene_reference_images(db, scene_id)


async def execute_repair_job(db: Session, job: ProductionJob) -> ProductionActionResult:
    repair_type = _repair_type(job.stage)
    if repair_type == "missing_character_reference":
        return await _repair_character_reference(db, job)
    if repair_type == "missing_scene_reference":
        return await _repair_scene_reference(db, job)
    if repair_type.startswith("storyboard_"):
        return _manual_block(job, "去分镜脚本处理", "/series")
    if repair_type.startswith("image_"):
        return _manual_block(job, "去审查中心处理", "/review-center")
    if repair_type.startswith("video_") or repair_type.startswith("compose_"):
        return _manual_block(job, "去生产监控处理", "/video-production")
    return _manual_block(job, "去审查中心处理", "/review-center")


async def _repair_character_reference(db: Session, job: ProductionJob) -> ProductionActionResult:
    character = db.query(Character).filter(Character.id == job.target_id).first()
    if not character:
        return _manual_block(job, "去角色资产补参考图", f"/characters/{job.target_id}")
    meta = dict(character.meta_json or {})
    meta["reference_generation"] = {"status": "running", "source": "agency_auto_repair", "job_id": job.id}
    character.meta_json = meta
    db.flush()
    result = await generate_character_reference_assets(db, character.id)
    meta = dict(character.meta_json or {})
    meta["reference_generation"] = {"status": "completed" if result.get("ok") else "failed", "source": "agency_auto_repair", "job_id": job.id, "result": result}
    if result.get("ok"):
        meta["repair_review_gate"] = {"status": "repair_recheck_pending", "source": "agency_auto_repair", "job_id": job.id}
    character.meta_json = meta
    _audit(db, job, "agency_repair_completed" if result.get("ok") else "agency_repair_failed", result)
    if result.get("ok"):
        _audit(db, job, "agency_repair_recheck_required", {"target_type": "character", "target_id": character.id, "next_gate": "style_lock_review"})
    db.flush()
    if not result.get("ok"):
        return _manual_block(job, "去角色资产补参考图", f"/characters/{character.id}")
    return ProductionActionResult.success(
        "角色参考图返修完成，等待复审",
        {"repair_type": "missing_character_reference", "target_id": character.id, "next_status": "repair_recheck_pending"},
    )


async def _repair_scene_reference(db: Session, job: ProductionJob) -> ProductionActionResult:
    scene = db.query(Scene).filter(Scene.id == job.target_id).first()
    if not scene:
        return _manual_block(job, "去场景资产补参考图", f"/scenes/{job.target_id}")
    meta = dict(scene.meta_json or {})
    meta["reference_generation"] = {"status": "running", "source": "agency_auto_repair", "job_id": job.id}
    scene.meta_json = meta
    db.flush()
    result = await generate_scene_reference_assets(db, scene.id)
    meta = dict(scene.meta_json or {})
    meta["reference_generation"] = {"status": "completed" if result.get("ok") else "failed", "source": "agency_auto_repair", "job_id": job.id, "result": result}
    if result.get("ok"):
        meta["repair_review_gate"] = {"status": "repair_recheck_pending", "source": "agency_auto_repair", "job_id": job.id}
    scene.meta_json = meta
    _audit(db, job, "agency_repair_completed" if result.get("ok") else "agency_repair_failed", result)
    if result.get("ok"):
        _audit(db, job, "agency_repair_recheck_required", {"target_type": "scene", "target_id": scene.id, "next_gate": "style_lock_review"})
    db.flush()
    if not result.get("ok"):
        return _manual_block(job, "去场景资产补参考图", f"/scenes/{scene.id}")
    return ProductionActionResult.success(
        "场景参考图返修完成，等待复审",
        {"repair_type": "missing_scene_reference", "target_id": scene.id, "next_status": "repair_recheck_pending"},
    )


def _manual_block(job: ProductionJob, label: str, route: str) -> ProductionActionResult:
    return ProductionActionResult.blocked(
        "AGENCY_REPAIR_MANUAL_REQUIRED",
        "自动返修需要人工处理。",
        label,
        repair_route=route,
        affected_ids=[job.target_id],
        retryable=False,
    )


def _repair_type(stage: str) -> str:
    return stage.split(":", 1)[1] if ":" in stage else stage


def _audit(db: Session, job: ProductionJob, event_type: str, payload: dict) -> None:
    db.add(ProductionAuditEvent(
        event_type=event_type,
        production_plan_id=job.plan_id,
        payload_json={"job_id": job.id, "repair_type": _repair_type(job.stage), "target_type": job.target_type, "target_id": job.target_id, "result": payload},
    ))
```

- [ ] **Step 4: Dispatch repair jobs in worker**

Modify `server/app/services/production_worker_service.py`.

Add import:

```python
from app.services.agency_repair_contracts import AUTO_REPAIR_STAGE
from app.services.agency_repair_executor import execute_repair_job
```

At the top of `execute_real_job`, before `_job_spec`:

```python
if job.stage == AUTO_REPAIR_STAGE or job.stage.startswith(f"{AUTO_REPAIR_STAGE}:"):
    return await execute_repair_job(db, job)
```

Do not add a commit inside `execute_repair_job`. The existing worker step must commit or roll back after applying the returned `ProductionActionResult`, exactly like normal production jobs.

- [ ] **Step 5: Write worker dispatch test**

Create `server/tests/test_agency_repair_worker.py`:

```python
from app.db_models import ProductionJob, ProductionPlan, Series, VideoProductionRun
from app.services.production_action_result import ProductionActionResult
from app.services.production_worker_service import run_real_worker_step


def test_real_worker_dispatches_agency_auto_repair(db, monkeypatch):
    series = Series(title="老李控糖")
    db.add(series)
    db.commit()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()
    run = VideoProductionRun(series_id=series.id, production_plan_id=plan.id, run_type="real_short_e2e", status="running")
    db.add(run)
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id="char-1",
        stage="agency_auto_repair:missing_character_reference",
        idempotency_key="repair:worker",
    )
    db.add(job)
    db.commit()

    async def fake_execute_repair_job(db, job):
        return ProductionActionResult.success("返修完成", {"ok": True})

    monkeypatch.setattr(
        "app.services.production_worker_service.execute_repair_job",
        fake_execute_repair_job,
    )

    result = run_real_worker_step(db, run.id, lease_id="test-lease", batch_size=1)

    assert result["processed"] == 1
    assert result["items"][0]["status"] == "completed"
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd server
pytest tests/test_agency_repair_executor.py tests/test_agency_repair_worker.py tests/test_video_production_real_worker_step.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/agency_repair_executor.py server/app/services/production_worker_service.py server/tests/test_agency_repair_executor.py server/tests/test_agency_repair_worker.py
git commit -m "feat: execute agency repair jobs"
```

---

### Task 4: Repair APIs, Console Projection, and Production Tree Aggregation

**Files:**
- Modify: `server/app/routers/agency.py`
- Modify: `server/app/services/agency_console.py`
- Modify: `server/app/services/production_tree_service.py`
- Create: `server/tests/test_agency_repair_api.py`
- Modify: `server/tests/test_agency_console.py`
- Modify: `server/tests/test_video_production_tree_api.py`

- [ ] **Step 1: Write repair API tests**

Create `server/tests/test_agency_repair_api.py`:

```python
from app.db_models import ProductionAuditEvent, ProductionJob, ProductionPlan, Series


def test_repair_tasks_api_returns_manual_action(client, db):
    series = Series(title="老李控糖")
    db.add(series)
    db.commit()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    db.commit()
    job = ProductionJob(
        plan_id=plan.id,
        target_type="character",
        target_id="char-1",
        stage="agency_auto_repair:missing_character_reference",
        status="queued",
        idempotency_key="repair:api",
        blocked_reason="缺少角色参考图",
    )
    db.add(job)
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        production_plan_id=plan.id,
        payload_json={
            "job_id": job.id,
            "repair_task": {
                "type": "missing_character_reference",
                "stage": "style_lock",
                "target_type": "character",
                "target_id": "char-1",
                "series_id": series.id,
                "reason": "缺少角色参考图",
                "expected_result": "补齐角色参考图",
                "repair_action_label": "去角色资产补参考图",
                "repair_route": "/characters/char-1",
                "affected_ids": ["char-1"],
                "estimated_cost": 0.2,
            },
        },
    ))
    db.commit()

    resp = client.get(f"/api/agency/repair-tasks?series_id={series.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total"] == 1
    assert body["items"][0]["repair_action_label"] == "去角色资产补参考图"
    assert body["items"][0]["repair_route"] == "/characters/char-1"
```

Create `server/tests/test_agency_repair_query_scale.py`:

```python
from app.db_models import ProductionAuditEvent, ProductionJob, ProductionPlan, Series


def test_repair_task_query_ignores_unrelated_plan_audit_events(client, db):
    target_series = Series(title="目标系列")
    noise_series = Series(title="噪声系列")
    db.add_all([target_series, noise_series])
    db.commit()
    target_plan = ProductionPlan(series_id=target_series.id, status="ready")
    noise_plan = ProductionPlan(series_id=noise_series.id, status="ready")
    db.add_all([target_plan, noise_plan])
    db.commit()
    job = ProductionJob(
        plan_id=target_plan.id,
        target_type="character",
        target_id="char-1",
        stage="agency_auto_repair:missing_character_reference",
        status="queued",
        idempotency_key="repair:target",
    )
    db.add(job)
    db.flush()
    db.add(ProductionAuditEvent(
        event_type="agency_repair_task_created",
        production_plan_id=target_plan.id,
        payload_json={"job_id": job.id, "repair_task": {"reason": "目标返修", "repair_action_label": "去角色资产补参考图"}},
    ))
    for index in range(1000):
        db.add(ProductionAuditEvent(
            event_type="agency_repair_task_created",
            production_plan_id=noise_plan.id,
            payload_json={"job_id": f"noise-{index}", "repair_task": {"reason": "无关返修"}},
        ))
    db.commit()

    resp = client.get(f"/api/agency/repair-tasks?series_id={target_series.id}&page_size=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["reason"] == "目标返修"
```

- [ ] **Step 2: Run API test and verify it fails**

Run:

```powershell
cd server
pytest tests/test_agency_repair_api.py -q
```

Expected: fail with 404 for `/api/agency/repair-tasks`.

- [ ] **Step 3: Add scale-safe production job indexes**

Create an Alembic migration, for example `server/alembic/versions/<revision>_agency_repair_job_indexes.py`:

```python
from alembic import op


revision = "<revision>"
down_revision = "<previous_revision>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_production_jobs_plan_stage_status",
        "production_jobs",
        ["plan_id", "stage", "status"],
        unique=False,
    )
    op.create_index(
        "idx_production_jobs_stage_created",
        "production_jobs",
        ["stage", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_production_jobs_stage_created", table_name="production_jobs")
    op.drop_index("idx_production_jobs_plan_stage_status", table_name="production_jobs")
```

Do not add indexes on `ProductionAuditEvent.payload_json` for this phase. Repair projections must first narrow by `production_plan_id`, optional `run_id`, and current-page `job_id` candidates, then inspect payloads in memory.

- [ ] **Step 4: Implement API helper and route**

Modify `server/app/routers/agency.py` with:

```python
from app.db_models import ProductionAuditEvent, ProductionJob, ProductionPlan
from app.services.production_status import JOB_BLOCKED, JOB_FAILED, JOB_QUEUED, JOB_RETRY_WAIT
```

Add:

```python
@router.get("/repair-tasks")
def list_repair_tasks(
    series_id: str | None = None,
    run_id: str | None = None,
    stage: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    query = db.query(ProductionJob).filter(ProductionJob.stage.like("agency_auto_repair%"))
    if series_id:
        query = query.join(ProductionPlan, ProductionPlan.id == ProductionJob.plan_id).filter(ProductionPlan.series_id == series_id)
    if stage:
        query = query.filter(ProductionJob.stage == stage)
    total = query.count()
    jobs = query.order_by(ProductionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    plan_ids = list({job.plan_id for job in jobs})
    audit_by_job = _repair_audit_by_job(db, [job.id for job in jobs], plan_ids=plan_ids, run_id=run_id)
    items = [_repair_task_item(job, audit_by_job.get(job.id)) for job in jobs]
    return {"summary": _repair_summary(items), "items": items, "page": page, "page_size": page_size, "total": total}


@router.post("/repair-tasks/{job_id}/retry")
def retry_repair_task(
    job_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job or not job.stage.startswith("agency_auto_repair"):
        raise HTTPException(status_code=404, detail="返修任务不存在")
    if job.status not in {JOB_FAILED, JOB_BLOCKED, JOB_RETRY_WAIT}:
        raise HTTPException(status_code=409, detail="当前返修任务状态不允许重试")
    job.status = JOB_QUEUED
    job.error_code = None
    job.error_message = None
    job.blocked_reason = None
    job.lease_id = None
    job.leased_until = None
    db.add(ProductionAuditEvent(
        event_type="agency_repair_retry_requested",
        production_plan_id=job.plan_id,
        payload_json={"job_id": job.id, "stage": job.stage, "target_type": job.target_type, "target_id": job.target_id},
    ))
    db.commit()
    db.refresh(job)
    return _repair_task_item(job, None)


def _repair_audit_by_job(db: Session, job_ids: list[str], *, plan_ids: list[str], run_id: str | None = None) -> dict[str, dict]:
    if not job_ids:
        return {}
    query = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id.in_(plan_ids))
        .filter(ProductionAuditEvent.event_type.in_(["agency_repair_task_created", "agency_repair_manual_required", "agency_repair_completed", "agency_repair_failed", "agency_repair_recheck_required"]))
    )
    if run_id:
        query = query.filter(ProductionAuditEvent.run_id == run_id)
    rows = query.order_by(ProductionAuditEvent.created_at.asc()).all()
    result = {}
    for row in rows:
        payload = row.payload_json or {}
        job_id = payload.get("job_id")
        if job_id in job_ids:
            current = result.setdefault(job_id, {})
            if payload.get("repair_task"):
                current["repair_task"] = payload["repair_task"]
            if row.event_type == "agency_repair_recheck_required":
                current["recheck_required"] = True
                current["next_gate"] = (payload.get("result") or {}).get("next_gate")
            current["last_event_type"] = row.event_type
    return result


def _repair_task_item(job: ProductionJob, audit: dict | None) -> dict:
    repair_task = (audit or {}).get("repair_task") or {}
    return {
        "id": job.id,
        "type": repair_task.get("type") or job.stage.split(":", 1)[-1],
        "stage": repair_task.get("stage") or job.stage,
        "status": job.status,
        "reason": repair_task.get("reason") or job.blocked_reason or "",
        "expected_result": repair_task.get("expected_result") or "",
        "repair_action_label": repair_task.get("repair_action_label") or "联系人工处理",
        "repair_route": repair_task.get("repair_route") or "/",
        "affected_ids": repair_task.get("affected_ids") or [job.target_id],
        "estimated_cost": repair_task.get("estimated_cost") or 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "recheck_required": bool((audit or {}).get("recheck_required")) or job.status == "repair_recheck_pending",
        "next_gate": (audit or {}).get("next_gate"),
    }


def _repair_summary(items: list[dict]) -> dict:
    summary = {"total": len(items), "queued": 0, "running": 0, "completed": 0, "failed": 0, "manual_required": 0, "recheck_required": 0}
    for item in items:
        status = item["status"]
        if status in summary:
            summary[status] += 1
        if item.get("recheck_required"):
            summary["recheck_required"] += 1
        if item["repair_action_label"]:
            summary["manual_required"] += 1 if status in {"failed", "blocked"} else 0
    return summary
```

- [ ] **Step 5: Add console `repair_summary`**

In `server/app/services/agency_console.py`, where the response dict is assembled, add:

```python
"repair_summary": _repair_summary_for_series(db, series.id),
```

Add helper:

```python
def _repair_summary_for_series(db: Session, series_id: str) -> dict:
    rows = (
        db.query(ProductionJob)
        .join(ProductionPlan, ProductionPlan.id == ProductionJob.plan_id)
        .filter(ProductionPlan.series_id == series_id)
        .filter(ProductionJob.stage.like("agency_auto_repair%"))
        .all()
    )
    plan_ids = list({row.plan_id for row in rows})
    job_ids = [row.id for row in rows]
    return {
        "total": len(rows),
        "queued": sum(1 for row in rows if row.status == "queued"),
        "running": sum(1 for row in rows if row.status in {"leased", "running", "retry_wait"}),
        "completed": sum(1 for row in rows if row.status == "completed"),
        "failed": sum(1 for row in rows if row.status == "failed"),
        "manual_required": sum(1 for row in rows if row.status in {"blocked", "failed"}),
        "recheck_required": _repair_recheck_required_count(db, job_ids, plan_ids=plan_ids),
    }


def _repair_recheck_required_count(db: Session, job_ids: list[str], *, plan_ids: list[str]) -> int:
    if not job_ids:
        return 0
    rows = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id.in_(plan_ids))
        .filter(ProductionAuditEvent.event_type == "agency_repair_recheck_required")
        .all()
    )
    return sum(1 for row in rows if (row.payload_json or {}).get("job_id") in job_ids)
```

Add imports if missing:

```python
from app.db_models import ProductionAuditEvent, ProductionJob, ProductionPlan
```

- [ ] **Step 6: Add production tree repair node**

In `server/app/services/production_tree_service.py`, add repair aggregation to the returned tree:

```python
def _repair_tree_node(db: Session, plan_id: str) -> dict | None:
    jobs = db.query(ProductionJob).filter(ProductionJob.plan_id == plan_id, ProductionJob.stage.like("agency_auto_repair%")).all()
    if not jobs:
        return None
    job_ids = [job.id for job in jobs]
    recheck_events = (
        db.query(ProductionAuditEvent)
        .filter(ProductionAuditEvent.production_plan_id == plan_id)
        .filter(ProductionAuditEvent.event_type == "agency_repair_recheck_required")
        .all()
    )
    recheck_required = sum(1 for event in recheck_events if (event.payload_json or {}).get("job_id") in job_ids)
    return {
        "id": f"repair:{plan_id}",
        "type": "agency_auto_repair",
        "label": "自动返修",
        "status": "failed" if any(job.status == "failed" for job in jobs) else "running" if any(job.status in {"queued", "leased", "running", "retry_wait"} for job in jobs) else "completed",
        "summary": {
            "total": len(jobs),
            "queued": sum(1 for job in jobs if job.status == "queued"),
            "running": sum(1 for job in jobs if job.status in {"leased", "running", "retry_wait"}),
            "completed": sum(1 for job in jobs if job.status == "completed"),
            "failed": sum(1 for job in jobs if job.status == "failed"),
            "manual_required": sum(1 for job in jobs if job.status in {"blocked", "failed"}),
            "recheck_required": recheck_required,
        },
    }
```

Append this node to the root or stage nodes according to the existing tree structure.

Add imports to `server/app/services/production_tree_service.py` if missing:

```python
from app.db_models import ProductionAuditEvent, ProductionJob
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd server
pytest tests/test_agency_repair_api.py tests/test_agency_repair_query_scale.py tests/test_agency_console.py tests/test_video_production_tree_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```powershell
git add server/app/routers/agency.py server/app/services/agency_console.py server/app/services/production_tree_service.py server/alembic/versions/<revision>_agency_repair_job_indexes.py server/tests/test_agency_repair_api.py server/tests/test_agency_repair_query_scale.py server/tests/test_agency_console.py server/tests/test_video_production_tree_api.py
git commit -m "feat: expose agency repair status"
```

---

### Task 5: Frontend Transparency and Policy Confirmation

**Files:**
- Modify: `web/src/api/agency.js`
- Modify: `web/src/api/videoProduction.js`
- Create: `web/src/components/agency/AutoRepairSummaryStrip.vue`
- Create: `web/src/components/agency/AutoRepairPolicyPanel.vue`
- Modify: `web/src/components/agency/AgencyDecisionLog.vue`
- Modify: `web/src/views/OneSentenceVideoPage.vue`
- Modify: `web/src/views/VideoProductionMonitorPage.vue`
- Create: `web/src/__tests__/auto-repair-summary-strip.test.js`
- Create: `web/src/__tests__/agency-auto-repair-log.test.js`
- Create: `web/src/__tests__/one-sentence-auto-repair-policy.test.js`
- Create: `web/src/__tests__/video-production-repair-node.test.js`

- [ ] **Step 1: Write frontend API and UI tests**

Create `web/src/__tests__/agency-auto-repair-log.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import AgencyDecisionLog from '../components/agency/AgencyDecisionLog.vue'

describe('AgencyDecisionLog auto repair transparency', () => {
  it('shows repair state and manual action in Chinese', () => {
    const wrapper = mount(AgencyDecisionLog, {
      props: {
        decisionLog: [
          {
            stage: 'style_lock',
            expert_name: '风格锁定质量审查专家',
            result_status: 'warning',
            summary: '发现角色参考图缺失',
            repair_tasks: [
              {
                type: 'missing_character_reference',
                status: 'manual_required',
                reason: '角色缺少侧面参考图',
                repair_action_label: '去角色资产补参考图',
                repair_route: '/characters/char-1',
                estimated_cost: 0.2,
              },
            ],
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('自动返修')
    expect(wrapper.text()).toContain('角色缺少侧面参考图')
    expect(wrapper.text()).toContain('去角色资产补参考图')
    expect(wrapper.text()).not.toContain('provider')
    expect(wrapper.text()).not.toMatch(/[鍘鑰鎺瑙闇鐢琛]|鈥|渆|�/)
  })
})
```

Create `web/src/__tests__/one-sentence-auto-repair-policy.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import OneSentenceVideoPage from '../views/OneSentenceVideoPage.vue'
import * as videoProductionApi from '../api/videoProduction'

vi.mock('../api/videoProduction', () => ({
  createOneSentenceVideo: vi.fn(() => Promise.resolve({ id: 'run-1' })),
}))

describe('OneSentenceVideoPage auto repair policy', () => {
  it('sends confirmed auto repair policy when starting production', async () => {
    const wrapper = mount(OneSentenceVideoPage, {
      global: { stubs: ['RouterLink'] },
    })

    await wrapper.find('[data-test="auto-repair-enabled"]').setValue(true)
    await wrapper.find('[data-test="auto-repair-budget"]').setValue('1.5')
    await wrapper.find('[data-test="submit-one-sentence"]').trigger('click')

    expect(videoProductionApi.createOneSentenceVideo).toHaveBeenCalled()
    const payload = videoProductionApi.createOneSentenceVideo.mock.calls[0][0]
    expect(payload.auto_repair_policy.enabled).toBe(true)
    expect(payload.auto_repair_policy.budget_limit).toBe(1.5)
    expect(payload.auto_repair_policy.requires_human_gate_after_repair).toBe(true)
  })
})
```

Create `web/src/__tests__/video-production-repair-node.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import VideoProductionMonitorPage from '../views/VideoProductionMonitorPage.vue'

describe('VideoProductionMonitorPage repair node', () => {
  it('shows aggregated repair counts before details', async () => {
    const wrapper = mount(VideoProductionMonitorPage, {
      global: {
        mocks: { $route: { params: { runId: 'run-1' } }, $router: { push: vi.fn() } },
        stubs: ['RouterLink'],
      },
    })
    wrapper.vm.tree = {
      nodes: [
        {
          id: 'repair:plan-1',
          type: 'agency_auto_repair',
          label: '自动返修',
          summary: { total: 12, running: 3, manual_required: 2, recheck_required: 1, failed: 1, completed: 6 },
        },
      ],
    }
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('自动返修')
    expect(wrapper.text()).toContain('待人工 2')
    expect(wrapper.text()).toContain('待复审')
    expect(wrapper.text()).toContain('失败 1')
  })
})
```

- [ ] **Step 1a: Write reusable summary strip test**

Create `web/src/__tests__/auto-repair-summary-strip.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'

describe('AutoRepairSummaryStrip', () => {
  it('summarizes repair state without exposing provider internals', () => {
    const wrapper = mount(AutoRepairSummaryStrip, {
      props: {
        summary: {
          total: 12,
          running: 3,
          manual_required: 2,
          failed: 1,
          completed: 6,
          repair_budget_spent: 0.8,
          recheck_required: 1,
          currency: 'CNY',
        },
      },
    })

    expect(wrapper.text()).toContain('自动返修')
    expect(wrapper.text()).toContain('返修中 3')
    expect(wrapper.text()).toContain('待人工 2')
    expect(wrapper.text()).toContain('待复审 1')
    expect(wrapper.text()).toContain('已花费 0.8 CNY')
    expect(wrapper.text()).not.toContain('provider')
  })

  it('shows suggestion-only state when budget is disabled', () => {
    const wrapper = mount(AutoRepairSummaryStrip, {
      props: {
        summary: {
          total: 2,
          manual_required: 2,
          repair_budget_spent: 0,
          budget_disabled: true,
        },
      },
    })

    expect(wrapper.text()).toContain('仅记录建议，不自动付费返修')
  })
})
```

- [ ] **Step 2: Run frontend tests and verify they fail**

Run:

```powershell
cd web
npm test -- auto-repair-summary-strip agency-auto-repair-log one-sentence-auto-repair-policy video-production-repair-node --run
```

Expected: tests fail because UI and selectors are not implemented yet.

- [ ] **Step 3: Add API helpers**

Modify `web/src/api/agency.js`:

```javascript
import client from './client'

export function getRepairTasks(params = {}) {
  return client.get('/agency/repair-tasks', { params })
}

export function retryRepairTask(jobId) {
  return client.post(`/agency/repair-tasks/${jobId}/retry`)
}
```

Modify `web/src/api/videoProduction.js` so both `startEpisodeProduction(payload)` and `createOneSentenceVideo(payload)` forward `auto_repair_policy`:

```javascript
export function startEpisodeProduction(payload) {
  return client.post('/video-production/runs/start', {
    ...payload,
    auto_repair_policy: payload.auto_repair_policy,
  })
}

export function createOneSentenceVideo(payload) {
  return client.post('/video-production/one-sentence', {
    ...payload,
    auto_repair_policy: payload.auto_repair_policy,
  })
}
```

- [ ] **Step 4: Create reusable summary strip**

Create `web/src/components/agency/AutoRepairSummaryStrip.vue`:

```vue
<template>
  <section class="border-y border-slate-800 bg-slate-950/60 px-3 py-2" data-test="auto-repair-summary-strip">
    <div class="flex flex-wrap items-center gap-2 text-xs text-slate-300">
      <strong class="text-slate-100">自动返修</strong>
      <span>共 {{ summary?.total || 0 }} 项</span>
      <span v-if="summary?.running">返修中 {{ summary.running }}</span>
      <span v-if="summary?.manual_required" class="text-amber-200">待人工 {{ summary.manual_required }}</span>
      <span v-if="summary?.recheck_required" class="text-cyan-200">待复审 {{ summary.recheck_required }}</span>
      <span v-if="summary?.failed" class="text-rose-200">失败 {{ summary.failed }}</span>
      <span v-if="summary?.completed">已完成 {{ summary.completed }}</span>
      <span v-if="Number(summary?.repair_budget_spent || 0) > 0" class="text-emerald-200">
        已花费 {{ summary.repair_budget_spent }} {{ summary.currency || 'CNY' }}
      </span>
      <span v-if="summary?.budget_disabled" class="text-slate-400">仅记录建议，不自动付费返修</span>
    </div>
  </section>
</template>

<script setup>
defineProps({
  summary: {
    type: Object,
    default: () => ({}),
  },
})
</script>
```

- [ ] **Step 5: Create compact policy panel**

Create `web/src/components/agency/AutoRepairPolicyPanel.vue`:

```vue
<template>
  <section class="border border-slate-800 bg-slate-950/50 p-3" data-test="auto-repair-policy-card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold text-slate-100">自动返修策略</h3>
        <p class="mt-1 text-xs text-slate-400">结构性缺口可自动补齐，质量和最终成片仍需审查确认。</p>
      </div>
      <label class="flex items-center gap-2 text-sm text-slate-200">
        <input data-test="auto-repair-enabled" :checked="policy.enabled" type="checkbox" class="h-4 w-4" @change="update('enabled', $event.target.checked)" />
        启用
      </label>
    </div>
    <div class="mt-3 grid gap-3 md:grid-cols-2">
      <label class="text-xs text-slate-300">
        最大返修轮数
        <input :value="policy.max_rounds" min="0" max="2" type="number" class="mt-1 w-full border border-slate-700 bg-slate-950 px-3 py-2 text-sm" @input="update('max_rounds', Number($event.target.value || 0))" />
      </label>
      <label class="text-xs text-slate-300">
        返修预算上限
        <input data-test="auto-repair-budget" :value="policy.budget_limit" min="0" step="0.1" type="number" class="mt-1 w-full border border-slate-700 bg-slate-950 px-3 py-2 text-sm" @input="update('budget_limit', Number($event.target.value || 0))" />
      </label>
    </div>
    <p v-if="!policy.enabled || Number(policy.budget_limit || 0) <= 0" class="mt-2 text-xs text-amber-200">
      仅记录返修建议，不自动调用付费模型。
    </p>
  </section>
</template>

<script setup>
const props = defineProps({
  policy: {
    type: Object,
    required: true,
  },
})
const emit = defineEmits(['update:policy'])

function update(key, value) {
  emit('update:policy', { ...props.policy, [key]: value })
}
</script>
```

- [ ] **Step 6: Add repair section to `AgencyDecisionLog.vue`**

Inside each decision log item template in `web/src/components/agency/AgencyDecisionLog.vue`, add:

```vue
<section v-if="item.repair_tasks?.length" class="mt-3 border-l-2 border-cyan-500/60 bg-slate-950/50 p-3" data-test="agency-repair-tasks">
  <div class="mb-2 flex items-center justify-between">
    <h4 class="text-sm font-semibold text-cyan-100">自动返修</h4>
    <span class="text-xs text-cyan-200">共 {{ item.repair_tasks.length }} 项</span>
  </div>
  <div v-for="task in item.repair_tasks" :key="`${task.type}-${task.target_id || task.repair_route}`" class="mb-2 last:mb-0">
    <p class="text-sm text-slate-100">{{ task.reason }}</p>
    <p class="mt-1 text-xs text-slate-400">下一步：{{ task.repair_action_label || '联系人工处理' }}</p>
    <p v-if="Number(task.estimated_cost || 0) > 0" class="mt-1 text-xs text-amber-200">预计返修成本：{{ task.estimated_cost }} 元</p>
    <RouterLink v-if="task.repair_route" :to="task.repair_route" class="mt-2 inline-flex text-xs text-cyan-200 hover:text-cyan-100">
      {{ task.repair_action_label || '去处理' }}
    </RouterLink>
  </div>
</section>
```

- [ ] **Step 7: Add policy confirmation panel to `OneSentenceVideoPage.vue`**

Add reactive state:

```javascript
const autoRepairPolicy = reactive({
  enabled: false,
  max_rounds: 2,
  budget_limit: 0,
  currency: 'CNY',
  allowed_stages: ['style_lock', 'storyboard', 'image_stage', 'video_stage', 'compose'],
  allowed_types: [
    'missing_character_reference',
    'missing_scene_reference',
    'storyboard_missing_references',
    'image_generation_timeout',
    'video_segment_timeout',
  ],
  requires_human_gate_after_repair: true,
})
```

Add import:

```javascript
import AutoRepairPolicyPanel from '../components/agency/AutoRepairPolicyPanel.vue'
```

Add template before the start button:

```vue
<AutoRepairPolicyPanel
  :policy="autoRepairPolicy"
  @update:policy="Object.assign(autoRepairPolicy, $event)"
/>
```

When starting production, include:

```javascript
auto_repair_policy: { ...autoRepairPolicy },
```

The primary start button text should be:

```vue
启动生产并应用返修策略
```

- [ ] **Step 8: Add repair aggregation to monitor page**

In `web/src/views/VideoProductionMonitorPage.vue`, import and render the summary strip before detailed nodes:

```javascript
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'
```

```vue
<AutoRepairSummaryStrip
  v-for="node in repairNodes"
  :key="node.id"
  :summary="node.summary"
  data-test="repair-tree-node"
/>
```

Add computed:

```javascript
const repairNodes = computed(() => {
  const nodes = tree.value?.nodes || []
  return nodes.filter((node) => node.type === 'agency_auto_repair')
})
```

- [ ] **Step 9: Run frontend tests**

Run:

```powershell
cd web
npm test -- auto-repair-summary-strip agency-auto-repair-log one-sentence-auto-repair-policy video-production-repair-node api-clients --run
```

Expected: selected tests pass.

- [ ] **Step 10: Commit**

```powershell
git add web/src/api/agency.js web/src/api/videoProduction.js web/src/components/agency/AutoRepairSummaryStrip.vue web/src/components/agency/AutoRepairPolicyPanel.vue web/src/components/agency/AgencyDecisionLog.vue web/src/views/OneSentenceVideoPage.vue web/src/views/VideoProductionMonitorPage.vue web/src/__tests__/auto-repair-summary-strip.test.js web/src/__tests__/agency-auto-repair-log.test.js web/src/__tests__/one-sentence-auto-repair-policy.test.js web/src/__tests__/video-production-repair-node.test.js
git commit -m "feat: show agency auto repair flow"
```

---

### Task 6: End-to-End Guardrails and Regression Verification

**Files:**
- Create: `server/tests/test_agency_auto_repair_e2e.py`
- Modify: `server/tests/test_video_production_full_mocked_e2e.py`
- Modify: `web/src/__tests__/series-detail-agency.test.js`
- Modify: `docs/superpowers/specs/2026-06-03-agency-auto-repair-loop-design.md` only if implementation discovers an accepted contract correction.

- [ ] **Step 1: Write mocked backend E2E test**

Create `server/tests/test_agency_auto_repair_e2e.py`:

```python
from app.db_models import AgencyExpertInvocation, ProductionAuditEvent, ProductionJob, ProductionPlan, Series, VideoProductionRun


def test_expert_finding_creates_repair_job_and_visible_audit(client, db):
    series = Series(title="老李控糖")
    db.add(series)
    db.commit()
    plan = ProductionPlan(series_id=series.id, status="ready")
    db.add(plan)
    run = VideoProductionRun(
        series_id=series.id,
        production_plan_id=plan.id,
        run_type="real_short_e2e",
        status="running",
        model_trace_json={
            "auto_repair_policy": {
                "enabled": True,
                "max_rounds": 2,
                "budget_limit": 1.0,
                "currency": "CNY",
                "allowed_stages": ["style_lock"],
                "allowed_types": ["missing_character_reference"],
                "requires_human_gate_after_repair": True,
            }
        },
    )
    db.add(run)
    db.commit()
    invocation = AgencyExpertInvocation(
        idempotency_key="invocation:e2e",
        series_id=series.id,
        run_id=run.id,
        production_plan_id=plan.id,
        stage="style_lock",
        expert_id="style_lock_quality_reviewer",
        role="reviewer",
        execution_status="completed",
        result_status="warning",
        output_summary_json={
            "repair_tasks": [
                {
                    "type": "missing_character_reference",
                    "stage": "style_lock",
                    "target_type": "character",
                    "target_id": "char-1",
                    "series_id": series.id,
                    "auto_execute": True,
                    "requires_paid_provider": True,
                    "estimated_cost": 0.2,
                    "reason": "角色缺少侧面参考图",
                    "expected_result": "补齐角色参考图",
                    "repair_action_label": "去角色资产补参考图",
                    "repair_route": "/characters/char-1",
                    "affected_ids": ["char-1"],
                }
            ]
        },
    )
    db.add(invocation)
    db.commit()

    from app.services.agency_repair_orchestrator import enqueue_repair_tasks_for_invocation
    enqueue_repair_tasks_for_invocation(db, invocation, run.model_trace_json["auto_repair_policy"])

    assert db.query(ProductionJob).filter(ProductionJob.stage.like("agency_auto_repair%")).count() == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_task_created").count() == 1
    assert db.query(ProductionAuditEvent).filter_by(event_type="agency_repair_recheck_required").count() == 0
    resp = client.get(f"/api/agency/repair-tasks?series_id={series.id}")
    assert resp.status_code == 200
    assert resp.json()["summary"]["total"] == 1
```

- [ ] **Step 2: Run mocked E2E and verify it passes**

Run:

```powershell
cd server
pytest tests/test_agency_auto_repair_e2e.py -q
```

Expected: pass. This test covers task creation only; executor tests must separately prove successful auto-repair creates `agency_repair_recheck_required` and does not mark assets as `approved`.

- [ ] **Step 3: Run backend regression set**

Run:

```powershell
cd server
pytest tests/test_agency_repair_classifier.py tests/test_agency_repair_orchestrator.py tests/test_agency_repair_executor.py tests/test_agency_repair_api.py tests/test_agency_repair_query_scale.py tests/test_agency_repair_worker.py tests/test_agency_console.py tests/test_series_style_lock_pipeline.py tests/test_video_production_full_mocked_e2e.py tests/test_video_production_real_worker_step.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run frontend regression set**

Run:

```powershell
cd web
npm test -- auto-repair-summary-strip agency-auto-repair-log one-sentence-auto-repair-policy video-production-repair-node agency-console-page series-detail-agency video-production-monitor-page api-clients --run
```

Expected: all selected tests pass.

- [ ] **Step 5: Run static checks used by the repo**

Run:

```powershell
cd web
npm run build
```

Expected: build exits successfully.

Run:

```powershell
cd server
pytest tests/test_video_production_named_errors.py tests/test_video_production_cost_safety.py -q
```

Expected: both tests pass, confirming named errors and cost guardrails remain intact.

- [ ] **Step 6: Commit**

```powershell
git add server/tests/test_agency_auto_repair_e2e.py server/tests/test_video_production_full_mocked_e2e.py web/src/__tests__/series-detail-agency.test.js
git commit -m "test: cover agency auto repair loop"
```

---

## Implementation Order

1. Task 1: Contracts and classifier.
2. Task 2: Policy and orchestrator.
3. Task 3: Executor and worker dispatch.
4. Task 4: APIs and backend projections.
5. Task 5: Frontend transparency.
6. Task 6: E2E and regression verification.

Each task should be committed independently. If a task fails review, fix it before starting the next task.

## Self-Review

### Spec Coverage

- Expert findings become structured repair tasks: Task 1.
- Only deterministic issues auto-execute: Task 1 and Task 2.
- User-authorized `auto_repair_policy`: Task 2 and Task 5.
- Reuse `ProductionJob.stage = "agency_auto_repair"`: Task 2 and Task 3.
- Worker execution and retry boundaries: Task 3.
- Repair status visible in agency console, assets, review center, and monitor: Task 4 and Task 5.
- Long-video aggregated repair display: Task 4 and Task 5.
- Compact reusable repair summary and policy components: Task 5.
- Manual-required action fields: Task 1, Task 4, and Task 5.
- Cost and provider audit trace: Task 2, Task 4, and Task 6.
- No automatic final approval: Task 3 and Task 6.

### Placeholder Scan

The plan avoids placeholder instructions. Each code-changing step includes concrete code or an exact insertion shape, and each verification step includes an exact command and expected result.

### Type Consistency

- `RepairTask.repair_action_label`, `repair_route`, and `affected_ids` are defined in Task 1 and reused in Tasks 2, 4, and 5.
- `AUTO_REPAIR_STAGE = "agency_auto_repair"` is defined in Task 1 and reused in Tasks 2 and 3.
- `auto_repair_policy` is persisted in `VideoProductionRun.model_trace_json` in Task 2 and sent from the frontend in Task 5.
- `ProductionJob.stage` uses `agency_auto_repair:<repair_type>` consistently.
