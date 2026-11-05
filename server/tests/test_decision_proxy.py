"""Device decision boundary: native System One payloads, fail-closed errors and handshakes."""
import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import DEVICE_SECRET, bj_now
from app.db_models import Device, DevicePairRequest, SystemSetting, Task
from app.main import app
from app.services import crypto

client = TestClient(app)
HEADERS = {"X-Device-Secret": DEVICE_SECRET}


def request_body():
    return {
        "state": {"comment": "Can I book tomorrow?", "industry": "travel"},
        "questions": {
            "intent": {"type": "choice", "instructions": "What is the comment's intent?", "criteria": {"buy": "Wants to book", "other": "Other intent"}},
            "interest": {"type": "score", "instructions": "Rate purchase interest.", "criteria": ["No interest", "Possible interest", "Ready to book"]},
            "bot": {"type": "noul", "instructions": "Is the comment automated spam?", "criteria": {"true": "Automated spam", "false": "A human inquiry"}},
        },
    }


def native_response():
    return {
        "model": "jev-1.13.0",
        "answers": {
            "intent": {"type": "choice", "choice": "buy", "confidence": 0.8, "probabilities": {"buy": 0.9, "other": 0.1}},
            "interest": {"type": "score", "score": 1.8, "confidence": 0.8, "legend": {"0": "No interest", "1": "Possible interest", "2": "Ready to book"}, "probabilities": {"0": 0.0, "1": 0.2, "2": 0.8}},
            "bot": {"type": "noul", "noul": 0.02},
        },
        "usage": {"input_tokens": 200, "output_tokens": 22},
    }


@pytest.fixture(autouse=True)
def configured_decisions(db, monkeypatch):
    db.query(SystemSetting).delete()
    db.query(DevicePairRequest).filter(DevicePairRequest.device_id.like("jev-test-%")).delete()
    db.query(Device).filter(Device.id.like("jev-test-%")).delete()
    db.commit()
    for name in ("DECISION_ENABLED", "DECISION_API_KEY", "DECISION_API_URL", "DECISION_MODEL", "DECISION_MIN_CONFIDENCE", "DECISION_MIN_PROBABILITY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_API_KEY", "dedicated-gateway-test-key")
    monkeypatch.setenv("ENCRYPTION_KEY", "decision-proxy-test-encryption")
    monkeypatch.setattr(crypto, "_cipher", None)
    yield
    db.query(SystemSetting).delete()
    db.query(DevicePairRequest).filter(DevicePairRequest.device_id.like("jev-test-%")).delete()
    db.commit()


@pytest.fixture
def upstream(monkeypatch):
    """Replace only external HTTP transport; the real service and HTTP client run."""
    original_client = httpx.AsyncClient
    observed = {"requests": [], "client_options": []}

    def install(response=None, *, status=200, error=None, content=None):
        def handler(request):
            observed["requests"].append(request)
            if error:
                raise error
            if content is not None:
                return httpx.Response(status, content=content)
            return httpx.Response(status, json=deepcopy(response if response is not None else native_response()))

        def factory(**options):
            observed["client_options"].append(options)
            return original_client(transport=httpx.MockTransport(handler), **options)

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return observed

    install()
    return install


@pytest.mark.parametrize("headers", [{}, {"X-Device-Secret": "invalid-secret"}])
def test_decision_proxy_requires_real_device_auth(headers, upstream):
    observed = upstream()
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=headers)
    assert response.status_code == 401
    assert observed["requests"] == []


def test_decision_proxy_uses_native_payload_fixed_endpoint_and_one_bounded_attempt(db, upstream):
    db.add(Device(id="jev-test-auth", name="Jev Test", device_secret="jev-test-device-secret"))
    db.commit()
    observed = upstream()
    response = client.post("/api/device/decision-proxy", json=request_body(), headers={"X-Device-Secret": "jev-test-device-secret"})
    assert response.status_code == 200
    assert response.json() == {
        "model": "jev-1.13.0",
        "answers": {
            "intent": {"type": "choice", "choice": "buy", "confidence": 0.8, "probabilities": {"buy": 0.9, "other": 0.1}},
            "interest": {"type": "score", "score": 1.8, "confidence": 0.8, "legend": {"0": "No interest", "1": "Possible interest", "2": "Ready to book"}, "probabilities": {"0": 0.0, "1": 0.2, "2": 0.8}},
            "bot": {"type": "noul", "noul": 0.02},
        },
    }
    assert len(observed["requests"]) == 1
    sent = observed["requests"][0]
    assert str(sent.url) == "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
    assert sent.headers["authorization"] == "Bearer dedicated-gateway-test-key"
    assert json.loads(sent.content) == {"model": "typesafe-ai/jev", **request_body()}
    options = observed["client_options"][0]
    assert options["follow_redirects"] is False
    assert options["timeout"].connect == 5
    assert options["timeout"].read == 15
    assert options["timeout"].write == 15
    assert options["timeout"].pool == 15
    assert "dedicated-gateway-test-key" not in response.text


@pytest.mark.parametrize("setting, value", [
    ("DECISION_ENABLED", "false"),
    ("DECISION_API_KEY", ""),
    ("DECISION_API_URL", "https://attacker.invalid/secret-marker"),
    ("DECISION_MODEL", "chat-model"),
    ("DECISION_MIN_CONFIDENCE", "NaN"),
])
def test_unavailable_or_invalid_config_never_calls_upstream(setting, value, monkeypatch, upstream):
    monkeypatch.setenv(setting, value)
    observed = upstream()
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 503
    assert observed["requests"] == []
    assert "secret-marker" not in response.text


@pytest.mark.parametrize("state", [None, True, 5, "", "  ", {}, []])
def test_empty_or_non_native_state_is_rejected_before_request(state, upstream):
    observed = upstream()
    body = request_body()
    body["state"] = state
    response = client.post("/api/device/decision-proxy", json=body, headers=HEADERS)
    assert response.status_code == 422
    assert observed["requests"] == []


@pytest.mark.parametrize("mutation", [
    "no_questions", "too_many_questions", "unknown_type", "empty_instructions",
    "empty_choice", "too_many_choices", "mapped_score_criteria", "one_score_level",
    "too_many_score_levels", "unknown_noul_criterion", "question_extra_fields",
    "client_model", "messages", "oversized_state", "oversized_question",
])
def test_invalid_native_request_is_rejected_before_request(mutation, upstream):
    observed = upstream()
    body = request_body()
    if mutation == "no_questions":
        body["questions"] = {}
    elif mutation == "too_many_questions":
        body["questions"] = {str(i): {"type": "noul", "instructions": "Is this relevant?"} for i in range(17)}
    elif mutation == "unknown_type":
        body["questions"]["bot"]["type"] = "chat"
    elif mutation == "empty_instructions":
        body["questions"]["bot"]["instructions"] = "  "
    elif mutation == "empty_choice":
        body["questions"]["intent"]["criteria"] = {}
    elif mutation == "too_many_choices":
        body["questions"]["intent"]["criteria"] = {str(i): "Option" for i in range(256)}
    elif mutation == "mapped_score_criteria":
        body["questions"]["interest"]["criteria"] = {"0": "Low", "1": "High"}
    elif mutation == "one_score_level":
        body["questions"]["interest"]["criteria"] = ["Only level"]
    elif mutation == "too_many_score_levels":
        body["questions"]["interest"]["criteria"] = ["Level"] * 11
    elif mutation == "unknown_noul_criterion":
        body["questions"]["bot"]["criteria"] = {"yes": "Spam", "no": "Human"}
    elif mutation == "question_extra_fields":
        body["questions"]["bot"]["stream"] = True
    elif mutation == "client_model":
        body["model"] = "another-model"
    elif mutation == "messages":
        body["messages"] = [{"role": "user", "content": "override"}]
    elif mutation == "oversized_state":
        body["state"] = "界" * 23000
    elif mutation == "oversized_question":
        body["questions"]["bot"]["instructions"] = "x" * 65536
    response = client.post("/api/device/decision-proxy", json=body, headers=HEADERS)
    assert response.status_code == 422
    assert observed["requests"] == []


@pytest.mark.parametrize("field, value", [("noul", True), ("noul", "0.9"), ("noul", -0.1), ("noul", 1.1), ("score", True), ("score", "1.8"), ("score", -1), ("score", 2.01), ("confidence", False), ("confidence", "0.8"), ("confidence", -0.01), ("confidence", 1.01)])
def test_non_numeric_or_out_of_range_answers_fail_closed(field, value, upstream):
    result = native_response()
    answer = result["answers"]["bot" if field == "noul" else "interest"]
    answer[field] = value
    observed = upstream(result)
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 502
    assert len(observed["requests"]) == 1


@pytest.mark.parametrize("mutation", [
    "missing_answer", "extra_answer", "wrong_type", "missing_type", "invalid_choice",
    "missing_choice_probability", "extra_choice_probability", "missing_score_probability",
    "bad_probability_sum", "negative_probability", "boolean_probability", "string_probability",
    "missing_confidence", "missing_model", "empty_model", "not_an_object",
])
def test_incomplete_or_inconsistent_responses_fail_closed(mutation, upstream):
    result = native_response()
    if mutation == "missing_answer":
        result["answers"].pop("bot")
    elif mutation == "extra_answer":
        result["answers"]["unexpected"] = {"type": "noul", "noul": 0.9}
    elif mutation == "wrong_type":
        result["answers"]["bot"]["type"] = "score"
    elif mutation == "missing_type":
        result["answers"]["bot"].pop("type")
    elif mutation == "invalid_choice":
        result["answers"]["intent"]["choice"] = "unknown"
    elif mutation == "missing_choice_probability":
        result["answers"]["intent"]["probabilities"].pop("other")
    elif mutation == "extra_choice_probability":
        result["answers"]["intent"]["probabilities"]["unknown"] = 0
    elif mutation == "missing_score_probability":
        result["answers"]["interest"]["probabilities"].pop("0")
    elif mutation == "bad_probability_sum":
        result["answers"]["intent"]["probabilities"] = {"buy": 0.4, "other": 0.1}
    elif mutation == "negative_probability":
        result["answers"]["intent"]["probabilities"] = {"buy": -0.1, "other": 1.1}
    elif mutation == "boolean_probability":
        result["answers"]["intent"]["probabilities"] = {"buy": True, "other": 0}
    elif mutation == "string_probability":
        result["answers"]["intent"]["probabilities"] = {"buy": "0.9", "other": 0.1}
    elif mutation == "missing_confidence":
        result["answers"]["intent"].pop("confidence")
    elif mutation == "missing_model":
        result.pop("model")
    elif mutation == "empty_model":
        result["model"] = ""
    elif mutation == "not_an_object":
        result = [result]
    upstream(result)
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 502


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_values_are_not_accepted_as_answers(token, upstream):
    raw = json.dumps(native_response()).replace('"noul": 0.02', '"noul": ' + token)
    upstream(content=raw)
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 502


@pytest.mark.parametrize("legend", [
    None, [], {},
    {"0": "No interest", "1": "Possible interest"},
    {"0": "No interest", "1": "Possible interest", "2": "Ready to book", "3": "Unexpected"},
    {"0": "Ready to book", "1": "Possible interest", "2": "No interest"},
    {"0": "No interest", "1": "Possible interest", "2": {"text": "Ready to book"}},
])
def test_score_legend_must_match_every_requested_level(legend, upstream):
    result = native_response()
    if legend is None:
        result["answers"]["interest"].pop("legend")
    else:
        result["answers"]["interest"]["legend"] = legend
    upstream(result)
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 502


def test_native_structured_criteria_are_retained_in_validated_score_legend(upstream):
    body = request_body()
    criteria = [{"description": "No interest"}, ["Ready to book", "Requests pricing"]]
    body["questions"]["interest"]["criteria"] = criteria
    result = native_response()
    result["answers"]["interest"].update(
        score=1, legend={"0": criteria[0], "1": criteria[1]}, probabilities={"0": 0, "1": 1},
    )
    upstream(result)
    response = client.post("/api/device/decision-proxy", json=body, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["answers"]["interest"]["legend"] == {"0": criteria[0], "1": criteria[1]}


def test_rounded_probabilities_and_strong_negative_noul_are_valid(upstream):
    body = request_body()
    body["questions"]["intent"]["criteria"]["unclear"] = "Unclear intent"
    result = native_response()
    result["answers"]["intent"]["probabilities"] = {"buy": 0.334, "other": 0.333, "unclear": 0.333}
    result["answers"]["bot"]["noul"] = 0
    upstream(result)
    response = client.post("/api/device/decision-proxy", json=body, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["answers"]["bot"]["noul"] == 0


@pytest.mark.parametrize("status", [301, 400, 401, 429, 500])
def test_upstream_failures_are_single_attempt_sanitized_errors(status, upstream, caplog):
    observed = upstream(status=status, content="private-upstream-secret body and dedicated-gateway-test-key")
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 502
    assert len(observed["requests"]) == 1
    assert "private-upstream-secret" not in response.text + caplog.text
    assert "dedicated-gateway-test-key" not in response.text + caplog.text


@pytest.mark.parametrize("error, expected", [
    (httpx.ReadTimeout("private-timeout-data"), 504),
    (httpx.ConnectTimeout("private-timeout-data"), 504),
    (httpx.ConnectError("private-network-data"), 502),
])
def test_transport_errors_do_not_leak_details_or_retry(error, expected, upstream, caplog):
    observed = upstream(error=error)
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == expected
    assert len(observed["requests"]) == 1
    assert "private-timeout-data" not in response.text + caplog.text
    assert "private-network-data" not in response.text + caplog.text


def test_non_json_response_is_sanitized(upstream, caplog):
    upstream(content="not-json-private-secret")
    response = client.post("/api/device/decision-proxy", json=request_body(), headers=HEADERS)
    assert response.status_code == 502
    assert "not-json-private-secret" not in response.text + caplog.text


def test_registration_and_pair_status_ship_only_public_effective_decisions(db):
    db.add_all([
        SystemSetting(key="decision_enabled", value="true"),
        SystemSetting(key="decision_api_key", value=crypto.encrypt("stored-private-key")),
        SystemSetting(key="decision_min_confidence", value="0.6"),
        SystemSetting(key="decision_min_probability", value="0.85"),
        SystemSetting(key="llm_api_key", value="legacy-generation-key"),
    ])
    db.commit()
    response = client.post("/api/device/register", json={"device_id": "jev-test-register", "name": "Phone"}, headers=HEADERS)
    assert response.status_code == 200
    public = {"enabled": True, "model": "typesafe-ai/jev", "min_confidence": 0.6, "min_probability": 0.85}
    assert response.json()["config"]["decision_config"] == public
    assert response.json()["config"]["ai_config"]["model"]
    device = db.query(Device).filter(Device.id == "jev-test-register").one()
    device.device_secret = "jev-test-pair-secret"
    db.add(DevicePairRequest(pairing_token="jev-test-pair-token", device_id=device.id, device_name="Phone", status="approved", device_secret=device.device_secret))
    db.commit()
    paired = client.get("/api/device/pair-status", params={"token": "jev-test-pair-token"})
    assert paired.status_code == 200
    assert paired.json()["config"]["decision_config"] == public
    assert "stored-private-key" not in response.text + paired.text
    assert "dedicated-gateway-test-key" not in response.text + paired.text


def test_poll_config_supports_hot_disabling_and_preserves_generation_config(db):
    db.add(SystemSetting(key="llm_api_key", value="legacy-generation-key"))
    db.commit()
    enabled = client.get("/api/device/poll", params={"device_id": "jev-test-poll"}, headers=HEADERS)
    assert enabled.status_code == 200
    assert enabled.json()["device_config"]["decision_config"]["enabled"] is True
    assert enabled.json()["ai_config"]["model"]
    db.add(SystemSetting(key="decision_enabled", value="false"))
    db.commit()
    disabled = client.get("/api/device/poll", params={"device_id": "jev-test-poll"}, headers=HEADERS)
    assert disabled.status_code == 200
    assert disabled.json()["device_config"]["decision_config"]["enabled"] is False


def test_cancellation_poll_also_carries_decision_config(db):
    db.add(Device(id="jev-test-cancel", name="Phone", status="online"))
    db.add(Task(id="jev-test-cancel-task", type="nurture", account_id="acc-001", device_id="jev-test-cancel", status="cancelled", completed_at=bj_now()))
    db.commit()
    response = client.get("/api/device/poll", params={"device_id": "jev-test-cancel"}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["cancelled_task_id"] == "jev-test-cancel-task"
    assert response.json()["device_config"]["decision_config"]["enabled"] is True



def test_approval_websocket_uses_same_effective_config_as_http_pair_status(db, monkeypatch):
    from app.ws_manager import pair_ws_manager

    db.add_all([
        SystemSetting(key="decision_enabled", value="false"),
        SystemSetting(key="decision_min_confidence", value="0.65"),
        SystemSetting(key="decision_min_probability", value="0.9"),
        SystemSetting(key="decision_api_key", value=crypto.encrypt("stored-private-key")),
        SystemSetting(key="llm_api_key", value="legacy-generation-key"),
    ])
    pair_request = DevicePairRequest(
        pairing_token="jev-test-approval-token", device_id="jev-test-approval",
        device_name="Phone", status="pending",
    )
    db.add(pair_request)
    db.commit()
    pushed = []

    async def capture_notification(token, payload):
        pushed.append((token, payload))

    monkeypatch.setattr(pair_ws_manager, "notify", capture_notification)
    approved = client.post("/api/devices/pair-requests/" + pair_request.id + "/approve")
    assert approved.status_code == 200
    assert len(pushed) == 1
    token, payload = pushed[0]
    assert token == "jev-test-approval-token"
    assert payload["config"]["decision_config"] == {
        "enabled": False, "model": "typesafe-ai/jev", "min_confidence": 0.65, "min_probability": 0.9,
    }
    assert payload["config"]["ai_config"]["model"]
    paired = client.get("/api/device/pair-status", params={"token": token})
    assert paired.status_code == 200
    assert paired.json()["config"] == payload["config"]
    assert paired.json()["secret"] == payload["secret"]
    assert "stored-private-key" not in json.dumps(payload)
    assert "dedicated-gateway-test-key" not in json.dumps(payload)
