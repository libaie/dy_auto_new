"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_debate_policy 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DebatePolicy:
    """业务类：承载 DebatePolicy 相关的数据结构、状态或业务协作。

    类参数：arbiter、critic、defender、focus、policy_id、stage 承载该类的业务配置、状态或数据字段。
    """
    stage: str
    policy_id: str
    critic: str
    defender: str
    arbiter: str
    focus: tuple[str, ...]


DEBATE_POLICIES: dict[str, DebatePolicy] = {
    "story_planning": DebatePolicy(
        stage="story_planning",
        policy_id="story_planning.v1",
        critic="narrative_designer",
        defender="story_generator",
        arbiter="douyin_strategist",
        focus=("整季主线", "逐集差异", "连续性台账", "锁定角色和场景"),
    ),
    "style_lock": DebatePolicy(
        stage="style_lock",
        policy_id="style_lock.v1",
        critic="visual_storyteller",
        defender="image_prompt_engineer",
        arbiter="style_lock_quality_reviewer",
        focus=("角色规则", "场景规则", "参考图准备度", "视觉继承"),
    ),
    "storyboard": DebatePolicy(
        stage="storyboard",
        policy_id="storyboard.v1",
        critic="visual_storyteller",
        defender="narrative_designer",
        arbiter="storyboard_quality_reviewer",
        focus=("可执行分镜", "角色场景锚点", "连续性", "镜头时长"),
    ),
    "image_stage": DebatePolicy(
        stage="image_stage",
        policy_id="image_stage.v1",
        critic="visual_storyteller",
        defender="image_prompt_engineer",
        arbiter="image_stage_quality_reviewer",
        focus=("提示词完整性", "参考图继承", "provider 约束", "风格漂移风险"),
    ),
    "image_review": DebatePolicy(
        stage="image_review",
        policy_id="image_review.v1",
        critic="image_prompt_engineer",
        defender="visual_storyteller",
        arbiter="image_review_quality_reviewer",
        focus=("角色身份", "场景一致", "图片可用性", "图生视频准备度"),
    ),
    "video_stage": DebatePolicy(
        stage="video_stage",
        policy_id="video_stage.v1",
        critic="visual_storyteller",
        defender="short_video_editing_coach",
        arbiter="video_stage_quality_reviewer",
        focus=("片段时长", "动作意图", "首帧继承", "连续性"),
    ),
    "video_review": DebatePolicy(
        stage="video_review",
        policy_id="video_review.v1",
        critic="video_optimization_specialist",
        defender="short_video_editing_coach",
        arbiter="video_review_quality_reviewer",
        focus=("身份漂移", "运动稳定", "镜头意图", "合成准备度"),
    ),
    "compose_preflight": DebatePolicy(
        stage="compose_preflight",
        policy_id="compose_preflight.v1",
        critic="douyin_strategist",
        defender="video_optimization_specialist",
        arbiter="compose_quality_reviewer",
        focus=("剧集完整度", "节奏", "平台适配", "缺失资产"),
    ),
    "compose": DebatePolicy(
        stage="compose",
        policy_id="compose.v1",
        critic="douyin_strategist",
        defender="short_video_editing_coach",
        arbiter="compose_quality_reviewer",
        focus=("最终交付", "剪辑节奏", "音频字幕", "发布适配"),
    ),
}
DEBATE_STAGES = set(DEBATE_POLICIES)


def debate_policy_for_stage(stage: str) -> DebatePolicy:
    """业务函数：处理 debate_policy_for_stage 对应的业务流程、校验或数据转换。

    入参：stage 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        return DEBATE_POLICIES[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported agency debate stage: {stage}") from exc
