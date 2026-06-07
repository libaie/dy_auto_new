# Series Continuity and AI Text Artifact Transparency Plan CEO Review

Date: 2026-06-08

Skill used:

- `plan-ceo-review`

Spec reviewed:

- `docs/superpowers/specs/2026-06-08-series-continuity-ai-artifact-transparency-design.md`

Mode: `SELECTIVE_EXPANSION`

Rationale: the user approved the baseline scope, and the plan touches product experience, persistence, APIs, and UI. The review holds the approved scope while auto-accepting small blast-radius additions that make the plan safer.

## Step 0: Premise Challenge

The right problem is not "why did one button label change?" The real problem is that the system can represent a multi-episode promise while persisting only a single production target, then hide most AI text decisions from the user. Fixing only the button text would preserve the underlying trust failure.

User/business outcome:

- Users see that a series is actually a series.
- Users can inspect, edit, regenerate, and approve the AI decisions that shape plot and production.
- Production runs are reproducible because they bind exact text artifact versions.

Doing nothing keeps the current failure mode: a 30-episode series can look complete after one episode, and the user cannot trace or correct upstream AI text.

## Existing Code Leverage

| Sub-problem | Existing leverage |
| --- | --- |
| Episode placeholders | Normal `POST /api/series` flow already creates all episodes. |
| Structured script persistence | `EpisodeScript`, `ScriptDramaticBeat`, `ScriptSceneOutline`, `ScriptVisualShot`. |
| Text snapshots | `Series.story_bible_json`, `Episode.script_json`, `Episode.storyboard_json`, `PipelineRun.layers_json`. |
| Expert trace | `AgencyExpertInvocation`, agency console, repair traces. |
| Prompt/edit patching | `AgencyCreativePatch` and CreativePatch workbench. |
| Production binding | `VideoProductionRun`, `ProductionPlan`, `ProductionSegment` metadata can be extended. |

The plan correctly reuses these instead of creating a parallel AI runtime.

## Alternatives Reviewed

| Approach | Effort | Risk | Pros | Cons | Decision |
| --- | --- | --- | --- | --- | --- |
| Minimal repair only | S | Medium | Quick; fixes E02 button; few files. | Leaves AI text as black box; continuity still weak. | Rejected. Too small for the user's request. |
| Planned series plus pilot-first production | L | Medium | Creates full series plan, preserves cost control, supports traceability. | Requires data model, APIs, UI, migrations. | Accepted. |
| Render all episodes automatically | XL | High | Maximizes automation. | Expensive, long-running, risky, likely wrong before review. | Rejected for v1. |

## Review Sections

### 1. Architecture

The architecture is directionally correct: add a universal artifact ledger while keeping compatibility snapshots. The main architectural risk is allowing `ai_text_artifacts` to become a vague dump table. The spec mitigates this with typed `artifact_type`, lineage, status, and consumer bindings.

Decision: keep the ledger, but require typed validators or serializers per artifact type during implementation.

### 2. Error and Rescue Map

The spec includes strong user-facing errors for missing placeholders, missing plans, stale scripts, and stale prompts. Two missing paths need to be added:

- planning AI generation failure
- concurrent approval conflict

Decision: amend the spec with explicit error codes and rescue actions.

### 3. Security and Threat Model

Manual text edits, AI regeneration, and approval change production inputs. These actions need authorization, audit logging, and prompt-injection hygiene. User-edited text should be treated as content, not trusted instructions for system/tool behavior.

Decision: amend the spec with auth and audit rules for edit/regenerate/approve/reject.

### 4. Data Flow and Interaction Edge Cases

Happy path is clear: series plan -> approved artifacts -> episode context -> production run -> bound consumers. Shadow paths need explicit handling for empty output, malformed JSON, stale parent, slow regeneration, double click, and navigate-away.

Decision: amend the spec with idempotency and optimistic concurrency requirements.

### 5. Code Quality

The plan is large but not speculative. The scope maps directly to the user's two complaints: missing episodes and hidden AI outputs. The proposed services are separable and fit existing boundaries.

Decision: keep service split, but avoid building a generic workflow engine in v1.

### 6. Test Review

The acceptance tests are good. Add missing tests for:

- concurrent approval race
- idempotent production start
- permission failure for manual edit/approval
- artifact list pagination
- migration dry run

Decision: amend the acceptance criteria.

### 7. Observability

Traceability is product-facing, but operators also need metrics: missing placeholder repairs, artifact generations, approval latency, stale downstream counts, production starts blocked by missing artifacts, and migration results.

Decision: amend the spec with observability and runbook requirements.

### 8. Database and State Management

The model handles versioning and consumers. The risky part is "one active approved version" if enforced only in application code. Use DB enforcement where available, with application fallback where dialect limitations apply.

Decision: amend constraints with optimistic locking and DB-level enforcement where safe.

### 9. API Contract

The endpoint list is appropriate. Add pagination, filters, diff, and idempotency keys.

Decision: amend API design.

### 10. Performance and Scalability

A 30-episode series can produce hundreds of artifacts. The plan must avoid rendering the full artifact tree eagerly.

Decision: amend frontend/API with pagination and lazy loading.

### 11. Design and UX

The proposed hierarchy is right: the series page answers "what episode is next?" while the workbench answers "what did AI produce and what version is approved?" Add empty/loading/error states and responsive behavior to the UI requirements.

Decision: amend frontend design.

## CEO Review Summary

Status: `DONE_WITH_CONCERNS`, expected to become `CLEAR` after accepted amendments are applied.

Strongest challenges:

1. Artifact edits and approvals need authorization, audit, and concurrency controls.
2. Production traceability must be backed by exact consumer bindings, not screenshots or summaries.
3. The UI must not eagerly load the full artifact universe for a 30-episode series.

Recommended path:

- Keep the approved "planned series plus pilot-first production" approach.
- Apply the amendments above before implementation planning.
- Move implementation through a staged plan, starting with placeholder repair and artifact ledger foundations.

Accepted scope:

- Multi-episode placeholder repair and correct completion semantics.
- Versioned AI text artifact ledger.
- Manual edit, AI regenerate, approve, reject, lineage, stale state.
- Production run artifact binding.
- Series detail, series plan, artifact workbench, production monitor updates.

Deferred:

- Rendering every episode automatically.
- Replacing the existing script pipeline tables.
- Building a separate AI provider runtime.

Not in scope:

- A new all-purpose workflow engine.
- Provider-specific prompt injection sandboxing beyond treating user text as untrusted content.

Follow-up: accepted amendments were applied to the spec on 2026-06-08. Current status: `CLEAR`.
