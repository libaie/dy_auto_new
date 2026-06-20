# Creative Anchor ORM Boundary Design

## Context

`CharacterAnchor` and `SceneAnchor` are creative-library persistence models,
but their class bodies still live in the monolithic `app.db_models` module.
The creative-library domain already owns anchor behavior through
`app.domains.creative_library.anchor_service`.

## Decision

Move `CharacterAnchor` and `SceneAnchor` to
`app.db.models.creative_library`. Keep `app.db_models.CharacterAnchor` and
`app.db_models.SceneAnchor` as compatibility re-exports. Leave `Character`
and `Scene` in `app.db_models` for now because that graph has wider series
relationships.

## Verification

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_creative_library_anchor_orm_boundary.py server/tests/test_asset_anchor_models.py server/tests/test_anchor_service.py server/tests/test_reference_asset_service.py -q
```
