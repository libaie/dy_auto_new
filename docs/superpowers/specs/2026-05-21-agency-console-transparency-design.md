# 专家团队透明控制台方案

## Summary

新增一个只读前端页面：`/series/:seriesId/agency-console`，用于直观展示“专家团队如何影响自动视频生产”和“后台每一步到底做了什么”。页面不参与审批，不阻塞“一句话生成内容”的主流程。现有系列详情页和流水线监控页增加入口，生成流程仍然从原来的按钮启动。

本方案的关键调整是：透明展示不能只靠前端拼 UI。后端需要在 pipeline 每层写入安全的执行摘要，并提供一个聚合接口给前端读取。这样用户看到的是可解释执行轨迹，而不是包装后的黑盒结果。

## Goals

- 用户能看到 5 个核心专家和 4 个支援专家的职责、参与阶段、版本和启用状态。
- 用户能看到从风格锁定、自动分镜、L0-L5、写回剧集、写入视频资产库的生产步骤。
- 用户能展开每一步，查看输入摘要、输出摘要、使用专家、质量门槛、失败原因和持久化位置。
- 后台不得暗箱操作：每个可展示步骤都要有来自后端的透明摘要，而不是前端推测。
- 不打断生成流程：新增页面只读、可观察、可解释，不做审批节点。

## Non-Goals

- 不做多 Agent 聊天窗口。
- 不做可视化剪辑器或拖拽时间线。
- 不做人工审批节点。
- 不展示 API key、api_secret、完整 provider response、完整模型配置。
- 不要求用户进入该页面后才能启动流水线。

## What Already Exists

- `server/app/services/video_agency_team.py` 已定义专家团队、质量门槛和 `build_agency_context()`。
- `server/app/routers/series.py` 的 `GET/POST /api/series/{series_id}/style-lock` 已返回 `agency_team_status`，并把 `agency_team` 写入 `Series.story_bible_json.style_lock`。
- `server/app/routers/director.py` 的 `POST /api/director/auto-plan` 已把 `agency_team` 和 `agency_context` 注入自动分镜，并写入 `Episode.storyboard_json`。
- `server/app/routers/pipeline.py` 已把 `agency_context`、`style_constraints` 和 `edit_manifest` 注入流水线执行。
- `web/src/views/SeriesDetailPage.vue` 目前只展示一行专家团队摘要。
- `web/src/views/PipelineMonitorPage.vue` 目前只展示 L0-L5 进度条，没有输入输出摘要。

## Recommended Architecture

采用“后端聚合 + 前端只读控制台”的结构。

```text
SeriesDetailPage
  |-- link --> AgencyConsolePage
  |             |
  |             | GET /api/series/{series_id}/agency-console
  |             v
  |        SeriesRouter
  |             |
  |             | reads
  |             v
  |  Series.story_bible_json.style_lock.agency_team
  |  Episode.storyboard_json
  |  PipelineRun.layers_json
  |  GeneratedVideo
  |
PipelineMonitorPage
  |-- link --> AgencyConsolePage
```

后端 pipeline 每层完成时把摘要写入 `PipelineRun.layers_json[str(i)]`：

```json
{
  "status": "completed",
  "agency_roles": ["short_video_editing_coach", "douyin_strategist"],
  "quality_gates": ["Every render payload receives the frame reference_urls and locked style constraints."],
  "input_summary": {
    "frame_count": 6,
    "reference_count": 12,
    "style_lock_version": 1,
    "has_storyboard": true
  },
  "output_summary": {
    "frame_result_count": 6,
    "video_path": "server/data/videos/final.mp4",
    "duration": 60
  },
  "result": {}
}
```

`result` 保持兼容，摘要字段是新增的只读可观测层。

## New Backend Interface

### `GET /api/series/{series_id}/agency-console`

返回结构：

```json
{
  "ok": true,
  "series": {
    "id": "series-id",
    "title": "series title",
    "logline": "one sentence"
  },
  "style_lock": {
    "locked": true,
    "version": 1,
    "missing_assets": []
  },
  "agency_team": {
    "enabled": true,
    "version": "2026-05-21.1",
    "core_roles": [],
    "support_roles": [],
    "quality_gates": {}
  },
  "agency_team_status": {
    "enabled": true,
    "core_role_count": 5,
    "support_role_count": 4,
    "quality_gate_count": 12
  },
  "current_episode": {
    "id": "episode-id",
    "episode_number": 1,
    "title": "Pilot",
    "status": "pending"
  },
  "latest_run": {
    "id": "run-id",
    "status": "running",
    "current_layer": 4
  },
  "production_steps": [],
  "generated_video": {
    "id": "video-id",
    "video_path": "server/data/videos/final.mp4",
    "status": "completed"
  }
}
```

`production_steps` 由后端统一构造，避免前端理解业务规则：

```json
{
  "id": "auto_plan",
  "label": "自动分镜",
  "status": "completed",
  "phase": "storyboard",
  "agency_roles": ["short_video_editing_coach", "douyin_strategist", "prompt_engineer"],
  "quality_gates": ["Every frame has character_ids, scene_id, reference_urls, image_prompt, narration, duration, audio_mode, and continuity_notes."],
  "input_summary": {
    "style_lock_version": 1,
    "target_duration": 60,
    "locked_character_count": 3,
    "locked_scene_count": 4
  },
  "output_summary": {
    "frame_count": 8,
    "total_duration": 60
  },
  "persistence": ["Episode.storyboard_json"],
  "error": ""
}
```

## Frontend Page

新增页面 `web/src/views/AgencyConsolePage.vue`。

页面区块：

1. 顶部总览
   - 系列名、风格锁定状态、专家团队版本。
   - 当前运行状态。
   - 明确展示“观察模式，不打断生成流程”。

2. 专家团队地图
   - 核心专家卡片：短视频剪辑指导师、抖音策略师、AI 工程师、提示词工程师、软件架构师。
   - 支援专家卡片：图像提示词工程师、产品经理、模型 QA、现实检验者。
   - 每张卡显示职责、参与阶段、是否已注入。

3. 生产过程时间线
   - `input`：输入系列一句话。
   - `style_lock`：风格锁定。
   - `asset_completion`：角色/场景补全。
   - `reference_generation`：参考图生成。
   - `auto_plan`：自动分镜。
   - `layer_0_assets` 至 `layer_5_postproduction`。
   - `episode_writeback`：写回剧集。
   - `video_library_writeback`：写入视频资产库。

4. 透明摘要抽屉
   - 点击步骤展开。
   - 展示输入摘要、输出摘要、专家策略、质量门槛、持久化位置、失败原因。
   - 不展示敏感密钥，不直接 dump 大段 JSON。

5. 质量门槛面板
   - 分组展示 `style_lock`、`storyboard`、`render`、`final_edit` 的质量门槛。

## CEO Review

### Verdict

做。这个页面不是锦上添花，它是“一句话生成内容”进入可用阶段的信任层。用户愿意让 AI 自动剪辑的前提是能解释后台行为、定位失败原因、看到风格一致性策略确实被执行。

### Scope Decision

推荐“透明控制台”而不是“专家团队介绍页”。只介绍专家角色会让用户觉得这是包装文案；把专家角色映射到真实生产步骤，才会让系统从黑盒变成可操作产品。

### Product Risks

1. 如果只展示专家卡片，不展示每步输入输出，用户仍然无法判断生成失败原因。
2. 如果控制台加入审批按钮，会破坏“一句话自动生产内容”的主价值。
3. 如果直接展示原始 JSON，会显得工程化但不直观，非开发用户会看不懂。

### CEO Additions

- 顶部必须写明“观察模式，不打断生成流程”。
- 生产步骤必须从用户输入开始，而不是从 L0 开始，否则用户无法把一句话输入和最终视频联系起来。
- 每个失败步骤必须有“下一步建议”，例如“缺少参考图，请重新锁定风格或补充角色头像”。
- 入口必须放在系列详情页和流水线监控页，用户遇到生成失败时能立刻进入透明控制台。

## Engineering Review

### Architecture Verdict

可行，推荐新增聚合接口和摘要字段，不推荐前端直接组合多个接口。前端直接读 `style-lock`、`runs`、`episodes`、`videos` 会把业务状态机复制到 Vue 层，后续很难维护。

### Data Flow

```text
style-lock
  -> stores agency_team and quality_gates

director/auto-plan
  -> stores Episode.storyboard_json
  -> includes agency_team_version and quality_gates

pipeline L0-L5
  -> each layer writes input_summary/output_summary/agency_roles/quality_gates
  -> L5 writes edit_manifest
  -> completion writes Episode and GeneratedVideo

agency-console endpoint
  -> reads existing persisted artifacts
  -> returns production_steps

AgencyConsolePage
  -> renders read-only state
```

### Implementation Notes

- `PipelineRun.layers_json` 保持向后兼容：新增摘要字段，不改变 `result`。
- 摘要字段必须经过裁剪，避免重复存储完整 `common` payload。
- 聚合接口需要处理没有 run、没有 storyboard、没有 style lock 的状态。
- 前端页面应优先展示结构化摘要，提供“复制技术摘要”可以放到后续版本。

### Failure Modes

| Failure | Handling |
|---|---|
| 系列未锁定风格 | 控制台显示 style_lock 未完成，生产步骤停在风格锁定前 |
| 没有 Episode.storyboard_json | 自动分镜步骤显示 pending 或 missing |
| PipelineRun 还未创建 | L0-L5 显示 pending |
| L4/L5 失败 | 展示 `run.error_log` 的安全摘要和失败层 |
| GeneratedVideo 未创建 | 最终写入视频资产库步骤显示 pending 或 failed |
| 老 run 没有摘要字段 | 从 `result` 做兼容摘要，避免页面空白 |

### Test Plan

- 后端单测：`GET /api/series/{series_id}/agency-console` 在没有风格锁定时返回 pending 步骤。
- 后端单测：已有 style lock、storyboard、run layers 时返回专家团队、生产步骤和持久化位置。
- 后端单测：pipeline 完成每层后写入 `input_summary`、`output_summary`、`agency_roles`、`quality_gates`。
- 前端 API 测试：`getAgencyConsole(seriesId)` 调用正确路径。
- 前端组件测试：`AgencyConsolePage` 能展示专家团队、观察模式、生产步骤和失败摘要。
- 回归测试：现有 `SeriesDetailPage` 启动流水线逻辑不依赖控制台页面。

## Decision Audit Trail

| # | Phase | Decision | Classification | Rationale | Rejected |
|---|---|---|---|---|---|
| 1 | Autoplan | 新增独立控制台页面 | Accepted | 满足直观展示和不打断生成流程 | 只在系列详情页展开 |
| 2 | CEO | 控制台必须展示生产步骤和失败建议 | Accepted | 解决后台暗箱问题 | 只展示专家角色 |
| 3 | Eng | 新增聚合接口 | Accepted | 避免前端复制业务状态机 | 前端组合多个接口 |
| 4 | Eng | pipeline 写入安全摘要 | Accepted | 让透明记录来自真实执行过程 | 只从结果倒推过程 |
| 5 | Security | 不展示密钥和完整 provider response | Accepted | 防止敏感信息泄露 | 原始 JSON 全量展示 |

## Final Recommendation

按“后端透明摘要 + 聚合接口 + 独立只读控制台”实现。这个方案能满足用户提出的两个硬要求：前端展示生产过程，后台不得暗箱操作；同时保留一键生成主流程。
