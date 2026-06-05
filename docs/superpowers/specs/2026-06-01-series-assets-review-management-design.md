# 系列资产与审查中心管理闭环设计

## Summary

本方案补齐 dy_auto 当前 AI 视频生产链路里的基础管理缺口：系列管理、角色资产、场景资产、审查中心需要具备可查看、可编辑、可删除或作废、可通过 AI 再生成的入口。重点不是新增可视化剪辑器，也不是重做资产系统，而是在现有数据结构和接口基础上补齐前端工作流，并补少量后端缺口。

成功标准：用户可以在前端完成系列、角色、场景和生产审查素材的日常维护；角色参考图和场景参考图有明确查看入口；资产修改和 AI 再生成不会打断现有一键成片、风格锁定、阶段审查闸门和长视频调度流程。

## Current Baseline

已有能力：

- `Character` 已有基础字段和四个参考图字段：`avatar_front_url`、`avatar_side_url`、`avatar_threequarter_url`、`avatar_fullbody_url`。
- `Scene` 已有基础字段和三个参考图字段：`reference_wideshot_url`、`reference_midshot_url`、`reference_aerial_url`。
- 角色和场景后端已有列表、新建、编辑、删除、AI 批量生成接口。
- 系列详情已有风格锁定、启动生产、关联角色和场景的部分后端能力。
- 审查中心已有图片、视频片段、最终视频的通过、驳回、重新生成能力。

当前缺口：

- 角色资产页和场景资产页只有新建和批量生成，缺少详情、编辑、删除、参考图查看和参考图再生成入口。
- 系列详情页没有直接管理已关联角色和场景的入口，也缺少系列基础信息编辑。
- 风格锁定生成的角色/场景参考图只能被后端使用，前端没有画廊入口。
- 审查中心没有清晰展示当前素材使用了哪些角色/场景参考图，也没有面向图片阶段的改图/重绘入口。
- 审查中心里的生产素材不能按普通资源做物理删除，否则会破坏版本链路和审计追溯。

## Goals

- 角色资产和场景资产支持详情查看、手动编辑、删除、AI 再生成。
- 角色参考图和场景参考图支持画廊查看、大图预览、复制 URL、手动替换 URL、AI 单张重生成、AI 全部重生成。
- 系列详情支持编辑系列基础信息、删除系列、查看和维护已关联角色/场景。
- 审查中心支持查看当前素材的分镜、参考图依据、AI 审查结果、人工审查记录，并支持图片改图/重绘。
- 所有生产素材的审查操作保留版本和审计链路，不做物理删除。
- 保持现有自动生成流程兼容：没有人工打开这些管理入口时，一键成片仍按现有链路运行。

## Non Goals

- 不建设可视化时间线剪辑器。
- 不新增独立媒体资产库产品。
- 不改变 Pixelle/Seedance 执行层职责边界。
- 不绕过阶段审查闸门。
- 不把生产素材物理删除作为常规能力。
- 不重新设计模型配置中心。

## Product Design

### 1. 系列管理

系列列表保留当前信息密度，在每个系列行或卡片上增加明确操作：

- 查看详情
- 编辑
- 删除

系列详情页增加“系列设置”区域：

- 编辑字段：标题、故事概要、类型、总集数、目标时长、生成模式、是否先生成试播集。
- 删除系列：需要二次确认，明确提示会删除剧集、系列关联和流水线记录。
- 风格锁定状态继续展示，但旁边增加“查看参考图资产”入口，滚动到角色/场景资产区。

系列详情页新增两个资产区：

- 关联角色：展示角色名、角色类型、参考图完整度、查看按钮、编辑按钮、取消关联按钮。
- 关联场景：展示场景名、类型、光照、氛围、参考图完整度、查看按钮、编辑按钮、取消关联按钮。

添加关联时复用已有角色/场景资产列表，不在系列详情里重复创建复杂资产，只提供快速选择和跳转创建。

### 2. 角色资产

角色资产页从纯卡片列表升级为“列表 + 详情抽屉”：

- 卡片显示：角色名、角色类型、性别、参考图完整度、所属系列数量。
- 点击卡片打开详情抽屉。
- 抽屉内支持手动编辑：姓名、角色类型、性别、年龄段、性格、外观、服装、默认音色。
- 抽屉内支持删除：删除前检查是否已关联系列；已关联时提示影响范围，允许取消关联后删除或强制删除。
- 抽屉内支持“AI 重写角色档案”：基于当前字段和可选补充说明生成新字段，用户确认后覆盖。

角色参考图画廊：

- 正面
- 侧面
- 三分之四
- 全身

每张图提供：

- 查看大图
- 复制 URL
- 手动替换 URL
- AI 重新生成本张

同时提供“AI 重新生成全部参考图”。生成后只更新对应 URL 字段，不自动改写角色基础档案，避免意外覆盖用户编辑内容。

### 3. 场景资产

场景资产页采用与角色资产一致的详情抽屉模式：

- 卡片显示：场景名、类型、光照、氛围、参考图完整度、所属系列数量。
- 抽屉内支持手动编辑：名称、场景类型、地点描述、光照、氛围。
- 抽屉内支持删除：删除前检查系列关联。
- 抽屉内支持“AI 重写场景档案”：基于当前字段和补充说明生成新描述，用户确认后覆盖。

场景参考图画廊：

- 广角环境图
- 中景光影图
- 俯拍布局图

每张图提供查看大图、复制 URL、手动替换 URL、AI 重新生成本张。也提供“AI 重新生成全部参考图”。

### 4. 审查中心

审查中心不做物理删除，改为以下操作：

- 通过当前版本
- 驳回当前版本
- 作废当前版本
- 重新生成
- 图片阶段改图/重绘

右侧详情区新增“参考图依据”模块：

- 当前分镜使用的角色参考图。
- 当前分镜使用的场景参考图。
- 当前分镜使用的风格参考图。
- 每张图可点击大图查看。

图片审查阶段新增“改图/重绘”入口：

- 默认带入当前图片、当前分镜 prompt、角色参考图、场景参考图。
- 用户可填写修改说明。
- 调用模型配置中心中 `Image · 以图改图` 或兼容的图片生成能力。
- 新结果作为新版本资产进入审查队列，不覆盖旧版本。

视频片段和最终视频阶段保留重新生成，不新增普通删除按钮。

## API Design

复用已有接口：

- `GET /api/characters`
- `POST /api/characters`
- `PUT /api/characters/{character_id}`
- `DELETE /api/characters/{character_id}`
- `POST /api/characters/auto-generate`
- `GET /api/scenes`
- `POST /api/scenes`
- `PUT /api/scenes/{scene_id}`
- `DELETE /api/scenes/{scene_id}`
- `POST /api/scenes/auto-generate`
- `DELETE /api/series/{series_id}`
- `POST /api/series/{series_id}/characters/{character_id}`
- `POST /api/series/{series_id}/scenes/{scene_id}`
- `POST /api/video-production/assets/{asset_id}/review`
- `POST /api/video-production/assets/{asset_id}/start-regeneration`

新增或补齐接口：

- `PUT /api/series/{series_id}`：编辑系列基础信息。
- `DELETE /api/series/{series_id}/characters/{character_id}`：取消系列和角色关联。
- `DELETE /api/series/{series_id}/scenes/{scene_id}`：取消系列和场景关联。
- `POST /api/characters/{character_id}/ai-rewrite`：AI 重写角色档案，返回候选字段，不直接覆盖。
- `POST /api/scenes/{scene_id}/ai-rewrite`：AI 重写场景档案，返回候选字段，不直接覆盖。
- `POST /api/characters/{character_id}/reference-images/generate`：生成或重生成角色参考图，支持 `slot` 或 `all`。
- `POST /api/scenes/{scene_id}/reference-images/generate`：生成或重生成场景参考图，支持 `slot` 或 `all`。
- `POST /api/video-production/assets/{asset_id}/image-edit`：基于当前图片和修改说明生成新版本图片资产。
- `POST /api/video-production/assets/{asset_id}/void`：作废生产资产，仅用于审查链路，不物理删除文件。

接口原则：

- AI rewrite 返回候选结果，由前端确认后再调用现有 `PUT` 保存。
- 参考图生成失败时返回缺失项和错误原因，不吞掉失败。
- 生产素材的改图、重绘、重生成都创建新版本，不覆盖旧资产。

## Data Model

第一阶段不新增角色/场景表字段，继续使用现有 URL 字段。

可以在 `meta_json` 中记录轻量追溯信息：

```json
{
  "reference_generation": {
    "avatar_front_url": {
      "model_id": "...",
      "prompt": "...",
      "generated_at": "..."
    }
  }
}
```

生产素材作废和图片改图复用现有 `VideoProductionAsset` 版本链路。只有现有字段无法表达作废状态时，才补充枚举状态或 `meta_json` 记录，不新增独立删除表。

## Frontend Components

新增通用组件：

- `AssetDetailDrawer.vue`：详情抽屉壳层。
- `ReferenceImageGallery.vue`：参考图画廊，支持查看、复制、替换、重生成。
- `AiRewriteConfirmDialog.vue`：AI 重写候选确认弹窗。
- `DangerConfirmDialog.vue`：删除或作废二次确认。

页面改造：

- `CharactersPage.vue`：接入角色详情抽屉、编辑、删除、AI 重写、参考图画廊。
- `ScenesPage.vue`：接入场景详情抽屉、编辑、删除、AI 重写、参考图画廊。
- `SeriesDetailPage.vue`：增加系列编辑、删除、角色/场景关联管理和参考图入口。
- `AIVideoReviewPage.vue`：增加参考图依据、图片改图/重绘、作废当前版本。

## UX Rules

- 所有会破坏当前工作状态的操作都需要二次确认。
- 删除普通角色/场景前必须展示关联影响。
- 审查中心不出现“删除生产素材”文案，使用“作废当前版本”。
- AI 重写不会自动保存，必须用户确认。
- AI 参考图重生成会明确标注目标槽位，避免误覆盖其它图。
- 参考图为空时显示明确的“待生成”状态和生成入口。
- 详情抽屉内不放营销式说明文案，只展示操作和状态。

## Error Handling

- 角色/场景删除遇到关联冲突时，返回 409 和关联系列列表。
- AI 重写失败时保留用户当前表单内容。
- 参考图生成失败时标记失败槽位，允许单槽位重试。
- 图片改图失败时旧版本仍可继续审查。
- 审查中心对过期版本操作返回 409，并提示刷新队列。

## Permissions

第一阶段沿用现有管理员权限：

- 编辑、删除、AI 重写、参考图生成、审查操作都需要登录态。
- 后续如需要细分权限，再把最终审查、批量作废、资产删除拆成独立角色能力。

## Test Plan

后端测试：

- 角色编辑、删除、AI 重写候选、参考图单槽位生成、全部生成。
- 场景编辑、删除、AI 重写候选、参考图单槽位生成、全部生成。
- 系列编辑、取消关联角色、取消关联场景。
- 已关联角色/场景删除时返回影响范围或按设计处理。
- 审查素材作废不删除文件和旧版本记录。
- 图片改图创建新版本资产，不覆盖旧资产。

前端测试：

- 角色资产页可以打开详情抽屉、编辑保存、删除确认、查看参考图。
- 场景资产页可以打开详情抽屉、编辑保存、删除确认、查看参考图。
- 系列详情页可以编辑系列信息、添加/取消关联角色和场景。
- 审查中心展示参考图依据，图片素材能打开改图/重绘入口。
- 空参考图、生成失败、关联冲突、过期版本操作都有明确状态。

回归测试：

- 一键成片入口不依赖手动打开资产抽屉。
- 风格锁定仍能自动补齐缺失角色/场景参考图。
- 图片、视频、最终视频阶段审查闸门仍保持阻断能力。
- 现有 Pixelle/Seedance 路径不被破坏。

## Implementation Phases

### Phase 1: 基础编辑与删除

- 补 `PUT /api/series/{series_id}`。
- 补取消系列角色/场景关联接口。
- 前端角色、场景、系列详情接入编辑和删除。
- 删除前展示影响范围。

### Phase 2: 参考图画廊

- 新增 `ReferenceImageGallery.vue`。
- 角色页展示四类角色参考图。
- 场景页展示三类场景参考图。
- 系列详情复用画廊查看已关联资产参考图。

### Phase 3: AI 再生成

- 补角色/场景 AI 重写候选接口。
- 补角色/场景参考图生成接口。
- 前端接入 AI 重写确认和单图/全部参考图重生成。

### Phase 4: 审查中心透明化

- 审查中心展示分镜参考图依据。
- 增加图片改图/重绘入口。
- 增加作废当前版本接口和前端操作。
- 保留旧版本和审查记录。

## Autoplan Review Corrections

本次 autoplan 按 CEO、Design、Eng、DX 四个角度审查后，方案做以下收敛和补强：

- 删除能力必须分层：普通角色/场景可以删除，但已被系列、风格锁定、剧集分镜或生产任务引用的资产不得直接物理删除，前端“删除”应转为“从系列移除”或“归档/停用”，避免破坏后续自动生成。
- 系列删除必须改为安全删除策略：有生产运行、已生成视频、审查资产或入库视频时，默认只允许归档 `Series.status=archived`；只有没有生产依赖的草稿系列才允许硬删除。
- 参考图生成不能继续散落在路由私有函数里，应抽成 `reference_asset_service`，供风格锁定、角色页、场景页、审查中心复用同一套 provider 解析、prompt 组装、错误返回和追溯记录。
- AI 重写和参考图重生成必须先检查模型配置中心能力：缺少 `image_generation` 或 `image_editing` 场景模型时，前端按钮置灰并展示配置入口，不允许点击后才失败成暗箱错误。
- 审查中心的“改图/重绘”只能创建新版本生产资产，且必须继承原资产的 `run_id`、`episode_id`、`frame_id`、`storyboard_frame`、版本链和审查状态，不能变成孤立图片。
- 所有新增前端文案必须是中文，不能出现英文状态裸露；接口状态值可以保留英文，但 UI 必须统一映射为中文标签。

## Deletion And Archive Policy

### Series

系列删除分为两类：

- 草稿硬删除：仅当系列没有 `VideoProductionRun`、`VideoProductionAsset`、`GeneratedVideo`、已完成 `Episode.video_url` 或活跃 `PipelineRun` 时允许。
- 归档删除：存在任何生产依赖时，将 `Series.status` 更新为 `archived`，列表默认隐藏，详情仍可打开查看历史资产和审查记录。

归档系列不再允许启动新的一键成片任务，但已存在的审查记录、视频资产和生产运行必须可追溯。

### Character And Scene

角色/场景删除分为三类：

- 未被任何系列引用：允许硬删除。
- 仅被当前系列引用且未进入风格锁定或生产分镜：允许先取消关联，再硬删除。
- 已被 `Series.story_bible_json`、`Episode.storyboard_json`、`VideoProductionAsset.storyboard_frame` 或生产运行引用：不允许硬删除，只能归档到 `meta_json.archived=true` 并从新的选择列表中隐藏。

归档角色/场景仍可在历史系列、旧分镜和审查中心中显示，避免旧视频生产记录出现空引用。

## Service Boundary

新增服务边界：

- `reference_asset_service.py`
  - 生成角色参考图。
  - 生成场景参考图。
  - 校验槽位名称。
  - 解析模型配置中心场景能力。
  - 记录 `meta_json.reference_generation`。
  - 返回结构化缺失项和 provider 错误。
- `asset_ai_rewrite_service.py`
  - 角色档案 AI 重写候选。
  - 场景档案 AI 重写候选。
  - 只返回候选，不保存。
- `review_asset_edit_service.py`
  - 图片审查阶段以图改图。
  - 创建新版本 `VideoProductionAsset`。
  - 保留原资产版本链和审查追溯。

路由只负责鉴权、参数校验和调用服务，不直接拼 provider 请求。

## API Contracts

新增接口返回必须统一：

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "missing_requirements": []
}
```

失败时使用明确错误码：

- `ASSET_REFERENCED`：角色/场景仍被系列或生产记录引用，不能硬删除。
- `SERIES_HAS_PRODUCTION_HISTORY`：系列已有生产历史，只能归档。
- `MODEL_SCENE_NOT_CONFIGURED`：模型配置中心缺少对应场景模型。
- `REFERENCE_SLOT_INVALID`：请求的参考图槽位不存在。
- `STALE_ASSET_VERSION`：审查中心操作的不是最新版本。
- `IMAGE_EDIT_UNSUPPORTED`：当前模型不支持以图改图。

前端必须把这些错误码映射为中文提示和可执行修复入口。

## Failure Modes Registry

| 风险 | 用户看到什么 | 方案约束 |
|---|---|---|
| 删除已被分镜引用的角色 | 历史分镜或审查素材出现空角色 | 阻止硬删除，改为归档 |
| 删除已有生产历史的系列 | 视频库、审查记录和运行记录断链 | 系列归档，不硬删 |
| 参考图重生成覆盖错槽位 | 角色一致性被破坏 | 槽位白名单校验，UI 明确目标槽位 |
| AI 重写直接覆盖用户手改内容 | 用户编辑丢失 | AI 只返回候选，用户确认后保存 |
| 图片改图生成孤立资产 | 审查通过后无法推进视频阶段 | 新版本必须继承 run/episode/frame/version 链 |
| 模型未配置时仍显示可用按钮 | 点击后失败，用户不知如何修 | 前端预检查能力，按钮置灰并给配置入口 |
| 英文状态裸露 | 控制台体验割裂 | UI 统一中文标签映射 |

## Autoplan Review Report

| Review | Result | Main Finding | Plan Change |
|---|---|---|---|
| CEO Review | PASS after scope guard | 需求正确，但删除能力不能牺牲生产追溯 | 增加删除/归档策略 |
| Design Review | PASS after interaction guard | 参考图查看和审查中心依据需要更明确 | 增加画廊、中文状态、能力置灰规则 |
| Eng Review | PASS after boundary fix | 路由层不应重复 provider 逻辑，删除会破坏引用 | 增加服务边界、API 错误码和引用保护 |
| DX Review | PASS after contract fix | 新接口缺少统一响应和错误码 | 增加 API Contracts |

## Decision Audit Trail

| # | Phase | Decision | Classification | Rationale | Rejected |
|---|---|---|---|---|---|
| 1 | CEO | 删除已有生产历史的系列改为归档 | Auto-decided | 用户要删除入口，但生产资产必须可追溯 | 直接硬删 |
| 2 | Eng | 角色/场景被风格锁定或生产引用后只归档 | Auto-decided | 防止 story_bible、storyboard、review asset 空引用 | 强制删除 |
| 3 | Eng | 抽 `reference_asset_service` 复用参考图生成 | Auto-decided | 避免风格锁定和资产页各写一套 provider 调用 | 路由内复制逻辑 |
| 4 | Design | 模型未配置时按钮置灰并给配置入口 | Auto-decided | 避免用户点击后才看到失败 | 点击后弹错误 |
| 5 | DX | 新接口统一错误码和响应结构 | Auto-decided | 前端和测试更稳定，用户提示更准确 | 每个接口自由返回 |

## Spec Self Review

- 没有把本方案扩展成可视化剪辑器或新媒体库。
- 没有要求物理删除生产素材。
- AI 重写和参考图生成均要求用户确认或明确槽位，避免暗箱覆盖。
- 后端新增接口都围绕现有表和现有生产资产版本链路。
- 测试覆盖了编辑、删除、参考图查看、AI 再生成、审查中心改图和回归链路。
- autoplan 已补充删除/归档边界、服务边界、统一 API 错误码和失败模式。
