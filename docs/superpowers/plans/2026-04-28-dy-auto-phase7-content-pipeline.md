# Phase 7: Content Template Pipeline Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the content template pipeline end-to-end — admin creates templates, assigns to tasks, server generates AI content at task creation time, device handlers use pre-generated content for comments/DMs/replies.

**Architecture:** Server resolves `content_template_id` and generates content **when the task is created** (not at dispatch time). Content is stored in `task.params.content`. The poll endpoint stays unchanged. Device handlers consume `params.content` directly. A device-facing `/api/device/generate-content` endpoint exists for on-demand generation but is not part of the main pipeline.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / AutoJS6 (JavaScript) / httpx

---

## Problem Statement

Phase 6 added content templates, sensitive word filtering, and AI content generation on the server side. The web UI allows admins to:
1. Create content templates with `{variable}` placeholders
2. Select a template when creating a task (stored as `content_template_id` in `params`)

**But the pipeline is broken:** When the device receives a task with `content_template_id`, there's no code to:
- Resolve the template to actual content
- Call the AI generator
- Inject `content` into `params` for handlers to use

Device handlers (search-comment, search-dm, reply-comment) all expect `params.content` — a ready-to-use string. Without it, they either fail or skip the interaction.

## Architecture Decision: Generate at Creation Time

**Why creation time, not dispatch time (poll)?**

Generating content at task creation eliminates three critical bugs:
1. **Device HTTP timeout** — The device's `_requestWithRetry` has a 10s default timeout. AI generation taking 5-30s would trigger timeouts, causing the device to retry poll requests.
2. **Task claiming death spiral** — `get_pending_task` claims the task as RUNNING before AI generation. If AI fails, the handler fails, the task re-queues, and after 3 retries it permanently fails. A transient AI outage kills every content-dependent task.
3. **Device fallback is not a fallback** — If server-side AI fails, the device hitting the same endpoint fails for the same reasons. It's a retry with extra latency.

**Tradeoff:** Content goes stale if the task sits in queue. For comments and DMs, this is irrelevant — the content is still valid minutes or hours later.

## File Structure

```
server/
├── app/
│   ├── routers/
│   │   ├── tasks.py              # Modify: resolve template at task creation
│   │   └── device.py             # Modify: add /generate-content endpoint
│   └── services/
│       └── content_service.py    # Modify: add generate_from_template shared helper
│
├── tests/
│   ├── test_device_api.py        # Modify: add generate-content tests
│   └── test_tasks_api.py         # Modify: add template resolution tests
```

No device-side changes needed. Handlers already expect `params.content`.

---

## Task 1: Shared Helper + _build_prompt Fix

**Files:**
- Modify: `server/app/services/content_service.py`
- Modify: `server/app/services/ai_generator.py`
- Test: `server/tests/test_content_service.py`

- [ ] **Step 1: Write failing tests for generate_from_template**

Add to `server/tests/test_content_service.py`:

```python
class TestGenerateFromTemplate:
    """Tests for ContentService.generate_from_template shared helper."""

    def test_generates_content_from_template(self, db):
        """Happy path: template + context → generated content."""
        from unittest.mock import patch, AsyncMock
        tpl = content_service.create_template(
            db, name="gen-test", body="关于{keyword}的评论",
            category="comment", variables=["keyword"],
        )
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch.object(content_service, "_generate_content", new_callable=AsyncMock, return_value="好内容"):
            import asyncio
            result = asyncio.run(content_service.generate_from_template(
                db, tpl.id, {"keyword": "美食"},
            ))
            assert result == "好内容"

    def test_template_not_found_raises(self, db):
        """Raises ValueError when template doesn't exist."""
        import asyncio
        with pytest.raises(ValueError, match="Template not found"):
            asyncio.run(content_service.generate_from_template(db, "nonexistent", {}))

    def test_substitutes_variables_before_generation(self, db):
        """Variables are substituted before passing to AI."""
        from unittest.mock import patch, AsyncMock
        tpl = content_service.create_template(
            db, name="subst-test", body="{keyword}很好吃",
            category="comment", variables=["keyword"],
        )
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch.object(content_service, "_generate_content", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "result"
            import asyncio
            asyncio.run(content_service.generate_from_template(
                db, tpl.id, {"keyword": "火锅"},
            ))
            # Verify the substituted body was passed to AI
            call_args = mock_gen.call_args
            assert "火锅很好吃" in call_args[0][1]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_content_service.py::TestGenerateFromTemplate -v
```

Expected: FAIL — method doesn't exist yet.

- [ ] **Step 3: Make _build_prompt dynamic**

The current `_build_prompt` in `ai_generator.py` has hardcoded `keyword`, `username`, `video_title` fields. Templates with different variables (e.g., `{product_name}`) get no context in the prompt.

Replace the static `_build_prompt` method:

```python
@staticmethod
def _build_prompt(template_body: str, context: dict[str, Any]) -> str:
    """Build the user prompt from template and context.

    Dynamically includes all context keys that have values,
    rather than hardcoding specific field names.
    """
    parts = [f"模板内容：{template_body}"]

    # Dynamic context — include all non-empty string values
    key_labels = {
        "keyword": "搜索关键词",
        "username": "目标用户",
        "video_title": "视频标题",
    }
    for key, value in context.items():
        if isinstance(value, str) and value:
            label = key_labels.get(key, key)
            parts.append(f"{label}：{value}")

    parts.append("请根据以上信息生成一条自然的评论/私信内容。只输出内容本身。")
    return "\n".join(parts)
```

- [ ] **Step 4: Implement generate_from_template shared helper**

Add to `server/app/services/content_service.py`:

```python
async def generate_from_template(
    self, db: Session, template_id: str, context: dict[str, str],
) -> str:
    """Generate content from a template. Shared by admin, device, and poll resolution.

    Args:
        db: Database session
        template_id: Content template ID
        context: Variable values for substitution (e.g., {"keyword": "美食"})

    Returns:
        Generated content string

    Raises:
        ValueError: If template not found
        RuntimeError: If AI API not configured or all retries fail
    """
    tpl = self.get_template(db, template_id)
    if not tpl:
        raise ValueError(f"Template {template_id} not found")

    substituted = self.substitute_variables(tpl.body, context)

    from app.services.ai_generator import ai_generator
    return await ai_generator.generate(db, substituted, context)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_content_service.py::TestGenerateFromTemplate -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add server/app/services/content_service.py server/app/services/ai_generator.py server/tests/test_content_service.py
git commit -m "feat: add shared generate_from_template helper + dynamic _build_prompt"
```

---

## Task 2: Resolve Template at Task Creation

**Files:**
- Modify: `server/app/routers/tasks.py`
- Modify: `server/app/models.py` (reuse existing models)
- Test: `server/tests/test_tasks_api.py` (or `test_device_api.py`)

- [ ] **Step 1: Write failing tests for template resolution at creation**

Add to the appropriate test file:

```python
class TestTaskCreationWithTemplate:
    """Tests for template resolution during task creation."""

    def test_create_task_with_template_resolves_content(self, db):
        """Task created with content_template_id gets content injected."""
        from app.services.content_service import content_service
        from unittest.mock import patch, AsyncMock

        tpl = content_service.create_template(
            db, name="create-test", body="关于{keyword}的评论",
            category="comment", variables=["keyword"],
        )

        with patch("app.services.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock, return_value="AI生成的评论"):
            resp = client.post("/api/tasks", json={
                "type": "search_comment",
                "account_id": "acc-001",
                "params": {
                    "keyword": "美食",
                    "count": 3,
                    "content_template_id": tpl.id,
                },
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["params"]["content"] == "AI生成的评论"
            assert "content_template_id" in data["params"]  # preserved for reference

    def test_create_task_without_template_unchanged(self):
        """Task without content_template_id keeps params as-is."""
        resp = client.post("/api/tasks", json={
            "type": "search_comment",
            "account_id": "acc-001",
            "params": {"keyword": "美食", "count": 3, "content": "静态内容"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["params"]["content"] == "静态内容"

    def test_create_task_template_not_found_stores_without_content(self, db):
        """If template doesn't exist, task is created without content (no crash)."""
        resp = client.post("/api/tasks", json={
            "type": "search_comment",
            "account_id": "acc-001",
            "params": {
                "keyword": "美食",
                "content_template_id": "nonexistent-template",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" not in data["params"] or data["params"]["content"] is None

    def test_create_task_ai_failure_stores_without_content(self, db):
        """If AI generation fails, task is created without content (no crash)."""
        from app.services.content_service import content_service
        from unittest.mock import patch, AsyncMock

        tpl = content_service.create_template(
            db, name="fail-test", body="测试内容",
            category="comment",
        )

        with patch("app.services.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock, side_effect=RuntimeError("AI API failed")):
            resp = client.post("/api/tasks", json={
                "type": "search_comment",
                "account_id": "acc-001",
                "params": {"keyword": "美食", "content_template_id": tpl.id},
            })
            assert resp.status_code == 200  # task still created
            data = resp.json()
            assert "content" not in data["params"] or data["params"]["content"] is None

    def test_nurture_task_skips_template_resolution(self, db):
        """Nurture tasks don't use content — skip AI generation."""
        from app.services.content_service import content_service
        from unittest.mock import patch, AsyncMock

        tpl = content_service.create_template(
            db, name="nurture-test", body="不相关",
            category="comment",
        )

        with patch("app.services.content_service.ContentService.generate_from_template",
                    new_callable=AsyncMock) as mock_gen:
            resp = client.post("/api/tasks", json={
                "type": "nurture",
                "account_id": "acc-001",
                "params": {"duration": 30, "content_template_id": tpl.id},
            })
            assert resp.status_code == 200
            mock_gen.assert_not_called()  # AI never called for nurture tasks
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_tasks_api.py::TestTaskCreationWithTemplate -v
```

Expected: FAIL — resolution logic doesn't exist yet.

- [ ] **Step 3: Implement template resolution in task creation**

Add a helper function and modify `create_task` in `server/app/routers/tasks.py`:

```python
"""Task management API -- create, list, get tasks."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TaskCreateRequest, TaskStatus
from app.database import get_db
from app.deps import verify_admin_token
from app.services.task_service import task_service

logger = logging.getLogger(__name__)

# Task types that use content (comments, DMs, replies)
CONTENT_TASK_TYPES = {"search_comment", "search_dm", "reply_comment"}

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _maybe_resolve_template(db: Session, params: dict, task_type: str) -> dict:
    """If task has content_template_id and is a content-using type, generate content.

    On any failure, returns params unchanged (task created without content).
    """
    template_id = params.get("content_template_id")
    if not template_id:
        return params

    if task_type not in CONTENT_TASK_TYPES:
        return params

    try:
        from app.services.content_service import content_service
        context = {k: v for k, v in params.items()
                   if k not in ("content_template_id", "content", "count") and isinstance(v, str)}
        content = await content_service.generate_from_template(db, template_id, context)
        params["content"] = content
    except Exception as e:
        logger.warning("Failed to resolve template %s at task creation: %s", template_id, e)
        # Task created without content — handler will fail gracefully

    return params


@router.post("")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    params = await _maybe_resolve_template(db, dict(request.params), request.type.value)
    task = task_service.create_task(
        db=db,
        task_type=request.type,
        account_id=request.account_id,
        params=params,
        scheduled_at=request.scheduled_at,
    )
    return task
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_tasks_api.py::TestTaskCreationWithTemplate -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/tasks.py
git commit -m "feat(server): resolve content templates at task creation time"
```

---

## Task 3: Device Content Generation Endpoint (On-Demand)

**Files:**
- Modify: `server/app/routers/device.py`
- Modify: `server/app/models.py`
- Test: `server/tests/test_device_api.py`

This endpoint is for on-demand use (e.g., device wants to generate fresh content), not part of the main pipeline.

- [ ] **Step 1: Write failing tests**

Add to `server/tests/test_device_api.py`:

```python
class TestGenerateContent:
    """Tests for POST /api/device/generate-content."""

    def test_generate_content_no_template(self):
        """Returns 404 when template doesn't exist."""
        resp = client.post("/api/device/generate-content", json={
            "template_id": "nonexistent",
            "context": {"keyword": "test"},
        }, headers=HEADERS)
        assert resp.status_code == 404

    def test_generate_content_no_api_key(self, db):
        """Returns 503 when AI_API_KEY is not set."""
        from app.services.content_service import content_service
        tpl = content_service.create_template(
            db, name="gen-test", body="关于{keyword}的评论",
            category="comment", variables=["keyword"],
        )
        resp = client.post("/api/device/generate-content", json={
            "template_id": tpl.id,
            "context": {"keyword": "美食"},
        }, headers=HEADERS)
        assert resp.status_code == 503

    def test_generate_content_requires_device_auth(self, real_auth):
        """Device endpoint requires device secret."""
        resp = client.post("/api/device/generate-content", json={
            "template_id": "any",
            "context": {},
        })
        assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Add Pydantic models**

Add to `server/app/models.py`:

```python
class DeviceGenerateRequest(BaseModel):
    template_id: str
    context: dict[str, str] = Field(default_factory=dict)


class DeviceGenerateResponse(BaseModel):
    content: str
    template_id: str
```

- [ ] **Step 3: Implement endpoint using shared helper**

Add to `server/app/routers/device.py`:

```python
@router.post("/generate-content")
async def generate_content(
    request: DeviceGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Generate content from a template on-demand."""
    from app.services.content_service import content_service

    try:
        content = await content_service.generate_from_template(
            db, request.template_id, request.context,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Template not found")
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return DeviceGenerateResponse(content=content, template_id=request.template_id)
```

- [ ] **Step 4: Run tests**

```bash
cd server && python -m pytest tests/test_device_api.py::TestGenerateContent -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/device.py server/app/models.py server/tests/test_device_api.py
git commit -m "feat(server): add device-facing generate-content endpoint (on-demand)"
```

---

## Task 4: Run Full Test Suite and Verify

- [ ] **Step 1: Run all server tests**

```bash
cd server && python -m pytest tests/ -v --tb=short
```

Expected: All tests pass. No regressions.

- [ ] **Step 2: Final commit**

```bash
git add .
git commit -m "feat: complete content template pipeline — generate at creation + on-demand endpoint"
```

---

## Task Dependency Graph

```
Task 1 (Shared helper + _build_prompt fix)
  ├─> Task 2 (Resolve at task creation)
  └─> Task 3 (Device on-demand endpoint)
       └─> Task 4 (Full test suite)
```

Tasks 2 and 3 can be done in parallel after Task 1.

---

## Design Decisions

**Why generate at creation time instead of dispatch?**
- Poll endpoint stays fast (no AI latency)
- No task claiming death spiral (content is ready before task is queued)
- No device HTTP timeout issues
- No device fallback complexity
- Tradeoff: content goes stale if task sits in queue (irrelevant for comments/DMs)

**Why shared helper?**
- Three callers (admin endpoint, device endpoint, task creation) use the same 3-step logic
- Error handling differs per caller (HTTP errors vs. log+continue), but the core logic is shared
- `_build_prompt` is made dynamic to support arbitrary template variables

**Why task type filter?**
- `nurture` and `search_like` tasks don't use content
- Skipping AI generation for these types saves API calls and avoids unnecessary latency

**Why device endpoint is on-demand only?**
- Main pipeline generates content at task creation
- Device endpoint exists for edge cases (e.g., regenerating content, testing templates)
- Not part of the critical path

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 4 | CLEAR | 5 issues, 0 critical gaps |
| CEO Review | — | — | 0 | — | — |
| Design Review | — | — | 0 | — | — |
| Adversarial | — | — | 0 | — | — |
| Outside Voice | Claude subagent | Independent 2nd opinion | 1 | CLEAN | 10 findings, 3 critical |

- **OUTSIDE VOICE:** Found 3 critical issues the initial review missed: device HTTP timeout vs AI latency, task claiming death spiral, device fallback redundancy. Led to architecture change from dispatch-time to creation-time generation.
- **CROSS-MODEL TENSION:** Review chose "generate at dispatch" (poll endpoint). Outside voice argued "generate at creation" — user agreed with outside voice. Plan rewritten.
- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — ready to implement
