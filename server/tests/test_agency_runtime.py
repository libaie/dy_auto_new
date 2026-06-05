import json

import httpx
import pytest

from app.services.agency_prompting import build_expert_prompt
from app.services.agency_runtime import AgencyRuntimeError, AgencySkillRuntime


def _runtime_config():
    return {
        "provider": "openai",
        "model": "mock-model",
        "base_url": "https://model.test/v1",
        "api_key": "secret-key",
        "config": {
            "timeout": 30,
            "max_tokens": 512,
            "temperature": 0.1,
            "nested_secret": "hidden",
        },
    }


def _valid_output(**overrides):
    payload = {
        "decision": "pass",
        "findings": ["clear storyboard"],
        "recommendations": [],
        "required_changes": [],
        "evidence": [{"message": "frame count checked"}],
        "status": "passed",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_prompt_keeps_expert_markdown_out_of_system_prompt():
    prompt = build_expert_prompt(
        expert_id="prompt_engineer",
        expert_markdown="PROMPT_ENGINEER_UNIQUE_TEXT",
        stage="storyboard",
        role="reviewer",
        stage_context={"story": "city doctor case"},
        output_schema={"type": "object"},
    )

    assert "PROMPT_ENGINEER_UNIQUE_TEXT" not in prompt.system_prompt
    assert "PROMPT_ENGINEER_UNIQUE_TEXT" in prompt.user_prompt
    assert "expert_markdown_untrusted" in prompt.user_prompt
    assert "untrusted" in prompt.system_prompt
    assert "dy_auto system safety rules" in prompt.system_prompt
    assert "简体中文" in prompt.system_prompt
    assert "Expert id: prompt_engineer" in prompt.system_prompt
    assert "Stage: storyboard" in prompt.system_prompt
    assert "Role: reviewer" in prompt.system_prompt
    assert "city doctor case" in prompt.user_prompt
    assert "marketing-short-video-editing-coach" not in prompt.system_prompt
    assert "marketing-short-video-editing-coach" not in prompt.user_prompt


@pytest.mark.asyncio
async def test_runtime_parses_valid_json_and_redacts_model_config():
    async def fake_client(system_prompt, user_prompt, config):
        assert "Prompt Engineer" not in system_prompt
        assert "expert_markdown_untrusted" in user_prompt
        assert '"frame_count": 3' in user_prompt
        assert config["api_key"] == "secret-key"
        return _valid_output(
            decision="pass",
            findings=["storyboard rhythm is clear"],
            evidence=[{"message": "first frame has a hook"}],
            token_usage={"total_tokens": 123},
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={"frame_count": 3},
        runtime_config=_runtime_config(),
    )

    assert result.result_status == "passed"
    assert result.output_summary["findings"] == ["storyboard rhythm is clear"]
    assert result.evidence == [{"message": "first frame has a hook"}]
    assert result.token_usage == {"total_tokens": 123}
    assert "api_key" not in result.model_config_snapshot
    assert "nested_secret" not in result.model_config_snapshot["config"]


@pytest.mark.asyncio
async def test_runtime_extracts_json_from_fenced_model_output():
    async def fenced_client(system_prompt, user_prompt, config):
        return f"```json\n{_valid_output(decision='wrapped json')}\n```"

    runtime = AgencySkillRuntime(model_client=fenced_client)
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={},
        runtime_config=_runtime_config(),
    )

    assert result.result_status == "passed"
    assert result.output_summary["decision"] == "wrapped json"


@pytest.mark.asyncio
async def test_runtime_invalid_json_maps_to_named_error():
    async def bad_client(system_prompt, user_prompt, config):
        return "not json"

    runtime = AgencySkillRuntime(model_client=bad_client)
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_OUTPUT_INVALID_JSON"


@pytest.mark.asyncio
async def test_runtime_invalid_status_maps_to_named_error():
    async def bad_client(system_prompt, user_prompt, config):
        return _valid_output(status="maybe")

    runtime = AgencySkillRuntime(model_client=bad_client)
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_OUTPUT_INVALID_JSON"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("decision", ["not a string"]),
        ("findings", "not a list"),
        ("recommendations", "not a list"),
        ("required_changes", "not a list"),
        ("evidence", "not a list"),
    ],
)
async def test_runtime_invalid_required_field_types_map_to_named_error(field, value):
    async def bad_client(system_prompt, user_prompt, config):
        return _valid_output(**{field: value})

    runtime = AgencySkillRuntime(model_client=bad_client)
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_OUTPUT_INVALID_JSON"


@pytest.mark.asyncio
async def test_runtime_missing_required_fields_map_to_named_error():
    async def bad_client(system_prompt, user_prompt, config):
        return json.dumps({"status": "passed"})

    runtime = AgencySkillRuntime(model_client=bad_client)
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_OUTPUT_INVALID_JSON"


@pytest.mark.asyncio
async def test_runtime_redacts_model_output_before_returning_it():
    async def fake_client(system_prompt, user_prompt, config):
        return _valid_output(
            decision="Authorization: Bearer sk-live-secret",
            findings=[{"api_key": "sk-hidden"}, "full system prompt: do not expose"],
            recommendations=["safe"],
            required_changes=["Bearer token leaked"],
            evidence=[{"nested": {"Authorization": "Bearer hidden"}}],
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={},
        runtime_config=_runtime_config(),
    )

    serialized = json.dumps({"summary": result.output_summary, "evidence": result.evidence})
    assert "sk-live-secret" not in serialized
    assert "sk-hidden" not in serialized
    assert "Bearer hidden" not in serialized
    assert "full system prompt" not in serialized
    assert result.output_summary["recommendations"] == ["safe"]


@pytest.mark.asyncio
async def test_runtime_redacts_bare_configured_secret_values_from_model_output():
    bare_api_key = "sk-runtime-secret-123"

    async def fake_client(system_prompt, user_prompt, config):
        return _valid_output(
            decision=f"provider returned {bare_api_key}",
            findings=[f"captured credential {bare_api_key}"],
            evidence=[{"nested": {"raw": bare_api_key}}],
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={},
        runtime_config={
            **_runtime_config(),
            "api_key": bare_api_key,
        },
    )

    serialized = json.dumps({"summary": result.output_summary, "evidence": result.evidence})
    assert bare_api_key not in serialized
    assert "[REDACTED]" in serialized


@pytest.mark.asyncio
async def test_runtime_maps_model_timeout_to_named_error():
    async def timeout_client(system_prompt, user_prompt, config):
        raise httpx.TimeoutException("timeout")

    runtime = AgencySkillRuntime(model_client=timeout_client)
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_MODEL_TIMEOUT"


@pytest.mark.asyncio
async def test_default_client_sends_openai_compatible_request_payload_headers_and_url():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["authorization"]
        seen["content_type"] = request.headers["content-type"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": _valid_output()}}],
                "usage": {"total_tokens": 77},
            },
        )

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={"frame_count": 3},
        runtime_config={
            **_runtime_config(),
            "provider": "ark",
            "base_url": "https://model.test/v1/chat/completions",
        },
    )

    assert result.result_status == "passed"
    assert result.token_usage == {"total_tokens": 77}
    assert seen["url"] == "https://model.test/v1/chat/completions"
    assert seen["authorization"] == "Bearer secret-key"
    assert seen["content_type"] == "application/json"
    assert seen["payload"]["model"] == "mock-model"
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert seen["payload"]["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_default_client_accepts_openai_chat_completions_protocol():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": _valid_output()}}]})

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={},
        runtime_config={
            **_runtime_config(),
            "provider": "custom",
            "config": {**_runtime_config()["config"], "protocol": "openai_chat_completions"},
        },
    )

    assert result.result_status == "passed"


@pytest.mark.asyncio
async def test_default_client_accepts_bailian_chat_completion_provider():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": _valid_output()}}]})

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={},
        runtime_config={
            **_runtime_config(),
            "provider": "bailian",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "config": {
                **_runtime_config()["config"],
                "max_tokens": 8192,
            },
        },
    )

    assert result.result_status == "passed"
    assert seen["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert seen["payload"]["model"] == "qwen-plus"
    assert seen["payload"]["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_default_client_rejects_unsupported_provider_before_http_call():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config={**_runtime_config(), "provider": "anthropic"},
        )

    assert exc.value.error_code == "EXPERT_MODEL_PROVIDER_UNSUPPORTED"
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_code"),
    [(429, "EXPERT_MODEL_RATE_LIMITED"), (500, "EXPERT_MODEL_HTTP_ERROR")],
)
async def test_default_client_maps_rate_limit_and_http_error_to_named_errors(status_code, error_code):
    def handler(request):
        return httpx.Response(status_code, request=request)

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == error_code


@pytest.mark.asyncio
async def test_default_client_wraps_non_json_provider_response():
    def handler(request):
        return httpx.Response(200, text="not json")

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_MODEL_HTTP_ERROR"


@pytest.mark.asyncio
async def test_default_client_wraps_missing_choices_body_shape():
    def handler(request):
        return httpx.Response(200, json={"choices": []})

    runtime = AgencySkillRuntime(http_transport=httpx.MockTransport(handler))
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_MODEL_HTTP_ERROR"
