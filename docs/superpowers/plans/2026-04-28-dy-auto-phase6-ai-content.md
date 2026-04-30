# Phase 6: AI 内容集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add content templates, AI-powered content generation, and sensitive word filtering so admins can manage reusable templates and auto-generate comments/DMs/replies.

**Architecture:** New `ContentTemplate` and `SensitiveWord` ORM models feed into a `ContentService` (CRUD + variable substitution) and `AiGeneratorService` (AI API call + sensitive word filtering + retry). A single `/api/content` router exposes template CRUD, sensitive word CRUD, and `POST /api/content/generate` for on-demand AI generation. The Vue frontend gets a new "内容管理" page with template editor, sensitive word list, and AI generation dialog integrated into the task creation flow.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, httpx (for AI API calls), Vue 3, Pinia, Headless UI, Tailwind CSS

---

## File Structure

### Backend — New Files
- `server/app/services/content_service.py` — ContentTemplate CRUD, SensitiveWord CRUD, variable substitution
- `server/app/services/ai_generator.py` — AI API integration, sensitive word filtering, retry logic
- `server/app/routers/content.py` — REST endpoints: templates, sensitive words, generate
- `server/config/sensitive_words.yaml` — Default sensitive word seed data

### Backend — Modified Files
- `server/app/db_models.py` — Add `ContentTemplate` and `SensitiveWord` ORM models
- `server/app/models.py` — Add Pydantic request/response models
- `server/app/main.py` — Mount content router
- `server/app/config.py` — Add `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` config vars
- `server/app/seed.py` — Add `seed_sensitive_words()` function

### Frontend — New Files
- `web/src/api/content.js` — API client for templates, sensitive words, generate
- `web/src/views/ContentPage.vue` — Template editor, sensitive word manager, AI generate dialog

### Frontend — Modified Files
- `web/src/router/index.js` — Add `/content` route
- `web/src/views/AdminLayout.vue` — Add "内容管理" nav item
- `web/src/views/TasksPage.vue` — Add template selector in create task dialog

### Test Files
- `server/tests/test_content_service.py` — Unit tests for content service
- `server/tests/test_content_api.py` — Integration tests for content API endpoints

---

## Task 1: Database Models — ContentTemplate + SensitiveWord

**Files:**
- Modify: `server/app/db_models.py:1-97` (add two new model classes after `DailyStats`)
- Test: `server/tests/test_content_api.py` (created in Task 5)

- [ ] **Step 1: Add ContentTemplate model to db_models.py**

Add after the `DailyStats` class (after line 97):

```python
class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="comment")  # comment, dm, reply
    body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)  # ["keyword", "username", "video_title"]
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(String(36), primary_key=True, default=_uuid)
    word = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 2: Verify the models load without import errors**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -c "from app.db_models import ContentTemplate, SensitiveWord; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Verify tables are created in test DB**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -c "from app.database import init_db; init_db(); print('Tables created')"`
Expected: `Tables created` (no errors about missing tables)

- [ ] **Step 4: Commit**

```bash
git add server/app/db_models.py
git commit -m "feat: add ContentTemplate and SensitiveWord ORM models"
```

---

## Task 2: Pydantic Models — Request/Response Schemas

**Files:**
- Modify: `server/app/models.py:1-120` (add new models at the end)

- [ ] **Step 1: Add ContentTemplate Pydantic models**

Append to the end of `server/app/models.py`:

```python
class ContentTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="comment", pattern="^(comment|dm|reply)$")
    body: str = Field(..., min_length=1)
    variables: list[str] = Field(default_factory=list)


class ContentTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, pattern="^(comment|dm|reply)$")
    body: Optional[str] = Field(None, min_length=1)
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ContentTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    body: str
    variables: list[str]
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SensitiveWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)


class SensitiveWordResponse(BaseModel):
    id: str
    word: str
    created_at: Optional[datetime] = None


class GenerateRequest(BaseModel):
    template_id: str
    context: dict[str, Any] = Field(default_factory=dict)  # {"keyword": "...", "username": "...", "video_title": "..."}


class GenerateResponse(BaseModel):
    content: str
    template_id: str
```

- [ ] **Step 2: Verify imports work**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -c "from app.models import ContentTemplateCreate, SensitiveWordCreate, GenerateRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/app/models.py
git commit -m "feat: add Pydantic models for content templates and AI generation"
```

---

## Task 3: Content Service — Template CRUD + Sensitive Word CRUD + Variable Substitution

**Files:**
- Create: `server/app/services/content_service.py`
- Create: `server/tests/test_content_service.py`

- [ ] **Step 1: Write tests for ContentTemplate CRUD**

Create `server/tests/test_content_service.py`:

```python
"""Tests for content service — template CRUD, sensitive word CRUD, variable substitution."""
import pytest
from app.services.content_service import content_service


class TestTemplateCRUD:
    def test_create_template(self, db):
        tpl = content_service.create_template(
            db, name="test-tpl", category="comment",
            body="Nice video about {keyword}!", variables=["keyword"]
        )
        assert tpl.id
        assert tpl.name == "test-tpl"
        assert tpl.category == "comment"
        assert tpl.body == "Nice video about {keyword}!"
        assert tpl.variables == ["keyword"]
        assert tpl.is_active is True

    def test_list_templates(self, db):
        content_service.create_template(db, name="t1", category="comment", body="b1")
        content_service.create_template(db, name="t2", category="dm", body="b2")
        templates, total = content_service.list_templates(db)
        assert total >= 2
        names = [t.name for t in templates]
        assert "t1" in names
        assert "t2" in names

    def test_list_templates_filter_category(self, db):
        content_service.create_template(db, name="c1", category="comment", body="b1")
        content_service.create_template(db, name="d1", category="dm", body="b2")
        templates, total = content_service.list_templates(db, category="comment")
        for t in templates:
            assert t.category == "comment"

    def test_get_template(self, db):
        tpl = content_service.create_template(db, name="get-me", category="reply", body="body")
        fetched = content_service.get_template(db, tpl.id)
        assert fetched is not None
        assert fetched.name == "get-me"

    def test_get_template_not_found(self, db):
        assert content_service.get_template(db, "nonexistent-id") is None

    def test_update_template(self, db):
        tpl = content_service.create_template(db, name="old", category="comment", body="old body")
        updated = content_service.update_template(db, tpl.id, name="new", body="new body")
        assert updated.name == "new"
        assert updated.body == "new body"

    def test_delete_template(self, db):
        tpl = content_service.create_template(db, name="delete-me", category="comment", body="body")
        result = content_service.delete_template(db, tpl.id)
        assert result is True
        assert content_service.get_template(db, tpl.id) is None

    def test_delete_template_not_found(self, db):
        assert content_service.delete_template(db, "nonexistent-id") is False


class TestSensitiveWordCRUD:
    def test_add_word(self, db):
        word = content_service.add_sensitive_word(db, "赌博")
        assert word.id
        assert word.word == "赌博"

    def test_add_duplicate_word(self, db):
        content_service.add_sensitive_word(db, "违禁词")
        with pytest.raises(ValueError, match="already exists"):
            content_service.add_sensitive_word(db, "违禁词")

    def test_list_words(self, db):
        content_service.add_sensitive_word(db, "word_a")
        content_service.add_sensitive_word(db, "word_b")
        words, total = content_service.list_sensitive_words(db)
        ws = [w.word for w in words]
        assert "word_a" in ws
        assert "word_b" in ws

    def test_delete_word(self, db):
        word = content_service.add_sensitive_word(db, "delete-word")
        result = content_service.delete_sensitive_word(db, word.id)
        assert result is True

    def test_contains_sensitive(self, db):
        content_service.add_sensitive_word(db, "赌博")
        assert content_service.contains_sensitive(db, "这个网站可以赌博赚钱") is True
        assert content_service.contains_sensitive(db, "正常评论内容") is False


class TestVariableSubstitution:
    def test_substitute_variables(self):
        body = "关于{keyword}的视频，作者{username}"
        context = {"keyword": "美食", "username": "小明"}
        result = content_service.substitute_variables(body, context)
        assert result == "关于美食的视频，作者小明"

    def test_substitute_missing_variable(self):
        body = "关于{keyword}的视频"
        context = {}  # keyword not provided
        result = content_service.substitute_variables(body, context)
        assert result == "关于{keyword}的视频"  # unchanged when missing

    def test_substitute_no_variables(self):
        body = "固定文本内容"
        result = content_service.substitute_variables(body, {"keyword": "test"})
        assert result == "固定文本内容"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -m pytest tests/test_content_service.py -v 2>&1 | head -30`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.content_service'`

- [ ] **Step 3: Implement ContentService**

Create `server/app/services/content_service.py`:

```python
"""Content template and sensitive word service — DB-backed."""
import re
import time
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db_models import ContentTemplate as DBTemplate, SensitiveWord as DBWord
from app.models import ContentTemplateResponse, SensitiveWordResponse

# Sensitive word cache TTL in seconds
_SENSITIVE_WORD_CACHE_TTL = 300  # 5 minutes


def _db_template_to_response(tpl: DBTemplate) -> ContentTemplateResponse:
    return ContentTemplateResponse(
        id=tpl.id,
        name=tpl.name,
        category=tpl.category,
        body=tpl.body,
        variables=tpl.variables or [],
        is_active=tpl.is_active,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


def _db_word_to_response(word: DBWord) -> SensitiveWordResponse:
    return SensitiveWordResponse(
        id=word.id,
        word=word.word,
        created_at=word.created_at,
    )


class ContentService:
    """Content template and sensitive word management."""

    def __init__(self):
        self._sensitive_words_cache: list[str] | None = None
        self._sensitive_words_cache_time: float = 0

    def _get_sensitive_words(self, db: Session) -> list[str]:
        """Get sensitive words with in-memory cache (5 min TTL)."""
        now = time.monotonic()
        if self._sensitive_words_cache is not None and (now - self._sensitive_words_cache_time) < _SENSITIVE_WORD_CACHE_TTL:
            return self._sensitive_words_cache
        words = [w for (w,) in db.query(DBWord.word).all()]
        self._sensitive_words_cache = words
        self._sensitive_words_cache_time = now
        return words

    def invalidate_sensitive_word_cache(self):
        """Call after adding/removing sensitive words to force refresh."""
        self._sensitive_words_cache = None

    # --- Template CRUD ---

    def create_template(
        self, db: Session, name: str, category: str = "comment",
        body: str = "", variables: list[str] | None = None,
    ) -> ContentTemplateResponse:
        tpl = DBTemplate(
            name=name,
            category=category,
            body=body,
            variables=variables or [],
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return _db_template_to_response(tpl)

    def get_template(self, db: Session, template_id: str) -> Optional[ContentTemplateResponse]:
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return None
        return _db_template_to_response(tpl)

    def list_templates(
        self, db: Session, category: Optional[str] = None,
        skip: int = 0, limit: int = 50,
    ) -> tuple[list[ContentTemplateResponse], int]:
        q = db.query(DBTemplate)
        if category:
            q = q.filter(DBTemplate.category == category)
        total = q.count()
        templates = q.order_by(DBTemplate.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_template_to_response(t) for t in templates], total

    def update_template(
        self, db: Session, template_id: str, **kwargs
    ) -> Optional[ContentTemplateResponse]:
        """Update template fields. Uses **kwargs for flexibility — caller (router) passes
        validated data from ContentTemplateUpdate via model_dump(exclude_none=True)."""
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(tpl, key):
                setattr(tpl, key, value)
        db.commit()
        db.refresh(tpl)
        return _db_template_to_response(tpl)

    def delete_template(self, db: Session, template_id: str) -> bool:
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return False
        db.delete(tpl)
        db.commit()
        return True

    # --- Sensitive Word CRUD ---

    def add_sensitive_word(self, db: Session, word: str) -> SensitiveWordResponse:
        existing = db.query(DBWord).filter(DBWord.word == word).first()
        if existing:
            raise ValueError(f"Word '{word}' already exists")
        db_word = DBWord(word=word)
        db.add(db_word)
        db.commit()
        db.refresh(db_word)
        self.invalidate_sensitive_word_cache()
        return _db_word_to_response(db_word)

    def list_sensitive_words(
        self, db: Session, skip: int = 0, limit: int = 200,
    ) -> tuple[list[SensitiveWordResponse], int]:
        total = db.query(DBWord).count()
        words = db.query(DBWord).order_by(DBWord.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_word_to_response(w) for w in words], total

    def delete_sensitive_word(self, db: Session, word_id: str) -> bool:
        word = db.query(DBWord).filter(DBWord.id == word_id).first()
        if not word:
            return False
        db.delete(word)
        db.commit()
        self.invalidate_sensitive_word_cache()
        return True

    def contains_sensitive(self, db: Session, text: str) -> bool:
        """Check if text contains any sensitive word (uses cached word list)."""
        words = self._get_sensitive_words(db)
        return any(word in text for word in words)

    # --- Variable Substitution ---

    @staticmethod
    def substitute_variables(body: str, context: dict[str, str]) -> str:
        """Replace {variable} placeholders in body with context values.
        Missing variables are left unchanged."""
        def replacer(match):
            key = match.group(1)
            return context.get(key, match.group(0))
        return re.sub(r"\{(\w+)\}", replacer, body)


content_service = ContentService()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -m pytest tests/test_content_service.py -v`
Expected: All 15 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/services/content_service.py server/tests/test_content_service.py
git commit -m "feat: add content service with template CRUD, sensitive word CRUD, variable substitution"
```

---

## Task 4: AI Generator Service

**Files:**
- Modify: `server/app/config.py` (add AI config vars)
- Create: `server/app/services/ai_generator.py`

- [ ] **Step 1: Add AI config variables to config.py**

Add at the end of the config section in `server/app/config.py` (after the existing config vars, before any function definitions):

```python
# AI Content Generation
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.anthropic.com")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-20250514")
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")  # anthropic or openai
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
```

Make sure `os` is already imported at the top of config.py. If not, add `import os` to the imports.

- [ ] **Step 2: Implement AiGeneratorService**

Create `server/app/services/ai_generator.py`:

```python
"""AI content generation service — calls external LLM API with sensitive word filtering."""
import logging
from typing import Any

import httpx

from app.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_PROVIDER, AI_MAX_RETRIES
from app.services.content_service import content_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个抖音评论/私信内容生成助手。根据给定的模板和上下文，生成自然、友好的中文内容。
规则：
1. 保持内容自然，像真人写的
2. 不要包含广告、链接、联系方式
3. 不要包含敏感、违规、政治相关内容
4. 内容长度控制在 20-100 字
5. 直接输出生成的内容，不要加引号或解释"""


class AiGeneratorService:
    """Generates content via external LLM API with sensitive word filtering.

    Supports two providers via AI_PROVIDER config:
    - "anthropic": Uses Anthropic Messages API (x-api-key header, /v1/messages)
    - "openai": Uses OpenAI-compatible API (Authorization Bearer, /v1/chat/completions)
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init httpx client with separated connect/read timeouts."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
            )
        return self._client

    async def aclose(self):
        """Close the httpx client. Call during app shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate(
        self,
        db,
        template_body: str,
        context: dict[str, Any],
    ) -> str:
        """Generate content from template + context. Retries if sensitive words detected.

        Args:
            db: SQLAlchemy session (for sensitive word lookup)
            template_body: Template text with {variable} placeholders already substituted
            context: Additional context for the AI prompt

        Returns:
            Generated content string

        Raises:
            RuntimeError: If AI API is not configured or all retries fail
            ValueError: If all retries produce sensitive content
        """
        if not AI_API_KEY:
            raise RuntimeError("AI_API_KEY not configured. Set the environment variable.")

        user_prompt = self._build_prompt(template_body, context)

        for attempt in range(AI_MAX_RETRIES):
            try:
                content = await self._call_api(user_prompt)
            except httpx.HTTPError as e:
                logger.warning("AI API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(f"AI API failed after {AI_MAX_RETRIES} attempts: {e}") from e
                continue

            if content_service.contains_sensitive(db, content):
                logger.info("Generated content contains sensitive words, retrying (%d/%d)", attempt + 1, AI_MAX_RETRIES)
                if attempt == AI_MAX_RETRIES - 1:
                    raise ValueError("All generated content contained sensitive words after max retries")
                continue

            return content

        raise RuntimeError("AI generation failed: exhausted all retries")

    async def _call_api(self, user_prompt: str) -> str:
        """Call the AI API and return the generated text. Dispatches by AI_PROVIDER."""
        if AI_PROVIDER == "openai":
            return await self._call_openai(user_prompt)
        return await self._call_anthropic(user_prompt)

    async def _call_anthropic(self, user_prompt: str) -> str:
        """Call Anthropic Messages API."""
        client = self._get_client()
        response = await client.post(
            f"{AI_BASE_URL.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": AI_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "max_tokens": 200,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"].strip()

    async def _call_openai(self, user_prompt: str) -> str:
        """Call OpenAI-compatible Chat Completions API."""
        client = self._get_client()
        response = await client.post(
            f"{AI_BASE_URL.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "content-type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "max_tokens": 200,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _build_prompt(template_body: str, context: dict[str, Any]) -> str:
        """Build the user prompt from template and context."""
        parts = [f"模板内容：{template_body}"]
        if context.get("keyword"):
            parts.append(f"搜索关键词：{context['keyword']}")
        if context.get("username"):
            parts.append(f"目标用户：{context['username']}")
        if context.get("video_title"):
            parts.append(f"视频标题：{context['video_title']}")
        parts.append("请根据以上信息生成一条自然的评论/私信内容。只输出内容本身。")
        return "\n".join(parts)


ai_generator = AiGeneratorService()
```

**注意：** 需要在 `server/app/main.py` 的 lifespan 中添加 `ai_generator.aclose()` 调用以关闭 HTTP 客户端。在 lifespan 的 yield 之后添加：

```python
from app.services.ai_generator import ai_generator

@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_db not in app.dependency_overrides:
        seed_all()
    yield
    await ai_generator.aclose()
```

- [ ] **Step 3: Verify the module imports correctly**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -c "from app.services.ai_generator import ai_generator; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/app/config.py server/app/services/ai_generator.py
git commit -m "feat: add AI generator service with sensitive word filtering and retry"
```

---

## Task 5: Content API Router + Tests

**Files:**
- Create: `server/app/routers/content.py`
- Modify: `server/app/main.py` (mount router)
- Create: `server/tests/test_content_api.py`

- [ ] **Step 1: Write integration tests for content API**

Create `server/tests/test_content_api.py`:

```python
"""Integration tests for content API — templates, sensitive words, generate."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _create_template(**overrides):
    """Helper: create a template and return its JSON response."""
    payload = {"name": "test-tpl", "body": "test body", "category": "comment"}
    payload.update(overrides)
    resp = client.post("/api/content/templates", json=payload)
    assert resp.status_code == 200
    return resp.json()


def _create_word(word):
    """Helper: add a sensitive word and return its JSON response."""
    resp = client.post("/api/content/sensitive-words", json={"word": word})
    assert resp.status_code == 200
    return resp.json()


class TestTemplateAPI:
    def test_create_template(self):
        resp = client.post("/api/content/templates", json={
            "name": "美食评论",
            "category": "comment",
            "body": "这个{keyword}看起来太好吃了！",
            "variables": ["keyword"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "美食评论"
        assert data["category"] == "comment"
        assert data["body"] == "这个{keyword}看起来太好吃了！"
        assert data["variables"] == ["keyword"]
        assert data["is_active"] is True
        assert "id" in data

    def test_create_template_validation_error(self):
        resp = client.post("/api/content/templates", json={
            "name": "",
            "body": "",
        })
        assert resp.status_code == 422

    def test_list_templates(self):
        _create_template(name="list-t1", body="body1")
        _create_template(name="list-t2", body="body2", category="dm")
        resp = client.get("/api/content/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "total" in data
        assert data["total"] >= 2

    def test_list_templates_filter_category(self):
        _create_template(name="filter-dm", body="dm body", category="dm")
        resp = client.get("/api/content/templates?category=dm")
        assert resp.status_code == 200
        for t in resp.json()["templates"]:
            assert t["category"] == "dm"

    def test_get_template(self):
        tpl = _create_template(name="get-me", body="body")
        resp = client.get(f"/api/content/templates/{tpl['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"

    def test_get_template_not_found(self):
        resp = client.get("/api/content/templates/nonexistent-id")
        assert resp.status_code == 404

    def test_update_template(self):
        tpl = _create_template(name="old", body="old body")
        resp = client.put(f"/api/content/templates/{tpl['id']}", json={"name": "new", "body": "new body"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new"
        assert resp.json()["body"] == "new body"

    def test_delete_template(self):
        tpl = _create_template(name="delete-me", body="body")
        resp = client.delete(f"/api/content/templates/{tpl['id']}")
        assert resp.status_code == 200
        resp = client.get(f"/api/content/templates/{tpl['id']}")
        assert resp.status_code == 404

    def test_delete_template_not_found(self):
        resp = client.delete("/api/content/templates/nonexistent-id")
        assert resp.status_code == 404


class TestSensitiveWordAPI:
    def test_add_word(self):
        resp = client.post("/api/content/sensitive-words", json={"word": "测试敏感词"})
        assert resp.status_code == 200
        assert resp.json()["word"] == "测试敏感词"

    def test_add_duplicate_word(self):
        _create_word("重复词")
        resp = client.post("/api/content/sensitive-words", json={"word": "重复词"})
        assert resp.status_code == 409

    def test_list_words(self):
        _create_word("列表词")
        resp = client.get("/api/content/sensitive-words")
        assert resp.status_code == 200
        data = resp.json()
        assert "words" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_delete_word(self):
        word = _create_word("删除词")
        resp = client.delete(f"/api/content/sensitive-words/{word['id']}")
        assert resp.status_code == 200

    def test_delete_word_not_found(self):
        resp = client.delete("/api/content/sensitive-words/nonexistent-id")
        assert resp.status_code == 404


class TestGenerateAPI:
    def test_generate_no_api_key(self):
        """Generate endpoint should return 503 when AI_API_KEY is not set."""
        tpl = _create_template(name="gen-test", body="关于{keyword}的评论", variables=["keyword"])
        resp = client.post("/api/content/generate", json={
            "template_id": tpl["id"],
            "context": {"keyword": "美食"},
        })
        assert resp.status_code == 503

    def test_generate_template_not_found(self):
        resp = client.post("/api/content/generate", json={
            "template_id": "nonexistent",
            "context": {},
        })
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -m pytest tests/test_content_api.py -v 2>&1 | head -30`
Expected: FAIL — router not mounted or not created

- [ ] **Step 3: Implement the content router**

Create `server/app/routers/content.py`:

```python
"""Content management API — templates, sensitive words, AI generation."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends

logger = logging.getLogger(__name__)
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    ContentTemplateCreate, ContentTemplateUpdate, ContentTemplateResponse,
    SensitiveWordCreate, SensitiveWordResponse,
    GenerateRequest, GenerateResponse,
)
from app.database import get_db
from app.deps import verify_admin_token
from app.services.content_service import content_service
from app.services.ai_generator import ai_generator

router = APIRouter(prefix="/api/content", tags=["content"])


# --- Template CRUD ---

@router.post("/templates", response_model=ContentTemplateResponse)
def create_template(
    request: ContentTemplateCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    return content_service.create_template(
        db, name=request.name, category=request.category,
        body=request.body, variables=request.variables,
    )


@router.get("/templates")
def list_templates(
    category: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    templates, total = content_service.list_templates(db, category=category, skip=skip, limit=limit)
    return {"templates": templates, "total": total}


@router.get("/templates/{template_id}", response_model=ContentTemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = content_service.get_template(db, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.put("/templates/{template_id}", response_model=ContentTemplateResponse)
def update_template(
    template_id: str,
    request: ContentTemplateUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    updates = request.model_dump(exclude_none=True)
    tpl = content_service.update_template(db, template_id, **updates)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not content_service.delete_template(db, template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


# --- Sensitive Word CRUD ---

@router.post("/sensitive-words", response_model=SensitiveWordResponse)
def add_sensitive_word(
    request: SensitiveWordCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        return content_service.add_sensitive_word(db, request.word)
    except ValueError:
        raise HTTPException(status_code=409, detail="Word already exists")


@router.get("/sensitive-words")
def list_sensitive_words(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    words, total = content_service.list_sensitive_words(db, skip=skip, limit=limit)
    return {"words": words, "total": total}


@router.delete("/sensitive-words/{word_id}")
def delete_sensitive_word(
    word_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not content_service.delete_sensitive_word(db, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    return {"ok": True}


# --- AI Generation ---

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = content_service.get_template(db, request.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Warn if context keys don't match template variables
    if tpl.variables:
        extra_keys = set(request.context.keys()) - set(tpl.variables)
        if extra_keys:
            logger.warning("Generate request has extra context keys not in template %s: %s", tpl.id, extra_keys)

    # Substitute variables first
    substituted = content_service.substitute_variables(tpl.body, request.context)

    try:
        content = await ai_generator.generate(db, substituted, request.context)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured. Set AI_API_KEY environment variable.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return GenerateResponse(content=content, template_id=request.template_id)
```

- [ ] **Step 4: Mount the router in main.py**

In `server/app/main.py`, add the import and mount:

At the imports line, add `content` to the import list:
```python
from app.routers import device, tasks, accounts, devices, auth, selectors, stats, content
```

After the existing `app.include_router(stats.router)` line, add:
```python
app.include_router(content.router)
```

Also add `ai_generator.aclose()` to the lifespan for proper HTTP client cleanup:

```python
from app.services.ai_generator import ai_generator

@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_db not in app.dependency_overrides:
        seed_all()
    yield
    await ai_generator.aclose()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -m pytest tests/test_content_api.py -v`
Expected: All 14 tests PASS (the generate tests pass because AI_API_KEY is empty → 503, and template-not-found → 404)

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -m pytest --tb=short -q`
Expected: All existing tests still pass + new tests pass

- [ ] **Step 7: Commit**

```bash
git add server/app/routers/content.py server/app/main.py server/tests/test_content_api.py
git commit -m "feat: add content API router with template CRUD, sensitive words, and AI generate endpoint"
```

---

## Task 6: Sensitive Words Seed Data

**Files:**
- Create: `server/config/sensitive_words.yaml`
- Modify: `server/app/seed.py` (add seed_sensitive_words function)

- [ ] **Step 1: Create default sensitive words config**

Create `server/config/sensitive_words.yaml`:

```yaml
# 敏感词库 — AI 生成内容过滤
# 注意：此文件仅在首次 seed 时加载。之后需通过管理接口添加/删除敏感词。
words:
  # 违法类
  - 赌博
  - 代购
  - 刷单
  - 返现
  - 套现
  - 借钱
  - 贷款
  - 裸聊
  - 色情
  - 毒品
  # 广告类
  - 加微信
  - 加V
  - 私聊我
  - 点击链接
  - 免费领
  - 月入过万
  - 日赚千元
```

- [ ] **Step 2: Add seed function to seed.py**

Read `server/app/seed.py` first to understand its structure, then add a `seed_sensitive_words` function following the same pattern as `seed_accounts` and `seed_selectors`. The function should:

```python
def seed_sensitive_words(db):
    """Load default sensitive words from YAML config."""
    words_path = Path(__file__).parent.parent / "config" / "sensitive_words.yaml"
    if not words_path.exists():
        return
    with open(words_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    words = data.get("words", [])
    for word in words:
        existing = db.query(SensitiveWord).filter(SensitiveWord.word == word).first()
        if not existing:
            db.add(SensitiveWord(word=word))
    db.commit()
```

Also add `from app.db_models import SensitiveWord` to the imports, and call `seed_sensitive_words(db)` from the `seed_all()` function.

- [ ] **Step 3: Verify seeding works**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -c "from app.database import init_db; init_db(); from app.seed import seed_all; from app.database import SessionLocal; db = SessionLocal(); seed_all(db); db.close(); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/config/sensitive_words.yaml server/app/seed.py
git commit -m "feat: add sensitive words seed data with default word list"
```

---

## Task 7: Frontend — Content API Client + ContentPage

**Files:**
- Create: `web/src/api/content.js`
- Create: `web/src/views/ContentPage.vue`
- Modify: `web/src/router/index.js` (add route)
- Modify: `web/src/views/AdminLayout.vue` (add nav item)

- [ ] **Step 1: Create content API client**

Create `web/src/api/content.js`:

```javascript
import client from './client.js'

// --- Templates ---
export function listTemplates(params = {}) {
  return client.get('/content/templates', { params })
}

export function getTemplate(id) {
  return client.get(`/content/templates/${id}`)
}

export function createTemplate(data) {
  return client.post('/content/templates', data)
}

export function updateTemplate(id, data) {
  return client.put(`/content/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return client.delete(`/content/templates/${id}`)
}

// --- Sensitive Words ---
export function listSensitiveWords(params = {}) {
  return client.get('/content/sensitive-words', { params })
}

export function addSensitiveWord(word) {
  return client.post('/content/sensitive-words', { word })
}

export function deleteSensitiveWord(id) {
  return client.delete(`/content/sensitive-words/${id}`)
}

// --- AI Generation ---
export function generateContent(templateId, context) {
  return client.post('/content/generate', {
    template_id: templateId,
    context,
  })
}
```

- [ ] **Step 2: Add route to router**

In `web/src/router/index.js`, add a new child route under the `/` layout route (after the `stats` route):

```javascript
{
  path: 'content',
  name: 'Content',
  component: () => import('../views/ContentPage.vue'),
},
```

- [ ] **Step 3: Add nav item to AdminLayout**

In `web/src/views/AdminLayout.vue`, add to the `navItems` array (after the stats item):

```javascript
{ name: '内容管理', path: '/content', icon: 'M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z' },
```

- [ ] **Step 4: Implement ContentPage.vue**

Create `web/src/views/ContentPage.vue` with three sections:
1. **Template list** — card-based layout (like SelectorsPage) showing template name, category badge, body preview, variable chips. Edit/delete/add buttons.
2. **Template dialog** — Headless UI Dialog for create/edit with fields: name, category (select), body (textarea), variables (comma-separated input).
3. **Sensitive words section** — collapsible section at bottom with word list, add input, delete buttons.
4. **AI Generate dialog** — accessible from template cards, shows template preview, context input fields (keyword, username, video_title), generate button, result display with copy button.

Full implementation:

```vue
<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild,
} from '@headlessui/vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  listTemplates, createTemplate, updateTemplate, deleteTemplate,
  listSensitiveWords, addSensitiveWord, deleteSensitiveWord,
  generateContent,
} from '../api/content.js'
import { formatDate } from '../utils/format.js'

// --- Templates state ---
const templates = ref([])
const loading = ref(false)
const pageError = ref(null)

// --- Template form dialog ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)
const defaultForm = { name: '', category: 'comment', body: '', variables: '' }
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation ---
const showDeleteDialog = ref(false)
const deletingTemplate = ref(null)
const deleting = ref(false)

// --- Sensitive words ---
const words = ref([])
const wordsLoading = ref(false)
const newWord = ref('')
const addingWord = ref(false)
const showWords = ref(false)

// --- AI Generate dialog ---
const showGenerateDialog = ref(false)
const generatingTemplate = ref(null)
const generateForm = reactive({ keyword: '', username: '', video_title: '' })
const generating = ref(false)
const generateResult = ref(null)
const generateError = ref(null)

const categoryLabels = { comment: '评论', dm: '私信', reply: '回复' }
const categoryColors = {
  comment: 'bg-blue-100 text-blue-800',
  dm: 'bg-green-100 text-green-800',
  reply: 'bg-purple-100 text-purple-800',
}

// --- Fetch templates ---
async function fetchTemplates() {
  loading.value = true
  try {
    const res = await listTemplates()
    templates.value = res.data.templates || []
  } catch (e) {
    pageError.value = e.response?.data?.detail || '加载模板失败'
    templates.value = []
  } finally {
    loading.value = false
  }
}

// --- Template CRUD ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  showFormDialog.value = true
}

function openEditDialog(tpl) {
  isEditing.value = true
  editingId.value = tpl.id
  form.name = tpl.name
  form.category = tpl.category
  form.body = tpl.body
  form.variables = (tpl.variables || []).join(', ')
  formError.value = null
  showFormDialog.value = true
}

async function handleSave() {
  if (!form.name.trim()) { formError.value = '名称不能为空'; return }
  if (!form.body.trim()) { formError.value = '模板内容不能为空'; return }

  saving.value = true
  formError.value = null

  const vars = form.variables.split(',').map(v => v.trim()).filter(Boolean)
  const payload = {
    name: form.name.trim(),
    category: form.category,
    body: form.body.trim(),
    variables: vars,
  }

  try {
    if (isEditing.value) {
      await updateTemplate(editingId.value, payload)
    } else {
      await createTemplate(payload)
    }
    showFormDialog.value = false
    fetchTemplates()
  } catch (e) {
    formError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

function openDeleteDialog(tpl) {
  deletingTemplate.value = tpl
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingTemplate.value) return
  deleting.value = true
  try {
    await deleteTemplate(deletingTemplate.value.id)
    showDeleteDialog.value = false
    deletingTemplate.value = null
    fetchTemplates()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败'
  } finally {
    deleting.value = false
  }
}

// --- Sensitive words ---
async function fetchWords() {
  wordsLoading.value = true
  try {
    const res = await listSensitiveWords()
    words.value = res.data.words || []
  } catch (e) {
    console.error('Failed to fetch words:', e)
  } finally {
    wordsLoading.value = false
  }
}

async function handleAddWord() {
  const w = newWord.value.trim()
  if (!w) return
  addingWord.value = true
  try {
    await addSensitiveWord(w)
    newWord.value = ''
    fetchWords()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '添加失败'
  } finally {
    addingWord.value = false
  }
}

async function handleDeleteWord(word) {
  try {
    await deleteSensitiveWord(word.id)
    fetchWords()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败'
  }
}

// --- AI Generate ---
function openGenerateDialog(tpl) {
  generatingTemplate.value = tpl
  generateForm.keyword = ''
  generateForm.username = ''
  generateForm.video_title = ''
  generateResult.value = null
  generateError.value = null
  showGenerateDialog.value = true
}

async function handleGenerate() {
  generating.value = true
  generateError.value = null
  generateResult.value = null
  try {
    const res = await generateContent(generatingTemplate.value.id, {
      keyword: generateForm.keyword,
      username: generateForm.username,
      video_title: generateForm.video_title,
    })
    generateResult.value = res.data.content
  } catch (e) {
    generateError.value = e.response?.data?.detail || '生成失败'
  } finally {
    generating.value = false
  }
}

function copyResult() {
  if (generateResult.value) {
    navigator.clipboard.writeText(generateResult.value)
  }
}

// --- Init ---
onMounted(() => {
  fetchTemplates()
  fetchWords()
})
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-500 hover:text-red-700 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">内容管理</h1>
      <button
        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
        @click="openCreateDialog"
      >
        <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        添加模板
      </button>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty -->
    <EmptyState v-else-if="templates.length === 0" message="暂无内容模板" />

    <!-- Template cards -->
    <div v-else class="grid gap-4 mb-8">
      <div
        v-for="tpl in templates"
        :key="tpl.id"
        class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
      >
        <div class="flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-semibold text-gray-900">{{ tpl.name }}</span>
              <span :class="[categoryColors[tpl.category] || 'bg-gray-100 text-gray-800']"
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
                {{ categoryLabels[tpl.category] || tpl.category }}
              </span>
              <span v-if="tpl.variables && tpl.variables.length > 0"
                class="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                {{ tpl.variables.length }} 个变量
              </span>
            </div>
            <p class="mt-2 text-sm text-gray-600 whitespace-pre-wrap">{{ tpl.body }}</p>
            <p v-if="tpl.variables && tpl.variables.length > 0" class="mt-1 text-xs text-gray-400">
              变量: {{ tpl.variables.map(v => '{' + v + '}').join(', ') }}
            </p>
          </div>
          <div class="ml-4 flex items-center gap-2 flex-shrink-0">
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-green-600 hover:text-green-800 hover:bg-green-50 rounded transition-colors"
              @click="openGenerateDialog(tpl)"
            >
              AI 生成
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
              @click="openEditDialog(tpl)"
            >
              编辑
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
              @click="openDeleteDialog(tpl)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sensitive Words Section -->
    <div class="bg-white rounded-lg shadow">
      <button
        class="w-full flex items-center justify-between px-6 py-4 text-left"
        @click="showWords = !showWords"
      >
        <h2 class="text-lg font-semibold text-gray-700">敏感词库 ({{ words.length }})</h2>
        <svg :class="showWords ? 'rotate-180' : ''" class="w-5 h-5 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="showWords" class="px-6 pb-4 border-t border-gray-100">
        <!-- Add word input -->
        <div class="flex gap-2 mt-4 mb-4">
          <input
            v-model="newWord"
            type="text"
            class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            placeholder="输入敏感词"
            @keyup.enter="handleAddWord"
          />
          <button
            :disabled="addingWord || !newWord.trim()"
            class="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleAddWord"
          >
            添加
          </button>
        </div>
        <!-- Word list -->
        <LoadingSpinner v-if="wordsLoading" />
        <div v-else-if="words.length === 0" class="text-sm text-gray-400 py-2">暂无敏感词</div>
        <div v-else class="flex flex-wrap gap-2">
          <span
            v-for="word in words"
            :key="word.id"
            class="inline-flex items-center gap-1 rounded-full bg-red-50 px-3 py-1 text-sm text-red-700"
          >
            {{ word.word }}
            <button class="text-red-400 hover:text-red-600" @click="handleDeleteWord(word)">&times;</button>
          </span>
        </div>
      </div>
    </div>

    <!-- Template Create/Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">
                  {{ isEditing ? '编辑模板' : '添加模板' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label for="tpl-name" class="block text-sm font-medium text-gray-700">名称 <span class="text-red-500">*</span></label>
                    <input id="tpl-name" v-model="form.name" type="text" required class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：美食评论模板" />
                  </div>
                  <div>
                    <label for="tpl-category" class="block text-sm font-medium text-gray-700">分类</label>
                    <select id="tpl-category" v-model="form.category" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                      <option value="comment">评论</option>
                      <option value="dm">私信</option>
                      <option value="reply">回复</option>
                    </select>
                  </div>
                  <div>
                    <label for="tpl-body" class="block text-sm font-medium text-gray-700">模板内容 <span class="text-red-500">*</span></label>
                    <textarea id="tpl-body" v-model="form.body" rows="4" required class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="支持 {keyword}、{username}、{video_title} 变量" />
                  </div>
                  <div>
                    <label for="tpl-vars" class="block text-sm font-medium text-gray-700">变量 (逗号分隔)</label>
                    <input id="tpl-vars" v-model="form.variables" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="keyword, username, video_title" />
                    <p class="mt-1 text-xs text-gray-400">在模板中使用 {变量名} 引用</p>
                  </div>
                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
                      {{ saving ? '保存中...' : '保存' }}
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除模板"
      :message="`确定要删除模板「${deletingTemplate?.name || ''}」吗？`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <!-- AI Generate Dialog -->
    <TransitionRoot :show="showGenerateDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showGenerateDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">AI 内容生成</DialogTitle>
                <p class="mt-1 text-sm text-gray-500">模板: {{ generatingTemplate?.name }}</p>
                <div class="mt-3 bg-gray-50 rounded p-3 text-sm text-gray-600 whitespace-pre-wrap">{{ generatingTemplate?.body }}</div>

                <div v-if="generateError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ generateError }}
                </div>

                <form class="mt-4 space-y-3" @submit.prevent="handleGenerate">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">搜索关键词</label>
                    <input v-model="generateForm.keyword" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：美食探店" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700">目标用户名</label>
                    <input v-model="generateForm.username" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：美食家小明" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700">视频标题</label>
                    <input v-model="generateForm.video_title" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：今天去了一家超好吃的火锅店" />
                  </div>

                  <!-- Result -->
                  <div v-if="generateResult" class="bg-green-50 border border-green-200 rounded p-3">
                    <div class="flex items-start justify-between">
                      <p class="text-sm text-green-800 flex-1">{{ generateResult }}</p>
                      <button type="button" class="ml-2 text-green-600 hover:text-green-800 text-xs" @click="copyResult">复制</button>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showGenerateDialog = false">关闭</button>
                    <button type="submit" :disabled="generating" class="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed">
                      {{ generating ? '生成中...' : 'AI 生成' }}
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>
  </div>
</template>
```

- [ ] **Step 5: Verify frontend builds**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\web && npm run build 2>&1`
Expected: Build successful, 0 errors

- [ ] **Step 6: Commit**

```bash
git add web/src/api/content.js web/src/views/ContentPage.vue web/src/router/index.js web/src/views/AdminLayout.vue
git commit -m "feat: add content management page with templates, sensitive words, and AI generate dialog"
```

---

## Task 8: Task Creation Integration — Template Selector

**Files:**
- Modify: `web/src/views/TasksPage.vue` (add template selector to create dialog)

- [ ] **Step 1: Import content API in TasksPage**

Add to the imports in `web/src/views/TasksPage.vue`:

```javascript
import { listTemplates } from '../api/content.js'
```

- [ ] **Step 2: Add template state and fetch logic**

After the existing `accounts` ref, add:

```javascript
// --- Templates for create form ---
const templates = ref([])

async function fetchTemplates() {
  try {
    const res = await listTemplates({ limit: 100 })
    templates.value = res.data.templates || []
  } catch (e) {
    console.error('Failed to fetch templates:', e)
    templates.value = []
  }
}
```

Update the `onMounted` to also fetch templates:

```javascript
onMounted(() => {
  fetchTasks()
  fetchAccounts()
  fetchTemplates()
})
```

- [ ] **Step 3: Add template selector to create dialog form**

In the create dialog form, after the "账号" select and before the "参数 (JSON)" textarea, add a template selector:

```vue
<!-- Content Template (optional, for comment/dm/reply tasks) -->
<div v-if="form.type !== 'nurture'">
  <label for="task-template" class="block text-sm font-medium text-gray-700">
    内容模板 (可选)
  </label>
  <select
    id="task-template"
    v-model="selectedTemplateId"
    class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
  >
    <option value="">不使用模板</option>
    <option
      v-for="tpl in filteredTemplates"
      :key="tpl.id"
      :value="tpl.id"
    >
      {{ tpl.name }} ({{ categoryLabels[tpl.category] || tpl.category }})
    </option>
  </select>
</div>
```

- [ ] **Step 4: Add template state variables and computed**

Add these after the existing `form` reactive:

```javascript
const selectedTemplateId = ref('')

const categoryLabels = { comment: '评论', dm: '私信', reply: '回复' }

const taskTypeToCategory = {
  search_comment: 'comment',
  search_like: 'comment',
  search_dm: 'dm',
  reply_comment: 'reply',
}

const filteredTemplates = computed(() => {
  const cat = taskTypeToCategory[form.type]
  if (!cat) return []  // nurture and unknown types have no templates
  return templates.value.filter(t => t.category === cat)
})
```

Make sure `computed` is imported from `vue` (add to the existing import).

- [ ] **Step 5: Update handleCreate to include template_id**

In the `handleCreate` function, update the payload to include `content_template_id` when a template is selected. Modify the `createTask` call:

```javascript
const taskParams = { ...parsedParams }
if (selectedTemplateId.value) {
  taskParams.content_template_id = selectedTemplateId.value
}

await createTask({
  type: form.type,
  account_id: Number(form.account_id),
  params: taskParams,
})
```

Also reset `selectedTemplateId` in `openCreateDialog`:

```javascript
function openCreateDialog() {
  Object.assign(form, defaultForm)
  createError.value = null
  selectedTemplateId.value = ''
  showCreateDialog.value = true
}
```

- [ ] **Step 6: Verify frontend builds**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\web && npm run build 2>&1`
Expected: Build successful, 0 errors

- [ ] **Step 7: Commit**

```bash
git add web/src/views/TasksPage.vue
git commit -m "feat: add template selector to task creation dialog"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\server && python -m pytest --tb=short -q`
Expected: All tests pass (existing + new content/ai tests)

- [ ] **Step 2: Run frontend build**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\web && npm run build 2>&1`
Expected: Build successful, 0 errors

- [ ] **Step 3: Verify no stale imports or broken references**

Run: `cd d:\devWorkspace\jsProjects\dy_auto\web && grep -r "NotificationToast" src/ || echo "No stale refs"`
Expected: `No stale refs`

- [ ] **Step 4: Final commit with all changes**

```bash
git add -A
git status
git commit -m "feat: phase 6 complete — AI content integration with templates, generation, and sensitive word filtering"
```
