from app.domains.quality_audit.audit_router import _audit_openai_compatible


class _AuditMessage:
    content = '{"score": 0.96, "pass": true, "issues": []}'


class _AuditModel:
    def __init__(self, captured):
        self.captured = captured

    def invoke(self, messages):
        self.captured["messages"] = messages
        return _AuditMessage()


def _patch_audit_model(monkeypatch, captured):
    def fake_create(self, cfg, **kwargs):
        captured["cfg"] = cfg
        captured["kwargs"] = kwargs
        return _AuditModel(captured)

    monkeypatch.setattr(
        "app.domains.quality_audit.audit_router.AiGeneratorService._create_chat_model",
        fake_create,
    )


def test_bailian_qwen_runtime_model_uses_text_only_audit_payload(monkeypatch):
    captured = {}
    _patch_audit_model(monkeypatch, captured)

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

    user_content = captured["messages"][1][1]

    assert result["pass_fail"] is True
    assert captured["cfg"]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured["cfg"]["model"] == "qwen3.7-plus"
    assert captured["kwargs"]["max_tokens"] == 8192
    assert captured["kwargs"]["temperature"] == 0.1
    assert "image_url" not in user_content
    assert "final.mp4" in user_content


def test_vision_enabled_openai_model_keeps_image_url_payload(monkeypatch):
    captured = {}
    _patch_audit_model(monkeypatch, captured)

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

    user_content = captured["messages"][1][1]

    assert captured["cfg"]["model"] == "gpt-4o"
    assert any(part.get("type") == "image_url" for part in user_content)
