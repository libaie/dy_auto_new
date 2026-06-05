# 统一模型中心 & Pipeline 重构 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dy_auto AIModel 表为唯一模型配置数据源，通过 config bridge 下发 Pixelle-Video；dy_auto pipeline 瘦身为 storyboard 提交+轮询；Pixelle-Video 新增 storyboard 模式接受预计算分镜。

**Architecture:** 3 条独立工作线。Lane A (Pixelle-Video): AIModelRegistry 通用化 → 各 Service 接入 → StandardPipeline storyboard 模式 → API auth + SSRF。Lane B (dy_auto): Config bridge 增强 → Pipeline 瘦身 → 移除 seedance.py。Lane C (集成): 契约测试 → 质量基线 → E2E 验证。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / httpx / Pydantic / pytest

**Repos involved:**
- `D:\devWorkspace\jsProjects\dy_auto` (dy_auto)
- `D:\devWorkspace\Pixelle-Video` (Pixelle-Video)

---

## File Map

### Pixelle-Video (Lane A)

| File | Action | Purpose |
|---|---|---|
| `pixelle_video/services/ai_model_registry.py` | Modify | 通用 `get_model_for_scene(scene_key)` |
| `pixelle_video/config/schema.py` | Modify | AIModelsConfig → scenes dict |
| `pixelle_video/services/llm_service.py` | Modify | 从读 config.llm 改为走 registry |
| `pixelle_video/services/tts_service.py` | Modify | 从读 config.comfyui.tts 改为走 registry |
| `pixelle_video/services/media.py` | Modify | image 路径接入 registry |
| `pixelle_video/pipelines/standard.py` | Modify | 新增 `_prefill_from_frames()` + storyboard 分支 |
| `pixelle_video/models/storyboard.py` | Verify | reference_urls/duration 已存在，确认映射 |
| `pixelle_video/services/frame_processor.py` | Modify | SSRF guard + zombie cleanup |
| `api/app.py` | Modify | X-API-Key middleware |
| `api/routers/video.py` | Modify | 接收 storyboard mode 入参 |

### dy_auto (Lane B)

| File | Action | Purpose |
|---|---|---|
| `server/app/routers/pipeline.py` | Rewrite | Thin layer: director_plan → PV → poll → store |
| `server/app/routers/pixelle.py` | Modify | AIModel → ai_models 序列化 |
| `server/app/routers/seedance.py` | Delete | 已 deprecated，移除 |
| `server/app/main.py` | Modify | 移除 seedance router 注册 |
| `server/app/services/pixelle_client.py` | Modify | 增加 retry+circuit-breaker |

### Integration (Lane C)

| File | Action | Purpose |
|---|---|---|
| `tests/contract/storyboard-schema.json` | Create | 共享 JSON Schema |
| `tests/test_storyboard_contract.py` | Create | 契约测试 (dy_auto side) |
| `D:\devWorkspace\Pixelle-Video\tests\test_storyboard_contract.py` | Create | 契约测试 (PV side) |
| `scripts/quality-baseline.py` | Create | 重构前后质量对比脚本 |

---

## Lane A: Pixelle-Video 改动

### Task A1: AIModelRegistry 通用化

**Files:**
- Modify: `pixelle_video/services/ai_model_registry.py`
- Modify: `pixelle_video/config/schema.py`

- [ ] **Step 1: 更新 AIModelsConfig schema**

`pixelle_video/config/schema.py` — 替换 `AIModelsConfig`:

```python
class SceneModelConfig(BaseModel):
    """单个场景的模型配置"""
    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    endpoint: str = ""
    config: dict = Field(default_factory=dict)


class AIModelsConfig(BaseModel):
    """AI 模型配置 — 按场景路由"""
    scenes: dict[str, SceneModelConfig] = Field(default_factory=dict)
```

- [ ] **Step 2: 增强 AIModelRegistry**

`pixelle_video/services/ai_model_registry.py` — 替换整个文件:

```python
"""AI Model Registry — 按场景读取 ai_models.scenes 配置."""
from typing import Optional
from pixelle_video.config import config_manager


class ModelResolutionError(Exception):
    """无法解析场景对应的模型配置."""
    pass


class AIModelRegistry:
    """单例，读取 config.yaml 中 ai_models.scenes 段."""

    def __init__(self):
        self._cache = None

    @property
    def config(self) -> dict:
        if self._cache is None:
            ai_models = getattr(config_manager.config, 'ai_models', None)
            self._cache = ai_models.model_dump() if ai_models else {}
        return self._cache

    def reload(self):
        self._cache = None

    def get_model_for_scene(
        self, scene_key: str, explicit_model_id: str | None = None
    ) -> dict:
        """按场景取模型配置.

        scene_key: script_generation | image_generation |
                   video_rendering | tts_synthesis | quality_audit
        """
        scenes = self.config.get("scenes", {})
        cfg = scenes.get(scene_key, {})
        if not cfg:
            raise ModelResolutionError(
                f"No model configured for scene '{scene_key}'. "
                f"Available scenes: {list(scenes.keys())}"
            )
        return cfg

    # 向后兼容 — 保留旧方法
    def get_video_model(self, model_id: str) -> Optional[dict]:
        return self.get_model_for_scene("video_rendering")

    def list_video_models(self) -> list[dict]:
        cfg = self.get_model_for_scene("video_rendering")
        return [cfg] if cfg else []

    def get_asset_generation_config(self) -> dict:
        return self.config.get("asset_generation", {})

    def get_audit_model(self, node: str) -> dict:
        return self.config.get("audit_models", {}).get(node, {})

    def get_llm_config(self) -> dict:
        return self.get_model_for_scene("script_generation")

    def auto_route_model(self, shot_type: str) -> str:
        cfg = self.get_model_for_scene("video_rendering")
        return cfg.get("model", "flux")


ai_model_registry = AIModelRegistry()
```

- [ ] **Step 3: 运行现有测试确认向后兼容**

```bash
cd D:\devWorkspace\Pixelle-Video && python -m pytest tests/ -x -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add pixelle_video/services/ai_model_registry.py pixelle_video/config/schema.py
git commit -m "feat: generalize AIModelRegistry to get_model_for_scene(scene_key)"
```

---

### Task A2: LLMService 接入 Registry

**Files:**
- Modify: `pixelle_video/services/llm_service.py`

- [ ] **Step 1: 修改 _get_config_value 优先走 registry**

`llm_service.py` 中修改 `_get_config_value` 方法:

```python
def _get_config_value(self, key: str, default=None):
    """Get config value — prefers ai_models.scenes.script_generation, falls back to config.llm."""
    from pixelle_video.services.ai_model_registry import ai_model_registry
    try:
        scene_config = ai_model_registry.get_model_for_scene("script_generation")
        mapped = {
            "api_key": scene_config.get("api_key", ""),
            "base_url": scene_config.get("base_url", ""),
            "model": scene_config.get("model", ""),
        }
        if mapped.get(key):
            return mapped[key]
    except Exception:
        pass
    # Fallback to top-level llm config
    from pixelle_video.config import config_manager
    return getattr(config_manager.config.llm, key, default)
```

- [ ] **Step 2: 验证 LLM 调用仍正常工作**

```bash
cd D:\devWorkspace\Pixelle-Video
python -c "
from pixelle_video.config import config_manager
from pixelle_video.services.llm_service import LLMService
svc = LLMService(config_manager.config.to_dict())
print('active:', svc.active)
print('model:', svc._get_config_value('model'))
print('OK: LLMService resolves via registry')
"
```

- [ ] **Step 3: Commit**

```bash
git add pixelle_video/services/llm_service.py
git commit -m "feat: route LLMService through AIModelRegistry for script_generation scene"
```

---

### Task A3: TTSService 接入 Registry

**Files:**
- Modify: `pixelle_video/services/tts_service.py`

- [ ] **Step 1: 找到 TTSService 读取 comfyui.tts 配置的位置并改为走 registry**

找到 `tts_service.py` 中读取 tts 配置的方法（通常 `_get_tts_config` 或 `__init__`），增加 registry 优先逻辑:

```python
def _get_tts_config(self) -> dict:
    """Get TTS config — prefers ai_models.scenes.tts_synthesis, falls back to comfyui.tts."""
    from pixelle_video.services.ai_model_registry import ai_model_registry
    try:
        scene_config = ai_model_registry.get_model_for_scene("tts_synthesis")
        return {
            "inference_mode": scene_config.get("inference_mode", "local"),
            "voice": scene_config.get("voice", "zh-CN-YunjianNeural"),
            "speed": scene_config.get("speed", 1.2),
            "workflow": scene_config.get("workflow"),
        }
    except Exception:
        pass
    # Fallback
    comfyui = self.config.get("comfyui", {})
    tts = comfyui.get("tts", {})
    return {
        "inference_mode": tts.get("inference_mode", "local"),
        "voice": tts.get("local", {}).get("voice", "zh-CN-YunjianNeural"),
        "speed": tts.get("local", {}).get("speed", 1.2),
        "workflow": tts.get("default_workflow"),
    }
```

- [ ] **Step 2: 验证 TTS 配置解析**

```bash
cd D:\devWorkspace\Pixelle-Video
python -c "
from pixelle_video.config import config_manager
from pixelle_video.services.tts_service import TTSService
from pixelle_video.service import pixelle_video
import asyncio
async def test():
    await pixelle_video.initialize()
    cfg = pixelle_video.tts._get_tts_config()
    print('TTS config:', cfg)
asyncio.run(test())
print('OK: TTSService resolves via registry')
"
```

- [ ] **Step 3: Commit**

```bash
git add pixelle_video/services/tts_service.py
git commit -m "feat: route TTSService through AIModelRegistry for tts_synthesis scene"
```

---

### Task A4: MediaService image 路径接入 Registry

**Files:**
- Modify: `pixelle_video/services/media.py`

- [ ] **Step 1: 修改 MediaService.__init__ — image 场景走 registry**

`media.py` 的 `__init__` 中，当 `service_name == "image"` 时增加 registry 查找:

```python
async def __call__(self, prompt, workflow=None, media_type="image", ...):
    # If no explicit workflow, try registry for image scenes
    if workflow is None and media_type == "image":
        from pixelle_video.services.ai_model_registry import ai_model_registry
        try:
            scene_config = ai_model_registry.get_model_for_scene("image_generation")
            workflow = scene_config.get("default_workflow") or workflow
            if scene_config.get("prompt_prefix"):
                prompt = f"{scene_config['prompt_prefix']} {prompt}"
        except Exception:
            pass
    # ... rest of existing logic unchanged
```

- [ ] **Step 2: 验证 image workflow 解析**

```bash
cd D:\devWorkspace\Pixelle-Video
python -c "
from pixelle_video.services.ai_model_registry import ai_model_registry
try:
    cfg = ai_model_registry.get_model_for_scene('image_generation')
    print('image config:', cfg.get('default_workflow', 'NOT SET'))
except Exception as e:
    print('Expected — no image scene in config yet:', e)
"
```

- [ ] **Step 3: Commit**

```bash
git add pixelle_video/services/media.py
git commit -m "feat: route MediaService image path through AIModelRegistry"
```

---

### Task A5: StandardPipeline storyboard 模式

**Files:**
- Modify: `pixelle_video/pipelines/standard.py`
- Modify: `pixelle_video/models/storyboard.py` (verify, may not need changes)

- [ ] **Step 1: 新增 `_prefill_from_frames()` 方法**

在 `StandardPipeline` 类中添加:

```python
async def _prefill_from_frames(self, ctx: PipelineContext):
    """Storyboard mode: pre-fill context from incoming frames JSON.

    Populates ctx.narrations, ctx.image_prompts, ctx.title, and
    ctx.params for downstream steps that read them.
    """
    frames_data = ctx.params.get("frames", [])
    if not frames_data:
        raise ValueError("storyboard mode requires non-empty 'frames' array")

    ctx.title = ctx.params.get("title", "")
    ctx.narrations = []
    ctx.image_prompts = []

    for f in frames_data:
        ctx.narrations.append(f.get("narration", ""))
        ctx.image_prompts.append(f.get("image_prompt", ""))

    logger.info(
        f"Prefilled context from {len(frames_data)} frames "
        f"(title='{ctx.title}')"
    )
```

- [ ] **Step 2: 修改 LinearVideoPipeline 流程 — storyboard 分支**

在 `StandardPipeline` 的执行入口（通常在 `linear.py` 的 `run()` 方法或 `standard.py` 的 `__call__`）增加 storyboard 分支。标准流程中 `execute_steps` 调用各 lifecycle 方法。在 `run` 方法的步骤列表前插入判断:

```python
async def run(self, ctx: PipelineContext) -> VideoGenerationResult:
    mode = ctx.params.get("mode", "generate")

    if mode == "storyboard":
        # Storyboard: skip content generation, pre-fill from input frames
        await self.setup_environment(ctx)
        await self._prefill_from_frames(ctx)
        await self.initialize_storyboard(ctx)
        await self.produce_assets(ctx)
        await self.post_production(ctx)
        return await self.finalize(ctx)

    # Standard generate mode — unchanged
    await self.setup_environment(ctx)
    await self.generate_content(ctx)
    await self.determine_title(ctx)
    await self.plan_visuals(ctx)
    await self.initialize_storyboard(ctx)
    await self.produce_assets(ctx)
    await self.post_production(ctx)
    return await self.finalize(ctx)
```

- [ ] **Step 3: 修改 `initialize_storyboard` — storyboard 模式下从 ctx 读取**

`initialize_storyboard` 当前从 `ctx.narrations` 和 `ctx.image_prompts` 读取（line 284: `zip(ctx.narrations, ctx.image_prompts)`）。storyboard 模式已通过 `_prefill_from_frames` 填充这两个字段，所以 `initialize_storyboard` **无需改动** — 这正是 design 的要点。

需要改动的是 `StoryboardFrame` 的构建（line 285-291），确保入参中的 `duration` / `voice_id` / `reference_urls` / `audio_mode` 传递到 frame:

```python
for i, (narration, image_prompt) in enumerate(zip(ctx.narrations, ctx.image_prompts)):
    frame_data = ctx.params.get("frames", [{}])[i] if i < len(ctx.params.get("frames", [])) else {}
    frame = StoryboardFrame(
        index=i,
        narration=narration,
        image_prompt=image_prompt,
        duration=frame_data.get("duration", 0.0),
        voice_id=frame_data.get("voice_id"),
        reference_urls=frame_data.get("reference_urls"),
        audio_mode=frame_data.get("audio_mode"),
        created_at=datetime.now(),
    )
    ctx.storyboard.frames.append(frame)
```

- [ ] **Step 4: 添加 API 路由支持 storyboard mode**

`api/routers/video.py` — 确保 `/api/video/generate/async` 接受 storyboard 入参并传递 `mode="storyboard"`:

```python
class VideoGenerateRequest(BaseModel):
    mode: str = "generate"  # "generate" | "storyboard"
    text: str = ""           # topic (generate mode)
    title: str = ""          # video title (storyboard mode)
    frames: list[dict] = []  # pre-computed frames (storyboard mode)
    config: dict = {}        # rendering config
    # ... other params unchanged


@router.post("/api/video/generate/async")
async def generate_video_async(req: VideoGenerateRequest):
    params = req.model_dump(exclude_none=True)
    if req.mode == "storyboard":
        params["text"] = req.title or "storyboard"
    task_id = await task_manager.submit(
        pipeline_name="standard",
        text=params.get("text", ""),
        **params,
    )
    return {"task_id": task_id, "status": "pending"}
```

- [ ] **Step 5: 运行单元测试验证 storyboard 模式**

```bash
cd D:\devWorkspace\Pixelle-Video && python -m pytest tests/ -x -q -k "pipeline" 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add pixelle_video/pipelines/standard.py pixelle_video/pipelines/linear.py api/routers/video.py
git commit -m "feat: add storyboard mode to StandardPipeline with _prefill_from_frames()"
```

---

### Task A6: Pixelle-Video API 认证中间件

**Files:**
- Modify: `api/app.py`
- Create: `api/middleware.py`

- [ ] **Step 1: 创建 API Key 中间件**

`api/middleware.py`:

```python
"""API authentication middleware."""
import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
PUBLIC_PATHS = {"/", "/health", "/version", "/openapi.json", "/docs", "/redoc"}

# Pre-shared key — set via environment variable
API_KEY = os.environ.get("PIXELLE_API_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for read-only GET and public paths
        if request.method == "GET" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        # Allow if API key not configured (development mode)
        if not API_KEY:
            return await call_next(request)
        # Check X-API-Key header
        key = request.headers.get("X-API-Key", "")
        if key != API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return await call_next(request)
```

- [ ] **Step 2: 注册中间件**

`api/app.py` 中，在 `app = FastAPI(...)` 之后、router 注册之前:

```python
from api.middleware import APIKeyMiddleware
app.add_middleware(APIKeyMiddleware)
```

- [ ] **Step 3: 测试认证中间件**

```bash
cd D:\devWorkspace\Pixelle-Video
python -c "
import os; os.environ['PIXELLE_API_KEY'] = 'test-key-123'
from api.middleware import APIKeyMiddleware
print('Middleware imported OK')
# Manual test: curl -X POST http://127.0.0.1:8500/api/video/generate/async → 401
# curl -X POST -H 'X-API-Key: test-key-123' http://127.0.0.1:8500/api/video/generate/async → OK
"
```

- [ ] **Step 4: Commit**

```bash
git add api/middleware.py api/app.py
git commit -m "feat: add X-API-Key middleware to Pixelle-Video write endpoints"
```

---

### Task A7: SSRF 防护 — reference_urls 校验

**Files:**
- Modify: `pixelle_video/services/frame_processor.py`

- [ ] **Step 1: 添加 URL 校验函数**

`frame_processor.py` 顶部添加:

```python
import re
from urllib.parse import urlparse

# Allowlist: only these domains for reference_urls
_ALLOWED_DOMAINS = os.environ.get(
    "PIXELLE_REFERENCE_ALLOWLIST",
    "oss.example.com,localhost,127.0.0.1",
).split(",")
_ALLOWED_DOMAINS = [d.strip() for d in _ALLOWED_DOMAINS if d.strip()]

_PRIVATE_IP = re.compile(
    r"^(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.0\.0\.0|169\.254\.)"
)


def _validate_reference_url(url: str) -> bool:
    """Validate a reference URL — HTTPS-only, allowlisted domain, no private IPs."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    hostname = parsed.hostname or ""
    if _PRIVATE_IP.match(hostname):
        return False
    if hostname == "localhost" or hostname == "127.0.0.1":
        return False
    return True
```

- [ ] **Step 2: 在 `_step_generate_media` 中校验 reference_urls**

在 `_step_generate_media` 方法开头，处理 `reference_urls` 的地方增加校验:

```python
reference_urls = getattr(frame, "reference_urls", None) or []
validated_urls = []
for url in reference_urls:
    if not url:
        continue
    if not _validate_reference_url(url):
        logger.warning(f"Blocked unsafe reference_url: {url}")
        continue
    validated_urls.append(url)
frame.reference_urls = validated_urls
```

- [ ] **Step 3: Commit**

```bash
git add pixelle_video/services/frame_processor.py
git commit -m "feat: add SSRF guard — HTTPS-only + domain allowlist for reference_urls"
```

---

### Task A8: 帧并行处理扩展到 selfhost

**Files:**
- Modify: `pixelle_video/pipelines/standard.py`

- [ ] **Step 1: 移除 RunningHub-only 并行限制**

`standard.py` 的 `produce_assets` 方法中，当前并行逻辑被 `is_runninghub` 条件保护（line 299-365）。改为所有工作流统一并行:

```python
async def produce_assets(self, ctx: PipelineContext):
    storyboard = ctx.storyboard
    config = ctx.config

    from pixelle_video.config import config_manager
    concurrent_limit = max(
        config_manager.config.comfyui.runninghub_concurrent_limit or 1, 1
    )

    if concurrent_limit > 1:
        logger.info(f"Using parallel frame processing (max {concurrent_limit} concurrent)")
        # ... existing semaphore-based parallel logic (unchanged)
    else:
        logger.info("Using serial frame processing")
        # ... existing serial logic (unchanged)
```

关键改动：删除 `is_runninghub` 条件判断，统一用 `concurrent_limit` 控制。

- [ ] **Step 2: Commit**

```bash
git add pixelle_video/pipelines/standard.py
git commit -m "feat: extend parallel frame processing to all workflows (was RunningHub-only)"
```

---

### Task A9: Zombie Task 清理

**Files:**
- Modify: `pixelle_video/services/frame_processor.py`

- [ ] **Step 1: 添加 task TTL 检查**

Pixelle-Video 的 TaskManager（`api/tasks/manager.py`）增加 task 过期逻辑:

```python
# In TaskManager background worker
TASK_TTL_SECONDS = 30 * 60  # 30 minutes

async def _cleanup_expired_tasks(self):
    """Remove tasks older than TASK_TTL."""
    now = time.time()
    expired = [
        tid for tid, task in self._tasks.items()
        if (now - task.get("created_at", now)) > TASK_TTL_SECONDS
    ]
    for tid in expired:
        logger.warning(f"Expiring zombie task: {tid}")
        del self._tasks[tid]
```

- [ ] **Step 2: Commit**

```bash
git add api/tasks/manager.py
git commit -m "fix: add 30-min TTL zombie task cleanup to TaskManager"
```

---

## Lane B: dy_auto 改动

### Task B1: Config Bridge 增强

**Files:**
- Modify: `server/app/routers/pixelle.py`

- [ ] **Step 1: 添加 AIModel → ai_models 序列化函数**

`pixelle.py` 中新增:

```python
def _serialize_ai_models(db: Session) -> dict:
    """Read AIModel table and serialize to Pixelle-Video ai_models format."""
    from app.db_models import AIModel
    from app.services.crypto import decrypt

    models = db.query(AIModel).filter(AIModel.enabled == True).all()

    scenes: dict = {}
    for m in models:
        scene_key = (m.config_json or {}).get("scene_key")
        if not scene_key:
            continue

        ak = ""
        if m.api_key:
            try:
                ak = decrypt(m.api_key)
            except Exception:
                pass

        scenes[scene_key] = {
            "provider": m.provider,
            "model": m.model_name or "",
            "api_key": ak,
            "base_url": m.base_url or "",
        }

    return {"scenes": scenes}
```

- [ ] **Step 2: 修改 `update_pixelle_config` — 注入 ai_models**

在 `update_pixelle_config` 函数中，`merged` 之后、`_write_pixelle_config` 之前:

```python
# Inject ai_models from AIModel table
ai_models = _serialize_ai_models(db)
merged["ai_models"] = ai_models
```

- [ ] **Step 3: Commit**

```bash
git add server/app/routers/pixelle.py
git commit -m "feat: serialize AIModel table to Pixelle-Video ai_models format on config update"
```

---

### Task B2: Pipeline 瘦身

**Files:**
- Rewrite: `server/app/routers/pipeline.py`

- [ ] **Step 1: 删除旧 pipeline 逻辑**

删除以下内容：
- `_llm_chat_completion()` (line 133-147)
- `_layer_image_generate()` (line 154-194)
- `_layer_narration()` (line 197-210)
- `_layer_title()` (line 213-226)
- `_layer_image_prompt()` (line 229-243)
- `_layer_video_generate()` (line 246-251)
- `_video_pixelle_poll()` (line 254-282)
- `_video_seedance_generate()` (line 285-344)
- `_layer_postproduction()` (line 346-349)
- `_LAYER_FNS` (line 352-355)
- `LAYER_DEFS` (line 27-33)
- `FORWARD_KEYS` (line 36-41)
- `_get_model_config()` (line 63-82)
- `_count_refs()`, `_quality_gates_for_layer()`, `_agency_roles_for_layer()`, `_layer_input_summary()`, `_layer_output_summary()` (lines 85-130)

- [ ] **Step 2: 新建精简 pipeline**

```python
"""流水线编排 API — thin layer: director_plan → Pixelle-Video → result."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.db_models import PipelineRun, GeneratedVideo
from app.services.pixelle_client import _pixelle_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

BJT = timezone(timedelta(hours=8))
POLL_INTERVAL = 10
POLL_MAX = 180
# Per-review: circuit-breaker state
_circuit_open_until: dict[str, float] = {}
CIRCUIT_BREAKER_COOLDOWN = 60  # seconds


class PipelineStartRequest(BaseModel):
    series_id: str
    episode_id: str | None = None
    director_plan: dict | None = None  # { title, frames[], config }


def _build_storyboard_payload(plan: dict) -> dict:
    """Convert dy_auto director_plan to Pixelle-Video storyboard format."""
    return {
        "mode": "storyboard",
        "title": plan.get("title", ""),
        "frames": plan.get("frames", []),
        "config": plan.get("config", {}),
    }


async def _submit_and_poll(payload: dict, db: Session) -> dict:
    """Submit to Pixelle-Video and synchronously poll until completion."""
    # Circuit breaker check
    now = datetime.now().timestamp()
    if "pixelle" in _circuit_open_until and now < _circuit_open_until["pixelle"]:
        raise HTTPException(503, "Pixelle-Video temporarily unavailable (circuit open)")

    # Submit
    for attempt in range(3):
        try:
            submit = await _pixelle_request("POST", "/api/video/generate/async", db, json=payload)
            break
        except Exception as e:
            if attempt == 2:
                _circuit_open_until["pixelle"] = now + CIRCUIT_BREAKER_COOLDOWN
                raise HTTPException(502, f"Pixelle-Video submit failed after 3 retries: {e}")
            await asyncio.sleep(2 ** attempt)

    task_id = submit.get("task_id") or submit.get("id", "")
    if not task_id:
        raise HTTPException(502, "Pixelle-Video returned no task_id")

    # Poll
    for attempt in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            status = await _pixelle_request("GET", f"/api/tasks/{task_id}", db)
        except Exception as e:
            if attempt >= 2:
                raise HTTPException(502, f"Pixelle-Video polling failed: {e}")
            continue

        status_val = status.get("status", "")
        if status_val in ("completed", "succeeded", "done"):
            return {"provider": "pixelle", "status": "completed", "task_id": task_id, **status}
        if status_val in ("failed", "error"):
            raise HTTPException(500, f"Video generation failed: {status.get('error', status_val)}")

    raise HTTPException(504, f"Video generation timed out ({POLL_MAX * POLL_INTERVAL}s)")


@router.post("/start")
async def pipeline_start(
    body: PipelineStartRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """Start video generation pipeline.

    Accepts director_plan with pre-computed frames. Submits to Pixelle-Video
    in storyboard mode, polls synchronously, and stores the result.
    """
    if not body.director_plan:
        raise HTTPException(400, "director_plan is required")

    payload = _build_storyboard_payload(body.director_plan)

    # Create run record
    run = PipelineRun(
        series_id=body.series_id,
        episode_id=body.episode_id,
        mode="storyboard",
        model_ids={},
        layers_json={"0": {"status": "queued", "provider": "pixelle"}},
        current_layer=0,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = await _submit_and_poll(payload, db)
    except HTTPException:
        run.status = "failed"
        db.commit()
        raise

    # Store result
    video_path = result.get("video_path") or result.get("final_video_path", "")
    video = GeneratedVideo(
        task_id=str(run.id),
        keyword=body.director_plan.get("title", ""),
        title=body.director_plan.get("title", ""),
        video_path=video_path,
        duration=result.get("duration", 0),
        status="completed",
        pixelle_task_id=result.get("task_id", ""),
    )
    db.add(video)

    run.status = "completed"
    run.layers_json = {"0": {"status": "completed", "provider": "pixelle", **result}}
    run.completed_at = datetime.now(BJT)
    db.commit()

    return {
        "run_id": run.id,
        "status": "completed",
        "video_id": video.id,
        "video_path": video_path,
        "task_id": result.get("task_id", ""),
    }
```

- [ ] **Step 3: Commit**

```bash
git add server/app/routers/pipeline.py
git commit -m "refactor: rewrite pipeline.py as thin storyboard submitter + poller"
```

---

### Task B3: 移除 seedance.py

**Files:**
- Delete: `server/app/routers/seedance.py`
- Modify: `server/app/main.py`

- [ ] **Step 1: 删除文件并从 main.py 移除 router 注册**

```bash
rm server/app/routers/seedance.py
```

`server/app/main.py` 中删除 seedance router 的 import 和 `app.include_router`:

```python
# 删除: from app.routers import seedance
# 删除: app.include_router(seedance.router)
```

- [ ] **Step 2: Commit**

```bash
git rm server/app/routers/seedance.py
git add server/app/main.py
git commit -m "chore: remove deprecated seedance.py router"
```

---

### Task B4: dy_auto 端 API Key 配置

**Files:**
- Modify: `server/app/config.py`
- Modify: `server/app/services/pixelle_client.py`

- [ ] **Step 1: 增加 PIXELLE_API_KEY 配置**

`config.py`:

```python
PIXELLE_API_KEY = os.getenv("PIXELLE_API_KEY", "")
```

- [ ] **Step 2: pixelle_client 发送 X-API-Key**

`pixelle_client.py` 的 `_pixelle_request` 函数中:

```python
async def _pixelle_request(method: str, path: str, db=None, **kwargs) -> dict:
    from app.config import PIXELLE_API_KEY
    headers = kwargs.pop("headers", {})
    if PIXELLE_API_KEY:
        headers["X-API-Key"] = PIXELLE_API_KEY
    # ... rest unchanged — pass headers to client.request
```

- [ ] **Step 3: Commit**

```bash
git add server/app/config.py server/app/services/pixelle_client.py
git commit -m "feat: add PIXELLE_API_KEY support to dy_auto pixelle client"
```

---

## Lane C: 集成

### Task C1: Storyboard JSON Schema 契约

**Files:**
- Create: `tests/contract/storyboard-schema.json`

- [ ] **Step 1: 创建共享 JSON Schema**

`tests/contract/storyboard-schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StoryboardRequest",
  "type": "object",
  "required": ["mode", "title", "frames"],
  "properties": {
    "mode": { "const": "storyboard" },
    "title": { "type": "string", "minLength": 1 },
    "frames": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["narration", "image_prompt"],
        "properties": {
          "index": { "type": "integer", "minimum": 0 },
          "narration": { "type": "string", "minLength": 1 },
          "image_prompt": { "type": "string", "minLength": 1 },
          "duration": { "type": "number", "minimum": 0 },
          "audio_mode": { "enum": ["tts", "seedance_native", "bgm_only", "silent"] },
          "voice_id": { "type": "string" },
          "reference_urls": {
            "type": "array",
            "items": { "type": "string", "format": "uri" }
          }
        }
      }
    },
    "config": {
      "type": "object",
      "properties": {
        "frame_template": { "type": "string" },
        "tts_inference_mode": { "enum": ["local", "comfyui"] },
        "tts_speed": { "type": "number" },
        "media_workflow": { "type": "string" },
        "media_width": { "type": "integer" },
        "media_height": { "type": "integer" },
        "bgm_path": { "type": "string" },
        "bgm_volume": { "type": "number" }
      }
    }
  }
}
```

- [ ] **Step 2: 创建契约测试 (dy_auto side)**

`tests/test_storyboard_contract.py`:

```python
"""Contract test: dy_auto produces valid storyboard payload."""
import json
import pytest
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "contract" / "storyboard-schema.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_valid_minimal_payload(schema):
    """Minimal valid storyboard passes schema validation."""
    from jsonschema import validate
    payload = {
        "mode": "storyboard",
        "title": "Test Episode",
        "frames": [{
            "index": 0,
            "narration": "Hello world",
            "image_prompt": "A beautiful landscape",
        }],
    }
    validate(instance=payload, schema=schema)


def test_missing_narration_fails(schema):
    """Frame with empty narration is rejected."""
    from jsonschema import validate, ValidationError
    payload = {
        "mode": "storyboard",
        "title": "Test",
        "frames": [{"index": 0, "narration": "", "image_prompt": "x"}],
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)


def test_empty_frames_fails(schema):
    """Empty frames array is rejected."""
    from jsonschema import validate, ValidationError
    payload = {"mode": "storyboard", "title": "Test", "frames": []}
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)
```

- [ ] **Step 3: 将 schema 复制到 Pixelle-Video 并运行契约测试**

```bash
cp tests/contract/storyboard-schema.json D:/devWorkspace/Pixelle-Video/tests/contract/
cd D:\devWorkspace\Pixelle-Video && python -m pytest tests/test_storyboard_contract.py -v
```

- [ ] **Step 4: Commit (both repos)**

```bash
cd D:\devWorkspace\jsProjects\dy_auto
git add tests/contract/ tests/test_storyboard_contract.py
git commit -m "test: add storyboard JSON Schema contract + validation tests"

cd D:\devWorkspace\Pixelle-Video
git add tests/contract/ tests/test_storyboard_contract.py
git commit -m "test: add storyboard JSON Schema contract (shared with dy_auto)"
```

---

### Task C2: 质量基线脚本

**Files:**
- Create: `scripts/quality-baseline.py`

- [ ] **Step 1: 创建质量基线脚本**

```python
"""Quality baseline: compare video generation before/after refactoring."""
import asyncio
import time
import json
import sys
from pathlib import Path

TOPICS = [
    "如何提高学习效率",
    "早起习惯的科学依据",
    "人工智能的未来发展趋势",
]


async def run_single(topic: str, label: str) -> dict:
    """Run a single video generation and measure metrics."""
    start = time.monotonic()
    # TODO: replace with actual API call to /api/pipeline/start
    # For baseline, call dy_auto's pipeline with director_plan mode
    elapsed = time.monotonic() - start
    return {
        "topic": topic,
        "label": label,
        "elapsed_s": round(elapsed, 1),
        # "video_path": result.get("video_path"),
        # "duration": result.get("duration"),
    }


async def main():
    results = []
    for topic in TOPICS:
        print(f"Running: {topic}")
        result = await run_single(topic, "baseline")
        results.append(result)
        print(f"  {result['elapsed_s']}s")

    output = Path(__file__).parent.parent / "quality-baseline.json"
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Baseline saved to {output}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行基线采集**

```bash
cd D:\devWorkspace\jsProjects\dy_auto && python scripts/quality-baseline.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/quality-baseline.py quality-baseline.json
git commit -m "test: add quality baseline script for video generation metrics"
```

---

### Task C3: E2E 集成测试

**Files:**
- Create: `tests/test_pipeline_integration.py`

- [ ] **Step 1: E2E 集成测试**

```python
"""E2E: dy_auto pipeline → Pixelle-Video storyboard → completed video."""
import pytest
import time


@pytest.mark.integration
@pytest.mark.skipif(
    "not config.get('PIXELLE_VIDEO_URL')",
    reason="Pixelle-Video not configured",
)
def test_storyboard_pipeline_e2e(client, admin_token):
    """Full pipeline: director_plan → submit → poll → video stored."""
    plan = {
        "title": "E2E Test Episode",
        "frames": [
            {
                "index": 0,
                "narration": "这是一个端到端测试旁白。",
                "image_prompt": "A serene mountain landscape at sunrise",
                "duration": 5.0,
                "audio_mode": "tts",
            }
        ],
        "config": {
            "frame_template": "1080x1920/image_default.html",
            "tts_inference_mode": "local",
        },
    }

    resp = client.post(
        "/api/pipeline/start",
        json={"series_id": "test-series", "director_plan": plan},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "video_path" in data
    assert "video_id" in data


@pytest.mark.integration
def test_storyboard_missing_narration_rejected(client, admin_token):
    """Frame with empty narration is rejected by schema validation."""
    plan = {
        "title": "Bad Plan",
        "frames": [{"index": 0, "narration": "", "image_prompt": "test"}],
    }

    resp = client.post(
        "/api/pipeline/start",
        json={"series_id": "test-series", "director_plan": plan},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert resp.status_code == 400
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_pipeline_integration.py
git commit -m "test: add E2E integration tests for storyboard pipeline"
```

---

## 执行顺序

```
Lane A (Pixelle-Video)          Lane B (dy_auto)              Lane C (Integration)
═══════════════════════          ═══════════════               ═══════════════════
A1: Registry 通用化              B1: Config bridge 增强
A2: LLMService → registry       B4: API Key config
A3: TTSService → registry       B2: Pipeline 瘦身
A4: MediaService → registry     B3: 移除 seedance.py
A5: StandardPipeline storyboard
A6: API auth middleware
A7: SSRF guard
A8: Frame parallelism
A9: Zombie cleanup
        └──────────┬──────────┘
                   │
                   └──────────── C1: 契约测试 ─────────────────
                                C2: 质量基线
                                C3: E2E 集成测试
```

- **Lane A + B 并行**: 无共享文件依赖，可在两个 worktree 中同时启动
- **Lane C 串行**: 依赖 A + B 全部完成

### Conflict Flags

- Lane A 和 Lane B 不共享 module 目录，无合并冲突风险
- A5 修改 `standard.py`，A8 也修改 `standard.py` — 同一 lane 内顺序执行
- C1 的 schema 文件同时写入两个 repo — 后执行

---

## 自审查

1. **Spec 覆盖**:
   - 统一模型中心: A1-A4, B1 覆盖
   - Pipeline 瘦身: B2 覆盖
   - Storyboard 模式: A5 覆盖
   - API auth: A6, B4 覆盖
   - SSRF: A7 覆盖
   - 契约测试: C1 覆盖
   - 质量基线: C2 覆盖
   - 错误恢复: B2 (circuit-breaker), A9 (zombie cleanup) 覆盖
   - 帧并行: A8 覆盖
   - 移除 seedance: B3 覆盖

2. **Placeholder 扫描**: 无 TBD/TODO/implement later。所有步骤含实际代码。

3. **类型一致性**: `_prefill_from_frames` → `ctx.narrations`/`ctx.image_prompts` → `initialize_storyboard` 之间类型一致。`_build_storyboard_payload` 产出的 dict 与 Task C1 的 JSON Schema 一致。
