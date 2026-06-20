"""Test series/characters/scenes API endpoints."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import AITextArtifact, Character, Episode, ProductionJob, Scene, Series, VideoProductionRun


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

    def test_get_series_requires_admin_auth(self, client, real_auth, db):
        series = Series(title="Private Series", logline="Hidden", genre="drama")
        db.add(series)
        db.commit()

        detail = client.get(f"/api/series/{series.id}")

        assert detail.status_code == 401

    def test_ensure_episode_placeholders_repairs_missing_episodes(self, client, db):
        series = Series(title="Broken API Series", total_episodes=3, status="draft")
        db.add(series)
        db.flush()
        db.add(Episode(series_id=series.id, episode_number=1, status="done"))
        db.commit()

        resp = client.post(f"/api/series/{series.id}/ensure-episodes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["target_episode_count"] == 3
        assert data["created_episode_numbers"] == [2, 3]
        assert data["created_outline_episode_numbers"] == [1, 2, 3]
        assert data["created_continuity_ledger"] is True
        numbers = [
            ep.episode_number
            for ep in db.query(Episode)
            .filter(Episode.series_id == series.id)
            .order_by(Episode.episode_number)
        ]
        assert numbers == [1, 2, 3]
        assert db.query(AITextArtifact).filter_by(
            series_id=series.id,
            artifact_type="episode_outline",
            status="approved",
        ).count() == 3

    def test_create_series_story_plan_endpoint_enqueues_background_job(self, client, db):
        series = Series(title="Story API", logline="A family secret returns.", total_episodes=2, status="draft")
        db.add(series)
        db.commit()

        resp = client.post(f"/api/series/{series.id}/story-plan")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "planning"
        assert data["story_planning"]["status"] == "queued"
        assert data["story_planning"]["job_id"] == data["job_id"]
        assert db.query(ProductionJob).filter_by(
            target_type="series",
            target_id=series.id,
            stage="story_planning",
            status="queued",
        ).count() == 1
        assert db.query(AITextArtifact).filter_by(
            series_id=series.id,
            artifact_type="series_story_plan",
            status="approved",
        ).count() == 0

    def test_create_series_story_plan_endpoint_blocks_duplicate_active_job(self, client, db):
        series = Series(title="Duplicate Story API", logline="A family secret returns.", total_episodes=2, status="draft")
        db.add(series)
        db.commit()

        first = client.post(f"/api/series/{series.id}/story-plan")
        duplicate = client.post(f"/api/series/{series.id}/story-plan")

        assert first.status_code == 200
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "STORY_PLANNING_IN_PROGRESS"
        assert db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="story_planning").count() == 1

    def test_create_series_story_plan_endpoint_reuses_completed_plan_without_queueing(self, client, db):
        series = Series(
            title="Completed Story API",
            logline="A family secret returns.",
            total_episodes=2,
            status="draft",
            story_bible_json={"story_planning": {"status": "completed", "version": 1, "job_id": "job-done"}},
        )
        db.add(series)
        db.flush()
        episodes = [
            Episode(series_id=series.id, episode_number=1, status="pending"),
            Episode(series_id=series.id, episode_number=2, status="pending"),
        ]
        db.add_all(episodes)
        db.flush()
        db.add_all([
            AITextArtifact(
                series_id=series.id,
                target_type="series",
                target_id=series.id,
                artifact_type="series_story_plan",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"summary": "The family secret escalates."},
            ),
            AITextArtifact(
                series_id=series.id,
                target_type="series",
                target_id=series.id,
                artifact_type="season_arc",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"arc_summary": "Truth rises episode by episode."},
            ),
            AITextArtifact(
                series_id=series.id,
                target_type="series",
                target_id=series.id,
                artifact_type="continuity_ledger",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"mainline": "Keep the secret consistent."},
            ),
            AITextArtifact(
                series_id=series.id,
                episode_id=episodes[0].id,
                target_type="episode",
                target_id=episodes[0].id,
                artifact_type="episode_outline",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"episode_number": 1, "episode_goal": "Expose the first clue."},
            ),
            AITextArtifact(
                series_id=series.id,
                episode_id=episodes[1].id,
                target_type="episode",
                target_id=episodes[1].id,
                artifact_type="episode_outline",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"episode_number": 2, "episode_goal": "Force a confession."},
            ),
        ])
        db.commit()

        resp = client.post(f"/api/series/{series.id}/story-plan")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "completed"
        assert data["job_id"] == "job-done"
        assert data["story_planning"]["status"] == "completed"
        assert data["story_planning"]["version"] == 1
        assert len(data["artifacts"]) == 5
        assert db.query(ProductionJob).filter_by(target_type="series", target_id=series.id, stage="story_planning").count() == 0

    def test_create_series_story_plan_endpoint_does_not_treat_system_backfill_outlines_as_completed(self, client, db):
        series = Series(
            title="Backfill Story API",
            logline="A family secret returns.",
            total_episodes=2,
            status="draft",
            story_bible_json={"story_planning": {"status": "completed", "version": 1, "job_id": "old-job"}},
        )
        db.add(series)
        db.flush()
        episodes = [
            Episode(series_id=series.id, episode_number=1, status="pending"),
            Episode(series_id=series.id, episode_number=2, status="pending"),
        ]
        db.add_all(episodes)
        db.flush()
        db.add_all([
            AITextArtifact(
                series_id=series.id,
                target_type="series",
                target_id=series.id,
                artifact_type="series_story_plan",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"summary": "The family secret escalates."},
            ),
            AITextArtifact(
                series_id=series.id,
                target_type="series",
                target_id=series.id,
                artifact_type="season_arc",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"arc_summary": "Truth rises episode by episode."},
            ),
            AITextArtifact(
                series_id=series.id,
                target_type="series",
                target_id=series.id,
                artifact_type="continuity_ledger",
                version=1,
                status="approved",
                source_type="ai",
                content_json={"mainline": "Keep the secret consistent."},
            ),
            AITextArtifact(
                series_id=series.id,
                episode_id=episodes[0].id,
                target_type="episode",
                target_id=episodes[0].id,
                artifact_type="episode_outline",
                version=1,
                status="approved",
                source_type="system_backfill",
                content_json={"episode_number": 1, "episode_goal": "Backfilled placeholder."},
            ),
            AITextArtifact(
                series_id=series.id,
                episode_id=episodes[1].id,
                target_type="episode",
                target_id=episodes[1].id,
                artifact_type="episode_outline",
                version=1,
                status="approved",
                source_type="system_backfill",
                content_json={"episode_number": 2, "episode_goal": "Backfilled placeholder."},
            ),
        ])
        db.commit()

        resp = client.post(f"/api/series/{series.id}/story-plan")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "planning"
        assert data["story_planning"]["status"] == "queued"
        assert db.query(ProductionJob).filter_by(
            target_type="series",
            target_id=series.id,
            stage="story_planning",
            status="queued",
        ).count() == 1

    def test_generate_episode_script_endpoint_creates_script_and_storyboard(self, client, db, monkeypatch):
        series = Series(title="Script API", logline="A vendor hides a secret.", total_episodes=1, target_duration=6, status="draft")
        db.add(series)
        db.flush()
        episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
        db.add(episode)
        db.commit()

        async def fake_generate_episode_script_storyboard(db_session, *, series_id, episode_id, target_duration_seconds=None):
            target = db_session.query(Episode).filter_by(id=episode_id, series_id=series_id).one()
            target.script_json = {"title": "Pilot", "target_duration_seconds": target_duration_seconds}
            target.storyboard_json = {
                "frames": [{
                    "frame_id": "shot-001",
                    "time_range": "0-2秒",
                    "duration": 2,
                    "narration": "摊主发现秘密账本。",
                    "image_prompt": "夜市摊位前，摊主看见一本旧账本。",
                    "video_prompt": "镜头从摊位招牌推向账本。",
                }]
            }
            db_session.add(AITextArtifact(
                series_id=series_id,
                episode_id=episode_id,
                target_type="episode",
                target_id=episode_id,
                artifact_type="episode_script",
                version=1,
                status="approved",
                source_type="ai",
                content_json=target.script_json,
            ))
            db_session.add(AITextArtifact(
                series_id=series_id,
                episode_id=episode_id,
                target_type="episode",
                target_id=episode_id,
                artifact_type="storyboard",
                version=1,
                status="approved",
                source_type="ai",
                content_json=target.storyboard_json,
            ))
            db_session.commit()
            return {"script": target.script_json, "storyboard": target.storyboard_json, "artifact_count": 2}

        monkeypatch.setattr(
            "app.routers.series.generate_episode_script_storyboard",
            fake_generate_episode_script_storyboard,
            raising=False,
        )

        resp = client.post(
            f"/api/series/{series.id}/episodes/{episode.id}/script",
            json={"target_duration_seconds": 6},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["script"]["title"] == "Pilot"
        assert data["storyboard"]["frames"][0]["time_range"] == "0-2秒"
        assert db.query(AITextArtifact).filter_by(
            series_id=series.id,
            episode_id=episode.id,
            artifact_type="episode_script",
            status="approved",
        ).count() == 1

    def test_get_series_marks_episode_active_video_run(self, client, db):
        resp = self._create_series(client)
        series_id = resp.json()["series"]["id"]
        detail = client.get(f"/api/series/{series_id}")
        episode_id = detail.json()["episodes"][0]["id"]
        run = VideoProductionRun(
            series_id=series_id,
            episode_id=episode_id,
            status="image_batch_running",
            current_stage="image_generation",
        )
        db.add(run)
        db.commit()

        detail = client.get(f"/api/series/{series_id}")

        episode = detail.json()["episodes"][0]
        assert episode["active_video_run_id"] == run.id
        assert episode["video_run_status"] == "image_batch_running"
        assert episode["video_run_route"] == f"/video-production/{run.id}"

    def test_get_series_includes_linked_assets_with_reference_urls(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        char_id = client.post("/api/characters", json={
            "name": "林岚", "role_type": "protagonist", "gender": "female",
        }).json()["character"]["id"]
        scene_id = client.post("/api/scenes", json={
            "name": "办公室", "scene_type": "indoor",
        }).json()["scene"]["id"]
        client.put(f"/api/characters/{char_id}", json={
            "avatar_front_url": "https://cdn.test/front.png",
        })
        client.put(f"/api/scenes/{scene_id}", json={
            "reference_wideshot_url": "/static/refs/wide.png",
        })
        client.post(f"/api/series/{series_id}/characters/{char_id}")
        client.post(f"/api/series/{series_id}/scenes/{scene_id}")

        detail = client.get(f"/api/series/{series_id}")

        assert detail.status_code == 200
        series = detail.json()["series"]
        assert series["characters"][0]["id"] == char_id
        assert series["characters"][0]["avatar_front_url"] == "https://cdn.test/front.png"
        assert series["scenes"][0]["id"] == scene_id
        assert series["scenes"][0]["reference_wideshot_url"] == "/static/refs/wide.png"

    def test_get_series_detail_includes_episode_asset_scope(self, client, db):
        series = Series(title="Episode Scope API", logline="A secret returns.", total_episodes=1, status="draft")
        character = Character(name="Scope Lead", role_type="protagonist", gender="female")
        scene = Scene(name="Scope Room", scene_type="indoor")
        series.characters.append(character)
        series.scenes.append(scene)
        db.add(series)
        db.flush()
        episode = Episode(series_id=series.id, episode_number=1, status="pending")
        db.add(episode)
        db.flush()
        db.add(AITextArtifact(
            series_id=series.id,
            episode_id=episode.id,
            target_type="episode",
            target_id=episode.id,
            artifact_type="episode_outline",
            version=1,
            status="approved",
            source_type="ai",
            content_json={
                "episode_number": 1,
                "character_ids": [character.id],
                "scene_ids": [scene.id],
                "asset_usage": {
                    "characters": [
                        {"id": character.id, "name": character.name, "usage": "Carries the episode.", "source": "existing"}
                    ],
                    "scenes": [
                        {"id": scene.id, "name": scene.name, "usage": "Hosts the reveal.", "source": "existing"}
                    ],
                },
                "generated_assets": {"characters": [], "scenes": []},
            },
        ))
        db.commit()

        detail = client.get(f"/api/series/{series.id}")

        assert detail.status_code == 200
        episode_payload = detail.json()["episodes"][0]
        assert episode_payload["asset_scope"]["character_ids"] == [character.id]
        assert episode_payload["asset_scope"]["scene_ids"] == [scene.id]
        assert episode_payload["asset_scope"]["characters"][0]["name"] == character.name
        assert episode_payload["asset_scope"]["scenes"][0]["name"] == scene.name
        assert episode_payload["asset_scope"]["source"] == "episode_outline"

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

    def test_update_series(self, client):
        series_id = self._create_series(client).json()["series"]["id"]

        resp = client.put(f"/api/series/{series_id}", json={
            "title": "Updated",
            "logline": "Updated logline",
            "total_episodes": 12,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["series"]["title"] == "Updated"
        assert data["series"]["logline"] == "Updated logline"
        assert data["series"]["total_episodes"] == 12

    def test_unlink_character_from_series(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        char_id = client.post("/api/characters", json={
            "name": "Lead", "role_type": "protagonist", "gender": "male",
        }).json()["character"]["id"]
        client.post(f"/api/series/{series_id}/characters/{char_id}")

        resp = client.delete(f"/api/series/{series_id}/characters/{char_id}")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "action": "unlinked"}

    def test_unlink_scene_from_series(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        scene_id = client.post("/api/scenes", json={
            "name": "Office", "scene_type": "indoor",
        }).json()["scene"]["id"]
        client.post(f"/api/series/{series_id}/scenes/{scene_id}")

        resp = client.delete(f"/api/series/{series_id}/scenes/{scene_id}")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "action": "unlinked"}

    def test_delete_empty_series_returns_deleted_action(self, client):
        series_id = self._create_series(client).json()["series"]["id"]

        resp = client.delete(f"/api/series/{series_id}")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "action": "deleted"}

    def test_update_episode(self, client, db):
        series_id = self._create_series(client).json()["series"]["id"]
        detail = client.get(f"/api/series/{series_id}")
        ep_id = detail.json()["episodes"][0]["id"]

        resp = client.put(f"/api/series/{series_id}/episodes/{ep_id}", json={
            "title": "初遇", "script_json": {"scenes": []},
        })
        assert resp.status_code == 200
        artifact = db.query(AITextArtifact).filter_by(
            series_id=series_id,
            episode_id=ep_id,
            target_type="episode",
            target_id=ep_id,
            artifact_type="episode_script",
        ).one()
        assert artifact.status == "approved"
        assert artifact.source_type == "human_edit"
        assert artifact.content_json == {"scenes": []}

    def test_update_episode_rolls_back_when_text_artifact_approval_fails(self, client, db, monkeypatch):
        from app.services.ai_text_artifact_service import AITextArtifactService

        series_id = self._create_series(client).json()["series"]["id"]
        detail = client.get(f"/api/series/{series_id}")
        ep_id = detail.json()["episodes"][0]["id"]

        def fail_approval(self, artifact_id, *, actor_user_id=None, commit=True):
            raise RuntimeError("approval failed")

        monkeypatch.setattr(AITextArtifactService, "approve_artifact", fail_approval)

        resp = client.put(f"/api/series/{series_id}/episodes/{ep_id}", json={
            "title": "不应半提交", "script_json": {"scenes": [{"summary": "不应落库"}]},
        })

        assert resp.status_code == 500

        db.expire_all()
        episode = db.query(Episode).filter(Episode.id == ep_id).one()
        assert episode.title != "不应半提交"
        assert episode.script_json in ({}, None)
        assert db.query(AITextArtifact).filter_by(series_id=series_id, episode_id=ep_id).count() == 0


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
