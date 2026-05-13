# dy_auto 后端 — 多模型系列生成系统 实施计划 (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans.

**Goal:** 在 dy_auto FastAPI 后端实现系列短剧管理、角色/场景资产库、七层流水线编排、AI 审图引擎、AI 模型配置中心。

**Architecture:** 新增 6 张 DB 表 (Character/Scene/Series/Episode/PipelineRun/AuditReport) + 6 个 router + 3 个 service。所有外部 API 调用通过 Pixelle-Video 透明代理。DB 迁移由 SQLAlchemy create_all 处理。

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0, httpx, Pydantic v2

**前置:** Plan A (Pixelle-Video 多模型渲染) 已完成

**与 Plan A 的关系:** Plan A 负责视频渲染层（frame_processor 路由 + Seedance/Kling 调用），Plan B 负责业务编排层（DB 模型 + API 路由 + 流水线状态机 + 审图 + 资产库）。

---

### Task 1: DB Models — 6 张新表

**Files:**
- Modify: `server/app/db_models.py`

在现有 Base 上新增 6 张表。遵循现有 Column/JSON/ForeignKey 模式。

- [ ] **Step 1: 新增 Character 表**

```python
class Character(Base):
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    role_type = Column(String(20), nullable=False, default="protagonist")  # protagonist/antagonist/supporting/cameo
    gender = Column(String(10), nullable=False, default="male")
    age_range = Column(String(20), nullable=True)
    personality = Column(Text, nullable=True)
    appearance_desc = Column(Text, nullable=True)         # 外观文字描述 → FLUX input
    outfit_desc = Column(Text, nullable=True)             # 服装描述
    avatar_front_url = Column(Text, nullable=True)        # FLUX 生成 → OSS 上传后的公网 URL
    avatar_side_url = Column(Text, nullable=True)
    avatar_threequarter_url = Column(Text, nullable=True)
    avatar_fullbody_url = Column(Text, nullable=True)
    default_voice_id = Column(String(100), nullable=True)  # Edge-TTS voice ID
    meta_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
```

- [ ] **Step 2: 新增 Scene 表**

```python
class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    scene_type = Column(String(20), nullable=False, default="indoor")  # indoor/outdoor/transition/special
    location_desc = Column(Text, nullable=True)                        # 地点描述
    lighting = Column(String(50), nullable=True)                       # 白天/黄昏/夜晚/室内暖光
    mood = Column(String(50), nullable=True)                           # 温馨/紧张/浪漫/悬疑
    reference_wideshot_url = Column(Text, nullable=True)               # 广角参考图 URL
    reference_midshot_url = Column(Text, nullable=True)                # 中景参考图 URL
    reference_aerial_url = Column(Text, nullable=True)                 # 俯拍参考图 URL
    meta_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
```

- [ ] **Step 3: 新增 Series + Episode + M2M 关联表**

```python
class Series(Base):
    __tablename__ = "series"

    id = Column(String(36), primary_key=True, default=_uuid)
    title = Column(String(200), nullable=False)
    logline = Column(Text, nullable=True)
    genre = Column(String(50), nullable=False, default="drama")  # drama/romance/fantasy/suspense/scifi
    total_episodes = Column(Integer, nullable=False, default=30)
    target_duration = Column(Integer, nullable=False, default=90)  # seconds per episode
    mode = Column(String(20), nullable=False, default="step_by_step")  # step_by_step/fully_automatic
    pilot_first = Column(Boolean, nullable=False, default=True)
    story_bible_json = Column(JSON, nullable=True, default=dict)   # 故事圣经
    status = Column(String(20), nullable=False, default="draft")   # draft/assets_ready/script_ready/rendering/postproduction/done/failed
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    episodes = relationship("Episode", back_populates="series", order_by="Episode.episode_number")
    characters = relationship("Character", secondary="series_characters", backref="series")
    scenes = relationship("Scene", secondary="series_scenes", backref="series")


series_characters = Table("series_characters", Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("character_id", String(36), ForeignKey("characters.id"), primary_key=True),
)

series_scenes = Table("series_scenes", Base.metadata,
    Column("series_id", String(36), ForeignKey("series.id"), primary_key=True),
    Column("scene_id", String(36), ForeignKey("scenes.id"), primary_key=True),
)


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    script_json = Column(JSON, nullable=True, default=dict)       # LLM 生成的剧本
    storyboard_json = Column(JSON, nullable=True, default=dict)   # 导演工坊产出的分镜表
    video_url = Column(Text, nullable=True)                        # 最终 mp4 URL
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="pending") # pending/script_ready/storyboard_ready/rendering/audit/done/failed
    cost_so_far = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    series = relationship("Series", back_populates="episodes")
    __table_args__ = (UniqueConstraint("series_id", "episode_number"),)
```

- [ ] **Step 4: 新增 PipelineRun + AuditReport 表**

```python
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id"), nullable=True)  # NULL = 全系列执行
    mode = Column(String(20), nullable=False, default="step_by_step")
    layers_json = Column(JSON, nullable=True, default=dict)         # 每层状态+checkpoint
    current_layer = Column(Integer, nullable=False, default=0)      # 当前执行到第几层 (0-6)
    status = Column(String(20), nullable=False, default="pending")  # pending/running/paused/completed/failed
    error_log = Column(Text, nullable=True)
    actual_cost_so_far = Column(Float, nullable=True, default=0.0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class AuditReport(Base):
    __tablename__ = "audit_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    target_type = Column(String(20), nullable=False)    # character/scene/frame/video
    target_id = Column(String(36), nullable=False)       # character.id / episode.id
    image_url = Column(Text, nullable=False)
    auditor_model = Column(String(50), nullable=False)  # gemini-2.5-pro / gpt-4o
    score = Column(Float, nullable=False, default=0.0)   # 0-100
    pass_fail = Column(Boolean, nullable=False, default=False)
    issues_json = Column(JSON, nullable=True, default=list)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
```

- [ ] **Step 5: 验证建表 + Commit**

```bash
cd server
python -c "
from app.database import init_db; init_db()
from app.db_models import Character, Scene, Series, Episode, PipelineRun, AuditReport
print('All 6 new models imported OK')
"
```

```bash
git add server/app/db_models.py
git commit -m "feat: add 6 DB models — Character/Scene/Series/Episode/PipelineRun/AuditReport + M2M tables"
```

---

### Task 2: AI Model Config Router + System Setting 扩展

**Files:**
- Create: `server/app/routers/ai_config.py`
- Modify: `server/app/main.py` — 注册 router
- Modify: `server/app/db_models.py` — 扩展 SystemSetting (如需要)

提供 `/api/ai-config/models` 端点，前端可通过此 API 读取和修改 AI 模型配置。配置持久化到 system_settings 表。

- [ ] **Step 1: 创建 `ai_config.py` router**

```python
"""AI 模型配置中心 — CRUD 管理所有 AI 模型配置."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import SystemSetting
import json

router = APIRouter(prefix="/api/ai-config", tags=["ai-config"])

AI_CONFIG_KEYS = [
    "seedance_api_key", "kling_access_key", "kling_secret_key",
    "runninghub_api_key", "comfyui_url", "comfyui_api_key",
    "llm_provider", "llm_api_key", "llm_base_url", "llm_model",
    "oss_provider", "oss_endpoint", "oss_bucket", "oss_access_key", "oss_secret_key",
    "audit_model_multi", "audit_model_single", "audit_model_batch",
]

@router.get("/models")
def list_models(db: Session = Depends(get_db)):
    """读取所有 AI 配置. Sensitive fields masked."""
    rows = db.query(SystemSetting).filter(SystemSetting.key.in_(AI_CONFIG_KEYS)).all()
    result = {}
    for r in rows:
        val = r.value
        if "api_key" in r.key or "secret_key" in r.key:
            if val:
                val = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
        result[r.key] = val
    return {"ok": True, "models": result}

@router.put("/models")
def update_models(body: dict, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    """批量更新 AI 配置."""
    for key, value in body.items():
        if key not in AI_CONFIG_KEYS:
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(SystemSetting(key=key, value=str(value)))
    db.commit()
    return {"ok": True}
```

- [ ] **Step 2: 注册到 main.py**

```python
# server/app/main.py
from app.routers import ai_config
app.include_router(ai_config.router)
```

- [ ] **Step 3: Commit**

```bash
git add server/app/routers/ai_config.py server/app/main.py
git commit -m "feat: add ai_config router — CRUD for all AI model settings"
```

---

### Task 3: Character + Scene Router

**Files:**
- Create: `server/app/routers/characters.py`
- Create: `server/app/routers/scenes.py`
- Modify: `server/app/main.py` — 注册 routers

提供角色和场景的 CRUD API。角色支持 4 张参考图的 URL 管理。场景支持 3 种角度参考图。

- [ ] **Step 1: 创建 `characters.py` router**

```python
"""角色管理 API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Character
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/characters", tags=["characters"])

class CharacterCreate(BaseModel):
    name: str
    role_type: str = "protagonist"
    gender: str = "male"
    personality: Optional[str] = None
    appearance_desc: Optional[str] = None
    outfit_desc: Optional[str] = None
    default_voice_id: Optional[str] = None

@router.get("")
def list_characters(db: Session = Depends(get_db)):
    return {"ok": True, "characters": [c.__dict__ for c in db.query(Character).all()]}

@router.post("")
def create_character(body: CharacterCreate, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    c = Character(**body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "character": c.__dict__}

@router.put("/{character_id}")
def update_character(character_id: str, body: dict, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    c = db.query(Character).filter(Character.id == character_id).first()
    if not c: raise HTTPException(404, "Character not found")
    for k, v in body.items():
        if hasattr(c, k): setattr(c, k, v)
    db.commit()
    return {"ok": True}

@router.delete("/{character_id}")
def delete_character(character_id: str, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    db.query(Character).filter(Character.id == character_id).delete()
    db.commit()
    return {"ok": True}
```

- [ ] **Step 2: 创建 `scenes.py` router**

```python
"""场景管理 API — 结构同 characters.py，字段映射到 Scene 模型."""
# ... 与 characters.py 类似，省略重复代码 ...
```

- [ ] **Step 3: 注册 + Commit**

```bash
git add server/app/routers/characters.py server/app/routers/scenes.py server/app/main.py
git commit -m "feat: add character + scene CRUD routers"
```

---

### Task 4: Series + Episode Router

**Files:**
- Create: `server/app/routers/series.py`
- Modify: `server/app/main.py` — 注册 router

系列和剧集的完整 CRUD，含角色/场景关联 (M2M)、剧本存储、分镜存储。

- [ ] **Step 1: 创建 `series.py` router**

```python
"""系列 + 剧集管理 API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import Series, Episode, Character, Scene

router = APIRouter(prefix="/api/series", tags=["series"])

class SeriesCreate(BaseModel):
    title: str
    logline: Optional[str] = None
    genre: str = "drama"
    total_episodes: int = 30
    target_duration: int = 90
    mode: str = "step_by_step"
    pilot_first: bool = True

class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None

# === Series CRUD ===

@router.get("")
def list_series(db: Session = Depends(get_db)):
    all_series = db.query(Series).order_by(Series.updated_at.desc()).all()
    return {"ok": True, "series": [s.__dict__ for s in all_series]}

@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    s = Series(**body.model_dump())
    db.add(s)
    # 自动创建 episode 占位行
    for ep_num in range(1, body.total_episodes + 1):
        db.add(Episode(series_id=s.id, episode_number=ep_num, status="pending"))
    db.commit(); db.refresh(s)
    return {"ok": True, "series": s.__dict__}

@router.get("/{series_id}")
def get_series(series_id: str, db: Session = Depends(get_db)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s: raise HTTPException(404)
    episodes = db.query(Episode).filter(Episode.series_id == series_id).order_by(Episode.episode_number).all()
    return {"ok": True, "series": s.__dict__, "episodes": [e.__dict__ for e in episodes]}

# === Character/Scene 关联 ===

@router.post("/{series_id}/characters/{character_id}")
def link_character(series_id: str, character_id: str, db: Session = Depends(get_db)):
    s = db.query(Series).filter(Series.id == series_id).first()
    c = db.query(Character).filter(Character.id == character_id).first()
    if not s or not c: raise HTTPException(404)
    s.characters.append(c)
    db.commit()
    return {"ok": True}

@router.post("/{series_id}/scenes/{scene_id}")
def link_scene(series_id: str, scene_id: str, db: Session = Depends(get_db)):
    s = db.query(Series).filter(Series.id == series_id).first()
    sc = db.query(Scene).filter(Scene.id == scene_id).first()
    if not s or not sc: raise HTTPException(404)
    s.scenes.append(sc)
    db.commit()
    return {"ok": True}

# === Episode 管理 ===

@router.put("/{series_id}/episodes/{episode_id}")
def update_episode(series_id: str, episode_id: str, body: EpisodeUpdate, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    ep = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not ep: raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 2: 注册 + Commit**

```bash
git add server/app/routers/series.py server/app/main.py
git commit -m "feat: add series + episode CRUD with character/scene M2M linking"
```

---

### Task 5: Pipeline Service + Router

**Files:**
- Create: `server/app/services/pipeline_service.py`
- Create: `server/app/routers/pipeline.py`
- Modify: `server/app/main.py` — 注册 router

七层流水线编排器。管理 PipelineRun 表，支持断点续传。通过 `httpx` 调用 Pixelle-Video API 执行各层任务。

- [ ] **Step 1: 创建 `pipeline_service.py`**

```python
"""Pipeline Orchestrator — 七层流水线引擎."""
import httpx
from loguru import logger
from sqlalchemy.orm import Session
from app.db_models import PipelineRun, Series, Episode

PIXELLE_URL = "http://127.0.0.1:8500"
LAYER_COUNT = 7

async def start_pipeline(db: Session, series_id: str, episode_id: str = None, mode: str = "step_by_step") -> PipelineRun:
    """创建新流水线运行实例."""
    run = PipelineRun(series_id=series_id, episode_id=episode_id, mode=mode, status="running")
    db.add(run); db.commit(); db.refresh(run)
    return run

async def execute_layer(db: Session, run: PipelineRun, layer: int):
    """执行单层流水线 (通过 Pixelle-Video API)."""
    # layers_json 结构: {layer_id: {status, result, completed_tasks}}
    layers = run.layers_json or {}
    layer_key = str(layer)
    if layers.get(layer_key, {}).get("status") == "completed":
        return  # 已完成，跳过

    async with httpx.AsyncClient(base_url=PIXELLE_URL, timeout=httpx.Timeout(600)) as client:
        # 各层对应 Pixelle-Video 的不同 API 端点
        if layer == 0:   # 资产生成
            resp = await client.post("/api/pipeline/assets/generate", json={
                "series_id": run.series_id
            })
        elif layer == 1: # 故事工坊
            resp = await client.post("/api/pipeline/story/generate", json={
                "series_id": run.series_id
            })
        elif layer == 2: # 导演工坊
            resp = await client.post("/api/pipeline/director/generate", json={
                "series_id": run.series_id, "episode_id": run.episode_id
            })
        elif layer == 3: # 渲染引擎
            resp = await client.post("/api/pipeline/render/execute", json={
                "series_id": run.series_id, "episode_id": run.episode_id
            })
        elif layer == 4: # 质量审计
            resp = await client.post("/api/pipeline/audit/execute", json={
                "series_id": run.series_id, "episode_id": run.episode_id
            })
        elif layer == 5: # 后期包装
            resp = await client.post("/api/pipeline/postproduction/execute", json={
                "series_id": run.series_id, "episode_id": run.episode_id
            })
        elif layer == 6: # 完成收尾
            resp = None

        if resp and not resp.is_success:
            raise RuntimeError(f"Layer {layer} failed: {resp.text}")

    # 更新 checkpoint
    layers[layer_key] = {"status": "completed", "completed_at": ...}
    run.layers_json = layers
    run.current_layer = layer
    db.commit()

async def resume_pipeline(db: Session, run_id: str):
    """从断点恢复流水线."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run or run.status not in ("pending", "running", "paused"):
        raise ValueError("PipelineRun not resumable")
    run.status = "running"; db.commit()
    for layer in range(run.current_layer, LAYER_COUNT):
        await execute_layer(db, run, layer)
    run.status = "completed"; db.commit()
```

- [ ] **Step 2: 创建 `pipeline.py` router**

```python
"""流水线 API — 启动/暂停/恢复/查询."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.services.pipeline_service import start_pipeline, resume_pipeline
from app.db_models import PipelineRun

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

@router.post("/start")
def pipeline_start(series_id: str, episode_id: str = None, mode: str = "step_by_step",
                   db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    run = await start_pipeline(db, series_id, episode_id, mode)
    return {"ok": True, "run_id": run.id}

@router.post("/resume/{run_id}")
def pipeline_resume(run_id: str, db: Session = Depends(get_db), _: str = Depends(verify_admin_token)):
    await resume_pipeline(db, run_id)
    return {"ok": True}

@router.get("/runs/{series_id}")
def list_runs(series_id: str, db: Session = Depends(get_db)):
    runs = db.query(PipelineRun).filter(PipelineRun.series_id == series_id).order_by(PipelineRun.created_at.desc()).all()
    return {"ok": True, "runs": [r.__dict__ for r in runs]}
```

- [ ] **Step 3: 注册 + Commit**

---

### Task 6: Audit Service (AI 审图引擎)

**Files:**
- Create: `server/app/services/audit_service.py`
- Create: `server/app/routers/audit.py`
- Modify: `server/app/main.py` — 注册 router

调用 Gemini/GPT-4o Vision 审图。三档审图节点 (multi_image_compare / single_image_detail / batch_quick_scan)，返回评分+问题列表。

- [ ] **Step 1: audit_service.py**

```python
"""AI Audit Engine — 多模态视觉审计."""
import httpx
from loguru import logger

AUDIT_PROMPTS = {
    "multi_image_compare": "Compare these images of the same character. Rate consistency 0-100...",
    "single_image_detail": "Evaluate this image for anatomical issues, artifacts, lighting..."
}

async def audit_image(image_url: str, reference_urls: list[str] = None, auditor_model: str = "gemini-2.5-pro") -> dict:
    """单张图审计 → {score, pass_fail, issues}"""
    # 通过 Pixelle-Video 代理调用 Gemini/GPT-4o Vision API
    ...
    return {"score": 85, "pass_fail": True, "issues": []}

async def audit_batch(image_urls: list[str], auditor_model: str = "gemini-2.5-flash") -> list[dict]:
    """批量快速扫描 → [{score, pass_fail, issues}]"""
    ...
```

- [ ] **Step 2: 注册 + Commit**

---

### Task 7: 注册所有新 router 到 main.py

- [ ] **Step 1: 补充 main.py 的 router 注册**

```python
from app.routers import characters, scenes, series, pipeline, audit, ai_config

app.include_router(characters.router)
app.include_router(scenes.router)
app.include_router(series.router)
app.include_router(pipeline.router)
app.include_router(audit.router)
app.include_router(ai_config.router)
```

---

## Plan B 总结

| Task | 内容 | 文件 | 行数 |
|------|------|------|------|
| 1 | DB Models (6 tables) | modify | ~160 |
| 2 | AI Config Router | new + modify | ~80 |
| 3 | Character + Scene Router | new + modify | ~140 |
| 4 | Series + Episode Router | new + modify | ~120 |
| 5 | Pipeline Service + Router | new + new + modify | ~180 |
| 6 | Audit Service + Router | new + new + modify | ~100 |
| 7 | main.py 注册 | modify | ~10 |

**Plan B 总工作量：约 790 行，2-3 天。**

Plan B 完成后，Plan C（前端）基于此 API 构建 UI。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | — | — | 0 | — | — |
| CEO Review | — | — | 0 | — | — |
| Design Review | — | — | 0 | — | — |
| Codex Review | — | — | 0 | — | — |

**VERDICT:** NO REVIEWS YET — run `/autoplan` or `/plan-eng-review` after Plan C is written.
