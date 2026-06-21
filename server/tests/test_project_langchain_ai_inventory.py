from pathlib import Path


DOMAINS = Path(__file__).resolve().parents[1] / "app/domains"
HTTP_BOUNDARY_ALLOW = {
    "device_operations/content_bridge.py",
    "image_generation/image_creation_router.py",
    "image_generation/image_creation_service.py",
    "model_configuration/ai_models_router.py",
    "pixelle_integration/pixelle_client.py",
    "pixelle_integration/pixelle_router.py",
    "quality_audit/audit_router.py",
    "seedance_integration/seedance_router.py",
    "video_production/asset_storage_guard.py",
}
HTTP_NEEDLES = [
    "httpx.AsyncClient(",
    "httpx.post(",
    "httpx.get(",
    "httpx.stream(",
]


def _python_files():
    yield from DOMAINS.rglob("*.py")


def _rel(path: Path) -> str:
    return path.relative_to(DOMAINS).as_posix()


def test_shared_ai_generator_is_langchain_backed():
    text = (DOMAINS / "model_configuration/ai_generator.py").read_text(encoding="utf-8")

    assert "from langchain_openai import ChatOpenAI" in text
    assert "import httpx" not in text
    assert "AsyncClient" not in text
    assert "client.post(" not in text


def test_domains_do_not_post_direct_chat_completions():
    violations = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if "/chat/completions" in text and _rel(path) != "model_configuration/ai_generator.py":
            violations.append(_rel(path))

    assert violations == []


def test_direct_http_is_limited_to_provider_proxy_or_health_boundaries():
    violations = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in HTTP_NEEDLES) and _rel(path) not in HTTP_BOUNDARY_ALLOW:
            violations.append(_rel(path))

    assert violations == []


def test_gemini_audit_http_is_behind_langchain_tool():
    text = (DOMAINS / "quality_audit/audit_router.py").read_text(encoding="utf-8")

    assert "@tool\ndef gemini_audit_request" in text
    assert "gemini_audit_request.invoke" in text
    gemini_body = text.split("def _audit_gemini", 1)[1]
    assert "httpx.post(" not in gemini_body