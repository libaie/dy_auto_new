import copy

import pytest

from app.db.models import AITextArtifact, Character, Episode, Scene, Series
from app.domains.ai_video_series.asset_director_service import (
    ASSET_DIRECTOR_ARTIFACT_TYPE,
    AssetDirectorError,
    apply_asset_director_plan,
    compute_asset_director_fingerprint,
    ensure_asset_director_plan_for_episode,
    load_asset_director_inputs,
)
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService


def _ready_character(name: str, **meta):
    return Character(
        name=name,
        role_type=meta.pop("role_type", "supporting"),
        gender=meta.pop("gender", "unknown"),
        avatar_front_url="https://cdn.test/front.png",
        avatar_threequarter_url="https://cdn.test/three.png",
        avatar_side_url="https://cdn.test/side.png",
        avatar_fullbody_url="https://cdn.test/full.png",
        meta_json=meta,
    )


def _ready_scene(name: str, **meta):
    return Scene(
        name=name,
        scene_type=meta.pop("scene_type", "indoor"),
        reference_wideshot_url="https://cdn.test/wide.png",
        reference_midshot_url="https://cdn.test/mid.png",
        reference_aerial_url="https://cdn.test/aerial.png",
        meta_json=meta,
    )


def _assets_by_stable_key(db, model, stable_key: str, series_id: str):
    return [
        asset
        for asset in db.query(model).all()
        if isinstance(asset.meta_json, dict)
        and asset.meta_json.get("asset_stable_key") == stable_key
        and asset.meta_json.get("series_id") == series_id
    ]


def _series_with_episodes(db):
    series = Series(
        title="Thirty Day Clinic",
        logline="A clinic team solves one moral dilemma per episode.",
        genre="medical",
        total_episodes=2,
        status="draft",
        story_bible_json={"style_lock": {"locked": True, "version": 2}},
    )
    ep1 = Episode(
        series=series,
        episode_number=1,
        title="The First Call",
        script_json={"script": "Lin treats Patient Wu."},
        storyboard_json={
            "frames": [
                {
                    "frame_id": "ep1-f1",
                    "visual": "Lin and Wu in exam room.",
                }
            ]
        },
    )
    ep2 = Episode(
        series=series,
        episode_number=2,
        title="The Return",
        script_json={"script": "Lin returns to the hallway."},
        storyboard_json={
            "frames": [
                {
                    "frame_id": "ep2-f1",
                    "visual": "Lin walks through the hallway.",
                }
            ]
        },
    )
    lin = _ready_character(
        "Dr Lin",
        asset_stable_key="lead_doctor",
        asset_scope="series_recurring",
        series_id="pending",
    )
    hallway = _ready_scene(
        "Clinic Hallway",
        asset_stable_key="clinic_hallway",
        asset_scope="location_recurring",
        series_id="pending",
    )
    series.characters.append(lin)
    series.scenes.append(hallway)
    db.add_all([series, ep1, ep2])
    db.commit()
    lin.meta_json = {**(lin.meta_json or {}), "series_id": series.id}
    hallway.meta_json = {**(hallway.meta_json or {}), "series_id": series.id}
    db.commit()
    return series, ep1, ep2, lin, hallway


def _approved_sources(db, series, ep1, ep2):
    service = AITextArtifactService(db)
    for artifact_type in ("series_bible", "series_story_plan", "season_arc", "continuity_ledger"):
        artifact = service.create_artifact(
            series_id=series.id,
            target_type="series",
            target_id=series.id,
            artifact_type=artifact_type,
            source_type="test",
            content_json={"title": series.title, "artifact_type": artifact_type},
            commit=False,
        )
        service.approve_artifact(artifact.id, commit=False)
    for ep in (ep1, ep2):
        for artifact_type in ("episode_outline", "episode_script", "storyboard"):
            artifact = service.create_artifact(
                series_id=series.id,
                episode_id=ep.id,
                target_type="episode",
                target_id=ep.id,
                artifact_type=artifact_type,
                source_type="test",
                content_json={
                    "episode_number": ep.episode_number,
                    "frames": ep.storyboard_json.get("frames", []),
                },
                commit=False,
            )
            service.approve_artifact(artifact.id, commit=False)
    db.commit()


def _plan(db, series, ep1, ep2, lin, hallway):
    inputs = load_asset_director_inputs(db=db, series_id=series.id)
    return {
        "series_id": series.id,
        "covered_episode_numbers": [1, 2],
        "style_lock_version": inputs.style_lock_version,
        "input_fingerprint": compute_asset_director_fingerprint(inputs),
        "source_artifacts": inputs.source_artifacts,
        "recurring_characters": [
            {
                "stable_key": "lead_doctor",
                "aliases": ["林医生", "Dr Lin"],
                "name": "Dr Lin",
                "reuse_character_id": lin.id,
                "asset_scope": "series_recurring",
                "match_confidence": "high",
                "episode_numbers": [1, 2],
                "usage": "Series lead.",
            }
        ],
        "recurring_scenes": [
            {
                "stable_key": "clinic_hallway",
                "name": "Clinic Hallway",
                "reuse_scene_id": hallway.id,
                "asset_scope": "location_recurring",
                "match_confidence": "high",
                "episode_numbers": [2],
                "usage": "Recurring clinic corridor.",
            }
        ],
        "episode_assets": [
            {
                "episode_number": 1,
                "characters": [
                    {
                        "stable_key": "patient_wu_ep1",
                        "aliases": ["吴病人"],
                        "name": "Patient Wu",
                        "asset_scope": "episode_only",
                        "match_confidence": "new",
                        "role_type": "supporting",
                        "gender": "unknown",
                        "appearance_desc": "Middle-aged patient with pale face.",
                        "outfit_desc": "Grey hoodie and hospital wristband.",
                        "usage": "Episode-only patient.",
                    }
                ],
                "scenes": [
                    {
                        "stable_key": "ep1_exam_room",
                        "name": "Exam Room One",
                        "asset_scope": "episode_only",
                        "match_confidence": "new",
                        "scene_type": "indoor",
                        "location_desc": "Small exam room with ultrasound monitor.",
                        "lighting": "warm_indoor",
                        "mood": "tense",
                        "usage": "Episode one diagnosis room.",
                    }
                ],
                "frame_bindings": [
                    {
                        "frame_id": "ep1-f1",
                        "scene_stable_key": "ep1_exam_room",
                        "character_stable_keys": ["lead_doctor", "patient_wu_ep1"],
                    }
                ],
            },
            {
                "episode_number": 2,
                "characters": [],
                "scenes": [],
                "frame_bindings": [
                    {
                        "frame_id": "ep2-f1",
                        "scene_stable_key": "clinic_hallway",
                        "character_stable_keys": ["lead_doctor"],
                    }
                ],
            },
        ],
    }


def test_load_inputs_collects_context_artifacts_and_reusable_assets(db):
    series, ep1, ep2, _lin, _hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)

    inputs = load_asset_director_inputs(db=db, series_id=series.id)

    assert inputs.series.id == series.id
    assert [episode.episode_number for episode in inputs.episodes] == [1, 2]
    assert inputs.style_lock_version == 2
    assert len(inputs.source_artifacts) == 10
    assert {artifact["artifact_type"] for artifact in inputs.source_artifacts} == {
        "series_bible",
        "series_story_plan",
        "season_arc",
        "continuity_ledger",
        "episode_outline",
        "episode_script",
        "storyboard",
    }
    assert {
        (artifact["episode_id"], artifact["artifact_type"])
        for artifact in inputs.source_artifacts
        if artifact["target_type"] == "episode"
    } == {
        (ep1.id, "episode_outline"),
        (ep1.id, "episode_script"),
        (ep1.id, "storyboard"),
        (ep2.id, "episode_outline"),
        (ep2.id, "episode_script"),
        (ep2.id, "storyboard"),
    }
    assert inputs.episodes[0].script_json["script"] == "Lin treats Patient Wu."
    assert inputs.episodes[0].storyboard_json["frames"][0]["frame_id"] == "ep1-f1"
    assert {asset.meta_json["asset_stable_key"] for asset in inputs.series.characters} == {"lead_doctor"}
    assert {asset.meta_json["asset_stable_key"] for asset in inputs.series.scenes} == {"clinic_hallway"}


def test_apply_plan_creates_episode_assets_and_binds_frames(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)

    result = apply_asset_director_plan(db, series.id, _plan(db, series, ep1, ep2, lin, hallway))

    db.refresh(ep1)
    db.refresh(ep2)
    patient = db.query(Character).filter(Character.name == "Patient Wu").one()
    exam_room = db.query(Scene).filter(Scene.name == "Exam Room One").one()
    assert result["status"] == "needs_reference"
    assert result["artifact"].artifact_type == ASSET_DIRECTOR_ARTIFACT_TYPE
    assert patient.meta_json["series_id"] == series.id
    assert patient.meta_json["episode_id"] == ep1.id
    assert patient.meta_json["asset_scope"] == "episode_only"
    assert patient.meta_json["asset_source"] == "asset_director"
    assert patient.meta_json["asset_stable_key"] == "patient_wu_ep1"
    assert patient.meta_json["asset_director_plan_id"] == result["artifact"].id
    assert patient.meta_json["match_confidence"] == "new"
    assert patient.meta_json["asset_readiness"] == "needs_reference"
    assert exam_room.meta_json["episode_id"] == ep1.id
    assert ep1.storyboard_json["frames"][0]["scene_id"] == exam_room.id
    assert ep1.storyboard_json["frames"][0]["character_ids"] == [lin.id, patient.id]
    assert ep2.storyboard_json["frames"][0]["scene_id"] == hallway.id
    assert ep2.storyboard_json["frames"][0]["character_ids"] == [lin.id]
    assert ep1.script_json["episode_asset_scope"]["character_ids"] == [lin.id, patient.id]
    assert ep1.script_json["episode_asset_scope"]["scene_ids"] == [exam_room.id]


def test_plan_rerun_is_idempotent_by_stable_key(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)

    first = apply_asset_director_plan(db, series.id, plan)
    patients = _assets_by_stable_key(db, Character, "patient_wu_ep1", series.id)
    exam_rooms = _assets_by_stable_key(db, Scene, "ep1_exam_room", series.id)
    assert len(patients) == 1
    assert len(exam_rooms) == 1
    patient_id = patients[0].id
    exam_room_id = exam_rooms[0].id

    second = apply_asset_director_plan(db, series.id, plan)
    patients = _assets_by_stable_key(db, Character, "patient_wu_ep1", series.id)
    exam_rooms = _assets_by_stable_key(db, Scene, "ep1_exam_room", series.id)

    assert first["artifact"].id != second["artifact"].id
    assert len(patients) == 1
    assert len(exam_rooms) == 1
    assert patients[0].id == patient_id
    assert exam_rooms[0].id == exam_room_id


def test_low_confidence_name_match_blocks(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    conflict = _ready_character("Patient Wu", asset_stable_key="other_patient", series_id=series.id)
    series.characters.append(conflict)
    db.add(conflict)
    db.commit()
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["episode_assets"][0]["characters"][0]["match_confidence"] = "low"

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_LOW_CONFIDENCE_MATCH"
    assert db.query(Character).filter(Character.name == "Patient Wu").count() == 1


def test_wrong_series_plan_raises_series_mismatch(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    other = Series(title="Other", genre="drama", total_episodes=1, status="draft")
    db.add(other)
    db.commit()
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["series_id"] = other.id

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_SERIES_MISMATCH"


def test_plan_payload_for_unknown_episode_raises_episode_not_found(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["covered_episode_numbers"].append(999)
    plan["episode_assets"].append(
        {
            "episode_number": 999,
            "characters": [],
            "scenes": [],
            "frame_bindings": [],
        }
    )

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_EPISODE_NOT_FOUND"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda item: item.pop("stable_key"),
        lambda item: item.pop("name"),
        lambda item: item.update({"asset_scope": "invalid_scope"}),
        lambda item: item.update({"match_confidence": "certain"}),
    ],
)
def test_invalid_asset_payload_raises_invalid_asset(db, mutation):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    mutation(plan["recurring_characters"][0])

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_INVALID_ASSET"


def test_scalar_covered_episode_numbers_raises_invalid_json(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["covered_episode_numbers"] = "1"

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_INVALID_JSON"


def test_scalar_episode_characters_raises_invalid_asset(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["episode_assets"][0]["characters"] = "patient_wu_ep1"

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_INVALID_ASSET"


def test_non_list_aliases_raises_invalid_asset(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["episode_assets"][0]["characters"][0]["aliases"] = "吴病人"

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_INVALID_ASSET"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda plan: plan.update({"recurring_characters": "lead_doctor"}), "ASSET_DIRECTOR_INVALID_ASSET"),
        (lambda plan: plan["episode_assets"][0].update({"frame_bindings": "ep1-f1"}), "ASSET_DIRECTOR_INVALID_JSON"),
    ],
)
def test_malformed_collection_fields_raise_registry_codes(db, mutation, expected_code):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    mutation(plan)

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == expected_code


def test_malformed_character_stable_keys_raise_invalid_json(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["episode_assets"][0]["frame_bindings"][0]["character_stable_keys"] = {"bad": "shape"}

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_INVALID_JSON"


def test_duplicate_stable_keys_raise_ambiguous_match(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["episode_assets"][0]["characters"][0]["stable_key"] = "lead_doctor"

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_AMBIGUOUS_MATCH"


@pytest.mark.asyncio
async def test_ensure_asset_director_plan_maps_reference_failed(db):
    series, ep1, ep2, _lin, _hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    inputs = load_asset_director_inputs(db=db, series_id=series.id)
    artifact_service = AITextArtifactService(db)
    artifact = artifact_service.create_artifact(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type=ASSET_DIRECTOR_ARTIFACT_TYPE,
        source_type="asset_director",
        content_json={
            "series_id": series.id,
            "covered_episode_numbers": [1, 2],
            "input_fingerprint": compute_asset_director_fingerprint(inputs),
            "readiness": {"status": "reference_failed"},
        },
        commit=False,
    )
    artifact_service.approve_artifact(artifact.id, commit=False)
    db.commit()

    with pytest.raises(AssetDirectorError) as exc:
        await ensure_asset_director_plan_for_episode(db, series.id, ep1.id)

    assert exc.value.code == "ASSET_DIRECTOR_REFERENCES_FAILED"


def test_invalid_frame_binding_rolls_back_without_partial_assets(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    script_before = copy.deepcopy(ep1.script_json)
    storyboard_before = copy.deepcopy(ep1.storyboard_json)
    plan = _plan(db, series, ep1, ep2, lin, hallway)
    plan["episode_assets"][0]["frame_bindings"][0]["frame_id"] = "missing-frame"

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "ASSET_DIRECTOR_FRAME_NOT_FOUND"
    assert db.query(Character).filter(Character.name == "Patient Wu").count() == 0
    assert db.query(Scene).filter(Scene.name == "Exam Room One").count() == 0
    assert db.query(AITextArtifact).filter(AITextArtifact.artifact_type == ASSET_DIRECTOR_ARTIFACT_TYPE).count() == 0
    db.refresh(ep1)
    assert ep1.script_json == script_before
    assert ep1.storyboard_json == storyboard_before


def test_fingerprint_changes_when_storyboard_changes(db):
    series, ep1, ep2, lin, hallway = _series_with_episodes(db)
    _approved_sources(db, series, ep1, ep2)
    before = compute_asset_director_fingerprint(load_asset_director_inputs(db=db, series_id=series.id))

    storyboard = dict(ep1.storyboard_json)
    storyboard["frames"] = [*storyboard.get("frames", []), {"frame_id": "ep1-f2", "visual": "New frame."}]
    ep1.storyboard_json = storyboard
    db.commit()
    after = compute_asset_director_fingerprint(load_asset_director_inputs(db=db, series_id=series.id))

    assert before != after
