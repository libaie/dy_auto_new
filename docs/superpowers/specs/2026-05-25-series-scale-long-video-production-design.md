# 系列级长视频自动制片设计

## Summary

本方案将 dy_auto 的 AI 视频能力从“单集短视频自动剪辑”升级为“系列级自动制片系统”。目标不是突破 Seedance 2.0 单段 15 秒上限，而是把 240 分钟级漫剧拆成可审查、可重试、可续跑的多层生产结构：`Series -> Volume -> Episode -> Scene -> Shot -> Segment`。

系统采用混合模式：默认全自动推进，但在角色锚点、风格锚点、关键审查失败、合集打包前提供可视化确认点。最终产物同时支持多集视频库和合集版视频；多集交付是主流程，合集是最终打包产物。

## Goals

- 支持超过 1 分钟、甚至超过 240 分钟的系列化视频生产。
- 用全局角色锚点稳定人物长相、发型、服饰和体态，单角色最多使用 9 张参考图。
- 用 1-3 张风格参考图稳定色调、光影、镜头语言和场景美学。
- 按导演式结构拆解长内容：每个镜头都有 `Scene / Character / Action / Emotion / Duration`。
- Seedance 2.0 执行层以 5-8 秒片段为默认生成单位，最多不超过模型配置上限。
- 使用上一段 `last_frame_url` 辅助下一段连续动作生成。
- 支持镜头图、镜头视频、单集成片、合集成片的 AI 审查和人工审查。
- 支持局部失败重试，不因一个镜头失败重跑整集或整个系列。
- 生产过程必须在前端可追踪，不能出现后台暗箱操作。

## Non-Goals

- 不把 Seedance 单段生成时长强行扩展到 15 秒以上。
- 不做可视化时间线剪辑器。
- 不做抖音发布闭环。
- 不要求首版实现复杂资产版权管理。
- 不要求首版实现多用户协作审批流。

## Recommended Architecture

### 1. Series 制片层

Series 是最高级生产单元，保存全局风格锁定结果：

- 角色圣经：姓名、身份、外观、服装、声音、性格边界。
- 角色锚点：正面、侧面、三分之四、全身、表情或动作补充图，最多 9 张。
- 场景圣经：核心场景、空间布局、灯光、色调、情绪。
- 风格锚点：1-3 张统一视觉参考图。
- 声音包装：TTS 策略、角色音色、BGM 基调。
- 字幕与成片包装：字幕样式、水印、片头片尾、输出规格。

现有 `Series.story_bible_json.style_lock` 可继续承载首版数据。后续如果生产规模明显扩大，再将 `Volume / ScenePlan / ShotPlan` 拆成独立表。

### 2. Volume/Episode 规划层

240 分钟级内容不能一次生成，应先拆成多个 Volume 或 Episode：

- Volume：一个篇章或合集段落，可选。
- Episode：主要交付单元，建议 3-8 分钟。
- Episode 内再拆 Scene。
- Scene 内再拆 Shot。
- Shot 最终拆为 5-8 秒 Segment。

自动规划时先生成系列大纲，再生成剧集列表，再逐集生成镜头表。这样可以控制人物成长线、冲突推进、伏笔回收和集间连续性。

### 3. Shot/Segment 执行层

Shot 是导演语义单元，Segment 是模型执行单元。

一个 Shot 必须包含：

- `scene_id`
- `character_ids`
- `action`
- `emotion`
- `duration`
- `shot_type`：全景、中景、特写等
- `camera_movement`
- `narration`
- `image_prompt`
- `video_prompt`
- `reference_urls`
- `continuity_notes`

如果 Shot 超过 8 秒，系统自动拆成多个 Segment。Segment 继承 Shot 的角色、场景和风格约束，并追加：

- `parent_shot_id`
- `segment_index`
- `segment_count`
- `previous_segment_id`
- `previous_end_frame_url`
- `expected_end_state`

### 4. Reference Anchor Policy

角色锚点顺序必须稳定。Prompt 中明确使用：

```text
@Image 1 locks the character face, hairstyle, outfit, body proportions, and costume continuity.
```

规则：

- 角色参考图优先排在 `reference_urls` 前面。
- 主角色第一张图必须是最稳定的身份锚点。
- 单角色最多 9 张角色参考图。
- 风格参考图最多 3 张。
- 场景参考图不能覆盖角色锚点，只能补充环境、灯光和空间布局。
- 每个 Segment 都必须继承相同角色锚点和风格锚点。

### 5. Continuity Policy

长视频连续性由三层保证：

- 全局连续性：Series story bible 固定人物、场景、色调、声音包装。
- 镜头连续性：Shot 记录动作、情绪、镜头类型和预期结束状态。
- 片段连续性：Segment 使用上一段 `last_frame_url` 辅助下一段生成。

当跨场景切换时，不强制使用上一段 end frame 作为第一帧，但仍应保留在参考列表或 continuity notes 中，说明这是叙事衔接而不是动作延展。

## Production Flow

1. 用户输入一句话或系列概要。
2. 系统生成 Series story bible。
3. 系统生成角色和场景，并补齐角色多角度锚点图、场景/风格参考图。
4. 用户确认或重新锁定全局风格。
5. 系统生成全系列或当前篇章大纲。
6. 系统生成 Episode 列表。
7. 系统逐集生成 Scene/Shot plan。
8. 系统把 Shot 拆成 5-8 秒 Segment。
9. 文生图阶段生成每个 Segment 的关键帧。
10. AI 审查关键帧；失败 Segment 局部重做。
11. 人工可选审查关键帧。
12. 图生视频阶段生成 Segment 视频。
13. AI 审查视频一致性、人物漂移、画面异常、动作断裂。
14. 人工可选审查视频。
15. Episode 合成并写入视频库。
16. 全部 Episode 通过后，系统生成合集版。
17. 合集版进行最终审查并入库。

## Review Gates

首版保留这些确认点：

- 风格锁定确认：角色锚点和风格锚点必须可见。
- Episode 规划确认：可跳过，但必须可查看。
- 关键帧失败确认：AI 审查失败时允许人工放行或重做。
- Segment 视频失败确认：允许局部重做。
- Episode 成片确认：通过后进入视频库。
- 合集打包确认：避免未通过剧集进入合集。

## API Shape

建议新增或扩展以下接口：

- `POST /api/series/{series_id}/style-lock`
  - 生成或重建角色/场景/风格锚点。
- `POST /api/director/series-plan`
  - 生成系列或篇章级大纲。
- `POST /api/director/episode-plan`
  - 生成某集的 Scene/Shot plan。
- `POST /api/director/shot-segments`
  - 将 Shot 拆成可执行 Segment。
- `POST /api/video-production/runs`
  - 创建系列级或集级生产任务。
- `POST /api/video-production/runs/{run_id}/resume`
  - 从失败节点继续。
- `POST /api/video-production/runs/{run_id}/retry`
  - 重做指定 Episode、Shot 或 Segment。
- `POST /api/video-production/collections`
  - 把已通过 Episode 合成为合集版。

现有 `POST /api/director/auto-plan` 可作为单集入口保留，但长视频主流程应迁移到 Episode/Shot/Segment 分层接口。

## Frontend Requirements

前端必须展示生产过程，避免暗箱操作：

- Series 页面展示风格锁定状态、角色锚点、风格锚点、缺失资产。
- Episode 页面展示场景、镜头、片段拆分结果。
- Production Monitor 展示当前生产层级：Series、Episode、Scene、Shot、Segment。
- 每个 Segment 展示关键帧、视频片段、审查结果、失败原因、重试入口。
- Episode 视频库展示单集成片。
- Collection 页面展示合集打包进度和最终合集视频。

首版不做时间线编辑器，但要做“树状生产追踪 + 局部重试”。

## Failure Handling

- 角色锚点生成失败：标记缺失资产，阻止进入全自动生产。
- 风格参考图缺失：允许使用文字风格锁定，但前端必须提示风险。
- 单个 Segment 图像失败：只重试该 Segment。
- 单个 Segment 视频失败：只重试该 Segment。
- AI 审查失败：记录失败原因，允许重试或人工放行。
- Episode 合成失败：不影响已通过 Segment，可重新合成该 Episode。
- 合集失败：不影响已完成 Episode 视频库。

## Data Model Direction

首版可以先复用 JSON 字段：

- `Series.story_bible_json.style_lock`
- `Episode.storyboard_json`
- `VideoProductionRun.storyboard_json`
- `VideoProductionRun.edit_manifest_json`
- `VideoProductionAsset.metadata`

当以下情况出现时再拆表：

- 单个 Series 超过 1000 个 Segment。
- 需要跨会话高频查询 Segment 状态。
- 需要批量重试、分页审查或并发生产多个 Episode。

拆表方向：

- `production_plans`
- `production_episodes`
- `production_scenes`
- `production_shots`
- `production_segments`
- `production_reviews`
- `video_collections`

## Testing Plan

- 单测：长 Shot 会拆成多个 5-8 秒 Segment。
- 单测：Segment 继承角色锚点最多 9 张、风格锚点最多 3 张。
- 单测：Prompt 明确包含 `@Image 1` 角色锁定说明。
- 单测：下一 Segment 会接收上一 Segment 的 `last_frame_url`。
- 单测：跨场景 Segment 不错误地把上一场景 end frame 当作强制第一帧。
- 单测：AI 审查失败只阻断局部节点。
- 集成测试：生成一个 3 集短剧，每集多镜头，逐集入库，再合成合集。
- 回归测试：现有 Pixelle 快速创作、Seedance 独立面板、单集 auto-plan 不被破坏。

## Rollout Plan

1. Phase 1：完善单集长视频，保证 1-8 分钟集级生产稳定。
2. Phase 2：增加系列/篇章/剧集规划，把 240 分钟内容拆成 Episode 队列。
3. Phase 3：增加 Segment 级状态、审查和局部重试。
4. Phase 4：增加合集打包与合集审查。
5. Phase 5：在前端做完整生产追踪和资产库浏览。

## Success Criteria

- 一句话输入后可以生成多集漫剧生产计划。
- 每集能被拆成多场景、多镜头、5-8 秒 Segment。
- 每个 Segment 都带角色锚点、风格锚点和连续性说明。
- 长视频生产失败时可以定位到具体 Episode、Shot 或 Segment。
- 单集视频可独立入库，合集版可在全部单集通过后生成。
- 前端能直观看到每一步生产状态、审查结果和失败原因。
