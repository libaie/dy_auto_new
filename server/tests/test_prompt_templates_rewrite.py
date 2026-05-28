from contextlib import nullcontext
import copy
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db_models import PromptTemplate, SystemSetting
from app.deps import verify_admin_token
from app.main import app
from app.services.prompt_template_service import prompt_template_service


@pytest.fixture(autouse=True)
def clean_prompt_template_rewrite_rows(db):
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
            "sentiments": ["neutral"],
            "scoringRules": ["consult = 40"],
            "replyRules": ["reply naturally"],
            "replyExample": {"good": "I can share a simple idea.", "bad": "No."},
            "tiers": {"consult": "helpful and warm"},
        },
        "videoComment": {
            "context": "comment under a short video",
            "goal": "attract qualified viewers",
            "rules": ["be useful"],
        },
        "dmOpener": {
            "context": "first private message",
            "identity": {"role": "advisor"},
            "goal": "start a conversation",
            "style": ["warm"],
            "tierTones": {"consult": "gentle"},
        },
        "dmStages": {
            "qualifying": {"name": "Qualify", "goal": "understand need", "style": "plain", "maxTokens": 150},
            "nurturing": {"name": "Nurture", "goal": "build trust", "style": "specific", "maxTokens": 200},
            "converting": {"name": "Convert", "goal": "guide next step", "style": "calm", "maxTokens": 150},
            "follow_up": {"name": "Follow up", "goal": "check back", "style": "light", "maxTokens": 120},
        },
        "localFilter": {"exclude": ["game"], "include": ["health"]},
    }


def rewritten_template_content():
    content = copy.deepcopy(valid_template_content())
    content["analysis"]["replyRules"] = ["reply with a warmer tone"]
    return content


def sse_events(response):
    events = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_rewrite_requires_admin_role():
    client = TestClient(app)
    app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "operator")
    try:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")

    assert response.status_code == 403


def test_rewrite_valid_ai_json_emits_done_without_persistence(db):
    db.add(
        PromptTemplate(
            name="health-default",
            industry="health",
            description="existing",
            content=valid_template_content(),
            version=1,
        )
    )
    db.add(SystemSetting(key="prompt_templates_revision", value="7"))
    db.commit()

    async def fake_stream(*args, **kwargs):
        yield json.dumps(rewritten_template_content())

    client = TestClient(app)
    with (
        patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={"api_key": "test-key"}) as cfg,
        patch("app.routers.prompt_templates.SessionLocal", return_value=nullcontext(db)),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", fake_stream),
        patch("app.ws_manager.pair_ws_manager.broadcast_to_devices", new=AsyncMock()) as broadcast_devices,
        patch("app.ws_manager.pair_ws_manager.broadcast_to_admins", new=AsyncMock()) as broadcast_admins,
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "done"
    assert events[-1]["content"]["analysis"]["replyRules"] == ["reply with a warmer tone"]
    cfg.assert_called_once_with(db)
    existing = db.query(PromptTemplate).filter(PromptTemplate.name == "health-default").one()
    assert existing.version == 1
    revision = db.query(SystemSetting).filter(SystemSetting.key == "prompt_templates_revision").one()
    assert revision.value == "7"
    broadcast_devices.assert_not_called()
    broadcast_admins.assert_not_called()


def test_rewrite_invalid_current_content_returns_error_before_ai():
    content = valid_template_content()
    del content["analysis"]["replyRules"]

    client = TestClient(app)
    with patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "content": content, "instruction": "make warmer"},
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


def test_rewrite_preflight_validation_does_not_log_content_sentinel(caplog):
    sentinel = "SECRET_PROMPT_SENTINEL"
    content = valid_template_content()
    content["analysis"]["replyExample"]["good"] = f"comment -> reply {sentinel}"

    client = TestClient(app)
    caplog.set_level(logging.WARNING, logger="app.routers.prompt_templates")
    with (
        patch(
            "app.routers.prompt_templates.prompt_template_service.validate_rewrite_request",
            side_effect=ValueError(f"invalid template text {sentinel}"),
        ),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream,
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "content": content, "instruction": "make warmer"},
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    assert sentinel in events[-1]["message"]
    assert sentinel not in caplog.text
    stream.assert_not_called()


def test_rewrite_long_instruction_returns_error_before_ai():
    client = TestClient(app)
    with patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "x" * 2001,
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


def test_rewrite_missing_content_returns_error_before_ai():
    client = TestClient(app)
    with patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "instruction": "make warmer"},
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


def test_rewrite_missing_instruction_returns_error_before_ai():
    client = TestClient(app)
    with patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config") as stream:
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={"industry": "health", "content": valid_template_content()},
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    stream.assert_not_called()


def test_rewrite_ai_invalid_json_emits_error(db):
    async def fake_stream(*args, **kwargs):
        yield "{not-json"

    client = TestClient(app)
    with (
        patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={"api_key": "test-key"}),
        patch("app.routers.prompt_templates.SessionLocal", return_value=nullcontext(db)),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", fake_stream),
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"


def test_rewrite_generic_stream_failure_does_not_log_sentinel(db, caplog):
    sentinel = "SECRET_PROVIDER_SENTINEL"

    async def fake_stream(*args, **kwargs):
        if False:
            yield ""
        raise RuntimeError(f"provider failed {sentinel}")

    client = TestClient(app)
    caplog.set_level(logging.ERROR, logger="app.routers.prompt_templates")
    with (
        patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={"api_key": "test-key"}),
        patch("app.routers.prompt_templates.SessionLocal", return_value=nullcontext(db)),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", fake_stream),
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    assert sentinel in events[-1]["message"]
    assert sentinel not in caplog.text


def test_rewrite_ai_invalid_template_emits_error_not_warning(db):
    invalid = rewritten_template_content()
    del invalid["semanticGuide"]["highValueSignals"]

    async def fake_stream(*args, **kwargs):
        yield json.dumps(invalid)

    client = TestClient(app)
    with (
        patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={"api_key": "test-key"}),
        patch("app.routers.prompt_templates.SessionLocal", return_value=nullcontext(db)),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", fake_stream),
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert "warning" not in {event["type"] for event in events}
    assert events[-1]["type"] == "error"


def test_rewrite_ai_incomplete_scenario_template_emits_error_not_done(db):
    invalid = rewritten_template_content()
    del invalid["videoComment"]

    async def fake_stream(*args, **kwargs):
        yield json.dumps(invalid)

    client = TestClient(app)
    with (
        patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={"api_key": "test-key"}),
        patch("app.routers.prompt_templates.SessionLocal", return_value=nullcontext(db)),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", fake_stream),
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert "done" not in {event["type"] for event in events}
    assert events[-1]["type"] == "error"
    assert "videoComment" in events[-1]["message"]


def test_rewrite_output_validation_does_not_log_content_sentinel(db, caplog):
    sentinel = "SECRET_REWRITE_SENTINEL"
    invalid = rewritten_template_content()
    invalid["analysis"]["replyExample"]["good"] = f"comment -> reply {sentinel}"

    async def fake_stream(*args, **kwargs):
        yield json.dumps(invalid)

    client = TestClient(app)
    caplog.set_level(logging.WARNING, logger="app.routers.prompt_templates")
    with (
        patch("app.routers.prompt_templates.get_ai_config_with_key", return_value={"api_key": "test-key"}),
        patch("app.routers.prompt_templates.SessionLocal", return_value=nullcontext(db)),
        patch("app.routers.prompt_templates.gen.generate_custom_stream_with_config", fake_stream),
        patch(
            "app.routers.prompt_templates.prompt_template_service.validate_rewrite_output",
            side_effect=ValueError(f"invalid rewritten text {sentinel}"),
        ),
    ):
        response = client.post(
            "/api/prompt-templates/rewrite-stream",
            json={
                "industry": "health",
                "content": valid_template_content(),
                "instruction": "make warmer",
            },
        )

    events = sse_events(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    assert sentinel in events[-1]["message"]
    assert sentinel not in caplog.text
