from app.db_models import AITextArtifact, AITextArtifactConsumer, Episode, Series, VideoProductionRun


def _create_series_episode(db):
    series = Series(title="Traceable Series", total_episodes=3, status="draft")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="planned")
    db.add(episode)
    db.commit()
    return series, episode


def test_manual_edit_creates_new_artifact_version_and_approval_supersedes_old(db):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    service = AITextArtifactService(db)

    artifact = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
        source_type="ai",
        input_json={"prompt": "write episode 1"},
        content_text="AI script v1",
        content_json={"title": "Pilot", "scenes": []},
        model_trace_json={"provider": "test", "model": "fake-llm"},
    )

    assert artifact.version == 1
    assert artifact.status == "review_pending"

    edited = service.edit_artifact(
        artifact.id,
        content_text="Human edited script v2",
        content_json={"title": "Pilot", "scenes": [{"summary": "edited"}]},
        actor_user_id="user-1",
    )

    assert edited.version == 2
    assert edited.source_type == "human_edit"
    assert edited.parent_artifact_id == artifact.id
    assert edited.created_by == "user-1"

    approved = service.approve_artifact(edited.id, actor_user_id="user-1")
    db.refresh(artifact)

    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert artifact.status == "superseded"
    assert service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
    ).id == approved.id
    assert [item.version for item in service.list_versions(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
    )] == [1, 2]


def test_approve_artifact_rejects_stale_version_when_newer_version_exists(db):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
        source_type="ai",
        content_text="AI script v1",
    )
    edited = service.edit_artifact(
        artifact.id,
        content_text="Human edited script v2",
        content_json={"scenes": [{"summary": "edited"}]},
        actor_user_id="user-1",
    )

    try:
        service.approve_artifact(artifact.id, actor_user_id="user-1")
    except ValueError as exc:
        assert str(exc) == "stale_artifact_version"
    else:
        raise AssertionError("Expected stale artifact approval to be rejected")

    db.refresh(artifact)
    db.refresh(edited)
    assert artifact.status == "review_pending"
    assert edited.status == "review_pending"
    assert service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_script",
    ) is None


def test_bind_consumer_records_exact_artifact_version(db):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
        source_type="ai",
        input_json={"script_artifact": "script-1"},
        content_json={"frames": []},
    )
    approved = service.approve_artifact(artifact.id, actor_user_id="user-1")

    consumer = service.bind_consumer(
        approved.id,
        consumer_type="video_run",
        consumer_id="run-1",
        run_id="run-1",
        metadata_json={"stage": "storyboard"},
    )

    assert consumer.artifact_id == approved.id
    assert consumer.series_id == series.id
    assert consumer.episode_id == episode.id
    assert consumer.run_id == "run-1"
    assert consumer.metadata_json == {"stage": "storyboard"}


def test_backfill_run_text_artifacts_imports_legacy_run_outputs_and_binds_run(db):
    from app.services.ai_text_artifact_service import AITextArtifactService

    series, episode = _create_series_episode(db)
    series.story_bible_json = {"style_lock": {"locked": True, "characters": [{"id": "char-1"}]}}
    episode.storyboard_json = {
        "frames": [{
            "frame_id": "shot-1",
            "duration": 5,
            "image_prompt": "legacy image prompt",
            "video_prompt": "legacy video prompt",
            "narration": "legacy narration",
        }]
    }
    episode.script_json = {"scenes": [{"dialogue": "legacy script line"}]}
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="completed",
        current_stage="completed",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    service = AITextArtifactService(db)

    consumed = service.backfill_run_text_artifacts(run.id)

    assert [item["artifact_type"] for item in consumed] == [
        "series_bible",
        "continuity_ledger",
        "episode_outline",
        "episode_script",
        "storyboard",
        "dialogue",
        "image_prompt",
        "video_prompt",
    ]
    assert {item["status"] for item in consumed} == {"approved"}
    assert consumed[3]["content_json"] == {"scenes": [{"dialogue": "legacy script line"}]}
    assert consumed[4]["content_text"] == "legacy narration"
    assert consumed[6]["content_json"] == {"prompts": ["legacy image prompt"]}
    assert consumed[7]["content_json"] == {"prompts": ["legacy video prompt"]}
    assert db.query(AITextArtifact).filter_by(series_id=series.id).count() == 8
    assert db.query(AITextArtifactConsumer).filter_by(
        consumer_type="video_production_run",
        consumer_id=run.id,
    ).count() == 8

    again = service.backfill_run_text_artifacts(run.id)

    assert [item["artifact_id"] for item in again] == [item["artifact_id"] for item in consumed]
    assert db.query(AITextArtifact).filter_by(series_id=series.id).count() == 8
    assert db.query(AITextArtifactConsumer).filter_by(
        consumer_type="video_production_run",
        consumer_id=run.id,
    ).count() == 8
