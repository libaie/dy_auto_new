# Video Production Real Loop And Scale Scheduler Autoplan Review

Review target: `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`

Review date: 2026-05-30

## Result

Status: approved after spec hardening.

The two-track direction is feasible and correctly bounded:

- real provider execution is limited to a 60-90 second short sample
- 240-minute production is a mock scheduling drill only
- human gates stay mandatory
- the existing dy_auto production control plane remains the implementation base

I revised the spec to close the main execution gaps: persisted `run_type`, hard real/mock enforcement, final human approval, readiness contract, aggregate monitor constraints, opt-in provider smoke rules, and Chinese UI copy requirements.

## Scope Challenge

Premise accepted: build the next phase around real one-click sample production plus mock long-form scheduling stability.

The original version had one dangerous ambiguity: the system could still interpret "one sentence to video" as a long real provider run because the current route accepts up to 14400 seconds. The revised spec now requires the real-short path to clamp 60-90 seconds before creating provider tasks, and routes longer requests into planning or mock scheduling.

No scope expansion is recommended. The out-of-scope list is strong and should remain binding.

## What Already Exists

| Capability | Existing code | Reuse decision |
|---|---|---|
| One-sentence entry | `server/app/services/one_sentence_video_service.py` | Reuse, but add real/mock mode and stricter duration gates. |
| Production run lifecycle | `server/app/services/video_production_service.py` | Reuse, add run-type and final human approval guards. |
| Stage gate checks | `server/app/services/video_production_state.py` | Reuse, add `assert_can_complete_final`. |
| Production tree | `server/app/services/production_plan_service.py` | Reuse, add deterministic mock-scale creation. |
| Queue leasing | `server/app/services/production_queue_service.py` | Reuse, add mock driver and failure injection around it. |
| Review records | `VideoReviewRecord` and review endpoints | Reuse, restrict bulk shortcuts by run type. |
| Monitor surface | `web/src/views/VideoProductionMonitorPage.vue` | Reuse, add Chinese labels, aggregates, run-type badges. |
| Cost events | `ProductionCostEvent` and cost summary service | Reuse, add preflight estimated next-cost readiness. |

## NOT In Scope

- 3D expert console polish: user explicitly paused it.
- real 240-minute provider execution: too costly and not needed for scheduler validation.
- automatic approval: violates the human gate requirement.
- Douyin publishing: not part of production quality closure.
- standalone BI dashboard: monitor aggregation is enough for this phase.
- visual timeline editor: not needed for one-click plus review-gated flow.

## CEO Review

Mode: hold scope with selective hardening.

Score: 8.5/10 before hardening, 9/10 after hardening.

Findings:

1. The dual-track plan is the right business wedge. It proves user value with a real short output while proving scale with mock scheduling.
2. The 240-minute target should stay a scheduling proof, not a media output promise.
3. "一键成片" needs visible human gates, not hidden automation. The revised readiness contract makes the process inspectable.
4. The biggest product risk is confusing mock success with real output. The revised run-type persistence and mock metadata rules close that gap.

CEO decision: proceed with the revised spec. No user challenge.

## Design Review

Initial score: 6.5/10.

Revised target score: 8/10.

| Dimension | Score | Issue | Required fix |
|---|---:|---|---|
| Information architecture | 8 | Real and mock paths were named but not operationally separated. | Add explicit run-type selection and badges. |
| Stage visibility | 8 | Stages exist but UI could still feel like autopilot magic. | Add readiness, next action, blocked reasons. |
| Review states | 8 | Image/video gates are visible, final gate needed stronger wording. | Autopilot must stop at final review too. |
| Language consistency | 5 | Current touched pages contain mojibake and English labels. | New controls must use Chinese; touched copy should be repaired. |
| Scale monitor | 7 | Segment tree pagination exists, but aggregate health strip is thin. | Add server aggregates for totals, queue, retry, failure, approval counts. |
| Error visibility | 7 | Provider errors can surface, but not as a readiness model. | Add structured blocked reasons and provider config status. |
| Mobile/operational ergonomics | 7 | Existing monitor has action bar but not mock/real distinction. | Add run-type label and next-action summary. |

Design decision: keep the existing pages and strengthen them. Do not create a new dashboard.

## Engineering Review

Initial score: 7/10.

Revised target score: 8.5/10.

### Architecture

```text
OneSentenceVideoPage
  -> /api/video-production/one-sentence or /one-sentence/start-real-short
    -> one_sentence_video_service
      -> production_run_service
        -> production_plan_service
        -> video_production_service
          -> video_production_state guards
          -> pixelle_stage_client / mock driver
          -> VideoProductionAsset + VideoReviewRecord
  -> VideoProductionMonitorPage
    -> run payload + readiness + tree aggregates + paged tree
```

### Main Engineering Findings

1. `run_type` is missing from `VideoProductionRun`.
   - Risk: mock drills can be mistaken for real runs, and route names become security boundaries.
   - Fix added to spec: persist run type and require every stage service to read it.

2. Current one-sentence request allows `target_duration_seconds <= 14400`.
   - Risk: real provider path can accidentally accept very long requests.
   - Fix added to spec: real-short clamps 60-90 seconds before creating tasks.

3. `run_final_audit_for_asset` can complete the run when AI final audit approves.
   - Risk: violates the requirement that final completion requires human approval.
   - Fix added to spec: AI audit is recommendation only in this phase; human final review is required for `completed`.

4. Bulk review endpoints currently do not know run type.
   - Risk: full mock shortcuts could be applied to real runs if implemented on the existing bulk path without checks.
   - Fix added to spec: mock bulk actions require `run_type = mock_series_scale`; normal real review endpoints stay separate.

5. Existing tree endpoint paginates segments, but top-level aggregate data is incomplete.
   - Risk: 1440-segment drill is hard to inspect and may push the UI toward loading too much detail.
   - Fix added to spec: aggregate monitor contract plus paged drill-down.

6. Cost enforcement exists as a helper but not yet as a stage preflight contract.
   - Risk: budget can be shown after the fact rather than blocking before provider submission.
   - Fix added to spec: readiness includes estimated next cost and stage guards enforce budget before submission.

### Failure Modes Registry

| Failure mode | Current protection | Gap | Required test |
|---|---|---|---|
| Real long request submits provider tasks | route allows long duration | critical | real-short rejects >90 before provider call |
| Mock run calls real provider | no persisted run type | critical | mock stage driver cannot call real clients |
| AI audit completes final video | current code can complete | critical | final human approval required for completed |
| Bulk mock approval touches real run | existing bulk review lacks run-type guard | high | bulk mock endpoint rejects real run |
| Resume duplicates assets | asset versioning exists | medium | mock resume creates no duplicate latest assets |
| Monitor loads full mock tree | pagination exists | medium | aggregate endpoint used for health strip |
| Provider secret stored in traces | redaction exists in runtime config | medium | provider response snapshots redact secrets |

Critical gaps after spec revision: 0 in the plan, implementation must cover all listed tests.

### Test Diagram

```text
real_short_e2e create
  -> duration/shot preflight tests
  -> provider config missing tests
  -> budget preflight tests
  -> image stage mocked success/failure tests
  -> human image approval gate tests
  -> video stage mocked success/failure tests
  -> human video approval gate tests
  -> compose mocked success tests
  -> final human approval tests

mock_series_scale create
  -> deterministic plan shape tests
  -> enqueue/lease/retry/lease-expiry tests
  -> deterministic failure injection tests
  -> resume idempotency tests
  -> mock bulk gate tests
  -> monitor aggregate and pagination tests
```

### Parallelization Strategy

| Lane | Modules touched | Depends on |
|---|---|---|
| A: run type and state guards | backend models, migrations, state service | none |
| B: real-short preflight and readiness | backend services, routes | A |
| C: mock-scale scheduler | backend services, tests | A |
| D: monitor and one-sentence UI | frontend views, API client | B and C payload contracts |
| E: E2E and regression tests | backend tests, frontend tests | A-D |

Recommended execution: A first, then B and C in parallel, then D, then E.

## DX Review

Product type: internal production platform with developer-facing APIs.

Initial score: 6/10.

Target score: 8/10.

Developer journey:

| Stage | Needed experience |
|---|---|
| Configure models | clear missing-model errors and scene keys |
| Start real short run | one request, bounded cost, visible readiness |
| Handle blocked provider config | error says what scene/model is missing |
| Review images | latest assets only, stale asset protection |
| Review videos | same review semantics as image gate |
| Compose | only after video approvals |
| Final approve | human action creates library asset |
| Start mock scale | deterministic options and mock label |
| Debug scale run | aggregate status, paged tree, failures, retry state |

DX fixes required by the spec:

- `readiness` endpoint returns problem, cause, fix, and next actions.
- provider smoke tests are opt-in with env flag and budget caps.
- API names can reuse current routes, but payloads must expose `run_type`.
- docs or implementation plan must include copy-paste test commands.

## Decision Audit Trail

| # | Phase | Decision | Classification | Rationale | Rejected |
|---|---|---|---|---|---|
| 1 | CEO | Keep dual-track scope | auto-decided | Real short proves value, mock scale proves stability without cost. | Real 240-minute provider execution |
| 2 | Design | Reuse current pages | auto-decided | Existing page structure matches workflow and avoids dashboard sprawl. | New standalone BI/dashboard |
| 3 | Eng | Persist run type | auto-decided | Route names and UI modes are not safe enforcement boundaries. | Infer mode from endpoint |
| 4 | Eng | Require human final approval | auto-decided | User explicitly wants review gates; AI audit can only recommend. | AI audit auto-completes run |
| 5 | Eng | Prefer route reuse with explicit payloads | auto-decided | Current route surface already owns lifecycle and tests. | Duplicate parallel route stack |
| 6 | DX | Add readiness contract | auto-decided | Operators need problem, cause, fix, and next allowed action. | UI-only disabled buttons |

## GSTACK Review Report

| Review | Status | Findings |
|---|---|---|
| CEO Review | clear after revision | scope held, 4 product findings, 0 user challenges |
| Design Review | clear after revision | 7 dimensions reviewed, Chinese copy and aggregate monitor added |
| Eng Review | clear after revision | 6 issues found, all converted into spec requirements |
| DX Review | clear after revision | readiness contract and smoke-test safety added |

Outside voices: not spawned in this run because the current tool policy requires an explicit sub-agent/delegation request from the user. The review still followed the autoplan phase order locally.

## Final Approval Gate

No user challenges.

No taste decisions require a pause before implementation.

The spec is ready for a detailed implementation plan.
