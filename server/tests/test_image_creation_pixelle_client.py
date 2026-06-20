import pytest

from app.domains.pixelle_integration.pixelle_stage_client import submit_image_create


@pytest.mark.asyncio
async def test_image_creation_pixelle_client_sends_external_task_and_mode(monkeypatch):
    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "stage-task-1", "assets": []}

    monkeypatch.setattr("app.domains.pixelle_integration.pixelle_stage_client._pixelle_request", fake_request)

    await submit_image_create(
        db=None,
        external_task_id="task-123",
        mode="character_set",
        capability_key="seedream",
        output_mode="single",
        prompt="character turnaround",
        model_config={"provider": "mock"},
    )

    assert calls == [
        (
            "POST",
            "/api/stages/images/create",
            {
                "external_task_id": "task-123",
                "mode": "character_set",
                "capability_key": "seedream",
                "output_mode": "single",
                "prompt": "character turnaround",
                "negative_prompt": "",
                "source_image_url": "",
                "reference_images": [],
                "count": 1,
                "size": "",
                "output_format": "",
                "response_format": "",
                "provider_options": {},
                "model_config": {"provider": "mock"},
                "context": {},
            },
        )
    ]
