import json

from app.domains.quality_audit.audit_router import _audit_openai_compatible


class _AuditResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"score": 0.96, "pass": true, "issues": []}'
                    }
                }
            ]
        }


def test_bailian_qwen_runtime_model_uses_text_only_audit_payload(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        captured["timeout"] = timeout
        return _AuditResponse()

    monkeypatch.setattr("app.domains.quality_audit.audit_router.httpx.post", fake_post)

    result = _audit_openai_compatible(
        {
            "provider": "bailian",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "secret",
            "model": "qwen3.7-plus",
            "config": {"max_tokens": 8192, "temperature": 0.1},
        },
        "D:/codex/dy_auto_new/server/output/video-production/final.mp4",
        "- 画面质量\n- 内容安全",
        "只返回 JSON",
    )

    payload = captured["payload"]
    user_content = payload["messages"][1]["content"]
    serialized_content = json.dumps(user_content, ensure_ascii=False)

    assert result["pass_fail"] is True
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert payload["model"] == "qwen3.7-plus"
    assert payload["max_tokens"] == 8192
    assert payload["temperature"] == 0.1
    assert "image_url" not in serialized_content
    assert "final.mp4" in serialized_content


def test_vision_enabled_openai_model_keeps_image_url_payload(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["payload"] = json
        return _AuditResponse()

    monkeypatch.setattr("app.domains.quality_audit.audit_router.httpx.post", fake_post)

    _audit_openai_compatible(
        {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "secret",
            "model_name": "gpt-4o",
            "config_json": {"supports_vision_audit": True},
        },
        "https://cdn.test/frame.png",
        "- 构图",
        "只返回 JSON",
    )

    user_content = captured["payload"]["messages"][1]["content"]

    assert captured["payload"]["model"] == "gpt-4o"
    assert any(part.get("type") == "image_url" for part in user_content)
