# Model Configuration Domain Design

## Goal

Move the legacy `/api/ai-models/*` model center router into a business-domain
package without changing route behavior, seeded defaults, auth dependencies,
credential handling, or existing compatibility imports.

## Approved Approach

Use the established facade-first domain migration pattern:

1. Create `app.domains.model_configuration`.
2. Move the current `app.routers.ai_config` implementation to
   `app.domains.model_configuration.ai_models_router` in
   `ai_models_router.py`.
3. Replace `app.routers.ai_config` with a thin `sys.modules` compatibility
   facade pointing at the domain router module.
4. Wire `app.main` directly to `ai_models_router.router`.
5. Import `seed_ai_models` from the domain during startup.

## Ownership Boundary

`app.domains.model_configuration` owns:

- `GET /api/ai-models`
- `GET /api/ai-models/options`
- `GET /api/ai-models/schema`
- `GET /api/ai-models/{model_id}`
- `POST /api/ai-models`
- `PUT /api/ai-models/{model_id}`
- `DELETE /api/ai-models/{model_id}`
- `POST /api/ai-models/{model_id}/test`
- Route-local request models `ModelCreate` and `ModelUpdate`
- Route-local helpers such as `_model_dict`, `_is_private_url`, and
  `_build_auth_headers`
- Default model constants and `DEFAULT_MODELS`
- `seed_ai_models`, including legacy Seedance and expert-review upgrades

`app.domains.model_configuration` does not own:

- `AIModel` ORM definition, which remains in `app.db_models`.
- DB session construction, which remains in `app.database`.
- Auth dependencies, which remain in `app.deps`.
- Secret encryption helpers, which remain in `app.services.crypto`.
- Model schema data, which remains in `app.services.model_schema` and
  `app.data.model_schema_data`.
- Runtime model resolution, which remains in `app.services.runtime_model_config`.
- Pixelle and Seedance execution routes.
- Quality audit routes that merely read `AIModel` rows.

## Compatibility Contract

The migration must preserve:

- All route paths, methods, names, dependency names, and response shapes.
- Blank-secret preservation and explicit `clear_secret` behavior.
- SSRF protection for model connection tests.
- Provider-specific connection-test strategy behavior.
- Existing tests that monkeypatch `app.routers.ai_config.httpx.get`.
- Existing imports of `DEFAULT_MODELS`, provider constants, and
  `seed_ai_models` from `app.routers.ai_config`.
- Startup seeding behavior in `app.main`.

## Testing Strategy

Add boundary tests that fail before the move and pass after domain wiring:

- Spec and plan mention the domain, facade, route prefix, `AIModel`,
  `DEFAULT_MODELS`, and `seed_ai_models`.
- Domain package exports `DOMAIN_NAME` and `PUBLIC_ROUTE_PREFIX`.
- Domain README documents the facade and cleanup gates.
- Legacy `app.routers.ai_config` is a thin `sys.modules` facade.
- Legacy and domain imports resolve to the same module object.
- Router snapshot matches the eight existing `/api/ai-models/*` routes.
- FastAPI route table uses `app.domains.model_configuration.ai_models_router`
  endpoint modules.
- `app.main` imports the domain router and domain seed helper directly.

Run existing model-center tests after migration.

## Cleanup Gates

Do not remove `app.routers.ai_config` until all of these are true:

- `app.main` imports `ai_models_router` and `seed_ai_models` from the domain.
- Route/auth snapshots pass against the domain endpoint module.
- Existing model-center and image model-resolution tests pass.
- Import inventory shows no unapproved production imports of
  `app.routers.ai_config`.
- Tests that monkeypatch the legacy module path are either updated or
  intentionally kept compatible through the alias phase.
