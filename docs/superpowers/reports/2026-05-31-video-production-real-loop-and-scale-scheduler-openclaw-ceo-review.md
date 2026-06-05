# Video Production Real Loop And Scale Scheduler OpenClaw CEO Review

Review target: `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`

Review date: 2026-05-31

Mode: HOLD SCOPE

## CEO Review Summary

Status: approved after CEO hardening.

The plan is solving the right problem: dy_auto needs a trustworthy production closure point before more 3D console polish,
publishing, or long real-provider runs. The correct wedge is still:

```text
real 60-90 second one-sentence sample
  + mandatory image/video/final human gates
  + mock 240-minute scheduler stability proof
```

I did not expand scope. I added business success metrics, no-go conditions, and operational observability requirements so
the phase cannot ship as a hidden backend demo or a mock success that looks like a real production result.

## Premise Challenge

The core user outcome is not "run another pipeline". The outcome is: the user can enter one sentence, see every production
stage, review each gate, and end with a real approved video asset.

The plan is the most direct path because it separates two promises that must not be mixed:

- real short output proves provider integration and library writeback
- mock long-form scheduling proves scale, queue stability, and recovery without spending money

Doing nothing keeps the current product in the worst middle state: many modules exist, but the operator still cannot trust
that "one sentence to video" is visible, bounded, reviewable, and actually closed.

## Existing Code Leverage

The plan correctly avoids a rewrite:

- one-sentence entry reuses `one_sentence_video_service.py`
- production lifecycle reuses `video_production_service.py`
- stage guards reuse `video_production_state.py`
- queue stability reuses `production_queue_service.py`
- plan and segment shape reuse `production_plan_service.py` and `production_segment_service.py`
- monitor and review UI reuse `VideoProductionMonitorPage.vue` and `AIVideoReviewPage.vue`

CEO decision: no new dashboard, no new review table, no new media library table, no new provider client for this phase.

## Alternatives Considered

### A. Minimal Viable Closure

Effort: M. Risk: Medium.

Summary: only harden the 60-90 second real-short path and final human gate.

Pros:

- fastest path to a real output
- lowest implementation risk
- easier to QA

Cons:

- does not prove long-video scheduling stability
- leaves the 240-minute planning claim untested
- less useful for the user's stated long-form goal

### B. Current Plan

Effort: L. Risk: Medium.

Summary: real short sample plus mock 240-minute scheduler stability, both using current control-plane modules.

Pros:

- proves real provider closure and long-form scheduler stability separately
- keeps cost controlled
- uses the existing architecture

Cons:

- touches many files
- requires disciplined run-type enforcement
- needs strong test coverage to avoid mock/real confusion

### C. Ideal Long-Form Architecture Now

Effort: XL. Risk: High.

Summary: build real multi-episode provider execution, continuation frames, advanced role anchoring, and full long-form
asset orchestration now.

Pros:

- closest to the eventual 12-month product
- addresses long-form quality and continuity sooner
- reduces later rework if executed perfectly

Cons:

- too expensive and risky for this phase
- likely delays the first trustworthy real output
- increases provider-cost blast radius

Recommendation: choose B. It is the best current tradeoff: real value now, scale confidence now, and no fake promise of
real 240-minute generation.

## 12-Month Ideal

```text
Current state:
  Many production modules exist, but one-click video trust is incomplete.

This plan:
  Real short E2E proves provider integration, human gates, final writeback, and visible operation.
  Mock long-form proves queue scale, retry, resume, and monitor ergonomics.

12-month ideal:
  dy_auto can safely produce multi-episode long-form video with role anchors, staged review, cost governance,
  resumable provider execution, and clear library ownership.
```

This plan moves toward the 12-month ideal without pretending the full long-form product is already solved.

## Section Review

### 1. Architecture

Pass after hardening.

The architecture is correct only if run type is a hard backend boundary. The revised spec now requires an explicit
`VideoProductionRun.run_type` column, shared guards, and a shared readiness service.

### 2. Error And Rescue Map

Pass after hardening.

The original plan had good safety language but not enough named no-go conditions. The spec now names failure outcomes:
duration rejected before DB mutation, provider config blocked, budget blocked, provider preflight blocked, review gate
blocked, mock provider blocked, and final writeback blocked.

### 3. Security And Threat Model

Pass.

Main risks are provider secret leakage, mock actions crossing into real runs, and unbounded provider calls. Existing
redaction plus new run-type, budget, and provider preflight requirements are the right controls.

### 4. Data Flow And Interaction Edge Cases

Pass after hardening.

The plan now covers nil/invalid duration, missing provider config, budget exceeded, stale assets, rejected assets, mock
resume, expired leases, and final review rejection. Frontend must also handle slow sync and stale readiness after every
mutation.

### 5. Code Quality

Pass.

The danger is scattering `run_type` and readiness logic. The spec now requires one helper path for run type and one backend
service for readiness.

### 6. Tests

Pass after engineering review additions.

The implementation must include the real-short no-partial-row regression, AI-final-audit-does-not-complete regression,
mock-provider-never-called proof, and monitor bounded-payload test. Without these, this phase should not be accepted.

### 7. Observability

Previously under-specified. Fixed in the spec.

I added required audit events, bounded monitor counters, and a minimum runbook. This matters because the user explicitly
does not want dark-box production.

### 8. Database And State Management

Pass with one important constraint.

`run_type` must be a column, not only JSON. Mock assets need stable idempotency keys. Final writeback must reject mock
compose markers.

### 9. API Design And Contract

Pass.

The API can reuse existing routes, but every touched mutation response must include the same readiness block. The UI should
not infer stage safety from route names or raw statuses.

### 10. Performance And Scalability

Pass if bounded aggregate contract is implemented.

The mock 1440-segment shape is acceptable for local validation. The monitor must not load the full tree. Aggregates and
paginated drill-down are release blockers.

### 11. Design And UX

Pass after design review.

The design direction is right: existing three pages, Chinese labels, no garbled text, no hidden automation, visible stage
timeline, and clear mock/real badges.

## Strongest Challenges

1. Mock success can become a false proxy for real production success.
   Control: mock output cannot enter real library, and UI must label it as scheduling validation.

2. AI audit can erode trust if it silently completes production.
   Control: AI final audit is recommendation-only; human final approval is required.

3. The product can look done while the operator still cannot diagnose blocked runs.
   Control: readiness, audit events, bounded counters, and visible blocked reasons are acceptance requirements.

## Recommended Path

Implement in this order:

1. `run_type` migration and payload exposure.
2. shared readiness service.
3. real-short preflight and final human gate hardening.
4. mock-scale queue driver and idempotent mock assets.
5. frontend mode selector, Chinese labels, readiness display, monitor badges, and review-center separation.
6. mocked E2E and opt-in real provider smoke test.

## Accepted Scope

- real 60-90 second one-sentence sample
- mandatory human image, video, and final gates
- model-center provider use
- budget and retry caps
- explicit real/mock run type
- mock 240-minute scheduler stability
- bounded monitor and review visibility
- no dark-box production behavior

## Deferred

- real 3-5 minute provider E2E
- real 10-minute provider E2E
- real multi-episode provider execution
- advanced Seedance continuation-frame optimization
- automated approval policies
- publishing workflow

These are valid next steps, but not needed to prove this phase.

## Not In Scope

- 3D expert console redesign
- Douyin publishing
- real 240-minute provider execution
- real 240-minute final video file
- visual timeline editor
- standalone BI dashboard
- hidden automatic approval

## Final Verdict

Proceed with implementation after the revised spec. The plan is now strategically coherent: it proves the smallest real
thing users can trust while proving the long-form scheduler without uncontrolled cost.
