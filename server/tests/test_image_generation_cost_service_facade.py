import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-production-cost-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-production-cost-domain-plan.md"
DOMAIN_PATH = REPO_ROOT / "server/app/domains/image_generation/image_production_cost_service.py"
LEGACY_PATH = REPO_ROOT / "server/app/services/image_production_cost_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"
IMAGE_CREATION_SERVICE_PATH = REPO_ROOT / "server/app/services/image_creation_service.py"


def test_image_production_cost_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_production_cost_service",
        "app.services.image_production_cost_service",
        "record_estimated_cost_event",
        "record_actual_cost_event",
    ]:
        assert term in spec
        assert term in plan


def test_image_production_cost_domain_file_exists():
    assert DOMAIN_PATH.exists()


def test_legacy_image_production_cost_service_is_thin_facade():
    text = LEGACY_PATH.read_text(encoding="utf-8")
    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def record_estimated_cost_event" not in text
    assert "def record_actual_cost_event" not in text
    assert _line_count(LEGACY_PATH) <= 12


def test_legacy_image_production_cost_service_module_is_domain_module():
    legacy = importlib.import_module("app.services.image_production_cost_service")
    domain = importlib.import_module("app.domains.image_generation.image_production_cost_service")
    assert legacy is domain
    assert legacy.record_estimated_cost_event is domain.record_estimated_cost_event
    assert legacy.record_actual_cost_event is domain.record_actual_cost_event


def test_services_parent_package_image_production_cost_attribute_is_domain_module():
    from app.services import image_production_cost_service as parent_import

    domain = importlib.import_module("app.domains.image_generation.image_production_cost_service")
    assert parent_import is domain


def test_image_creation_service_keeps_approved_legacy_cost_import():
    text = IMAGE_CREATION_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.services.image_production_cost_service" in text
    assert "app.domains.image_generation.image_production_cost_service" not in text


def test_image_generation_docs_register_image_production_cost_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_production_cost_service",
        "app.services.image_production_cost_service",
        "record_estimated_cost_event",
        "approved image creation service compatibility import",
    ]:
        assert term in readme


def test_record_actual_cost_event_stays_legacy_compatible(db):
    from app.db_models import ImageCreationTask, ImageProductionCostEvent
    from app.services.image_production_cost_service import record_actual_cost_event

    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="cost test",
        status="succeeded",
        count=1,
        target_count=1,
        provider="pixelle",
        provider_task_id="provider-1",
        estimated_cost_json={"amount": 1.25, "currency": "CNY", "estimate_source": "policy"},
        provider_response_json={"usage": {"actual_cost": 2.5, "currency": "CNY", "images": 1}},
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    event = record_actual_cost_event(db, task)

    assert event is not None
    assert event.event_type == "actual"
    assert event.actual_cost == 2.5
    assert event.estimated_cost == 1.25
    assert db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).count() == 1


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
