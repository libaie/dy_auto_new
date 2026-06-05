# Video Production Real Loop And Scale Scheduler Autoplan Plan Review

Review target: `docs/superpowers/plans/2026-05-31-video-production-real-loop-and-scale-scheduler.md`

Review date: 2026-05-31

Reviewer mode: `/autoplan`

## Verdict

Status: approved after plan corrections.

The plan remains aligned with the user's latest boundary: pause 3D expert-console work, build real one-click short-video closure, enforce visible review gates, and prove long-video scheduler stability without real provider spend.

Autoplan found eight actionable plan risks. All were patched into the plan as explicit implementation steps, tests, or execution rules.

## Corrections Applied

1. P0 unknown `run_type` bypass: added `validate_run_type`, route-level structured 400 handling, malformed persisted-value rejection, and zero-row tests.
2. P1 long-form promise mismatch: mock scale now defaults to 240 minutes and must accept at least 480 minutes for stress testing.
3. P1 run-type policy ambiguity: added a run-type action matrix covering real, mock, and legacy behavior.
4. P1 scheduler stability gap: added tests for expired leases, retry-wait jobs, pause/resume, partial completion, and provider-call count zero.
5. P1 review gate UI ambiguity: added visible gate tabs with counts and route sync.
6. P2 final bulk approval risk: bulk approval now hides when the active gate is final or any loaded item is `final_video`.
7. P1 frontend test append risk: changed test instructions to update existing mocks/imports in place.
8. P1 dirty-worktree staging risk: final commit now uses an exact owned file list.

## Scope Decision

No scope expansion beyond the current phase was accepted. The plan still excludes:

- 3D expert console enhancements.
- Douyin publishing.
- Visual timeline editing.
- Automatic final approval.
- Real provider execution for 240-minute runs.
- New scheduler infrastructure.

## Dual Voice Note

Codex CLI ran in read-only mode as the independent outside voice. Subagent voice was not spawned because the current tool policy only allows spawning when the user explicitly asks for subagents or parallel agent work.

## Implementation Readiness

Ready to implement after this review. The next implementation pass must follow the task order and should not skip the new validation, gate-count, mock-scheduler stability, and exact-staging requirements.
