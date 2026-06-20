from app.domains.pixelle_integration.pixelle_router import _redact_secrets


def test_redact_secrets_recursively_redacts_nested_api_keys():
    config = {
        "llm": {"api_key": "llm-secret"},
        "ai_models": {
            "scenes": {
                "image_generation": {
                    "provider": "seedance",
                    "api_key": "image-secret",
                    "nested": {"api_secret": "nested-secret"},
                }
            }
        },
    }

    redacted = _redact_secrets(config)

    assert redacted["llm"]["api_key"] != "llm-secret"
    assert redacted["ai_models"]["scenes"]["image_generation"]["api_key"] != "image-secret"
    assert redacted["ai_models"]["scenes"]["image_generation"]["nested"]["api_secret"] != "nested-secret"
    assert config["ai_models"]["scenes"]["image_generation"]["api_key"] == "image-secret"
