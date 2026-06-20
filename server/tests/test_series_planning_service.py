import json
from types import SimpleNamespace

import pytest

from app.db.models import AgencyCreativePatch, AgencyExpertInvocation, AITextArtifact, Character, Episode, Scene, Series


RICH_OUTLINE_FIELDS = {
    "episode_number",
    "title",
    "hook",
    "episode_goal",
    "central_conflict",
    "reversal",
    "cliffhanger",
    "previous_episode_handoff",
    "next_episode_handoff",
    "character_state_changes",
    "foreshadowing_introduced",
    "foreshadowing_resolved",
    "character_ids",
    "scene_ids",
}


def _planning_payload(total_episodes=3):
    return {
        "series_story_plan": {
            "schema_version": "series.story_plan.v1",
            "summary": "A family secret escalates across the season.",
            "theme": "truth versus loyalty",
        },
        "season_arc": {
            "schema_version": "series.season_arc.v1",
            "arc_summary": "Each episode reveals a deeper betrayal.",
            "turning_points": ["Discovery", "Betrayal", "Choice"],
        },
        "episode_outlines": [
            {
                "episode_number": episode_number,
                "title": f"AI Episode {episode_number}",
                "hook": f"Hook {episode_number}",
                "episode_goal": f"Goal {episode_number}",
                "central_conflict": f"Conflict {episode_number}",
                "reversal": f"Reversal {episode_number}",
                "cliffhanger": f"Cliffhanger {episode_number}",
                "previous_episode_handoff": "" if episode_number == 1 else f"From {episode_number - 1}",
                "next_episode_handoff": (
                    "Final resolution" if episode_number == total_episodes else f"To {episode_number + 1}"
                ),
                "character_state_changes": [{"character_id": "char-1", "change": f"State {episode_number}"}],
                "foreshadowing_introduced": [f"Seed {episode_number}"],
                "foreshadowing_resolved": [] if episode_number == 1 else [f"Resolve {episode_number - 1}"],
                "character_ids": ["char-1"],
                "scene_ids": ["scene-1"],
            }
            for episode_number in range(1, total_episodes + 1)
        ],
    }


def _latest_outline(db, episode_id):
    artifact = (
        db.query(AITextArtifact)
        .filter(
            AITextArtifact.episode_id == episode_id,
            AITextArtifact.artifact_type == "episode_outline",
            AITextArtifact.status == "approved",
        )
        .order_by(AITextArtifact.version.desc())
        .first()
    )
    assert artifact is not None
    return artifact.content_json


def _add_series_assets(series, *, character_name="Lin", scene_name="House"):
    character = Character(name=character_name, role_type="protagonist", gender="female")
    scene = Scene(name=scene_name, scene_type="indoor")
    series.characters.append(character)
    series.scenes.append(scene)
    return character, scene


def test_ensure_episode_placeholders_creates_missing_episodes_idempotently(db):
    from app.domains.ai_video_series.series_planning_service import ensure_episode_placeholders

    series = Series(title="Broken", total_episodes=3, status="draft")
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="done"))
    db.commit()

    result = ensure_episode_placeholders(db, series.id)

    assert result.created_episode_numbers == [2, 3]

    again = ensure_episode_placeholders(db, series.id)

    assert again.created_episode_numbers == []
    numbers = [
        ep.episode_number
        for ep in db.query(Episode)
        .filter(Episode.series_id == series.id)
        .order_by(Episode.episode_number)
    ]
    assert numbers == [1, 2, 3]


def test_series_completion_requires_all_target_episodes_done(db):
    from app.domains.ai_video_series.series_planning_service import is_series_completed, next_episode_number

    series = Series(title="Pilot only", total_episodes=3, status="draft")
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="done"))
    db.commit()

    assert is_series_completed(db, series.id) is False
    assert next_episode_number(db, series.id) == 2


def test_ensure_series_continuity_artifacts_creates_connected_episode_outlines(db):
    from app.domains.ai_video_series.series_planning_service import ensure_episode_placeholders, ensure_series_continuity_artifacts

    series = Series(
        title="Continuity Series",
        logline="A family secret resurfaces.",
        total_episodes=3,
        status="draft",
    )
    character, scene = _add_series_assets(series, character_name="林夏", scene_name="老宅")
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, title="Pilot", status="done"))
    db.commit()
    ensure_episode_placeholders(db, series.id)

    result = ensure_series_continuity_artifacts(db, series.id)

    assert result.created_continuity_ledger is True
    assert result.created_outline_episode_numbers == [1, 2, 3]
    outlines = (
        db.query(AITextArtifact)
        .filter(AITextArtifact.series_id == series.id, AITextArtifact.artifact_type == "episode_outline")
        .order_by(AITextArtifact.version.asc())
        .all()
    )
    assert len(outlines) == 3
    assert {outline.status for outline in outlines} == {"approved"}
    episode_2 = next(outline for outline in outlines if outline.content_json["episode_number"] == 2)
    assert episode_2.content_json["previous_episode_handoff"]
    assert episode_2.content_json["character_ids"] == [character.id]
    assert episode_2.content_json["scene_ids"] == [scene.id]


def test_ensure_series_continuity_artifacts_preserves_existing_approved_outline(db):
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
    from app.domains.ai_video_series.series_planning_service import ensure_series_continuity_artifacts

    series = Series(title="Manual Outline", logline="Keep edits.", total_episodes=1, status="draft")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()
    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={"episode_number": 1, "episode_goal": "Manual approved outline"},
        content_text="Manual approved outline",
    )
    service.approve_artifact(manual.id)

    result = ensure_series_continuity_artifacts(db, series.id)

    assert result.created_outline_episode_numbers == []
    outlines = db.query(AITextArtifact).filter(
        AITextArtifact.series_id == series.id,
        AITextArtifact.artifact_type == "episode_outline",
    ).all()
    assert len(outlines) == 1
    assert outlines[0].id == manual.id


@pytest.mark.asyncio
async def test_generate_series_story_plan_creates_approved_story_artifacts_and_rich_outlines(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    calls = []

    async def fake_story_generator(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            parsed=payload,
            source_type="ai",
            model_trace={
                "stage": "story_planning",
                "stage_status": "expert",
                "expert_id": "story_generator",
                "scene_key": "script_generation",
                "invocation_id": "inv-story",
            },
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)
    series = Series(
        title="Continuity Series",
        logline="A family secret resurfaces.",
        total_episodes=3,
        status="draft",
    )
    character, scene = _add_series_assets(series)
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending"))
    db.commit()
    payload = _planning_payload()
    for outline in payload["episode_outlines"]:
        outline["character_ids"] = [character.id]
        outline["scene_ids"] = [scene.id]
        outline["character_state_changes"] = [{"character_id": character.id, "change": "State"}]

    result = await planning.generate_series_story_plan(db, series.id)

    assert result.series_id == series.id
    assert result.target_episode_count == 3
    assert result.created_episode_numbers == [2, 3]
    assert calls[0]["series"].id == series.id
    assert calls[0]["character_ids"] == [character.id]
    assert calls[0]["scene_ids"] == [scene.id]

    episode_numbers = [
        episode.episode_number
        for episode in db.query(Episode)
        .filter(Episode.series_id == series.id)
        .order_by(Episode.episode_number)
        .all()
    ]
    assert episode_numbers == [1, 2, 3]

    approved = (
        db.query(AITextArtifact)
        .filter(AITextArtifact.series_id == series.id, AITextArtifact.status == "approved")
        .all()
    )
    approved_types = [artifact.artifact_type for artifact in approved]
    assert approved_types.count("series_story_plan") == 1
    assert approved_types.count("season_arc") == 1
    assert approved_types.count("continuity_ledger") == 1
    assert approved_types.count("episode_outline") == 3

    outlines = [artifact for artifact in approved if artifact.artifact_type == "episode_outline"]
    assert {outline.content_json["episode_number"] for outline in outlines} == {1, 2, 3}
    for outline in outlines:
        assert RICH_OUTLINE_FIELDS <= set(outline.content_json)
        assert outline.content_json["character_ids"] == [character.id]
        assert outline.content_json["scene_ids"] == [scene.id]
        assert outline.model_trace_json["expert_id"] == "story_generator"
        assert outline.model_trace_json["stage"] == "story_planning"


@pytest.mark.asyncio
async def test_generate_series_story_plan_creates_episode_specific_assets_from_story_output(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    series = Series(title="Asset Scope", logline="A hidden heir returns.", total_episodes=2, status="draft")
    lead, home = _add_series_assets(series, character_name="Lin Xia", scene_name="Lin Home")
    db.add(series)
    db.flush()
    ep1 = Episode(series_id=series.id, episode_number=1, title="Receipt", status="pending")
    ep2 = Episode(series_id=series.id, episode_number=2, title="Diagnosis", status="pending")
    db.add_all([ep1, ep2])
    db.commit()

    payload = _planning_payload(total_episodes=2)
    payload["episode_outlines"][0]["character_ids"] = [lead.id]
    payload["episode_outlines"][0]["scene_ids"] = [home.id]
    payload["episode_outlines"][0]["character_state_changes"] = [
        {"character_id": lead.id, "change": "Finds the first clue"}
    ]
    payload["episode_outlines"][1]["character_ids"] = []
    payload["episode_outlines"][1]["scene_ids"] = []
    payload["episode_outlines"][1]["generated_assets"] = {
        "characters": [
            {
                "name": "Doctor Ren",
                "role_type": "supporting",
                "gender": "female",
                "usage": "Names the real heir.",
            }
        ],
        "scenes": [
            {
                "name": "Clinic Archive",
                "scene_type": "indoor",
                "usage": "Hides the adoption file.",
            }
        ],
    }

    async def fake_story_generator(**_kwargs):
        return SimpleNamespace(
            parsed=payload,
            source_type="ai",
            model_trace={"stage": "story_planning", "stage_status": "expert", "expert_id": "story_generator"},
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)

    result = await planning.generate_series_story_plan(db, series.id, force=True)
    ep1_outline = _latest_outline(db, ep1.id)
    ep2_outline = _latest_outline(db, ep2.id)
    db.refresh(series)

    assert result.series_id == series.id
    assert ep1_outline["character_ids"] == [lead.id]
    assert ep1_outline["scene_ids"] == [home.id]
    assert ep2_outline["character_ids"] != ep1_outline["character_ids"]
    assert ep2_outline["scene_ids"] != ep1_outline["scene_ids"]
    assert any(character.name == "Doctor Ren" for character in series.characters)
    assert any(scene.name == "Clinic Archive" for scene in series.scenes)
    assert ep2_outline["asset_usage"]["characters"][0]["source"] == "generated"
    assert ep2_outline["asset_usage"]["scenes"][0]["source"] == "generated"


@pytest.mark.asyncio
async def test_generate_series_story_plan_missing_episode_ids_falls_back_to_primary_asset_only(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    series = Series(title="Fallback Scope", logline="A family secret returns.", total_episodes=1, status="draft")
    lead, home = _add_series_assets(series, character_name="Lead", scene_name="Home")
    series.characters.append(Character(name="Supporting", role_type="supporting", gender="female"))
    series.scenes.append(Scene(name="Office", scene_type="indoor"))
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()

    payload = _planning_payload(total_episodes=1)
    payload["episode_outlines"][0]["character_ids"] = []
    payload["episode_outlines"][0]["scene_ids"] = []

    async def fake_story_generator(**_kwargs):
        return SimpleNamespace(
            parsed=payload,
            source_type="ai",
            model_trace={"stage": "story_planning", "stage_status": "expert", "expert_id": "story_generator"},
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)

    await planning.generate_series_story_plan(db, series.id, force=True)
    outline = _latest_outline(db, episode.id)

    assert outline["character_ids"] == [lead.id]
    assert outline["scene_ids"] == [home.id]
    assert outline["asset_usage"]["characters"][0]["source"] == "fallback"
    assert outline["asset_usage"]["scenes"][0]["source"] == "fallback"


@pytest.mark.asyncio
async def test_generate_series_story_plan_idempotent_when_ai_or_fallback_artifacts_already_approved(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    call_count = 0

    async def fake_story_generator(**_kwargs):
        nonlocal call_count
        call_count += 1
        return SimpleNamespace(
            parsed=payload,
            source_type="ai",
            model_trace={"stage": "story_planning", "stage_status": "expert", "expert_id": "story_generator"},
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)
    series = Series(title="Idempotent", logline="Keep one plan.", total_episodes=2, status="draft")
    character, scene = _add_series_assets(series)
    db.add(series)
    db.commit()
    payload = _planning_payload(total_episodes=2)
    for outline in payload["episode_outlines"]:
        outline["character_ids"] = [character.id]
        outline["scene_ids"] = [scene.id]

    await planning.generate_series_story_plan(db, series.id)
    first_ids = {
        artifact.id
        for artifact in db.query(AITextArtifact)
        .filter(AITextArtifact.series_id == series.id)
        .all()
    }

    async def fail_if_called(**_kwargs):
        raise AssertionError("story generator should not be called for an idempotent rerun")

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fail_if_called, raising=False)
    result = await planning.generate_series_story_plan(db, series.id)

    second_ids = {
        artifact.id
        for artifact in db.query(AITextArtifact)
        .filter(AITextArtifact.series_id == series.id)
        .all()
    }
    assert call_count == 1
    assert second_ids == first_ids
    assert result.replaced_outline_episode_numbers == []
    assert result.preserved_outline_episode_numbers == [1, 2]


@pytest.mark.asyncio
async def test_generate_series_story_plan_preserves_human_edit_approved_episode_outline(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    async def fake_story_generator(**_kwargs):
        return SimpleNamespace(
            parsed=payload,
            source_type="ai",
            model_trace={"stage": "story_planning", "stage_status": "expert", "expert_id": "story_generator"},
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)
    series = Series(title="Manual Outline", logline="Keep edits.", total_episodes=2, status="draft")
    character, scene = _add_series_assets(series)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()
    payload = _planning_payload(total_episodes=2)
    for outline in payload["episode_outlines"]:
        outline["character_ids"] = [character.id]
        outline["scene_ids"] = [scene.id]

    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={"episode_number": 1, "episode_goal": "Manual approved outline"},
        content_text="Manual approved outline",
    )
    service.approve_artifact(manual.id)

    result = await planning.generate_series_story_plan(db, series.id)

    latest_manual = service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
    )
    assert latest_manual.id == manual.id
    assert result.preserved_outline_episode_numbers == [1]

    approved_outlines = (
        db.query(AITextArtifact)
        .filter(
            AITextArtifact.series_id == series.id,
            AITextArtifact.artifact_type == "episode_outline",
            AITextArtifact.status == "approved",
        )
        .all()
    )
    assert len(approved_outlines) == 2
    assert {outline.content_json["episode_number"] for outline in approved_outlines} == {1, 2}


@pytest.mark.asyncio
async def test_generate_series_story_plan_preserves_valid_human_asset_ids_and_adds_usage(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService

    async def fake_story_generator(**_kwargs):
        return SimpleNamespace(
            parsed=_planning_payload(total_episodes=1),
            source_type="ai",
            model_trace={"stage": "story_planning", "stage_status": "expert", "expert_id": "story_generator"},
        )

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)
    series = Series(title="Manual Asset Outline", logline="Keep valid IDs.", total_episodes=1, status="draft")
    character, scene = _add_series_assets(series, character_name="Manual Lead", scene_name="Manual Room")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()

    service = AITextArtifactService(db)
    manual = service.create_artifact(
        series_id=series.id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
        source_type="human_edit",
        content_json={
            "episode_number": 1,
            "episode_goal": "Manual approved outline",
            "character_ids": [character.id],
            "scene_ids": [scene.id],
        },
        content_text="Manual approved outline",
    )
    service.approve_artifact(manual.id)

    result = await planning.generate_series_story_plan(db, series.id)
    latest = service.latest_approved(target_type="episode", target_id=episode.id, artifact_type="episode_outline")

    assert latest.id == manual.id
    assert latest.content_json["character_ids"] == [character.id]
    assert latest.content_json["scene_ids"] == [scene.id]
    assert latest.content_json["asset_usage"]["characters"][0]["name"] == "Manual Lead"
    assert latest.content_json["asset_usage"]["scenes"][0]["name"] == "Manual Room"
    assert result.preserved_outline_episode_numbers == [1]


@pytest.mark.asyncio
async def test_generate_series_story_plan_falls_back_when_ai_generation_raises(db, monkeypatch):
    from app.domains.ai_video_series import series_planning_service as planning
    async def fake_story_generator(**_kwargs):
        raise RuntimeError("AI API not configured")

    monkeypatch.setattr(planning, "generate_story_plan_with_expert", fake_story_generator, raising=False)
    series = Series(title="Fallback", logline="Plan without AI.", total_episodes=2, status="draft")
    db.add(series)
    db.commit()

    result = await planning.generate_series_story_plan(db, series.id)

    assert result.model_trace["stage_status"] == "fallback"
    plan = (
        db.query(AITextArtifact)
        .filter(
            AITextArtifact.series_id == series.id,
            AITextArtifact.artifact_type == "series_story_plan",
            AITextArtifact.status == "approved",
        )
        .one()
    )
    assert plan.source_type == "system_fallback"
    assert plan.model_trace_json["stage"] == "story_planning"
    assert plan.model_trace_json["stage_status"] == "fallback"
    assert plan.model_trace_json["expert_id"] == "story_generator"
    assert "AI API not configured" in plan.model_trace_json["error"]

    outlines = (
        db.query(AITextArtifact)
        .filter(
            AITextArtifact.series_id == series.id,
            AITextArtifact.artifact_type == "episode_outline",
            AITextArtifact.status == "approved",
        )
        .all()
    )
    assert len(outlines) == 2
    for outline in outlines:
        assert outline.source_type == "system_fallback"
        assert outline.model_trace_json["stage_status"] == "fallback"
        assert outline.model_trace_json["expert_id"] == "story_generator"
        assert RICH_OUTLINE_FIELDS <= set(outline.content_json)
        assert outline.content_json["character_ids"]
        assert outline.content_json["scene_ids"]
        assert outline.content_json["asset_usage"]["characters"][0]["source"] == "fallback"
        assert outline.content_json["asset_usage"]["scenes"][0]["source"] == "fallback"


@pytest.mark.asyncio
async def test_story_generator_runtime_finalizes_safe_invocation_without_repair_side_effects(db):
    from app.domains.ai_video_series.story_generator_expert import generate_story_plan_with_expert

    captured = {}

    async def fake_model_client(system_prompt, user_prompt, runtime_config, response_format=None):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        captured["response_format"] = response_format
        return {
            "content": json.dumps(payload, ensure_ascii=False),
            "token_usage": {"total_tokens": 123},
        }

    series = Series(title="Expert Runtime", logline="A secret returns.", total_episodes=1, status="draft")
    character, scene = _add_series_assets(series, character_name="Runtime Lead", scene_name="Runtime Room")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot", status="pending")
    db.add(episode)
    db.commit()
    payload = _planning_payload(total_episodes=1)
    payload["episode_outlines"][0]["character_ids"] = [character.id]
    payload["episode_outlines"][0]["scene_ids"] = [scene.id]

    result = await generate_story_plan_with_expert(
        db,
        series=series,
        episodes=[episode],
        character_ids=[character.id],
        scene_ids=[scene.id],
        existing_artifacts=[],
        runtime_config={
            "scene_key": "script_generation",
            "provider": "openai-compatible",
            "model": "story-model",
            "base_url": "https://model.example/v1",
            "api_key": "sk-secret",
            "config": {"protocol": "openai_chat_completions", "supports_json_schema": True},
        },
        model_client=fake_model_client,
    )

    assert result.parsed["series_story_plan"]["summary"] == "A family secret escalates across the season."
    assert result.source_type == "ai"
    assert result.model_trace["expert_id"] == "story_generator"
    assert result.model_trace["stage"] == "story_planning"
    assert result.model_trace["scene_key"] == "script_generation"
    assert captured["response_format"]["type"] == "json_schema"
    assert "generated_assets" in captured["system_prompt"]
    assert "asset_usage" in captured["system_prompt"]
    assert "series_asset_pool" in captured["user_prompt"]
    assert "Runtime Lead" in captured["user_prompt"]
    assert "Runtime Room" in captured["user_prompt"]
    assert captured["response_format"]["json_schema"]["schema"]["properties"]["episode_outlines"]["items"]["properties"]["generated_assets"]["type"] == "object"

    invocation = db.query(AgencyExpertInvocation).filter_by(
        series_id=series.id,
        stage="story_planning",
        expert_id="story_generator",
        role="lead",
    ).one()
    assert invocation.execution_status == "completed"
    assert invocation.result_status == "passed"
    assert invocation.output_summary_json["repair_tasks"] == []
    assert "creative_patches" not in invocation.output_summary_json
    assert db.query(AgencyCreativePatch).filter_by(source_invocation_id=invocation.id).count() == 0
