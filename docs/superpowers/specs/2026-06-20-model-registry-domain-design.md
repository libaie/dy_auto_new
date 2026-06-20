# Model Registry Domain Design

Date: 2026-06-20

## Goal

Move scene-based AI model registry resolution from `app.services.model_registry`
into `app.domains.model_configuration.model_registry` without changing audit
model resolution, decrypted runtime payloads, or legacy imports.

## Approved Approach

Move the current implementation to
`server/app/domains/model_configuration/model_registry.py`.

Keep `app.services.model_registry` as a `sys.modules` compatibility facade.
Update the clean `quality_audit.audit_router` caller to import the domain
registry directly. Leave `video_production_service` on the legacy path in this
slice because that file has unrelated WIP.

## Boundaries

- Preserve `ModelResolutionError`, `get_model_for_scene`, `_get_scene_label`,
  decrypted `api_key`/`api_secret` handling, status codes, repair messages,
  and returned `config_json`.
- Preserve legacy imports such as
  `from app.services.model_registry import get_model_for_scene`.
- Keep `AIModel` persistence in `app.db_models`, encryption in
  `app.services.crypto`, and schema data in `app.data.model_schema_data`.
- Do not change audit route paths, response shapes, AI provider calls, video
  production behavior, or model center CRUD behavior.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, quality
  audit direct import, video compatibility import, README ownership, and error
  class identity.
- Run model registry tests after migration.
