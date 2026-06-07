# Series Continuity and AI Text Artifact Transparency Test Plan

Date: 2026-06-08

Related spec:

- `docs/superpowers/specs/2026-06-08-series-continuity-ai-artifact-transparency-design.md`

## Coverage Diagram

```text
One-sentence input
  |
  +-- create Series(total_episodes=N)
  |     |
  |     +-- ensure Episode placeholders E01..EN
  |     |     +-- [unit] count, idempotency, existing repair
  |     |
  |     +-- generate/approve series_bible
  |     |     +-- [unit] artifact versioning
  |     |     +-- [integration] model trace captured
  |     |
  |     +-- generate/approve episode outlines
  |           +-- [unit] N outlines match target count
  |           +-- [integration] continuity fields present
  |
  +-- start production for episode K
        |
        +-- assemble approved context
        |     +-- [unit] missing bible/outline/handoff blocks
        |     +-- [unit] E02 requires E01 handoff
        |
        +-- bind consumed artifact versions
        |     +-- [unit] consumer rows created
        |     +-- [integration] run response shows versions
        |
        +-- manual edit / regenerate
              +-- [unit] new version, old version preserved
              +-- [unit] downstream stale propagation
              +-- [frontend] workbench actions and diff
```

## Backend Tests

| Test | Type | Purpose |
| --- | --- | --- |
| `test_one_sentence_creates_series_episode_placeholders` | unit/integration | One-sentence path creates E01..EN. |
| `test_completed_pilot_does_not_complete_series` | unit | E01 done does not mark a 30-episode series complete. |
| `test_missing_placeholders_repair_is_idempotent` | unit | Repair can run repeatedly without duplicates. |
| `test_start_production_requires_approved_text_artifacts` | unit | Production blocks on missing/unapproved artifacts. |
| `test_episode_generation_context_requires_previous_handoff_for_episode_2` | unit | E02+ requires previous summary and character state. |
| `test_manual_edit_creates_new_artifact_version` | unit | Manual edit preserves parent and creates child version. |
| `test_regenerate_creates_child_artifact_version` | unit | AI regeneration records input/output/model trace. |
| `test_approve_script_marks_storyboard_and_prompts_stale` | unit | Downstream stale propagation works. |
| `test_video_run_binds_consumed_artifact_versions` | integration | Run records exact artifact consumers. |
| `test_concurrent_approval_allows_one_active_approved_version` | unit/integration | Race condition does not create two active approved versions. |
| `test_artifact_mutation_requires_authorization` | API | Edit/approve/regenerate reject unauthorized actors. |
| `test_artifact_list_paginates_large_series` | API | 30-episode artifact trees are paginated. |
| `test_migration_dry_run_reports_repairs_without_mutating` | migration | Dry run reports what would change. |
| `test_migration_backfill_creates_artifacts_from_snapshots` | migration | Existing snapshots become traceable artifacts. |

## Frontend Tests

| Test | Purpose |
| --- | --- |
| `series-detail-agency` | E01 done with total 30 shows `生成第 2 集`. |
| `series-detail-agency` | Missing placeholders shows `补齐剧集占位`. |
| `series-plan-page` | Shows bible, outlines, continuity ledger, approval states. |
| `series-plan-page` | Handles loading, empty, error, and partial planning states. |
| `ai-text-artifact-workbench` | Shows version history, diff, edit, regenerate, approve, reject. |
| `ai-text-artifact-workbench` | Shows stale downstream actions. |
| `video-production-monitor-page` | Shows consumed artifact versions for a run. |

## Manual Verification

1. Create a one-sentence 30-episode series.
2. Confirm the database has 30 `Episode` rows.
3. Produce E01 only.
4. Confirm the series page shows `生成第 2 集`, not `全部剧集已完成`.
5. Open the artifact workbench and inspect the AI input/output/model trace.
6. Edit the E01 script and approve the new version.
7. Confirm storyboard and prompt artifacts become stale.
8. Regenerate the storyboard from the edited script.
9. Start production and confirm the monitor shows exact consumed artifact versions.

## Not Yet Verifiable

These checks require implementation:

- Real provider failure handling during series planning.
- End-to-end migration against a production-like database snapshot.
- Browser screenshots for the new workbench and plan page.

