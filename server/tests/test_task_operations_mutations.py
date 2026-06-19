import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_PATH = REPO_ROOT / "server/app/domains/task_operations"


def test_task_operations_pr4_module_split_exists():
    expected_files = {
        "adapters.py",
        "param_resolution.py",
        "read_models.py",
        "realtime_events.py",
        "schemas.py",
        "task_use_cases.py",
        "tasks_router.py",
    }

    assert expected_files <= {path.name for path in DOMAIN_PATH.iterdir()}


def test_task_operations_non_router_use_cases_stay_out_of_fastapi():
    use_case_text = (DOMAIN_PATH / "task_use_cases.py").read_text(encoding="utf-8")

    assert "fastapi" not in use_case_text.lower()
    assert "HTTPException" not in use_case_text


def test_task_router_delegates_to_domain_modules():
    router_text = (DOMAIN_PATH / "tasks_router.py").read_text(encoding="utf-8")

    assert "task_use_cases.create_task" in router_text
    assert "task_use_cases.batch_create_tasks" in router_text
    assert "realtime_events.broadcast_new_task_available" in router_text
    assert "task_service.create_task(" not in router_text
    assert "content_service.generate_from_template" not in router_text


def test_legacy_param_helper_aliases_point_to_domain_module():
    param_resolution = importlib.import_module("app.domains.task_operations.param_resolution")
    tasks_router = importlib.import_module("app.domains.task_operations.tasks_router")

    assert tasks_router._maybe_resolve_content_template is param_resolution.maybe_resolve_content_template
    assert tasks_router._maybe_resolve_dm_sequence is param_resolution.maybe_resolve_dm_sequence
    assert tasks_router._maybe_expand_keywords is param_resolution.maybe_expand_keywords
    assert tasks_router._validate_and_normalize_params is param_resolution.validate_and_normalize_params
