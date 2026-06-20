# Agency Manifest Domain Design

Date: 2026-06-20

## Goal

Move agency expert manifest loading into the `agency_operations` domain. The
manifest defines the agency expert team and is agency business logic, not a
generic shared service.

## Design

`app.domains.agency_operations.agency_manifest` owns `AgencyManifest`,
`AgencyManifestError`, `EXPERT_IDS`, manifest loading, expert markdown hash
checks, legacy expert lookup, and `verify_manifest`.

`app.services.agency_manifest` remains a `sys.modules` compatibility facade so
old imports and monkeypatches resolve to the same module object. Dirty
in-progress service modules may keep legacy imports until their own domains
move.

Clean domain callers should import the domain path directly:

- `app.domains.agency_operations.agency_router`
- `app.domains.ai_video_series.story_generator_expert`

## Boundaries

- Keep agency expert data under `server/app/data/agency_agents_zh`.
- Preserve path traversal protection for manifest and legacy expert files.
- Preserve `load_manifest` caching behavior.
- Do not edit dirty agency service modules in this slice.

## Verification

- Add a boundary test for domain file ownership, data root correctness, legacy
  facade identity, direct domain imports, README registration, and legacy-path
  behavior.
- Run existing agency manifest tests.
- Run a focused agency API test that imports the agency router.
