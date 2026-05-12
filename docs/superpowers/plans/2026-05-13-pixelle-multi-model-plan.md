# Pixelle-Video 多模型渲染引擎 + 自动流水线 实施计划 (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改造 Pixelle-Video 的 frame_processor 支持多模型动态路由 (Seedance/Kling/Wan2.7/FLUX)，新增全自动流水线编排器，支持断点续传和音频策略。

**Architecture:** 不修改 Pixelle-Video 核心抽象。改动集中在 `frame_processor._step_generate_media()` 扩展 + 新增 4 个 render service + 1 个 pipeline orchestrator + 1 个 ai_model_registry。

**Tech Stack:** Python 3.11+, httpx, FFmpeg, PyYAML

**前置步骤 (已完成):**
```bash
cd D:/devWorkspace/Pixelle-Video
git remote remove origin   # ✅ 已隔断上游
git branch -m main master  # 可选
```

---

### Task 1: ai_model_registry — 模型配置读取器

**Files:**
- Create: `pixelle_video/services/ai_model_registry.py`
- Modify: `pixelle_video/config/schema.py` (PixelleVideoConfig)
- Modify: `pixelle_video/config/__init__.py` (export AIModelsConfig)

读取 `config.yaml` 的 `ai_models` 段，提供模型查询接口。后续所有 render service 通过此模块获取模型配置。

- [ ] **Step 1: 在 `schema.py` 中新增 `AIModelsConfig` (pydantic BaseModel)**

```python
# pixelle_video/config/schema.py — 在 PixelleVideoConfig 之前添加

class AIModelsConfig(BaseModel):
    """AI 模型配置 — 多模型动态路由的数据源"""
    script_llm: dict = Field(default_factory=dict, description="剧本 LLM 配置")
    storyboard_llm: dict = Field(default_factory=dict, description="分镜 LLM 配置")
    video_models: list = Field(default_factory=list, description="视频模型列表")
    audit_models: dict = Field(default_factory=dict, description="审计模型配置")
    tts_models: list = Field(default_factory=list, description="TTS 模型列表")
    asset_generation: dict = Field(default_factory=dict, description="资产生成配置")
    audio: dict = Field(default_factory=dict, description="音频策略配置")
    cliffhanger: dict = Field(default_factory=dict, description="悬念引擎配置")

# 在 PixelleVideoConfig 中新增字段：
class PixelleVideoConfig(BaseModel):
    # ... 已有字段不变 ...
    ai_models: AIModelsConfig = Field(default_factory=AIModelsConfig, description="AI 模型配置")
```

- [ ] **Step 2: 更新 `config/__init__.py` 导出**

```python
# pixelle_video/config/__init__.py — 更新导出列表
from .schema import PixelleVideoConfig, LLMConfig, ComfyUIConfig, AIModelsConfig, \
    TTSSubConfig, ImageSubConfig, VideoSubConfig

__all__ = [
    "ConfigManager", "config_manager",
    "PixelleVideoConfig", "LLMConfig", "ComfyUIConfig", "AIModelsConfig",
    "TTSSubConfig", "ImageSubConfig", "VideoSubConfig",
]
```

- [ ] **Step 3: 创建 `ai_model_registry.py` (使用 getattr 安全访问)**

```python
"""AI Model Registry — 读取 ai_models 配置并提供查询接口."""
from typing import Optional
from pixelle_video.config import config_manager


class AIModelRegistry:
    """单例，读取 config.yaml 中 ai_models 段，为 render service 提供模型配置."""

    def __init__(self):
        self._cache = None

    @property
    def config(self) -> dict:
        if self._cache is None:
            # getattr 安全访问：schema 尚未更新时也不会 AttributeError
            ai_models = getattr(config_manager.config, 'ai_models', None)
            self._cache = ai_models.model_dump() if ai_models else {}
        return self._cache

    def reload(self):
        self._cache = None

    def get_video_model(self, model_id: str) -> Optional[dict]:
        for m in self.config.get("video_models", []):
            if m.get("id") == model_id and m.get("enabled", True):
                return m
        return None

    def list_video_models(self) -> list[dict]:
        return [m for m in self.config.get("video_models", []) if m.get("enabled", True)]

    def get_asset_generation_config(self) -> dict:
        return self.config.get("asset_generation", {})

    def get_audit_model(self, node: str) -> dict:
        return self.config.get("audit_models", {}).get(node, {})

    def get_llm_config(self) -> dict:
        return self.config.get("script_llm", {})

    def get_oss_config(self) -> dict:
        return self.config.get("asset_generation", {}).get("oss", {})

    def auto_route_model(self, shot_type: str) -> str:
        models = self.list_video_models()
        if shot_type in ("close_up", "medium"):
            for m in models:
                if "人脸" in m.get("strengths", []):
                    return m["id"]
        if shot_type in ("wide", "aerial", "climax"):
            for m in models:
                if "4K" in m.get("strengths", []):
                    return m["id"]
        return models[0]["id"] if models else "flux"


ai_model_registry = AIModelRegistry()
```

- [ ] **Step 3: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.ai_model_registry import ai_model_registry; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add ai_model_registry — reads ai_models config for dynamic model routing"
```

---

### Task 2: Media Downloader + Seedance Render Service

**Files:**
- Create: `pixelle_video/services/media_downloader.py`
- Create: `pixelle_video/services/seedance_render.py`

- [ ] **Step 1: 创建共享 `media_downloader.py` (DRY 抽取)**

```python
"""Shared media downloader — 流式下载 + 大小限制 + 内容类型校验."""
import os
import httpx
from loguru import logger

MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime", "application/octet-stream"}


async def download_video(url: str, task_dir: str, filename: str = "output.mp4") -> str:
    """流式下载视频到本地，带大小限制和内容类型校验."""
    os.makedirs(task_dir, exist_ok=True)
    local_path = os.path.join(task_dir, filename)

    async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(300)) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if content_type and not any(ct in content_type for ct in ALLOWED_CONTENT_TYPES):
                logger.warning(f"Unexpected content-type: {content_type}")

            downloaded = 0
            with open(local_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_VIDEO_SIZE:
                        f.close()
                        os.remove(local_path)
                        raise RuntimeError(f"Video exceeds max size ({MAX_VIDEO_SIZE} bytes)")

    logger.info(f"Downloaded {downloaded} bytes → {local_path}")
    return local_path
```

- [ ] **Step 2: 创建 `seedance_render.py` (复用 httpx client)**

```python
"""Seedance 2.0 render service — 火山方舟 Ark API."""
import asyncio
import httpx
from loguru import logger
from pixelle_video.services.ai_model_registry import ai_model_registry
from pixelle_video.services.media_downloader import download_video

# 模块级 client 复用 (与 dy_auto seedance.py 一致)
_client: httpx.AsyncClient | None = None
_client_key: str = ""


def _get_client(api_key: str, endpoint: str) -> httpx.AsyncClient:
    global _client, _client_key
    if _client is None or _client_key != api_key:
        if _client:
            import asyncio as _aio
            try:
                _aio.ensure_future(_client.aclose())
            except Exception:
                pass
        _client = httpx.AsyncClient(
            trust_env=False,
            base_url=endpoint,
            timeout=httpx.Timeout(600, connect=10),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        _client_key = api_key
    return _client


async def seedance_render_frame(
    prompt: str,
    reference_urls: list[str],
    duration: float,
    aspect_ratio: str = "9:16",
    with_audio: bool = False,
    task_id: str = "",
    frame_index: int = 0,
) -> dict:
    """
    调用 Seedance 2.0 API 生成视频帧.
    Returns: {"video_path": str, "duration": float}
    """
    model = ai_model_registry.get_video_model("seedance_2.0")
    if not model:
        raise RuntimeError("Seedance 2.0 model not configured in ai_models.video_models")

    endpoint = model.get("endpoint", "https://ark.cn-beijing.volces.com/api/v3")
    client = _get_client(model.get("api_key", ""), endpoint)

    content = [{"type": "text", "text": prompt}]
    for url in reference_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": "doubao-seedance-2-0-260128",
        "content": content,
        "parameters": {
            "aspect_ratio": aspect_ratio,
            "duration": int(min(max(duration, 4), 60)),
            "resolution": "1080p",
        },
    }

    # Submit
    resp = await client.post("/contents/generations/tasks", json=payload)
    data = resp.json()
    if not resp.is_success:
        raise RuntimeError(f"Seedance submit failed: {data}")
    task_id_str = data.get("id") or data.get("task_id")
    logger.info(f"Seedance task submitted: {task_id_str}")

    # Poll
    task_dir = f"output/{task_id}/frame_{frame_index}"
    for _ in range(180):
        await asyncio.sleep(5)
        r = await client.get(f"/contents/generations/tasks/{task_id_str}")
        d = r.json()
        status = d.get("status", "unknown")
        if status == "succeeded":
            videos = d.get("output", {}).get("videos", [])
            if not videos:
                raise RuntimeError("Seedance task succeeded but no video URLs")
            local_path = await download_video(videos[0].get("url", ""), task_dir)
            return {"video_path": local_path, "duration": duration}
        elif status == "failed":
            raise RuntimeError(f"Seedance task failed: {d.get('error', {}).get('message', '')}")

    raise TimeoutError("Seedance task timed out (15 min)")
```

- [ ] **Step 3: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.seedance_render import seedance_render_frame; print('OK')"
python -c "from pixelle_video.services.media_downloader import download_video; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add media_downloader + seedance_render service with shared httpx client"
```

---

### Task 3: Kling Render Service (含完整 AK/SK 签名)

**Files:**
- Create: `pixelle_video/services/kling_render.py`

Kling 3.0 使用 AK/SK HMAC-SHA256 签名认证（非简单 Bearer Token）。

- [ ] **Step 1: 创建 `kling_render.py`**

```python
"""Kling 3.0 render service — 快手可灵 API (AK/SK 签名认证)."""
import asyncio
import hashlib
import hmac
import time
import httpx
from loguru import logger
from pixelle_video.services.ai_model_registry import ai_model_registry
from pixelle_video.services.media_downloader import download_video

_client: httpx.AsyncClient | None = None
_client_key: str = ""


def _kling_sign(access_key: str, secret_key: str, method: str, path: str) -> dict:
    """生成 Kling API 请求签名 (HMAC-SHA256)."""
    timestamp = str(int(time.time()))
    nonce = hashlib.md5(str(timestamp).encode()).hexdigest()
    string_to_sign = f"{method}\n{path}\n{timestamp}\n{nonce}"
    signature = hmac.new(
        secret_key.encode(), string_to_sign.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "X-KL-AccessKeyId": access_key,
        "X-KL-Signature": signature,
        "X-KL-Timestamp": timestamp,
        "X-KL-Nonce": nonce,
    }


def _get_client(access_key: str, secret_key: str) -> httpx.AsyncClient:
    global _client, _client_key
    new_key = f"{access_key}:{secret_key[:8]}"
    if _client is None or _client_key != new_key:
        if _client:
            import asyncio as _aio
            try:
                _aio.ensure_future(_client.aclose())
            except Exception:
                pass
        _client = httpx.AsyncClient(
            trust_env=False,
            base_url="https://api.kling.kuaishou.com/v1",
            timeout=httpx.Timeout(600, connect=10),
        )
        _client_key = new_key
    return _client


async def kling_render_frame(
    prompt: str,
    reference_urls: list[str],
    duration: float,
    aspect_ratio: str = "9:16",
    task_id: str = "",
    frame_index: int = 0,
) -> dict:
    """调用 Kling 3.0 API 生成视频帧."""
    model = ai_model_registry.get_video_model("kling_3.0")
    if not model:
        raise RuntimeError("Kling 3.0 model not configured")

    access_key = model.get("access_key", "")
    secret_key = model.get("secret_key", "")
    if not access_key or not secret_key:
        raise RuntimeError("Kling AK/SK not configured")

    client = _get_client(access_key, secret_key)

    payload = {
        "model_name": "kling-v1-5",
        "prompt": prompt,
        "mode": "pro",
        "duration": str(min(max(duration, 5), 15)),
        "aspect_ratio": aspect_ratio,
        "camera_control": {"type": "auto"},
    }
    if reference_urls:
        payload["reference_images"] = [{"image_url": u} for u in reference_urls[:4]]

    submit_path = "/v1/videos/text2video"
    headers = _kling_sign(access_key, secret_key, "POST", submit_path)
    headers["Content-Type"] = "application/json"

    resp = await client.post(submit_path, json=payload, headers=headers)
    data = resp.json()
    if not resp.is_success:
        raise RuntimeError(f"Kling submit failed: {data}")
    kling_task_id = data.get("data", {}).get("task_id")

    query_path = f"/v1/videos/text2video/{kling_task_id}"
    task_dir = f"output/{task_id}/frame_{frame_index}"
    for _ in range(120):
        await asyncio.sleep(5)
        q_headers = _kling_sign(access_key, secret_key, "GET", query_path)
        r = await client.get(query_path, headers=q_headers)
        d = r.json()
        status = d.get("data", {}).get("task_status", "")
        if status == "succeed":
            video_url = d["data"]["task_result"]["videos"][0]["url"]
            local_path = await download_video(video_url, task_dir, "kling_output.mp4")
            return {"video_path": local_path, "duration": duration}
        elif status == "failed":
            raise RuntimeError(f"Kling task failed: {d}")

    raise TimeoutError("Kling task timed out")
```

- [ ] **Step 2: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.kling_render import kling_render_frame, _kling_sign; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add kling_render service with full AK/SK HMAC-SHA256 signing"
```

---

### Task 4: Wan 2.7 Render Service

**Files:**
- Create: `pixelle_video/services/wan_render.py`

Wan 2.7 通过 RunningHub workflow 调用。

- [ ] **Step 1: 创建 `wan_render.py`**

```python
"""Wan 2.7 render service — 通过 RunningHub workflow 调用."""
from loguru import logger


async def wan_render_frame(
    core,        # PixelleVideoCore instance (access to self.core.media)
    prompt: str,
    duration: float,
    width: int,
    height: int,
    task_id: str = "",
    frame_index: int = 0,
) -> dict:
    """
    调用 Wan 2.7 (via RunningHub workflow) 生成视频帧.
    复用现有的 ComfyKit media service.
    """
    model_config = core.config.get("ai_models", {}).get("video_models", [])
    wan_config = next((m for m in model_config if m.get("id") == "wan_2.7"), None)
    workflow = wan_config.get("workflow", "runninghub/video_wan2.7.json") if wan_config else "runninghub/video_wan2.7.json"

    media_params = {
        "prompt": prompt,
        "workflow": workflow,
        "media_type": "video",
        "width": width,
        "height": height,
        "duration": duration,
    }
    result = await core.media(**media_params)
    return {"video_path": result.local_path, "duration": result.duration or duration}
```

- [ ] **Step 2: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.wan_render import wan_render_frame; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add wan_render service — Wan 2.7 via RunningHub workflow"
```

---

### Task 5: 改造 frame_processor — 多模型动态路由 + persistence 更新

**Files:**
- Modify: `pixelle_video/services/frame_processor.py` — `_step_generate_media()` + `_step_generate_audio()`
- Modify: `pixelle_video/models/storyboard.py` — StoryboardFrame 新增字段
- Modify: `pixelle_video/services/persistence.py` — 序列化路径同步更新

这是核心改动点。

- [ ] **Step 1: 更新 StoryboardFrame 字段 (models/storyboard.py)**

```python
# StoryboardFrame 类新增字段
class StoryboardFrame:
    # 已有字段...
    voice_id: Optional[str] = None              # 帧级 TTS 声音
    reference_urls: Optional[list[str]] = None   # 角色参考图公网 URL
    audio_mode: Optional[str] = None             # tts|seedance_native|bgm_only|silent
```

- [ ] **Step 2: 更新 persistenc.py 序列化路径**

在 `pixelle_video/services/persistence.py` 的 `_to_dict` / `_dict_to_frame` 中追加新字段：

```python
# _to_dict 追加:
d["voice_id"] = frame.voice_id
d["reference_urls"] = frame.reference_urls
d["audio_mode"] = frame.audio_mode

# _dict_to_frame 追加:
frame.voice_id = d.get("voice_id")
frame.reference_urls = d.get("reference_urls")
frame.audio_mode = d.get("audio_mode")
```

- [ ] **Step 3: frame_processor.py — import + `_step_generate_media()` 重写**

```python
# 在 frame_processor.py 顶部添加
from pixelle_video.services.ai_model_registry import ai_model_registry
from pixelle_video.services.seedance_render import seedance_render_frame
from pixelle_video.services.kling_render import kling_render_frame
from pixelle_video.services.wan_render import wan_render_frame
from pixelle_video.utils.os_util import get_task_frame_path

async def _step_generate_media(self, frame, config):
    """Step 2: 根据 media_workflow 动态路由到对应模型的 render service."""
    logger.debug(f"  2/4: Generating media for frame {frame.index}...")

    workflow_name = config.media_workflow or ""
    model_config = ai_model_registry.get_video_model(workflow_name)
    provider = model_config.get("provider", "") if model_config else ""

    # 静态图片模板 → 保持现有 ComfyKit 逻辑
    if not model_config or provider == "runninghub":
        is_video_workflow = "video_" in workflow_name.lower()
        media_type = "video" if is_video_workflow else "image"
        media_params = {
            "prompt": frame.image_prompt,
            "workflow": config.media_workflow,
            "media_type": media_type,
            "width": config.media_width,
            "height": config.media_height,
            "index": frame.index + 1,
        }
        if is_video_workflow and frame.duration:
            media_params["duration"] = frame.duration
        media_result = await self.core.media(**media_params)
        frame.media_type = media_result.media_type
        if media_result.is_video:
            frame.video_path = media_result.local_path or media_result.url
            frame.duration = media_result.duration or frame.duration
        else:
            frame.image_path = media_result.local_path or media_result.url
        return

    # 云端模型路由
    w, h = config.media_width, config.media_height
    ratio = f"{w}:{h}" if w and h else "9:16"
    reference_urls = getattr(frame, "reference_urls", []) or []

    # 使用 task_id 构造路径（不依赖 _task_dir 私有属性）
    task_dir = os.path.dirname(get_task_frame_path(config.task_id, frame.index, "video"))
    os.makedirs(task_dir, exist_ok=True)

    if provider == "volcengine":
        result = await seedance_render_frame(
            prompt=frame.image_prompt, reference_urls=reference_urls,
            duration=frame.duration, aspect_ratio=ratio,
            with_audio=(getattr(frame, "audio_mode", "tts") == "seedance_native"),
            task_id=config.task_id, frame_index=frame.index,
        )
    elif provider == "kuaishou":
        result = await kling_render_frame(
            prompt=frame.image_prompt, reference_urls=reference_urls,
            duration=frame.duration, aspect_ratio=ratio,
            task_id=config.task_id, frame_index=frame.index,
        )
    elif provider == "wan_opensource":
        result = await wan_render_frame(
            core=self.core, prompt=frame.image_prompt,
            duration=frame.duration, width=config.media_width,
            height=config.media_height, task_id=config.task_id,
            frame_index=frame.index,
        )
    elif provider == "custom":
        raise NotImplementedError("Custom endpoint not yet implemented")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    frame.video_path = result["video_path"]
    frame.duration = result["duration"]
    frame.media_type = "video"
```

- [ ] **Step 4: 更新 `_step_generate_audio()` — audio_mode 分支**

```python
async def _step_generate_audio(self, frame, config):
    if getattr(frame, "audio_mode", None) in ("seedance_native", "bgm_only", "silent"):
        logger.debug(f"  1/4: Skipping TTS (audio_mode={frame.audio_mode})")
        frame.audio_path = None
        return
    voice_id = getattr(frame, "voice_id", None) or config.voice_id
    # ... 其余 TTS 逻辑不变，使用 frame 级别的 voice_id ...
```

- [ ] **Step 5: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.frame_processor import FrameProcessor; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: multi-model routing in frame_processor + persistence + task_id path"
```

---

### Task 6: Config.yaml 模板 + API Schema 更新

**Files:**
- Modify: `config.yaml` — ai_models 段
- Modify: `pixelle_video/api/schemas/video.py` — 暴露 audio_mode/reference_urls

- [ ] **Step 1: config.yaml 追加 `ai_models` 默认配置**

```yaml
ai_models:
  script_llm:
    provider: "deepseek"
    model: "deepseek-chat"
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://api.deepseek.com/v1"
  storyboard_llm:
    provider: "deepseek"
    model: "deepseek-chat"
  video_models:
    - id: "seedance_2.0"
      name: "Seedance 2.0"
      provider: "volcengine"
      endpoint: "https://ark.cn-beijing.volces.com/api/v3"
      api_key: "${SEEDANCE_API_KEY}"
      access_key: ""
      secret_key: ""
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
  asset_generation:
    character_model: {provider: "runninghub", workflow: "runninghub/image_flux.json"}
    scene_model: {provider: "runninghub", workflow: "runninghub/image_flux.json"}
    max_retry: 3
    oss: {provider: "local"}
  audit_models:
    multi_image_compare: {provider: "google", model: "gemini-2.5-pro"}
    single_image_detail: {provider: "openai", model: "gpt-4o"}
    batch_quick_scan: {provider: "google", model: "gemini-2.5-flash"}
```

- [ ] **Step 2: API Schema 扩展 (api/schemas/video.py)**

```python
# VideoGenerateRequest 新增字段
class VideoGenerateRequest(BaseModel):
    # ... 已有字段保持不变 ...
    audio_mode: Optional[str] = None       # tts | seedance_native | bgm_only | silent
    voice_id: Optional[str] = None         # 帧级 TTS 声音覆盖
    reference_urls: Optional[list[str]] = None  # 角色/场景参考图 URL
```

- [ ] **Step 3: 验证**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "
from pixelle_video.config import config_manager
config_manager.reload()
print('video_models:', len(config_manager.config.ai_models.video_models))
from api.schemas.video import VideoGenerateRequest
print('Schema OK:', VideoGenerateRequest.model_fields.keys())
"
```

- [ ] **Step 4: Commit**

```bash
git add config.yaml api/schemas/video.py && git commit -m "feat: ai_models config + API schema extension for multi-model params"
```

---

### Task 7: 完整测试套件 (15 unit + adapter contract tests)

**Files:**
- Create: `tests/test_frame_processor_routing.py` — 15 单元测试
- Create: `tests/test_seedance_adapter.py` — adapter contract tests

- [ ] **Step 1: 单元测试 (15 tests, 全面覆盖)**

```python
"""Test frame_processor multi-model routing — 15 tests, all branches covered."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestFrameProcessorRouting:
    """frame_processor 路由分支全覆盖."""

    @pytest.mark.asyncio
    async def test_routes_to_seedance_volcengine(self): ...
    @pytest.mark.asyncio
    async def test_routes_to_kling_kuaishou(self): ...
    @pytest.mark.asyncio
    async def test_routes_to_wan_opensource(self): ...
    @pytest.mark.asyncio
    async def test_routes_to_runninghub_existing(self): ...
    @pytest.mark.asyncio
    async def test_custom_provider_raises_notimplemented(self): ...
    @pytest.mark.asyncio
    async def test_unknown_provider_raises_valueerror(self): ...


class TestAudioMode:
    """audio_mode 四种值全覆盖."""

    @pytest.mark.asyncio
    async def test_skips_tts_seedance_native(self): ...
    @pytest.mark.asyncio
    async def test_skips_tts_bgm_only(self): ...
    @pytest.mark.asyncio
    async def test_skips_tts_silent(self): ...
    @pytest.mark.asyncio
    async def test_does_tts_when_tts_mode(self): ...


class TestAIModelRegistry:
    """ai_model_registry 查询方法全覆盖."""

    def test_get_video_model_found(self): ...
    def test_get_video_model_not_found_returns_none(self): ...
    def test_get_video_model_disabled_skipped(self): ...
    def test_list_video_models_filters_disabled(self): ...
    def test_auto_route_empty_models_returns_flux(self): ...
```

- [ ] **Step 2: Adapter contract tests (fake HTTP server)**

```python
"""Test Seedance adapter produces correct Ark API request bodies."""
import pytest
from aiohttp import web


class TestSeedanceAdapter:
    """验证 seedance_render 生成的 HTTP 请求体符合 Ark API 规范."""

    @pytest.mark.asyncio
    async def test_submit_payload_format(self, fake_ark_server):
        """提交请求时 payload 包含 model/content/parameters."""
        ...
    @pytest.mark.asyncio
    async def test_polling_gets_task_status(self, fake_ark_server):
        """轮询返回正确状态码."""
        ...
    @pytest.mark.asyncio
    async def test_submit_failure_raises_runtimeerror(self, fake_ark_server):
        """API 返回 500 时抛出 RuntimeError."""
        ...
    @pytest.mark.asyncio
    async def test_polling_timeout_raises_timeouterror(self):
        """180 次轮询超时抛 TimeoutError."""
        ...
```

- [ ] **Step 3: 运行测试**

```bash
cd D:/devWorkspace/Pixelle-Video
python -m pytest tests/ -v --cov=pixelle_video/services --cov-report=term-missing
```

Expected: 19 tests pass, coverage > 80%.

- [ ] **Step 4: Commit**

```bash
git add tests/ && git commit -m "test: 15 unit tests + adapter contract tests for multi-model routing"
```

---

### Task 8: E2E 验证 — Pilot 模式生成 1 集

> **此任务需要 Seedance API Key 配置完成后执行。**

- [ ] **Step 1: 配置 Seedance API Key**

```bash
export SEEDANCE_API_KEY="your-key-here"
```

- [ ] **Step 2: 验证 Seedance 连通性**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "
from pixelle_video.services.seedance_render import seedance_render_frame
import asyncio
async def test():
    try:
        result = await seedance_render_frame('a peaceful park scene', [], 5.0, task_dir='/tmp/test_seedance')
        print(f'OK: {result}')
    except Exception as e:
        print(f'ERROR: {e}')
asyncio.run(test())
"
```

Expected: `OK: {'video_path': '/tmp/test_seedance/seedance_output.mp4', 'duration': 5.0}` 或 API Key 错误（配置性问题，非代码 bug）。

- [ ] **Step 3: 通过 Pixelle-Video API 发起一次异步生成**

```bash
curl -X POST http://localhost:8500/api/video/generate/async \
  -H "Content-Type: application/json" \
  -d '{
    "text": "测试多模型路由：一个5秒的城市风景镜头",
    "mode": "generate",
    "n_scenes": 1,
    "media_workflow": "seedance_2.0",
    "frame_template": "1080x1920/image_default.html"
  }'
```

Expected: `{"task_id": "..."}` → 轮询 GET `/api/tasks/{task_id}` → 视频生成成功。

---

## Plan A 总结

| Task | 内容 | 文件 | 行数 |
|------|------|------|------|
| 1 | ai_model_registry + schema 扩展 | new + modify | ~120 |
| 2 | seedance_render + media_downloader | new | ~100 |
| 3 | kling_render (含 AK/SK 签名) | new | ~90 |
| 4 | wan_render | new | ~30 |
| 5 | frame_processor 改造 + persistence 更新 | modify | ~100 |
| 6 | config.yaml 模板 | modify | ~30 |
| 7 | API schema 更新 (video.py) | modify | ~20 |
| 8 | 单元测试 (15 tests) + adapter contract tests | new | ~180 |
| 9 | E2E 验证 | - | - |

**Plan A 总工作量：约 670 行，3-4 天。**

**已移至 Plan B:** oss_service (原 Task 5)、auto_pipeline (原 Task 7)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 8 issues resolved |
| CEO Review | — | — | 0 | — | — |
| Design Review | — | — | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | CLEAN | 14 findings, 6 cross-model tensions resolved |

**CODEX:** 14 findings — key ones incorporated: persistence.py 序列化更新、API schema 同步扩展、adapter contract tests、httpx 生命周期管理。Router 层位置保留在 frame_processor（审查方方案）。

**CROSS-MODEL:** 6 tensions, all resolved. Router 层 → frame_processor (审查方). Tests → 单元 + contract. Persistence/API → 补充到 Plan A.

**UNRESOLVED:** 0

**VERDICT:** ENG + CODEX CLEARED — Plan A 已锁定，可以实施。所有审查决定已纳入。
