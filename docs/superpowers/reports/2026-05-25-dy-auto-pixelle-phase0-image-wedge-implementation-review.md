# dy_auto + Pixelle Phase 0 Image Wedge 实现复核报告

日期：2026-05-25

审查对象：

- 计划文档：`D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-25-dy-auto-pixelle-phase0-image-wedge.md`
- dy_auto：`D:\devWorkspace\jsProjects\dy_auto`
- Pixelle-Video：`D:\devWorkspace\Pixelle-Video`

## 结论

当前实现已经比首次审查时更完整：Pixelle stage 鉴权、文件前缀校验、mock 图片落盘、图片同步后的 AI 审查记录、reject 动作、review-items 过滤分页、审查页手动同步入口都已经落地。

但按 Phase 0 计划的“安全可信的图片生成 -> AI 审查 -> 人工审查 -> 单图重生 wedge”衡量，仍不能判定为全部完成。主要缺口集中在状态机推进、幂等性、前端透明度和 Pixelle 测试可运行性。

## 当前已落地

### dy_auto

- `VideoProductionRun` / `VideoProductionAsset` / `VideoReviewRecord` 相关模型、迁移和基础服务已存在。
- `sync_image_stage_results` 在 Pixelle task 完成后会写入图片资产，并调用 `run_ai_audit_for_assets`。
- `run_ai_audit_for_assets` 会创建 `VideoReviewRecord(review_type="ai")`，AI 通过时将资产置为 `approved`，否则置为 `review_pending`。
- `/api/video-production/review-items` 已支持 `run_id`、`status`、`series_id`、`episode_id`、`stage`、`asset_type`、`page/page_size`。
- `/assets/{asset_id}/review` 已支持 `approve` 和 `reject`。
- 审查页已支持查看 run status、手动 `Sync Pixelle Results`、approve、reject。

### Pixelle-Video

- `/api/stages/*` 在 `PIXELLE_API_KEY` 未配置时返回 503，不再空 key 放行。
- `/api/files/*` 改为 `resolve` 后检查根目录，并用 `rel_path.parts[0]` 判断一级目录，修复 `output_evil` 这类前缀绕过。
- mock 图片 provider 会写出最小 PNG 到 `output/{task_id}/{frame_id}.png`，审查页预览不再天然 404。

## 仍存在的缺陷

### P1: 图片同步接口不是幂等的，重复同步会为同一 Pixelle 任务重复生成新版本资产

证据：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:89`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:102`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:257`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:266`

`sync_image_stage_results` 每次任务完成后都会调用 `mark_image_stage_assets`，而 `mark_image_stage_assets` 每次都用 `_next_asset_version` 新建资产。对同一个 `pixelle_stage_task_id` 重复点击同步，会把同一批图片不断写成 v2、v3、v4。

影响：

- 人工审查对象会被重复版本污染。
- 已审批版本可能被新同步出来的重复版本覆盖为非最新版本。
- 后续图生视频阶段如果按最新版本取图，会拿到重复写入的资产。

建议：

- 对 `(run_id, frame_id, asset_type, pixelle_task_id)` 做幂等判断。
- 或在 `sync_image_stage_results` 中如果该 `pixelle_stage_task_id` 已同步过，直接返回已有资产。
- 增加重复同步测试：同一个 completed task 调两次，资产数量和版本号不变。

### P1: AI 审查全通过后 run 状态仍停在 `image_review_pending`

证据：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:109`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:118`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:267`

`mark_image_stage_assets` 先把 run 置为 `image_review_pending`。随后 `run_ai_audit_for_assets` 即使把所有资产都置为 `approved`，也没有重新计算 run 级状态。

影响：

- 审查队列可能为空，但 run 仍显示需要图片审查。
- 后续阶段无法通过明确状态知道“图片阶段已全部通过”。
- 自动化流水线无法可靠进入图生视频阶段。

建议：

- 增加 run 级 gate 计算：最新版本图片全部 `approved` 时，将 run 更新为 `image_approved` 或下一阶段待启动状态。
- 若任一资产 `review_pending`，run 保持 `image_review_pending`。
- 若任一资产 `rejected`，run 进入 `image_revision_required` 或等价状态。

### P1: 人工 approve/reject 后也不会推进 run 状态

证据：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:176`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:213`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:231`

`approve_asset` 和 `reject_asset` 只更新单个 asset 并写人工审查记录，没有在每次人工决策后重新计算 run 是否已经全部通过、是否需要重生、是否可进入下一阶段。

影响：

- 人工审查完成后系统没有明确完成态。
- 前端和后续编排层只能看到单资产状态，无法知道整个 run 是否可继续。

建议：

- 抽出 `recompute_image_stage_gate(db, run_id)`。
- 在 AI 审查、人工 approve/reject、重生资产创建后都调用。
- 以“每个 frame 的最新 image asset”为准计算 run 状态。

### P1: 图片阶段可重复提交，可能覆盖 run 的 Pixelle task 并制造多批结果

证据：

- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:234`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:247`
- `D:\devWorkspace\jsProjects\dy_auto\server\app\services\video_production_service.py:254`

`start_image_stage` 没有检查 run 当前状态或已有 `pixelle_stage_task_id`。重复调用会再次提交 Pixelle，并覆盖 run 上的 task id。

影响：

- 旧 Pixelle task 结果仍可能存在，但 dy_auto 已失去引用。
- 用户重复点击或请求重试时，会产生多批不可追踪图片。

建议：

- `draft/storyboard_ready` 才允许 start。
- 已有 running task 时返回现有 run，不重复提交。
- 失败重试必须显式走 retry 状态，并记录旧 task。

### P1: Pixelle 测试在当前环境仍无法运行

命令：

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_files_security.py -q
```

结果：测试收集阶段失败。

错误摘要：

```text
ModuleNotFoundError: No module named 'comfykit'
```

导入链路：

```text
tests -> api.app -> api.dependencies -> pixelle_video.service -> comfykit
```

影响：

- Pixelle stage auth、stage image、files security 测试没有真实执行通过。
- 这不只是“缺依赖”，也暴露出 API 测试被核心 Comfy/Pixelle runtime 强耦合，难以单独验证轻量 stage API。

建议：

- 为 API 测试提供 mock Pixelle dependency 或 lazy import。
- 或在测试环境安装/声明 `comfykit`。
- 目标是让 stage API、auth、files security 不依赖完整视频执行环境也能跑通。

### P2: 审查中心仍缺少单图重生 UI 和版本对比

证据：

- `D:\devWorkspace\jsProjects\dy_auto\web\src\api\videoProduction.js:30`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:101`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:149`

API client 已有 `regenerateAsset`，但 `AIVideoReviewPage.vue` 没有导入或使用它。页面只提供同步、刷新、approve、reject。

影响：

- 计划中的“单图重生 wedge”仍不是用户可操作闭环。
- reject 后没有自然的“重新生成当前 frame”入口。

建议：

- 审查页增加 Regenerate 按钮和重生参数输入。
- 重生后展示新旧版本对比，并默认选中新版本。
- 后续再将当前 payload 型重生升级为真实调用 Pixelle 生成。

### P2: 审查中心缺少 AI 审查报告、模型链路和分镜上下文展示

证据：

- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:45`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:64`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\AIVideoReviewPage.vue:92`

页面目前展示图片、run、version、local path、Pixelle task 和操作按钮，但没有展示：

- AI 审查记录、分数、issues。
- 使用的模型配置摘要。
- frame 的 image prompt、reference_urls、角色/场景信息。
- 历史版本与当前版本差异。

影响：

- 不符合“后台不得暗箱操作”的产品要求。
- 人工审查者无法知道为什么 AI 放行或退回。

建议：

- 后端 asset payload 增加最近一条 AI review record。
- 前端展示 prompt/reference/model trace/audit issues。
- 资产列表中标识“AI 通过 / 需人工 / 已拒绝 / 已重生”。

### P2: 系列页启动后仍直接跳审查页，没有自动轮询到首批结果

证据：

- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\SeriesDetailPage.vue:208`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\SeriesDetailPage.vue:209`

审查页现在有手动 `Sync Pixelle Results`，但从系列页启动后仍是提交图片阶段后直接跳转。用户必须理解并点击同步按钮才能把 Pixelle 任务结果写回 dy_auto。

影响：

- 对“一句话生产内容”的目标仍有摩擦。
- 如果图片任务已经完成但未同步，页面可能显示空队列或仅显示 run 状态。

建议：

- 启动后进入生产过程页，自动轮询 run/Pixelle task。
- Pixelle 完成后自动调用 sync。
- 同步失败时展示可重试错误。

### P2: PipelineMonitorPage 仍使用旧 pipeline run，不适配 VideoProductionRun

证据：

- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\PipelineMonitorPage.vue:58`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\PipelineMonitorPage.vue:63`

staged production 使用 `VideoProductionRun`，但 PipelineMonitorPage 仍调用 `getRunById` 读取旧 pipeline run，并按 `layers_json/current_layer` 渲染。

影响：

- 新图片 wedge 的 run 无法稳定在监控页展示。
- “生产过程步骤透明展示”仍需要单独补齐。

建议：

- 新增 `VideoProductionMonitorPage`，或让当前监控页按 run 类型分支读取。
- 用 `current_stage/status/assets/review records/model trace` 渲染 Phase 0 步骤。

### P2: 前端仍有明显乱码文案

证据：

- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\SeriesDetailPage.vue:3`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\PipelineMonitorPage.vue:3`
- `D:\devWorkspace\jsProjects\dy_auto\web\src\views\PipelineMonitorPage.vue:10`

影响：

- 用户无法准确理解关键操作和状态。
- 在审查、生产流程这种高信任页面里会显著降低可用性。

建议：

- 统一文件编码为 UTF-8。
- 修复已损坏中文文案。
- 增加一次前端文本快照或页面 smoke test，防止乱码回归。

## 已修复或不再成立的首次审查结论

以下问题在当前代码中已经不再成立：

- Pixelle `/api/stages/*` 空 `PIXELLE_API_KEY` 放行：已改为 503。
- Pixelle files `output_evil` 前缀绕过：已改为检查 `rel_path.parts[0]`。
- Pixelle mock provider 只返回 URL 不写文件：已写出最小 PNG。
- 图片同步后完全没有 AI 审查：当前已接入 `run_ai_audit_for_assets` 并创建 AI review record。
- `/review-items` 只有 `run_id/status`：当前已支持更多过滤和分页。
- 审查动作只有 approve：当前已支持 reject。
- 审查页没有同步入口：当前已有手动 `Sync Pixelle Results`。

## 验证结果

### 通过

dy_auto 后端选定测试：

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_models.py tests/test_pipeline_saved_storyboard_compat.py tests/test_pixelle_config_security.py tests/test_audit_gate.py tests/test_runtime_model_config.py tests/test_pixelle_stage_client.py tests/test_video_production_service.py tests/test_video_production_api.py tests/test_video_production_mocked_e2e.py -q
```

结果：`20 passed in 0.48s`

dy_auto 前端选定测试：

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js
```

结果：`3 files passed, 23 tests passed`

### 未通过

Pixelle-Video 选定测试：

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_files_security.py -q
```

结果：收集阶段失败，`ModuleNotFoundError: No module named 'comfykit'`。

## 建议修复顺序

1. 修复 Pixelle API 测试环境或导入耦合，让 stage/auth/files 测试能独立运行。
2. 为 `start_image_stage` 增加状态保护，避免重复提交。
3. 为 `sync_image_stage_results` 增加幂等保护，避免重复同步制造新版本。
4. 实现 run 级图片阶段 gate：AI 审查、人工审查、重生后统一重算 run 状态。
5. 审查页补齐 Regenerate、版本对比、AI 审查报告、prompt/reference/model trace。
6. 用自动轮询/自动同步替代“启动后人工点 Sync”。
7. 新增或改造生产监控页，专门展示 VideoProductionRun 的阶段进度。
8. 修复前端乱码文案。

## 最终判定

Phase 0 Image Wedge 已经具备核心骨架和部分闭环能力，但仍不是完整可交付状态。

当前最关键的阻断点不是“有没有接口”，而是：

- 状态机无法可靠推进。
- 重复操作会产生重复资产或覆盖任务引用。
- Pixelle 侧测试不可运行。
- 前端还不能完整透明地展示和驱动生产过程。
