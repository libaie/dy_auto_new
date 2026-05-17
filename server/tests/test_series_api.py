"""Test series/characters/scenes API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestCharactersAPI:
    def test_list_characters_empty(self, client):
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["characters"] == []

    def test_create_and_list_character(self, client):
        resp = client.post("/api/characters", json={
            "name": "高冷总裁", "role_type": "protagonist", "gender": "male",
            "personality": "外冷内热", "appearance_desc": "身高185，西装革履",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        char_id = resp.json()["character"]["id"]

        resp2 = client.get("/api/characters")
        assert len(resp2.json()["characters"]) == 1
        assert resp2.json()["characters"][0]["name"] == "高冷总裁"

    def test_update_character(self, client):
        resp = client.post("/api/characters", json={
            "name": "温柔闺蜜", "role_type": "supporting", "gender": "female",
        })
        char_id = resp.json()["character"]["id"]

        client.put(f"/api/characters/{char_id}", json={"name": "毒舌闺蜜"})
        resp2 = client.get("/api/characters")
        assert resp2.json()["characters"][0]["name"] == "毒舌闺蜜"

    def test_delete_character(self, client):
        resp = client.post("/api/characters", json={
            "name": "路人甲", "role_type": "cameo", "gender": "male",
        })
        char_id = resp.json()["character"]["id"]

        client.delete(f"/api/characters/{char_id}")
        assert len(client.get("/api/characters").json()["characters"]) == 0


class TestScenesAPI:
    def test_create_and_list_scene(self, client):
        client.post("/api/scenes", json={
            "name": "办公室", "scene_type": "indoor",
            "lighting": "白天", "mood": "紧张",
        })
        resp = client.get("/api/scenes")
        assert len(resp.json()["scenes"]) == 1


class TestSeriesAPI:
    def _create_series(self, client, title="测试系列"):
        return client.post("/api/series", json={
            "title": title, "logline": "测试梗概", "genre": "drama",
            "total_episodes": 10, "target_duration": 90,
            "mode": "step_by_step", "pilot_first": True,
        })

    def test_create_series(self, client):
        resp = self._create_series(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["series"]["title"] == "测试系列"

    def test_get_series_with_episodes(self, client):
        resp = self._create_series(client)
        series_id = resp.json()["series"]["id"]

        detail = client.get(f"/api/series/{series_id}")
        assert detail.status_code == 200
        assert len(detail.json()["episodes"]) == 10  # auto-created 10 episodes
        assert detail.json()["episodes"][0]["episode_number"] == 1
        assert detail.json()["episodes"][0]["status"] == "pending"

    def test_list_series(self, client):
        self._create_series(client, "S1")
        self._create_series(client, "S2")
        resp = client.get("/api/series")
        assert len(resp.json()["series"]) == 2

    def test_link_character_to_series(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        char_id = client.post("/api/characters", json={
            "name": "男主", "role_type": "protagonist", "gender": "male",
        }).json()["character"]["id"]

        resp = client.post(f"/api/series/{series_id}/characters/{char_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_update_episode(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        detail = client.get(f"/api/series/{series_id}")
        ep_id = detail.json()["episodes"][0]["id"]

        resp = client.put(f"/api/series/{series_id}/episodes/{ep_id}", json={
            "title": "初遇", "script_json": {"scenes": []},
        })
        assert resp.status_code == 200


class TestPipelineAPI:
    def _create_series_and_start(self, client):
        series_id = client.post("/api/series", json={
            "title": "Pipeline Test", "logline": "test", "genre": "drama",
            "total_episodes": 5, "target_duration": 60,
        }).json()["series"]["id"]
        resp = client.post("/api/pipeline/start", json={
            "series_id": series_id, "mode": "step_by_step",
        })
        return series_id, resp

    def test_start_pipeline(self, client):
        series_id, resp = self._create_series_and_start(client)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert "run_id" in resp.json()

    def test_list_runs(self, client):
        series_id, _ = self._create_series_and_start(client)
        resp = client.get(f"/api/pipeline/runs/{series_id}")
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        assert isinstance(runs, list)

    def test_get_single_run(self, client):
        series_id, start_resp = self._create_series_and_start(client)
        run_id = start_resp.json()["run_id"]

        # Poll the run endpoint
        resp = client.get(f"/api/pipeline/runs/{series_id}/{run_id}")
        assert resp.status_code == 200
        run = resp.json()["run"]
        assert run["status"] in ("running", "pending", "completed", "failed")


class TestAIConfigAPI:
    def test_list_and_create_model(self, client):
        """New AIModel CRUD — list seeded models, then create one."""
        resp = client.get("/api/ai-models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["models"], list)

        # Create a new model
        resp2 = client.post("/api/ai-models", json={
            "name": "Test Model",
            "model_type": "llm",
            "provider": "openai",
            "base_url": "https://test.openai.com/v1",
            "api_key": "sk-test-123",
            "model_name": "gpt-test",
        })
        assert resp2.status_code == 200
        assert resp2.json()["model"]["name"] == "Test Model"
        assert resp2.json()["model"]["api_key"] == "sk-test-123"

    def test_update_and_delete_model(self, client):
        """Update then delete a model."""
        # Create
        resp = client.post("/api/ai-models", json={
            "name": "To Update", "model_type": "tts", "provider": "edge-tts",
            "model_name": "tts-test",
        })
        model_id = resp.json()["model"]["id"]

        # Update
        resp2 = client.put(f"/api/ai-models/{model_id}", json={
            "name": "Updated Name", "enabled": False,
        })
        assert resp2.status_code == 200
        assert resp2.json()["model"]["name"] == "Updated Name"
        assert resp2.json()["model"]["enabled"] is False

        # Verify via detail
        resp3 = client.get(f"/api/ai-models/{model_id}")
        assert resp3.json()["model"]["name"] == "Updated Name"

        # Delete
        resp4 = client.delete(f"/api/ai-models/{model_id}")
        assert resp4.status_code == 200

        # Gone
        resp5 = client.get(f"/api/ai-models/{model_id}")
        assert resp5.status_code == 404
