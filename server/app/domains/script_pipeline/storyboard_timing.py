"""剧本流水线业务域模块。

剧本流水线业务域，负责剧本、分镜节奏和文本生产阶段衔接。本文件负责 storyboard_timing 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any


DEFAULT_TIMED_SHOT_SECONDS = 2.0


def _duration(value: Any, default_seconds: float) -> float:
    """业务函数：处理 _duration 对应的业务流程、校验或数据转换。"""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default_seconds
    return round(parsed if parsed > 0 else default_seconds, 2)


def format_second(value: float) -> str:
    """业务函数：处理 format_second 对应的业务流程、校验或数据转换。"""
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:g}"


def format_time_range(start_second: float, end_second: float) -> str:
    """业务函数：处理 format_time_range 对应的业务流程、校验或数据转换。"""
    return f"{format_second(start_second)}-{format_second(end_second)}秒"


def shot_durations_for_total(
    total_seconds: int | float,
    *,
    preferred_seconds: float = DEFAULT_TIMED_SHOT_SECONDS,
) -> list[float]:
    """业务函数：处理 shot_durations_for_total 对应的业务流程、校验或数据转换。"""
    remaining = _duration(total_seconds, preferred_seconds)
    preferred = max(0.1, float(preferred_seconds or DEFAULT_TIMED_SHOT_SECONDS))
    durations: list[float] = []
    while remaining > preferred:
        if durations and remaining - preferred < preferred:
            durations.append(round(remaining, 2))
            remaining = 0
            break
        durations.append(round(preferred, 2))
        remaining = round(remaining - preferred, 2)
    if remaining > 0:
        durations.append(round(remaining, 2))
    return durations or [round(preferred, 2)]


def annotate_frames_with_timing(
    frames: list[dict[str, Any]],
    *,
    default_duration_seconds: float = DEFAULT_TIMED_SHOT_SECONDS,
) -> list[dict[str, Any]]:
    """业务函数：处理 annotate_frames_with_timing 对应的业务流程、校验或数据转换。"""
    elapsed = 0.0
    timed_frames: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        duration = _duration(
            frame.get("duration") or frame.get("duration_seconds"),
            default_duration_seconds,
        )
        start_second = round(elapsed, 2)
        end_second = round(start_second + duration, 2)
        timed = dict(frame)
        timed["index"] = index
        timed["duration"] = duration
        timed["start_second"] = start_second
        timed["end_second"] = end_second
        timed["time_range"] = format_time_range(start_second, end_second)
        timed_frames.append(timed)
        elapsed = end_second
    return timed_frames


def annotate_storyboard_with_timing(
    storyboard: dict[str, Any],
    *,
    default_duration_seconds: float = DEFAULT_TIMED_SHOT_SECONDS,
) -> dict[str, Any]:
    """业务函数：处理 annotate_storyboard_with_timing 对应的业务流程、校验或数据转换。"""
    frames = storyboard.get("frames") if isinstance(storyboard, dict) else []
    if not isinstance(frames, list):
        frames = []
    object_frames = [frame for frame in frames if isinstance(frame, dict)]
    timed_frames = annotate_frames_with_timing(
        object_frames,
        default_duration_seconds=default_duration_seconds,
    )
    timed_storyboard = dict(storyboard or {})
    timed_storyboard["frames"] = timed_frames
    timed_storyboard["frame_count"] = len(timed_frames)
    timed_storyboard["total_duration"] = round(sum(float(frame["duration"]) for frame in timed_frames), 2)
    return timed_storyboard


def timed_storyboard_lines(storyboard: dict[str, Any]) -> list[str]:
    """业务函数：处理 timed_storyboard_lines 对应的业务流程、校验或数据转换。"""
    frames = storyboard.get("frames") if isinstance(storyboard, dict) else []
    if not isinstance(frames, list):
        return []
    lines: list[str] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        label = str(frame.get("time_range") or "")
        narration = str(frame.get("narration") or frame.get("voiceover") or frame.get("dialogue") or "")
        image_prompt = str(frame.get("image_prompt") or frame.get("visual_prompt") or "")
        video_prompt = str(frame.get("video_prompt") or frame.get("action") or "")
        parts = [part for part in [
            label,
            f"旁白: {narration}" if narration else "",
            f"画面: {image_prompt}" if image_prompt else "",
            f"动作: {video_prompt}" if video_prompt else "",
        ] if part]
        if parts:
            lines.append(" | ".join(parts))
    return lines


def _compact_text(value: str, fallback: str) -> str:
    """业务函数：处理 _compact_text 对应的业务流程、校验或数据转换。"""
    compacted = " ".join(str(value or "").split()).strip("；;，,。 ")
    return compacted or fallback


def build_second_level_motion_detail(
    *,
    time_range: str,
    action: str,
    emotion: str,
    raw_prompt: str = "",
) -> str:
    """业务函数：处理 build_second_level_motion_detail 对应的业务流程、校验或数据转换。"""
    action_text = _compact_text(action or raw_prompt, "执行本秒段剧情动作")
    emotion_text = _compact_text(emotion, "当前情绪")
    return (
        f"{time_range}: "
        f"视线先锁定动作目标，再在段尾给出明确落点；"
        f"眉眼呈现{emotion_text}，避免空泛表情；"
        f"嘴角/唇部随情绪轻微变化，不做无意义夸张；"
        f"头部有小幅转向或停顿，承接上一秒段姿态；"
        f"手部/身体完成“{action_text}”的可见动作；"
        f"情绪由{emotion_text}起步，在段尾落到清晰可见的表情或动作结果。"
    )


def build_detailed_image_prompt(
    *,
    time_range: str,
    subject: str,
    scene: str,
    action: str,
    shot_type: str,
    emotion: str,
    visual_style: str = "",
    raw_prompt: str = "",
    continuity: str = "",
) -> str:
    """业务函数：处理 build_detailed_image_prompt 对应的业务流程、校验或数据转换。"""
    second_level_detail = build_second_level_motion_detail(
        time_range=time_range,
        action=action,
        emotion=emotion,
        raw_prompt=raw_prompt,
    )
    return "\n".join(part for part in [
        f"时间段: {time_range}",
        f"主体/角色: {subject or '核心角色'}",
        f"场景/环境: {scene or '锁定场景'}",
        f"画面动作: {action or raw_prompt or '执行本秒段剧情动作'}",
        f"秒段细节: {second_level_detail}",
        f"镜头语言: {shot_type or 'medium'} 构图，主体动作清晰可见，画面只表现本秒段事件。",
        f"情绪/光线: {emotion or '符合剧情情绪'}；{visual_style or '保持已锁定视觉风格、光线和色彩'}",
        f"连续性: {continuity or '保持角色身份、服装、场景、道具和上一镜头动作连续'}",
        "收尾约束: 本秒段末尾停在可见表情或动作结果上，无黑屏、无转场。",
        f"原始画面提示: {raw_prompt}" if raw_prompt else "",
    ] if part)


def build_detailed_video_prompt(
    *,
    time_range: str,
    subject: str,
    scene: str,
    action: str,
    shot_type: str,
    camera_movement: str,
    emotion: str,
    raw_prompt: str = "",
    continuity: str = "",
) -> str:
    """业务函数：处理 build_detailed_video_prompt 对应的业务流程、校验或数据转换。"""
    second_level_detail = build_second_level_motion_detail(
        time_range=time_range,
        action=action,
        emotion=emotion,
        raw_prompt=raw_prompt,
    )
    return "\n".join(part for part in [
        f"时间段: {time_range}",
        f"主体/角色: {subject or '核心角色'}",
        f"场景/环境: {scene or '锁定场景'}",
        f"画面动作: {action or raw_prompt or '完成本秒段动作变化'}",
        f"秒段细节: {second_level_detail}",
        f"镜头语言: {shot_type or 'medium'}，{camera_movement or '稳定推进'}，动作起点和终点明确。",
        f"情绪/节奏: {emotion or '符合剧情情绪'}，节奏服务短视频留存，不跳过关键反应。",
        f"连续性: {continuity or '承接上一秒段姿态、视线、道具位置和光线方向'}",
        "收尾约束: 本秒段末尾停在可见表情或动作结果上，无黑屏、无转场。",
        f"原始视频提示: {raw_prompt}" if raw_prompt else "",
    ] if part)
