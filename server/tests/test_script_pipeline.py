from app.db.models import (
    Episode,
    EpisodeScript as DbEpisodeScript,
    AITextArtifact,
    PipelineRun,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
    Series,
)
import pytest

from app.models.script import DramaticBeatType, EpisodeScript, PipelineStage
from app.domains.script_pipeline import script_pipeline_service as script_pipeline_module
from app.domains.script_pipeline.script_pipeline_service import (
    DynamicPromptBuilder,
    PipelineManager,
    ScriptGenerationError,
    ScriptGenerationPipeline,
    default_gate_runner,
)


def test_script_sqlalchemy_tables_persist_structured_rows(db):
    series = Series(title="逆袭短剧", logline="她被羞辱后反转身份", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="第一集")
    db.add(episode)
    db.flush()

    script = DbEpisodeScript(
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags_json=["都市逆袭"],
        target_duration_seconds=60,
        status="completed",
    )
    db.add(script)
    db.flush()
    db.add(ScriptDramaticBeat(
        script_id=script.id,
        order_index=1,
        beat_type="HOOK",
        emotional_value="震惊",
        plot_summary="反派摔杯逼女主下跪。",
    ))
    db.add(ScriptSceneOutline(
        script_id=script.id,
        scene_number=1,
        dramatic_beat_type="HOOK",
        location="豪门门口",
        characters_json=["女主", "反派"],
        conflict="反派逼女主下跪。",
        emotional_turn="从羞辱到压迫。",
        visual_mandate="前3秒摔杯。",
    ))
    db.add(ScriptVisualShot(
        script_id=script.id,
        shot_number=1,
        scene_number=1,
        beat_type="HOOK",
        narration="震惊！你竟敢让我跪下？",
        visual_prompt="女主站在雨夜门口，破碎茶杯在脚边。",
        video_prompt="镜头快速推近，女主抬眼。",
        duration=3.0,
    ))
    db.commit()

    saved = db.query(DbEpisodeScript).filter_by(id=script.id).one()
    assert saved.tags_json == ["都市逆袭"]
    assert db.query(ScriptDramaticBeat).filter_by(script_id=script.id).count() == 1
    assert db.query(ScriptSceneOutline).filter_by(script_id=script.id).count() == 1
    assert db.query(ScriptVisualShot).filter_by(script_id=script.id).count() == 1


class FakeModelClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, *, system_prompt, user_prompt, runtime_config):
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "runtime_config": runtime_config,
        })
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeGate:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    async def __call__(self, db, *, gate_name, series_id, episode_id, pipeline_run_id, stage_context, runtime_config):
        self.calls.append({
            "gate_name": gate_name,
            "series_id": series_id,
            "episode_id": episode_id,
            "pipeline_run_id": pipeline_run_id,
            "stage_context": stage_context,
            "runtime_config": runtime_config,
        })
        status = self.statuses.pop(0)
        return {"stage": gate_name, "stage_status": status, "invocation_ids": [f"{gate_name}-1"], "invocations": []}


class CommittingFakeGate(FakeGate):
    async def __call__(self, db, **kwargs):
        result = await super().__call__(db, **kwargs)
        db.commit()
        return result


def _series_episode(db):
    series = Series(title="逆袭短剧", logline="她被羞辱后反转身份", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="第一集")
    db.add(episode)
    db.flush()
    return series, episode


def _stage_outputs():
    beats = {
        "beats": [
            {"beat_type": "HOOK", "emotional_value": "震惊", "plot_summary": "反派摔杯逼女主下跪。"},
            {"beat_type": "CONFLICT_1", "emotional_value": "憋屈", "plot_summary": "反派逼她签协议。"},
            {"beat_type": "REVERSAL", "emotional_value": "爽", "plot_summary": "女主亮明身份。"},
            {"beat_type": "CLIMAX", "emotional_value": "震撼", "plot_summary": "反派发现自己求错人。"},
            {"beat_type": "CLIFFHANGER", "emotional_value": "紧张", "plot_summary": "幕后人出现。"},
        ]
    }
    scenes = {
        "scenes": [
            {
                "scene_number": 1,
                "dramatic_beat_type": "HOOK",
                "location": "豪门门口",
                "characters": ["女主", "反派"],
                "conflict": "反派逼女主下跪。",
                "emotional_turn": "羞辱压到极点。",
                "visual_mandate": "前3秒摔杯。",
            }
        ]
    }
    shots = {
        "shots": [
            {
                "shot_number": 1,
                "scene_number": 1,
                "beat_type": "HOOK",
                "narration": "震惊！你竟敢让我跪下？",
                "visual_prompt": "女主站在雨夜门口，破碎茶杯在脚边。",
                "video_prompt": "镜头快速推近，女主抬眼。",
                "duration": 3.0,
            }
        ]
    }
    return beats, scenes, shots


def _valid_episode_script(**overrides):
    beats, scenes, shots = _stage_outputs()
    payload = {
        "series_id": "series-1",
        "episode_id": "episode-1",
        "source_prompt": "她被逼下跪，却亮出集团继承人身份",
        "tags": ["都市逆袭"],
        "target_duration_seconds": 60,
        "dramatic_beats": beats,
        "scene_outlines": scenes,
        "visual_shots": shots,
        "agency_trace": {},
    }
    payload.update(overrides)
    return EpisodeScript(**payload)


def _test_asset_scope():
    return {
        "character_ids": ["char-1"],
        "scene_ids": ["scene-1"],
        "source": "episode_outline",
    }


def _timed_stage_outputs():
    beats, scenes, _ = _stage_outputs()
    shots = {
        "shots": [
            {
                "shot_number": 1,
                "scene_number": 1,
                "beat_type": "HOOK",
                "narration": "震惊！她被逼到门口。",
                "visual_prompt": "女主站在雨夜门口，破碎茶杯在脚边。",
                "video_prompt": "镜头从碎杯推到女主抬眼。",
                "duration": 2.0,
            },
            {
                "shot_number": 2,
                "scene_number": 1,
                "beat_type": "CONFLICT_1",
                "narration": "委屈！她被要求签下协议。",
                "visual_prompt": "反派把协议拍在桌上，众人围观。",
                "video_prompt": "手持镜头跟随协议落桌。",
                "duration": 2.0,
            },
            {
                "shot_number": 3,
                "scene_number": 1,
                "beat_type": "REVERSAL",
                "narration": "痛快！她亮出继承人身份。",
                "visual_prompt": "女主举起印章，反派表情僵住。",
                "video_prompt": "低角度推近女主，反派后退。",
                "duration": 2.0,
            },
        ]
    }
    return beats, scenes, shots


def test_visual_shots_prompt_requires_fine_grained_prompt_fields():
    payload = DynamicPromptBuilder().build(
        stage=PipelineStage.VISUAL_SHOTS,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=6,
        previous_outputs={},
    )

    assert "主体/角色" in payload.user_prompt
    assert "场景/环境" in payload.user_prompt
    assert "画面动作" in payload.user_prompt
    assert "镜头语言" in payload.user_prompt
    assert "情绪/光线" in payload.user_prompt
    assert "连续性" in payload.user_prompt


def test_script_snapshot_persists_episode_asset_scope():
    script = _valid_episode_script(episode_asset_scope=_test_asset_scope())

    snapshot = PipelineManager()._script_snapshot(script, "script-1")

    assert snapshot["episode_asset_scope"] == {
        "character_ids": ["char-1"],
        "scene_ids": ["scene-1"],
        "source": "episode_outline",
    }


def test_storyboard_snapshot_copies_episode_asset_scope_to_frames():
    script = _valid_episode_script(episode_asset_scope=_test_asset_scope())

    storyboard = PipelineManager()._storyboard_snapshot(script)

    assert storyboard["frames"][0]["scene_id"] == "scene-1"
    assert storyboard["frames"][0]["character_ids"] == ["char-1"]


def test_storyboard_snapshot_blocks_when_asset_scope_is_missing():
    script = _valid_episode_script(episode_asset_scope={"character_ids": [], "scene_ids": []})

    with pytest.raises(ScriptGenerationError) as exc:
        PipelineManager()._storyboard_snapshot(script)

    assert exc.value.error_code == "EPISODE_ASSET_SCOPE_MISSING"


def test_storyboard_snapshot_blocks_ambiguous_multi_scene_scope():
    script = _valid_episode_script(
        episode_asset_scope={
            "character_ids": ["char-1"],
            "scene_ids": ["scene-1", "scene-2"],
            "source": "episode_outline",
        }
    )

    with pytest.raises(ScriptGenerationError) as exc:
        PipelineManager()._storyboard_snapshot(script)

    assert exc.value.error_code == "EPISODE_ASSET_SCOPE_MISSING"


@pytest.mark.asyncio
async def test_default_gate_runner_routes_script_stages_to_matching_agency_stages(db, monkeypatch):
    calls = []

    class SpyOrchestrator:
        async def run_story_planning_review(self, db, **kwargs):
            calls.append(("story_planning", kwargs["stage_context"]))
            return {"stage": "story_planning", "stage_status": "completed", "invocation_ids": [], "invocations": []}

        async def run_storyboard_review(self, db, **kwargs):
            calls.append(("storyboard", kwargs["stage_context"]))
            return {"stage": "storyboard", "stage_status": "completed", "invocation_ids": [], "invocations": []}

        async def run_style_lock_review(self, db, **kwargs):
            calls.append(("style_lock", kwargs["stage_context"]))
            return {"stage": "style_lock", "stage_status": "completed", "invocation_ids": [], "invocations": []}

    monkeypatch.setattr(script_pipeline_module, "AgencyOrchestrator", SpyOrchestrator)

    for stage in (
        PipelineStage.DRAMATIC_BEATS,
        PipelineStage.SCENE_OUTLINES,
        PipelineStage.VISUAL_SHOTS,
    ):
        await default_gate_runner(
            db,
            gate_name=stage.value,
            series_id="series-1",
            episode_id="episode-1",
            pipeline_run_id="run-1",
            stage_context={stage.value: {}},
            runtime_config={"provider": "mock"},
        )

    assert [call[0] for call in calls] == ["story_planning", "story_planning", "storyboard"]


@pytest.mark.asyncio
async def test_script_pipeline_runs_three_stages_sequentially(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["completed", "completed", "completed"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    result = await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        episode_asset_scope=_test_asset_scope(),
    )

    assert isinstance(result, EpisodeScript)
    assert [beat.beat_type for beat in result.dramatic_beats.beats][0] == DramaticBeatType.HOOK
    assert len(pipeline.model_client.calls) == 3
    assert [call["gate_name"] for call in pipeline.gate_runner.calls] == ["dramatic_beats", "scene_outlines", "visual_shots"]
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    state = saved_run.layers_json["script_generation"]
    assert state["stages"]["visual_shots"]["status"] == "completed"


@pytest.mark.asyncio
async def test_script_pipeline_records_gate_block_but_still_generates_script(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["blocked", "completed", "completed"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    result = await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        episode_asset_scope=_test_asset_scope(),
    )

    assert isinstance(result, EpisodeScript)
    assert len(pipeline.model_client.calls) == 3
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    assert saved_run.layers_json["script_generation"]["human_intervention_required"] is True
    assert saved_run.status == "completed"
    assert saved_run.layers_json["script_generation"]["stages"]["dramatic_beats"]["status"] == "completed"
    assert saved_run.layers_json["script_generation"]["stages"]["dramatic_beats"]["gate_trace"]["stage_status"] == "blocked"


@pytest.mark.asyncio
async def test_script_pipeline_retries_stage_twice_then_marks_human_intervention(db):
    series, episode = _series_episode(db)
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([
            RuntimeError("bad json"),
            RuntimeError("bad json"),
            RuntimeError("bad json"),
        ]),
        gate_runner=FakeGate([]),
    )
    manager = PipelineManager(pipeline=pipeline)

    with pytest.raises(ScriptGenerationError) as exc:
        await manager.start_or_resume(
            db,
            series_id=series.id,
            episode_id=episode.id,
            source_prompt="她被逼下跪，却亮出集团继承人身份",
            tags=["都市逆袭"],
            target_duration_seconds=60,
        )

    assert exc.value.attempts == 3
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    stage = saved_run.layers_json["script_generation"]["stages"]["dramatic_beats"]
    assert stage["attempts"] == 3
    assert stage["status"] == "failed"
    assert saved_run.layers_json["script_generation"]["human_intervention_required"] is True


@pytest.mark.asyncio
async def test_script_pipeline_resume_skips_completed_stage(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    manager = PipelineManager(pipeline=ScriptGenerationPipeline(
        model_client=FakeModelClient([beats]),
        gate_runner=FakeGate(["completed"]),
    ))
    run = manager.get_or_create_run(db, series_id=series.id, episode_id=episode.id)
    manager.mark_stage_completed_for_test(
        db,
        run=run,
        stage_name="dramatic_beats",
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        output=beats,
        gate_trace={"stage_status": "completed"},
    )
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([scenes, shots]),
        gate_runner=FakeGate(["completed", "completed"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    result = await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        episode_asset_scope=_test_asset_scope(),
    )

    assert result.dramatic_beats.beats[0].beat_type == DramaticBeatType.HOOK
    assert len(pipeline.model_client.calls) == 2


@pytest.mark.asyncio
async def test_script_pipeline_persists_structured_script_and_snapshots(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    manager = PipelineManager(pipeline=ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["completed", "completed", "completed"]),
    ))

    await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        episode_asset_scope=_test_asset_scope(),
    )

    saved_script = db.query(DbEpisodeScript).filter_by(episode_id=episode.id).one()
    assert saved_script.status == "completed"
    assert db.query(ScriptDramaticBeat).filter_by(script_id=saved_script.id).count() == 5
    assert db.query(ScriptSceneOutline).filter_by(script_id=saved_script.id).count() == 1
    assert db.query(ScriptVisualShot).filter_by(script_id=saved_script.id).count() == 1
    db.refresh(episode)
    assert episode.script_json["source"] == "dramatic_script_pipeline"
    assert "女主站在雨夜门口，破碎茶杯在脚边。" in episode.storyboard_json["frames"][0]["image_prompt"]
    assert "主体/角色:" in episode.storyboard_json["frames"][0]["image_prompt"]
    artifact_types = {
        artifact.artifact_type
        for artifact in db.query(AITextArtifact).filter_by(series_id=series.id).all()
    }
    assert {
        "episode_script",
        "storyboard",
        "dialogue",
        "image_prompt",
        "video_prompt",
    }.issubset(artifact_types)


@pytest.mark.asyncio
async def test_script_pipeline_preserves_layers_after_gate_commit_expires_run(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    manager = PipelineManager(pipeline=ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=CommittingFakeGate(["completed", "completed", "completed"]),
    ))

    await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        episode_asset_scope=_test_asset_scope(),
    )

    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    state = saved_run.layers_json["script_generation"]
    assert state["stages"]["dramatic_beats"]["gate_trace"]["stage_status"] == "completed"
    assert state["stages"]["scene_outlines"]["gate_trace"]["stage_status"] == "completed"
    assert state["stages"]["visual_shots"]["gate_trace"]["stage_status"] == "completed"
    assert state["stages"]["visual_shots"]["status"] == "completed"


@pytest.mark.asyncio
async def test_script_pipeline_storyboard_snapshot_has_precise_second_ranges(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _timed_stage_outputs()
    manager = PipelineManager(pipeline=ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["completed", "completed", "completed"]),
    ))

    await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=6,
        episode_asset_scope=_test_asset_scope(),
    )

    db.refresh(episode)
    frames = episode.storyboard_json["frames"]
    assert [frame["time_range"] for frame in frames] == ["0-2秒", "2-4秒", "4-6秒"]
    assert [(frame["start_second"], frame["end_second"]) for frame in frames] == [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
    assert "时间段: 2-4秒" in frames[1]["image_prompt"]
    assert "主体/角色:" in frames[1]["image_prompt"]
    assert "场景/环境:" in frames[1]["image_prompt"]
    assert "画面动作:" in frames[1]["image_prompt"]
    assert "秒段细节: 2-4秒:" in frames[1]["image_prompt"]
    assert "视线" in frames[1]["image_prompt"]
    assert "眉眼" in frames[1]["image_prompt"]
    assert "嘴角/唇部" in frames[1]["image_prompt"]
    assert "头部" in frames[1]["image_prompt"]
    assert "手部/身体" in frames[1]["image_prompt"]
    assert "镜头语言:" in frames[1]["video_prompt"]
    assert "连续性:" in frames[1]["video_prompt"]
    assert "秒段细节: 2-4秒:" in frames[1]["video_prompt"]
    assert "情绪由" in frames[1]["video_prompt"]
    assert "无黑屏、无转场" in frames[1]["video_prompt"]
    assert episode.storyboard_json["total_duration"] == 6.0
    storyboard_artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        episode_id=episode.id,
        artifact_type="storyboard",
    ).one()
    assert "2-4秒" in storyboard_artifact.content_text
