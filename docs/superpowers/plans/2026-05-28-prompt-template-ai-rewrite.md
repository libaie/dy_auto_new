# Prompt Template AI Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only AI rewrite preview for existing prompt templates, allowing plain-language edits to the current JSON without auto-saving or broadcasting device updates.

**Architecture:** Add a stateless `POST /api/prompt-templates/rewrite-stream` SSE endpoint next to the existing generation endpoints. Keep persistence in the existing update route, move rewrite validation and prompt construction into `PromptTemplateService`, snapshot AI config before streaming, and use a shared frontend raw-fetch SSE helper for create/rewrite streams.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest, Vue 3, Headless UI, Pinia, Vite, Vitest, Vue Test Utils.

---

## File Structure

- Modify `server/app/services/prompt_template_service.py`
  - Own no-side-effect rewrite validation.
  - Own rewrite prompt construction.
  - Reuse existing `_validate_content()` so create/update/rewrite use the same template rules.

- Modify `server/app/services/ai_generator.py`
  - Add a config-based stream helper that does not accept or retain a SQLAlchemy session.
  - Keep `generate_custom_stream(db, ...)` backward compatible by delegating after resolving config.

- Modify `server/app/routers/prompt_templates.py`
  - Add permissive request model for rewrite.
  - Add `rewrite-stream` endpoint with `require_role("admin")`.
  - Emit only `status`, `token`, `done`, and `error`.
  - Avoid template CRUD/version/broadcast calls.

- Create `server/tests/test_prompt_template_service.py`
  - Unit-test rewrite validation and prompt construction.

- Create `server/tests/test_prompt_templates_rewrite.py`
  - API-test rewrite stream auth, SSE behavior, validation failures, AI failures, and no persistence side effects.

- Modify `server/tests/test_ai_generator.py`
  - Unit-test the new config-based stream helper.

- Modify `web/src/api/promptTemplates.js`
  - Export a raw-fetch SSE helper.
  - Export `streamTemplateGeneration()` and `streamTemplateRewrite()`.

- Modify `web/src/api/client.js`
  - Export a shared 401 handler so axios requests and raw-fetch SSE requests do not drift.

- Create `web/src/__tests__/prompt-templates-api.test.js`
  - Unit-test raw-fetch SSE helper behavior.

- Create `web/src/__tests__/prompt-templates-page.test.js`
  - Component-test rewrite UI, restore behavior, save boundary, and disabled states.

- Modify `web/src/views/PromptTemplatesPage.vue`
  - Use the shared SSE helper for create generation.
  - Add edit-mode rewrite card and rewrite state.
  - Disable save/cancel/dialog close while rewriting.
  - Restore previous JSON after failed/early-ended rewrite and expose local restore after success.

---

### Task 1: Backend Rewrite Service Helpers

**Files:**
- Modify: `server/app/services/prompt_template_service.py`
- Create: `server/tests/test_prompt_template_service.py`

- [ ] **Step 1: Write failing service helper tests**

Create `server/tests/test_prompt_template_service.py`:

```python
import copy

import pytest

from app.services.prompt_template_service import (
    PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES,
    PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS,
    prompt_template_service,
)


def valid_template_content():
    return {
        "identity": {"role": "advisor", "constraints": ["stay safe"]},
        "disabledWords": "guarantee / cure",
        "semanticGuide": {
            "mission": "Classify useful comments.",
            "highValueSignals": ["specific need"],
            "lowValueSignals": ["empty praise"],
            "keyExamples": ["specific symptom -> high value"],
        },
        "analysis": {
            "intents": ["consult"],
            "scoringRules": ["consult = 40"],
            "replyRules": ["reply naturally"],
            "replyExample": {"good": "I can share a simple idea.", "bad": "No."},
        },
        "localFilter": {"exclude": ["game"], "include": ["health"]},
        "videoComment": {"context": "short video", "goal": "attract", "rules": ["be useful"]},
        "dmOpener": {
            "context": "dm",
            "identity": {"role": "advisor"},
            "goal": "open conversation",
            "style": ["warm"],
        },
        "dmStages": {
            "qualifying": {
                "name": "qualify",
                "goal": "understand need",
                "style": "brief",
                "maxTokens": 120,
            }
        },
    }


def test_validate_rewrite_request_trims_instruction_and_accepts_valid_content():
    content = valid_template_content()

    instruction = prompt_template_service.validate_rewrite_request(
        content,
        "  make the tone warmer  ",
    )

    assert instruction == "make the tone warmer"


@pytest.mark.parametrize("instruction", ["", "   ", None, 123])
def test_validate_rewrite_request_rejects_empty_or_non_string_instruction(instruction):
    with pytest.raises(ValueError, match="instruction"):
        prompt_template_service.validate_rewrite_request(
            valid_template_content(),
            instruction,
        )


def test_validate_rewrite_request_rejects_long_instruction():
    instruction = "x" * (PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS + 1)

    with pytest.raises(ValueError, match="too long"):
        prompt_template_service.validate_rewrite_request(
            valid_template_content(),
            instruction,
        )


def test_validate_rewrite_request_rejects_non_object_content():
    with pytest.raises(ValueError, match="content must be an object"):
        prompt_template_service.validate_rewrite_request(
            ["not", "object"],
            "make it warmer",
        )


def test_validate_rewrite_request_rejects_invalid_template_content():
    content = valid_template_content()
    del content["analysis"]["replyRules"]

    with pytest.raises(ValueError, match="analysis"):
        prompt_template_service.validate_rewrite_request(
            content,
            "make it warmer",
        )


def test_validate_rewrite_request_rejects_oversized_content():
    content = valid_template_content()
    content["semanticGuide"]["keyExamples"] = ["x" * PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES]

    with pytest.raises(ValueError, match="too large"):
        prompt_template_service.validate_rewrite_request(
            content,
            "make it warmer",
        )


def test_validate_rewrite_output_reuses_full_template_validation():
    content = valid_template_content()
    del content["semanticGuide"]["highValueSignals"]

    with pytest.raises(ValueError, match="semanticGuide"):
        prompt_template_service.validate_rewrite_output(content)


def test_build_rewrite_prompt_includes_industry_instruction_and_current_json():
    content = valid_template_content()

    prompt = prompt_template_service.build_rewrite_prompt(
        industry="health",
        content=content,
        instruction="soften dm stages",
    )

    assert "Industry: health" in prompt
    assert "soften dm stages" in prompt
    assert '"disabledWords": "guarantee / cure"' in prompt
    assert "Return the complete rewritten JSON object only." in prompt
```

- [ ] **Step 2: Run service helper tests and verify they fail**

Run:

```bash
cd server && pytest tests/test_prompt_template_service.py -v
```

Expected: FAIL with an import error for `PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES` or an `AttributeError` for `validate_rewrite_request`.

- [ ] **Step 3: Add rewrite constants and helpers**

Modify `server/app/services/prompt_template_service.py`.

Add `json` to the imports:

```python
import json
from typing import Optional
```

Add constants after `_TEMPLATES_REVISION_KEY`:

```python
PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS = 2000
PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES = 50 * 1024
```

Add these methods inside `PromptTemplateService`, directly after `_validate_content()`:

```python
    @classmethod
    def _serialized_content_size(cls, content: dict) -> int:
        return len(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    @classmethod
    def validate_rewrite_request(
        cls,
        content,
        instruction,
        max_instruction_chars: int = PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS,
        max_content_bytes: int = PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES,
    ) -> str:
        """Validate rewrite input without reading or writing template rows."""
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction is required")
        trimmed_instruction = instruction.strip()
        if len(trimmed_instruction) > max_instruction_chars:
            raise ValueError(f"instruction is too long; max {max_instruction_chars} characters")
        if not isinstance(content, dict):
            raise ValueError("content must be an object")
        if cls._serialized_content_size(content) > max_content_bytes:
            raise ValueError(f"content is too large; max {max_content_bytes} bytes")
        cls._validate_content(content)
        return trimmed_instruction

    @classmethod
    def validate_rewrite_output(cls, content):
        """Validate AI rewritten output before emitting SSE done."""
        if not isinstance(content, dict):
            raise ValueError("rewritten content must be an object")
        cls._validate_content(content)
        return content

    @staticmethod
    def build_rewrite_prompt(industry: str, content: dict, instruction: str) -> str:
        current_json = json.dumps(content, ensure_ascii=False, indent=2)
        return (
            f"Industry: {industry or 'health'}\n"
            f"User rewrite instruction:\n{instruction}\n\n"
            "Current prompt template JSON:\n"
            f"{current_json}\n\n"
            "Rewrite rules:\n"
            "1. Return the complete rewritten JSON object only.\n"
            "2. Preserve the existing schema and all required fields.\n"
            "3. Apply only the requested change.\n"
            "4. Keep unrelated fields stable where possible.\n"
            "5. Do not wrap the JSON in markdown fences.\n"
        )
```

- [ ] **Step 4: Run service helper tests and verify they pass**

Run:

```bash
cd server && pytest tests/test_prompt_template_service.py -v
```

Expected: PASS for all tests in `test_prompt_template_service.py`.

- [ ] **Step 5: Commit service helper work**

Run:

```bash
git add server/app/services/prompt_template_service.py server/tests/test_prompt_template_service.py
git commit -m "test: cover prompt template rewrite helpers"
```

Expected: commit succeeds and includes only those two files.

---

### Task 2: Config-Based AI Streaming Helper

**Files:**
- Modify: `server/app/services/ai_generator.py`
- Modify: `server/tests/test_ai_generator.py`

- [ ] **Step 1: Add failing AI stream helper tests**

Append to `server/tests/test_ai_generator.py`:

```python
class _AsyncStreamResponse:
    def __init__(self, lines):
        self._lines = lines
        self.raised = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        self.raised = True

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _StreamClient:
    is_closed = False

    def __init__(self, lines):
        self.lines = lines
        self.calls = []

    def stream(self, method, url, headers=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        return _AsyncStreamResponse(self.lines)


class TestGenerateCustomStreamWithConfig:
    async def test_streams_openai_compatible_chunks_without_db(self):
        gen = AiGeneratorService()
        client = _StreamClient([
            'data: {"choices":[{"delta":{"content":"{\\"a\\""}}]}',
            'data: {"choices":[{"delta":{"content":":1}"}}]}',
            "data: [DONE]",
        ])
        gen._client = client

        chunks = []
        async for chunk in gen.generate_custom_stream_with_config(
            _openai_cfg(),
            "system",
            "user",
            max_tokens=123,
            temperature=0.2,
        ):
            chunks.append(chunk)

        assert chunks == ['{"a"', ":1}"]
        assert client.calls[0]["url"] == "https://api.example.test/v1/chat/completions"
        assert client.calls[0]["headers"]["Authorization"] == "Bearer test-key"
        assert client.calls[0]["json"]["max_tokens"] == 123
        assert client.calls[0]["json"]["temperature"] == 0.2
        assert client.calls[0]["json"]["messages"] == [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]

    async def test_stream_with_config_rejects_missing_api_key(self):
        gen = AiGeneratorService()

        with pytest.raises(RuntimeError, match="AI API not configured"):
            async for _chunk in gen.generate_custom_stream_with_config(
                {"api_key": "", "api_url": "https://api.example.test/v1/chat/completions"},
                "system",
                "user",
            ):
                pass

    async def test_existing_db_stream_resolves_config_then_delegates(self, db):
        gen = AiGeneratorService()

        async def fake_stream(ai_cfg, system_prompt, user_prompt, max_tokens=4096, temperature=0.7):
            assert ai_cfg["api_key"] == "test-key"
            assert system_prompt == "system"
            assert user_prompt == "user"
            yield "ok"

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch.object(gen, "generate_custom_stream_with_config", side_effect=fake_stream):
            chunks = []
            async for chunk in gen.generate_custom_stream(db, "system", "user"):
                chunks.append(chunk)

        assert chunks == ["ok"]
```

- [ ] **Step 2: Run AI generator tests and verify they fail**

Run:

```bash
cd server && pytest tests/test_ai_generator.py::TestGenerateCustomStreamWithConfig -v
```

Expected: FAIL with `AttributeError: 'AiGeneratorService' object has no attribute 'generate_custom_stream_with_config'`.

- [ ] **Step 3: Add config-based stream helper**

In `server/app/services/ai_generator.py`, replace the body of `generate_custom_stream()` with:

```python
        from app.config import get_ai_config_with_key
        ai_cfg = get_ai_config_with_key(db)
        async for chunk in self.generate_custom_stream_with_config(
            ai_cfg,
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk
```

Add this method directly below `generate_custom_stream()`:

```python
    async def generate_custom_stream_with_config(
        self,
        ai_cfg: dict,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Generate streaming content from a pre-resolved AI config.

        This helper intentionally does not accept a DB session so streaming
        responses do not keep SQLAlchemy sessions open while waiting on the LLM.
        """
        from app.config import AI_MAX_RETRIES

        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")

        api_url = ai_cfg.get("api_url", "")
        if "/v1/messages" in api_url:
            raise RuntimeError("Streaming is only supported for OpenAI-compatible APIs")

        client = self._get_client()

        for attempt in range(max(1, AI_MAX_RETRIES)):
            try:
                async with client.stream(
                    "POST",
                    api_url,
                    headers={
                        "Authorization": f"Bearer {ai_cfg['api_key']}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": ai_cfg.get("model", "deepseek-chat"),
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": True,
                        **({} if not ai_cfg.get("thinking_enabled") else {"thinking": {"type": "enabled"}}),
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                    return
            except httpx.HTTPError as e:
                logger.warning(
                    "generate_custom_stream_with_config API call failed (attempt %d/%d): %s",
                    attempt + 1, AI_MAX_RETRIES, e,
                )
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"generate_custom_stream_with_config failed after {AI_MAX_RETRIES} attempts: {e}"
                    ) from e
                continue
```

- [ ] **Step 4: Run AI generator tests and verify they pass**

Run:

```bash
cd server && pytest tests/test_ai_generator.py::TestGenerateCustomStreamWithConfig -v
```

Expected: PASS for the three new tests.

- [ ] **Step 5: Commit AI stream helper work**

Run:

```bash
git add server/app/services/ai_generator.py server/tests/test_ai_generator.py
git commit -m "feat: stream ai output from resolved config"
```

Expected: commit succeeds and includes only those two files.

---

### Task 3: Backend Rewrite SSE Endpoint

**Files:**
- Modify: `server/app/routers/prompt_templates.py`
- Create: `server/tests/test_prompt_templates_rewrite.py`

- [ ] **Step 1: Write failing rewrite endpoint tests**

Create `server/tests/test_prompt_templates_rewrite.py`:

```python
from contextlib import nullcontext
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db_models import PromptTemplate, SystemSetting
from app.deps import verify_admin_token
from app.main import app
from app.services.prompt_template_service import prompt_template_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_prompt_template_rows(db):
    db.query(PromptTemplate).delete()
    db.query(SystemSetting).filter(SystemSetting.key == "prompt_templates_revision").delete()
    db.commit()
    yield
    db.query(PromptTemplate).delete()
    db.query(SystemSetting).filter(SystemSetting.key == "prompt_templates_revision").delete()
    db.commit()


def valid_template_content():
    return {
        "identity": {"role": "advisor", "constraints": ["stay safe"]},
        "disabledWords": "guarantee / cure",
        "semanticGuide": {
            "mission": "Classify useful comments.",
            "highValueSignals": ["specific need"],
            "lowValueSignals": ["empty praise"],
            "keyExamples": ["specific symptom -> high value"],
        },
        "analysis": {
            "intents": ["consult"],
            "scoringRules": ["consult = 40"],
            "replyRules": ["reply naturally"],
            "replyExample": {"good": "I can share a simple idea.", "bad": "No."},
        },
        "localFilter": {"exclude": ["game"], "include": ["health"]},
    }


def rewritten_template_content():
    content = valid_template_content()
    content["analysis"]["replyRules"] = ["reply warmly"]
    return content


def sse_events(response):
    events = []
    for frame in response.text.split("\n\n"):
        frame = frame.strip()
        if frame.startswith("data: "):
            events.append(json.loads(frame[6:]))
    return events


def test_rewrite_requires_admin_role(db):
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "warmer", "content": valid_template_content()},
        )
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert response.status_code == 403


def test_rewrite_valid_ai_json_emits_done_without_persistence(db):
    template = PromptTemplate(
        name="health-default",
        industry="health",
        content=valid_template_content(),
        version=1,
    )
    db.add(template)
    db.add(SystemSetting(key="prompt_templates_revision", value="7"))
    db.commit()

    async def fake_stream(ai_cfg, system_prompt, user_prompt, max_tokens=4096, temperature=0.7):
        assert ai_cfg["api_key"] == "test-key"
        assert "warmer" in user_prompt
        yield json.dumps(rewritten_template_content())

    with patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={
        "api_key": "test-key",
        "api_url": "https://api.example.test/v1/chat/completions",
        "model": "test-model",
        "thinking_enabled": False,
    }) as cfg, \
         patch("app.routers.prompt_templates.SessionLocal", side_effect=lambda: nullcontext(db)), \
         patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", side_effect=fake_stream), \
         patch("app.ws_manager.pair_ws_manager.broadcast_to_devices", new_callable=AsyncMock) as device_broadcast, \
         patch("app.ws_manager.pair_ws_manager.broadcast_to_admins", new_callable=AsyncMock) as admin_broadcast:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "warmer", "content": valid_template_content()},
        )

    assert response.status_code == 200
    events = sse_events(response)
    assert events[-1]["type"] == "done"
    assert events[-1]["content"]["analysis"]["replyRules"] == ["reply warmly"]
    assert cfg.call_count == 1
    assert db.query(PromptTemplate).filter_by(name="health-default").one().version == 1
    assert prompt_template_service.get_version(db) == 7
    device_broadcast.assert_not_called()
    admin_broadcast.assert_not_called()


def test_rewrite_invalid_current_content_returns_error_before_ai(db):
    bad_content = valid_template_content()
    del bad_content["analysis"]["replyRules"]

    with patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "warmer", "content": bad_content},
        )

    assert response.status_code == 200
    assert sse_events(response)[-1]["type"] == "error"
    stream.assert_not_called()


def test_rewrite_long_instruction_returns_error_before_ai(db):
    with patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "x" * 2001, "content": valid_template_content()},
        )

    assert response.status_code == 200
    assert sse_events(response)[-1]["type"] == "error"
    stream.assert_not_called()


def test_rewrite_ai_invalid_json_emits_error(db):
    async def fake_stream(ai_cfg, system_prompt, user_prompt, max_tokens=4096, temperature=0.7):
        yield "{not-json"

    with patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={
        "api_key": "test-key",
        "api_url": "https://api.example.test/v1/chat/completions",
        "model": "test-model",
        "thinking_enabled": False,
    }), patch("app.routers.prompt_templates.SessionLocal", side_effect=lambda: nullcontext(db)), \
         patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", side_effect=fake_stream):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "warmer", "content": valid_template_content()},
        )

    assert sse_events(response)[-1]["type"] == "error"


def test_rewrite_ai_invalid_template_emits_error_not_warning(db):
    invalid_output = rewritten_template_content()
    del invalid_output["semanticGuide"]["highValueSignals"]

    async def fake_stream(ai_cfg, system_prompt, user_prompt, max_tokens=4096, temperature=0.7):
        yield json.dumps(invalid_output)

    with patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={
        "api_key": "test-key",
        "api_url": "https://api.example.test/v1/chat/completions",
        "model": "test-model",
        "thinking_enabled": False,
    }), patch("app.routers.prompt_templates.SessionLocal", side_effect=lambda: nullcontext(db)), \
         patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", side_effect=fake_stream):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "warmer", "content": valid_template_content()},
        )

    event_types = [event["type"] for event in sse_events(response)]
    assert "warning" not in event_types
    assert event_types[-1] == "error"
```

- [ ] **Step 2: Run rewrite endpoint tests and verify they fail**

Run:

```bash
cd server && pytest tests/test_prompt_templates_rewrite.py -v
```

Expected: FAIL with HTTP 404 for `/api/prompt-templates/rewrite-stream`.

- [ ] **Step 3: Add rewrite request model, SSE helpers, and imports**

Modify `server/app/routers/prompt_templates.py`.

Update imports:

```python
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict
from app.database import get_db, SessionLocal
from app.config import get_ai_config_with_key
from app.services.ai_generator import ai_generator as gen
```

Add this request model after `TemplateGenerateRequest`:

```python
class TemplateRewriteRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    industry: str = "health"
    instruction: Any = ""
    content: Any = None
```

Add these module helpers after `TEMPLATE_GEN_SYSTEM`:

```python
TEMPLATE_REWRITE_SYSTEM = """You are an expert prompt-template editor.

Rewrite the provided prompt template JSON according to the user instruction.
Return valid JSON only. Do not include markdown fences or explanations.
Preserve the existing schema. Preserve unrelated fields where possible.
"""


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _strip_json_fence(raw: str) -> str:
    content = raw.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:])
        if content.endswith("```"):
            content = content[: content.rfind("```")].strip()
    return content
```

- [ ] **Step 4: Add rewrite endpoint**

Add this endpoint before `@router.get("")`:

Do not add `db: Session = Depends(get_db)` to this endpoint. The endpoint snapshots AI config with a short-lived `SessionLocal()` block before returning `StreamingResponse`, so the LLM stream does not keep the request DB dependency open.

```python
@router.post("/rewrite-stream")
async def rewrite_template_stream(
    request: TemplateRewriteRequest,
    user = Depends(require_role("admin")),
):
    """AI rewrite preview for an existing prompt template JSON. Does not persist."""

    def stream_headers():
        return {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }

    logger.info("Prompt template rewrite started industry=%s", request.industry)
    try:
        instruction = prompt_template_service.validate_rewrite_request(
            request.content,
            request.instruction,
        )
        user_prompt = prompt_template_service.build_rewrite_prompt(
            request.industry,
            request.content,
            instruction,
        )
        with SessionLocal() as db:
            ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg:
            raise ValueError("AI API not configured")
    except ValueError as e:
        logger.warning(
            "Prompt template rewrite failed industry=%s error_type=preflight",
            request.industry,
        )

        async def validation_stream():
            yield _sse({"type": "error", "message": str(e)})

        return StreamingResponse(
            validation_stream(),
            media_type="text/event-stream",
            headers=stream_headers(),
        )

    async def event_stream():
        yield _sse({"type": "status", "text": "Rewriting prompt template..."})

        raw_chunks = []
        try:
            async for chunk in gen.generate_custom_stream_with_config(
                ai_cfg,
                TEMPLATE_REWRITE_SYSTEM,
                user_prompt,
                max_tokens=4096,
            ):
                raw_chunks.append(chunk)
                yield _sse({"type": "token", "text": chunk})

            raw = _strip_json_fence("".join(raw_chunks))
            rewritten = json.loads(raw)
            prompt_template_service.validate_rewrite_output(rewritten)
            logger.info("Prompt template rewrite succeeded industry=%s", request.industry)
            yield _sse({"type": "done", "content": rewritten})
        except json.JSONDecodeError as e:
            logger.warning(
                "Prompt template rewrite failed industry=%s error_type=json_decode",
                request.industry,
            )
            yield _sse({"type": "error", "message": f"AI returned invalid JSON: {str(e)[:200]}"})
        except ValueError as e:
            logger.warning(
                "Prompt template rewrite failed industry=%s error_type=validation",
                request.industry,
            )
            yield _sse({"type": "error", "message": str(e)})
        except Exception as e:
            logger.error(
                "Prompt template rewrite failed industry=%s error_type=stream",
                request.industry,
            )
            yield _sse({"type": "error", "message": str(e)[:200]})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=stream_headers(),
    )
```

- [ ] **Step 5: Run rewrite endpoint tests and verify they pass**

Run:

```bash
cd server && pytest tests/test_prompt_templates_rewrite.py -v
```

Expected: PASS for all rewrite endpoint tests.

- [ ] **Step 6: Run prompt-template related backend tests**

Run:

```bash
cd server && pytest tests/test_prompt_template_service.py tests/test_prompt_templates_rewrite.py tests/test_ai_generator.py::TestGenerateCustomStreamWithConfig -v
```

Expected: PASS.

- [ ] **Step 7: Commit rewrite endpoint work**

Run:

```bash
git add server/app/routers/prompt_templates.py server/tests/test_prompt_templates_rewrite.py
git commit -m "feat: add prompt template rewrite stream endpoint"
```

Expected: commit succeeds and includes only those two files.

---

### Task 4: Frontend Prompt Template SSE Helper

**Files:**
- Modify: `web/src/api/client.js`
- Modify: `web/src/api/promptTemplates.js`
- Create: `web/src/__tests__/prompt-templates-api.test.js`

- [ ] **Step 1: Write failing frontend API helper tests**

Create `web/src/__tests__/prompt-templates-api.test.js`:

```javascript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  handleUnauthorizedResponse: vi.fn(),
}))

vi.mock('../api/client.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
  handleUnauthorizedResponse: mocks.handleUnauthorizedResponse,
}))

function streamFrom(chunks) {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
}

describe('prompt template SSE API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
    localStorage.setItem('token', 'token-123')
  })

  it('streamTemplateRewrite posts to /api with bearer token and parses split SSE frames', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom([
        'data: {"type":"status","text":"start"}\n',
        '\ndata: {"type":"token","text":"{\\"a\\""}\n\n',
        'data: {"type":"done","content":{"a":1}}\n\n',
      ]),
    })
    vi.stubGlobal('fetch', fetchMock)
    const events = []

    const { streamTemplateRewrite } = await import('../api/promptTemplates.js')
    await streamTemplateRewrite(
      { industry: 'health', content: { a: 1 }, instruction: 'warmer' },
      { onEvent: (event) => events.push(event) },
    )

    expect(fetchMock).toHaveBeenCalledWith('/api/prompt-templates/rewrite-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-123',
      },
      body: JSON.stringify({ industry: 'health', content: { a: 1 }, instruction: 'warmer' }),
    })
    expect(events).toEqual([
      { type: 'status', text: 'start' },
      { type: 'token', text: '{"a"' },
      { type: 'done', content: { a: 1 } },
    ])
  })

  it('throws on non-ok responses with parsed detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Server Error',
      json: async () => ({ detail: 'failed' }),
    }))

    const { streamTemplateRewrite } = await import('../api/promptTemplates.js')

    await expect(streamTemplateRewrite({}, { onEvent: () => {} })).rejects.toThrow('failed')
  })

  it('uses the shared unauthorized handler on 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'expired' }),
    }))

    const { streamTemplateRewrite } = await import('../api/promptTemplates.js')

    await expect(streamTemplateRewrite({}, { onEvent: () => {} })).rejects.toThrow('expired')
    expect(mocks.handleUnauthorizedResponse).toHaveBeenCalledTimes(1)
  })

  it('throws after forwarding an SSE error event', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom([
        'data: {"type":"token","text":"{\\"partial\\""}\n\n',
        'data: {"type":"error","message":"invalid output"}\n\n',
      ]),
    }))
    const events = []

    const { streamTemplateRewrite } = await import('../api/promptTemplates.js')

    await expect(streamTemplateRewrite(
      { industry: 'health', content: { a: 1 }, instruction: 'warmer' },
      { onEvent: (event) => events.push(event) },
    )).rejects.toThrow('invalid output')
    expect(events).toEqual([
      { type: 'token', text: '{"partial"' },
      { type: 'error', message: 'invalid output' },
    ])
  })
})
```

- [ ] **Step 2: Run frontend API helper tests and verify they fail**

Run:

```bash
cd web && npx vitest run src/__tests__/prompt-templates-api.test.js
```

Expected: FAIL because `streamTemplateRewrite` is not exported.

- [ ] **Step 3: Export shared 401 handler and add raw-fetch SSE helper exports**

In `web/src/api/client.js`, add the shared handler after `_authHandler` / `_toastHandler`:

```javascript
export function handleUnauthorizedResponse() {
  if (_authHandler) {
    _authHandler()
  } else {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
  }
}
```

Then replace the inline 401 interceptor body with:

```javascript
if (error.response && error.response.status === 401) {
  handleUnauthorizedResponse()
  return Promise.reject(error)
}
```

In `web/src/api/promptTemplates.js`, change the existing import:

```javascript
import client, { handleUnauthorizedResponse } from './client.js'
```

Then append:

```javascript
async function parseErrorResponse(resp) {
  const err = await resp.json().catch(() => ({ detail: resp.statusText }))
  return err.detail || err.message || `HTTP ${resp.status}`
}

export async function streamPromptTemplateSse(path, payload, { onEvent } = {}) {
  const token = localStorage.getItem('token') || ''
  const resp = await fetch(`/api${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })

  if (!resp.ok) {
    const message = await parseErrorResponse(resp)
    if (resp.status === 401) {
      handleUnauthorizedResponse()
    }
    throw new Error(message)
  }

  if (!resp.body) {
    throw new Error('Streaming response body is unavailable')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    while (buffer.includes('\n\n')) {
      const idx = buffer.indexOf('\n\n')
      const raw = buffer.slice(0, idx).trim()
      buffer = buffer.slice(idx + 2)
      if (!raw.startsWith('data: ')) continue
      const event = JSON.parse(raw.slice(6))
      if (onEvent) await onEvent(event)
      if (event.type === 'error') {
        throw new Error(event.message || 'Stream error')
      }
    }
  }

  const trailing = buffer.trim()
  if (trailing.startsWith('data: ')) {
    const event = JSON.parse(trailing.slice(6))
    if (onEvent) await onEvent(event)
    if (event.type === 'error') {
      throw new Error(event.message || 'Stream error')
    }
  }
}

export function streamTemplateGeneration(payload, callbacks) {
  return streamPromptTemplateSse('/prompt-templates/generate-stream', payload, callbacks)
}

export function streamTemplateRewrite(payload, callbacks) {
  return streamPromptTemplateSse('/prompt-templates/rewrite-stream', payload, callbacks)
}
```

- [ ] **Step 4: Run frontend API helper tests and verify they pass**

Run:

```bash
cd web && npx vitest run src/__tests__/prompt-templates-api.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit frontend API helper work**

Run:

```bash
git add web/src/api/client.js web/src/api/promptTemplates.js web/src/__tests__/prompt-templates-api.test.js
git commit -m "feat: add prompt template sse api helper"
```

Expected: commit succeeds and includes only those three files.

---

### Task 5: Prompt Templates Page Rewrite UI

**Files:**
- Modify: `web/src/views/PromptTemplatesPage.vue`
- Create: `web/src/__tests__/prompt-templates-page.test.js`

- [ ] **Step 1: Write failing page tests**

Create `web/src/__tests__/prompt-templates-page.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  listTemplates: vi.fn(),
  updateTemplate: vi.fn(),
  createTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  toggleTemplate: vi.fn(),
  streamTemplateRewrite: vi.fn(),
  streamTemplateGeneration: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
  useWebSocket: vi.fn(),
}))

vi.mock('../api/promptTemplates.js', () => ({
  listTemplates: mocks.listTemplates,
  updateTemplate: mocks.updateTemplate,
  createTemplate: mocks.createTemplate,
  deleteTemplate: mocks.deleteTemplate,
  toggleTemplate: mocks.toggleTemplate,
  streamTemplateRewrite: mocks.streamTemplateRewrite,
  streamTemplateGeneration: mocks.streamTemplateGeneration,
}))

vi.mock('../stores/toast.js', () => ({
  useToastStore: () => mocks.toast,
}))

vi.mock('../composables/useWebSocket.js', () => ({
  useWebSocket: mocks.useWebSocket,
}))

const currentContent = {
  identity: { role: 'advisor', constraints: ['safe'] },
  disabledWords: 'guarantee',
  semanticGuide: {
    mission: 'classify',
    highValueSignals: ['need'],
    lowValueSignals: ['empty'],
    keyExamples: ['example'],
  },
  analysis: {
    intents: ['consult'],
    scoringRules: ['consult = 40'],
    replyRules: ['reply naturally'],
    replyExample: { good: 'good reply', bad: 'bad reply' },
  },
  localFilter: { exclude: ['game'], include: ['health'] },
}

const rewrittenContent = {
  ...currentContent,
  analysis: {
    ...currentContent.analysis,
    replyRules: ['reply warmly'],
  },
}

function templateRow() {
  return {
    id: 1,
    name: 'health-default',
    industry: 'health',
    description: 'default',
    content: currentContent,
    version: 1,
    enabled: true,
  }
}

async function mountPage() {
  mocks.listTemplates.mockResolvedValue({ data: { templates: [templateRow()] } })
  const Page = (await import('../views/PromptTemplatesPage.vue')).default
  const wrapper = mount(Page)
  await flushPromises()
  return wrapper
}

describe('PromptTemplatesPage AI rewrite', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('shows rewrite card in edit mode and hides it in create mode', async () => {
    const wrapper = await mountPage()

    wrapper.vm.openCreate()
    await flushPromises()
    expect(wrapper.text()).not.toContain('AI 修改')

    wrapper.vm.openEdit(templateRow())
    await flushPromises()
    expect(wrapper.text()).toContain('AI 修改')
  })

  it('blocks invalid current JSON before calling rewrite API', async () => {
    const wrapper = await mountPage()
    wrapper.vm.openEdit(templateRow())
    wrapper.vm.form.contentJson = '{bad json'
    wrapper.vm.rewriteInstruction = 'make warmer'

    await wrapper.vm.handleRewrite()

    expect(mocks.streamTemplateRewrite).not.toHaveBeenCalled()
    expect(mocks.toast.error).toHaveBeenCalled()
  })

  it('successful rewrite replaces editor but does not call updateTemplate', async () => {
    const wrapper = await mountPage()
    wrapper.vm.openEdit(templateRow())
    wrapper.vm.rewriteInstruction = 'make warmer'
    mocks.streamTemplateRewrite.mockImplementation(async (_payload, { onEvent }) => {
      await onEvent({ type: 'token', text: '{"identity"' })
      await onEvent({ type: 'done', content: rewrittenContent })
    })

    await wrapper.vm.handleRewrite()

    expect(JSON.parse(wrapper.vm.form.contentJson).analysis.replyRules).toEqual(['reply warmly'])
    expect(mocks.updateTemplate).not.toHaveBeenCalled()
    expect(wrapper.vm.rewriteHasRestore).toBe(true)
  })

  it('failed rewrite restores previous editor content', async () => {
    const wrapper = await mountPage()
    wrapper.vm.openEdit(templateRow())
    wrapper.vm.rewriteInstruction = 'make warmer'
    const previous = wrapper.vm.form.contentJson
    mocks.streamTemplateRewrite.mockImplementation(async (_payload, { onEvent }) => {
      await onEvent({ type: 'token', text: '{"partial"' })
      await onEvent({ type: 'error', message: 'invalid output' })
    })

    await wrapper.vm.handleRewrite()

    expect(wrapper.vm.form.contentJson).toBe(previous)
    expect(mocks.toast.error).toHaveBeenCalled()
  })

  it('restore action returns to previous editor content after success', async () => {
    const wrapper = await mountPage()
    wrapper.vm.openEdit(templateRow())
    wrapper.vm.rewriteInstruction = 'make warmer'
    const previous = wrapper.vm.form.contentJson
    mocks.streamTemplateRewrite.mockImplementation(async (_payload, { onEvent }) => {
      await onEvent({ type: 'done', content: rewrittenContent })
    })

    await wrapper.vm.handleRewrite()
    wrapper.vm.restoreLastRewrite()

    expect(wrapper.vm.form.contentJson).toBe(previous)
    expect(wrapper.vm.rewriteHasRestore).toBe(false)
  })

  it('keeps save and close disabled while rewriting', async () => {
    const wrapper = await mountPage()
    wrapper.vm.openEdit(templateRow())
    wrapper.vm.rewriteInstruction = 'make warmer'
    let finish
    mocks.streamTemplateRewrite.mockImplementation(() => new Promise((resolve) => { finish = resolve }))

    const promise = wrapper.vm.handleRewrite()
    await flushPromises()

    expect(wrapper.vm.rewriting).toBe(true)
    wrapper.vm.closeDialog()
    expect(wrapper.vm.dialogOpen).toBe(true)
    await wrapper.vm.handleSave()
    expect(mocks.updateTemplate).not.toHaveBeenCalled()

    finish()
    await promise
  })
})
```

- [ ] **Step 2: Run page tests and verify they fail**

Run:

```bash
cd web && npx vitest run src/__tests__/prompt-templates-page.test.js
```

Expected: FAIL because rewrite state/functions/UI do not exist.

- [ ] **Step 3: Add rewrite state and reset helpers**

Modify `web/src/views/PromptTemplatesPage.vue`.

Keep the existing import:

```javascript
import { ref, onMounted, nextTick } from 'vue'
```

Add after `const aiDesc = useSavedPrompt('template_generator', '')`:

```javascript
const rewriteInstruction = useSavedPrompt('template_rewriter', '')
const rewriting = ref(false)
const rewriteStatus = ref('')
const rewriteRestoreContent = ref('')
const rewriteHasRestore = ref(false)
```

Add after helper functions:

```javascript
function resetRewriteState() {
  rewriteStatus.value = ''
  rewriteRestoreContent.value = ''
  rewriteHasRestore.value = false
}

function closeDialog() {
  if (rewriting.value) return
  dialogOpen.value = false
}

function restoreLastRewrite() {
  if (!rewriteHasRestore.value) return
  form.value.contentJson = rewriteRestoreContent.value
  rewriteRestoreContent.value = ''
  rewriteHasRestore.value = false
  toast.success('已恢复 AI 修改前内容')
}
```

In `openCreate()` and `openEdit(row)`, call `resetRewriteState()` before opening the dialog:

```javascript
  resetRewriteState()
```

- [ ] **Step 4: Add rewrite action**

Add this function before `handleSave()`:

```javascript
async function handleRewrite() {
  if (rewriting.value) return

  const instruction = rewriteInstruction.value.trim()
  if (!instruction) {
    toast.error('请输入 AI 修改要求')
    return
  }

  let currentContent
  try {
    currentContent = JSON.parse(form.value.contentJson)
  } catch (e) {
    toast.error('JSON 格式无效: ' + e.message)
    return
  }

  const previousContent = form.value.contentJson
  let tokenBuffer = ''
  let receivedDone = false
  let lastRender = Date.now()

  rewriting.value = true
  rewriteStatus.value = '正在连接...'
  rewriteRestoreContent.value = ''
  rewriteHasRestore.value = false

  try {
    await api.streamTemplateRewrite({
      industry: form.value.industry,
      instruction,
      content: currentContent,
    }, {
      onEvent: async (data) => {
        if (data.type === 'status') {
          rewriteStatus.value = data.text || ''
        } else if (data.type === 'token') {
          tokenBuffer += data.text || ''
          rewriteStatus.value = 'AI 正在修改...'
          const now = Date.now()
          if (now - lastRender > 50) {
            form.value.contentJson = tokenBuffer
            await nextTick()
            lastRender = now
          }
        } else if (data.type === 'done') {
          receivedDone = true
          rewriteRestoreContent.value = previousContent
          rewriteHasRestore.value = true
          form.value.contentJson = JSON.stringify(data.content, null, 2)
          rewriteStatus.value = ''
          toast.success('AI 修改完成，请检查后保存')
        } else if (data.type === 'error') {
          throw new Error(data.message || 'AI 修改失败')
        }
      },
    })

    if (!receivedDone) {
      throw new Error('AI 修改连接中断')
    }
  } catch (e) {
    if (!receivedDone) {
      form.value.contentJson = previousContent
      rewriteRestoreContent.value = ''
      rewriteHasRestore.value = false
    }
    rewriteStatus.value = ''
    toast.error('AI 修改失败: ' + e.message)
  } finally {
    rewriting.value = false
  }
}
```

- [ ] **Step 5: Update create generation to use the shared SSE helper**

Replace only the fetch/reader loop inside `handleGenerate()` with:

```javascript
    await api.streamTemplateGeneration(
      { description: aiDesc.value, industry: form.value.industry },
      {
        onEvent: async (data) => {
          if (data.type === 'token') {
            form.value.contentJson += data.text
            generatingStatus.value = 'AI 正在生成...'
          } else if (data.type === 'status') {
            generatingStatus.value = data.text
          } else if (data.type === 'done') {
            receivedDone = true
            form.value.contentJson = JSON.stringify(data.content, null, 2)
            generatingStatus.value = ''
            if (!form.value.name) {
              const words = aiDesc.value.split(/[\s,，]+/).filter(w => w.length > 1)
              form.value.name = form.value.industry + '-' + (words.slice(0, 3).join('-') || 'custom')
            }
            toast.success('模板已生成，请检查并保存')
          } else if (data.type === 'error') {
            generatingStatus.value = ''
          }
        },
      },
    )
```

Keep the existing `receivedDone` variable and the final interrupted-connection check. Do not set `receivedDone = true` in the `error` branch, and do not toast inside that branch because `streamPromptTemplateSse()` throws after forwarding the `error` event and the existing outer `catch` owns the user-facing error toast.

- [ ] **Step 6: Add rewrite card and disabled close/save behavior**

In the template, change the dialog close binding:

```vue
<Dialog as="div" class="relative z-50" @close="closeDialog">
```

Add this card after the description field and before the create-mode AI generate card:

```vue
                  <!-- AI rewrite card -->
                  <div v-if="isEditing" class="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.03] p-4 space-y-3">
                    <div class="flex items-center gap-2">
                      <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v6h6M20 20v-6h-6M20 9A7 7 0 008.2 4.2L4 10m16 4l-4.2 5.8A7 7 0 014 15" />
                      </svg>
                      <span class="text-sm font-semibold text-cyan-300">AI 修改</span>
                      <span class="text-xs text-slate-500">用自然语言微调当前模板 JSON</span>
                    </div>
                    <div class="flex flex-col sm:flex-row gap-2">
                      <input
                        v-model="rewriteInstruction"
                        :disabled="rewriting"
                        maxlength="2000"
                        class="flex-1 rounded-lg bg-slate-900/60 border border-white/[0.08] px-3.5 py-2 text-sm text-white placeholder-slate-500 transition-all duration-200 disabled:opacity-50"
                        placeholder="例如：语气更温和，私信阶段少一些营销感"
                        @keydown.enter="handleRewrite"
                      />
                      <button
                        class="btn-aurora rounded-lg px-4 py-2 text-sm font-semibold inline-flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                        :disabled="rewriting || !rewriteInstruction.trim()"
                        @click="handleRewrite"
                      >
                        <svg v-if="rewriting" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        <span>{{ rewriting ? '修改中...' : 'AI 修改' }}</span>
                      </button>
                    </div>
                    <div v-if="rewriteStatus" class="text-xs text-cyan-300" aria-live="polite">
                      {{ rewriteStatus }}
                    </div>
                    <button
                      v-if="rewriteHasRestore"
                      class="text-xs font-semibold text-slate-300 hover:text-white"
                      type="button"
                      @click="restoreLastRewrite"
                    >
                      恢复 AI 修改前内容
                    </button>
                  </div>
```

Update cancel and save buttons:

```vue
                    @click="closeDialog"
                    :disabled="saving || rewriting"
```

```vue
                    :disabled="saving || rewriting"
```

Also add a method-level guard at the top of `handleSave()`:

```javascript
  if (rewriting.value) return
```

- [ ] **Step 7: Run page tests and verify they pass**

Run:

```bash
cd web && npx vitest run src/__tests__/prompt-templates-page.test.js
```

Expected: PASS.

- [ ] **Step 8: Commit page UI work**

Run:

```bash
git add web/src/views/PromptTemplatesPage.vue web/src/__tests__/prompt-templates-page.test.js
git commit -m "feat: add prompt template ai rewrite UI"
```

Expected: commit succeeds and includes only those two files.

---

### Task 6: Full Verification

**Files:**
- Read: all files modified in Tasks 1-5.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
cd server && pytest tests/test_prompt_template_service.py tests/test_prompt_templates_rewrite.py tests/test_ai_generator.py::TestGenerateCustomStreamWithConfig -v
```

Expected: PASS.

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
cd web && npx vitest run src/__tests__/prompt-templates-api.test.js src/__tests__/prompt-templates-page.test.js
```

Expected: PASS.

- [ ] **Step 3: Run frontend production build**

Run:

```bash
cd web && npm run build
```

Expected: PASS and Vite emits a `dist` build.

- [ ] **Step 4: Check diff for unintended side effects**

Run:

```bash
git diff --stat HEAD
git diff -- server/app/routers/prompt_templates.py server/app/services/prompt_template_service.py server/app/services/ai_generator.py web/src/api/client.js web/src/api/promptTemplates.js web/src/views/PromptTemplatesPage.vue
```

Expected:
- No template create/update/delete/toggle behavior is changed except create generation using the shared SSE helper.
- No device API code is changed.
- No migration or database model is changed.
- No automatic save call is added to rewrite.

- [ ] **Step 5: Commit verification-only adjustments if any were required**

If the verification steps required code fixes, stage only the files changed by those fixes:

```bash
git add server/app/routers/prompt_templates.py server/app/services/prompt_template_service.py server/app/services/ai_generator.py server/tests/test_prompt_template_service.py server/tests/test_prompt_templates_rewrite.py server/tests/test_ai_generator.py web/src/api/client.js web/src/api/promptTemplates.js web/src/views/PromptTemplatesPage.vue web/src/__tests__/prompt-templates-api.test.js web/src/__tests__/prompt-templates-page.test.js
git commit -m "fix: harden prompt template rewrite flow"
```

Expected: commit succeeds only if there were verification fixes. If there were no fixes, leave this step unchecked and do not create an empty commit.

---

## Self-Review

**Spec coverage check:**
- Edit-only rewrite UI: Task 5.
- Plain-language instruction: Task 5.
- Complete JSON rewrite output: Tasks 1 and 3.
- No auto-save: Tasks 3 and 5 tests.
- Admin role: Task 3.
- SSE `status/token/done/error`: Tasks 3 and 4.
- Full validation before `done`: Tasks 1 and 3.
- 2,000 char instruction limit: Tasks 1, 3, and 5.
- 50 KB content limit: Task 1 and Task 3.
- AI config snapshot before stream: Tasks 2 and 3.
- Shared raw-fetch SSE helper: Task 4 and Task 5.
- Restore previous content on failure and after success: Task 5.
- Disable save/cancel/close while rewriting: Task 5.
- No DB write/version/broadcast: Task 3.

**Placeholder scan:**
- Checked for disallowed placeholder markers; none found.
- Every task includes concrete test code, implementation code, commands, and expected outcomes.
- Every referenced helper is introduced by a defining task before execution depends on it.

**Type consistency check:**
- Backend service methods: `validate_rewrite_request()`, `validate_rewrite_output()`, `build_rewrite_prompt()`.
- Backend AI helper: `generate_custom_stream_with_config()`.
- Frontend API helpers: `handleUnauthorizedResponse()`, `streamPromptTemplateSse()`, `streamTemplateGeneration()`, `streamTemplateRewrite()`.
- Page state names: `rewriteInstruction`, `rewriting`, `rewriteStatus`, `rewriteRestoreContent`, `rewriteHasRestore`.
- Page actions: `handleRewrite()`, `restoreLastRewrite()`, `closeDialog()`, `resetRewriteState()`.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR | Scope held: edit-mode rewrite preview, no persistence side effects |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | SKIPPED | No implementation diff yet |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | CLEAR | 7 plan fixes applied: SSE error throw, test DB isolation, shared 401 handler, DB session snapshot, preflight logging, duplicate toast removal, rewrite/save guards |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | Rewrite card placement and restore/disabled states covered in page tests |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | SKIPPED | Not needed for this admin-only UI/API feature |

**Plan Eng Review Summary**
- Step 0: Scope accepted as-is. Source changes are concentrated; tests are intentionally broad because this touches backend SSE, frontend streaming, and edit UI state.
- Architecture Review: 3 issues found and fixed in the plan: SSE `error` events must reject, rewrite streaming must not hold request DB dependencies, and 401 behavior must be shared with axios.
- Code Quality Review: 3 issues found and fixed in the plan: duplicate create-generation error toast, missing method-level rewriting guards, and preflight failure logs.
- Test Review: 3 gaps fixed in the plan: local cleanup for `PromptTemplate`/`SystemSetting`, `SessionLocal` patched to test DB context, and save-block behavior asserted during rewriting.
- Performance Review: 1 issue fixed in the plan: AI config is loaded with a short-lived session before returning `StreamingResponse`.
- NOT in scope: changing prompt-template CRUD semantics, adding DB migrations, changing device APIs, auto-saving rewritten templates, or redesigning the create-template flow beyond reusing the SSE helper.
- What already exists: prompt-template CRUD, create-template AI stream endpoint, template content validation, auth role checks, and WebSocket broadcasts for actual persisted changes.
- Failure modes: no critical gaps remain after the plan fixes; execution still must run the focused pytest/Vitest/build commands in Task 6.
- Worktree parallelization strategy: sequential implementation recommended because backend contract, SSE helper, and UI behavior build on each other.
- Unresolved decisions: none.
