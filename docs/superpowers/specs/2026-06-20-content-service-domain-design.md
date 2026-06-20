# Content Service Domain Design

Date: 2026-06-20

## Goal

Move content template CRUD, sensitive word CRUD, sensitive-word matching,
variable substitution, and content-generation helpers from
`app.services.content_service` into
`app.domains.content_collection.content_service` without changing content API,
device bridge, task bridge, channel nurture injection, or AI generator behavior.

## Approved Approach

Move `server/app/services/content_service.py` to
`server/app/domains/content_collection/content_service.py`.

Keep `app.services.content_service` as a `sys.modules` compatibility facade.
`content_collection` modules import the domain service directly. Existing task,
device, account/channel, and AI generator bridges keep the legacy path until
their cleanup slices.

## Boundaries

- Preserve `ContentService`, `content_service`, `_build_ac_automaton`,
  `_ac_contains`, `_db_template_to_response`, and `_db_word_to_response`.
- Preserve template CRUD, sensitive word CRUD, Aho-Corasick cache behavior,
  variable substitution, template generation, keyword matrix, regex, and clean
  prompt generation.
- Preserve legacy monkeypatch paths such as
  `app.services.content_service.ContentService.generate_from_template`.
- Do not move `ai_generator`, task operations, device/content bridge,
  account/channel bridge, route behavior, ORM models, or websocket ownership in
  this slice.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, direct
  content collection imports, documented cleanup gates, and bridge compatibility.
- Run content service, content API, content collection mutation, device bridge,
  and task compatibility tests after migration.
