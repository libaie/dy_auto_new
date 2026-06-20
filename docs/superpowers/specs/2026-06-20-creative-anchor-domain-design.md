# Creative Anchor Domain Design

Date: 2026-06-20

## Goal

Move creative asset anchor management into the `creative_library` domain. The
manager owns character/scene anchor creation, prompt construction, provider
reference payload adaptation, and latest locked anchor lookup.

## Design

`app.domains.creative_library.anchor_service` becomes the implementation owner
for `AssetAnchorManager`, anchor reference mode maps, slot validation, prompt
helpers, provider payload helpers, and deterministic seed resolution.

`app.services.anchor_service` remains a `sys.modules` compatibility facade so
legacy imports and monkeypatches resolve to the same module object. Existing
utility or service modules may keep their legacy import until their own domain
migration.

The domain implementation imports same-domain reference asset helpers from
`app.domains.creative_library.reference_asset_service`.
The existing same-domain reference asset service lazy-loads
`AssetAnchorManager` from `app.domains.creative_library.anchor_service`.

## Boundaries

- Keep ORM models in `app.db_models`.
- Keep reference image generation behavior in `reference_asset_service`.
- Keep prompt compositor and video production callers outside this slice.
- Preserve all public names, payload shapes, validation errors, seed behavior,
  and monkeypatch compatibility.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  same-domain imports, README registration, and legacy monkeypatch visibility.
- Run existing anchor service tests.
- Run app import smoke to catch import regressions.
