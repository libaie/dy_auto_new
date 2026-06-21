from pathlib import Path


DOMAINS = Path(__file__).resolve().parents[1] / "app/domains"
HTTP_BOUNDARY_ALLOW = {
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

def test_model_connection_check_uses_langchain_tool():
    text = (DOMAINS / "model_configuration/ai_models_router.py").read_text(encoding="utf-8")

    assert "@tool\ndef model_connection_check" in text
    route_body = text.split("def test_connection", 1)[1]
    assert "model_connection_check.invoke" in route_body
    assert "httpx.get(" not in route_body


def test_seedance_submit_and_query_routes_use_langchain_tools():
    text = (DOMAINS / "seedance_integration/seedance_router.py").read_text(encoding="utf-8")

    assert "@tool\nasync def submit_seedance_generation" in text
    assert "@tool\nasync def query_seedance_task" in text
    generate_body = text.split('async def seedance_generate', 1)[1].split('async def seedance_get_task', 1)[0]
    query_body = text.split('async def seedance_get_task', 1)[1].split('proxy_router =', 1)[0]
    assert "submit_seedance_generation.ainvoke" in generate_body
    assert "query_seedance_task.ainvoke" in query_body
    assert "client.post(" not in generate_body
    assert "client.get(" not in query_body


def test_pixelle_router_provider_actions_use_langchain_tools():
    text = (DOMAINS / "pixelle_integration/pixelle_router.py").read_text(encoding="utf-8")

    assert "@tool\nasync def reload_pixelle_config" in text
    assert "@tool\nasync def pixelle_openapi_probe" in text
    update_body = text.split("async def update_pixelle_config", 1)[1].split("# ---- Template", 1)[0]
    test_body = text.split("async def test_connection", 1)[1].split("# ---- 透明代理", 1)[0]
    assert "reload_pixelle_config.ainvoke" in update_body
    assert "pixelle_openapi_probe.ainvoke" in test_body
    assert "client.post(" not in update_body
    assert "client.get(" not in test_body


def test_pixelle_unified_request_uses_langchain_tool_boundary():
    text = (DOMAINS / "pixelle_integration/pixelle_client.py").read_text(encoding="utf-8")

    assert "@tool\nasync def pixelle_provider_request" in text
    wrapper = text.split("async def _pixelle_request(", 1)[1]
    assert "pixelle_provider_request.ainvoke" in wrapper
    assert "_get_client()" not in wrapper
