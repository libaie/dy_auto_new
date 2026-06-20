# Script Pipeline Storyboard Timing Domain Design

Date: 2026-06-20

## Goal

Move storyboard timing helpers into the `script_pipeline` domain. The helper
owns shot duration normalization, time range formatting, storyboard timing
annotation, timed storyboard line rendering, and detailed image/video prompt
timing text.

## Design

`app.domains.script_pipeline.storyboard_timing` becomes the implementation
owner for `DEFAULT_TIMED_SHOT_SECONDS`, `format_time_range`,
`shot_durations_for_total`, `annotate_frames_with_timing`,
`annotate_storyboard_with_timing`, `timed_storyboard_lines`,
`build_second_level_motion_detail`, `build_detailed_image_prompt`, and
`build_detailed_video_prompt`.

`app.services.storyboard_timing` remains a `sys.modules` compatibility facade
so legacy imports continue to resolve to the same module object. Existing
one-sentence and production-run callers may keep the legacy import until their
own domains are migrated.

`app.domains.script_pipeline.script_pipeline_service` imports the domain path
directly.

## Boundaries

- Keep production run and one-sentence callers on the legacy facade.
- Keep director planning timing helpers separate; they are not this module.
- Preserve public function names, output keys, Chinese prompt text, rounding,
  and duration fallback behavior.

## Verification

- Add a boundary test for domain ownership, legacy facade identity, direct
  script pipeline import, README registration, and representative legacy-path
  timing behavior.
- Run app import smoke to catch startup import regressions.
