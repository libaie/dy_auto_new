# Video Production Real Loop And Scale Scheduler Plan Engineering Review

Review target: `docs/superpowers/plans/2026-05-31-video-production-real-loop-and-scale-scheduler.md`

Review date: 2026-05-31

Reviewer mode: `/plan-eng-review`

## Verdict

Status: approved after plan hardening.

This implementation plan is feasible and appropriately scoped for the current project boundary: real one-click short-video closure, explicit review gates, and a mock long-form scheduler for scale stability. I revised the plan to close the engineering gaps that could have caused flaky implementation or unsafe run-type crossover.

No implementation-blocking engineering issue remains in the plan. This review did not claim business code is complete; it only reviewed and corrected the implementation plan.

## Findings Fixed

1. P1, mock scheduler could lease work from another active plan.

   The original `run_mock_scheduler_step` called `claim_next_job` globally, then broke if the leased job belonged to a different plan. That still left the wrong job leased. The plan now requires `claim_next_job(plan_id=...)` and adds a queue test for plan-scoped claiming.

2. P1, mock run creation could commit partial queue rows before the run existed.

   The original mock service snippet called `enqueue_job`, whose existing implementation commits by default, while still building the series, episode, production plan, segments, and run. The plan now requires `enqueue_job(commit=False)` and one outer commit from `create_mock_scale_run`.

3. P2, mock scheduler service snippet missed `ProductionJob`.

   `run_mock_scheduler_step` queries remaining jobs through `ProductionJob`, but the import list omitted it. The plan now includes the import.

4. P2, provider stage guard snippet missed `LEGACY_EPISODE_RUN`.

   The assertion allowed `LEGACY_EPISODE_RUN`, but the import only showed `REAL_SHORT_E2E`. The plan now imports both and explicitly documents that legacy runs remain compatible while mock scale runs are blocked.

5. P2, queue tests covered completion but not the new transaction and scoping contracts.

   Task 5 now requires tests for `enqueue_job(commit=False)` and `claim_next_job(plan_id=...)`, not only `mark_job_completed`.

## Scope Challenge

Scope is held. The plan touches many files, but that is expected because the feature crosses persisted run type, stage execution, review gates, queue lifecycle, monitor payloads, and three frontend surfaces.

No new scheduler runtime, media table, review table, design system, visual editor, publishing flow, or 3D expert console work should be added in this phase.

## Architecture Notes

Real short path:

```text
one-sentence request
  -> validate run_type + duration + budget before DB writes
  -> real staged provider execution
  -> image human gate
  -> video human gate
  -> compose
  -> AI final audit recommendation
  -> final human approval
  -> Episode + GeneratedVideo writeback
```

Mock scale path:

```text
mock one-sentence request
  -> build mock production plan and segments
  -> enqueue jobs with commit=False
  -> commit run atomically
  -> worker step claims by plan_id
  -> complete queue and segment records
  -> monitor reads bounded readiness and paginated tree
```

## Required Verification During Implementation

- Run the added queue tests before Task 6 begins.
- Keep real provider calls guarded by `run_type`.
- Keep final AI audit recommendation-only.
- Keep mock scale provider-free.
- Run the focused backend, frontend, mocked E2E, migration, mojibake, and placeholder scans listed in Task 13 before final commit.

## Result

The plan is engineering-ready after the documented corrections. Proceed with implementation using the task order in the plan.
