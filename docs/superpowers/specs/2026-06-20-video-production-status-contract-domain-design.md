# Video Production Status Contract Domain Design

Status: auto-approved.

## Context

`app.services.production_status` defines the status constants used by video
production plans, jobs, segments, provider stages, continuity modes, and
reference types. It is a pure production domain contract, but still lives in the
flat service folder and is imported by video production services plus temporary
cross-domain consumers such as agency repair and AI video series orchestration.

## Decision

Move the implementation to `app.domains.video_production.production_status` and
keep `app.services.production_status` as a thin `sys.modules` compatibility
facade.

Domain-owned video production modules should import the new domain path
directly as they are migrated. Existing service modules, tests, and approved
cross-domain consumers can keep the legacy path until their own domain cleanup
gates are satisfied.

## Scope

In scope:

- Create `server/app/domains/video_production/production_status.py` with the
  current status constant implementation.
- Replace `server/app/services/production_status.py` with a compatibility
  facade.
- Update `server/app/domains/video_production/production_cost_service.py` to
  import production status constants from the domain path.
- Update `server/app/domains/video_production/README.md` to document production
  status ownership, facade mapping, and cleanup gates.
- Add focused boundary tests proving old and new imports resolve to the same
  module object and expose identical representative constants.

Out of scope:

- No behavior or value changes to plan, job, segment, stage, continuity, or
  reference constants.
- No migration of queue, plan, worker, agency repair, AI video series, or test
  consumers in this step.

## Architecture

The domain production status contract owns:

- Plan statuses such as `PLAN_DRAFT` and `PLAN_BLOCKED`
- Job statuses such as `JOB_QUEUED`, `JOB_LEASED`, and `JOB_COMPLETED`
- Segment statuses such as `SEGMENT_IMAGE_QUEUED` and `SEGMENT_SUPERSEDED`
- Stage constants such as `STAGE_IMAGE_GENERATION`
- Continuity constants such as `CONTINUITY_NARRATIVE_CUT`
- Reference constants such as `REFERENCE_CHARACTER_ANCHOR`

The legacy service module imports the domain status module, replaces itself in
`sys.modules`, and updates globals so existing imports and monkeypatch paths keep
targeting the same module object.

## Testing

Add `server/tests/test_video_production_status_contract_facade.py` to verify:

- this spec and plan mention
  `app.domains.video_production.production_status`,
  `app.services.production_status`, `PLAN_DRAFT`, `JOB_QUEUED`,
  `SEGMENT_IMAGE_QUEUED`, `STAGE_IMAGE_GENERATION`,
  `CONTINUITY_NARRATIVE_CUT`, and `REFERENCE_CHARACTER_ANCHOR`;
- the domain production status file exists;
- the legacy service file is a thin facade with no copied constants;
- old and new imports resolve to the same module object and expose identical
  representative constants;
- `production_cost_service.py` imports the domain status path directly;
- the video production README records status ownership, facade mapping, and
  cleanup gate.

Run focused verification:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_status_contract_facade.py server/tests/test_production_cost_service.py server/tests/test_production_queue_service.py -q
```
