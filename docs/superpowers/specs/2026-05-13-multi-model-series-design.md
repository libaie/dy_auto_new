# 多模型分镜视频 + 角色档案 + 系列生成 — 行业最高标准架构

## 背景

Pixelle-Video 已通过透明代理整合到 dy_auto（spec 2026-05-12），Seedance 2.0 端点代理已就绪。

用户的核心业务是**可商业化的多角色连续短剧**，质量优先，不计成本。需要一个从资产准备→剧本创作→分镜导演→多模型渲染→后期包装的完整生产线。

## 总体架构（三层设计）

```
┌──────────────────────────────────────────────────────────────────┐
│                        dy_auto 管理后台                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │ 资产工坊  │ │ 故事工坊  │ │ 导演工坊  │ │ 渲染 & 后期       │    │
│  │ 角色管理  │ │ 系列管理  │ │ 分镜编排  │ │ 批量渲染/监控     │    │
│  │ 场景管理  │ │ 剧本生成  │ │ 镜头设计  │ │ 转场/片头尾/包装  │    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘    │
│       │             │             │                │              │
│  /api/assets   /api/series   /api/director   /api/pixelle-proxy  │
│  /api/seedance-proxy  /api/kling-proxy                            │
└───────┼─────────────┼─────────────┼────────────────┼──────────────┘
        │             │             │                │
  ┌─────▼─────┐ ┌─────▼──────┐ ┌───▼────────┐ ┌────▼──────────────┐
  │ dy_auto   │ │ Pixelle-   │ │ Pixelle-   │ │ Cloud APIs        │
  │ DB        │ │ Video      │ │ Video      │ │                   │
  │           │ │            │ │            │ │ Seedance 2.0      │
  │ characters│ │ LLM 剧本   │ │ Director   │ │ (人脸/动作/60s)    │
  │ scenes    │ │ TTS 配音   │ │ Pipeline   │ │ Kling 3.0         │
  │ series    │ │ FFmpeg     │ │ (新增)     │ │ (4K/AI导演/转场)   │
  │ episodes  │ │            │ │            │ │                   │
  └───────────┘ └────────────┘ └────────────┘ └───────────────────┘
```

---

## 第 1 层：资产工坊（Asset Workshop）

### 1.1 角色管理

**数据库：** `characters` 表
```sql
characters (
  id, name, display_name,
  -- 多角度参考图（Seedance 支持最多 9 张，Kling 最多 4 张）
  avatar_front_url,     -- 正面照
  avatar_profile_url,   -- 侧面照
  avatar_three_quarter_url, -- 3/4 侧面
  avatar_full_body_url, -- 全身照
  -- TTS 绑定
  voice_id,             -- Edge-TTS 语音角色
  voice_speed,          -- 语速 0.5-2.0
  -- 角色描述（注入 LLM prompt 和图像生成 prompt）
  appearance,           -- 外貌描述 "25岁男性，短发，戴黑框眼镜，身高175cm"
  personality,          -- 性格特征 "开朗活泼，说话喜欢挥手"
  outfit,               -- 默认服装 "白色T恤+牛仔裤"
  -- 元数据
  created_at, updated_at
)
```

**管理 UI：** `/characters` 页面
- 角色卡片网格（大头像 + 名称 + 声音预览按钮）
- 创建/编辑：拖拽上传多角度照片，TTS 试听，描述模板
- 角色预览：点击展开所有参考图

### 1.2 场景管理

```sql
scenes (
  id, name, display_name,
  -- 多角度场景参考图
  reference_urls_json,  -- ["front.jpg", "left.jpg", "wide.jpg"]
  -- 场景描述
  description,          -- "城市公园，绿树成荫，中央有喷泉和长椅"
  lighting,             -- "午后自然光，暖色调"
  -- 元数据
  created_at, updated_at
)
```

**管理 UI：** `/scenes` 页面
- 场景卡片（场景缩略图 + 名称 + 关联视频数）
- 创建/编辑：上传多角度场景图，填写光照/氛围描述
- 场景绑定到系列/视频

### 1.3 资产注入机制

角色和场景的参考图在分镜渲染时自动注入到对应模型的 API 调用中：

```
Seedance 2.0:  image_urls = [角色正面, 角色侧面, 场景宽角度]  (最多 9 张)
Kling 3.0:     reference_images = [角色正面, 场景参考]       (最多 4 张)
FLUX img2img:  input_image = 角色正面                          (1 张)
```

---

## 第 2 层：故事工坊（Story Workshop）

### 2.1 系列管理

```sql
series (
  id, title, logline,           -- 一句话梗概
  genre,                        -- 类型：都市/古装/科幻/悬疑...
  tone,                         -- 基调：轻松/严肃/温馨/紧张
  characters_json,              -- 出场角色 [{id, name}]
  scenes_json,                  -- 场景列表 [{id, name}]
  target_duration_per_episode,  -- 每集目标时长（秒）
  status, created_at, updated_at
)

episodes (
  id, series_id, episode_number, title,
  outline,                  -- 本集大纲（LLM 生成）
  script,                   -- 完整剧本（含角色标注和镜头指示）
  scene_characters_json,    -- 本集出场 [{character_id, scene_id}]
  storyboard_json,          -- 分镜表（导演工坊产出）
  media_workflow,           -- 本集画面模型
  tts_workflow,             -- 本集配音方案
  status, result_video_path, duration,
  created_at
)
```

### 2.2 多层剧本生成（LLM 链）

```
第 1 层 — 系列大纲
  输入: logline + genre + tone + 角色列表
  输出: N 集大纲，每集 3-5 句话
  模型: DeepSeek-Chat (已有)

第 2 层 — 逐集剧本
  输入: 系列大纲 + 本集大纲 + 角色档案 + 场景档案
  输出: 完整剧本，含:
    - 角色标注 [角色名] 对话内容
    - 场景标注 [场景:公园] 场景描述
    - 情绪标注 (高兴)(悲伤)(紧张)
    - 动作标注 *走向长椅* *挥手*
  模型: DeepSeek-Chat (已有)

第 3 层 — 分镜拆分
  输入: 逐集剧本
  输出: StoryboardFrame[] — 每个分镜帧独立 prompt
  模型: DeepSeek-Chat (已有)
```

---

## 第 3 层：导演工坊（Director Workshop）

### 3.1 分镜设计

每帧的分镜表新增导演参数：

```python
class DirectorFrame:
    index: int
    narration: str
    character_ids: list[str]       # 出镜角色
    scene_id: str                  # 场景
    
    # 镜头设计
    shot_type: str                 # close_up / medium / wide / tracking / aerial
    camera_angle: str              # eye_level / low_angle / high_angle / dutch
    camera_movement: str           # static / pan_left / pan_right / zoom_in / zoom_out / dolly
    composition: str               # rule_of_thirds / center / leading_lines
    
    # 时长控制
    target_duration: float         # 目标秒数
    
    # 视觉风格
    color_grade: str               # warm / cool / cinematic / natural
    lighting_mood: str             # bright / moody / dramatic / soft
```

### 3.2 模型路由策略

不同镜头类型自动路由到最优模型：

| 镜头类型 | 推荐模型 | 理由 |
|----------|----------|------|
| 人物特写 (close_up) | **Seedance 2.0** | 最佳人脸保真度，90% 可用率 |
| 对话场景 (medium) | **Seedance 2.0** | 多角色一致性 + 9 张参考图 |
| 广角/建立 (wide/establishing) | **Kling 3.0** | 4K 分辨率 + AI 导演自动运镜 |
| 动作/追逐 (action) | **Seedance 2.0** | 最佳动作平滑度 |
| 高潮/结尾 (climax) | **Kling 3.0** | 4K 电影感 + 多语言唇形同步 |
| 转场镜头 (transition) | **Kling 3.0** | AI 导演自动机位编排 |
| 静态文字帧 (static) | FLUX + HTML | 最快、最便宜 |

> 模型路由在分镜设计阶段自动决策，用户可逐帧覆盖。

### 3.3 分镜导演 UI

「导演工坊」页面：
- 分镜表时间线视图（横向滚动）
- 每帧卡片：缩略图占位 + 镜头类型图标 + 角色标签 + 时长
- 点击帧 → 右侧属性面板：镜头类型/机位/运镜/调色 下拉选择
- 拖拽调整帧顺序
- 「预览剧本」按钮 → LLM 实时生成分镜表
- 「提交渲染」→ 批量提交所有帧到渲染队列

---

## 第 4 层：渲染 & 后期（Render & Post）

### 4.1 多模型渲染引擎

Pixelle-Video `frame_processor._step_generate_media()` 扩展为模型路由器：

```python
async def _step_generate_media(frame, config):
    model = config.media_workflow or _auto_route(frame)
    
    if model == "seedance_2.0":
        return await _seedance_render(frame, config)
    elif model == "kling_3.0":
        return await _kling_render(frame, config)
    elif model.startswith("wan"):
        return await self.core.media(workflow=model, ...)  # 现有 ComfyKit
    elif model.startswith("flux"):
        return await self.core.media(workflow=model, ...)
```

### 4.2 Kling 3.0 集成

新增 dy_auto 代理路由 `server/app/routers/kling.py`（类似 seedance.py）：

```
POST /api/kling/generate    → 提交 Kling 视频生成任务
GET  /api/kling/task/{id}   → 查询任务状态
```

Kling API 特有参数：
- `mode`: `std` (标准) / `pro` (专业 4K)
- `camera_control`: AI 导演自动运镜开关
- `lip_sync`: 多语言唇形同步
- `duration`: 5/10/15 秒
- `aspect_ratio`: 16:9 / 9:16 / 1:1

### 4.3 后期包装引擎

**转场：**
```python
# FFmpeg xfade 实现集间过渡
transitions = {
    "hard_cut":    None,
    "dissolve":    "fade,duration=0.5",
    "wipe_left":   "wiperight,duration=0.8",
    "zoom_in":     "zoompan,z='min(zoom+0.0015,1.5)'",
}
```

**片头/片尾模板：**
- 系列级配置：片头动画模板 + 片尾字幕模板
- 渲染：HTML 模板 → Playwright 截图 → FFmpeg 合成

**字幕样式：**
```yaml
subtitle:
  font: "PingFang SC"
  size: "32px"
  color: "#ffffff"
  stroke_color: "#000000"
  stroke_width: "2px"
  position: "bottom"  # bottom / top / center
  animation: "fade_in"  # none / fade_in / typewriter / slide_up
```

---

## 系统配置（Pixelle-Video config.yaml）

```yaml
# 多模型 API Keys
seedance:
  api_key: ""
  provider: "volcengine"     # volcengine / atlas_cloud

kling:
  access_key: ""
  secret_key: ""
  provider: "kuaishou"

# 模型路由规则
model_routing:
  close_up: "seedance_2.0"
  medium: "seedance_2.0"
  wide: "kling_3.0"
  action: "seedance_2.0"
  climax: "kling_3.0"
  transition: "kling_3.0"
  static: "flux"

# 后期
post_production:
  default_transition: "dissolve"
  title_template: "templates/title_default.html"
  credits_template: "templates/credits_default.html"
  subtitle_style:
    font: "PingFang SC"
    size: "32px"
```

---

## 文件改动清单

### Pixelle-Video

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `pixelle_video/services/frame_processor.py` | 多模型路由器 (~120行) | 1天 |
| `pixelle_video/models/storyboard.py` | `DirectorFrame` 模型 + `StoryboardFrame` 扩展 (~50行) | 0.5天 |
| `pixelle_video/pipelines/standard.py` | 导演参数注入 + 多角色支持 (~80行) | 0.5天 |
| `pixelle_video/pipelines/director.py` | **新文件** 导演流水线 (~200行) | 1天 |
| `pixelle_video/services/post_production.py` | **新文件** 转场/片头尾/字幕 (~150行) | 1天 |
| `pixelle_video/config.py` | 解析完整配置 (~60行) | 0.5天 |
| `config.yaml` | 完整配置模板 | - |

### dy_auto 后端

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `server/app/db_models.py` | `Character` + `Scene` + `Series` + `Episode` 表 (~120行) | 0.5天 |
| `server/app/routers/characters.py` | 角色 CRUD + 多角度图上传 (~150行) | 0.5天 |
| `server/app/routers/scenes.py` | 场景 CRUD + 多角度图上传 (~100行) | 0.5天 |
| `server/app/routers/series.py` | 系列+剧集 CRUD + LLM 剧本生成 (~250行) | 1天 |
| `server/app/routers/director.py` | 分镜编排 API (~150行) | 0.5天 |
| `server/app/routers/kling.py` | **新文件** Kling 3.0 代理 (~200行) | 1天 |
| `server/app/main.py` | 注册新路由 | - |

### dy_auto 前端

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `web/src/views/CharactersPage.vue` | 角色管理（多角度上传+声音绑定） (~300行) | 1天 |
| `web/src/views/ScenesPage.vue` | 场景管理 (~200行) | 0.5天 |
| `web/src/views/SeriesPage.vue` | 系列管理 + 剧本生成 (~400行) | 1.5天 |
| `web/src/views/DirectorPage.vue` | **新页面** 分镜导演时间线 (~500行) | 2天 |
| `web/src/components/video-studio/VoiceVisualPanel.vue` | 模型选择器重构为4选项 (~30行) | - |
| `web/src/components/video-studio/ModelRouter.vue` | **新组件** 模型路由配置面板 (~150行) | 0.5天 |
| `web/src/router/index.js` | 新增路由 | - |
| `web/src/constants/navigation.js` | 新增菜单 | - |
| `web/src/api/kling-client.js` | Kling API 客户端 | - |

**总估算：≈ 3000 行，8-10 天工作量。**

---

## 与之前版本的差异

| 维度 | 旧 spec（预算限制） | 新 spec（最高标准） |
|------|---------------------|---------------------|
| 模型 | Seedance 为主，Kling 可选项 | **Seedance + Kling 双引擎**，按镜头类型自动路由 |
| 角色 | 单张参考图 | **多角度参考图**（正面/侧面/全身） |
| 场景 | Phase 2 后续 | **Phase 1 独立管理**，多角度参考图 |
| 剧本 | 手动输入 | **LLM 三层链**自动生成（大纲→剧本→分镜） |
| 导演 | 无 | **完整导演工坊**（镜头/机位/运镜/调色） |
| 后期 | FFmpeg 简单拼接 | **专业后期**（转场/片头尾/字幕样式） |
| 资产 | 手动管理 | **OSS/CDN 自动上传**（Seedance/Kling 需要公网 URL） |

---

## 验证计划

1. 创建角色（多角度图 + TTS 绑定）→ 创建场景 → 创建系列
2. LLM 自动生成大纲 → 逐集剧本 → 分镜表
3. 导演工坊调整分镜 → 提交渲染
4. Seedance 生成人物特写帧 → Kling 生成广角建立帧
5. 后期包装：转场 + 片头尾 → 最终 mp4
6. 验证角色一致性：同角色在不同视频/分镜中长相一致
7. 验证场景一致性：同场景在不同视频中氛围一致
