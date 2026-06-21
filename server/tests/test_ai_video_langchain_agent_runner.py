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
