# 多模型分镜视频 + 角色档案 + 系列生成 — 行业最高标准架构 v4

## 背景

Pixelle-Video 已通过透明代理整合到 dy_auto（spec 2026-05-12），Seedance 2.0/Kling 端点代理已就绪。

用户的核心业务是**可商业化的多角色连续短剧**，质量优先，不计成本。全流程中每个环节使用的 AI 模型均可通过前端自主配置，不硬编码。

## 运行模式

### 模式 A：逐步确认（默认）

```
人工输入故事创意 → AI生成角色图 → [审图+人工确认] → AI生成场景图 → [审图+人工确认]
→ AI生成剧本 → [人工确认分镜] → 渲染 → [审图+人工确认] → 后期 → 成品
```

### 模式 B：全自动一键生成

```
人工输入一句话 → 全自动七层流水线 → 成品
  "生成一个30集的都市爱情短剧，男主是高冷总裁，女主是活泼实习生"
          ↓
  ┌───────────────────────────────────────────────────────────────┐
  │  ⓪ 自动生成角色图(FLUX) → ① 审图(自动,失败重试3次)             │
  │  → ② 自动生成场景图(FLUX) → ③ 审图(自动)                     │
  │  → ④ LLM生成30集剧本(含钩子+故事圣经)                         │
  │  → ⑤ LLM生成分镜表 + 模型路由 + 音频策略                      │
  │  → ⑥ 批量渲染(Seedance/Kling,并发3-5,断点续传)                │
  │  → ⑦ 审图抽查(视频关键帧提取) → 不通过自动重渲染              │
  │  → ⑧ FFmpeg合成 + 钩子衔接 + 后期包装                         │
  │  → ⑨ 30个mp4 + 跨集质量报告 + 成本报表                        │
  └───────────────────────────────────────────────────────────────┘
```

---

## 第 ⓪ 层：资产自动生成（Asset Auto-Generator）

### 角色图自动生成

**输入：** 角色文字描述（appearance + personality + outfit）
**输出：** 4 张多角度参考图（正面/侧面/3/4侧脸/全身）

**模型：** `ai_models.asset_generation.character_model`（默认 FLUX via RunningHub）

**后处理：** 生成后自动送入审图节点①，不通过（<70分）自动重试最多 3 次。3 次仍不通过 → 降级为「需人工上传」。

### 场景图自动生成

**输入：** 场景文字描述（description + lighting + mood）
**输出：** 2-3 张不同角度场景参考图（广角/中景/俯拍）

**模型：** `ai_models.asset_generation.scene_model`（默认 FLUX）

### CDN/OSS 自动上传（Critical — 解决 Seedance 公网 URL 需求）

> **问题：** FLUX 生成的参考图存在本地，Seedance/Kling API 需要**公网可访问的 HTTP URL**，无法直接使用本地路径。

**方案：**
- 集成 OSS/CDN SDK（默认：阿里云 OSS / 火山引擎 TOS）
- 资产生成后自动上传到 OSS，获得公网 URL
- 公网 URL 写入 `characters.avatar_*_url` 和 `scenes.reference_urls_json`
- OSS 配置通过 `/ai-config` 页面管理（endpoint/bucket/access_key）

```
FLUX 生成本地图 → OSS SDK 上传 → 获得公网 URL → 写入 DB → Seedance API 可用
```

> **降级方案：** OSS 未配置时，角色图仍可手动上传到图床后粘贴 URL。

---

## 第 ① 层：资产工坊（Asset Workshop）

### 1.1 角色管理

**数据库：**
```sql
characters (
  id, name, display_name,
  -- 多角度参考图（自动生成后上传 OSS 获得公网 URL）
  avatar_front_url, avatar_profile_url,
  avatar_three_quarter_url, avatar_full_body_url,
  -- TTS 绑定
  voice_id, voice_speed,
  -- 描述
  appearance, personality, outfit,
  -- 审图状态
  audit_status,           -- pending/approved/warning/rejected
  audit_score,
  audit_issues_json,
  -- 元数据
  series_id,              -- 所属系列 (FK)
  created_at, updated_at
)
```

### 1.2 场景管理

```sql
scenes (
  id, name, display_name,
  reference_urls_json,    -- OSS 公网 URL 列表
  description, lighting,
  audit_status, audit_score, audit_issues_json,
  series_id,
  created_at, updated_at
)
```

### 1.3 AI 审图引擎

**三层审查节点：**

```
节点① — 入库审查 (Pre-ingestion)
  时机: 上传或自动生成角色/场景参考图后
  模型: ai_models.audit_models.multi_image_compare (默认 Gemini 2.5 Pro)
  输入: 多张静态参考图
  审核: 人脸匹配度 / 服装一致性 / 关键特征
  输出: 一致性评分 (0-100) + 逐项差异 + 通过(≥85)/警告(70-84)/拒绝(<70)
  行动: 拒绝 → 阻止使用，自动重试或提示人工

节点② — 生成审查 (Post-generation)
  时机: Seedance/Kling 生成分镜帧后
  ⚠️ 生成的是视频，不是图片。处理方式:
    1. FFmpeg 提取首帧+中间帧+尾帧 3 张静态图
    2. 3 张静态图分别与角色参考图组对比
    3. 评分取 3 张图的平均分
  模型: ai_models.audit_models.single_image_detail (默认 GPT-4o)
  抽样: 首帧必审 + 随机 20% + 角色首次出场帧
  行动: 不通过 → 自动重新生成 (最多 2 次)，仍不通过 → 标记人工审核

节点③ — 跨集审查 (Cross-episode)
  时机: 系列全部渲染完成后
  模型: ai_models.audit_models.batch_quick_scan (默认 Gemini Flash)
  输入: 每集角色首次出场帧（提取的静态图）
  审核: 同角色跨集长相一致性、同场景跨集环境一致性
  输出: 跨集一致性报告
```

**审图 API：**
```python
POST /api/audit/characters/{id}/validate
POST /api/audit/frames/{frame_id}/check
POST /api/audit/series/{id}/cross-check
GET  /api/audit/reports/{id}
```

**审图服务：** `server/app/services/audit_service.py` — 从 `ai_models.audit_models` 读取模型配置，所有模型可通过 `/ai-config` 替换。

---

## 第 ② 层：故事工坊（Story Workshop）

### 2.1 故事圣经（Story Bible）— Critical

> **问题：** LLM 上下文窗口装不下 30 集完整剧本，逐集生成时后期剧集会"忘记"前期设定。

**方案：** 在系列剧本生成前，先创建一个「故事圣经」文档，贯穿所有 LLM 调用。

```
故事圣经 (Story Bible):
  ├── 世界观 (World Rules): "现代都市，2024年上海，无超自然元素"
  ├── 角色档案 (Character Sheets):
  │   ├── 小明: {性格/外貌/口头禅/关系网/成长弧光}
  │   └── 小红: {性格/外貌/口头禅/关系网/成长弧光}
  ├── 情节时间线 (Plot Timeline):
  │   ├── 第1-5集: 相遇与误会
  │   ├── 第6-15集: 感情升温与外部冲突
  │   └── ...
  ├── 伏笔追踪 (Chekhov's Gun Tracker):
  │   ├── 第3集埋下: 总裁的家族秘密
  │   └── 第25集回收: ...
  └── 角色出场表 (Character Appearance Map):
      ├── 第1集: 小明✓ 小红✓ 总裁✗
      └── ...
```

**LLM 调用时注入：** 每次生成剧本/分镜时，将圣经摘要（~2K tokens）注入 system prompt。

**圣经更新：** 每生成 5 集剧本后，LLM 自动更新圣经（追加新伏笔、更新角色状态）。

### 2.2 剧本生成 LLM 链

```
第 1 层 — 圣经创建
  模型: ai_models.script_llm.model
  输入: logline + genre + characters
  输出: 故事圣经 (角色档案+世界观+情节时间线)

第 2 层 — 系列大纲
  输入: 圣经摘要 + logline
  输出: N 集大纲，每集 5-8 句话

第 3 层 — 逐集剧本（分批生成，每批 5 集）
  输入: 圣经摘要 + 大纲 + 前一批的剧情摘要
  输出: 完整剧本 (角色标注+场景标注+情绪标注+钩子)

第 4 层 — 分镜拆分
  模型: ai_models.storyboard_llm.model
  输入: 逐集剧本 + 圣经摘要
  输出: StoryboardFrame[] (含镜头设计+音频策略)
```

### 2.3 系列 & 剧集管理

```sql
series (
  id, title, logline, genre, tone,
  story_bible_json,          -- 故事圣经结构化数据
  characters_json, scenes_json,
  target_duration_per_episode,
  status, created_at, updated_at
)

episodes (
  id, series_id, episode_number, title,
  outline, script,
  hook_json,                 -- {type, scene, dialogue, next_episode_link}
  storyboard_json,           -- 分镜表
  media_workflow,            -- 本集视频模型
  audio_mode,                -- "tts" | "seedance_native" | "hybrid"
  tts_workflow,
  status, result_video_path, duration,
  version,                   -- 生成版本号 (支持 A/B 迭代)
  created_at
)

pipeline_runs (              -- 流水线运行状态（持久化 + 断点续传）
  id, series_id, mode,       -- "step_by_step" | "fully_automatic"
  current_layer,             -- 当前执行到第几层
  layers_json,               -- 每层状态 {layer: 0, status: "completed", checkpoint: {...}}
  total_cost_estimate,       -- 预估总成本
  actual_cost_so_far,        -- 已产生成本
  started_at, paused_at, completed_at,
  status                     -- running/paused/completed/failed
)

audit_reports (
  id, audit_node,            -- "ingestion" | "generation" | "cross_episode"
  target_type, target_id,    -- character/scene/frame/series
  model_used, score, passed,
  details_json,              -- 逐项差异
  created_at
)

prompt_history (             -- Prompt 调试器存储
  id, pipeline_run_id, step, -- "asset_generation" | "script_writing" | ...
  model_used, prompt_text, response_text,
  tokens_used, cost,
  created_at
)
```

---

## 第 ③ 层：导演工坊（Director Workshop）

### 3.1 分镜设计（含音频策略）

```python
class DirectorFrame:
    # 基础
    index: int
    narration: str
    character_ids: list[str]
    scene_id: str

    # 镜头设计
    shot_type: str           # close_up/medium/wide/tracking/aerial
    camera_angle: str        # eye_level/low_angle/high_angle/dutch
    camera_movement: str     # static/pan_left/zoom_in/dolly
    target_duration: float

    # ⚠️ 音频策略 — 每帧独立决策
    audio_mode: str          # "tts" | "seedance_native" | "bgm_only" | "silent"
    # "tts":              TTS 配音 + 视频静音轨道
    # "seedance_native":  Seedance 原生声画同步 (该帧跳过 TTS)
    # "bgm_only":         仅背景音乐 (过渡/空镜/开场帧)
    # "silent":           无声 (结尾黑屏帧)

    voice_id: str            # audio_mode=tts 时使用
    bgm_track: str           # 背景音乐轨道名称（可选，覆盖系列默认 BGM）

    # 视频模型
    media_workflow: str      # seedance_2.0 / kling_3.0 / wan_2.7 / flux
```

### 3.2 音频策略规则

> **原则：** 一集内统一音频策略，避免频繁切换导致听感不一致。

| 系列级别 | 每集可独立选择 `audio_mode` |
|----------|---------------------------|
| `tts_only` | 全系列用 TTS 配音（Edge-TTS 多角色），Seedance 生成静音视频 |
| `seedance_native` | 全系列用 Seedance 原生声画同步（该模式下 TTS 配置无效） |
| `hybrid` | 对话帧用 TTS，过渡/空镜/高潮帧用 Seedance 原生 |

**BGM 配置：**
```
ai_models.audio.bgm:
  default_track: "bgm/calm_piano.mp3"    # 默认背景音乐
  per_scene_overrides:                   # 场景级别覆盖
    climax: "bgm/intense_orchestra.mp3"
    cliffhanger: "bgm/tense_drone.mp3"
    romantic: "bgm/soft_guitar.mp3"
```

### 3.3 模型路由器

| 镜头类型 | 路由规则 | 音频策略 |
|----------|----------|----------|
| 人物特写/对话 | → strengths:["人脸"] | tts（多角色配音） |
| 广角/建立 | → strengths:["4K","电影感"] | bgm_only |
| 动作/高潮 | → strengths:["多角色","60s"] | seedance_native |
| 钩子/悬念 | → strengths:["电影感"] | bgm_only + 紧张 BGM |
| 静态文字 | → FLUX + HTML | silent |

---

## 第 ④ 层：渲染引擎（Render Engine）

### 4.1 多模型渲染 + 断点续传

Pixelle-Video `frame_processor._step_generate_media()` 动态路由，所有模型从 `ai_models.video_models` 读取：

```python
async def _step_generate_media(frame, config):
    model_config = get_model_config(config.media_workflow)
    audio_mode = frame.audio_mode

    # 根据 audio_mode 决定视频是否需要原生音频
    if audio_mode == "seedance_native":
        # Seedance 原生声画同步
        return await _seedance_render(frame, config, model_config, with_audio=True)
    elif audio_mode == "tts":
        # 先生成 TTS 音频，再生成静音视频
        return await _seedance_render(frame, config, model_config, with_audio=False)
    elif audio_mode == "bgm_only":
        return await _render_with_bgm_only(frame, config, model_config)
```

### 4.2 流水线持久化与断点续传

```python
class PipelineRun:
    """流水线运行时状态，每一步完成后写入 DB"""

    async def run_layer(self, layer: int):
        checkpoint = self.load_checkpoint(layer)
        if checkpoint and checkpoint["status"] == "completed":
            logger.info(f"Layer {layer} already completed, skipping")
            return checkpoint["result"]

        # 执行这层的所有任务
        for task in self.get_tasks(layer):
            if task.id in checkpoint.get("completed_tasks", []):
                continue  # 跳过已完成的任务
            result = await task.execute()
            checkpoint["completed_tasks"].append(task.id)
            self.save_checkpoint(layer, checkpoint)  # 每个任务完成后立即写 checkpoint

    async def resume(self):
        """从最后一个 checkpoint 恢复"""
        last_layer = self.load_last_completed_layer()
        for layer in range(last_layer + 1, TOTAL_LAYERS):
            await self.run_layer(layer)
```

### 4.3 长剧集处理（90-120s/集）

一集 = 6-12 个分镜帧 → 每帧 5-60s → FFmpeg 拼接 + 片头尾 = 90-120s

```
30 集 × 10 帧/集 = 300 次 Seedance 调用
并发 3-5 个，约 2-3 小时完成
每 5 集自动写 checkpoint，崩溃后从上一个 checkpoint 恢复
```

### 4.4 错误预算与降级策略

| 错误类型 | 预估概率 | 降级策略 |
|----------|----------|----------|
| Seedance API rate limit | 5% | 指数退避重试 (1s→2s→4s→8s)，最多 5 次 |
| Seedance 任务失败 | 10% | 自动重试最多 2 次，仍失败 → 切换备用模型 |
| Kling 队列超时 | 15% | 超时后降级到 Seedance |
| FLUX 出图异常 | 3% | 重试最多 3 次，调整 prompt 增加约束 |
| OSS 上传失败 | 1% | 重试 3 次，仍失败 → 暂停流水线 |

**成本实时监控：** 每 10 次 API 调用更新 `pipeline_runs.actual_cost_so_far`，UI 实时展示。

---

## 第 ⑤ 层：后期包装（Post Production）

- FFmpeg xfade 转场（dissolve/wipe/zoom）
- 片头/片尾 HTML 模板渲染
- 字幕叠加（可配置字体/大小/颜色/动画）
- BGM 混音（场景级别切换）

---

## 全自动流水线 API

```
POST /api/pipeline/auto-generate
  Body: {
    "logline": "...",
    "genre": "urban_romance",
    "mode": "fully_automatic",
    "audio_strategy": "tts_only",       # 系列级音频策略
    "pilot_first": true                 # 是否先生成 1 集试点
  }
  → pipeline_run_id

GET  /api/pipeline/status/{id}          # 进度 + 成本
POST /api/pipeline/{id}/pause           # 暂停
POST /api/pipeline/{id}/resume          # 恢复（断点续传）
POST /api/pipeline/{id}/retry_layer     # 重跑某一层
GET  /api/pipeline/{id}/cost            # 成本明细
WS   /ws/pipeline/{id}                  # SSE 进度事件
```

### 试点生成（Pilot Mode）

```
pilot_first: true
  → 先生成 1 集完整剧集
  → 人工审核质量（审图报告+成品预览）
  → 确认后批量生成剩余 29 集
  → 不满意 → 调整参数 → 重新试点
```

### 版本管理

- 每集支持多个 `version`（同一集的不同生成尝试）
- UI 可切换版本对比
- 保留最近 3 个版本，旧版本可手动删除

---

## 全透明可观测性

```
「流水线监控」页面 (/pipeline/{run_id}):
  ├── 总进度条 + 当前步骤 + 预估剩余时间 + 当前成本
  ├── 每层展开：
  │   ├── 状态 + 耗时 + 完成/总数
  │   ├── 每个子任务: [查看产物] [查看原始Prompt] [查看响应]
  │   └── 审图结果: 评分 + 差异项
  ├── 产出物预览
  └── 成本报表 (预估 vs 实际)

「Prompt 调试器」组件:
  ├── 所有 AI 调用的 prompt 可点击展开
  ├── 支持运行前预览/编辑 prompt 模板
  ├── A/B 对比模式
  └── Prompt 历史库 (prompt_history 表)
```

---

## AI 模型配置中心

所有环节的模型通过 `/ai-config` 页面 + `Pixelle-Video/config.yaml` 的 `ai_models` 段管理：

```yaml
ai_models:
  script_llm:        # 剧本生成
  storyboard_llm:    # 分镜拆分
  asset_generation:  # 资产生成（角色/场景图）
    character_model: {...}
    scene_model: {...}
    oss:             # CDN/OSS 配置
      provider: "aliyun_oss"
      endpoint: "oss-cn-shanghai.aliyuncs.com"
      bucket: "dy-auto-assets"
      access_key: "${OSS_ACCESS_KEY}"
      secret_key: "${OSS_SECRET_KEY}"
  video_models: []   # 视频生成模型列表
  audit_models:      # 审图模型
  tts_models: []     # TTS 模型列表
  audio:             # BGM 配置
    bgm: {...}
  cliffhanger:       # 钩子 prompt 模板
```

---

## 文件改动清单

### Pixelle-Video

| 文件 | 改动说明 |
|------|----------|
| `pixelle_video/services/frame_processor.py` | 多模型路由器 + audio_mode 分支 |
| `pixelle_video/services/ai_model_registry.py` | **新** 读取 ai_models 配置 |
| `pixelle_video/services/asset_generator.py` | **新** 角色/场景图生成 + OSS 上传 |
| `pixelle_video/services/kling_render.py` | **新** Kling 3.0 渲染 |
| `pixelle_video/services/seedance_render.py` | **新** Seedance 渲染 (with_audio 参数) |
| `pixelle_video/pipelines/auto_pipeline.py` | **新** 全自动编排器 + 断点续传 |
| `pixelle_video/pipelines/director.py` | **新** 导演流水线 |
| `pixelle_video/services/post_production.py` | **新** 转场/片头尾/字幕/BGM |
| `pixelle_video/models/storyboard.py` | DirectorFrame + audio_mode |
| `pixelle_video/config.py` | 解析 ai_models 完整配置 |

### dy_auto 后端

| 文件 | 改动说明 |
|------|----------|
| `server/app/db_models.py` | Character/Scene/Series/Episode/PipelineRun/AuditReport/PromptHistory |
| `server/app/routers/pipeline.py` | **新** 流水线 API + 断点续传 |
| `server/app/routers/audit.py` | **新** 审图 API |
| `server/app/routers/ai_config.py` | **新** AI 模型配置 CRUD |
| `server/app/routers/characters.py` | 角色 CRUD + OSS 上传回调 |
| `server/app/routers/scenes.py` | 场景 CRUD |
| `server/app/routers/series.py` | 系列+剧集 CRUD + LLM 剧本 |
| `server/app/routers/director.py` | 分镜编排 API |
| `server/app/services/audit_service.py` | **新** 审图引擎 |
| `server/app/services/pipeline_service.py` | **新** 流水线编排引擎 |
| `server/app/services/oss_service.py` | **新** OSS/CDN 上传服务 |

### dy_auto 前端

| 文件 | 改动说明 |
|------|----------|
| `web/src/views/AiConfigPage.vue` | **新** AI 模型配置 |
| `web/src/views/PipelineMonitorPage.vue` | **新** 流水线监控 + 成本 |
| `web/src/views/CharactersPage.vue` | 角色管理 + 审图状态 |
| `web/src/views/ScenesPage.vue` | 场景管理 |
| `web/src/views/SeriesPage.vue` | 系列管理 + 剧本生成 |
| `web/src/views/DirectorPage.vue` | **新** 导演时间线 |
| `web/src/components/video-studio/AuditReport.vue` | **新** 审图报告面板 |
| `web/src/components/video-studio/ModelRouter.vue` | **新** 模型路由配置 |
| `web/src/components/video-studio/PromptDebugger.vue` | **新** Prompt 调试器 |
| `web/src/router/index.js` | 新增 6 个路由 |
| `web/src/constants/navigation.js` | 新增 6 个菜单项 |

**总估算：≈ 6500 行，18-22 天。**

---

## 验证计划

1. `/ai-config` 修改 script_llm → 测试连接 → 剧本使用新模型
2. 新增 video_models 条目 → 前端下拉框自动出现
3. 上传角色多角度图 → OSS 自动上传 → 审图自动触发
4. `pilot_first: true` → 生成 1 集 → 审核 → 确认后批量生成
5. 流水线运行中 kill 服务器 → 重启 → `resume` 从中断处继续
6. 30 集生成完成 → 跨集审图报告输出 → 成本报表核对
7. A/B 对比：同一集 2 个版本 → 审图评分对比 → 选择更好的
