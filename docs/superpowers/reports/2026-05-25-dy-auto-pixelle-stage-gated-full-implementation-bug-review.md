# dy_auto + Pixelle Stage-Gated Full Implementation Bug Review

日期：2026-05-25

审查对象：

- 实现计划：`D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-25-dy-auto-pixelle-stage-gated-full-implementation.md`
- dy_auto：`D:\devWorkspace\jsProjects\dy_auto`
- Pixelle-Video：`D:\devWorkspace\Pixelle-Video`

## 结论

当前实现不能判定为“全部无 bug 可交付”。dy_auto mock 链路的后端核心测试通过，但 Pixelle 阶段 API 在当前环境下仍被完整运行时依赖阻断；前端的资产重生闭环、失败资产审核入口和监控页测试覆盖仍有缺口。

最优修复顺序：

1. 先修 Pixelle API 导入耦合，让阶段 API 测试可以独立运行。
2. 再修 dy_auto 资产状态机和审核队列可见性，避免生产流程卡死但前端看不到原因。
3. 最后补齐前端监控页测试和 API client 测试，防止后续回归。

## 验证结果

### 已通过

dy_auto 后端阶段链路：

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_state_machine.py tests/test_video_production_video_stage.py tests/test_video_production_compose.py tests/test_video_production_regeneration.py tests/test_video_production_api.py tests/test_video_production_full_mocked_e2e.py -q
```

结果：`24 passed in 0.51s`

dy_auto 前端现有测试：

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/video-production-monitor-page.test.js
```

结果：实际只运行到 3 个存在的测试文件，`3 files / 23 tests passed`。`video-production-monitor-page.test.js` 当前不存在。

### 未通过

Pixelle-Video 阶段测试：

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_runtime_config.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py -q
```

结果：测试收集阶段失败，核心错误为：

```text
ModuleNotFoundError: No module named 'comfykit'
```

相关导入链：

- `D:\devWorkspace\Pixelle-Video\api\routers\__init__.py:17`
- `D:\devWorkspace\Pixelle-Video\api\routers\health.py:20`
- `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py:7`
- `D:\devWorkspace\Pixelle-Video\pixelle_video\__init__.py:46`
- `D:\devWorkspace\Pixelle-Video\pixelle_video\service.py:24`

## P1: Pixelle Stage API 被完整运行时依赖阻断

### 问题

计划要求 Stage API 测试独立于完整 Pixelle runtime，但当前 API app 导入 router 时会进入 `pixelle_video` 包初始化，最终加载 `pixelle_video.service` 并要求 `comfykit`。

具体触发点：

- `api/routers/__init__.py` 顶层导入 `health_router`
- `api/routers/health.py` 顶层导入 `pixelle_video.config.manager.ConfigManager`
- `api/services/stage_compose.py` 顶层导入 `pixelle_video.services.post_production`
- `pixelle_video/__init__.py` 顶层导入 `pixelle_video.service`
- `pixelle_video/service.py` 顶层导入 `comfykit`

### 影响

- Pixelle Stage API 的视频阶段、合成阶段测试无法运行。
- `dy_auto -> Pixelle` 的真实 E2E 无法被可靠验证。
- 轻量阶段 API 与重型视频执行 runtime 耦合，后续 CI 或本地开发都会不稳定。

### 修复方案

1. 调整 `D:\devWorkspace\Pixelle-Video\api\routers\health.py`：
   - 移除顶层 `from pixelle_video.config.manager import ConfigManager`。
   - 只在需要 reload config 的 endpoint 内部延迟导入。
   - 如果只是健康检查，不应触发 Pixelle core runtime。

2. 调整 `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py`：
   - 移除顶层 `from pixelle_video.services.post_production import ...`。
   - 在 `compose_stage_video()` 内部、且仅 real compose 分支执行时再延迟导入。
   - 更彻底的方案是把 `post_production.py` 移出会触发 `pixelle_video/__init__.py` 的包导入路径，或重构 `pixelle_video/__init__.py` 不再顶层导入 `service`。

3. 调整 `D:\devWorkspace\Pixelle-Video\pixelle_video\__init__.py`：
   - 避免包初始化时自动导入 `PixelleVideoCore` 和 `pixelle_video` 单例。
   - 改为显式工厂函数或 lazy getter，例如 `get_pixelle_video()`。
   - 这可以从根源上避免 `import pixelle_video.config.manager` 也连带加载 `comfykit`。

4. 测试侧保持 mock Pixelle dependency：
   - Stage API 单测只 mock `PixelleVideoDep` / `api.dependencies`。
   - Stage API 单测不应该要求真实 Comfy、Seedance、RunningHub 或 Pixelle core runtime。

### 验收标准

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_runtime_config.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py -q
```

预期：通过，且不安装 `comfykit` 也能完成 Stage API 单测。

## P1: 资产重生同步入口会被前端默认筛选隐藏

### 问题

后端 `start_asset_regeneration()` 会把原资产状态改成 `regenerating`，但 `AIVideoReviewPage.vue` 每次加载默认只请求 `status=review_pending`。用户点击 Regenerate 后页面刷新，资产从列表中消失，导致 `Sync Regeneration` 按钮难以出现。

相关位置：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:708`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:115`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:154`

### 影响

- 重生任务已提交，但用户无法在审核中心继续同步结果。
- 生产流程出现“后台有任务、前台无入口”的暗箱体验。
- 违反“后台不得暗箱操作、前端展示生产过程步骤”的产品要求。

### 修复方案

1. 后端保留 `regenerating` 状态，但 review items 支持复合状态查询：
   - 方案 A：新增 `statuses` 查询参数，支持 `review_pending,regenerating,failed,rejected`。
   - 方案 B：新增 `include_active=true`，默认包含 `review_pending` 和 `regenerating`。

2. 前端审核页调整默认查询：
   - 当存在 `run_id` 时，默认展示该 run 下所有需要人工关注的资产：`review_pending`、`regenerating`、`failed`、`rejected`。
   - 保留状态筛选控件，让用户能切换只看待审、重生中、失败项。

3. 前端按钮逻辑调整：
   - `selected.status === "regenerating"` 时显示 `Sync Regeneration`。
   - `selected.status !== "regenerating"` 且非 `final_video` 时显示 `Regenerate`。
   - 重生提交后不要让用户丢失当前选中资产。

4. 增加测试：
   - `ai-video-review-page.test.js` 覆盖点击 Regenerate 后，列表仍显示该资产并出现 `Sync Regeneration`。
   - 后端 API 测试覆盖 `review-items` 能返回 `regenerating` 资产。

### 验收标准

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_regeneration.py tests/test_video_production_api.py -q
```

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/ai-video-review-page.test.js
```

预期：重生任务提交后，审核页仍可看到资产，并能同步重生结果。

## P2: 视频分段失败资产可能进入不可见待处理状态

### 问题

Pixelle 返回单帧失败时，dy_auto 会保存 `status="failed"` 的 `video_segment` 资产；但 run gate 只把 `rejected` 识别为人工介入，默认审核列表又只显示 `review_pending`。

相关位置：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:379`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_state.py:92`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\video_production.py:146`

### 影响

- run 可能停在 `video_review_pending`，但审核中心默认看不到失败资产。
- 用户不知道哪一帧失败，也无法直接重生失败帧。
- 批量生产时会出现“流程卡住但没有明确补救入口”。

### 修复方案

1. 状态机明确失败含义：
   - `failed` 应进入 `video_human_review_required` 或专门的 `video_generation_failed`。
   - 不要把存在失败资产的 run 归类为普通 `video_review_pending`。

2. 审核队列默认包含失败项：
   - `review-items` 默认状态可以调整为“待处理集合”，而不是单一 `review_pending`。
   - 或前端默认请求 `statuses=review_pending,failed,rejected,regenerating`。

3. 前端失败项展示：
   - 对 `failed` 资产展示 `error_code`、`message`、`retryable`。
   - 对 `retryable=true` 的失败项显示 `Regenerate`。

4. 增加测试：
   - Pixelle mock 返回部分 failed video asset。
   - dy_auto sync 后 run 状态应进入人工处理状态。
   - 审核接口默认或指定参数能返回 failed 资产。

### 验收标准

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_video_stage.py tests/test_video_production_api.py -q
```

预期：视频帧失败不会被隐藏，用户能在审核中心看到错误并发起重生。

## P2: 前端监控页测试未落地

### 问题

实现计划明确要求创建 `web/src/__tests__/video-production-monitor-page.test.js`，但当前文件不存在。Vitest 命令传入该文件时，实际只运行了已存在的 3 个测试文件。

计划位置：

- `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-25-dy-auto-pixelle-stage-gated-full-implementation.md:3453`

当前测试目录：

- `agency-console-page.test.js`
- `ai-video-review-page.test.js`
- `api-clients.test.js`
- `navigation.test.js`
- `series-detail-agency.test.js`
- `series-detail-video-production.test.js`

### 影响

- 生产步骤展示页没有测试保护。
- 阶段按钮、blocked 状态、sync 按钮、review center 跳转容易回归。
- 用户要求“前端展示生产过程步骤，后台不得暗箱操作”，该要求缺少测试保障。

### 修复方案

1. 新增 `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\video-production-monitor-page.test.js`。

2. 覆盖场景：
   - 加载 run 后展示 7 个阶段：Storyboard、Images、Img Review、Videos、Vid Review、Compose、Complete。
   - `image_batch_running` 显示 `Sync Images`。
   - `image_approved` 显示 `Start Video Segments`。
   - `video_batch_running` 显示 `Sync Video Segments`。
   - `video_segments_approved` 显示 `Compose Final Video`。
   - `composing` 显示 `Sync Final Video`。
   - 审核阻塞状态显示 `Open Review Center`。

3. 补齐 `api-clients.test.js`：
   - 覆盖 `startVideoStage`
   - 覆盖 `syncVideoStage`
   - 覆盖 `startComposeStage`
   - 覆盖 `syncComposeStage`
   - 覆盖 `startAssetRegeneration`
   - 覆盖 `syncAssetRegeneration`

### 验收标准

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/video-production-monitor-page.test.js
```

预期：4 个测试文件全部存在并通过。

## P2: Pixelle real compose 对无音轨视频段存在失败风险

### 问题

`stage_compose.py` 调用 `compose_final_video()` 时传入 `audio_paths=[]`。`post_production.py` 在没有 BGM 时会映射 `0:a`，如果视频段没有音轨，FFmpeg 可能失败。

相关位置：

- `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py:23`
- `D:\devWorkspace\Pixelle-Video\pixelle_video\services\post_production.py:55`

### 影响

- mock MP4 或部分图生视频 provider 输出的视频可能没有音轨。
- 最终合成阶段在真实执行时失败，尤其是纯视觉短片或无 TTS/BGM 配置时。

### 修复方案

1. `compose_final_video()` 先 probe 输入视频是否存在音轨。
2. 没有音轨且没有 BGM 时：
   - 不映射 `0:a`；或
   - 注入静音音轨，例如 `anullsrc`。
3. 有 BGM 时继续走 mix 分支，但也要兼容原视频没有音轨的情况。
4. 增加测试：
   - 输入无音轨 mp4 + 无 BGM，合成应成功。
   - 输入无音轨 mp4 + BGM，合成应成功并带音轨。

### 验收标准

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_compose_api.py -q
```

预期：无音轨视频段也能完成 compose。

## 修复任务拆分

### Lane A: Pixelle API 可测性修复

目标：Stage API 单测不依赖完整 Pixelle runtime。

改动范围：

- `D:\devWorkspace\Pixelle-Video\api\routers\health.py`
- `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py`
- `D:\devWorkspace\Pixelle-Video\pixelle_video\__init__.py`
- `D:\devWorkspace\Pixelle-Video\tests\test_stage_videos_api.py`
- `D:\devWorkspace\Pixelle-Video\tests\test_stage_compose_api.py`

验证：

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_runtime_config.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py -q
```

### Lane B: dy_auto 状态机与审核队列修复

目标：失败、重生、待审资产都能被前端看见，并且 run 状态能准确表达阻塞原因。

改动范围：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_state.py`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\video_production.py`
- `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_video_production_video_stage.py`
- `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_video_production_regeneration.py`
- `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_video_production_api.py`

验证：

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_state_machine.py tests/test_video_production_video_stage.py tests/test_video_production_regeneration.py tests/test_video_production_api.py -q
```

### Lane C: 前端透明生产流程修复

目标：生产监控页和审核页能直观看到当前步骤、阻塞原因和可执行操作。

改动范围：

- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\VideoProductionMonitorPage.vue`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\api\videoProduction.js`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\video-production-monitor-page.test.js`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\ai-video-review-page.test.js`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\api-clients.test.js`

验证：

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/video-production-monitor-page.test.js
```

## 最终验收清单

- Pixelle Stage API 单测不再因为 `comfykit` 缺失而 collection 失败。
- `video-production-monitor-page.test.js` 存在并通过。
- 审核中心能看到 `review_pending`、`regenerating`、`failed`、`rejected` 等需要人工关注的资产。
- 点击 Regenerate 后，用户能继续在前端同步重生结果。
- 视频帧失败会清晰展示错误原因和重生入口。
- 最终 compose 能兼容无音轨视频段。
- dy_auto 后端、dy_auto 前端、Pixelle stage 三组验证命令全部通过。
