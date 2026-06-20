# Industry Profile Domain Design

Date: 2026-06-20

## Goal

Move DM industry compliance profile helpers from
`app.services.industry_profile_service` into
`app.domains.content_collection.industry_profile_service` without changing DM
sequence generation behavior or legacy imports.

## Approved Approach

Move the implementation to
`server/app/domains/content_collection/industry_profile_service.py`.

Keep `app.services.industry_profile_service` as a `sys.modules`
compatibility facade. Update `content_collection.mutations` to import the
domain helper directly. Keep JSON profile data in
`server/app/data/industry_profiles`.

## Boundaries

- Preserve `load_profile`, `list_industries`, LRU caching, missing-industry
  fallback to `general.json`, and UTF-8 JSON loading.
- Preserve legacy imports such as
  `from app.services.industry_profile_service import load_profile`.
- Do not change DM sequence routes, generation prompts, profile JSON content,
  AI generator calls, response shapes, or database behavior.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, direct
  content collection imports, README ownership, and fallback profile behavior.
- Run content collection mutation tests after migration.
