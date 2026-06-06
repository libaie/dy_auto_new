from app.db_models import (
    Episode,
    EpisodeScript as DbEpisodeScript,
    PipelineRun,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
    Series,
)
import pytest

from app.models.script import DramaticBeatType, EpisodeScript
from app.services.script_pipeline import PipelineManager, ScriptGenerationError, ScriptGenerationPipeline


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


@pytest.mark.asyncio
async def test_script_pipeline_runs_three_stages_sequentially(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
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
    )

    assert isinstance(result, EpisodeScript)
    assert [beat.beat_type for beat in result.dramatic_beats.beats][0] == DramaticBeatType.HOOK
    assert len(pipeline.model_client.calls) == 3
    assert [call["gate_name"] for call in pipeline.gate_runner.calls] == ["dramatic_beats", "scene_outlines"]
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    state = saved_run.layers_json["script_generation"]
    assert state["stages"]["visual_shots"]["status"] == "completed"


@pytest.mark.asyncio
async def test_script_pipeline_blocks_stage_two_when_gate_one_blocks(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["blocked"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    with pytest.raises(ScriptGenerationError, match="expert gate blocked"):
        await manager.start_or_resume(
            db,
            series_id=series.id,
            episode_id=episode.id,
            source_prompt="她被逼下跪，却亮出集团继承人身份",
            tags=["都市逆袭"],
            target_duration_seconds=60,
        )

    assert len(pipeline.model_client.calls) == 1
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    assert saved_run.layers_json["script_generation"]["human_intervention_required"] is True


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
        gate_runner=FakeGate(["completed"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    result = await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
    )

    assert result.dramatic_beats.beats[0].beat_type == DramaticBeatType.HOOK
    assert len(pipeline.model_client.calls) == 2
