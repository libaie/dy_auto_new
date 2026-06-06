# Short Video Creative Workbench Design

Date: 2026-06-06

Status: Approved design. Spec review is auto-approved by user instruction.

## Summary

dy_auto already has an expert team, stage reviews, repair tasks, Pixelle stage submission, and an agency console. The current expert loop is still mostly an audit loop: experts return `findings`, `recommendations`, `required_changes`, and `status`; the production path only blocks on `blocked` or `failed`; when a stage is merely `warn` or `passed`, the original script, frames, segments, prompts, and edit manifest continue to Pixelle.

This design turns the agency path into a professional short-video production workbench. Experts must be able to produce structured creative patches for scripts, storyboards, image prompts, video prompts, and edit manifests. Professional users must be able to review, edit, approve, reject, and apply those patches before paid generation. After generation, multimodal review will reuse the same patch contract to repair real images, videos, shots, and edit decisions.

The recommended delivery is an end-to-end director workbench, shipped in phases. Phase 1 builds the pre-generation creative patch loop and the workbench controls. Phase 2 adds multimodal asset review that looks at real image and video outputs and produces new patch proposals instead of plain advice.

## Goals

- Convert expert output from passive audit notes into applicable content versions.
- Let experts propose concrete rewrites for `Episode.script_json`, `Episode.storyboard_json`, `ProductionSegment.image_prompt`, `ProductionSegment.video_prompt`, and `VideoProductionRun.edit_manifest_json`.
- Require human approval before expert patches mutate production data.
- Block Pixelle submission when required creative patches are still pending approval.
- Give internal creative staff a director workbench for brief control, script/storyboard review, prompt review, edit manifest review, and repair decisions.
- Preserve the existing `AgencyExpertInvocation`, repair task, production job, audit event, stage gate, and Pixelle submission architecture.
- Prepare the same patch contract for Phase 2 multimodal review of real image and video assets.
- Keep API keys, provider payloads, full prompts, and secrets out of traces, logs, and frontend payloads.

## Non Goals

- Do not build a full timeline video editor in Phase 1.
- Do not let experts directly write production database fields without human approval.
- Do not auto-approve final images, videos, or composed videos.
- Do not replace the existing Pixelle bridge or provider stage API.
- Do not create an external long-running multi-agent runtime.
- Do not automatically execute subjective quality changes without a visible workbench action.

## Current Baseline

Relevant current files and behavior:

- `server/app/services/agency_runtime.py`
  - Accepts expert statuses `passed`, `warn`, `blocked`, and `failed`.
  - Validates strict JSON with `decision`, `findings`, `recommendations`, `required_changes`, and `evidence`.
- `server/app/services/agency_orchestrator.py`
  - Runs reviewer, lead, and QA experts per stage.
  - Aggregates any `warn` into stage status `warning`.
- `server/app/services/video_production_service.py`
  - Calls agency review before image, video, and compose stages.
  - Blocks provider stages only for `blocked` or `failed`.
  - Builds Pixelle payloads from current storyboard, segments, prompts, and edit manifest.
- `server/app/services/agency_persistence.py`
  - Stores expert output in `AgencyExpertInvocation.output_summary_json`.
  - Classifies `repair_tasks` and may enqueue auto repair jobs.
- `server/app/services/agency_repair_*`
  - Provides a repair task path, but current repair tasks are mostly structural or manual handling tasks.
- `server/app/services/script_pipeline.py`
  - Persists structured dramatic script outputs and compatibility snapshots into `Episode.script_json` and `Episode.storyboard_json`.
- `server/app/db_models.py`
  - Has `Episode.script_json`, `Episode.storyboard_json`, `ProductionSegment.image_prompt`, `ProductionSegment.video_prompt`, `VideoProductionRun.edit_manifest_json`, `AgencyExpertInvocation`, `ProductionAuditEvent`, and production plan/run entities.
- `web/src/views/AgencyConsolePage.vue`
  - Shows stage traces, expert invocations, decision logs, and repair summaries.
  - It is currently a transparency console, not an editing workbench.

The core gap: expert findings are visible but do not reliably become improved production inputs.

## Recommended Approach

Use a structured creative patch system with human approval and Pixelle preflight enforcement.

The expert model still returns audit fields, but it can also return `creative_patches`. These patches are validated, persisted, shown in the workbench, optionally edited by a human, approved, then applied through server-side services. Pixelle submission checks pending patches before sending paid provider requests.

This keeps the existing architecture intact while adding the missing production layer.

## Alternatives Considered

### Alternative 1: Store Patches Only In Invocation JSON

Pros:

- Minimal database changes.
- Easy to add to current expert output.

Cons:

- Hard to query pending patches across a run.
- Hard to edit, approve, reject, apply, or audit independently.
- Workbench interactions become brittle because each action must rewrite an invocation snapshot.

Decision: reject for Phase 1. Invocation JSON should keep a source snapshot, but approvals need first-class rows.

### Alternative 2: Add A Dedicated Creative Patch Table

Pros:

- Clear lifecycle and filtering.
- Better auditability.
- Easier frontend queries and bulk status summaries.
- Safer apply behavior through stable patch IDs.

Cons:

- Requires migration and service layer.

Decision: accept. The workbench needs lifecycle state, not just logs.

### Alternative 3: Let Experts Auto-Apply Low-Risk Patches

Pros:

- Faster automation.

Cons:

- Violates the professional workflow: internal staff want control before generation.
- Increases risk of silent content drift.
- Makes cost and quality responsibility unclear.

Decision: reject for Phase 1. All creative patches require human approval.

## Creative Patch Contract

Expert output extends `output_summary_json` with `creative_patches`.

```json
{
  "decision": "存在警告，但已给出可执行改稿方案",
  "findings": ["前三秒冲突不够强"],
  "recommendations": ["把第一镜改成公开羞辱场景"],
  "required_changes": ["强化 shot-001 的动作和视觉冲突"],
  "creative_patches": [
    {
      "patch_type": "storyboard_patch",
      "target_type": "storyboard_frame",
      "target_id": "shot-001",
      "stage": "storyboard",
      "title": "强化前三秒钩子",
      "reason": "原镜头只是铺垫，没有足够短视频冲突。",
      "before": {
        "image_prompt": "主角站在办公室门口",
        "video_prompt": "镜头缓慢推进"
      },
      "after": {
        "image_prompt": "主角在会议室被当众撕毁方案，纸张飞散，众人冷眼旁观，低角度压迫构图",
        "video_prompt": "开场 1 秒纸张砸向镜头，随后快速推近主角克制表情，形成强冲突钩子"
      },
      "apply_policy": "requires_human_approval",
      "priority": "high"
    }
  ],
  "evidence": ["storyboard.frames[0]"]
}
```

Allowed `patch_type` values for Phase 1:

- `script_patch`
- `storyboard_patch`
- `image_prompt_patch`
- `video_prompt_patch`
- `edit_manifest_patch`

Allowed `target_type` values for Phase 1:

- `episode_script`
- `storyboard_frame`
- `production_segment`
- `edit_manifest`

Patch fields:

- `patch_type`: fixed enum.
- `target_type`: fixed enum.
- `target_id`: existing episode, frame, segment, or run identifier.
- `stage`: agency stage that produced the patch.
- `title`: short Chinese title for the workbench.
- `reason`: Chinese explanation of why the patch improves the piece.
- `before`: sanitized JSON snapshot from current production data.
- `after`: sanitized JSON object with only allowed fields for the patch type.
- `apply_policy`: `requires_human_approval` in Phase 1.
- `priority`: `low`, `normal`, or `high`.

Rejected fields:

- Raw provider credentials.
- Arbitrary URLs not already part of controlled assets.
- Shell commands, filesystem paths, or provider API payloads.
- Unknown database column names.
- Full prompt dumps that include hidden system instructions.

## Persistence Model

Add `AgencyCreativePatch` to `server/app/db_models.py` and an Alembic migration.

Table: `agency_creative_patches`

Fields:

- `id`
- `series_id`
- `episode_id`
- `run_id`
- `production_plan_id`
- `production_episode_id`
- `production_segment_id`
- `source_invocation_id`
- `stage`
- `expert_id`
- `patch_type`
- `target_type`
- `target_id`
- `title`
- `reason`
- `before_json`
- `after_json`
- `status`
- `priority`
- `reviewer_user_id`
- `applied_at`
- `rejected_at`
- `created_at`
- `updated_at`

Statuses:

- `proposed`: expert-generated and awaiting review.
- `edited`: human edited the `after_json`.
- `approved`: human approved but not yet applied.
- `applied`: patch was written back into production data.
- `rejected`: human rejected it.

Important indexes:

- `(series_id, created_at)`
- `(run_id, status)`
- `(source_invocation_id)`
- `(target_type, target_id, status)`
- `(production_plan_id, stage, status)`

The source `AgencyExpertInvocation.output_summary_json.creative_patches` remains as an immutable source snapshot. The patch table is the operational lifecycle.

## Backend Services

### `agency_creative_patch_contracts.py`

Defines Pydantic contracts:

- `CreativePatchType`
- `CreativePatchStatus`
- `CreativePatchTargetType`
- `CreativePatchProposal`
- `CreativePatchApplyResult`

Validation rules:

- Unknown patch types are rejected.
- Unknown target types are rejected.
- `after` may contain only allowed fields for the patch type.
- `apply_policy` must be `requires_human_approval`.
- `reason` and `title` must be readable Chinese-facing text.

### `agency_creative_patch_service.py`

Responsibilities:

- Extract patch proposals from expert output.
- Validate target existence.
- Create `AgencyCreativePatch` rows.
- List patches for a series or run.
- Update an editable patch.
- Approve, reject, and apply patches.
- Record `ProductionAuditEvent` entries for create, edit, approve, reject, and apply actions.

Apply behavior:

- `script_patch`
  - Writes approved `after` fields into `Episode.script_json`.
- `storyboard_patch`
  - Finds a frame in `Episode.storyboard_json.frames` or `VideoProductionRun.storyboard_json.frames`.
  - Updates allowed frame fields.
- `image_prompt_patch`
  - Writes `ProductionSegment.image_prompt`.
  - If run storyboard has a linked frame for the segment, updates frame `image_prompt` too.
- `video_prompt_patch`
  - Writes `ProductionSegment.video_prompt`.
  - If run storyboard has a linked frame for the segment, updates frame `video_prompt` too.
- `edit_manifest_patch`
  - Merges allowed `after` fields into `VideoProductionRun.edit_manifest_json`.

Allowed patch fields by type:

- `script_patch`: `hook`, `beats`, `scene_outlines`, `visual_shots`, `notes`
- `storyboard_patch`: `image_prompt`, `video_prompt`, `narration`, `duration`, `action`, `emotion`, `shot_type`, `continuity_notes`, `reference_urls`
- `image_prompt_patch`: `image_prompt`, `negative_prompt`, `reference_instructions`
- `video_prompt_patch`: `video_prompt`, `duration`, `continuity_notes`, `expected_end_state`
- `edit_manifest_patch`: `subtitle_style`, `bgm_policy`, `intro_outro`, `watermark`, `output_spec`, `rhythm_notes`

### `agency_persistence.py`

Extend `finalize_invocation_and_audit()`:

- Keep current repair task classification.
- After saving invocation output, call creative patch extraction.
- Store created patch IDs in the audit payload.
- Do not auto-apply patches.

### `agency_runtime.py`

Extend the expert output schema:

- Add optional `creative_patches` array.
- Keep existing required fields unchanged for compatibility.
- Redact secrets from creative patch payloads using current redaction path.

### `agency_prompting.py`

Update expert prompt instructions:

- Experts should return `creative_patches` when they can improve a script, storyboard, prompt, or edit manifest.
- Experts must put executable rewrites in `creative_patches.after`, not only in `recommendations`.
- Experts must not invent target IDs.
- Experts must not include secrets or raw provider payloads.

## Pixelle Preflight Gate

Add a creative workbench gate before paid provider submission.

The gate checks whether a run has unresolved required creative patches:

- Pending `proposed` or `edited` patches for the same run and stage block provider submission.
- `approved` patches should be applied before provider submission.
- `rejected` patches do not block.
- `applied` patches do not block.

Gate locations:

- Before image generation payload submission.
- Before video generation payload submission.
- Before compose submission.

Concrete integration points:

- `start_image_stage()`
- `start_video_stage()`
- `start_compose_stage()`
- worker path in `production_worker_service.py` for queued provider stages.

Blocked result:

- Run enters a review-required current stage.
- A `ProductionAuditEvent` records `agency_creative_patch_gate_blocked`.
- Frontend receives a repair/workbench route pointing to the director tab.

This changes the current behavior from "warning continues with old payload" to "unresolved creative rewrites must be resolved before paid generation".

## API Design

Add routes under `server/app/routers/agency.py`.

### `GET /api/agency/creative-patches`

Query parameters:

- `series_id`
- `run_id`
- `status`
- `stage`
- `target_type`
- `target_id`

Response:

```json
{
  "summary": {
    "total": 3,
    "pending": 2,
    "approved": 0,
    "applied": 1,
    "rejected": 0,
    "blocking": 2
  },
  "items": []
}
```

### `PATCH /api/agency/creative-patches/{patch_id}`

Updates editable `after_json`, `title`, or `reason` while status is `proposed` or `edited`.

### `POST /api/agency/creative-patches/{patch_id}/approve`

Marks a patch `approved`.

### `POST /api/agency/creative-patches/{patch_id}/reject`

Marks a patch `rejected` with a required reason.

### `POST /api/agency/creative-patches/{patch_id}/apply`

Applies one approved patch and marks it `applied`.

### `POST /api/agency/creative-patches/apply-approved`

Applies approved patches for a run or stage in safe order:

1. `script_patch`
2. `storyboard_patch`
3. `image_prompt_patch`
4. `video_prompt_patch`
5. `edit_manifest_patch`

### Existing API Extension

Extend `GET /api/series/{series_id}/agency-console` with:

```json
{
  "creative_patch_summary": {
    "total": 4,
    "pending": 2,
    "blocking": 2
  },
  "creative_patches": []
}
```

The console payload only returns compact patch summaries. The full patch list is loaded from the dedicated patch API.

## Frontend Workbench

Upgrade `web/src/views/AgencyConsolePage.vue` from a transparency console into a director workbench.

Tabs:

- `创作 Brief`
- `脚本/分镜`
- `提示词台`
- `剪辑与返修`
- `专家轨迹`

Phase 1 implements:

- Patch summary strip in the header.
- Patch list grouped by stage and target.
- Before/after diff for each patch.
- Editable `after` text/JSON fields with clear save action.
- Approve, reject, and apply actions.
- Link from a patch to the source expert invocation.
- Clear blocked state when Pixelle submission is waiting on patch approval.

UI principles:

- This is an operational tool, not a landing page.
- Use dense but readable panels.
- Keep cards only for individual patch items or modals.
- Keep stage navigation and patch status visible without a giant hero.
- Do not show raw API keys, provider raw payloads, or hidden prompt text.
- Use Chinese user-facing text.
- Do not rely on 3D expert visualization for core workflow controls.

Suggested components:

- `CreativePatchWorkbench.vue`
- `CreativePatchList.vue`
- `CreativePatchDiff.vue`
- `CreativePatchActions.vue`
- `CreativePatchSummaryStrip.vue`

API client additions:

- `listAgencyCreativePatches(params)`
- `updateAgencyCreativePatch(patchId, payload)`
- `approveAgencyCreativePatch(patchId)`
- `rejectAgencyCreativePatch(patchId, payload)`
- `applyAgencyCreativePatch(patchId)`
- `applyApprovedAgencyCreativePatches(payload)`

## Multimodal Review Phase

Phase 2 reuses the same patch lifecycle after real asset generation.

Inputs to multimodal experts:

- Controlled image or video asset URL.
- Thumbnail URL when available.
- Original prompt.
- Approved reference images.
- Shot metadata.
- Review status.
- Continuity notes.
- Edit manifest context for compose review.

Outputs:

- `image_prompt_patch` for image regeneration.
- `video_prompt_patch` for segment regeneration.
- `storyboard_patch` when the shot itself is wrong.
- `edit_manifest_patch` for subtitle, BGM, rhythm, intro/outro, watermark, or output spec changes.
- `repair_tasks` only when an actual provider retry or manual repair action is needed.

This closes the visual quality gap: experts must look at actual artifacts before judging identity consistency, visual impact, and short-video feel.

## Security And Cost Boundaries

- Expert output is untrusted model output.
- Creative patches can update only whitelisted fields.
- Target IDs must exist and belong to the scoped series/run.
- Experts cannot create arbitrary provider calls.
- Experts cannot add unknown URLs into controlled production data.
- Patch approval is required before apply.
- Paid provider calls remain behind existing provider configuration, budget, and worker safety gates.
- API keys and secrets must be redacted from expert prompts, traces, patch payloads, audit events, and frontend payloads.
- Rejected or unapplied patches must not affect Pixelle payloads.

## Error Handling

- Invalid patch payload: store the invocation, skip the bad patch, record validation error in audit event.
- Missing target: convert patch into non-blocking invalid patch audit, do not create operational row.
- Patch apply conflict: return `409` and keep patch `approved`.
- Already applied patch: idempotently return current applied state.
- Rejected patch apply attempt: return `409`.
- Pixelle gate blocked by pending patches: return a repairable production error with route to the director workbench.
- Workbench API failures: show a concise Chinese error and preserve current patch state.

## Testing

Backend tests:

- Expert runtime accepts optional `creative_patches`.
- Invalid patch types are rejected.
- Valid expert output creates `AgencyCreativePatch` rows.
- Missing or cross-series targets do not create operational patches.
- Approving a patch does not mutate production data.
- Applying `storyboard_patch` updates `Episode.storyboard_json`.
- Applying `image_prompt_patch` updates `ProductionSegment.image_prompt`.
- Applying `video_prompt_patch` updates `ProductionSegment.video_prompt`.
- Applying `edit_manifest_patch` updates `VideoProductionRun.edit_manifest_json`.
- Pixelle image stage blocks when pending required patches exist.
- Pixelle video stage blocks when pending required patches exist.
- Compose preflight blocks when pending edit manifest patches exist.
- Applied or rejected patches do not block Pixelle submission.
- Audit events are recorded for create, edit, approve, reject, apply, and gate block.

Frontend tests:

- Agency console shows the creative patch summary.
- Director workbench tab renders patch list.
- Patch diff shows before and after values.
- Editing a patch calls the update API.
- Approving a patch updates status.
- Applying an approved patch calls the apply API.
- Pending blocking patches show a Pixelle preflight warning.
- Rejected patches no longer show as blocking.
- User-facing copy remains Chinese and does not show raw provider fields.

gstack verification after implementation:

- Start backend and frontend dev servers.
- Open the agency console route in the browser.
- Verify workbench tabs render.
- Verify patch list and diff interaction.
- Check console errors.
- Capture desktop and mobile screenshots.
- Verify no text overlap in patch cards, tabs, or action buttons.

## Rollout

### Phase 1: Creative Patch Loop

- Add patch contracts and table.
- Extend expert output parsing and prompting.
- Persist patch proposals from invocations.
- Add patch API.
- Add apply service for script, storyboard, prompt, and edit manifest patches.
- Add Pixelle preflight gate.
- Upgrade agency console into a director workbench.
- Add focused backend and frontend tests.
- Verify with gstack/browser.

### Phase 2: Multimodal Asset Repair

- Extend asset review context with media URLs and thumbnails.
- Route multimodal expert outputs into the same patch table.
- Add regeneration actions that use applied prompt patches.
- Show real asset evidence in the workbench.
- Add multimodal-specific tests and smoke checks.

### Phase 3: Production Refinement

- Add batch approve/apply for trusted internal runs.
- Add patch version comparison across attempts.
- Add workbench filters for target audience, account style, platform goal, and taboo rules.
- Add metrics for patch acceptance rate, generation cost avoided, and post-generation repair rate.

## Success Criteria

Phase 1 is successful when:

- Experts can return `creative_patches` without breaking existing invocation parsing.
- Valid patches become queryable workbench rows.
- Professional users can edit, approve, reject, and apply patches.
- Applied patches write back to actual production data used by Pixelle payload builders.
- Pending patches block paid Pixelle image, video, or compose submission.
- Rejected and applied patches do not block.
- Agency console exposes the director workbench controls.
- Tests prove patch lifecycle, apply behavior, and preflight blocking.
- Browser QA proves the workbench is usable on desktop and mobile.

The full objective is successful only after Phase 2 also proves that generated real image and video assets can be reviewed by multimodal experts and converted into new prompt, shot, or edit manifest patches instead of plain advice.

## Spec Self-Review

- Placeholder scan: no unfinished markers or intentionally incomplete sections remain.
- Consistency check: the chosen architecture uses a dedicated table, patch service, API, workbench, and Pixelle preflight gate consistently.
- Scope check: Phase 1 is a coherent implementation slice; Phase 2 preserves the full end-state requirement for multimodal visual review.
- Ambiguity check: patch types, statuses, target types, apply behavior, gate locations, and tests are explicitly defined.
