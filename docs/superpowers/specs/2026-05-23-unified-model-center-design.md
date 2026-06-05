# AI 视频模块 — 统一模型中心 & Pipeline 重构设计

## 背景

dy_auto 和 Pixelle-Video 两套系统处于"半截子集成"状态：

- **dy_auto**：6 层 pipeline 每层自己调 LLM 直连（简陋 prompt）或 fallback 到 Pixelle-Video，prompt 质量差、架构冗余
- **Pixelle-Video**：专业的视频生产引擎（7 个 prompt 模板、30 个 HTML 分镜模板、ComfyUI/FFmpeg），但 `ai_models` 只有 `video_models` 一圈闭环
- **环境层面**：端口冲突（8000 vs 8000）、URL 指向错误、env var 未注入（已于 2026-05-23 修复）

## 设计目标

1. dy_auto 的 `AIModel` 表作为**唯一模型配置数据源**，通过 config bridge 下发 Pixelle-Video
2. dy_auto pipeline 从"6 层自己什么都干"瘦身为"分镜提交 + 轮询验收"
3. Pixelle-Video 新增 `storyboard` 模式，接受预计算分镜直接渲染
4. Pixelle-Video 的 `ai_models` 各场景接入 `AIModelRegistry`

## 架构全景

```
┌─ dy_auto（编排层）────────────────────────────┐
│                                                │
│  Series 管理 → 角色/场景/风格锁定              │
│  Director Workshop → AI 自动分镜               │
│  AIModel 表 → 模型配置管理 (唯一信源)          │
│  Video Library → 存储/检索/下载                │
│                                                │
│  pipeline (简化后):                             │
│    director_plan frames[]                      │
│         │                                      │
│         ▼                                      │
│    Pixelle-Video /api/video/generate/async     │
│    (storyboard 模式)                            │
│         │                                      │
│         ▼                                      │
│    轮询 → 存 GeneratedVideo                     │
│                                                │
├────────────────────────────────────────────────┤
│  Config Bridge: PUT /api/pixelle/config        │
│    读 AIModel 表 → 序列化 ai_models →          │
│    写 config.yaml → POST /api/admin/reload     │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌─ Pixelle-Video（执行层）───────────────────────┐
│                                                │
│  StandardPipeline (新增 storyboard 模式):       │
│    frames[] → TTS → 素材生成 → HTML渲染        │
│    → FFmpeg合成 → MP4                          │
│                                                │
│  AIModelRegistry:                               │
│    get_model_for_scene("script_generation")     │
│    get_model_for_scene("image_generation")      │
│    get_model_for_scene("video_rendering")  ✅   │
│    get_model_for_scene("tts_synthesis")         │
│                                                │
│  不动: prompts/*.py / templates/ / workflows/  │
│        ComfyUI / FFmpeg                         │
└────────────────────────────────────────────────┘
```

## 分界线

| 层 | 归谁 | 内容 |
|---|---|---|
| **内容策划** | dy_auto | Series/Episode/Character/Scene 管理、风格锁定、Agency Team 质量把关、AI 自动分镜 |
| **模型配置** | dy_auto | AIModel 表为唯一信源，Web UI 管理，加密存储 |
| **视频生产** | Pixelle-Video | 脚本→TTS→素材→模板渲染→合成，全链路 |
| **Prompt 模板** | Pixelle-Video | 7 个 `prompts/*.py`（脚本/图片提示词/视频提示词/标题/风格转换） |
| **分镜模板** | Pixelle-Video | 30 个 HTML 模板，Playwright 渲染 |
| **视频存储** | dy_auto | GeneratedVideo 表 + 文件管理 |

## dy_auto 改动

### 1. Pipeline 瘦身 (`server/app/routers/pipeline.py`)

**删**：
- `_llm_chat_completion()` — 不再自己调 LLM
- `_layer_image_generate` 中 OpenAI/Seedance 直调分支
- `_layer_narration` / `_layer_title` / `_layer_image_prompt` 中 LLM 直调分支
- `_layer_postproduction` 单独的 Pixelle-Video 调用

**改**：整条 pipeline 简化为 thin layer：
1. 接收 `director_plan`（frames 数组 + config）
2. 组装为 Pixelle-Video storyboard 格式（见下方数据协议）
3. 调 `POST /api/video/generate/async`
4. 轮询 `GET /api/tasks/{task_id}` 直到 completed
5. 结果存入 `GeneratedVideo` 表

### 2. Config Bridge 增强 (`server/app/routers/pixelle.py`)

`PUT /api/pixelle/config` 触发时：
1. 读取 `AIModel` 表所有 enabled 模型
2. 按 scene_key 分组序列化为 Pixelle-Video `ai_models` 格式
3. 写 config.yaml + `POST /api/admin/reload`

### 3. 移除废弃代码

| 文件 | 说明 |
|---|---|
| `server/app/routers/seedance.py` | 已标记 deprecated，彻底移除 |
| `pipeline.py` 中 Seedance 直连逻辑 | Pixelle-Video 接管 |

### 4. 不改

- Series/Episode/Character/Scene CRUD
- Director Workshop (`/api/director/auto-plan`)
- AI Model Center Web UI (`AIConfigPage.vue`)
- Video Library (`/api/videos`)
- 账号/养号/评论/私信等其他模块

## Pixelle-Video 改动

### 1. StandardPipeline 新增 storyboard 模式

`StandardPipeline` 增加 `mode="storyboard"`，跳过脚本/标题/提示词生成步骤：

```
mode=generate (现有):          mode=storyboard (新增):
─────────────────────          ─────────────────────
generate_content     →         跳过 (frames 已带 narration)
determine_title      →         跳过 (使用入参 title)
plan_visuals         →         跳过 (frames 已带 image_prompt)
initialize_storyboard →        从入参 frames[] 直接构建 Storyboard
produce_assets       →         ✅ 执行 (TTS + 素材 + 渲染)
post_production      →         ✅ 执行
finalize             →         ✅ 执行
```

### 2. AIModelRegistry 通用化 (`services/ai_model_registry.py`)

从当前只支持 `get_video_model()` 增强为：

```python
def get_model_for_scene(self, scene_key: str, explicit_model_id: str = None) -> dict:
    """按场景取模型配置。script_generation / image_generation /
       video_rendering / tts_synthesis / quality_audit"""
```

### 3. 各 Service 接入 Registry

| Service | 改动 |
|---|---|
| `LLMService` | `_get_config_value()` → `ai_model_registry.get_model_for_scene("script_generation")` |
| `MediaService` (image) | `__init__` → `ai_model_registry.get_model_for_scene("image_generation")` |
| `MediaService` (video) | 已接入，无需改 |
| `TTSService` | 从读 `config.comfyui.tts` → `ai_model_registry.get_model_for_scene("tts_synthesis")` |

### 4. 不改

- `prompts/*.py` — 7 个 prompt 模板
- `templates/` — 30 个 HTML 分镜模板
- `workflows/` — ComfyUI 工作流
- 配置热重载机制（已正常工作）
- Config loader 的 `${VAR}` 解析（已实现）

## 数据协议：dy_auto → Pixelle-Video

### `/api/video/generate/async` 请求体

```json
{
  "mode": "storyboard",
  "title": "第3集：如何打破信息茧房",

  "frames": [
    {
      "index": 0,
      "narration": "你有没有发现，刷到的视频越来越像你...",
      "image_prompt": "A person trapped inside a transparent bubble...",
      "duration": 8.5,
      "audio_mode": "tts",
      "voice_id": "zh-CN-YunjianNeural",
      "reference_urls": [
        "https://oss.example.com/characters/alice_front.png"
      ]
    }
  ],

  "config": {
    "frame_template": "1080x1920/image_elegant.html",
    "tts_inference_mode": "local",
    "tts_speed": 1.2,
    "media_workflow": "runninghub/video_wan2.1_fusionx.json",
    "media_width": 1024,
    "media_height": 1024,
    "bgm_path": "bgm/default.mp3",
    "bgm_volume": 0.2
  }
}
```

### 字段映射

| dy_auto director_plan frame | Pixelle-Video StoryboardFrame |
|---|---|
| `narration` | `.narration` |
| `image_prompt` | `.image_prompt` |
| `duration` | `.duration` |
| `audio_mode` | `.audio_mode` |
| `voice_id` | `.voice_id` |
| `reference_urls` | `.reference_urls` |
| `camera_direction` | 拼入 `image_prompt` 前缀 |

## ai_models 配置格式（Config Bridge 下发）

```yaml
ai_models:
  scenes:
    script_generation:
      provider: deepseek
      model: deepseek-chat
      api_key: "sk-xxx"
      base_url: https://api.deepseek.com/v1
      config:
        temperature: 0.7
        max_tokens: 4096

    image_generation:
      provider: comfyui
      comfyui_url: http://127.0.0.1:8188
      default_workflow: runninghub/image_flux.json
      config:
        prompt_prefix: ""

    video_rendering:
      provider: volcengine
      model: doubao-seedance-2-0-260128
      endpoint: https://ark.cn-beijing.volces.com/api/v3
      api_key: "xxx"
      config:
        aspect_ratio: "9:16"

    tts_synthesis:
      provider: edge_tts
      voice: zh-CN-YunjianNeural
      speed: 1.2
```

## 已修复的环境问题（2026-05-23）

| 问题 | 修复 |
|---|---|
| Pixelle-Video 端口 8000 与 dy_auto 冲突 | `api/app.py:166` 默认端口改为 8500 |
| dy_auto pixelle_client 默认端口错误 | 已是 8500，无需改 |
| config.yaml 中 `${VAR}` 未解析 | `config/loader.py` 增加 `_resolve_env_vars()` |

## 风险点

1. **Pixelle-Video 的 storyboard 模式需要新增** — 这是最大的改动块，涉及 StandardPipeline 流程分支
2. **config bridge 的序列化逻辑** — 需要保证 AIModel 表字段到 Pixelle-Video `ai_models` 格式的映射正确
3. **向后兼容** — Pixelle-Video 的 `mode="generate"` 保持不变，dy_auto 其他模块（评论/私信）不涉及

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 2 | issues_open | SELECTIVE EXPANSION, quality baseline added as P1 |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | issues_open | 5 issues, 3 critical gaps, full test plan recommended |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | skipped | No UI scope — backend/integration only |

- **UNRESOLVED:** 0 — all decisions made
- **VERDICT:** CEO + ENG CLEARED with remediation tasks in plan. Ready to implement after pre-implementation design for critical gaps.

### Implementation Tasks (aggregated across reviews)

- [ ] **P1 (human: ~2 days / CC: ~1 day)** — Pixelle-Video StandardPipeline — Add storyboard mode with `_prefill_from_frames()` context builder. Files: `pixelle_video/pipelines/standard.py`, `pixelle_video/models/storyboard.py`
- [ ] **P1 (human: ~1 day / CC: ~3 hrs)** — dy_auto pipeline.py — Thin-layer rewrite: director_plan → PV storyboard API → poll → GeneratedVideo. Files: `server/app/routers/pipeline.py`
- [ ] **P1 (human: ~1 day / CC: ~2 hrs)** — Config bridge + AIModelRegistry — AIModel serialization + universal `get_model_for_scene()`. Files: `server/app/routers/pixelle.py`, `pixelle_video/services/ai_model_registry.py`, `pixelle_video/services/llm_service.py`, `pixelle_video/services/tts_service.py`
- [ ] **P1 (human: ~0.5 days / CC: ~1 hr)** — Pixelle-Video API auth — X-API-Key on write endpoints. Files: `api/app.py`, `server/app/config.py`
- [ ] **P1 (human: ~0.5 days / CC: ~1 hr)** — Integration contract test — JSON Schema for storyboard + both CI pipelines. Files: `tests/contract/storyboard-schema.json`
- [ ] **P1 (human: ~0.5 days / CC: ~30 min)** — SSRF guard — URL allowlist for reference_urls. Files: `pixelle_video/services/frame_processor.py`
- [ ] **P1 (human: ~0.5 days / CC: ~1 hr)** — Quality baseline — Before/after comparison on 3 topics before refactoring. Files: `scripts/quality-baseline.py`
- [ ] **P2 (human: ~1 day / CC: ~2 hrs)** — Error recovery — Retry+circuit-breaker + zombie task cleanup on both sides. Files: `server/app/routers/pipeline.py`, `pixelle_video/services/frame_processor.py`
- [ ] **P2 (human: ~4 hrs / CC: ~1 hr)** — Frame parallelism — Extend Semaphore parallel path to selfhost workflows. Files: `pixelle_video/pipelines/standard.py`
- [ ] **P3 (human: ~3 days / CC: ~4 hrs)** — Full test suite — 20 test specs across all gaps identified in eng review. Files: `tests/`
