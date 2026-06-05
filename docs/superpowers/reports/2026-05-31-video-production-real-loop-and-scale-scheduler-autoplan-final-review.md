# Video Production Real Loop And Scale Scheduler Autoplan Final Review

Review target: `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`

Review date: 2026-05-31

Mode: automatic review pipeline with auto-decisions

Restore point: `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260531-002540.md`

## Plan Summary

The reviewed plan builds the next dy_auto video-production boundary:

```text
真实短片 60-90 秒真实闭环
  -> 人工图像审查
  -> 人工视频片段审查
  -> 人工终审入库

模拟长剧调度 240 分钟形态
  -> 不调用真实 provider
  -> 验证队列、租约、失败、重试、恢复和监控稳定性
```
UI scope: yes. The plan touches one-sentence entry, production monitor, and review center.

DX scope: yes. The plan introduces API contracts, migration behavior, readiness shape, named errors, provider smoke safety,
and local verification commands.

## Final Status

Status: approved for implementation after autoplan hardening.

There are no user challenges. No review phase found a reason to change the user's stated direction. The most important
autoplan decision is to hold scope, not expand:

- no 3D expert console work
- no Douyin publishing
- no real 240-minute provider execution
- no visual editor
- no automatic approval

## Phase 1 CEO Review

Decision: keep the current two-track scope.

Premises accepted:

- one real 60-90 second sample is the right first value proof
- 240-minute work should be a scheduler drill, not a real provider run
- human gates are product trust, not friction
- dy_auto should remain the control plane and reuse existing modules

What was hardened:

- product success metrics
- no-go conditions
- visible operator trust requirements
- operational observability as a product deliverable

CEO consensus:

| Dimension | Result |
|---|---|
| Premises valid | Confirmed |
| Right problem | Confirmed |
| Scope calibration | Confirmed |
| Alternatives explored | Confirmed |
| Six-month direction | Confirmed |
| Expansion needed now | Rejected |

Independent voice status: Codex CLI timed out during the combined read-only challenge, so autoplan continued with prior
specialized review artifacts and primary analysis. No issue was hidden by this degradation.

## Phase 2 Design Review

Decision: reuse existing UI surfaces and make production visible.

Existing UI audit found:

- one-sentence page has garbled text and English gate labels
- monitor has English primary labels
- review page has English primary labels
- tests currently assert some English labels

What was hardened:

- shared design rules
- Chinese valid UTF-8 copy requirement
- no garbled text on touched controls
- `真实短片` and `模拟长剧调度` badges
- visible stage timeline
- monitor first-viewport health strip
- review center separation for image, video segment, and final review
- responsive overflow and accessibility test requirements

Design consensus:

| Dimension | Result |
|---|---|
| Information architecture | Confirmed after two-mode selector |
| Stage visibility | Confirmed after readiness and blocked reasons |
| Review clarity | Confirmed after review-center separation |
| Language quality | Confirmed with Chinese/no-garbled-copy tests |
| Responsive strategy | Confirmed with overflow and pagination requirements |

## Phase 3 Engineering Review

Decision: make real/mock safety a backend invariant.

Critical findings resolved in the spec:

| Finding | Resolution |
|---|---|
| `VideoProductionRun` lacked explicit `run_type` | add indexed column and helper functions |
| AI final audit could complete a run | make AI audit recommendation-only |
| one-sentence duration allowed long runs | reject invalid real-short duration before DB mutation |
| queue lacked completion primitive | add `mark_job_completed` |
| bulk review did not know run type | restrict mock shortcuts to `mock_series_scale` |

Architecture shape:

```text
video_production.py routes
  -> one_sentence_video_service / mock_scale_service
  -> video_production_readiness_service
  -> video_production_state guards
  -> video_production_service stage executors
  -> production_queue_service
  -> production_tree_service / production_status_aggregation
```

Engineering consensus:

| Dimension | Result |
|---|---|
| Architecture | Confirmed after explicit run type and readiness service |
| Test coverage | Confirmed after expanded backend/frontend/E2E requirements |
| Performance | Confirmed with bounded aggregates plus pagination |
| Security | Confirmed with provider preflight and secret redaction |
| Error paths | Confirmed with named repairable errors |
| Deployment risk | Manageable if implementation follows sequence |

## Phase 3.5 DX Review

Decision: add developer-experience requirements because the phase changes APIs, migrations, errors, and local verification.

What was hardened:

- migration and rollback expectation for `run_type`
- required model-center scene keys
- readiness happy-path and blocked-path examples
- named error fields: code, message, cause, repair action, route, affected ids, retryable
- mock-scale seed and failure profile examples
- opt-in provider smoke safety checklist
- local verification time targets

DX score:

| Dimension | Before | After |
|---|---:|---:|
| Local verification | 6 | 8 |
| Error actionability | 7 | 9 |
| API contract clarity | 7 | 8.5 |
| Provider safety | 8 | 9 |
| Migration clarity | 6 | 8 |
| Debuggability | 7 | 9 |
| Documentation completeness | 6 | 8 |
| Onboarding for implementer | 6 | 8 |

Target time-to-verify:

- unit test slice under 5 minutes
- mocked real-short E2E under 10 minutes
- mock-scale scheduler E2E under 15 minutes

## Cross-Phase Themes

| Theme | Phases | Action |
|---|---|---|
| No hidden automation | CEO, Design, Eng, DX | readiness, audit events, visible gates |
| Real and mock must never blur | CEO, Eng, Design | `run_type`, mock labels, backend guards |
| Human final approval is mandatory | CEO, Eng | AI audit recommendation-only, final guard |
| Monitor must be bounded | Design, Eng, Performance | aggregates plus paginated tree |
| Errors must be repairable | Eng, DX | named errors and repair routes |

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Hold scope on real-short plus mock-scale | Auto | Focus as subtraction | This proves value and stability without uncontrolled cost | Real long-provider execution now |
| 2 | CEO | Add no-go conditions | Auto | Choose completeness | Prevents fake completion or hidden unsafe behavior | Soft acceptance wording |
| 3 | Design | Reuse existing three UI surfaces | Auto | DRY | Existing pages match the workflow | New dashboard shell |
| 4 | Design | Require Chinese/no-garbled primary copy | Auto | Explicit over clever | Operator trust requires readable UI | Raw English production labels |
| 5 | Eng | Require explicit `run_type` column | Auto | Explicit over clever | JSON-only mode is unsafe for enforcement | Infer mode from route or trace JSON |
| 6 | Eng | Make AI final audit recommendation-only | Auto | Choose completeness | User required human gates | AI audit auto-completion |
| 7 | Eng | Add shared readiness service | Auto | DRY | Prevents divergent route payloads | Per-route readiness builders |
| 8 | Eng | Add queue completion primitive | Auto | Explicit over clever | Mock scheduler must exercise queue lifecycle | Direct job status edits |
| 9 | DX | Add verification and error-contract requirements | Auto | Bias toward action | Implementers need fast local confidence | Leave commands and errors implicit |

## Final Gate

Recommendation: approve as-is and proceed to implementation planning.

User challenges: none.

Taste decisions: none requiring user input. The plan is deliberately scoped and already reflects the user's latest boundary:
build real one-click closure, review gates, and scheduler stability first.

Deferred after this phase:

- real 3-5 minute provider E2E
- real 10-minute provider E2E
- real multi-episode provider execution
- advanced Seedance continuation-frame optimization
- automated approval policies
- publishing workflow

## Completion

Autoplan review is complete. The spec is implementation-ready after the added success metrics, no-go conditions,
observability requirements, explicit engineering guards, test coverage requirements, and DX verification requirements.
