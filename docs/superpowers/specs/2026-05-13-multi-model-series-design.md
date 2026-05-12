# 多模型分镜视频 + 角色档案 + 系列生成

## 背景

Pixelle-Video 已通过透明代理整合到 dy_auto（spec 2026-05-12），Seedance 2.0 端点的代理也已就绪。

用户的核心业务场景是**多角色连续短剧**：
- 同一主题下多个视频，角色和场景跨视频保持一致
- 选一个 AI 模型（FLUX/Wan2.1/Seedance 2.0/...）指定到分镜视频画面生成
- 后续目标：可商业化的连续短剧（当前先满足基础链路）

## 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│                      dy_auto 管理后台                         │
│  ┌───────────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │ AI 视频工坊     │  │ 角色管理  │  │ 系列管理             │    │
│  │ + 模型选择器    │  │ 头像/声音│  │ 创建系列→视频→角色   │    │
│  └───────┬───────┘  └────┬─────┘  └──────────┬─────────┘    │
│          │               │                    │              │
│     /api/pixelle-proxy   │              /api/series          │
│     /api/seedance        │              /api/characters      │
└──────────┼───────────────┼────────────────────┼──────────────┘
           │               │                    │
     ┌─────▼─────┐   ┌─────▼──────────┐  ┌─────▼──────┐
     │ Pixelle-  │   │ Pixelle-Video  │  │  dy_auto   │
     │ Video     │   │ config.yaml    │  │  DB        │
     │           │   │                │  │            │
     │ LLM 脚本  │   │ characters:    │  │ series     │
     │ TTS 配音  │   │   小明:        │  │ series_    │
     │ Seedance  │   │     avatar:... │  │ videos     │
     │ FFmpeg    │   │     voice:...  │  │            │
     └───────────┘   └────────────────┘  └────────────┘
```

---

## Phase 1: 模型选择 + 角色档案 + 系列管理（当前）

### 1.1 分镜模型选择器

**前端：** VoiceVisualPanel 的「画面/视频生成引擎」下拉框增加以下选项：

| 选项值 | 显示名称 | 适用场景 |
|--------|----------|----------|
| (现有) | FLUX / Wan2.1 / SDXL... | 静态模板、本地 ComfyUI |
| `seedance_2.0` | **Seedance 2.0** — 最佳人脸+多角色一致性 | 多角色对话、需要参考图锚定 |
| `kling_3.0` | Kling 3.0 — 4K 电影感 | 高潮/结尾镜头、需要 AI 导演 |
| `wan_2.7` | Wan 2.7 — 开源自部署 | 预算敏感、无内容限制 |

**后端（Pixelle-Video）：** `frame_processor._step_generate_media()` 增加分支：

```python
if media_workflow == "seedance_2.0":
    video_path = await _seedance_generate_frame(
        prompt=frame.image_prompt,
        duration=frame.duration,
        reference_urls=frame.reference_urls,
        aspect_ratio=f"{config.media_width}:{config.media_height}"
    )
    frame.video_path = video_path
    frame.media_type = "video"
else:
    # 现有 ComfyKit/RunningHub 逻辑不变
    ...
```

Seedance 调用的异步轮询逻辑复用 `dy_auto/server/app/routers/seedance.py` 的已有模式。

**配置：** `Pixelle-Video/config.yaml` 新增：
```yaml
seedance_api_key: ""
kling_access_key: ""
kling_secret_key: ""
```

### 1.2 角色档案

**存储：** dy_auto DB 新增 `characters` 表（避免与 Pixelle-Video config.yaml 分裂）：
```sql
characters (
  id, name, avatar_path, avatar_url,  -- avatar_url 用于 Seedance 公网参考图
  voice_id, description, created_at
)
```

生成时，角色信息通过 API 参数注入到 Pixelle-Video 请求中，而非通过 config.yaml 静态配置。

**角色图片：** 存放在 dy_auto `server/app/data/characters/` 目录，通过 `/api/characters/avatar/{filename}` 端点对外暴露。

> **Seedance 公网 URL 约束：** 火山方舟 Seedance API 的 `image_urls` 参数需要**公网可访问的 HTTP URL**。本地部署时 dy_auto 无公网 IP，参考图无法直接传给 Seedance。
> 
> **解决方案：**
> - **MVP 阶段**：允许用户手动填入公网图片 URL（如上传到图床后粘贴链接），同时支持本地上传（供 FLUX/Wan2.1 本地使用）
> - **后续优化**：集成 OSS/CDN 自动上传，或使用 Seedance 第三方 API（Atlas Cloud 等）看是否支持 base64 图片

**dy_auto 管理 UI：** 新增「角色管理」页面：
- 角色列表（名称+头像卡片）
- 创建/编辑角色：上传头像、选择 TTS 声音（从 Edge-TTS 9 个中文语音中选）、填写描述文本
- 角色绑定到系列/视频

### 1.3 系列管理

**数据库：** dy_auto DB 新增两张表：
```sql
series (id, name, topic, characters_json, status, created_at, updated_at)

series_videos (
  id, series_id, title, script, 
  scene_characters_json,  -- [角色名列表]
  media_workflow,          -- 每个视频可独立选模型
  status, result_video_path, created_at
)
```

**dy_auto 管理 UI：** 「系列管理」页面（独立路由 `/series`）：
- 系列列表
- 创建系列：主题 + 选择参与角色 → 自动生成系列名称
- 系列详情：视频列表 + 每个视频独立配置（标题、脚本、角色分配、模型选择）
- 系列级属性：批量选择所有视频的默认模型
- 批量生成：一键提交系列内所有视频，含并发控制（最大 3 并发）、失败自动重试（最多 2 次）、预估成本展示（基于 Seedance 定价 × 预计时长）

### 1.4 多角色 TTS

**模型改动：** `StoryboardFrame` 增加 `voice_id` 字段：
```python
class StoryboardFrame:
    voice_id: Optional[str] = None  # 帧级 TTS 声音，覆盖全局配置
```

**LLM 改动：** narration 生成 prompt 增加角色标注指令：
```
在 narration 文本中标注角色名，格式：
  [小明] 大家好我是小明
  [小红] 大家好我是小红
```

**frame_processor 改动：**
```python
# _step_generate_audio 读取帧级 voice_id
voice_id = frame.voice_id or config.voice_id
```

### 1.5 角色参考图注入（Seedance 专用）

**standard pipeline 改动：** `plan_visuals` 中，检测到 `media_workflow=seedance_2.0` 时，将帧对应的角色参考图 URL 注入 `frame.reference_urls`：

```python
if media_workflow == "seedance_2.0" and frame.character_ids:
    frame.reference_urls = [
        resolve_character_avatar(cid) 
        for cid in frame.character_ids
    ]
```

### 1.6 文件改动清单

| 项目 | 文件 | 改动说明 |
|------|------|----------|
| **Pixelle-Video** | `pixelle_video/services/frame_processor.py` | `_step_generate_media` 增加 Seedance 分支 (~60行) |
| | `pixelle_video/models/storyboard.py` | `StoryboardFrame` 加 `voice_id`/`reference_urls` (~10行) |
| | `pixelle_video/pipelines/standard.py` | `plan_visuals` 注入角色参考图 (~30行) |
| | `pixelle_video/config.py` | `config_manager` 解析 `seedance_api_key` + `kling_access_key` + `kling_secret_key` (~40行) |
| | `config.yaml` | 模板新增 `seedance_api_key` + `kling_*` + `characters` 段 |
| **dy_auto 后端** | `server/app/db_models.py` | 新表 `Character` + `Series` + `SeriesVideo` (~80行) |
| | `server/app/routers/series.py` | 系列 CRUD API (~150行) |
| | `server/app/routers/characters.py` | 角色 CRUD API + 头像上传 (~100行) |
| | `server/app/routers/seedance.py` | 已有，无需改动 |
| | `server/app/main.py` | 注册新路由 |
| **dy_auto 前端** | `web/src/views/SeriesPage.vue` | 系列管理页 (~250行) |
| | `web/src/views/CharactersPage.vue` | 角色管理页 (~200行) |
| | `web/src/components/video-studio/VoiceVisualPanel.vue` | 模型选择下拉加 Seedance (~10行) |
| | `web/src/components/video-studio/ContentPanel.vue` | 角色绑定多选 (~40行) |
| | `web/src/views/VideoStudio.vue` | 新增系列 Tab (~30行) |
| | `web/src/router/index.js` | 系列/角色路由 |
| | `web/src/constants/navigation.js` | 菜单项 |

**总估算：≈ 1200 行，3-4 天工作量。**

---

## Phase 2: 可商业化连续短剧（后续）

以下需求已确认列入后续方向，当前不动工：

- [ ] **场景资产库** — 场景参考图上传/管理（公园/家/办公室多角度），注入到 media 生成 prompt
- [ ] **分镜导演层** — 镜头类型（特写/中景/全景/跟拍）、机位、运镜方向，生成前写入 prompt template
- [ ] **故事规划器** — 大纲→分集摘要→逐集剧本 多层 LLM 链，关联角色出场表
- [ ] **画面一致性增强** — 评估角色 LoRA 或角色 embedding 方案，跨集角色长相稳定
- [ ] **批量渲染队列** — 30 集并行调度、并发限制、失败重试、成本预估
- [ ] **转场引擎** — 集间过渡效果（硬切/淡入淡出/推拉），FFmpeg xfade 实现
- [ ] **品牌化包装** — 片头/片尾/角标/统一字幕样式模板
- [ ] **Seedance 声画同步模式** — 评估 Seedance 原生配音质量，可行时跳过 TTS 步骤降低复杂度

---

## 约束

- GPU：单卡 RTX 3060 12GB，仅 ComfyUI 串行出图。Seedance 在云端不占 GPU。
- Pixelle-Video 是外部 fork 项目，改动集中在 pipeline 和 frame_processor 两个模块，不碰核心抽象
- dy_auto 前端保持 Vue 3 + Tailwind CSS + glass-card 风格

## 验证

1. 选择 Seedance 2.0 → 输入脚本含两个角色 → 生成视频，两角色 TTS 声音不同
2. 创建系列"小明冒险" → 添加 3 个视频 → 批量生成 → 产出 3 个 mp4
3. 上传角色头像 → 绑定 Seedance 生成 → 验证画面是否维持角色长相
4. 切换到 FLUX → 验证原有 RunningHub 流程不受影响
