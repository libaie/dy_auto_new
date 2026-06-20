# Creative Visual Style Domain Design

Date: 2026-06-20

## Goal

Move creative visual style inference into the `creative_library` domain. The
service owns story-text flattening, live-action versus default style inference,
visual style merging, prompt constraint appending, and stored prompt style
matching.

## Design

`app.domains.creative_library.visual_style_inference_service` becomes the
implementation owner for `infer_visual_style_from_story`,
`merge_visual_style`, `append_visual_style_constraints`,
`reference_prompt_matches_visual_style`, `DEFAULT_NEGATIVE`, and related
style constants.

`app.services.visual_style_inference_service` remains a `sys.modules`
compatibility facade so legacy imports continue to resolve to the same module
object. Existing one-sentence and AI video series callers may keep the legacy
import until their own domains are migrated.

`app.domains.creative_library.reference_asset_service` imports the domain path
directly.

## Boundaries

- Keep AI generation and image creation outside this slice.
- Keep one-sentence and AI video series callers on the legacy facade.
- Preserve public function names, constants, prompt text, rationale text, and
  live-action matching behavior.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  reference asset import, README registration, and representative legacy-path
  behavior.
- Run reference asset tests because reference asset prompts depend on visual
  style inference.
- Run app import smoke to catch startup import regressions.
