import json

import httpx
import openai
import pytest

from app.domains.agency_operations.agency_prompting import build_expert_prompt
from app.domains.agency_operations.agency_runtime import AgencyRuntimeError, AgencySkillRuntime


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
async def test_runtime_preserves_optional_creative_patches():
    async def fake_client(system_prompt, user_prompt, config):
        return _valid_output(
            decision="需要改稿",
            creative_patches=[{
                "patch_type": "storyboard_patch",
                "target_type": "storyboard_frame",
                "target_id": "shot-001",
                "stage": "storyboard",
                "title": "强化前三秒钩子",
                "reason": "冲突不够强。",
                "before": {"image_prompt": "原"},
                "after": {"image_prompt": "新"},
                "apply_policy": "requires_human_approval",
            }],
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={"frame_count": 1},
        runtime_config=_runtime_config(),
    )

    assert result.output_summary["creative_patches"][0]["patch_type"] == "storyboard_patch"


@pytest.mark.asyncio
async def test_runtime_preserves_optional_scorecard():
    async def fake_client(system_prompt, user_prompt, config):
        assert '"scorecard"' in system_prompt
        return _valid_output(
            decision="通过",
            scorecard={
                "overall_score": 91,
                "pass_threshold": 80,
                "verdict": "pass",
                "dimensions": [{"key": "continuity", "score": 91}],
            },
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="image_review_quality_reviewer",
        stage="image_review",
        role="qa",
        stage_context={"frame_count": 1},
        runtime_config=_runtime_config(),
    )

    assert result.output_summary["scorecard"]["overall_score"] == 91
    assert result.output_summary["scorecard"]["schema_version"] == "agency.scorecard.v1"


@pytest.mark.asyncio
async def test_runtime_can_send_multimodal_user_content():
    captured = {}

    async def fake_client(system_prompt, user_prompt, config):
        captured["user_prompt"] = user_prompt
        return _valid_output(decision="reviewed from image evidence")

    runtime = AgencySkillRuntime(model_client=fake_client)
    await runtime.invoke(
        db=None,
        expert_id="image_review_quality_reviewer",
        stage="image_review",
        role="qa",
        stage_context={
            "asset_review": {
                "media_inputs": [{"type": "image_url", "url": "https://cdn.test/shot.png"}],
                "prompt": "original image prompt",
            }
        },
        runtime_config=_runtime_config(),
    )

    assert "https://cdn.test/shot.png" in str(captured["user_prompt"])


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
            decision="Authorization: Bearer live-secret-token",
            findings=[{"api_key": "hidden-secret-token"}, "full system prompt: do not expose"],
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
    assert "live-secret-token" not in serialized
    assert "hidden-secret-token" not in serialized
    assert "Bearer hidden" not in serialized
    assert "full system prompt" not in serialized
    assert result.output_summary["recommendations"] == ["safe"]


@pytest.mark.asyncio
async def test_runtime_redacts_bare_configured_secret_values_from_model_output():
    bare_api_key = "runtime-secret-token-123"

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
async def test_runtime_maps_injected_model_http_status_to_named_error():
    request = httpx.Request("POST", "https://model.test")
    response = httpx.Response(429, request=request)

    async def status_client(system_prompt, user_prompt, config):
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    runtime = AgencySkillRuntime(model_client=status_client)
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_MODEL_RATE_LIMITED"


@pytest.mark.asyncio
async def test_runtime_maps_injected_model_request_error_to_named_error():
    async def request_error_client(system_prompt, user_prompt, config):
        raise httpx.RequestError("network failed")

    runtime = AgencySkillRuntime(model_client=request_error_client)
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
async def test_runtime_maps_langchain_rate_limit_to_named_error():
    request = httpx.Request("POST", "https://model.test")
    response = httpx.Response(429, request=request)

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            raise openai.RateLimitError("rate limited", response=response, body=None)

    runtime = AgencySkillRuntime(agent_runner=FakeRunner())
    with pytest.raises(AgencyRuntimeError) as exc:
        await runtime.invoke(
            db=None,
            expert_id="prompt_engineer",
            stage="storyboard",
            role="reviewer",
            stage_context={},
            runtime_config=_runtime_config(),
        )

    assert exc.value.error_code == "EXPERT_MODEL_RATE_LIMITED"


@pytest.mark.asyncio
async def test_runtime_maps_langchain_timeout_to_named_error():
    request = httpx.Request("POST", "https://model.test")

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            raise openai.APITimeoutError(request)

    runtime = AgencySkillRuntime(agent_runner=FakeRunner())
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
async def test_runtime_uses_langchain_runner_for_expert_output():
    captured = {}

    class FakeRunner:
        async def run_json(self, *, system_prompt, user_prompt, runtime_config, tools):
            captured["runtime_config"] = runtime_config
            captured["tools"] = [tool.name for tool in tools]
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
    assert "validate_json" in captured["tools"]
