# AI Video LangChain Agent Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AI video direct LLM calls with LangChain LLM + tools and preserve the existing multi-agent production flow.

**Architecture:** Add a focused LangChain runtime under `server/app/domains/ai_video_series/langchain_runtime/`. Keep provider renderers, production queues, cost accounting, persistence, and route contracts in their current domains; expose them as tools only when agents need deterministic project actions.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic v2, LangChain `1.3.10`, `langchain-openai` `1.3.2`, pytest.

---

## Scope Check

This is one cohesive subsystem: AI video LLM application orchestration. The plan does not migrate unrelated content, account, device, or frontend AI features.

## File Structure

- Create `server/app/domains/ai_video_series/langchain_runtime/__init__.py`: package marker and public exports.
- Create `server/app/domains/ai_video_series/langchain_runtime/models.py`: runtime config to LangChain chat model mapping.
- Create `server/app/domains/ai_video_series/langchain_runtime/agent_runner.py`: minimal async agent runner, structured JSON extraction, and tool binding.
- Create `server/app/domains/ai_video_series/langchain_runtime/tools.py`: deterministic AI video tool definitions.
- Create `server/tests/test_ai_video_langchain_models.py`: model config mapping tests.
- Create `server/tests/test_ai_video_langchain_agent_runner.py`: fake-agent runner tests.
- Create `server/tests/test_ai_video_langchain_tools.py`: tool behavior tests.
- Modify `server/requirements.txt`: add LangChain dependencies.
- Modify `server/app/domains/agency_operations/agency_runtime.py`: replace direct `httpx` model client path with LangChain runner.
- Modify `server/app/domains/ai_video_series/story_generator_expert.py`: replace direct `httpx` story model client with LangChain runner.
- Modify `server/app/domains/script_pipeline/script_pipeline_service.py`: route default script stage generation through LangChain runner.
- Modify `server/app/domains/director_planning/director_router.py`: route auto-storyboard generation through LangChain runner.
- Modify `server/app/domains/ai_video_series/style_lock.py`: route character/scene extraction through LangChain runner.
- Add or update an inventory test proving AI video modules no longer call `ai_generator.generate_custom()` or direct chat-completion `httpx` clients.

---

### Task 1: Add Dependencies And Model Mapping

**Files:**
- Modify: `server/requirements.txt`
- Create: `server/app/domains/ai_video_series/langchain_runtime/__init__.py`
- Create: `server/app/domains/ai_video_series/langchain_runtime/models.py`
- Test: `server/tests/test_ai_video_langchain_models.py`

- [ ] **Step 1: Write the failing model mapping tests**

Create `server/tests/test_ai_video_langchain_models.py`:

```python
import pytest

from app.domains.agency_operations.agency_runtime import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.models import (
    build_langchain_openai_kwargs,
    ensure_langchain_provider_supported,
)


def _runtime_config(**overrides):
    config = {
        "provider": "bailian",
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-test",
        "config": {"temperature": 0.2, "max_tokens": 4096, "timeout": 90},
    }
    config.update(overrides)
    return config


def test_build_langchain_openai_kwargs_preserves_runtime_model_config():
    kwargs = build_langchain_openai_kwargs(_runtime_config())

    assert kwargs == {
        "model": "qwen-plus",
        "api_key": "sk-test",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "temperature": 0.2,
        "max_tokens": 4096,
        "timeout": 90.0,
    }


def test_build_langchain_openai_kwargs_accepts_model_id_fallback():
    kwargs = build_langchain_openai_kwargs(_runtime_config(model="", model_id="qwen-max"))

    assert kwargs["model"] == "qwen-max"


@pytest.mark.parametrize("provider", ["openai", "ark", "doubao", "openai-compatible", "bailian"])
def test_langchain_provider_allows_existing_openai_compatible_providers(provider):
    ensure_langchain_provider_supported(_runtime_config(provider=provider))


def test_langchain_provider_allows_explicit_chat_completions_protocol():
    ensure_langchain_provider_supported(
        _runtime_config(provider="custom", config={"protocol": "openai_chat_completions"})
    )


def test_langchain_provider_rejects_unsupported_provider():
    with pytest.raises(AgencyRuntimeError) as exc:
        ensure_langchain_provider_supported(_runtime_config(provider="anthropic"))

    assert exc.value.error_code == "EXPERT_MODEL_PROVIDER_UNSUPPORTED"


def test_build_langchain_openai_kwargs_requires_base_url_key_and_model():
    with pytest.raises(AgencyRuntimeError) as exc:
        build_langchain_openai_kwargs(_runtime_config(base_url="", api_key="", model=""))

    assert exc.value.error_code == "EXPERT_MODEL_CONFIG_MISSING"
    assert "base_url, api_key, model" in str(exc.value)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_models.py -q
```

Expected: import failure for `app.domains.ai_video_series.langchain_runtime`.

- [ ] **Step 3: Add the dependencies**

Append these exact lines to `server/requirements.txt`:

```text
langchain==1.3.10
langchain-openai==1.3.2
```

- [ ] **Step 4: Create the model mapping module**

Create `server/app/domains/ai_video_series/langchain_runtime/__init__.py`:

```python
from app.domains.ai_video_series.langchain_runtime.models import (
    build_langchain_openai_kwargs,
    create_chat_model,
)

__all__ = ["build_langchain_openai_kwargs", "create_chat_model"]
```

Create `server/app/domains/ai_video_series/langchain_runtime/models.py`:

```python
from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from app.domains.agency_operations.agency_runtime import (
    AgencyRuntimeError,
    OPENAI_CHAT_COMPLETIONS_PROTOCOL,
    OPENAI_COMPATIBLE_PROVIDERS,
    _runtime_setting,
)


def ensure_langchain_provider_supported(config: dict[str, Any]) -> None:
    protocol = str(_runtime_setting(config, "protocol", "") or "").lower()
    provider = str(config.get("provider") or "").lower()
    if protocol == OPENAI_CHAT_COMPLETIONS_PROTOCOL or provider in OPENAI_COMPATIBLE_PROVIDERS:
        return
    raise AgencyRuntimeError(
        "EXPERT_MODEL_PROVIDER_UNSUPPORTED",
        "AI video LangChain runtime only supports OpenAI-compatible chat completion providers.",
    )


def build_langchain_openai_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    ensure_langchain_provider_supported(config)
    base_url = str(config.get("base_url") or "").strip()
    api_key = str(config.get("api_key") or "").strip()
    model = str(config.get("model") or config.get("model_id") or "").strip()
    missing = [name for name, value in (("base_url", base_url), ("api_key", api_key), ("model", model)) if not value]
    if missing:
        raise AgencyRuntimeError(
            "EXPERT_MODEL_CONFIG_MISSING",
            f"AI video LangChain runtime requires {', '.join(missing)}.",
        )
    return {
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": float(_runtime_setting(config, "temperature", 0.2)),
        "max_tokens": int(_runtime_setting(config, "max_tokens", 2048)),
        "timeout": float(_runtime_setting(config, "timeout", 60)),
    }


def create_chat_model(config: dict[str, Any]) -> ChatOpenAI:
    return ChatOpenAI(**build_langchain_openai_kwargs(config))
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_models.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add server/requirements.txt server/app/domains/ai_video_series/langchain_runtime server/tests/test_ai_video_langchain_models.py
git commit -m "feat: add ai video langchain model adapter"
```

---

### Task 2: Add A Minimal LangChain Agent Runner

**Files:**
- Create: `server/app/domains/ai_video_series/langchain_runtime/agent_runner.py`
- Test: `server/tests/test_ai_video_langchain_agent_runner.py`

- [ ] **Step 1: Write the failing runner tests**

Create `server/tests/test_ai_video_langchain_agent_runner.py`:

```python
import json

import pytest

from app.domains.agency_operations.agency_runtime import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.agent_runner import (
    LangChainAgentRunner,
    extract_json_object,
)


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def ainvoke(self, payload):
        self.calls.append(payload)
        return self.response


def test_extract_json_object_accepts_plain_json():
    assert extract_json_object('{"status": "passed"}') == {"status": "passed"}


def test_extract_json_object_accepts_fenced_json():
    assert extract_json_object('```json\n{"status": "passed"}\n```') == {"status": "passed"}


def test_extract_json_object_rejects_non_json():
    with pytest.raises(AgencyRuntimeError) as exc:
        extract_json_object("not json")

    assert exc.value.error_code == "EXPERT_OUTPUT_INVALID_JSON"


@pytest.mark.asyncio
async def test_runner_invokes_agent_with_system_and_user_messages():
    agent = FakeAgent({"messages": [{"content": '{"status": "passed", "decision": "ok"}'}]})
    runner = LangChainAgentRunner(agent_factory=lambda **_kwargs: agent)

    result = await runner.run_json(
        system_prompt="system",
        user_prompt="user",
        runtime_config={"provider": "mock"},
        tools=[],
    )

    assert result == {"status": "passed", "decision": "ok"}
    assert agent.calls[0]["messages"][0] == {"role": "system", "content": "system"}
    assert agent.calls[0]["messages"][1] == {"role": "user", "content": "user"}


@pytest.mark.asyncio
async def test_runner_accepts_string_agent_response():
    runner = LangChainAgentRunner(agent_factory=lambda **_kwargs: FakeAgent('{"ok": true}'))

    assert await runner.run_json(system_prompt="s", user_prompt="u", runtime_config={}, tools=[]) == {"ok": True}
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_agent_runner.py -q
```

Expected: import failure for `agent_runner`.

- [ ] **Step 3: Implement the runner**

Create `server/app/domains/ai_video_series/langchain_runtime/agent_runner.py`:

```python
from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Callable

from langchain.agents import create_agent

from app.domains.agency_operations.agency_runtime import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.models import create_chat_model


def extract_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "LangChain agent output was empty.")
    candidates = [raw.strip()]
    if "```" in raw:
        for part in raw.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate:
                candidates.append(candidate)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[index:])
            except JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "LangChain agent output was not valid JSON.")


def _content_from_agent_response(response: Any) -> Any:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                return last.get("content")
            content = getattr(last, "content", None)
            if content is not None:
                return content
        return response.get("content", response)
    content = getattr(response, "content", None)
    return content if content is not None else response


class LangChainAgentRunner:
    def __init__(self, agent_factory: Callable[..., Any] | None = None):
        self.agent_factory = agent_factory or create_agent

    async def run_json(
        self,
        *,
        system_prompt: str,
        user_prompt: Any,
        runtime_config: dict[str, Any],
        tools: list[Any],
    ) -> dict[str, Any]:
        model = None if self.agent_factory is not create_agent else create_chat_model(runtime_config)
        agent = self.agent_factory(model=model, tools=tools)
        response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            }
        )
        return extract_json_object(_content_from_agent_response(response))
```

- [ ] **Step 4: Export the runner**

Update `server/app/domains/ai_video_series/langchain_runtime/__init__.py`:

```python
from app.domains.ai_video_series.langchain_runtime.agent_runner import (
    LangChainAgentRunner,
    extract_json_object,
)
from app.domains.ai_video_series.langchain_runtime.models import (
    build_langchain_openai_kwargs,
    create_chat_model,
)

__all__ = [
    "LangChainAgentRunner",
    "build_langchain_openai_kwargs",
    "create_chat_model",
    "extract_json_object",
]
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_agent_runner.py server/tests/test_ai_video_langchain_models.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add server/app/domains/ai_video_series/langchain_runtime server/tests/test_ai_video_langchain_agent_runner.py
git commit -m "feat: add ai video langchain agent runner"
```

---

### Task 3: Add Deterministic AI Video Tools

**Files:**
- Create: `server/app/domains/ai_video_series/langchain_runtime/tools.py`
- Test: `server/tests/test_ai_video_langchain_tools.py`

- [ ] **Step 1: Write failing tool tests**

Create `server/tests/test_ai_video_langchain_tools.py`:

```python
from app.db.models import Character, Episode, Scene, Series
from app.domains.ai_video_series.langchain_runtime.tools import (
    build_ai_video_tools,
    series_context_payload,
)


def test_series_context_payload_includes_episode_assets(db):
    series = Series(title="Tool Series", logline="Secret heir.", total_episodes=1)
    character = Character(name="Lin Xia", role_type="protagonist", gender="female")
    scene = Scene(name="Clinic", scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.commit()

    payload = series_context_payload(db, series.id, episode.id)

    assert payload["series"]["title"] == "Tool Series"
    assert payload["episode"]["title"] == "Pilot"
    assert payload["characters"] == [{"id": character.id, "name": "Lin Xia", "role_type": "protagonist"}]
    assert payload["scenes"] == [{"id": scene.id, "name": "Clinic", "scene_type": "indoor"}]


def test_build_ai_video_tools_returns_restricted_tool_names(db):
    tools = build_ai_video_tools(db=None, allowed_tools=["validate_json"])

    assert [tool.name for tool in tools] == ["validate_json"]
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_tools.py -q
```

Expected: import failure for `langchain_runtime.tools`.

- [ ] **Step 3: Implement the tools**

Create `server/app/domains/ai_video_series/langchain_runtime/tools.py`:

```python
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.db.models import Episode, Series
from app.domains.agency_operations.agency_runtime import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.agent_runner import extract_json_object


def series_context_payload(db: Session, series_id: str, episode_id: str | None = None) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise AgencyRuntimeError("AI_VIDEO_CONTEXT_NOT_FOUND", "Series not found.")
    episode = None
    if episode_id:
        episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
        if not episode:
            raise AgencyRuntimeError("AI_VIDEO_CONTEXT_NOT_FOUND", "Episode not found.")
    return {
        "series": {
            "id": series.id,
            "title": series.title,
            "logline": series.logline,
            "genre": series.genre,
            "total_episodes": series.total_episodes,
        },
        "episode": None if episode is None else {
            "id": episode.id,
            "episode_number": episode.episode_number,
            "title": episode.title,
        },
        "characters": [
            {"id": item.id, "name": item.name, "role_type": item.role_type}
            for item in (series.characters or [])
        ],
        "scenes": [
            {"id": item.id, "name": item.name, "scene_type": item.scene_type}
            for item in (series.scenes or [])
        ],
        "story_bible": series.story_bible_json if isinstance(series.story_bible_json, dict) else {},
    }


def build_ai_video_tools(db: Session | None, allowed_tools: list[str] | None = None) -> list[Any]:
    selected = set(allowed_tools or ["validate_json", "read_series_context"])

    @tool
    def validate_json(raw: str) -> dict[str, Any]:
        """Parse a JSON object from model text and return it."""
        return extract_json_object(raw)

    @tool
    def read_series_context(series_id: str, episode_id: str | None = None) -> str:
        """Read series and optional episode context as JSON."""
        if db is None:
            raise AgencyRuntimeError("AI_VIDEO_CONTEXT_NOT_FOUND", "Database session is required.")
        return json.dumps(series_context_payload(db, series_id, episode_id), ensure_ascii=False)

    tools_by_name = {
        "validate_json": validate_json,
        "read_series_context": read_series_context,
    }
    return [tools_by_name[name] for name in tools_by_name if name in selected]
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/ai_video_series/langchain_runtime/tools.py server/tests/test_ai_video_langchain_tools.py
git commit -m "feat: add ai video langchain tools"
```

---

### Task 4: Replace Agency Expert Runtime With LangChain Runner

**Files:**
- Modify: `server/app/domains/agency_operations/agency_runtime.py`
- Modify: `server/tests/test_agency_runtime.py`

- [ ] **Step 1: Add a failing agency runtime test for LangChain runner injection**

Append to `server/tests/test_agency_runtime.py`:

```python
@pytest.mark.asyncio
async def test_runtime_uses_langchain_runner_for_expert_output():
    captured = {}

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            captured["runtime_config"] = runtime_config
            captured["tools"] = tools
            return {
                "decision": "pass",
                "findings": ["from langchain"],
                "recommendations": [],
                "required_changes": [],
                "evidence": [{"message": "checked"}],
                "status": "passed",
                "token_usage": {"total_tokens": 42},
            }

    runtime = AgencySkillRuntime(agent_runner=FakeRunner())
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={"frame_count": 1},
        runtime_config=_runtime_config(),
    )

    assert result.result_status == "passed"
    assert result.output_summary["findings"] == ["from langchain"]
    assert result.token_usage == {"total_tokens": 42}
    assert captured["runtime_config"]["model"] == "mock-model"
    assert captured["tools"]
```

- [ ] **Step 2: Remove direct HTTP transport tests**

Delete these tests from `server/tests/test_agency_runtime.py` because the production default must no longer verify a hand-written chat-completions client:

```text
test_default_client_sends_openai_compatible_request_payload_headers_and_url
test_default_client_sends_multimodal_content_parts
test_default_client_sends_video_content_parts
test_default_client_accepts_openai_chat_completions_protocol
test_default_client_accepts_bailian_chat_completion_provider
test_default_client_rejects_unsupported_provider_before_http_call
test_default_client_maps_rate_limit_and_http_error_to_named_errors
test_default_client_wraps_non_json_provider_response
test_default_client_wraps_missing_choices_body_shape
```

- [ ] **Step 3: Run the test and verify it fails**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_runtime.py::test_runtime_uses_langchain_runner_for_expert_output -q
```

Expected: `AgencySkillRuntime.__init__()` does not accept `agent_runner`.

- [ ] **Step 4: Modify `AgencySkillRuntime` to use the LangChain runner**

In `server/app/domains/agency_operations/agency_runtime.py`, keep parsing, redaction, and error mapping. Replace default direct model-client construction with this shape:

```python
from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools
```

Replace `_default_model_client` with a LangChain-backed compatibility function:

```python
async def _default_model_client(
    system_prompt: str,
    user_prompt: MessageContent,
    config: dict[str, Any],
) -> ModelClientResponse:
    parsed = await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=config,
        tools=build_ai_video_tools(None, allowed_tools=["validate_json"]),
    )
    return {
        "content": json.dumps(parsed, ensure_ascii=False),
        "token_usage": parsed.get("token_usage") if isinstance(parsed.get("token_usage"), dict) else {},
    }
```

Update `AgencySkillRuntime.__init__`:

```python
    def __init__(
        self,
        model_client: ModelClient | None = None,
        agent_runner: Any | None = None,
    ):
        self.agent_runner = agent_runner or LangChainAgentRunner()
        if model_client is not None:
            self.model_client = model_client
        else:
            async def default_client(
                system_prompt: str,
                user_prompt: MessageContent,
                config: dict[str, Any],
            ) -> ModelClientResponse:
                parsed = await self.agent_runner.run_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    runtime_config=config,
                    tools=build_ai_video_tools(None, allowed_tools=["validate_json"]),
                )
                return {"content": json.dumps(parsed, ensure_ascii=False), "token_usage": parsed.get("token_usage", {})}

            self.model_client = default_client
```

- [ ] **Step 5: Run agency runtime tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add server/app/domains/agency_operations/agency_runtime.py server/tests/test_agency_runtime.py
git commit -m "feat: run agency experts through langchain"
```

---

### Task 5: Replace Story Generator Direct HTTP Client

**Files:**
- Modify: `server/app/domains/ai_video_series/story_generator_expert.py`
- Modify: `server/tests/test_series_planning_service.py`

- [ ] **Step 1: Add a failing story generator test for LangChain runner injection**

Append to `server/tests/test_series_planning_service.py`:

```python
@pytest.mark.asyncio
async def test_story_generator_uses_langchain_runner_when_no_model_client(db):
    from app.domains.ai_video_series.story_generator_expert import generate_story_plan_with_expert

    captured = {}

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            captured["runtime_config"] = runtime_config
            captured["tools"] = tools
            return payload

    series = Series(title="LangChain Story", logline="A secret returns.", total_episodes=1, status="draft")
    character, scene = _add_series_assets(series)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()
    payload = _planning_payload(total_episodes=1)
    payload["episode_outlines"][0]["character_ids"] = [character.id]
    payload["episode_outlines"][0]["scene_ids"] = [scene.id]

    result = await generate_story_plan_with_expert(
        db,
        series=series,
        episodes=[episode],
        character_ids=[character.id],
        scene_ids=[scene.id],
        existing_artifacts=[],
        runtime_config={
            "scene_key": "script_generation",
            "provider": "openai-compatible",
            "model": "story-model",
            "base_url": "https://model.example/v1",
            "api_key": "sk-secret",
            "config": {"protocol": "openai_chat_completions"},
        },
        agent_runner=FakeRunner(),
    )

    assert result.parsed == payload
    assert result.model_trace["expert_id"] == "story_generator"
    assert captured["tools"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py::test_story_generator_uses_langchain_runner_when_no_model_client -q
```

Expected: `generate_story_plan_with_expert()` does not accept `agent_runner`.

- [ ] **Step 3: Update story generator implementation**

In `server/app/domains/ai_video_series/story_generator_expert.py`:

```python
from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools
```

Remove the imports of `_chat_completion_url` and `_ensure_openai_compatible_provider`, and delete `_default_story_model_client()`.

Update the function signature:

```python
    model_client: StoryModelClient | None = None,
    agent_runner: LangChainAgentRunner | None = None,
) -> StoryGeneratorResult:
```

Replace the default model call branch with:

```python
    agent_runner = agent_runner or LangChainAgentRunner()
    model_client = model_client
```

Inside the `try` block:

```python
        if model_client is not None:
            model_response = await model_client(system_prompt, user_prompt, runtime_config, response_format)
            raw_output, token_usage = _split_model_response(model_response)
            parsed = _parse_json_object(raw_output)
        else:
            parsed = await agent_runner.run_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                runtime_config=runtime_config,
                tools=build_ai_video_tools(db, allowed_tools=["validate_json", "read_series_context"]),
            )
            token_usage = parsed.get("token_usage") if isinstance(parsed.get("token_usage"), dict) else {}
            raw_output = json.dumps(parsed, ensure_ascii=False)
        _validate_story_payload(parsed)
```

- [ ] **Step 4: Run focused series planning tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/ai_video_series/story_generator_expert.py server/tests/test_series_planning_service.py
git commit -m "feat: run story planning through langchain"
```

---

### Task 6: Replace Script Pipeline Default Model Client

**Files:**
- Modify: `server/app/domains/script_pipeline/script_pipeline_service.py`
- Modify: `server/tests/test_script_pipeline.py`

- [ ] **Step 1: Add a failing default client test**

Append to `server/tests/test_script_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_default_script_model_client_uses_langchain_runner(monkeypatch):
    calls = []

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            calls.append((system_prompt, user_prompt, runtime_config, [tool.name for tool in tools]))
            return {"beats": []}

    monkeypatch.setattr(script_pipeline_module, "LangChainAgentRunner", lambda: FakeRunner())

    result = await script_pipeline_module.default_script_model_client(
        system_prompt="system",
        user_prompt="user",
        runtime_config={"provider": "openai-compatible", "model": "m"},
    )

    assert result == {"beats": []}
    assert calls[0][0] == "system"
    assert calls[0][3] == ["validate_json"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline.py::test_default_script_model_client_uses_langchain_runner -q
```

Expected: `LangChainAgentRunner` is not imported in `script_pipeline_service`.

- [ ] **Step 3: Update default script client**

In `server/app/domains/script_pipeline/script_pipeline_service.py`, replace the `_default_model_client` import with:

```python
from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools
```

Update `default_script_model_client`:

```python
async def default_script_model_client(
    *,
    system_prompt: str,
    user_prompt: str,
    runtime_config: dict[str, Any],
) -> Any:
    return await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=runtime_config,
        tools=build_ai_video_tools(None, allowed_tools=["validate_json"]),
    )
```

- [ ] **Step 4: Run focused script pipeline tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/script_pipeline/script_pipeline_service.py server/tests/test_script_pipeline.py
git commit -m "feat: run script pipeline through langchain"
```

---

### Task 7: Replace Director And Style-Lock Direct Generation Calls

**Files:**
- Modify: `server/app/domains/director_planning/director_router.py`
- Modify: `server/app/domains/ai_video_series/style_lock.py`
- Test: existing `server/tests/test_director_episode_plan.py`, `server/tests/test_series_style_lock_pipeline.py`, `server/tests/test_series_auto_generate_assets.py`

- [ ] **Step 1: Add helper functions for direct structured AI video generation**

In `server/app/domains/ai_video_series/langchain_runtime/agent_runner.py`, add:

```python
async def run_structured_ai_video_json(
    *,
    system_prompt: str,
    user_prompt: Any,
    runtime_config: dict[str, Any],
    db: Any = None,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools

    return await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=runtime_config,
        tools=build_ai_video_tools(db, allowed_tools=allowed_tools or ["validate_json"]),
    )
```

- [ ] **Step 2: Replace director auto-storyboard call**

In `server/app/domains/director_planning/director_router.py`, replace the `ai_generator.generate_custom(...)` block in `generate_auto_storyboard()` with:

```python
        runtime_config = resolve_runtime_model_config(db, "script_generation")
        parsed = await run_structured_ai_video_json(
            system_prompt="You are a short-video director. Create a concise storyboard that preserves locked character and scene continuity.",
            user_prompt=json.dumps(prompt, ensure_ascii=False),
            runtime_config=runtime_config,
            db=db,
            allowed_tools=["validate_json", "read_series_context"],
        )
```

Keep the existing timeout wrapper and fallback behavior.

- [ ] **Step 3: Replace style-lock character and scene generation calls**

In `server/app/domains/ai_video_series/style_lock.py`, import:

```python
from app.domains.ai_video_series.langchain_runtime.agent_runner import run_structured_ai_video_json
```

Replace each `ai_generator.generate_custom(...)` structured character or scene call with:

```python
        char_data = await run_structured_ai_video_json(
            system_prompt=_CHAR_SYSTEM,
            user_prompt=char_prompt,
            runtime_config=resolve_runtime_model_config(db, "script_generation"),
            db=db,
            allowed_tools=["validate_json", "read_series_context"],
        )
```

Use `scene_data` and `_SCENE_SYSTEM` for scene prompts. Keep `parse_json_with_key()` only for tests or non-replaced compatibility paths until the inventory task removes the last direct call.

- [ ] **Step 4: Run focused director and style-lock tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_director_episode_plan.py server/tests/test_series_style_lock_pipeline.py server/tests/test_series_auto_generate_assets.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add server/app/domains/director_planning/director_router.py server/app/domains/ai_video_series/style_lock.py server/app/domains/ai_video_series/langchain_runtime/agent_runner.py
git commit -m "feat: run director and style lock through langchain"
```

---

### Task 8: Add AI Video LLM Inventory Guard And Final Verification

**Files:**
- Create: `server/tests/test_ai_video_langchain_inventory.py`
- Modify: `docs/superpowers/specs/2026-06-21-ai-video-langchain-agent-orchestration-design.md` if the implemented boundary differs from the design.

- [ ] **Step 1: Write inventory guard**

Create `server/tests/test_ai_video_langchain_inventory.py`:

```python
from pathlib import Path


AI_VIDEO_PATHS = [
    Path("server/app/domains/ai_video_series"),
    Path("server/app/domains/director_planning"),
    Path("server/app/domains/script_pipeline"),
    Path("server/app/domains/agency_operations"),
]
FORBIDDEN_PATTERNS = [
    ("ai_generator.generate_custom(", "legacy ai_generator call"),
    ("httpx.AsyncClient(", "direct httpx LLM client"),
    ("chat/completions", "direct chat completions URL"),
]


def _python_files(root: Path):
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def test_ai_video_modules_do_not_call_legacy_ai_generator():
    offenders = []
    for root in AI_VIDEO_PATHS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            if "ai_generator.generate_custom(" in text:
                offenders.append(str(path))
    assert offenders == []


def test_ai_video_modules_do_not_add_new_direct_chat_completion_clients():
    offenders = []
    for root in AI_VIDEO_PATHS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern, label in FORBIDDEN_PATTERNS:
                if pattern in text:
                    offenders.append(f"{path}: {label}")
    assert offenders == []
```

- [ ] **Step 2: Run guard and focused suites**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_ai_video_langchain_inventory.py server/tests/test_ai_video_langchain_models.py server/tests/test_ai_video_langchain_agent_runner.py server/tests/test_ai_video_langchain_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run AI video regression suite**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_runtime.py server/tests/test_agency_orchestrator.py server/tests/test_series_planning_service.py server/tests/test_script_pipeline.py server/tests/test_director_episode_plan.py server/tests/test_series_style_lock_pipeline.py server/tests/test_series_auto_generate_assets.py server/tests/test_video_production_start_flow_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run app smoke**

Run:

```powershell
$env:PYTHONPATH='server'; .\server\.venv\Scripts\python.exe -c "import app.main; print('routes', len(app.main.app.routes)); import app.db.models as models; print('tables', len(models.Base.metadata.tables))"
```

Expected output includes:

```text
routes 304
tables 72
```

- [ ] **Step 5: Commit final guard**

```powershell
git add server/tests/test_ai_video_langchain_inventory.py docs/superpowers/specs/2026-06-21-ai-video-langchain-agent-orchestration-design.md
git commit -m "test: guard ai video langchain migration"
```

---

## Self-Review

- Spec coverage: Task 1 covers LangChain dependency and model mapping; Tasks 2 and 3 cover agent and tool foundation; Tasks 4 through 7 cover agency review, story planning, script generation, director storyboard, and style-lock generation; Task 8 proves old AI video direct LLM paths are gone.
- Type consistency: `LangChainAgentRunner.run_json()` always returns `dict[str, Any]`; existing callers that need raw content serialize the dict back to JSON only at the compatibility boundary.
- Risk control: provider rendering remains in existing services; agents get deterministic tools and do not own provider lifecycle state.
