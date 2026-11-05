"""Device snapshots must retain the revision when the last template disappears."""
import pytest
from fastapi.testclient import TestClient

from app.config import DEVICE_SECRET
from app.db_models import PromptTemplate, SystemSetting
from app.main import app
from app.services.prompt_template_service import prompt_template_service


@pytest.fixture(autouse=True)
def isolated_templates(db):
    db.query(PromptTemplate).delete()
    db.query(SystemSetting).filter(SystemSetting.key == "prompt_templates_revision").delete()
    db.add(PromptTemplate(id="fullchain-template", name="fullchain-template", industry="general", content={}, enabled=True))
    db.add(SystemSetting(key="prompt_templates_revision", value="10"))
    db.commit()
    yield
    db.rollback()
    db.query(PromptTemplate).delete()
    db.query(SystemSetting).filter(SystemSetting.key == "prompt_templates_revision").delete()
    db.commit()


@pytest.mark.parametrize("operation", ["disable", "delete"])
def test_last_template_removal_delivers_empty_snapshot_at_current_revision(db, operation):
    client = TestClient(app)
    headers = {"X-Device-Secret": DEVICE_SECRET}
    before = client.get("/api/device/prompt-templates", params={"version": 0}, headers=headers)
    assert before.status_code == 200
    assert before.json()["version"] == 10
    assert len(before.json()["templates"]) == 1
    if operation == "disable":
        prompt_template_service.toggle_template(db, "fullchain-template", False)
    else:
        prompt_template_service.delete_template(db, "fullchain-template")
    response = client.get("/api/device/prompt-templates", params={"version": 10}, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"version": 11, "templates": [], "changed": True}
    current = client.get("/api/device/prompt-templates", params={"version": 11}, headers=headers)
    assert current.status_code == 200
    assert current.json() == {"version": 11, "templates": None, "changed": False}
