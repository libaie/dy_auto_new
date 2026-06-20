from fastapi.routing import APIRoute

from app.main import app


EXPECTED_CONTENT_COLLECTION_HTTP_ROUTES = [
    ("/api/device/generate-content", ("POST",), "generate_content", "app.domains.device_operations.content_bridge.generate_content", ("get_db", "verify_device_secret")),
    ("/api/device/collect-report", ("POST",), "collect_report", "app.domains.device_operations.content_bridge.collect_report", ("get_db", "verify_device_secret")),
    ("/api/device/dm-claim-recipient", ("POST",), "dm_claim_recipient", "app.domains.device_operations.content_bridge.dm_claim_recipient", ("get_db", "verify_device_secret")),
    ("/api/device/dm-send-report", ("POST",), "dm_send_report", "app.domains.device_operations.content_bridge.dm_send_report", ("get_db", "verify_device_secret")),
    ("/api/device/dm-release-recipient", ("POST",), "dm_release_recipient", "app.domains.device_operations.content_bridge.dm_release_recipient", ("get_db", "verify_device_secret")),
    ("/api/device/comment-ai-reply", ("POST",), "save_comment_ai_reply", "app.domains.device_operations.content_bridge.save_comment_ai_reply", ("get_db", "verify_device_secret")),
    ("/api/device/user-profile", ("POST",), "save_user_profile", "app.domains.device_operations.content_bridge.save_user_profile", ("get_db", "verify_device_secret")),
    ("/api/device/user-avatar", ("POST",), "upload_user_avatar", "app.domains.device_operations.content_bridge.upload_user_avatar", ("get_db", "verify_device_secret")),
    ("/api/content/templates", ("POST",), "create_template", "app.domains.content_collection.content_router.create_template", ("get_db", "verify_admin_token")),
    ("/api/content/templates", ("GET",), "list_templates", "app.domains.content_collection.content_router.list_templates", ("get_db", "verify_admin_token")),
    ("/api/content/templates/{template_id}", ("GET",), "get_template", "app.domains.content_collection.content_router.get_template", ("get_db", "verify_admin_token")),
    ("/api/content/templates/{template_id}", ("PUT",), "update_template", "app.domains.content_collection.content_router.update_template", ("get_db", "verify_admin_token")),
    ("/api/content/templates/{template_id}", ("DELETE",), "delete_template", "app.domains.content_collection.content_router.delete_template", ("get_db", "verify_admin_token")),
    ("/api/content/sensitive-words", ("POST",), "add_sensitive_word", "app.domains.content_collection.content_router.add_sensitive_word", ("get_db", "verify_admin_token")),
    ("/api/content/sensitive-words", ("GET",), "list_sensitive_words", "app.domains.content_collection.content_router.list_sensitive_words", ("get_db", "verify_admin_token")),
    ("/api/content/sensitive-words/{word_id}", ("DELETE",), "delete_sensitive_word", "app.domains.content_collection.content_router.delete_sensitive_word", ("get_db", "verify_admin_token")),
    ("/api/content/generate", ("POST",), "generate_content", "app.domains.content_collection.content_router.generate_content", ("get_db", "verify_admin_token")),
    ("/api/content/generate-keywords", ("POST",), "generate_keywords", "app.domains.content_collection.content_router.generate_keywords", ("get_db", "verify_admin_token")),
    ("/api/content/generate-regex", ("POST",), "generate_regex", "app.domains.content_collection.content_router.generate_regex", ("get_db", "verify_admin_token")),
    ("/api/content/generate-clean-prompt", ("POST",), "generate_clean_prompt", "app.domains.content_collection.content_router.generate_clean_prompt", ("get_db", "verify_admin_token")),
    ("/api/data/comments", ("GET",), "list_comments", "app.domains.content_collection.data_router.list_comments", ("get_db", "verify_admin_token")),
    ("/api/data/users", ("GET",), "list_users", "app.domains.content_collection.data_router.list_users", ("get_db", "verify_admin_token")),
    ("/api/data/conversations", ("GET",), "list_conversations", "app.domains.content_collection.data_router.list_conversations", ("get_db", "verify_admin_token")),
    ("/api/data/conversations/{conversation_id}", ("GET",), "get_conversation", "app.domains.content_collection.data_router.get_conversation", ("get_db", "verify_admin_token")),
    ("/api/data/export/comments", ("GET",), "export_comments", "app.domains.content_collection.data_router.export_comments", ("get_db", "verify_admin_token")),
    ("/api/data/export/users", ("GET",), "export_users", "app.domains.content_collection.data_router.export_users", ("get_db", "verify_admin_token")),
    ("/api/data/export/conversations", ("GET",), "export_conversations", "app.domains.content_collection.data_router.export_conversations", ("get_db", "verify_admin_token")),
    ("/api/dm-sequences", ("GET",), "list_sequences", "app.domains.content_collection.dm_sequences_router.list_sequences", ("get_db", "verify_admin_token")),
    ("/api/dm-sequences", ("POST",), "create_sequence", "app.domains.content_collection.dm_sequences_router.create_sequence", ("get_db", "require_role:admin")),
    ("/api/dm-sequences/{sequence_id}", ("GET",), "get_sequence", "app.domains.content_collection.dm_sequences_router.get_sequence", ("get_db", "verify_admin_token")),
    ("/api/dm-sequences/{sequence_id}", ("PUT",), "update_sequence", "app.domains.content_collection.dm_sequences_router.update_sequence", ("get_db", "require_role:admin")),
    ("/api/dm-sequences/{sequence_id}", ("DELETE",), "delete_sequence", "app.domains.content_collection.dm_sequences_router.delete_sequence", ("get_db", "require_role:admin")),
    ("/api/dm-sequences/generate", ("POST",), "generate_dm_sequence", "app.domains.content_collection.dm_sequences_router.generate_dm_sequence", ("get_db", "require_role:admin")),
    ("/api/dm-sequences/{seq_id}/variants", ("POST",), "generate_variants", "app.domains.content_collection.dm_sequences_router.generate_variants", ("get_db", "require_role:admin")),
    ("/api/dm-sequences/device/sync", ("GET",), "device_sync", "app.domains.content_collection.dm_sequences_router.device_sync", ("get_db", "verify_device_secret")),
]


def test_content_collection_route_table_snapshot():
    assert _content_collection_http_routes() == EXPECTED_CONTENT_COLLECTION_HTTP_ROUTES


def test_content_collection_auth_dependency_snapshot():
    assert _dependencies_for("/api/content/templates", ("GET",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/content/templates", ("POST",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/data/comments", ("GET",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/dm-sequences", ("GET",)) == ("get_db", "verify_admin_token")
    assert _dependencies_for("/api/dm-sequences", ("POST",)) == ("get_db", "require_role:admin")
    assert _dependencies_for("/api/dm-sequences/device/sync", ("GET",)) == ("get_db", "verify_device_secret")
    assert _dependencies_for("/api/device/collect-report", ("POST",)) == ("get_db", "verify_device_secret")


def _content_collection_http_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and _is_content_collection_route(route.path):
            endpoint = f"{route.endpoint.__module__}.{route.endpoint.__qualname__}"
            dependency_names = tuple(
                _dependency_identity(dep.call)
                for dep in route.dependant.dependencies
                if dep.call
            )
            routes.append((route.path, tuple(sorted(route.methods)), route.name, endpoint, dependency_names))
    return routes


def _dependencies_for(path, methods):
    for route_path, route_methods, _name, _endpoint, dependencies in _content_collection_http_routes():
        if route_path == path and route_methods == methods:
            return dependencies
    raise AssertionError(f"Route not found: {methods} {path}")


def _is_content_collection_route(path):
    return (
        path.startswith("/api/content/")
        or path.startswith("/api/data/")
        or path == "/api/dm-sequences"
        or path.startswith("/api/dm-sequences/")
        or path in {
            "/api/device/generate-content",
            "/api/device/collect-report",
            "/api/device/dm-claim-recipient",
            "/api/device/dm-send-report",
            "/api/device/dm-release-recipient",
            "/api/device/comment-ai-reply",
            "/api/device/user-profile",
            "/api/device/user-avatar",
        }
    )


def _dependency_identity(call):
    name = getattr(call, "__name__", repr(call))
    qualname = getattr(call, "__qualname__", "")
    if name == "checker" and qualname.endswith("require_role.<locals>.checker"):
        closure = getattr(call, "__closure__", None) or ()
        for cell in closure:
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, str):
                return f"require_role:{value}"
            if isinstance(value, (frozenset, set, tuple, list)) and value:
                roles = ",".join(sorted(str(role) for role in value))
                return f"require_role:{roles}"
    return name
