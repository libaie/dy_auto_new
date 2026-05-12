# 多模型分镜视频 + 角色档案 + 系列生成 — 行业最高标准架构

## 背景

Pixelle-Video 已通过透明代理整合到 dy_auto（spec 2026-05-12），Seedance 2.0/Kling 端点代理已就绪。

用户的核心业务是**可商业化的多角色连续短剧**，质量优先，不计成本。全流程中每个环节使用的 AI 模型均可通过前端自主配置，不硬编码。

## 总体架构（五层设计）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          dy_auto 管理后台                                  │
│                                                                          │
│  ┌────────────┐  管理入口  ┌──────────────────────────────────────────┐  │
│  │ AI 模型配置  │←────────→│         AI 视频生产线                      │  │
│  │ (全局)      │  所有模型  │                                          │  │
│  │            │  可替换    │  ①资产工坊 → ②故事工坊 → ③导演工坊         │  │
│  │ 每个环节用   │           │       ↓          ↓          ↓             │  │
│  │ 什么模型由   │           │  ④质量管理(审图) ← → ⑤渲染 & 后期          │  │
│  │ 用户选择     │           │                                          │  │
│  └────────────┘           └──────────────────────────────────────────┘  │
│                                                                          │
│  /api/ai-config  /api/assets  /api/series  /api/director  /api/audit     │
│  /api/pixelle-proxy  /api/seedance  /api/kling                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 第 0 层：AI 模型配置中心（全局基础设施）

> **核心原则：** 生产线上每个环节的 AI 模型，用户可从前端自主选择/切换。不硬编码任何模型名。

### 配置存储

`Pixelle-Video/config.yaml` 新增 `ai_models` 段 + dy_auto DB `ai_model_configs` 表：

```yaml
# Pixelle-Video/config.yaml — ai_models 段
ai_models:
  # ---- ① 故事工坊 ----
  script_llm:           # 剧本生成
    provider: "deepseek"       # deepseek / openai / anthropic / qwen / custom
    model: "deepseek-chat"
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://api.deepseek.com/v1"
    temperature: 0.8
    max_tokens: 4096

  # ---- ② 导演工坊 ----
  storyboard_llm:       # 分镜拆分
    provider: "deepseek"
    model: "deepseek-chat"
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://api.deepseek.com/v1"

  # ---- ③ 渲染 ----
  video_models:         # 视频生成模型列表（前端下拉框来源）
    - id: "seedance_2.0"
      name: "Seedance 2.0"
      provider: "volcengine"
      endpoint: "https://ark.cn-beijing.volces.com/api/v3"
      api_key: "${SEEDANCE_API_KEY}"
      strengths: ["人脸", "多角色", "60s长视频"]
      enabled: true
    - id: "kling_3.0"
      name: "Kling 3.0"
      provider: "kuaishou"
      access_key: "${KLING_ACCESS_KEY}"
      secret_key: "${KLING_SECRET_KEY}"
      strengths: ["4K", "AI导演", "电影感"]
      enabled: true
    - id: "wan_2.7"
      name: "Wan 2.7"
      provider: "runninghub"
      workflow: "runninghub/video_wan2.7.json"
      strengths: ["开源", "无限制", "自部署"]
      enabled: true

  # ---- ④ 审图 ----
  audit_models:
    multi_image_compare:  # 多图一致性对比
      provider: "google"
      model: "gemini-2.5-pro"
      api_key: "${GEMINI_API_KEY}"
    single_image_detail:  # 单图细节审核
      provider: "openai"
      model: "gpt-4o"
      api_key: "${OPENAI_API_KEY}"
    batch_quick_scan:      # 批量快速筛查
      provider: "google"
      model: "gemini-2.5-flash"
      api_key: "${GEMINI_API_KEY}"

  # ---- ⑤ TTS ----
  tts_models:
    - id: "edge-tts"
      name: "Microsoft Edge-TTS"
      type: "local"
      voices: ["zh-CN-XiaoxiaoNeural", "zh-CN-YunjianNeural", ...]
    - id: "index-tts"
      name: "Index-TTS (声音克隆)"
      type: "runninghub"
      workflow: "runninghub/tts_index2.json"
```

### 管理 UI

`/ai-config` 页面 — 全局 AI 模型配置：
- 每个环节显示当前使用的模型（名称 + provider logo）
- 下拉选择预设模型或填入自定义端点
- **API Key 管理：** 每个 provider 的 Key 独立配置，加密存储
- **模型测试：** 每行一个「测试连接」按钮，发测试请求验证连通性
- **预设模板：** "行业最高标准" / "预算优先" / "开源自部署" 一键切换所有模型

### 数据流

```
前端 /ai-config → PUT /api/pixelle/config (更新 ai_models 段)
                → Pixelle-Video ConfigManager.reload()
                → 所有下游服务读取最新 ai_models 配置
```

---

## 第 1 层：资产工坊（Asset Workshop）

### 1.1 角色管理

**数据库：** `characters` 表（dy_auto DB）
```sql
characters (
  id, name, display_name,
  avatar_front_url, avatar_profile_url,
  avatar_three_quarter_url, avatar_full_body_url,
  voice_id, voice_speed,
  appearance, personality, outfit,
  audit_status,           -- pending/approved/warning/rejected
  audit_score,            -- AI 审图评分 0-100
  audit_issues_json,      -- 审图发现的差异项
  created_at, updated_at
)
```

**管理 UI：** `/characters` 页面
- 角色卡片网格（多角度照片缩略图 + 审图状态标签）
- 上传多角度照片后**自动触发 AI 审图**，不通过则阻止使用
- 审图结果展示：一致性评分 + 差异项清单 + 通过/警告/拒绝

### 1.2 场景管理

```sql
scenes (
  id, name, display_name,
  reference_urls_json,
  description, lighting,
  audit_status, audit_score, audit_issues_json,
  created_at, updated_at
)
```

### 1.3 AI 审图引擎（Quality Audit）

**三层审查节点：**

```
节点① — 入库审查 (Pre-ingestion)
  时机: 用户上传角色/场景参考图后
  模型: ai_models.audit_models.multi_image_compare (默认 Gemini 2.5 Pro)
  输入: 多张参考图 (正面+侧面+3/4+全身)
  审核: 人脸匹配度 / 服装一致性 / 关键特征
  输出: 一致性评分 (0-100) + 逐项差异 + 通过(≥85)/警告(70-84)/拒绝(<70)
  行动: 拒绝 → 阻止使用，提示重传

节点② — 生成审查 (Post-generation)
  时机: Seedance/Kling 生成分镜帧后，FFmpeg 合成前
  模型: ai_models.audit_models.single_image_detail (默认 GPT-4o)
  输入: 生成帧 + 角色参考图组
  审核: 生成画面与参考图的匹配度
  抽样: 首帧必审 + 随机 20% + 角色首次出场帧
  行动: 不通过 → 自动重新生成 (最多 2 次)，仍不通过 → 标记人工审核

节点③ — 跨集审查 (Cross-episode)
  时机: 系列全部渲染完成后
  模型: ai_models.audit_models.batch_quick_scan (默认 Gemini Flash)
  输入: 每集角色首次出场帧
  审核: 同角色跨集长相一致性、同场景跨集环境一致性
  输出: 跨集一致性报告
```

**审图 API 端点：**

```python
# dy_auto 后端新增: server/app/routers/audit.py
POST /api/audit/characters/{id}/validate   # 节点① — 上传后手动/自动触发
POST /api/audit/frames/{frame_id}/check    # 节点② — 渲染后触发
POST /api/audit/series/{id}/cross-check    # 节点③ — 系列完成后触发
GET  /api/audit/reports/{id}               # 查看审图报告
```

**审图服务实现：**
- `server/app/services/audit_service.py` — 读取 `ai_models.audit_models` 配置，调用对应模型 API
- 所有审图模型通过配置中心可替换（GPT-4o → Claude Opus 4、Gemini → Qwen-VL-Max）

---

## 第 2 层：故事工坊（Story Workshop）

### 2.1 剧本生成 LLM 链

三层 LLM 链，每层使用的模型从 `ai_models.script_llm` 读取：

```
第 1 层 — 系列大纲
  模型: ai_models.script_llm.model (默认 deepseek-chat)
  输入: logline + genre + tone + characters
  输出: N 集大纲

第 2 层 — 逐集剧本
  模型: ai_models.script_llm.model
  输入: 大纲 + 角色档案 + 场景档案
  输出: 完整剧本 (角色标注 + 场景标注 + 情绪标注)

第 3 层 — 分镜拆分
  模型: ai_models.storyboard_llm.model (可与 script_llm 不同)
  输入: 逐集剧本
  输出: StoryboardFrame[]
```

### 2.2 系列 & 剧集管理

数据库和 UI 同上一版 spec。

---

## 第 3 层：导演工坊（Director Workshop）

### 3.1 分镜设计

```python
class DirectorFrame:
    index: int
    narration: str
    character_ids: list[str]
    scene_id: str
    shot_type: str           # close_up/medium/wide/tracking/aerial
    camera_angle: str        # eye_level/low_angle/high_angle/dutch
    camera_movement: str     # static/pan_left/zoom_in/dolly
    composition: str         # rule_of_thirds/center/leading_lines
    target_duration: float
    color_grade: str         # warm/cool/cinematic/natural
    lighting_mood: str       # bright/moody/dramatic/soft
```

### 3.2 模型路由器

不同镜头类型自动路由到 `ai_models.video_models` 中的最优模型：

| 镜头类型 | 路由规则 |
|----------|----------|
| 人物特写/对话 | → 标记 `strengths: ["人脸"]` 的模型 |
| 广角/建立/高潮 | → 标记 `strengths: ["4K", "电影感"]` 的模型 |
| 动作场景 | → 标记 `strengths: ["多角色", "60s长视频"]` 的模型 |
| 静态文字帧 | → FLUX + HTML（本地） |

> 自动路由规则可由用户在 `/ai-config` 页面自定义。每帧的模型选择可在导演工坊手动覆盖。

---

## 第 4 层：渲染引擎（Render Engine）

### 4.1 多模型渲染

Pixelle-Video `frame_processor._step_generate_media()` 读取 `ai_models.video_models` 中 `enabled: true` 的模型列表，动态路由：

```python
async def _step_generate_media(frame, config):
    model_config = get_model_config(config.media_workflow)  # 从 ai_models 读取

    if model_config.provider == "volcengine":
        return await _seedance_render(frame, config, model_config)
    elif model_config.provider == "kuaishou":
        return await _kling_render(frame, config, model_config)
    elif model_config.provider == "runninghub":
        return await self.core.media(workflow=model_config.workflow, ...)
    elif model_config.provider == "custom":
        return await _custom_endpoint_render(frame, config, model_config)
```

**关键：** 不硬编码模型名，所有模型元数据（endpoint/auth/provider）从 `ai_models.video_models` 读取。

### 4.2 后期包装

转场/片头尾/字幕配置同上一版 spec。

---

## 文件改动清单 (更新)

### Pixelle-Video

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `pixelle_video/services/frame_processor.py` | 多模型动态路由器（读 ai_models 配置）(~150行) |
| `pixelle_video/models/storyboard.py` | DirectorFrame + StoryboardFrame 扩展 (~50行) |
| `pixelle_video/pipelines/standard.py` | 导演参数注入 + 角色多图注入 (~100行) |
| `pixelle_video/pipelines/director.py` | **新文件** 导演流水线 (~200行) |
| `pixelle_video/services/post_production.py` | **新文件** 转场/片头尾/字幕 (~150行) |
| `pixelle_video/services/ai_model_registry.py` | **新文件** 读取 ai_models 配置 + 模型路由 (~100行) |
| `pixelle_video/config.py` | 解析 ai_models + characters 完整配置 (~80行) |
| `config.yaml` | ai_models 完整配置模板 |

### dy_auto 后端

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `server/app/db_models.py` | Character + Scene + Series + Episode + AuditReport 表 (~180行) |
| `server/app/routers/characters.py` | 角色 CRUD + 多角度图上传 (~150行) |
| `server/app/routers/scenes.py` | 场景 CRUD (~100行) |
| `server/app/routers/series.py` | 系列+剧集 CRUD + LLM 剧本 (~250行) |
| `server/app/routers/director.py` | 分镜编排 API (~150行) |
| `server/app/routers/audit.py` | **新文件** 审图 API (~200行) |
| `server/app/routers/ai_config.py` | **新文件** AI 模型配置 CRUD (~150行) |
| `server/app/services/audit_service.py` | **新文件** 审图引擎 (~250行) |
| `server/app/routers/kling.py` | **新文件** Kling 3.0 代理 (~200行) |
| `server/app/main.py` | 注册 audit/kling/ai_config 路由 |

### dy_auto 前端

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `web/src/views/AiConfigPage.vue` | **新页面** AI 模型配置 (~350行) |
| `web/src/views/CharactersPage.vue` | 角色管理 + 审图状态展示 (~350行) |
| `web/src/views/ScenesPage.vue` | 场景管理 + 审图状态 (~250行) |
| `web/src/views/SeriesPage.vue` | 系列管理 + 剧本生成 (~400行) |
| `web/src/views/DirectorPage.vue` | **新页面** 分镜导演时间线 (~500行) |
| `web/src/components/video-studio/AuditReport.vue` | **新组件** 审图报告面板 (~200行) |
| `web/src/components/video-studio/ModelRouter.vue` | **新组件** 模型路由配置 (~150行) |
| `web/src/router/index.js` | 新增 5 个路由 |
| `web/src/constants/navigation.js` | 新增 5 个菜单项 |

**总估算：≈ 4200 行，12-15 天。**

---

## 与 old spec 的关键差异

| 维度 | 旧 spec | 新 spec |
|------|---------|---------|
| AI 模型管理 | 硬编码在代码中 | **全局配置中心**，每环节可自主替换 |
| 审图 | 无 | **三层审查节点** + 审图报告 |
| 视频模型 | 3 个固定选项 | **动态注册**，通过配置新增/禁用 |
| 质量关卡 | 用户目视检查 | **AI 自动审核**，不通过阻止入库/合成 |

## 验证计划

1. 打开 `/ai-config` → 修改 script_llm 为 GPT-4o → 测试连接 → 生成剧本使用新模型
2. 新增自定义 video_models 条目 → 前端下拉框自动出现 → 选择后正常渲染
3. 上传角色多角度图 → 自动触发审图 → 审图报告显示一致性评分
4. 审图拒绝(<70分) → 阻止使用该角色生成视频
5. 生成分镜帧 → 审图节点② → 不通过帧自动重新生成
