# Ark Seedream/Seedance Real Smoke Report

Date: 2026-05-26

## Scope

Validated the paid Volcengine Ark Agent Plan V3 path for dy_auto's configured image and video production models.

## Endpoints

- Image generation: `POST https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`
- Video task creation: `POST https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks`
- Video task polling: `GET https://ark.cn-beijing.volces.com/api/plan/v3/contents/generations/tasks/{id}`

No `/api/v3/...` endpoint was used.

## Models

- Image: `doubao-seedream-5.0-lite`
- Image-to-video: `doubao-seedance-2.0`

## Results

- Auth/list smoke: passed with HTTP 200 against the V3 task list endpoint.
- First image attempt: reached the correct endpoint but failed because `1024x1024` is below the model's minimum pixel requirement.
- Usable image generation: passed with `1440x2560`.
- Image-to-video generation: passed.
- dy_auto -> Pixelle -> Ark stage-gated E2E: passed for image generation, human approval, image-to-video generation, human approval, real Pixelle compose, final approval, and run completion.

Video task:

- Task ID: `cgt-20260526133953-jjbpm`
- Status: `succeeded`
- Resolution: `720p`
- Ratio: `9:16`
- Duration: `5`
- FPS: `24`
- Audio: disabled

Local artifacts:

- First frame: `D:\devWorkspace\jsProjects\dy_auto\output\ark-smoke-20260526\seedream-first-frame-usable.jpg`
- Video: `D:\devWorkspace\jsProjects\dy_auto\output\ark-smoke-20260526\seedance-video\01-content.video_url.mp4`
- Last frame: `D:\devWorkspace\jsProjects\dy_auto\output\ark-smoke-20260526\seedance-video\02-content.last_frame_url.png`
- Task JSON: `D:\devWorkspace\jsProjects\dy_auto\output\ark-smoke-20260526\seedance-video\task.json`

The downloaded video file is non-empty and has an MP4 `ftypisom` signature.

dy_auto E2E run:

- Series ID: `42cfbc1f-16e5-4685-b1a9-1d3818500583`
- Episode ID: `1900f596-aeee-41c6-9cd1-b088e37c5653`
- Run ID: `3c265d65-4b60-4ca6-97ec-b479bcdb3e29`
- Image stage task: `1682626e-a410-49ee-8600-ce5a25670b44`
- Video stage task: `dd889f4f-c8f2-4bd7-b494-a4832d5f9a37`
- Compose stage task: `d1a2d350-b95c-4631-9c1c-90a7ae14b0b2`
- Final asset ID: `ec3050e8-ea90-4ea1-a8f4-a1ce805dc238`
- Final local file: `D:\devWorkspace\Pixelle-Video\output\d1a2d350-b95c-4631-9c1c-90a7ae14b0b2\final.mp4`
- Final file size: `1085744` bytes
- Final signature: MP4 `ftyp`
- Run status after final approval: `completed`

## Follow-Up Fixes Applied

- Updated the default Seedream model config from `1024x1024` to `1440x2560`.
- Added `1440x2560` and `2560x1440` as selectable image sizes in the model config UI/schema.
- Updated style-lock reference image generation fallback so Seedream uses `1440x2560` when no explicit size is configured.
- Normalized dy_auto's configured Pixelle base URL so both `http://host:8500` and `http://host:8500/api` resolve to the same stage API paths.
- Disabled environment proxy inheritance for dy_auto's local Pixelle HTTP client to prevent local `127.0.0.1` calls from being routed through external proxy settings.
- Changed dy_auto compose stage submission from mock compose to Pixelle compose.
- Updated Pixelle compose to download remote Seedance segment URLs into local files before ffmpeg concatenation.
- Updated Pixelle post-production to use bundled `imageio-ffmpeg` when `ffmpeg` is not available in PATH, and to tolerate missing `ffprobe` metadata.
- Encrypted and saved the provided Ark key into the local AIModel rows for:
  - `image_generation` / `doubao-seedream-5.0-lite`
  - `video_rendering` / `doubao-seedance-2.0`

## Verification

- `cd server && pytest tests/test_pixelle_client.py tests/test_pixelle_stage_client.py tests/test_video_production_compose.py tests/test_ai_config_scene_schema.py tests/test_runtime_model_config.py`
- `cd D:\devWorkspace\Pixelle-Video && venv\Scripts\python.exe -m pytest tests/test_stage_compose_api.py tests/test_ark_plan_v3.py tests/test_stage_runtime_config.py`
- `cd web && npm run build`
- Real dy_auto/Pixelle/Ark E2E through run `3c265d65-4b60-4ca6-97ec-b479bcdb3e29`

All passed. The report intentionally omits raw API keys and signed provider asset URLs.
