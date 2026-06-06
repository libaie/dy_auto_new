from app.models.script import DramaticBeatType, PipelineStage
from app.services.script_pipeline import DynamicPromptBuilder


def test_prompt_builder_injects_hook_and_tag_constraints():
    builder = DynamicPromptBuilder()

    payload = builder.build(
        stage=PipelineStage.DRAMATIC_BEATS,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭", "歪嘴战神"],
        target_duration_seconds=60,
        beat_types=[DramaticBeatType.HOOK],
    )

    assert "只输出严格 JSON" in payload.system_prompt
    assert "前3秒必须出现视觉冲突" in payload.user_prompt
    assert "台词字数不得超过15字" in payload.user_prompt
    assert "现代层级压力" in payload.user_prompt
    assert "被压制的主角身份" in payload.user_prompt


def test_prompt_builder_injects_climax_constraints():
    builder = DynamicPromptBuilder()

    payload = builder.build(
        stage=PipelineStage.VISUAL_SHOTS,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["主母黑化"],
        target_duration_seconds=60,
        beat_types=[DramaticBeatType.CLIMAX],
        previous_outputs={"scene_outlines": {"scenes": []}},
    )

    assert "必须完成身份反转" in payload.user_prompt
    assert "低角度仰拍" in payload.user_prompt
    assert "背叛" in payload.user_prompt
    assert "不得输出 Markdown" in payload.system_prompt
