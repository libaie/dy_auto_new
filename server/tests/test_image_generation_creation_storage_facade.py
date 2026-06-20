import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-image-creation-storage-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-image-creation-storage-domain-plan.md"
DOMAIN_STORAGE_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_storage.py"
LEGACY_STORAGE_PATH = REPO_ROOT / "server/app/services/image_creation_storage.py"
IMAGE_ROUTER_PATH = REPO_ROOT / "server/app/domains/image_generation/image_creation_router.py"
REFERENCE_ASSET_PATH = REPO_ROOT / "server/app/domains/creative_library/reference_asset_service.py"
IMAGE_CREATION_SERVICE_PATH = REPO_ROOT / "server/app/services/image_creation_service.py"
README_PATH = REPO_ROOT / "server/app/domains/image_generation/README.md"


def test_image_creation_storage_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_creation_storage",
        "app.services.image_creation_storage",
        "save_output_bytes",
    ]:
        assert term in spec
        assert term in plan


def test_image_creation_storage_domain_file_exists():
    assert DOMAIN_STORAGE_PATH.exists()


def test_legacy_image_creation_storage_is_thin_facade():
    text = LEGACY_STORAGE_PATH.read_text(encoding="utf-8")
    assert "app.domains.image_generation" in text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in text
    assert "def save_output_bytes" not in text
    assert "def save_upload" not in text
    assert _line_count(LEGACY_STORAGE_PATH) <= 12


def test_legacy_image_creation_storage_module_is_domain_module():
    legacy = importlib.import_module("app.services.image_creation_storage")
    domain = importlib.import_module("app.domains.image_generation.image_creation_storage")
    assert legacy is domain
    assert legacy.save_output_bytes is domain.save_output_bytes
    assert legacy.save_upload is domain.save_upload
    assert legacy.configured_public_base_url is domain.configured_public_base_url
    assert legacy.IMAGE_CREATION_ROOT is domain.IMAGE_CREATION_ROOT


def test_services_parent_package_image_creation_storage_attribute_is_domain_module():
    from app.services import image_creation_storage as parent_import

    domain = importlib.import_module("app.domains.image_generation.image_creation_storage")
    assert parent_import is domain


def test_image_creation_storage_root_stays_under_app_static():
    domain = importlib.import_module("app.domains.image_generation.image_creation_storage")
    assert domain.IMAGE_CREATION_ROOT == REPO_ROOT / "server/app/static/image-creation"


def test_domain_callers_import_domain_storage_only():
    for path in [IMAGE_ROUTER_PATH, REFERENCE_ASSET_PATH]:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.image_generation.image_creation_storage" in text
        assert "app.services.image_creation_storage" not in text


def test_image_creation_service_stays_legacy_compatible_for_wip_slice():
    text = IMAGE_CREATION_SERVICE_PATH.read_text(encoding="utf-8")
    assert "app.services.image_creation_storage" in text
    assert "app.domains.image_generation.image_creation_storage" not in text


def test_image_generation_docs_register_image_creation_storage_facade():
    readme = README_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.image_generation.image_creation_storage",
        "app.services.image_creation_storage",
        "save_output_bytes",
        "approved image creation service compatibility import",
    ]:
        assert term in readme


def test_save_output_bytes_stays_legacy_compatible(tmp_path, monkeypatch):
    legacy = importlib.import_module("app.services.image_creation_storage")
    monkeypatch.setattr(legacy, "IMAGE_CREATION_ROOT", tmp_path / "image-creation")
    saved = legacy.save_output_bytes(
        b"fake image",
        "https://cdn.example.test",
        content_type="image/png",
    )
    assert saved["url"].startswith("https://cdn.example.test/static/image-creation/outputs/")
    assert saved["storage_path"].startswith("outputs/")
    assert Path(saved["local_path"]).read_bytes() == b"fake image"
    assert saved["mime_type"] == "image/png"


def _line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())
