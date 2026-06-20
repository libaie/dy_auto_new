# Video Production Review Asset Edit Domain Design

## Context

`app.services.review_asset_edit_service` owns review-time image edit and asset
voiding workflows used by `/api/video-production/*` routes. It creates edited
image versions, demotes old latest assets, records human void reviews, and
surfaces provider/task failures. This is video production review domain logic,
but it still lives in the generic service folder.

## Approved Approach

Move the implementation to
`app.domains.video_production.review_asset_edit_service` and keep
`app.services.review_asset_edit_service` as a temporary compatibility facade.
Update `video_production_router.py` to import `ReviewAssetEditError`,
`edit_image_asset`, and `void_asset_version` from the domain path directly.

## Boundaries

- Preserve `ReviewAssetEditError` shape and string behavior.
- Preserve `void_asset_version`, `edit_image_asset`, and `_generate_edited_image`
  behavior.
- Preserve existing tests and callers that monkeypatch
  `app.services.review_asset_edit_service._generate_edited_image`.
- Preserve image creation service integration; do not move image generation
  dependencies in this step.
- Document the legacy facade in the video production domain README with an
  explicit cleanup gate.

## Verification

- Add a boundary test proving spec and plan coverage for
  `app.domains.video_production.review_asset_edit_service`,
  `app.services.review_asset_edit_service`, `edit_image_asset`, and
  `void_asset_version`.
- Prove the legacy import and domain import resolve to the same module object.
- Prove the legacy file is a thin facade and contains no local
  `def edit_image_asset`.
- Prove `video_production_router.py` imports review asset edit helpers from the
  domain path.
- Run review asset edit behavior tests after migration.
