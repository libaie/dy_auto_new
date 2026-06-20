# Runtime Model Config Domain Design

Date: 2026-06-20

## Goal

Move runtime model configuration resolution into the `model_configuration`
domain. The code resolves enabled `AIModel` rows, decrypts runtime credentials,
checks scene/capability support, and redacts secrets for traces, so it belongs
with model configuration rather than the flat `app.services` folder.

## Design

`app.domains.model_configuration.runtime_model_config` owns
`RuntimeModelConfigError`, `resolve_runtime_model_config`,
`resolve_image_model_for_capability`, `_model_supports_capability`, and
`redact_runtime_model_config`.

`app.services.runtime_model_config` remains a `sys.modules` compatibility
facade so old imports and monkeypatches resolve to the same module object.
Dirty or not-yet-moved service modules may keep legacy imports until their
own domain migrations happen.

Clean domain callers should import the domain path directly:

- `app.domains.image_generation.image_model_selection_service`
- `app.domains.script_pipeline.script_pipeline_service`
- `app.domains.script_pipeline.pipeline_router`
- `app.domains.director_planning.director_router`
- `app.domains.ai_video_series.story_generator_expert`
- `app.domains.ai_video_series.style_lock`

## Boundaries

- Keep `AIModel` ORM definitions in `app.db_models`.
- Keep encryption helpers in `app.services.crypto`.
- Keep Pixelle and production execution ownership in their existing domains or
  service modules.
- Do not edit dirty large orchestration services in this slice.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  domain imports, README registration, and legacy-path runtime resolution.
- Run existing runtime model config tests.
- Run existing image model resolution tests.
