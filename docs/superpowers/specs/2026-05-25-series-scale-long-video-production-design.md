<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260525-193857.md -->

# 系列级长视频自动制片设计

## Summary

本方案将 dy_auto 的 AI 视频能力从“单集短视频自动剪辑”升级为“系列级自动制片系统”。目标不是突破 Seedance 2.0 单段 15 秒上限，而是把 240 分钟级漫剧拆成可审查、可重试、可续跑的多层生产结构：`Series -> Volume -> Episode -> Scene -> Shot -> Segment`。

系统采用混合模式：默认全自动推进，但在角色锚点、风格锚点、关键审查失败、合集打包前提供可视化确认点。最终产物同时支持多集视频库和合集版视频；多集交付是主流程，合集是最终打包产物。

## Autoplan Review Decision

`/autoplan` 审查后，本设计做出一个关键修订：**240 分钟级生产不能首版只依赖 JSON 字段保存 Segment 状态。** 240 分钟按 5 秒片段计算约 2880 个 Segment，已经超过原设计中“单个 Series 超过 1000 个 Segment 再拆表”的阈值。因此首版长视频主流程必须引入持久化生产表，JSON 只保留为快照、兼容层和导出格式。

审查结论：

- 保留混合模式、多集交付和最终合集打包。
- 将 `production_*` 表从“后续扩展”提升为 Phase 1 必须项。
- 将 Series/Episode/Scene/Shot/Segment 状态机作为核心架构，不再把 Episode storyboard JSON 当作唯一事实源。
- 前端必须支持树状生产追踪、虚拟滚动、批量筛选和局部重试，不能只展示少量卡片。
- 需要增加队列、并发、预算、幂等、断点续跑和资产清理策略。

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

现有 `Series.story_bible_json.style_lock` 可继续承载风格锁定快照。生产计划和执行状态不能继续只放在 JSON 中；长视频主流程必须使用独立生产表保存 Volume、Episode、Scene、Shot、Segment 和 Review 状态。

### 2. Volume/Episode 规划层

240 分钟级内容不能一次生成，应先拆成多个 Volume 或 Episode：

- Volume：一个篇章或合集段落，240 分钟级内容必须启用。
- Episode：主要交付单元，建议 3-8 分钟。
- Episode 内再拆 Scene。
- Scene 内再拆 Shot。
- Shot 最终拆为 5-8 秒 Segment。

自动规划时先生成系列大纲，再生成剧集列表，再逐集生成镜头表。这样可以控制人物成长线、冲突推进、伏笔回收和集间连续性。

规划层必须写入 `production_episodes`、`production_scenes`、`production_shots`。`Episode.storyboard_json` 只保存当前集的可读快照，便于兼容现有接口和前端预览。

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
- `reference_roles`
- `continuity_mode`

`reference_roles` 必须区分 `character_anchor`、`style_anchor`、`scene_reference`、`first_frame`、`previous_end_frame`。不能只传 URL 数组，否则跨场景时上一段 end frame 可能被执行层误当成同场景动作延展。

`continuity_mode` 取值建议：

- `continuous_action`：同一场景同一动作延展，可使用上一段 end frame 辅助下一段。
- `narrative_cut`：叙事剪切，可参考上一段但不得强制画面连续。
- `scene_change`：跨场景切换，不把上一段 end frame 当作 first frame。
- `montage`：蒙太奇组接，只继承角色/风格锚点。

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
- `GET /api/video-production/runs/{run_id}/tree`
  - 返回生产树，支持按层级展开、分页和筛选。
- `POST /api/video-production/runs/{run_id}/pause`
  - 暂停 Series、Episode 或 Segment 队列。
- `POST /api/video-production/runs/{run_id}/resume`
  - 从暂停或失败节点继续。
- `POST /api/video-production/segments/{segment_id}/retry`
  - 重做指定 Segment，并生成新版本。
- `POST /api/video-production/reviews/bulk-action`
  - 批量通过、拒绝、重试或人工放行审查项。
- `GET /api/video-production/runs/{run_id}/costs`
  - 返回成本、耗时、provider 调用量和剩余估算。

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

240 分钟级内容会产生数千个 Segment，前端必须避免把所有节点一次性平铺渲染。Production Monitor 首版要求：

- 按 `Volume -> Episode -> Scene -> Shot -> Segment` 折叠展示。
- Segment 列表使用分页或虚拟滚动。
- 支持按状态、审查结果、角色、场景、失败原因筛选。
- 支持批量操作：批量通过 AI 低风险项、批量重试失败项、批量暂停某集。
- 当前运行节点必须有实时进度、外部任务 ID、模型配置摘要和预计剩余量。
- 每个失败节点必须展示“失败原因、可否重试、重试会影响的下游范围”。

## DESIGN PLAN REVIEW ADDENDUM

Design review mode: APP UI. This is not a marketing page; it is a dense production control surface for repeat operators.

Initial design completeness: 6/10. The plan had the right product surfaces, but not enough detail about information hierarchy, states, responsive behavior, accessibility, and bulk-operation safety. After the additions below, target completeness is 9/10. Remaining visual QA must happen after implementation with `/design-review`.

Design artifact:

`C:\Users\HNXE\.gstack\projects\dy_auto\designs\2026-05-25-series-production-control-room-wireframe.html`

### What Already Exists

- Reuse the existing dark operations-console visual language from `VideoProductionMonitorPage.vue`, `AIVideoReviewPage.vue`, and `AgencyConsolePage.vue`.
- Reuse status semantics already present in the app: emerald/pass, sky/running, amber/warning or waiting, red/failure, slate/pending.
- Reuse existing review-center patterns: left queue, center preview, right metadata/actions.
- Reuse existing expert-console pattern for technical summaries inside collapsible details.
- Reuse existing shared components where possible: `StatusBadge.vue`, `EmptyState.vue`, app buttons/inputs/selects, and existing table/list density.
- Gap: no project-level `DESIGN.md` exists. Until one is added, implementation should follow these plan-level decisions rather than inventing new page-specific styles.

### Pass 1: Information Architecture

Production Monitor must use a three-pane control-room layout on desktop:

```text
Persistent app navigation
  -> Series header: title, run id, global status, budget, primary actions
  -> KPI strip: progress, blocked items, cost, estimated remaining, quality risk
  -> Workspace
      Left: production tree + filters
            Volume -> Episode -> Scene -> Shot -> Segment
      Center: selected node preview
              key frame/video, storyboard, prompt, references, continuity notes
      Right: review/audit/action panel
             AI review, model trace, retry impact, approve/reject/regenerate/pause
  -> Event log / provenance drawer
```

If only three things can be shown above the fold, they must be:

1. Current production status and the next required action.
2. What is blocked or risky.
3. Current cost and remaining estimate.

Navigation flow:

```text
Series Detail
  -> Style Lock
  -> Production Plan
  -> Production Run Monitor
      -> Segment Detail
      -> Review Center filtered by current run/node
      -> Video Library
      -> Collection Builder
```

The Review Center must not become a separate mental model. It should accept deep links from the production tree and preserve context: run, episode, shot, segment, selected asset, and active filters.

### Pass 2: Interaction State Coverage

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Style Lock | Skeleton rows for characters/scenes/references | Explain that style must be locked before auto-production; primary action: lock style | Show missing provider/config/reference item and recovery action | Show locked version, anchor thumbnails, relock entry | Show which anchors are missing and whether planning can continue |
| Production Tree | Tree skeleton with status placeholders | Show "no production run yet" with primary action: create plan/run | Show failed API/provider sync reason plus retry | Tree shows counts and current node | Show loaded branch while other branches page in |
| Segment Detail | Preview placeholder and metadata skeleton | Show selected tree node needs generation | Show asset missing, task failed, or review blocked | Show key frame/video, prompts, references, audit, model trace | Show image passed but video pending, or video generated but review pending |
| Review Queue | Queue skeleton | Friendly empty state: no human review required, link back to run | Show failed load and preserve filters | Show next review item automatically | Show mixed statuses with filters and bulk actions |
| Bulk Actions | Disable action while impact is calculated | Hide when no selectable items | Show why action cannot apply to some selected items | Show affected count and next state | Allow valid subset only after explicit confirmation |
| Cost View | Loading cost ledger | Show no spend yet and configured budget | Show missing pricing/model config | Show spend, remaining budget, provider breakdown | Show known spend and mark pending estimates separately |
| Collection Builder | Loading approved episodes | Show no approved episodes yet | Show compose failure without hiding approved episodes | Show final collection video and included episodes | Show which episodes are excluded or still pending |

Every destructive or expensive action must use an impact confirmation dialog before execution. "Retry Segment" must show the new version number, affected downstream nodes, estimated cost, and whether prior approved assets are retained.

### Pass 3: User Journey & Emotional Arc

| Step | User Does | User Should Feel | Plan Must Show |
|---|---|---|---|
| 1 | Enters a one-sentence brief | Oriented, not dumped into automation | A visible plan draft, not immediate dark-box generation |
| 2 | Locks style | Confident that characters and style are anchored | Character/style thumbnails, missing assets, version, relock risk |
| 3 | Starts production | In control of spend and scope | Budget ceiling, target duration, provider readiness, pause button |
| 4 | Watches progress | Able to scan without reading every row | Tree counts, current node, blocked count, cost, ETA |
| 5 | Handles failures | Safe to intervene locally | Failure reason, retry scope, previous versions, human override |
| 6 | Reviews assets | Fast decisions, low fatigue | One focused asset, AI rationale, prompt/reference context, keyboard shortcuts |
| 7 | Approves episode | Trusts the output is shippable | Episode quality rubric and final preview |
| 8 | Builds collection | Understands it is downstream packaging | Included episodes, excluded episodes, final compose progress |

Time horizon:

- First 5 seconds: user must know whether the run is healthy, blocked, over budget, or waiting for review.
- First 5 minutes: user must be able to filter, inspect, approve, retry, pause, and resume without leaving the production context.
- Long-term relationship: user must trust that every provider call, retry, version, and human override is traceable.

### Pass 4: AI Slop Risk And UI Specificity

Avoid generic dashboard-card mosaics. Cards are allowed only for repeated entities or isolated status modules; the main experience must be a stable workbench with panes, tables/tree rows, preview, and action drawers.

Specific UI direction:

- Use a calm dark operations palette aligned with the existing app: slate surfaces, cyan primary actions, emerald pass, amber warning, red failure.
- Do not introduce purple/violet gradient hero patterns, decorative blobs, marketing-style feature grids, or oversized welcome sections.
- Keep headings functional: "Production Run", "Review Queue", "Cost Ledger", "Retry Impact", not aspirational slogans.
- Keep text dense but scannable. Prefer labels, status chips, counts, and short explanations over paragraphs.
- Use monospaced text only for ids, provider task ids, hashes, paths, and model identifiers.
- Use thumbnails and previews only where they carry production meaning: anchors, key frames, video segments, and final outputs.

### Pass 5: Design System Alignment

Until a formal `DESIGN.md` exists, this feature must align with existing app conventions:

- Layout: padded admin pages, dark slate backgrounds, bordered panels, compact controls.
- Status: same semantic colors across Production Monitor, Review Center, Agency Console, and Collection Builder.
- Controls: buttons for commands, selects/chips for filters, tabs for major page sections, drawers/modals for confirmation and detail.
- Typography: use the existing app font stack unless a project-wide design-system change is made separately.
- Radius: keep operational panels and controls at the existing small/medium radius; do not introduce large bubbly cards.
- Density: desktop screens should prioritize scan density; mobile screens should prioritize one current task at a time.

New reusable components implied by this plan:

- `ProductionTree`
- `SegmentPreviewPanel`
- `ReviewActionPanel`
- `RetryImpactDialog`
- `CostLedgerSummary`
- `CollectionBuilder`
- `AnchorThumbnailStrip`

### Pass 6: Responsive And Accessibility

Responsive rules:

| Viewport | Layout |
|---|---|
| Desktop >= 1280px | Three panes: tree, preview, review/action. KPI strip stays visible above panes. |
| Tablet 768-1279px | Two panes: collapsible tree on left, preview/action stacked on right. Filters move into a sticky toolbar. |
| Mobile < 768px | Single-column task flow: status summary, current blocked item, preview, actions. Tree becomes searchable drill-down list. Right panel becomes bottom drawer. |

Accessibility rules:

- Production tree must be keyboard navigable and expose hierarchy via ARIA tree or treegrid semantics.
- Review queue must support keyboard movement between items and visible focus states.
- Status cannot rely on color only; every status needs text labels.
- All action buttons must be at least 44px touch target height on mobile.
- Dialogs must trap focus, announce title/description, and return focus to the invoking control.
- Media previews need alt text or labels derived from frame/segment ids.
- Error messages must name the problem and the recovery action.
- Body text contrast must meet at least 4.5:1; secondary text must not drop below readable contrast on slate backgrounds.

### Pass 7: Unresolved Design Decisions

| Decision | Resolution |
|---|---|
| Should the primary run UI be cards or a tree workbench? | Tree workbench. Cards only for summaries and repeated leaf items. |
| Should Review Center be standalone or contextual? | Both: standalone queue plus deep-linked contextual mode from a run/node. |
| Should mobile expose the full tree? | No. Mobile uses drill-down and search; full expanded tree is desktop/tablet only. |
| Should bulk actions execute immediately? | No. Bulk actions require impact calculation and confirmation. |
| Should collection failure block episode library delivery? | No. Collection is downstream; approved episodes stay visible and usable. |
| Should expert/team transparency interrupt generation? | No. It remains observational unless a real gate requires action. |

### Design NOT In Scope

- Pixel-perfect visual redesign of the whole admin shell.
- Marketing landing page or promotional hero.
- Visual timeline editor.
- Drag-and-drop manual shot editing.
- Multi-user approval roles and permissions.

### Design Review Completion Summary

| Area | Before | After |
|---|---:|---:|
| Information Architecture | 6/10 | 9/10 |
| Interaction State Coverage | 5/10 | 9/10 |
| User Journey | 6/10 | 9/10 |
| AI Slop Risk | 7/10 | 9/10 |
| Design System Alignment | 6/10 | 8/10 |
| Responsive & Accessibility | 4/10 | 9/10 |
| Unresolved Decisions | 5/10 | 9/10 |

Overall design score: 6/10 -> 9/10.

## Operational Controls

240 分钟级生产必须有生产控制层，否则成本、并发和失败恢复不可控：

- 队列：Episode、Shot、Segment 都要进入可暂停、可恢复的任务队列。
- 并发：按 provider 设置最大并发，例如图像生成、视频生成、AI 审查分别限流。
- 预算：Series、Volume、Episode 三层都要有预算和成本累计。
- 幂等：重复提交同一 Segment 不应生成重复资产，除非显式创建新版本。
- 断点续跑：系统重启后能从未完成、失败或待审查节点继续。
- 版本：每次重做 Segment 都生成新版本，旧版本保留审查记录。
- 清理：提供临时资产清理策略，防止数千个中间视频耗尽磁盘。
- 观测：记录 provider task id、请求参数摘要、耗时、失败码、重试次数。

## Failure Handling

- 角色锚点生成失败：标记缺失资产，阻止进入全自动生产。
- 风格参考图缺失：允许使用文字风格锁定，但前端必须提示风险。
- 单个 Segment 图像失败：只重试该 Segment。
- 单个 Segment 视频失败：只重试该 Segment。
- AI 审查失败：记录失败原因，允许重试或人工放行。
- Episode 合成失败：不影响已通过 Segment，可重新合成该 Episode。
- 合集失败：不影响已完成 Episode 视频库。
- 外部 provider 限流：任务回到 queued 状态，记录 retry_after，不占用并发槽。
- 预算超限：暂停后续 Segment，前端显示已花费、剩余估算和继续生产按钮。
- 上一段 end frame 缺失：同场景动作延展降级为 style/character anchor 续接，并标记连续性风险。
- 人物漂移连续失败：冻结该角色相关 Segment，要求重新生成角色锚点或人工放行。
- 磁盘空间不足：暂停合成和视频生成，保留数据库状态，提示清理中间资产。

## Data Model Direction

首版保留 JSON 字段作为快照和兼容层：

- `Series.story_bible_json.style_lock`
- `Episode.storyboard_json`
- `VideoProductionRun.storyboard_json`
- `VideoProductionRun.edit_manifest_json`
- `VideoProductionAsset.metadata`

但长视频主事实源必须是独立表：

- `production_plans`
- `production_episodes`
- `production_scenes`
- `production_shots`
- `production_segments`
- `production_reviews`
- `video_collections`

最低字段要求：

- `production_plans`：`series_id`、`status`、`target_total_duration_seconds`、`budget_limit`、`current_cost`。
- `production_episodes`：`plan_id`、`episode_id`、`order_index`、`status`、`target_duration_seconds`、`approved_at`。
- `production_scenes`：`episode_plan_id`、`scene_id`、`order_index`、`status`、`location_summary`。
- `production_shots`：`scene_plan_id`、`shot_id`、`order_index`、`character_ids`、`action`、`emotion`、`shot_type`、`duration_seconds`。
- `production_segments`：`shot_plan_id`、`segment_id`、`order_index`、`status`、`duration_seconds`、`continuity_mode`、`previous_segment_id`、`previous_end_frame_url`、`retry_count`。
- `production_reviews`：`target_type`、`target_id`、`review_type`、`status`、`score`、`issues_json`、`reviewer_user_id`。
- `video_collections`：`series_id`、`included_episode_ids`、`status`、`video_url`、`duration_seconds`。

索引要求：

- `(plan_id, status)`
- `(episode_plan_id, order_index)`
- `(scene_plan_id, order_index)`
- `(shot_plan_id, order_index)`
- `(status, updated_at)`
- `(target_type, target_id, review_type)`

## ENGINEERING PLAN REVIEW ADDENDUM

Mode: FULL_REVIEW.

Engineering completeness before review: 7/10. The product direction is right, but the plan needs sharper execution boundaries around data ownership, queue semantics, idempotency, Pixelle request contracts, cost accounting, pagination, and tests. After the additions below, target engineering completeness is 9/10.

### Step 0: Scope Challenge

Complexity check: triggered. The complete implementation touches more than eight files and introduces more than two new domain concepts. That is acceptable only because 240+ minute production creates hundreds or thousands of independently retryable segments; trying to force this into the current episode-level `VideoProductionRun.storyboard_json` would be a false simplification.

Minimum viable complete scope:

- Phase 1 must support stable 3-8 minute episode production with persisted `Shot -> Segment` rows, local retry, review gates, model provenance, and cost events.
- Phase 1 must not attempt 240-minute collections end-to-end before the segment queue and tree API are proven on short episodes.
- Existing `VideoProductionRun`, `VideoProductionAsset`, and `VideoReviewRecord` should be reused as compatibility and asset/review layers, but not as the only source of production truth.
- Existing `Task`/device queue should not be reused for AI video production. Device automation jobs and AI provider jobs have different ownership, lease semantics, retry policies, and operator UX.

Search check:

- FastAPI `BackgroundTasks` is suitable for lightweight work after a response, but official FastAPI guidance points to Celery-style tooling for heavy computation or distributed background work. Long video generation must therefore use a durable production queue, not request-scoped background tasks.
- Celery's task guidance emphasizes retry behavior and idempotent work. Segment generation jobs must have idempotency keys and versioned outputs before provider calls.
- SQLAlchemy supports row-level locking patterns such as `with_for_update(skip_locked=True)` on databases that support it. Because dy_auto uses SQLite in development and MySQL in production, the queue claim path needs a DB-capability abstraction: use `SKIP LOCKED` where available and an optimistic compare-and-swap fallback for SQLite.

### What Already Exists

| Need | Existing Code | Reuse Decision |
|---|---|---|
| Episode-level staged run | `server/app/services/video_production_service.py` | Reuse as the first execution adapter, then feed it from persisted Segment rows. |
| Asset persistence | `VideoProductionAsset` | Reuse, but add target linkage to `production_segment_id` or `target_type/target_id`; `frame_id` alone is not enough. |
| Review records | `VideoReviewRecord` and review item API | Reuse review concepts, but add bulk actions and target-level review for Segment/Episode/Collection. |
| State gates | `server/app/services/video_production_state.py` | Reuse pattern, but split into plan, episode, segment, asset, and collection state machines. |
| Runtime model resolution | `runtime_model_config.py` and `model_registry.py` | Reuse as provider policy source; add per-scene limits, pricing, concurrency, and config version snapshot. |
| Pixelle stage client | `pixelle_stage_client.py` and Pixelle `stages.py` | Reuse transport, but extend request schema with typed references and continuity mode. |
| Frontend monitor/review pages | `VideoProductionMonitorPage.vue`, `AIVideoReviewPage.vue` | Reuse visual and interaction patterns; replace all-assets payloads with paginated tree/detail APIs. |

### Architecture Review

Source of truth:

```text
Series.story_bible_json.style_lock     snapshot only
Episode.storyboard_json                readable episode snapshot only

production_plans                       production truth
  -> production_plan_versions          style/model/prompt snapshot per run version
  -> production_episodes
      -> production_scenes
          -> production_shots
              -> production_segments   execution atom
                  -> production_jobs   queue/lease/retry atom
                  -> VideoProductionAsset / production_artifacts
                  -> VideoReviewRecord / production_reviews
  -> video_collections
```

`VideoProductionRun` can remain as an episode-stage adapter for compatibility, but the new APIs must read and write `production_*` rows first. JSON snapshots are derived views, not authoritative state.

Execution flow:

```text
POST /director/series-plan
  -> create production_plan + version snapshot
  -> create production_episodes/scenes/shots/segments
  -> enqueue segment image jobs

Worker claim loop
  -> claim production_job with lease
  -> load segment + style/model snapshot
  -> build Pixelle stage payload
  -> submit provider task idempotently
  -> poll/sync result
  -> write asset + cost event + review record
  -> advance segment/shot/episode gates

Review action
  -> verify latest version
  -> apply approve/reject/override
  -> recompute downstream gates
  -> enqueue next eligible jobs
```

New required table: `production_jobs`.

Minimum fields:

- `id`, `plan_id`, `target_type`, `target_id`
- `stage`: `image_generation`, `image_audit`, `video_generation`, `video_audit`, `episode_compose`, `collection_compose`
- `status`: `queued`, `leased`, `running`, `retry_wait`, `blocked`, `completed`, `failed`, `cancelled`
- `idempotency_key`
- `provider_task_id`
- `attempt_count`, `max_attempts`, `retry_after`
- `lease_id`, `leased_until`
- `priority`, `scheduled_at`, `started_at`, `completed_at`
- `error_code`, `error_message`, `retryable`

Indexes:

- unique `(idempotency_key)`
- `(status, scheduled_at, priority)`
- `(plan_id, status)`
- `(target_type, target_id, stage)`
- `(lease_id, leased_until)`

New required table: `production_cost_events`.

Minimum fields:

- `plan_id`, `episode_plan_id`, `segment_id`
- `stage`, `provider`, `model_name`, `model_config_id`, `config_version`
- `estimated_cost`, `actual_cost`, `currency`
- `units_json`: duration, resolution, image count, token count, provider billing unit
- `provider_task_id`, `created_at`

Security and trust boundaries:

- API keys must never be stored in `model_trace_json`, provider payload logs, or frontend responses.
- Reference URLs should be validated before being sent to providers. Allow HTTP(S) and configured local asset hosts; reject file paths, private network URLs, and unsupported schemes unless explicitly whitelisted.
- Provider task ids, prompt hashes, model ids, and config versions are safe for UI. Raw prompts can be shown to admins, but external API keys and signed URLs must be redacted.
- Bulk approval and human override must record reviewer id, timestamp, target version, and reason.

### State Machine Review

Plan states:

```text
draft -> planning -> style_blocked -> ready -> running
running -> paused -> running
running -> blocked -> running
running -> completed
running -> failed
running -> cancelled
```

Segment states:

```text
planned
  -> image_queued -> image_running -> image_review_pending -> image_approved
  -> video_queued -> video_running -> video_review_pending -> video_approved
  -> completed

Any active state -> paused
Any generation/review state -> failed
Any failed/rejected state -> retry_queued
Any old version -> superseded
```

Gate rules:

- A segment cannot enter `video_queued` until its latest image asset is approved.
- A segment cannot enter `completed` until its latest video asset is approved or explicitly overridden.
- A shot is complete only when all latest segment versions are complete.
- An episode is composable only when all required shots are complete and the episode review gate passes.
- A collection is composable only from approved episode videos.
- Retrying a segment creates a new segment/asset version and marks downstream dependent jobs as `blocked` or `retry_queued` according to continuity mode.

### Pixelle / Seedance Contract Review

The current Pixelle video stage appends `previous_end_frame_url` to later frames whenever it exists. That is unsafe for long-form generation because cross-scene cuts and montage segments must not be treated as continuous action extension.

Required request fields for Pixelle video frames:

- `frame_id`
- `production_segment_id`
- `continuity_mode`
- `approved_image_url`
- `previous_end_frame_url`
- `reference_roles`: ordered objects with `{ role, url, character_id?, scene_id?, priority }`
- `duration`
- `video_prompt`
- `return_last_frame: true`

Execution rule:

- `continuous_action`: pass `previous_end_frame_url` as a continuity/first-frame aid.
- `narrative_cut`: include previous frame only as low-priority context, not as a forced first frame.
- `scene_change`: do not pass previous end frame as first-frame input.
- `montage`: pass only character/style anchors unless the shot explicitly opts in.

Pixelle response must preserve per-segment `status`, `retryable`, `error_code`, `message`, `provider_task_id`, `last_frame_url`, and model metadata.

### Code Quality Review

Implementation should avoid growing `video_production_service.py` into a single orchestration file. Split responsibilities:

| Service | Responsibility |
|---|---|
| `production_plan_service.py` | Plan creation, version snapshot, episode/scene/shot/segment materialization. |
| `production_queue_service.py` | Job enqueue, claim, lease, retry, pause/resume, idempotency. |
| `production_segment_service.py` | Segment state transitions, retry versioning, continuity impact. |
| `production_review_service.py` | AI review, human review, bulk actions, gate recomputation. |
| `production_cost_service.py` | Estimate, budget checks, actual cost events, budget pause. |
| `production_tree_service.py` | Paginated tree and detail query assembly for frontend. |
| `pixelle_execution_service.py` | Payload mapping to Pixelle/Seedance and response normalization. |

Rules:

- Define status constants or enums in one module; do not scatter string literals across routers, services, and Vue components.
- Keep routers thin: validate request, call service, return response.
- Keep provider-specific mapping outside domain state machines.
- Use transaction boundaries around "claim job -> mark leased" and "persist result -> advance gates".
- Any service that mutates state must return the updated object and not require callers to remember follow-up recompute calls.

### Test Review

Detected framework:

- Backend: `pytest` with `server/tests`.
- Frontend: `vitest` under `web/src/__tests__`.

Coverage diagram:

```text
CODE PATHS                                                     USER FLOWS
[GAP] production_plan_service.create_plan()                    [GAP] [->E2E] Brief -> style lock -> plan -> run tree
  ├── [GAP] style locked                                       [GAP] [->E2E] Start short episode and finish final video
  ├── [GAP] style missing blocks auto-execution                [GAP] Review image failure -> retry segment -> approve new version
  └── [GAP] model config missing returns readiness issue        [GAP] Budget exceeded -> queue pauses -> resume with new budget

[GAP] production_queue_service.claim_next_job()                [GAP] Production Monitor tree filters 2000+ segments
  ├── [GAP] claim with lease                                   [GAP] Bulk approve low-risk reviews with impact confirmation
  ├── [GAP] expired lease reclaims                             [GAP] Mobile drill-down view for current blocked item
  ├── [GAP] idempotent duplicate enqueue                       [GAP] Collection compose excludes unapproved episodes
  └── [GAP] SQLite fallback claim path

[GAP] pixelle_execution_service.submit_segment()
  ├── [GAP] continuous_action passes previous_end_frame
  ├── [GAP] scene_change does not pass previous as first frame
  ├── [GAP] provider timeout creates retry_wait job
  └── [GAP] provider hard failure creates failed asset/review

[GAP] production_review_service.apply_bulk_action()
  ├── [GAP] approve latest only
  ├── [GAP] reject with reason
  ├── [GAP] stale version conflict
  └── [GAP] downstream impact calculation

[GAP] production_cost_service.record_cost_event()
  ├── [GAP] estimated cost before provider call
  ├── [GAP] actual cost after sync
  └── [GAP] budget ceiling prevents new jobs
```

Required backend tests:

- `server/tests/test_production_plan_models.py`: migrations/models, indexes, relationships, version snapshots.
- `server/tests/test_production_plan_service.py`: style readiness, segment materialization, JSON snapshot compatibility.
- `server/tests/test_production_queue_service.py`: enqueue idempotency, lease claim, expired lease recovery, pause/resume, SQLite fallback.
- `server/tests/test_production_segment_continuity.py`: reference roles, continuity modes, last-frame propagation rules.
- `server/tests/test_production_cost_service.py`: estimate, actual event, budget pause, resume.
- `server/tests/test_video_production_tree_api.py`: paginated tree, filters, detail payload, no all-assets response.
- `server/tests/test_production_bulk_review.py`: bulk approve/reject/retry, stale latest-version conflict, reviewer audit trail.
- `server/tests/test_collection_builder.py`: approved episode inclusion, compose failure isolation, final collection asset.
- `server/tests/test_long_video_mocked_e2e.py`: 3 episodes with multiple scenes/shots/segments, mocked providers, local retry, collection compose.

Required frontend tests:

- `web/src/__tests__/production-tree-page.test.js`: desktop tree/detail/action layout, filters, pagination.
- `web/src/__tests__/review-bulk-actions.test.js`: impact dialog, partial valid selection, stale conflict message.
- `web/src/__tests__/cost-ledger-summary.test.js`: known vs estimated cost and budget pause state.
- `web/src/__tests__/collection-builder.test.js`: approved/pending/failed episode states and independent retry.
- `web/src/__tests__/production-monitor-responsive.test.js`: mobile drill-down behavior and bottom drawer action panel.

LLM/eval requirement:

- Planning prompts that create `Scene/Character/Action/Emotion/Duration`, continuity notes, and reference role assignments need deterministic mocked unit tests plus a small golden-output eval set. At minimum include: same-scene action extension, scene change, montage, two-character dialogue, and style-anchor-only fallback.

### Performance Review

High-risk paths:

- `GET /api/video-production/runs/{run_id}` currently returns all assets for a run. This cannot scale to thousands of segments. Add paginated `tree`, `assets`, and `node detail` endpoints; keep the current run endpoint as summary-only.
- Do not store all segment facts only inside JSON blobs. Filtering by status, review result, character, scene, and failure reason must use indexed columns or narrow JSON indexes where supported.
- Cost and progress counters should be cached on plan/episode rows and updated transactionally when jobs complete; do not recompute the entire tree on every page load.
- Use bounded page sizes and server-side filters. Default page size should be 50-100 Segment rows.
- Avoid fetching every review record for every asset in list views. Return latest review summaries via subquery or denormalized latest fields.

### Failure Modes

| Failure | Test Required | Handling Required | User Visibility |
|---|---|---|---|
| Provider returns task id then polling times out | Yes | job -> `retry_wait` with `retry_after`; keep provider_task_id | Show external task id and retry time |
| Duplicate start request | Yes | same idempotency key returns existing job/task | Show already running state |
| Worker dies after provider submit before DB update | Yes | reconcile by idempotency key/provider task id | Show task as leased expired, then recovered |
| Style lock version changes mid-run | Yes | run uses version snapshot; relock requires new plan version | Show current run style version |
| Previous end frame missing | Yes | continuity degradation per mode | Show continuity risk |
| Budget exhausted | Yes | pause new queued jobs before provider call | Show spend, remaining, resume action |
| Bulk approve stale version | Yes | reject action with 409/conflict | Show reload/newer version message |
| Collection compose fails | Yes | keep episode videos approved | Show collection retry without hiding episodes |
| Disk full during asset write | Yes | fail job retryably, keep DB state | Show cleanup action and affected node |

Critical silent gaps after this addendum: 0, assuming the required tests and error paths are implemented.

### Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| A. Data model and migrations | `server/app/db_models.py`, `server/alembic`, `server/tests` | None |
| B. Queue/cost/state services | `server/app/services`, `server/tests` | A |
| C. Pixelle contract adapter | `server/app/services`, `D:\devWorkspace\Pixelle-Video\api`, provider tests | A |
| D. API routes and schemas | `server/app/routers`, `server/tests` | A, B |
| E. Frontend control room UI | `web/src/views`, `web/src/components`, `web/src/api`, frontend tests | D API shape |
| F. Collection builder | `server/app/services`, `server/app/routers`, `web/src/views`, tests | A, B, D |
| G. Mocked E2E/regression suite | `server/tests`, `web/src/__tests__` | B, C, D, E |

Parallel lanes:

- Lane A: data model/migrations first.
- Lane B: queue/cost/state services after A.
- Lane C: Pixelle contract adapter after A; can run parallel with Lane B if write scopes stay separate.
- Lane D: API routes after B/C.
- Lane E: frontend after API contracts are stable.
- Lane F: collection builder after core API.
- Lane G: E2E tests run throughout, but final E2E depends on D/E/F.

Conflict flags:

- Lane B and Lane C both touch `server/app/services`; coordinate file ownership or run sequentially.
- Lane D and Lane F both touch `server/app/routers`; keep collection routes isolated or sequence them.

### Engineering NOT In Scope

- Replacing the whole app task system.
- Introducing a visual timeline editor.
- Rewriting Pixelle-Video internals beyond the stage request/response contract needed by dy_auto.
- Distributed multi-worker deployment in Phase 1. Phase 1 may use a DB-backed worker loop with leases; it must be adapter-compatible with Celery/RQ later.
- Multi-user approval permissions.
- Publishing or distribution workflows.

### Engineering Review Completion Summary

| Area | Result |
|---|---|
| Step 0 Scope Challenge | Scope accepted with sequencing: short-episode wedge first, 240+ minute scale after queue/tree proof |
| Architecture Review | 7 issues found and resolved in plan: source of truth, queue, cost ledger, Pixelle contract, security, state machine, asset linkage |
| Code Quality Review | 4 issues found and resolved in plan: service split, enums/constants, thin routers, transaction boundaries |
| Test Review | Coverage diagram produced, 18 gaps identified and converted to required tests |
| Performance Review | 5 issues found and resolved in plan: all-assets endpoint, JSON filtering, counters, page size, latest review lookup |
| NOT in scope | Written |
| What already exists | Written |
| Failure modes | 0 silent critical gaps after required handling/tests |
| Outside voice | Skipped; prior Codex outside review timed out and no subagent was requested |
| Parallelization | 7 lanes: 2 can run parallel after model baseline, rest sequenced by API contract |
| Lake Score | 9/10 complete path selected over JSON/BackgroundTasks shortcuts |

## Testing Plan

- 单测：长 Shot 会拆成多个 5-8 秒 Segment。
- 单测：Segment 继承角色锚点最多 9 张、风格锚点最多 3 张。
- 单测：Prompt 明确包含 `@Image 1` 角色锁定说明。
- 单测：下一 Segment 会接收上一 Segment 的 `last_frame_url`。
- 单测：跨场景 Segment 不错误地把上一场景 end frame 当作强制第一帧。
- 单测：AI 审查失败只阻断局部节点。
- 单测：Segment 级 retry 只创建新版本，不覆盖旧资产和旧审查记录。
- 单测：重复提交同一 Segment 任务具有幂等行为。
- 单测：预算超限会暂停后续队列，不会继续调用外部 provider。
- 单测：状态树 API 支持分页、状态筛选和层级展开。
- 集成测试：生成一个 3 集短剧，每集多镜头，逐集入库，再合成合集。
- 集成测试：模拟 240 分钟计划，验证 2000+ Segment 的分页查询、恢复、统计不退化。
- 集成测试：模拟 provider 限流、任务超时、进程重启后从断点继续。
- 回归测试：现有 Pixelle 快速创作、Seedance 独立面板、单集 auto-plan 不被破坏。

## Rollout Plan

1. Phase 1：建立生产表、状态机和 Segment 队列，保证 1-8 分钟集级生产稳定。
2. Phase 2：增加系列/篇章/剧集规划，把 240 分钟内容拆成 Episode 队列。
3. Phase 3：完善 Segment 级审查、局部重试、版本保留、预算和并发控制。
4. Phase 4：增加合集打包、合集审查和合集视频库。
5. Phase 5：在前端做完整生产追踪、批量审查、成本视图和资产库浏览。

## Success Criteria

- 一句话输入后可以生成多集漫剧生产计划。
- 每集能被拆成多场景、多镜头、5-8 秒 Segment。
- 每个 Segment 都带角色锚点、风格锚点和连续性说明。
- 长视频生产失败时可以定位到具体 Episode、Shot 或 Segment。
- 单集视频可独立入库，合集版可在全部单集通过后生成。
- 前端能直观看到每一步生产状态、审查结果和失败原因。
- 240 分钟级计划能稳定生成 2000+ Segment 队列，并支持分页查看、暂停、恢复和局部重试。
- 每个外部模型调用都有 provider task id、模型配置摘要、耗时、成本估算和失败码。
- 合集失败不会影响已通过的 Episode 视频库。

## GSTACK REVIEW REPORT

### Review Scope

本次 `/autoplan` 审查对象是系列级长视频自动制片设计。UI scope: yes，涉及 Production Monitor、Review Center、Collection 页面。DX scope: yes，涉及 API、状态机、外部 Pixelle/Seedance 集成和任务恢复。

Codex 外部声音尝试运行 12 分钟后超时，无输出文件，按降级规则记录为 `codex-unavailable`。本报告由 primary reviewer 完成，后续进入实现计划前建议再跑一次 `plan-eng-review` 或代码审查。

### CEO Review

Premises checked:

| Premise | Verdict | Decision |
|---|---|---|
| 240 分钟视频必须拆成多集、多场景、多镜头、多 Segment | Valid | Keep |
| 多集交付是主流程，合集是最终打包产物 | Valid | Keep |
| 首版可只用 JSON 保存生产状态 | Invalid for 240+ minutes | Changed to production tables in Phase 1 |
| 人工确认点只放在风格锁定和失败节点 | Mostly valid | Keep, but add bulk review and collection gate |

Strategic findings:

- Critical: 原设计的 JSON-first 策略和 240 分钟目标冲突。Fix: 生产表提前到 Phase 1。
- High: 缺少成本、并发和暂停策略会让超长生产不可控。Fix: 增加 Operational Controls。
- High: 合集应是派生产物，不能阻塞单集视频库交付。Fix: Success Criteria 明确合集失败不影响 Episode。

### Design Review

Initial autoplan design score: 7/10 after amendments.
Full `/plan-design-review` score: 6/10 -> 9/10 after adding the dedicated design addendum.

Findings:

- High: “树状生产追踪”需要分页或虚拟滚动，否则 2000+ Segment 会拖垮页面。Fix: Frontend Requirements 增加分页、虚拟滚动和筛选。
- High: 审查中心不能只支持单条通过/拒绝。Fix: 增加批量通过、批量重试、批量暂停。
- Medium: 失败状态需要显示影响范围。Fix: 失败节点必须展示重试会影响的下游范围。
- High: 缺少明确页面信息架构、空/错/部分状态、响应式和可访问性规则。Fix: 增加 `DESIGN PLAN REVIEW ADDENDUM`，定义三栏控制台、状态表、用户旅程、AI slop 防线、响应式和 a11y 要求。

### Engineering Review

Architecture graph:

```text
Series story bible
  -> production_plans
      -> production_episodes
          -> production_scenes
              -> production_shots
                  -> production_segments
                      -> image asset -> image review
                      -> video asset -> video review
          -> episode final video
      -> video_collections
```

What already exists:

| Need | Existing code | Gap |
|---|---|---|
| Style lock | `series.py`, `Series.story_bible_json.style_lock` | Good for snapshot, not enough for segment execution state |
| Single episode auto-plan | `director.py /api/director/auto-plan` | Needs series/episode/shot/segment planning APIs |
| Staged production | `video_production_service.py` | Episode-level only, no production tree or queue |
| Asset review | `video_production.py /review-items` | Needs bulk actions and segment tree filters |
| Seedance execution | Pixelle `stages.py`, `ark_plan_v3.py` | Needs typed reference roles and continuity modes |
| Transparency UI | `AgencyConsolePage.vue`, `AIVideoReviewPage.vue` | Needs scale-ready tree, batch controls, cost/progress views |

Failure modes:

| Failure | Risk | Required handling |
|---|---|---|
| Provider rate limit | Wastes retries, blocks pipeline | Queue retry_after and release concurrency slot |
| Segment duplicated by retry | Cost and review confusion | Idempotency key plus versioned retry |
| Character drift across many episodes | Product quality collapse | Role anchor audit, drift threshold, freeze affected segments |
| Cross-scene end frame misuse | Visual continuity artifact | `continuity_mode` and typed `reference_roles` |
| Disk exhaustion | Production stop | Asset retention and cleanup policy |

Test plan artifact:

`C:\Users\HNXE\.gstack\projects\dy_auto\HNXE-feature-video-review-fixes-series-scale-long-video-test-plan-20260525-195243.md`

### DX Review

DX score: 7/10 after amendments.

Developer-facing concerns:

- API names must distinguish plan/run/review/collection. Fix: API Shape now includes run tree, costs, bulk actions, retry and collection endpoints.
- Error messages must include problem, cause and fix. Fix: Failure Handling now names specific recoveries for rate limit, budget, missing end frame and disk issues.
- Implementers need clear data ownership. Fix: Data Model Direction defines production tables as facts and JSON as snapshots.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Move production tables into Phase 1 | Auto | Completeness | 240 minutes creates thousands of segments immediately | JSON-only first version |
| 2 | Eng | Add typed reference roles | Auto | Explicit over clever | URL arrays cannot distinguish character anchors from previous end frames | Ambiguous `reference_urls` only |
| 3 | Eng | Add continuity modes | Auto | Pragmatic | Cross-scene cuts should not be treated like action extension | Blindly passing previous end frame |
| 4 | Design | Require tree pagination and virtual scrolling | Auto | Completeness | 2000+ Segment UI cannot render as flat cards | Simple card list |
| 5 | Design | Add batch review and retry actions | Auto | Bias toward action | Human review at segment scale needs bulk operations | Single-item-only review |
| 6 | Eng | Add queue, budget, concurrency and cleanup controls | Auto | Boil the lake | These are in the blast radius of long production reliability | Treat operations as later concern |
| 7 | DX | Add run tree, cost, pause/resume, retry and bulk APIs | Auto | Explicit over clever | Developers need predictable endpoint boundaries | Overloading existing run endpoint |
| 8 | Eng | Add `production_jobs` as durable queue table | Auto | Explicit over clever | Heavy provider work needs leases, retry, idempotency, and recovery | FastAPI request/background-task only |
| 9 | Eng | Add `production_cost_events` | Auto | Completeness | Long runs need spend audit before and after provider calls | Cost only on Episode/Series summary |
| 10 | Eng | Treat `VideoProductionRun` as compatibility/asset-stage layer | Auto | Simplicity with correctness | Existing run/asset code is valuable but cannot be the production fact source | Replace all current staged production code immediately |
| 11 | Eng | Add typed Pixelle continuity contract | Auto | Explicit over clever | Previous end frame must be mode-aware, not blindly appended | URL-only frame payload |
| 12 | Eng | Split production services by responsibility | Auto | Maintainability | A single orchestration service would become too large and fragile | Continue growing `video_production_service.py` |
| 13 | Eng | Replace all-assets run payload with paginated tree/detail APIs | Auto | Performance | 2000+ segments cannot load as one run response | Keep `GET /runs/{id}` returning every asset |

### Not In Scope

- Visual timeline editor.
- Douyin publishing workflow.
- Multi-user approval workflow.
- Rights management for generated assets.
- Rewriting Pixelle-Video internals beyond typed request metadata needed by dy_auto.

### Cross-Phase Themes

- The design must treat Segment as a first-class persisted entity.
- Long-video success depends as much on operations controls as on model prompts.
- The frontend must be a production control surface, not just a gallery.
- Reference images need roles, not only ordered URLs.

## CEO REVIEW ADDENDUM

Mode: `SELECTIVE EXPANSION`.

This feature is an enhancement of an existing system, so the review treats the current scope as the baseline and only accepts expansions that are load-bearing for series-scale production.

### Step 0A: Premise Challenge

| Premise | CEO Verdict | Required Plan Adjustment |
|---|---|---|
| The product goal is "one sentence creates a long video" | Reframe | One sentence should create a visible production plan; style lock, cost ceiling, and review gates still decide whether execution starts. |
| 240+ minutes can be treated as one long video job | Reject | Treat it as a series/volume/episode production system. Collection output is a packaging artifact, not the primary production unit. |
| Segment-level operations can wait until later | Reject | At 5-8 seconds per segment, even a 60-minute project creates hundreds of segments. Segment must be first-class from Phase 1. |
| Human review should not interrupt automation | Keep with constraint | Human review should be optional for low-risk steps, but every blocking AI failure must be visible and actionable. No backend dark-box operations. |
| Character/style consistency can be solved mostly by prompts | Reject | Prompts are necessary but insufficient. The business feature is anchored assets, typed reference roles, drift scoring, and local retry. |

### Step 0B: Existing Code Leverage

| Capability | Current Leverage | CEO Read |
|---|---|---|
| Style lock | `server/app/routers/series.py` and `Series.story_bible_json.style_lock` | Keep as the confirmation gate and style snapshot. Do not overload it with production status. |
| Episode auto-plan | `server/app/routers/director.py /api/director/auto-plan` | Reuse for the episode wedge, then graduate to series/episode/shot/segment planning APIs. |
| Staged video production | `server/app/services/video_production_service.py` and `server/app/routers/video_production.py` | Good wedge for image review, video review, and compose. Needs production tree and queue semantics before 240-minute work. |
| Transparency surface | `server/app/services/agency_console.py`, `web/src/views/AgencyConsolePage.vue`, `web/src/views/VideoProductionMonitorPage.vue` | Must evolve from activity display into a real production control room. |
| Pixelle/Seedance execution | `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` and `ark_plan_v3.py` | Keep Pixelle as execution layer, but dy_auto owns orchestration, gates, provenance, and run status. |
| Model configuration | `server/app/routers/ai_config.py`, model schema data, and registry tests | Use the model center as the policy source for provider choice, limits, cost estimates, and concurrency. |

### Step 0C: Dream State Mapping

```text
Current state:
  Episode-level staged production + style lock + Seedance/Pixelle execution.

This plan:
  Series production tree with persisted Segment queue, review gates, cost controls, local retry, and optional collection packaging.

12-month ideal:
  An inspectable AI showrunner/studio:
    - reusable character universes and style packs
    - production runs that can pause, resume, fork, retry, and audit every model call
    - cost/quality dashboards per series, episode, provider, and character
    - episode-first delivery with collection packaging as a downstream artifact
```

### Step 0C-bis: Implementation Alternatives

| Option | Description | Completeness | CEO Decision |
|---|---|---:|---|
| A. Episode-only wedge | Extend existing episode pipeline with better long-shot splitting and anchors, but no full production tree. | 6/10 | Reject as final architecture; acceptable only as a temporary migration bridge. |
| B. Series production control plane | Add persisted `production_*` tables, Segment queue, review gates, budget controls, tree UI, and collection packaging. | 9/10 | Recommended and accepted. |
| C. Full studio platform | Add team approval, schedule boards, templates, analytics, rights management, publishing, and marketplace-like asset reuse. | 10/10 | Defer. Too broad for the current implementation plan. |

### Accepted Selective Expansions

| Expansion | Effort | Decision | Why |
|---|---:|---|---|
| Production budget and cost ledger | M | Accepted | Without a cost ceiling, long-running generation can burn external model spend before anyone notices. |
| Character/style drift scoreboard | M | Accepted | This is the core quality promise for long-form AI video, not decoration. |
| Segment-level provenance | M | Accepted | Every generated image/video needs provider task id, model config summary, prompt hash, reference roles, review result, and retry version. |
| Collection builder as separate artifact | S | Accepted | It preserves episode-first delivery and prevents collection failures from blocking the video library. |
| Multi-user approval workflow | L | Deferred | Valuable later, but not required for solo/operator flow. |
| Visual timeline editor | L | Deferred | Explicit non-goal; tree controls and local retry solve the current operational need. |
| Douyin publishing workflow | L | Deferred | Publishing is downstream of reliable generation and review. |

### Strategic Product Decisions

- P0: The first sellable wedge is repeatable 3-8 minute episodes with stable characters, visible steps, and local retry. 240+ minute productions should validate the same architecture at scale, not define the first usable milestone.
- P0: `Segment` is the economic and operational atom. It carries cost, retry, provider task id, reference roles, continuity mode, review state, and version history.
- P0: "One sentence generation" must mean one sentence to create a production plan, not one sentence to silently spend model budget and emit an unreviewable 240-minute asset.
- P1: Style lock is a blocking business gate. If required character anchors or style anchors are missing, the system can plan but must not enter full auto-execution.
- P1: The frontend must explain production state in operator language: what is running, what is blocked, what it costs, what retry changes, and what downstream nodes are affected.
- P1: A shippable episode needs a quality rubric: character identity, style consistency, scene continuity, motion coherence, audio/subtitle packaging, and review outcome.

### CEO Rescue Map

| Failure | Business Risk | Rescue Requirement |
|---|---|---|
| Model API key or provider config is missing | User thinks automation is broken | Stop at planning/style-lock readiness; show missing model scene and exact config item. |
| Long run exceeds budget | Unexpected spend | Pause queue before new provider calls, preserve completed assets, and show continue-with-new-budget action. |
| Character drift detected after many segments | Core promise fails | Freeze affected character/segments, keep unaffected episodes running, require anchor regeneration or human override. |
| Review backlog becomes too large | Operator cannot manage output | Provide filters, bulk low-risk approval, batch retry, and per-episode acceptance gates. |
| Collection composition fails | Completed episodes look lost | Keep episode videos approved and visible; collection can retry independently. |

### CEO Final Position

Implement Option B. Keep the implementation plan ambitious enough to support 240+ minute series, but sequence the rollout around stable episode delivery first. The plan should not add timeline editing, publishing, or multi-user workflow until the production tree, Segment queue, review gates, and cost controls are proven.
