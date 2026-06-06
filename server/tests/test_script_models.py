import pytest
from pydantic import ValidationError

from app.models.script import (
    DramaticBeat,
    DramaticBeatList,
    DramaticBeatType,
    EpisodeScript,
    SceneOutline,
    SceneOutlineList,
    VisualShot,
    VisualShotList,
)


def _beats():
    return [
        DramaticBeat(beat_type=DramaticBeatType.HOOK, emotional_value="震惊", plot_summary="女主被当众羞辱，摔杯声压住全场。"),
        DramaticBeat(beat_type=DramaticBeatType.CONFLICT_1, emotional_value="憋屈", plot_summary="反派逼她签下不平等协议。"),
        DramaticBeat(beat_type=DramaticBeatType.REVERSAL, emotional_value="爽", plot_summary="女主亮出真实身份，局势倒转。"),
        DramaticBeat(beat_type=DramaticBeatType.CLIMAX, emotional_value="震撼", plot_summary="反派发现自己求错了人。"),
        DramaticBeat(beat_type=DramaticBeatType.CLIFFHANGER, emotional_value="紧张", plot_summary="真正幕后人推门出现。"),
    ]


def test_dramatic_beat_list_requires_five_core_beats():
    beat_list = DramaticBeatList(beats=_beats())

    assert [beat.beat_type for beat in beat_list.beats] == [
        DramaticBeatType.HOOK,
        DramaticBeatType.CONFLICT_1,
        DramaticBeatType.REVERSAL,
        DramaticBeatType.CLIMAX,
        DramaticBeatType.CLIFFHANGER,
    ]


def test_dramatic_beat_list_rejects_missing_core_beat():
    with pytest.raises(ValidationError, match="missing required dramatic beat"):
        DramaticBeatList(beats=_beats()[:-1])


def test_visual_shot_requires_positive_duration_and_emotional_narration():
    shot = VisualShot(
        shot_number=1,
        scene_number=1,
        beat_type=DramaticBeatType.HOOK,
        narration="震惊！你竟敢让我跪下？",
        visual_prompt="女主站在雨夜门口，破碎茶杯在脚边，强对比光。",
        video_prompt="镜头快速推近，女主抬眼，雨水划过脸颊。",
        duration=3.0,
    )

    assert shot.duration == 3.0


def test_visual_shot_rejects_narration_without_emotional_marker():
    with pytest.raises(ValidationError, match="emotional tone marker"):
        VisualShot(
            shot_number=1,
            scene_number=1,
            beat_type=DramaticBeatType.HOOK,
            narration="你让我跪下",
            visual_prompt="女主站在雨夜门口，破碎茶杯在脚边，强对比光。",
            video_prompt="镜头快速推近，女主抬眼，雨水划过脸颊。",
            duration=3.0,
        )


def test_episode_script_requires_structured_components():
    script = EpisodeScript(
        series_id="series-001",
        episode_id="episode-001",
        source_prompt="一句话短剧",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        dramatic_beats=DramaticBeatList(beats=_beats()),
        scene_outlines=SceneOutlineList(scenes=[
            SceneOutline(
                scene_number=1,
                dramatic_beat_type=DramaticBeatType.HOOK,
                location="雨夜豪门门口",
                characters=["女主", "反派"],
                conflict="反派逼女主下跪。",
                emotional_turn="从羞辱转为压迫。",
                visual_mandate="前3秒必须出现摔杯和身份反差。",
            )
        ]),
        visual_shots=VisualShotList(shots=[
            VisualShot(
                shot_number=1,
                scene_number=1,
                beat_type=DramaticBeatType.HOOK,
                narration="震惊！你竟敢让我跪下？",
                visual_prompt="女主站在雨夜门口，破碎茶杯在脚边，强对比光。",
                video_prompt="镜头快速推近，女主抬眼，雨水划过脸颊。",
                duration=3.0,
            )
        ]),
    )

    assert script.tags == ["都市逆袭"]
