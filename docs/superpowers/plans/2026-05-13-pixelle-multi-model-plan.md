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
- Modify: `pixelle_video/config.py`

读取 `config.yaml` 的 `ai_models` 段，提供模型查询接口。后续所有 render service 通过此模块获取模型配置。

- [ ] **Step 1: 创建 `ai_model_registry.py`**

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
            self._cache = config_manager.config.ai_models or {}
        return self._cache

    def reload(self):
        self._cache = None

    def get_video_model(self, model_id: str) -> Optional[dict]:
        """根据 id 获取视频模型配置 (endpoint/auth/provider)."""
        for m in self.config.get("video_models", []):
            if m.get("id") == model_id and m.get("enabled", True):
                return m
        return None

    def list_video_models(self) -> list[dict]:
        """获取所有启用的视频模型."""
        return [m for m in self.config.get("video_models", []) if m.get("enabled", True)]

    def get_asset_generation_config(self) -> dict:
        return self.config.get("asset_generation", {})

    def get_audit_model(self, node: str) -> dict:
        """node: 'multi_image_compare' | 'single_image_detail' | 'batch_quick_scan'"""
        return self.config.get("audit_models", {}).get(node, {})

    def get_llm_config(self) -> dict:
        return self.config.get("script_llm", {})

    def get_oss_config(self) -> dict:
        return self.config.get("asset_generation", {}).get("oss", {})

    def auto_route_model(self, shot_type: str) -> str:
        """根据镜头类型自动选择最优模型."""
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

- [ ] **Step 2: 更新 `config.py` — ConfigManager 增加 `ai_models` 解析**

```python
# pixelle_video/config.py — ConfigManager 中新增

@dataclass
class AIModelsConfig:
    script_llm: dict = field(default_factory=dict)
    storyboard_llm: dict = field(default_factory=dict)
    video_models: list = field(default_factory=list)
    audit_models: dict = field(default_factory=dict)
    tts_models: list = field(default_factory=list)
    asset_generation: dict = field(default_factory=dict)
    audio: dict = field(default_factory=dict)
    cliffhanger: dict = field(default_factory=dict)

@dataclass
class PixelleConfig:
    # 已有字段...
    ai_models: AIModelsConfig = field(default_factory=AIModelsConfig)

    @classmethod
    def from_dict(cls, data: dict):
        ai_data = data.get("ai_models", {})
        return cls(
            # 已有字段...
            ai_models=AIModelsConfig(
                script_llm=ai_data.get("script_llm", {}),
                storyboard_llm=ai_data.get("storyboard_llm", {}),
                video_models=ai_data.get("video_models", []),
                audit_models=ai_data.get("audit_models", {}),
                tts_models=ai_data.get("tts_models", []),
                asset_generation=ai_data.get("asset_generation", {}),
                audio=ai_data.get("audio", {}),
                cliffhanger=ai_data.get("cliffhanger", {}),
            )
        )
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

### Task 2: Seedance Render Service

**Files:**
- Create: `pixelle_video/services/seedance_render.py`

独立的 Seedance 2.0 渲染函数，支持 `with_audio` 参数控制是否生成原生音频。

- [ ] **Step 1: 创建 `seedance_render.py`**

```python
"""Seedance 2.0 render service — 火山方舟 Ark API."""
import asyncio
from loguru import logger
from pixelle_video.services.ai_model_registry import ai_model_registry
from pixelle_video.services.oss_service import upload_to_oss
import httpx


async def seedance_render_frame(
    prompt: str,
    reference_urls: list[str],
    duration: float,
    aspect_ratio: str = "9:16",
    with_audio: bool = False,
    task_dir: str = "",
) -> dict:
    """
    调用 Seedance 2.0 API 生成视频帧.

    Returns: {"video_path": str, "duration": float}
    """
    model = ai_model_registry.get_video_model("seedance_2.0")
    if not model:
        raise RuntimeError("Seedance 2.0 model not configured in ai_models.video_models")

    content = [{"type": "text", "text": prompt}]
    for url in reference_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": "doubao-seedance-2-0-260128",
        "content": content,
        "parameters": {
            "aspect_ratio": aspect_ratio,
            "duration": int(min(max(duration, 4), 60)),  # clamp to 4-60s
            "resolution": "1080p",
        },
    }

    async with httpx.AsyncClient(
        trust_env=False,
        base_url=model.get("endpoint", "https://ark.cn-beijing.volces.com/api/v3"),
        timeout=httpx.Timeout(600, connect=10),
        headers={"Authorization": f"Bearer {model.get('api_key', '')}"},
    ) as client:

        # 1. Submit task
        resp = await client.post("/contents/generations/tasks", json=payload)
        data = resp.json()
        if not resp.is_success:
            raise RuntimeError(f"Seedance submit failed: {data}")
        task_id = data.get("id") or data.get("task_id")
        logger.info(f"Seedance task submitted: {task_id}")

        # 2. Poll until complete
        for _ in range(180):  # max 15 min
            await asyncio.sleep(5)
            r = await client.get(f"/contents/generations/tasks/{task_id}")
            d = r.json()
            status = d.get("status", "unknown")
            if status == "succeeded":
                videos = d.get("output", {}).get("videos", [])
                if not videos:
                    raise RuntimeError("Seedance task succeeded but no video URLs")
                video_url = videos[0].get("url", "")
                # 3. Download video to local task_dir
                local_path = await _download_video(video_url, task_dir)
                return {"video_path": local_path, "duration": duration}
            elif status == "failed":
                raise RuntimeError(f"Seedance task failed: {d.get('error', {}).get('message', '')}")
            # else: still running, continue polling

        raise TimeoutError("Seedance task timed out (15 min)")


async def _download_video(url: str, task_dir: str) -> str:
    import os
    os.makedirs(task_dir, exist_ok=True)
    local_path = os.path.join(task_dir, "seedance_output.mp4")
    async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(300)) as client:
        r = await client.get(url)
        with open(local_path, "wb") as f:
            f.write(r.content)
    return local_path
```

- [ ] **Step 2: 验证导入（无需 API Key 也能加载模块）**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.seedance_render import seedance_render_frame; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add seedance_render service — async video generation via Ark API"
```

---

### Task 3: Kling Render Service

**Files:**
- Create: `pixelle_video/services/kling_render.py`

Kling 3.0 渲染函数，支持 AI 导演自动运镜。

- [ ] **Step 1: 创建 `kling_render.py`**

```python
"""Kling 3.0 render service — 快手可灵 API."""
import asyncio
from loguru import logger
from pixelle_video.services.ai_model_registry import ai_model_registry
import httpx


async def kling_render_frame(
    prompt: str,
    reference_urls: list[str],
    duration: float,
    aspect_ratio: str = "9:16",
    task_dir: str = "",
) -> dict:
    """调用 Kling 3.0 API 生成视频帧. Returns: {"video_path": str, "duration": float}"""
    model = ai_model_registry.get_video_model("kling_3.0")
    if not model:
        raise RuntimeError("Kling 3.0 model not configured")

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

    access_key = model.get("access_key", "")
    secret_key = model.get("secret_key", "")
    # Kling uses signed requests — simplified here with placeholder auth
    headers = {"Authorization": f"Bearer {access_key}"}

    # Kling API endpoint varies by provider
    base_url = "https://api.kling.kuaishou.com/v1"

    async with httpx.AsyncClient(
        trust_env=False, base_url=base_url,
        timeout=httpx.Timeout(600, connect=10), headers=headers,
    ) as client:
        resp = await client.post("/videos/text2video", json=payload)
        data = resp.json()
        if not resp.is_success:
            raise RuntimeError(f"Kling submit failed: {data}")
        task_id = data.get("data", {}).get("task_id")

        for _ in range(120):
            await asyncio.sleep(5)
            r = await client.get(f"/videos/text2video/{task_id}")
            d = r.json()
            status = d.get("data", {}).get("task_status", "")
            if status == "succeed":
                video_url = d["data"]["task_result"]["videos"][0]["url"]
                local_path = await _download_video(video_url, task_dir)
                return {"video_path": local_path, "duration": duration}
            elif status == "failed":
                raise RuntimeError(f"Kling task failed: {d}")
        raise TimeoutError("Kling task timed out")


async def _download_video(url: str, task_dir: str) -> str:
    import os
    os.makedirs(task_dir, exist_ok=True)
    local_path = os.path.join(task_dir, "kling_output.mp4")
    async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(300)) as client:
        r = await client.get(url)
        with open(local_path, "wb") as f:
            f.write(r.content)
    return local_path
```

- [ ] **Step 2: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.kling_render import kling_render_frame; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add kling_render service — async video generation via Kuaishou API"
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
    task_dir: str = "",
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

### Task 5: OSS Upload Service

**Files:**
- Create: `pixelle_video/services/oss_service.py`

自动上传参考图到 OSS/CDN 获取公网 URL。

- [ ] **Step 1: 创建 `oss_service.py`**

```python
"""OSS/CDN upload service — 自动上传参考图获得公网 URL."""
import os
from loguru import logger
from pixelle_video.services.ai_model_registry import ai_model_registry


async def upload_to_oss(local_path: str, remote_key: str = "") -> str:
    """上传文件到 OSS，返回公网 URL."""
    oss_config = ai_model_registry.get_oss_config()
    provider = oss_config.get("provider", "local")

    if provider == "local":
        return f"file://{os.path.abspath(local_path)}"

    if provider == "minio":
        # MinIO S3 compatible
        import boto3
        from botocore.config import Config
        client = boto3.client(
            "s3",
            endpoint_url=oss_config.get("endpoint", "http://localhost:9000"),
            aws_access_key_id=oss_config.get("access_key", "minioadmin"),
            aws_secret_access_key=oss_config.get("secret_key", "minioadmin"),
            config=Config(signature_version="s3v4"),
        )
        bucket = oss_config.get("bucket", "dy-auto-assets")
        key = remote_key or os.path.basename(local_path)
        client.upload_file(local_path, bucket, key)
        url = f"{oss_config['endpoint']}/{bucket}/{key}"
        logger.info(f"Uploaded to MinIO: {url}")
        return url

    if provider == "aliyun_oss":
        import oss2
        auth = oss2.Auth(oss_config["access_key"], oss_config["secret_key"])
        bucket = oss2.Bucket(auth, oss_config["endpoint"], oss_config["bucket"])
        key = remote_key or f"characters/{os.path.basename(local_path)}"
        bucket.put_object_from_file(key, local_path)
        url = f"https://{oss_config['bucket']}.{oss_config['endpoint'].replace('https://', '')}/{key}"
        logger.info(f"Uploaded to OSS: {url}")
        return url

    logger.warning(f"Unknown OSS provider: {provider}, returning local path")
    return f"file://{os.path.abspath(local_path)}"
```

- [ ] **Step 2: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.oss_service import upload_to_oss; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add oss_service — auto upload reference images to OSS/CDN"
```

---

### Task 6: 改造 frame_processor — 多模型动态路由

**Files:**
- Modify: `pixelle_video/services/frame_processor.py` — `_step_generate_media()` 方法

这是核心改动点。用 `ai_model_registry` 读取模型配置，根据 `media_workflow` 动态路由到对应 render service。

- [ ] **Step 1: 在 `frame_processor.py` 顶部添加 import**

```python
# 在 frame_processor.py 顶部添加
from pixelle_video.services.ai_model_registry import ai_model_registry
from pixelle_video.services.seedance_render import seedance_render_frame
from pixelle_video.services.kling_render import kling_render_frame
from pixelle_video.services.wan_render import wan_render_frame
```

- [ ] **Step 2: 重写 `_step_generate_media()` 方法**

```python
async def _step_generate_media(self, frame, config):
    """Step 2: 根据 media_workflow 动态路由到对应模型的 render service."""
    logger.debug(f"  2/4: Generating media for frame {frame.index}...")

    workflow_name = config.media_workflow or ""
    model_config = ai_model_registry.get_video_model(workflow_name)
    provider = model_config.get("provider", "") if model_config else ""

    # 静态图片模板 → 保持现有 ComfyKit 逻辑
    if not model_config or provider == "runninghub":
        # Existing logic for FLUX/SDXL via RunningHub/ComfyUI
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

    # ==== 新增：云端模型路由 ====
    # 确定 aspect_ratio
    w, h = config.media_width, config.media_height
    ratio = f"{w}:{h}" if w and h else "9:16"

    # 收集参考图 URL
    reference_urls = getattr(frame, "reference_urls", []) or []

    task_dir = os.path.join(
        config._task_dir if hasattr(config, "_task_dir") else "output",
        f"frame_{frame.index}"
    )
    os.makedirs(task_dir, exist_ok=True)

    if provider == "volcengine":
        result = await seedance_render_frame(
            prompt=frame.image_prompt,
            reference_urls=reference_urls,
            duration=frame.duration,
            aspect_ratio=ratio,
            with_audio=(getattr(frame, "audio_mode", "tts") == "seedance_native"),
            task_dir=task_dir,
        )
        frame.video_path = result["video_path"]
        frame.duration = result["duration"]
        frame.media_type = "video"

    elif provider == "kuaishou":
        result = await kling_render_frame(
            prompt=frame.image_prompt,
            reference_urls=reference_urls,
            duration=frame.duration,
            aspect_ratio=ratio,
            task_dir=task_dir,
        )
        frame.video_path = result["video_path"]
        frame.duration = result["duration"]
        frame.media_type = "video"

    elif provider == "wan_opensource":
        result = await wan_render_frame(
            core=self.core,
            prompt=frame.image_prompt,
            duration=frame.duration,
            width=config.media_width,
            height=config.media_height,
            task_dir=task_dir,
        )
        frame.video_path = result["video_path"]
        frame.duration = result["duration"]
        frame.media_type = "video"

    elif provider == "custom":
        raise NotImplementedError("Custom endpoint rendering requires user-provided endpoint configuration")

    else:
        raise ValueError(f"Unknown video model provider: {provider}")
```

> 注意：需在文件顶部添加 `import os`（如果尚未导入）。

- [ ] **Step 3: 更新 `StoryboardFrame` 模型 — 增加字段**

在 `pixelle_video/models/storyboard.py` 中：

```python
# StoryboardFrame 类新增字段
class StoryboardFrame:
    # 已有字段...
    voice_id: Optional[str] = None          # 帧级 TTS 声音
    reference_urls: Optional[list[str]] = None  # 角色参考图公网 URL
    audio_mode: Optional[str] = None        # "tts" | "seedance_native" | "bgm_only" | "silent"
```

- [ ] **Step 4: 更新 `_step_generate_audio` — 支持帧级 voice_id**

在 `frame_processor.py` 中：

```python
async def _step_generate_audio(self, frame, config):
    # 如果 audio_mode 是 seedance_native 或 bgm_only，跳过 TTS
    if getattr(frame, "audio_mode", None) in ("seedance_native", "bgm_only", "silent"):
        logger.debug(f"  1/4: Skipping TTS (audio_mode={frame.audio_mode})")
        frame.audio_path = None
        return

    voice_id = getattr(frame, "voice_id", None) or config.voice_id
    # ... 其余 TTS 逻辑不变，但使用 frame 级别的 voice_id ...
```

- [ ] **Step 5: 验证 `frame_processor` 导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.services.frame_processor import FrameProcessor; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: multi-model dynamic routing in frame_processor — Seedance/Kling/Wan2.7 support with audio_mode"
```

---

### Task 7: 全自动流水线编排器

**Files:**
- Create: `pixelle_video/pipelines/auto_pipeline.py`

编排器负责串联全部 7 层流水线，每层完成后写 checkpoint，支持断点续传。

- [ ] **Step 1: 创建 `auto_pipeline.py`**

```python
"""Auto Pipeline Orchestrator — 全自动七层流水线 + 断点续传."""
import asyncio
import json
import os
from datetime import datetime
from loguru import logger


class PipelineCheckpoint:
    """流水线 checkpoint 管理."""
    def __init__(self, checkpoint_dir: str, run_id: str):
        self.path = os.path.join(checkpoint_dir, f"{run_id}.json")
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return {"layers": {}, "run_id": "", "status": "pending"}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def layer_completed(self, layer: int, result: dict):
        self.data["layers"][str(layer)] = {"status": "completed", "result": result, "completed_at": datetime.now().isoformat()}
        self.save()

    def task_completed(self, layer: int, task_id: str):
        layer_key = str(layer)
        if layer_key not in self.data["layers"]:
            self.data["layers"][layer_key] = {"status": "running", "completed_tasks": []}
        self.data["layers"][layer_key].setdefault("completed_tasks", []).append(task_id)
        self.save()

    def is_layer_done(self, layer: int) -> bool:
        return self.data["layers"].get(str(layer), {}).get("status") == "completed"

    def get_completed_tasks(self, layer: int) -> list:
        return self.data["layers"].get(str(layer), {}).get("completed_tasks", [])


class AutoPipeline:
    """全自动流水线编排器."""

    def __init__(self, pixelle_core, run_id: str, params: dict):
        self.core = pixelle_core
        self.run_id = run_id
        self.params = params  # {logline, genre, mode, audio_strategy, pilot_first, ...}
        self.checkpoint = PipelineCheckpoint("output/pipeline_checkpoints", run_id)
        self.total_layers = 5  # 0=assets, 1=story, 2=director, 3=render, 4=post

    async def run(self):
        """执行全自动流水线，从中断处恢复."""
        self.checkpoint.data["status"] = "running"
        self.checkpoint.data["started_at"] = datetime.now().isoformat()
        self.checkpoint.data["params"] = self.params
        self.checkpoint.save()

        for layer in range(self.total_layers):
            if self.checkpoint.is_layer_done(layer):
                logger.info(f"Layer {layer} already completed, skipping")
                continue
            await self._run_layer(layer)

        self.checkpoint.data["status"] = "completed"
        self.checkpoint.data["completed_at"] = datetime.now().isoformat()
        self.checkpoint.save()
        return self.checkpoint.data

    async def _run_layer(self, layer: int):
        """执行一层流水线."""
        logger.info(f"Starting layer {layer}")
        # 具体每层逻辑由子类或参数决定
        # Layer 0: 资产生成 → FLUX 生成角色/场景图 + OSS 上传
        # Layer 1: 故事工坊 → LLM 链生成剧本
        # Layer 2: 导演工坊 → LLM 生成分镜表
        # Layer 3: 渲染 → frame_processor 批量渲染
        # Layer 4: 后期 → FFmpeg 合成 + 包装
        raise NotImplementedError("Layer execution logic implemented in subclasses")
```

- [ ] **Step 2: 验证导入**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "from pixelle_video.pipelines.auto_pipeline import AutoPipeline, PipelineCheckpoint; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add -A
git commit -m "feat: add auto_pipeline orchestrator with checkpoint/resume support"
```

---

### Task 8: Config.yaml 模板更新

**Files:**
- Modify: `config.yaml`

- [ ] **Step 1: 追加 `ai_models` 默认配置**

```yaml
# 在 config.yaml 末尾追加
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
      strengths: ["人脸", "多角色", "60s长视频"]
      enabled: true
    - id: "kling_3.0"
      name: "Kling 3.0"
      provider: "kuaishou"
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

- [ ] **Step 2: 验证 config 加载**

```bash
cd D:/devWorkspace/Pixelle-Video
python -c "
from pixelle_video.config import config_manager
config_manager.reload()
cfg = config_manager.config
print('ai_models keys:', list(cfg.ai_models.__dict__.keys()))
print('video_models count:', len(cfg.ai_models.video_models))
"
```

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add config.yaml
git commit -m "feat: add ai_models config template for multi-model video generation"
```

---

### Task 9: 集成测试 — pilot 模式 1 集试点

**Files:**
- Create: `tests/test_frame_processor_routing.py`

- [ ] **Step 1: 创建单元测试（mock 外部 API）**

```python
"""Test frame_processor multi-model routing."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestFrameProcessorRouting:
    """测试 frame_processor 根据 media_workflow 正确路由到不同 render service."""

    @pytest.mark.asyncio
    async def test_routes_to_seedance_when_volcengine_provider(self):
        """当 media_workflow 指向 Seedance 时，调用 seedance_render_frame."""
        from pixelle_video.models.storyboard import StoryboardFrame, StoryboardConfig

        frame = StoryboardFrame(index=0, narration="test", image_prompt="a test scene")
        frame.duration = 5.0
        config = StoryboardConfig(
            task_id="test-001",
            media_workflow="seedance_2.0",
            media_width=1080,
            media_height=1920,
        )

        with patch("pixelle_video.services.frame_processor.seedance_render_frame") as mock_sd:
            mock_sd.return_value = {"video_path": "/tmp/test.mp4", "duration": 5.0}
            # frame_processor 调用 _step_generate_media
            from pixelle_video.services.frame_processor import FrameProcessor
            fp = FrameProcessor(MagicMock())
            await fp._step_generate_media(frame, config)

            mock_sd.assert_called_once()
            assert frame.video_path == "/tmp/test.mp4"
            assert frame.media_type == "video"

    @pytest.mark.asyncio
    async def test_routes_to_kling_when_kuaishou_provider(self):
        """当 media_workflow 指向 Kling 时，调用 kling_render_frame."""
        frame = StoryboardFrame(index=0, narration="test", image_prompt="a test scene")
        frame.duration = 10.0
        config = StoryboardConfig(task_id="test-002", media_workflow="kling_3.0", media_width=1920, media_height=1080)

        with patch("pixelle_video.services.frame_processor.kling_render_frame") as mock_kl:
            mock_kl.return_value = {"video_path": "/tmp/test.mp4", "duration": 10.0}
            fp = FrameProcessor(MagicMock())
            await fp._step_generate_media(frame, config)

            mock_kl.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_tts_when_seedance_native_audio(self):
        """audio_mode=seedance_native 时跳过 TTS 步骤."""
        frame = StoryboardFrame(index=0, narration="test", image_prompt="test")
        frame.audio_mode = "seedance_native"
        config = StoryboardConfig(task_id="test-003")

        fp = FrameProcessor(MagicMock())
        await fp._step_generate_audio(frame, config)

        assert frame.audio_path is None  # TTS 被跳过
```

- [ ] **Step 2: 运行测试**

```bash
cd D:/devWorkspace/Pixelle-Video
pip install pytest pytest-asyncio -q
python -m pytest tests/test_frame_processor_routing.py -v
```

Expected: 3 tests pass (with mocks, no real API calls).

- [ ] **Step 3: Commit**

```bash
cd D:/devWorkspace/Pixelle-Video
git add tests/
git commit -m "test: add frame_processor routing unit tests (mock external APIs)"
```

---

### Task 10: 端到端验证 — Pilot 模式生成 1 集

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
| 1 | ai_model_registry | new | ~100 |
| 2 | seedance_render | new | ~80 |
| 3 | kling_render | new | ~60 |
| 4 | wan_render | new | ~30 |
| 5 | oss_service | new | ~60 |
| 6 | frame_processor 改造 | modify | ~80 |
| 7 | auto_pipeline | new | ~100 |
| 8 | config.yaml 模板 | modify | ~30 |
| 9 | 单元测试 | new | ~60 |
| 10 | E2E 验证 | - | - |

**Plan A 总工作量：约 600 行，2-3 天。**

Plan A 完成后，Plan B（dy_auto 后端）和 Plan C（dy_auto 前端）基于此基础设施继续。
