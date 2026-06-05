# Video Production Real Loop And Scale Scheduler Design Review

Review target: `docs/superpowers/specs/2026-05-30-video-production-real-loop-and-scale-scheduler-design.md`

Review date: 2026-05-31

Reviewer mode: product design review

## Result

Status: approved after design hardening.

The plan is feasible for the next phase: real one-sentence short video closure plus mock long-form scheduling stability.
The design risk was not the workflow itself, but whether the operator could actually see what the system was doing. I
revised the spec to make the production process visible, Chinese, review-gated, and testable across the one-sentence page,
production monitor, and review center.

Implementation should proceed against the revised design contract. Do not treat the current English or mojibake page copy
as acceptable baseline behavior for this phase.

## Current UI Audit

Observed code:

- `web/src/views/OneSentenceVideoPage.vue`
- `web/src/views/VideoProductionMonitorPage.vue`
- `web/src/views/AIVideoReviewPage.vue`
- `web/src/views/ImageCreationPage.vue`
- related frontend tests under `web/src/__tests__`

Findings:

1. The one-sentence page currently contains mojibake Chinese text and English gate labels such as `Image review gate`,
   `Video review gate`, and `Final review gate`.
2. The production monitor currently uses English primary labels such as `Production Run Control Room`, `Run Health`,
   `Exception Queue`, `Sync Images`, `Start Video Segments`, and `Open Review Center`.
3. The AI video review page currently uses English primary labels such as `AI Video Review`, `Pending review`, `Bulk
   approve`, and `Approve latest`.
4. Existing tests still assert several English production labels, so implementation must update tests instead of preserving
   the old wording.
5. `ImageCreationPage.vue` already has useful Chinese review-state precedent, including `待审`, `已通过`, `阻断/驳回`, and
   `审查状态`. This should be reused as the local style direction.
6. No project-level `DESIGN.md` was found in the docs tree during this pass, so the revised spec now carries the binding UI
   rules for this phase.

## Design Decisions

1. Reuse the existing three surfaces: one-sentence entry, production monitor, and review center. A new dashboard page is not
   needed for this phase.
2. Add a top-level two-mode selector on the one-sentence page: `真实短片` and `模拟长剧调度`.
3. Make all touched production copy Chinese and valid UTF-8. Raw ids can remain as secondary debug text only.
4. Treat the review page as a first-class review center, not a generic AI audit list.
5. Require the monitor to show aggregate health first, with paginated drill-down for long mock runs.
6. Use explicit run-type badges everywhere a production run is shown.

## Required Spec Changes Applied

The spec now includes:

- shared design rules for production surfaces
- Chinese copy and no-mojibake requirements
- run-type badge labels for `真实短片` and `模拟长剧调度`
- semantic status colors for approved, waiting, running, failed, and mock states
- accessibility requirements for live readiness changes and keyboard navigation
- one-sentence mode-specific field requirements
- visible Chinese production timeline stages
- production monitor first-viewport dashboard requirements
- mock drill warning banner requirements
- segment detail panel requirements
- review center queue grouping and gate-specific controls
- frontend tests for Chinese copy, no mojibake, run-type badges, review center separation, and responsive overflow

## Scorecard

| Dimension | Before | After | Notes |
|---|---:|---:|---|
| Information architecture | 7 | 9 | Two explicit modes and three reused surfaces are now clear. |
| Production state visibility | 6 | 8.5 | Readiness, current gate, next action, and blocked reasons are required. |
| Operator journey | 7 | 8.5 | One-sentence entry, monitor, and review center are now linked by visible actions. |
| Review gate clarity | 6 | 9 | Image, video, and final review must be distinct. |
| Language quality | 5 | 8 | Chinese copy and no mojibake are now testable. |
| Design system consistency | 6 | 8 | Semantic colors and run-type badges are defined. |
| Scale ergonomics | 6 | 8.5 | Aggregates plus paginated tree avoid a 1440-segment client payload. |
| Accessibility and responsive behavior | 6 | 8 | Live regions, keyboard navigation, wrapping, and overflow tests are required. |

## What Is Not In Scope

- 3D expert console redesign
- visual timeline editor
- new BI dashboard
- publishing workflow
- real 240-minute provider execution
- marketing-style landing page

## Implementation Guidance

Keep the UI work surgical:

1. Repair only the touched production copy in the relevant pages.
2. Preserve the current operational dark interface direction unless a component actively fails clarity or responsiveness.
3. Prefer existing API surfaces and add readiness/run-type fields rather than building another parallel UI stack.
4. Update frontend tests to assert the intended Chinese operator language.
5. Use the image creation page's Chinese review-state wording as the local precedent.

## Completion Summary

Design review is complete. The plan is approved after hardening, with no unresolved design decisions. The remaining work is
implementation and verification against the revised spec.
