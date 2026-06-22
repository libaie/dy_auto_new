"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 one_sentence_video_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import timedelta
from math import ceil
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.db.models.video_production import ProductionScene, ProductionSegment, ProductionShot, VideoProductionRun
from app.db.models import (
    Character,
    Episode,
    Scene,
    Series,
)
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
from app.domains.ai_video_series.series_planning_service import ensure_episode_placeholders
from app.domains.creative_library import reference_asset_service
from app.domains.creative_library.reference_asset_service import ReferenceAssetError
from app.domains.creative_library.visual_style_inference_service import (
    DEFAULT_NEGATIVE,
    append_visual_style_constraints,
    infer_visual_style_from_story,
    merge_visual_style,
)
from app.domains.model_configuration.runtime_model_config import (
    RuntimeModelConfigError,
    resolve_runtime_model_config,
)
from app.domains.production_observability.production_observability_service import (
    record_production_event,
)
from app.domains.script_pipeline.storyboard_timing import format_time_range
from app.domains.video_production import production_plan_service, production_run_service
from app.domains.video_production.production_errors import ProductionErrorCode, ProductionRepairableError
from app.domains.agency_operations.video_agency_team import ensure_video_agency_team
from app.domains.video_production.video_production_service import VideoProductionError
from app.domains.video_production.video_production_run_types import (
    MOCK_SERIES_SCALE,
    REAL_SHORT_E2E,
    validate_run_type,
)


DEFAULT_TARGET_SECONDS = 60
MAX_STORYBOARD_FRAME_SECONDS = 8
MIN_MULTI_SHOT_SECONDS = 15
MIN_MULTI_SHOT_FRAME_COUNT = 3
MAX_MATERIALIZED_STORYBOARD_FRAMES = 120
REAL_SHORT_MAX_MATERIALIZED_SECONDS = MAX_MATERIALIZED_STORYBOARD_FRAMES * MAX_STORYBOARD_FRAME_SECONDS
REAL_SHORT_MIN_SECONDS = 5
REAL_SHORT_MAX_SECONDS = REAL_SHORT_MAX_MATERIALIZED_SECONDS
CHARACTER_REFERENCE_FIELDS = (
    "avatar_front_url",
    "avatar_side_url",
    "avatar_threequarter_url",
    "avatar_fullbody_url",
)
SCENE_REFERENCE_FIELDS = (
    "reference_wideshot_url",
    "reference_midshot_url",
    "reference_aerial_url",
)
BLOCKING_AGENCY_STATUSES = {"blocked", "failed"}
ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS", "8"))
ONE_SENTENCE_REFERENCE_RECHECK_SECONDS = float(os.getenv("DY_AUTO_ONE_SENTENCE_REFERENCE_RECHECK_SECONDS", "30"))
ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS = float(os.getenv("DY_AUTO_ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS", "8"))
ONE_SENTENCE_REFERENCE_RUNNING_STATUS = "reference_generation_running"
ONE_SENTENCE_REFERENCE_BLOCKED_STATUS = "reference_generation_blocked"


def _missing_agency_trace(stage: str, exc: Exception) -> dict[str, Any]:
    """业务函数：处理 _missing_agency_trace 对应的业务流程、校验或数据转换。

    入参：stage、exc 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": str(exc),
    }


def _timeout_trace(stage: str, error_code: str, timeout_seconds: float) -> dict[str, Any]:
    """业务函数：处理 _timeout_trace 对应的业务流程、校验或数据转换。

    入参：stage、error_code、timeout_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "stage": stage,
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": error_code,
        "error_message": f"{stage} exceeded {timeout_seconds:g} seconds.",
    }


def _safe_reference_error_details(exc: ReferenceAssetError) -> dict[str, Any]:
    """业务函数：处理 _safe_reference_error_details 对应的业务流程、校验或数据转换。

    入参：exc 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    allowed_keys = {"image_task_id", "status", "scene_key", "provider_code", "status_code"}
    details = exc.details if isinstance(exc.details, dict) else {}
    return {key: details[key] for key in allowed_keys if details.get(key) is not None}


def _reference_deferred_trace(exc: ReferenceAssetError) -> dict[str, Any]:
    """业务函数：处理 _reference_deferred_trace 对应的业务流程、校验或数据转换。

    入参：exc 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    trace = {
        "stage": "reference_generation",
        "stage_status": "partial",
        "invocation_ids": [],
        "invocations": [],
        "error_code": exc.code,
        "error_message": exc.message,
        "details": _safe_reference_error_details(exc),
    }
    if exc.code == "REFERENCE_PROVIDER_STILL_RUNNING":
        trace["next_reference_check_at"] = (
            bj_now() + timedelta(seconds=max(1.0, ONE_SENTENCE_REFERENCE_RECHECK_SECONDS))
        ).isoformat()
    return trace


def _agency_trace_status(*traces: dict[str, Any] | None) -> str:
    """业务函数：处理 _agency_trace_status 对应的业务流程、校验或数据转换。

    入参：traces 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return "complete" if traces and all(trace and not trace.get("error_code") for trace in traces) else "partial"


def _dedupe_urls(urls: list[str]) -> list[str]:
    """业务函数：处理 _dedupe_urls 对应的业务流程、校验或数据转换。

    入参：urls 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return list(dict.fromkeys(url for url in urls if url))


def _reference_urls_from_fields(row: Any, fields: tuple[str, ...]) -> list[str]:
    """业务函数：处理 _reference_urls_from_fields 对应的业务流程、校验或数据转换。

    入参：row、fields 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return _dedupe_urls([
        value
        for field in fields
        if reference_asset_service.reference_url_is_usable(value := getattr(row, field, None))
    ])


def _reference_instruction(character_urls: list[str], style_urls: list[str]) -> str:
    """业务函数：处理 _reference_instruction 对应的业务流程、校验或数据转换。

    入参：character_urls、style_urls 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    parts = []
    if character_urls:
        parts.append(
            "@Image 1 locks the protagonist face, hairstyle, outfit, and body proportions; "
            "additional character images reinforce side, three-quarter, and full-body identity."
        )
    if style_urls:
        parts.append("Style reference images lock scene layout, lighting, palette, and mood.")
    return " ".join(parts)


def _agency_trace_blocks(trace: dict[str, Any] | None) -> bool:
    """业务函数：处理 _agency_trace_blocks 对应的业务流程、校验或数据转换。

    入参：trace 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return bool(trace and trace.get("stage_status") in BLOCKING_AGENCY_STATUSES)


def _raise_blocked_agency_gate(
    db: Session,
    run: Any,
    *traces: dict[str, Any] | None,
) -> None:
    """业务函数：处理 _raise_blocked_agency_gate 对应的业务流程、校验或数据转换。

    入参：db、run、traces 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    blocking_traces = [trace for trace in traces if _agency_trace_blocks(trace)]
    if not blocking_traces:
        return
    first = blocking_traces[0]
    invocation_ids = []
    for trace in blocking_traces:
        invocation_ids.extend([str(item) for item in (trace.get("invocation_ids") or []) if item])
    run.status = "blocked"
    run.current_stage = str(first.get("stage") or "expert_review")
    record_production_event(
        db,
        event_type="one_sentence.expert_gate_blocked",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload={
            "stage": first.get("stage"),
            "stage_status": first.get("stage_status"),
            "invocation_ids": invocation_ids,
        },
    )
    db.commit()
    raise ProductionRepairableError(
        code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
        message=f"{first.get('stage', 'expert')} expert review blocked one-sentence production.",
        cause="one_sentence_expert_gate_blocked",
        repair_action="Open the expert trace, fix required style/storyboard changes, then regenerate one-sentence production.",
        repair_route=f"/video-production/{run.id}",
        retryable=True,
        affected_ids=invocation_ids or [run.id],
    )


def _clean_prompt(prompt: str) -> str:
    """业务函数：处理 _clean_prompt 对应的业务流程、校验或数据转换。

    入参：prompt 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return " ".join((prompt or "").strip().split())


def _story_content_prompt(prompt: str) -> str:
    """业务函数：处理 _story_content_prompt 对应的业务流程、校验或数据转换。

    入参：prompt 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    clean = _clean_prompt(prompt)
    if not clean:
        return clean
    text = re.sub(
        r"([,，、]\s*)?(竖屏|横屏|vertical|horizontal|9\s*[:：]\s*16|16\s*[:：]\s*9)(\s*[,，、])?",
        "，",
        clean,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"([,，、]\s*)?\d+\s*秒\s*(以内|内|左右)?(\s*[,，、])?",
        "，",
        text,
    )
    text = re.sub(r"[，,、]+", "，", text)
    text = re.sub(r"\s+", " ", text).strip(" ，,、")
    return text or clean


def _contains_cjk(text: str) -> bool:
    """业务函数：处理 _contains_cjk 对应的业务流程、校验或数据转换。

    入参：text 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _static_story_prompt(prompt: str) -> str:
    """业务函数：处理 _static_story_prompt 对应的业务流程、校验或数据转换。

    入参：prompt 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    clean = _story_content_prompt(prompt)
    text = re.sub(r"([，,。；;]\s*)?镜头[^，,。；;]*(?:[，,。；;]\s*)?", "，", clean)
    text = re.sub(r"[，,、]+", "，", text)
    text = re.sub(r"\s+", " ", text).strip(" ，,、")
    return text or clean


def _positive_visual_style_prompt(visual_style: dict[str, Any]) -> str:
    """业务函数：处理 _positive_visual_style_prompt 对应的业务流程、校验或数据转换。

    入参：visual_style 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    prompt = str((visual_style or {}).get("prompt") or "").strip()
    for phrase in ("no text", "no logo", "no watermark"):
        prompt = re.sub(rf"([,，]\s*)?{re.escape(phrase)}(\s*[,，])?", ", ", prompt, flags=re.IGNORECASE)
    return re.sub(r"\s*,\s*", ", ", prompt).strip(" ,，")


def _negative_prompt(visual_style: dict[str, Any]) -> str:
    """业务函数：处理 _negative_prompt 对应的业务流程、校验或数据转换。

    入参：visual_style 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    parts = [
        str((visual_style or {}).get("negative_prompt") or ""),
        DEFAULT_NEGATIVE,
        "extra fingers, distorted hands, blurry, malformed face, duplicated limbs",
    ]
    values: list[str] = []
    for part in parts:
        for value in re.split(r"[,，]", part):
            value = value.strip()
            if value and value.lower() not in {item.lower() for item in values}:
                values.append(value)
    return ", ".join(values)


def _title_from_prompt(prompt: str, explicit_title: str | None = None) -> str:
    """业务函数：处理 _title_from_prompt 对应的业务流程、校验或数据转换。

    入参：prompt、explicit_title 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()[:80]
    clean = _clean_prompt(prompt)
    return clean[:28] + ("..." if len(clean) > 28 else "")


def _segment_durations(total_seconds: int) -> list[int]:
    """业务函数：处理 _segment_durations 对应的业务流程、校验或数据转换。

    入参：total_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    frame_count = max(1, ceil(total_seconds / MAX_STORYBOARD_FRAME_SECONDS))
    if total_seconds >= MIN_MULTI_SHOT_SECONDS:
        frame_count = max(MIN_MULTI_SHOT_FRAME_COUNT, frame_count)
    base = total_seconds // frame_count
    remainder = total_seconds % frame_count
    return [base + (1 if index < remainder else 0) for index in range(frame_count)]


def _shot_type(index: int, total: int) -> str:
    """业务函数：处理 _shot_type 对应的业务流程、校验或数据转换。

    入参：index、total 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if total == 1:
        return "medium"
    sequence = ["wide", "medium", "close_up", "medium"]
    return sequence[index % len(sequence)]


def _camera_language(shot_type: str) -> str:
    """业务函数：处理 _camera_language 对应的业务流程、校验或数据转换。

    入参：shot_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if shot_type == "wide":
        return "35mm lens, wide establishing composition, wet foreground reflections, deep background layers"
    if shot_type == "close_up":
        return "85mm macro lens, shallow depth of field, tactile detail, softly blurred background"
    return "50mm lens, medium composition, clear hand action and readable facial expression"


def _shot_focus(prompt: str, index: int, total: int) -> str:
    """业务函数：处理 _shot_focus 对应的业务流程、校验或数据转换。

    入参：prompt、index、total 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if _contains_cjk(prompt):
        if total <= 1:
            return f"单帧画面聚焦核心剧情瞬间：{prompt}"
        if index == 0:
            return f"雨夜开场画面，湿石板路、红伞、老剧院入口和火漆旧信同时建立悬疑关系；故事线索：{prompt}"
        if index == total - 1:
            return "特写画面聚焦带火漆印章的旧信和伞沿雨滴，背景剧院灯牌虚化，悬念停在关键信物上"
        return "中景画面聚焦主角伸手接过旧信的动作，红伞遮住部分面部，雨水沿袖口滴落，神情警觉"
    if total <= 1:
        return f"single still frame focused on the central story moment: {prompt}"
    if index == 0:
        return f"opening still frame establishes the key object, protagonist, and environment with immediate clarity: {prompt}"
    if index == total - 1:
        return "close-up still frame focused on the decisive clue, tactile object detail, and a suspenseful unresolved expression"
    return "medium still frame focused on the protagonist reacting to the clue with a clear hand action and readable emotion"


def _video_motion(prompt: str, index: int, total: int, duration_seconds: int | float = 5) -> str:
    """业务函数：处理 _video_motion 对应的业务流程、校验或数据转换。

    入参：prompt、index、total、duration_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    duration_label = f"{duration_seconds:g}" if float(duration_seconds).is_integer() else f"{duration_seconds:.2f}".rstrip("0").rstrip(".")
    if _contains_cjk(prompt):
        if total <= 1:
            return f"{duration_label}秒图生视频，保持主体稳定，轻微推进核心剧情瞬间：{prompt}"
        if index == 0:
            return f"{duration_label}秒图生视频，雨水自然下落，镜头缓慢推向老剧院门口的红伞和旧信"
        if index == total - 1:
            return f"{duration_label}秒图生视频，微距缓慢推进火漆印章与伞沿雨滴，背景保持浅景深虚化"
        return f"{duration_label}秒图生视频，主角缓慢伸手接过旧信，红伞轻微晃动，雨滴沿袖口滑落"
    if total <= 1:
        return f"{duration_label}-second image-to-video shot with restrained physical motion around the central story moment: {prompt}"
    if index == 0:
        return f"{duration_label}-second image-to-video shot with natural rain motion and a slow push toward the mystery object"
    if index == total - 1:
        return f"{duration_label}-second image-to-video shot with a gentle macro push toward the final clue and shallow depth of field"
    return f"{duration_label}-second image-to-video shot with a subtle protagonist reaction and a clear hand movement connecting the clue"


def _narration_line(prompt: str, index: int, total: int) -> str:
    """业务函数：处理 _narration_line 对应的业务流程、校验或数据转换。

    入参：prompt、index、total 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if _contains_cjk(prompt):
        if total <= 1:
            return prompt
        if index == 0:
            return "雨夜里，线索突然递到眼前。"
        if index == total - 1:
            return "火漆印章背后，到底是谁在等？"
        return "那封旧信，把他推向剧院深处。"
    if total <= 1:
        return prompt
    if index == 0:
        return "The clue appears before anyone is ready."
    if index == total - 1:
        return "Who left this clue behind?"
    return "One small detail pulls the story forward."


def _scene_location_from_prompt(prompt: str) -> str:
    """业务函数：处理 _scene_location_from_prompt 对应的业务流程、校验或数据转换。

    入参：prompt 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    lowered = prompt.lower()
    details = []
    if "雨" in prompt or "rain" in lowered:
        details.append("rain-slick surfaces, visible raindrops, wet reflections")
    if "霓虹" in prompt or "neon" in lowered:
        details.append("neon signage and colored reflections")
    if "街" in prompt or "street" in lowered:
        details.append("urban street depth with foreground, midground, and background layers")
    if "剧场" in prompt or "theater" in lowered:
        details.append("abandoned theater interior with mirrors, stage depth, and practical light sources")
    if not details:
        details.append("a concrete story-specific environment with clear foreground action and background depth")
    return f"{'; '.join(details)}. Main story environment: {prompt}"


def _shot_beat(prompt: str, index: int, total: int, duration_seconds: int | float = 5) -> dict[str, str]:
    """业务函数：处理 _shot_beat 对应的业务流程、校验或数据转换。

    入参：prompt、index、total、duration_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    shot_type = _shot_type(index, total)
    if total <= 1:
        return {
            "label": "core story moment",
            "image": _shot_focus(prompt, index, total),
            "video": _video_motion(prompt, index, total, duration_seconds),
            "narration": _narration_line(prompt, index, total),
            "emotion": "focused",
            "camera": _camera_language(shot_type),
        }
    if index == 0:
        return {
            "label": "opening hook",
            "image": _shot_focus(prompt, index, total),
            "video": _video_motion(prompt, index, total, duration_seconds),
            "narration": _narration_line(prompt, index, total),
            "emotion": "suspense",
            "camera": _camera_language(shot_type),
        }
    if index == total - 1:
        return {
            "label": "close-up reveal and audience question",
            "image": _shot_focus(prompt, index, total),
            "video": _video_motion(prompt, index, total, duration_seconds),
            "narration": _narration_line(prompt, index, total),
            "emotion": "intrigued",
            "camera": _camera_language(shot_type),
        }
    return {
        "label": "investigation beat",
        "image": _shot_focus(prompt, index, total),
        "video": _video_motion(prompt, index, total, duration_seconds),
        "narration": _narration_line(prompt, index, total),
        "emotion": "focused",
        "camera": _camera_language(shot_type),
    }


def _build_style_lock(series: Series, character: Character, scene: Scene, prompt: str) -> dict[str, Any]:
    """业务函数：处理 _build_style_lock 对应的业务流程、校验或数据转换。

    入参：series、character、scene、prompt 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    character_reference_urls = _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS)
    scene_reference_urls = _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS)
    inferred_visual_style = infer_visual_style_from_story(
        prompt,
        series.title,
        series.logline,
        series.genre,
        character.appearance_desc,
        character.outfit_desc,
        scene.location_desc,
        scene.lighting,
        scene.mood,
    )
    visual_style = merge_visual_style(
        {
            "aspect_ratio": "9:16",
            "color_policy": "keep lighting and palette consistent across every shot",
            "reference_urls": scene_reference_urls[:3],
        },
        inferred_visual_style,
    )
    style_lock = {
            "locked": True,
            "version": 1,
            "source": "one_sentence",
            "series_id": series.id,
            "input_prompt": prompt,
            "visual_style": visual_style,
            "audio_packaging": {
                "voice_policy": "use project default TTS unless a character voice is configured",
                "bgm_policy": "restrained background music, low volume, do not overpower narration",
            },
            "edit_packaging": {
                "subtitle_style": "bottom safe-area subtitles with high contrast",
                "transition_style": "clean hard cuts between shots",
                "intro_outro": "none for the first automatic draft",
                "watermark": "",
            },
            "characters": [{
                "id": character.id,
                "name": character.name,
                "role_type": character.role_type,
                "appearance_desc": character.appearance_desc,
                "outfit_desc": character.outfit_desc,
                "reference_urls": character_reference_urls,
            }],
            "scenes": [{
                "id": scene.id,
                "name": scene.name,
                "scene_type": scene.scene_type,
                "location_desc": scene.location_desc,
                "lighting": scene.lighting,
                "mood": scene.mood,
                "reference_urls": scene_reference_urls,
            }],
            "style_anchors": [
                {"role": "style_reference", "url": url, "source": "scene_reference"}
                for url in scene_reference_urls[:3]
            ],
            "missing_assets": [],
    }
    ensure_video_agency_team(style_lock)
    return {"style_lock": style_lock}


def _storyboard_frame_values(storyboard: dict[str, Any], key: str) -> list[str]:
    """业务函数：处理 _storyboard_frame_values 对应的业务流程、校验或数据转换。

    入参：storyboard、key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return [
        str(frame.get(key) or "").strip()
        for frame in storyboard.get("frames", [])
        if str(frame.get(key) or "").strip()
    ]


def _record_one_sentence_text_artifacts(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    run: VideoProductionRun,
    prompt: str,
    story_bible: dict[str, Any],
    storyboard: dict[str, Any],
) -> None:
    """业务函数：处理 _record_one_sentence_text_artifacts 对应的业务流程、校验或数据转换。

    入参：db、series、episode、run、prompt、story_bible、storyboard 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    service = AITextArtifactService(db)
    frame_narration = _storyboard_frame_values(storyboard, "narration")
    image_prompts = _storyboard_frame_values(storyboard, "image_prompt")
    video_prompts = _storyboard_frame_values(storyboard, "video_prompt")
    all_episodes = (
        db.query(Episode)
        .filter(Episode.series_id == series.id)
        .order_by(Episode.episode_number)
        .all()
    )
    style_lock = story_bible.get("style_lock", {}) if isinstance(story_bible, dict) else {}
    characters = style_lock.get("characters", []) if isinstance(style_lock, dict) else []
    scenes = style_lock.get("scenes", []) if isinstance(style_lock, dict) else []
    episode_outlines = [
        _build_one_sentence_episode_outline(
            prompt=prompt,
            episode_number=ep.episode_number,
            total_episodes=series.total_episodes,
            character_ids=[item.get("id") for item in characters if item.get("id")],
            scene_ids=[item.get("id") for item in scenes if item.get("id")],
        )
        for ep in all_episodes
    ]
    continuity_ledger = {
        "schema_version": "series.continuity.v1",
        "series_id": series.id,
        "total_episodes": series.total_episodes,
        "mainline": prompt,
        "episode_timeline": [
            {
                "episode_number": outline["episode_number"],
                "goal": outline["episode_goal"],
                "handoff": outline["previous_episode_handoff"],
                "next_hook": outline["next_hook"],
            }
            for outline in episode_outlines
        ],
        "character_states": [
            {
                "character_id": item.get("id"),
                "name": item.get("name"),
                "state_after_latest_episode": "introduced" if item.get("id") else "unknown",
                "visual_reference_urls": item.get("reference_urls", []),
            }
            for item in characters
        ],
        "scene_anchors": [
            {
                "scene_id": item.get("id"),
                "name": item.get("name"),
                "reference_urls": item.get("reference_urls", []),
            }
            for item in scenes
        ],
        "open_foreshadowing": [
            {
                "episode_number": outline["episode_number"],
                "hook": outline["next_hook"],
            }
            for outline in episode_outlines[:-1]
        ],
        "forbidden_contradictions": [
            "Do not change approved character identity or visual anchors without creating a new artifact version.",
            "Do not resolve a previous episode hook without recording the resolution in continuity writeback.",
        ],
    }
    series_story_plan = {
        "schema_version": "series.story_plan.v1",
        "series_id": series.id,
        "title": series.title,
        "logline": prompt,
        "target_episode_count": series.total_episodes,
        "story_engine": prompt,
        "season_promise": f"围绕“{prompt}”逐集升级悬念、人物选择和视觉钩子。",
        "character_ids": [item.get("id") for item in characters if item.get("id")],
        "scene_ids": [item.get("id") for item in scenes if item.get("id")],
        "episode_numbers": [outline["episode_number"] for outline in episode_outlines],
    }
    season_arc = {
        "schema_version": "series.season_arc.v1",
        "series_id": series.id,
        "arc_summary": f"从一句话主线出发，前集建立悬念，中段逐集加压，最终收束核心问题：{prompt}",
        "turning_points": [
            {
                "episode_number": outline["episode_number"],
                "beat": (
                    "setup"
                    if outline["episode_number"] == 1
                    else "finale"
                    if outline["episode_number"] >= series.total_episodes
                    else "escalation"
                ),
                "purpose": outline["episode_goal"],
                "next_hook": outline["next_hook"],
            }
            for outline in episode_outlines
        ],
    }
    artifact_specs = [
        {
            "artifact_type": "series_bible",
            "target_type": "series",
            "target_id": series.id,
            "episode_id": None,
            "content_json": story_bible,
            "content_text": series.logline or prompt,
            "stage": "style_lock",
        },
        {
            "artifact_type": "series_story_plan",
            "target_type": "series",
            "target_id": series.id,
            "episode_id": None,
            "content_json": series_story_plan,
            "content_text": series_story_plan["season_promise"],
            "stage": "series_story_planning",
        },
        {
            "artifact_type": "season_arc",
            "target_type": "series",
            "target_id": series.id,
            "episode_id": None,
            "content_json": season_arc,
            "content_text": season_arc["arc_summary"],
            "stage": "season_arc",
        },
        {
            "artifact_type": "continuity_ledger",
            "target_type": "series",
            "target_id": series.id,
            "episode_id": None,
            "content_json": continuity_ledger,
            "content_text": prompt,
            "stage": "continuity_planning",
        },
        {
            "artifact_type": "storyboard",
            "target_type": "episode",
            "target_id": episode.id,
            "episode_id": episode.id,
            "content_json": storyboard,
            "content_text": "\n".join(frame_narration),
            "stage": "storyboard",
        },
        {
            "artifact_type": "dialogue",
            "target_type": "episode",
            "target_id": episode.id,
            "episode_id": episode.id,
            "content_json": {"lines": frame_narration},
            "content_text": "\n".join(frame_narration),
            "stage": "storyboard",
        },
        {
            "artifact_type": "image_prompt",
            "target_type": "episode",
            "target_id": episode.id,
            "episode_id": episode.id,
            "content_json": {"prompts": image_prompts},
            "content_text": "\n".join(image_prompts),
            "stage": "image_prompt",
        },
        {
            "artifact_type": "video_prompt",
            "target_type": "episode",
            "target_id": episode.id,
            "episode_id": episode.id,
            "content_json": {"prompts": video_prompts},
            "content_text": "\n".join(video_prompts),
            "stage": "video_prompt",
        },
    ]
    for ep, outline in zip(all_episodes, episode_outlines):
        artifact_specs.append({
            "artifact_type": "episode_outline",
            "target_type": "episode",
            "target_id": ep.id,
            "episode_id": ep.id,
            "content_json": outline,
            "content_text": outline["episode_goal"],
            "stage": "episode_planning",
        })

    for spec in artifact_specs:
        belongs_to_current_run = (
            spec["target_type"] == "series"
            or spec["target_id"] == episode.id
        )
        artifact = service.create_artifact(
            series_id=series.id,
            episode_id=spec["episode_id"],
            run_id=run.id if belongs_to_current_run else None,
            production_plan_id=run.production_plan_id if belongs_to_current_run else None,
            target_type=spec["target_type"],
            target_id=spec["target_id"],
            artifact_type=spec["artifact_type"],
            source_type="ai",
            input_json={"prompt": prompt, "source": "one_sentence"},
            content_json=spec["content_json"],
            content_text=spec["content_text"],
            model_trace_json={"source": "one_sentence", "stage": spec["stage"]},
            created_by="one_sentence",
        )
        approved = service.approve_artifact(artifact.id, actor_user_id="one_sentence")
        if belongs_to_current_run:
            service.bind_consumer(
                approved.id,
                consumer_type="video_production_run",
                consumer_id=run.id,
                run_id=run.id,
                metadata_json={"source": "one_sentence", "stage": spec["stage"]},
            )


def _build_one_sentence_episode_outline(
    *,
    prompt: str,
    episode_number: int,
    total_episodes: int,
    character_ids: list[str],
    scene_ids: list[str],
) -> dict[str, Any]:
    """业务函数：处理 _build_one_sentence_episode_outline 对应的业务流程、校验或数据转换。

    入参：prompt、episode_number、total_episodes、character_ids、scene_ids 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if episode_number == 1:
        previous_handoff = ""
        episode_goal = f"建立主线悬念：{prompt}"
    else:
        previous_handoff = f"承接第 {episode_number - 1} 集留下的线索和人物状态。"
        episode_goal = f"推进主线第 {episode_number} 阶段，延续核心冲突并保持人物动机一致。"
    next_hook = (
        "完成系列主线收束。"
        if episode_number >= total_episodes
        else f"留下通往第 {episode_number + 1} 集的新线索。"
    )
    return {
        "schema_version": "series.episode_outline.v1",
        "episode_number": episode_number,
        "title": f"Episode {episode_number}",
        "hook": (
            f"用一句话主线的最强视觉冲突开场：{prompt}"
            if episode_number == 1
            else f"从第 {episode_number - 1} 集留下的线索和情绪余波切入。"
        ),
        "episode_goal": episode_goal,
        "previous_episode_handoff": previous_handoff,
        "central_conflict": prompt,
        "reversal": f"第 {episode_number} 集中段让主角对线索、人物关系或危险来源产生新的误判。",
        "cliffhanger": next_hook,
        "next_episode_handoff": next_hook,
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "character_state_changes": [
            {
                "character_id": character_id,
                "change": "introduced" if episode_number == 1 else "state advances from previous episode",
            }
            for character_id in character_ids
        ],
        "foreshadowing_introduced": [] if episode_number >= total_episodes else [next_hook],
        "foreshadowing_resolved": [] if episode_number == 1 else [previous_handoff],
        "next_hook": next_hook,
    }


def _without_agency_trace(value: dict[str, Any]) -> dict[str, Any]:
    """业务函数：处理 _without_agency_trace 对应的业务流程、校验或数据转换。

    入参：value 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    clean = dict(value or {})
    clean.pop("agency_trace", None)
    return clean


def _first_linked_character_and_scene(db: Session, series: Series) -> tuple[Character | None, Scene | None]:
    """业务函数：处理 _first_linked_character_and_scene 对应的业务流程、校验或数据转换。

    入参：db、series 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    character = series.characters[0] if series.characters else None
    scene = series.scenes[0] if series.scenes else None
    if character and scene:
        return character, scene
    character = db.query(Character).join(Series.characters).filter(Series.id == series.id).first()
    scene = db.query(Scene).join(Series.scenes).filter(Series.id == series.id).first()
    return character, scene


def _set_run_reference_generation_state(
    db: Session,
    run: VideoProductionRun,
    *,
    status: str,
    trace: dict[str, Any],
    autostart_images: bool,
) -> None:
    """业务函数：处理 _set_run_reference_generation_state 对应的业务流程、校验或数据转换。

    入参：db、run、status、trace、autostart_images 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    model_trace = dict(run.model_trace_json or {})
    one_sentence = dict(model_trace.get("one_sentence") or {})
    one_sentence["reference_generation"] = trace
    one_sentence["autostart_images_after_references"] = bool(autostart_images)
    model_trace["one_sentence"] = one_sentence
    run.model_trace_json = model_trace
    run.status = status
    run.current_stage = "reference_generation"
    if status == ONE_SENTENCE_REFERENCE_RUNNING_STATUS:
        run.error_message = None
    run.updated_at = bj_now()
    db.commit()


def _mark_storyboard_ready_for_image_start(db: Session, run: VideoProductionRun) -> VideoProductionRun:
    """业务函数：处理 _mark_storyboard_ready_for_image_start 对应的业务流程、校验或数据转换。

    入参：db、run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    run.status = "storyboard_ready"
    run.current_stage = "storyboard_ready"
    run.error_message = None
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run


def _is_past_one_sentence_reference_generation(run: VideoProductionRun) -> bool:
    """业务函数：处理 _is_past_one_sentence_reference_generation 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return run.status not in {
        "draft",
        ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
        ONE_SENTENCE_REFERENCE_BLOCKED_STATUS,
    }


def _storyboard_frames_by_id(storyboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """业务函数：处理 _storyboard_frames_by_id 对应的业务流程、校验或数据转换。

    入参：storyboard 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        str(frame.get("frame_id")): frame
        for frame in (storyboard.get("frames") or [])
        if isinstance(frame, dict) and frame.get("frame_id")
    }


def _refresh_segment_references_from_storyboard(
    db: Session,
    run: VideoProductionRun,
    storyboard: dict[str, Any],
    style_lock: dict[str, Any],
) -> None:
    """业务函数：处理 _refresh_segment_references_from_storyboard 对应的业务流程、校验或数据转换。

    入参：db、run、storyboard、style_lock 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not run.production_episode_id:
        return
    frames = _storyboard_frames_by_id(storyboard)
    ordered_frames = [frame for frame in (storyboard.get("frames") or []) if isinstance(frame, dict)]
    if not frames and not ordered_frames:
        return
    rows = (
        db.query(ProductionSegment, ProductionShot)
        .join(ProductionShot, ProductionSegment.shot_plan_id == ProductionShot.id)
        .filter(ProductionShot.scene_plan_id.in_(
            db.query(ProductionScene.id)
            .filter(ProductionScene.episode_plan_id == run.production_episode_id)
        ))
        .order_by(ProductionShot.order_index.asc(), ProductionSegment.order_index.asc())
        .all()
    )
    for segment, shot in rows:
        frame = frames.get(str(shot.shot_id))
        if not frame and ordered_frames:
            frame_index = max(0, int(shot.order_index or 1) - 1)
            frame = ordered_frames[min(frame_index, len(ordered_frames) - 1)]
        if not frame:
            continue
        segment.reference_roles_json = production_plan_service._reference_roles(frame, style_lock)
        flag_modified(segment, "reference_roles_json")
        segment.image_prompt = str(frame.get("image_prompt") or segment.image_prompt or "")
        segment.video_prompt = str(frame.get("video_prompt") or segment.video_prompt or "")
        segment.narration = frame.get("narration") or segment.narration
    db.commit()


async def _run_one_sentence_expert_reviews(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    run: VideoProductionRun,
    story_bible: dict[str, Any],
    storyboard: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """业务函数：处理 _run_one_sentence_expert_reviews 对应的业务流程、校验或数据转换。

    入参：db、series、episode、run、story_bible、storyboard 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
    except RuntimeModelConfigError as exc:
        return _missing_agency_trace("style_lock", exc), _missing_agency_trace("storyboard", exc)

    orchestrator = AgencyOrchestrator()
    try:
        style_trace = await asyncio.wait_for(
            orchestrator.run_style_lock_review(
                db,
                series_id=series.id,
                run_id=run.id,
                production_plan_id=run.production_plan_id,
                production_episode_id=run.production_episode_id,
                stage_context={"style_lock": _without_agency_trace(story_bible.get("style_lock", {}))},
                runtime_config=runtime_config,
            ),
            timeout=ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        style_trace = _timeout_trace(
            "style_lock",
            "ONE_SENTENCE_STYLE_REVIEW_TIMEOUT",
            ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    try:
        storyboard_trace = await asyncio.wait_for(
            orchestrator.run_storyboard_review(
                db,
                series_id=series.id,
                episode_id=episode.id,
                run_id=run.id,
                production_plan_id=run.production_plan_id,
                production_episode_id=run.production_episode_id,
                stage_context={
                    "storyboard": _without_agency_trace(storyboard),
                    "style_lock": _without_agency_trace(story_bible.get("style_lock", {})),
                },
                runtime_config=runtime_config,
            ),
            timeout=ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        storyboard_trace = _timeout_trace(
            "storyboard",
            "ONE_SENTENCE_STORYBOARD_REVIEW_TIMEOUT",
            ONE_SENTENCE_AGENCY_REVIEW_TIMEOUT_SECONDS,
        )
    return style_trace, storyboard_trace


def _build_storyboard(
    *,
    series: Series,
    episode: Episode,
    character: Character,
    scene: Scene,
    prompt: str,
    target_duration_seconds: int,
) -> dict[str, Any]:
    """业务函数：处理 _build_storyboard 对应的业务流程、校验或数据转换。

    入参：series、episode、character、scene、prompt、target_duration_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    durations = _segment_durations(target_duration_seconds)
    total_frame_count = len(durations)
    story_prompt = _static_story_prompt(prompt)
    materialized_durations = durations[:MAX_MATERIALIZED_STORYBOARD_FRAMES]
    character_reference_urls = _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS)[:9]
    style_reference_urls = _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS)[:3]
    reference_urls = _dedupe_urls(character_reference_urls + style_reference_urls)
    reference_instructions = _reference_instruction(character_reference_urls, style_reference_urls)
    visual_style = series.story_bible_json.get("style_lock", {}).get("visual_style", {})
    positive_visual_style = _positive_visual_style_prompt(visual_style)
    negative_prompt = _negative_prompt(visual_style)
    frames = []
    elapsed_seconds = 0
    for index, duration in enumerate(materialized_durations):
        shot_number = index + 1
        start_second = elapsed_seconds
        end_second = start_second + duration
        time_range = format_time_range(start_second, end_second)
        beat = _shot_beat(story_prompt, index, total_frame_count, duration)
        shot_type = _shot_type(index, total_frame_count)
        character_desc = _static_story_prompt(character.appearance_desc or character.name)
        outfit_desc = _static_story_prompt(character.outfit_desc or "consistent story outfit")
        scene_desc = _static_story_prompt(scene.location_desc or scene.name)
        image_prompt = (
            f"时间段: {time_range}. {positive_visual_style}. Vertical cinematic still frame. {beat['image']}. "
            f"{beat['camera']}. Character: {character_desc}; "
            f"outfit: {outfit_desc}. "
            f"Lighting and environment: {scene_desc}; {scene.lighting or 'cinematic rain-night lighting'}."
        ).strip()
        video_prompt = (
            f"时间段: {time_range}. {beat['video']}. {shot_type} framing. "
            f"Preserve the approved first frame, protagonist face, outfit, rain lighting, and color palette. "
            "Use restrained motion and physically plausible rain, hands, cloth, and camera movement."
        ).strip()
        frames.append({
            "frame_id": f"shot-{shot_number:03d}",
            "scene_id": scene.id,
            "character_ids": [character.id],
            "reference_urls": reference_urls,
            "character_reference_urls": character_reference_urls,
            "style_reference_urls": style_reference_urls,
            "reference_instructions": reference_instructions,
            "image_prompt": image_prompt,
            "video_prompt": video_prompt,
            "negative_prompt": negative_prompt,
            "narration": beat["narration"],
            "duration": duration,
            "start_second": start_second,
            "end_second": end_second,
            "time_range": time_range,
            "audio_mode": "tts",
            "bgm_direction": "restrained suspense bed with rain ambience and a small rise on the final reveal",
            "continuity_notes": (
                "Maintain the same protagonist appearance, costume, environment lighting, "
                "and emotional tone from previous shots."
            ),
            "action": beat["label"],
            "emotion": beat["emotion"],
            "shot_type": _shot_type(index, total_frame_count),
        })
        elapsed_seconds = end_second
    materialized_duration = sum(materialized_durations)
    remaining_frame_count = max(0, total_frame_count - len(frames))
    remaining_duration = max(0, target_duration_seconds - materialized_duration)
    return {
        "series_id": series.id,
        "episode_id": episode.id,
        "style_lock_version": 1,
        "source": "one_sentence",
        "frames": frames,
        "frame_count": total_frame_count,
        "materialized_frame_count": len(frames),
        "materialized_duration": materialized_duration,
        "total_duration": target_duration_seconds,
        "storyboard_window": {
            "mode": "windowed" if remaining_frame_count else "complete",
            "window_index": 1,
            "max_materialized_frames": MAX_MATERIALIZED_STORYBOARD_FRAMES,
            "start_frame_index": 1,
            "end_frame_index": len(frames),
            "remaining_frame_count": remaining_frame_count,
            "remaining_duration": remaining_duration,
        },
        "edit_packaging": series.story_bible_json.get("style_lock", {}).get("edit_packaging", {}),
    }


def _steps(run_status: str, autostart_images: bool, frame_count: int) -> list[dict[str, Any]]:
    """业务函数：处理 _steps 对应的业务流程、校验或数据转换。

    入参：run_status、autostart_images、frame_count 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if run_status == ONE_SENTENCE_REFERENCE_RUNNING_STATUS:
        return [
            {"key": "prompt", "label": "提示词已接收", "status": "done"},
            {"key": "series", "label": "系列与剧集已创建", "status": "done"},
            {"key": "reference_generation", "label": "参考图生成", "status": "running"},
            {"key": "style_lock", "label": "风格锁定", "status": "waiting"},
            {"key": "storyboard", "label": "分镜生成", "status": "waiting", "frame_count": frame_count},
            {"key": "production_plan", "label": "生产计划关联", "status": "waiting"},
            {"key": "image_generation", "label": "画面生成", "status": "waiting"},
            {"key": "image_review", "label": "画面审查闸门", "status": "waiting"},
            {"key": "video_generation", "label": "视频片段生成", "status": "waiting"},
            {"key": "video_review", "label": "视频审查闸门", "status": "waiting"},
            {"key": "compose", "label": "最终合成", "status": "waiting"},
            {"key": "final_review", "label": "最终审查闸门", "status": "waiting"},
            {"key": "completed", "label": "成片完成", "status": "waiting"},
        ]
    image_status = "running" if autostart_images and run_status == "image_batch_running" else "ready"
    return [
        {"key": "prompt", "label": "提示词已接收", "status": "done"},
        {"key": "series", "label": "系列与剧集已创建", "status": "done"},
        {"key": "style_lock", "label": "风格已锁定", "status": "done"},
        {"key": "storyboard", "label": "分镜已生成", "status": "done", "frame_count": frame_count},
        {"key": "production_plan", "label": "生产计划已关联", "status": "done"},
        {"key": "image_generation", "label": "画面生成", "status": image_status},
        {"key": "image_review", "label": "画面审查闸门", "status": "pending"},
        {"key": "video_generation", "label": "视频片段生成", "status": "waiting"},
        {"key": "video_review", "label": "视频审查闸门", "status": "waiting"},
        {"key": "compose", "label": "最终合成", "status": "waiting"},
        {"key": "final_review", "label": "最终审查闸门", "status": "waiting"},
        {"key": "completed", "label": "成片完成", "status": "waiting"},
    ]


def _invalid_run_type(run_type: str, message: str) -> ProductionRepairableError:
    """业务函数：处理 _invalid_run_type 对应的业务流程、校验或数据转换。

    入参：run_type、message 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return ProductionRepairableError(
        code=ProductionErrorCode.INVALID_RUN_TYPE,
        message=message,
        cause="invalid_run_type",
        repair_action="Use run_type=real_short_e2e for one-sentence real short runs.",
        repair_route="/one-sentence-video",
        affected_ids=[run_type],
    )


def _validate_one_sentence_run_type(run_type: str | None) -> str:
    """业务函数：处理 _validate_one_sentence_run_type 对应的业务流程、校验或数据转换。

    入参：run_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        validated = validate_run_type(run_type or REAL_SHORT_E2E)
    except ValueError as exc:
        raise _invalid_run_type(str(run_type), str(exc)) from exc
    return validated


def _validate_real_short_duration(run_type: str, target_duration_seconds: int) -> None:
    """业务函数：处理 _validate_real_short_duration 对应的业务流程、校验或数据转换。

    入参：run_type、target_duration_seconds 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if run_type != REAL_SHORT_E2E:
        return
    if not REAL_SHORT_MIN_SECONDS <= target_duration_seconds <= REAL_SHORT_MAX_SECONDS:
        raise VideoProductionError(
            f"real_short_e2e target_duration_seconds must be at least {REAL_SHORT_MIN_SECONDS} seconds "
            f"and no more than {REAL_SHORT_MAX_SECONDS} seconds."
        )
    if len(_segment_durations(target_duration_seconds)) > MAX_MATERIALIZED_STORYBOARD_FRAMES:
        raise VideoProductionError(
            "real_short_e2e target_duration_seconds exceeds the current materialized storyboard window "
            f"of {REAL_SHORT_MAX_MATERIALIZED_SECONDS} seconds. Windowed production is not implemented yet."
        )


def _assert_budget_allows_real_short(run_type: str, budget_limit: float | None) -> None:
    """业务函数：处理 _assert_budget_allows_real_short 对应的业务流程、校验或数据转换。

    入参：run_type、budget_limit 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if run_type == REAL_SHORT_E2E and (budget_limit is None or float(budget_limit) <= 0):
        raise ProductionRepairableError(
            code=ProductionErrorCode.BUDGET_EXCEEDED,
            message="real_short_e2e requires a positive budget_limit before production can start.",
            cause="budget_limit_exhausted",
            repair_action="Set budget_limit greater than 0 or use mock_series_scale for provider-free runs.",
            repair_route="/one-sentence-video",
            retryable=True,
        )


async def _generate_required_reference_images(db: Session, character: Character, scene: Scene) -> None:
    """业务函数：处理 _generate_required_reference_images 对应的业务流程、校验或数据转换。

    入参：db、character、scene 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await reference_asset_service.generate_character_reference_images(db, character.id, slot="all")
    await reference_asset_service.generate_scene_reference_images(db, scene.id, slot="all")


async def _generate_required_references(db: Session, character: Character, scene: Scene) -> dict[str, Any]:
    """业务函数：处理 _generate_required_references 对应的业务流程、校验或数据转换。

    入参：db、character、scene 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        await asyncio.wait_for(
            _generate_required_reference_images(db, character, scene),
            timeout=ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        db.refresh(character)
        db.refresh(scene)
        return _timeout_trace(
            "reference_generation",
            "REFERENCE_GENERATION_TIMEOUT",
            ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
    except ReferenceAssetError as exc:
        if exc.code == "REFERENCE_PROVIDER_STILL_RUNNING":
            db.refresh(character)
            db.refresh(scene)
            return _reference_deferred_trace(exc)
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_URL_MISSING,
            message=f"Required one-sentence reference images are missing: {exc.message}",
            cause=exc.code,
            repair_action="Configure a text-to-image model and regenerate character/scene reference images before starting production.",
            repair_route="/ai-config",
            retryable=True,
            affected_ids=[character.id, scene.id],
        ) from exc
    db.refresh(character)
    db.refresh(scene)
    missing = []
    if not _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS):
        missing.append(character.id)
    if not _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS):
        missing.append(scene.id)
    if missing:
        raise ProductionRepairableError(
            code=ProductionErrorCode.ASSET_URL_MISSING,
            message="Required one-sentence reference images were not generated.",
            cause="reference_assets_empty",
            repair_action="Regenerate character and scene reference images, then retry one-sentence production.",
            repair_route="/characters",
            retryable=True,
            affected_ids=missing,
        )
    return {"stage": "reference_generation", "stage_status": "complete"}


async def complete_one_sentence_reference_generation(
    db: Session,
    run_id: str,
    *,
    autostart_images: bool | None = None,
) -> VideoProductionRun:
    """业务函数：处理 complete_one_sentence_reference_generation 对应的业务流程、校验或数据转换。

    入参：db、run_id、autostart_images 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    series = db.query(Series).filter(Series.id == run.series_id).first()
    episode = db.query(Episode).filter(Episode.id == run.episode_id).first()
    if not series or not episode:
        raise VideoProductionError("Run series or episode not found")
    character, scene = _first_linked_character_and_scene(db, series)
    if not character or not scene:
        raise VideoProductionError("Run is missing linked character or scene")
    if _is_past_one_sentence_reference_generation(run):
        return run

    trace = dict((run.model_trace_json or {}).get("one_sentence") or {})
    should_autostart = bool(
        autostart_images
        if autostart_images is not None
        else trace.get("autostart_images_after_references")
    )
    _set_run_reference_generation_state(
        db,
        run,
        status=ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
        trace={"stage": "reference_generation", "stage_status": "running"},
        autostart_images=should_autostart,
    )
    try:
        await _generate_required_reference_images(db, character, scene)
        db.refresh(character)
        db.refresh(scene)
        if not _reference_urls_from_fields(character, CHARACTER_REFERENCE_FIELDS) or not _reference_urls_from_fields(scene, SCENE_REFERENCE_FIELDS):
            raise VideoProductionError("Reference generation completed without usable character and scene URLs")

        story_bible = _build_style_lock(series, character, scene, series.logline or series.title)
        story_bible["style_lock"]["reference_generation_trace"] = {
            "stage": "reference_generation",
            "stage_status": "complete",
        }
        series.story_bible_json = story_bible
        storyboard = _build_storyboard(
            series=series,
            episode=episode,
            character=character,
            scene=scene,
            prompt=series.logline or series.title,
            target_duration_seconds=int(series.target_duration or episode.duration_seconds or DEFAULT_TARGET_SECONDS),
        )
        episode.storyboard_json = storyboard
        run.storyboard_json = storyboard
        flag_modified(series, "story_bible_json")
        flag_modified(episode, "storyboard_json")
        flag_modified(run, "storyboard_json")
        db.commit()
        db.refresh(series)
        db.refresh(episode)
        db.refresh(run)

        _refresh_segment_references_from_storyboard(db, run, storyboard, story_bible["style_lock"])
        style_trace, storyboard_trace = await _run_one_sentence_expert_reviews(
            db,
            series=series,
            episode=episode,
            run=run,
            story_bible=story_bible,
            storyboard=storyboard,
        )
        story_bible["style_lock"]["agency_trace"] = style_trace
        storyboard["agency_trace"] = storyboard_trace
        series.story_bible_json = {**story_bible, "style_lock": dict(story_bible["style_lock"])}
        episode.storyboard_json = dict(storyboard)
        run.storyboard_json = dict(storyboard)
        flag_modified(series, "story_bible_json")
        flag_modified(episode, "storyboard_json")
        flag_modified(run, "storyboard_json")
        db.commit()
        _raise_blocked_agency_gate(db, run, style_trace, storyboard_trace)

        _record_one_sentence_text_artifacts(
            db,
            series=series,
            episode=episode,
            run=run,
            prompt=series.logline or series.title,
            story_bible=story_bible,
            storyboard=storyboard,
        )

        if should_autostart:
            run = _mark_storyboard_ready_for_image_start(db, run)
            run = await production_run_service.start_image_stage(db, run.id)
        else:
            run = _mark_storyboard_ready_for_image_start(db, run)
        return run
    except ReferenceAssetError as exc:
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
        if run and exc.code == "REFERENCE_PROVIDER_STILL_RUNNING":
            _set_run_reference_generation_state(
                db,
                run,
                status=ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
                trace=_reference_deferred_trace(exc),
                autostart_images=should_autostart,
            )
            db.refresh(run)
            return run
        if run:
            if _is_past_one_sentence_reference_generation(run):
                return run
            error_trace = _reference_deferred_trace(exc)
            error_trace["stage_status"] = "failed"
            model_trace = dict(run.model_trace_json or {})
            one_sentence = dict(model_trace.get("one_sentence") or {})
            one_sentence["reference_generation"] = error_trace
            model_trace["one_sentence"] = one_sentence
            run.model_trace_json = model_trace
            run.status = ONE_SENTENCE_REFERENCE_BLOCKED_STATUS
            run.current_stage = "reference_generation"
            run.error_message = exc.message
            run.updated_at = bj_now()
            db.commit()
        raise
    except Exception as exc:
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
        if run:
            if _is_past_one_sentence_reference_generation(run):
                return run
            error_trace = {
                "stage": "reference_generation",
                "stage_status": "failed",
                "error_code": exc.__class__.__name__,
                "error_message": str(exc),
            }
            model_trace = dict(run.model_trace_json or {})
            one_sentence = dict(model_trace.get("one_sentence") or {})
            one_sentence["reference_generation"] = error_trace
            model_trace["one_sentence"] = one_sentence
            run.model_trace_json = model_trace
            run.status = ONE_SENTENCE_REFERENCE_BLOCKED_STATUS
            run.current_stage = "reference_generation"
            run.error_message = str(exc)
            run.updated_at = bj_now()
            db.commit()
        raise


async def create_one_sentence_video(
    db: Session,
    *,
    prompt: str,
    title: str | None = None,
    genre: str = "drama",
    target_duration_seconds: int = DEFAULT_TARGET_SECONDS,
    budget_limit: float | None = None,
    autostart_images: bool = True,
    run_type: str | None = REAL_SHORT_E2E,
    auto_repair_policy: dict | None = None,
) -> dict[str, Any]:
    """业务函数：处理 create_one_sentence_video 对应的业务流程、校验或数据转换。

    入参：db、prompt、title、genre、target_duration_seconds、budget_limit、autostart_images、run_type、auto_repair_policy 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    run_type = _validate_one_sentence_run_type(run_type)
    clean_prompt = _clean_prompt(prompt)
    title_value = _title_from_prompt(clean_prompt, title)
    target_duration_seconds = max(5, int(target_duration_seconds or DEFAULT_TARGET_SECONDS))
    _assert_budget_allows_real_short(run_type, budget_limit)
    if run_type == MOCK_SERIES_SCALE:
        from app.domains.video_production.mock_scale_scheduler_service import create_mock_scale_run

        result = create_mock_scale_run(
            db,
            prompt=clean_prompt,
            title=title_value,
            target_duration_seconds=target_duration_seconds,
            budget_limit=budget_limit,
        )
        return {
            "series": result["series"],
            "episode": result["episode"],
            "run": result["run"],
            "steps": [
                {"key": "prompt", "label": "提示词已接收", "status": "done"},
                {"key": "production_plan", "label": "模拟生产计划已关联", "status": "done"},
                {"key": "mock_scheduler", "label": "模拟调度器", "status": "pending"},
                {"key": "completed", "label": "模拟运行完成", "status": "waiting"},
            ],
            "agency_trace_status": "complete",
            "agency_trace": {
                "mock_scheduler": {
                    "stage": "mock_scheduler",
                    "stage_status": "complete",
                    "provider_free": True,
                    "provider_calls": 0,
                }
            },
        }
    _validate_real_short_duration(run_type, target_duration_seconds)

    series = Series(
        title=title_value,
        logline=clean_prompt,
        genre=genre or "drama",
        total_episodes=30,
        target_duration=target_duration_seconds,
        mode="fully_automatic",
        pilot_first=True,
        status="rendering",
    )
    db.add(series)
    db.flush()

    character = Character(
        name="Main Character",
        role_type="protagonist",
        gender="unknown",
        age_range="adult",
        personality="Driven by the central conflict in the prompt.",
        appearance_desc=(
            "Adult protagonist with a clear recognizable face, stable hairstyle, natural proportions, "
            f"focused expression, and visual details inspired by the story prompt: {clean_prompt}"
        ),
        outfit_desc=(
            "Consistent fitted dark outer coat, neutral inner layer, practical trousers, and one subtle "
            "accent color carried across every shot."
        ),
    )
    scene = Scene(
        name="Primary Scene",
        scene_type="mixed",
        location_desc=_scene_location_from_prompt(clean_prompt),
        lighting="cinematic",
        mood="dramatic",
    )
    db.add(character)
    db.add(scene)
    db.flush()
    series.characters.append(character)
    series.scenes.append(scene)
    reference_trace = await _generate_required_references(db, character, scene)
    story_bible = _build_style_lock(series, character, scene, clean_prompt)
    story_bible["style_lock"]["reference_generation_trace"] = reference_trace
    series.story_bible_json = story_bible

    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Episode 1",
        status="storyboard_ready",
    )
    db.add(episode)
    db.flush()
    ensure_episode_placeholders(db, series.id, commit=False)
    storyboard = _build_storyboard(
        series=series,
        episode=episode,
        character=character,
        scene=scene,
        prompt=clean_prompt,
        target_duration_seconds=target_duration_seconds,
    )
    episode.storyboard_json = storyboard

    run = await production_run_service.start_episode_production(
        db,
        series_id=series.id,
        episode_id=episode.id,
        target_duration_seconds=target_duration_seconds,
        budget_limit=budget_limit,
        autostart_images=False,
        run_type=run_type,
        auto_repair_policy=auto_repair_policy,
        prepare_text_artifacts=False,
        episode_asset_scope_override={
            "character_ids": [character.id],
            "scene_ids": [scene.id],
            "source": "one_sentence",
            "characters": [{
                "id": character.id,
                "name": character.name,
                "source": "generated",
                "usage": "一句话成片主角，贯穿本集所有镜头。",
            }],
            "scenes": [{
                "id": scene.id,
                "name": scene.name,
                "source": "generated",
                "usage": "一句话成片主场景，承载本集视觉连续性。",
            }],
        },
    )
    reference_pending = reference_trace.get("error_code") in {"REFERENCE_GENERATION_TIMEOUT", "REFERENCE_PROVIDER_STILL_RUNNING"}
    if reference_pending:
        story_bible["style_lock"]["agency_trace"] = _timeout_trace(
            "style_lock",
            "ONE_SENTENCE_REFERENCE_GENERATION_PENDING",
            ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
        storyboard["agency_trace"] = _timeout_trace(
            "storyboard",
            "ONE_SENTENCE_REFERENCE_GENERATION_PENDING",
            ONE_SENTENCE_REFERENCE_TIMEOUT_SECONDS,
        )
        series.story_bible_json = {**story_bible, "style_lock": dict(story_bible["style_lock"])}
        episode.storyboard_json = dict(storyboard)
        run.storyboard_json = dict(storyboard)
        flag_modified(series, "story_bible_json")
        flag_modified(episode, "storyboard_json")
        flag_modified(run, "storyboard_json")
        db.commit()
        _set_run_reference_generation_state(
            db,
            run,
            status=ONE_SENTENCE_REFERENCE_RUNNING_STATUS,
            trace=reference_trace,
            autostart_images=autostart_images,
        )
        db.refresh(series)
        db.refresh(episode)
        db.refresh(run)
        record_production_event(
            db,
            event_type="one_sentence.reference_generation_deferred",
            run_id=run.id,
            production_plan_id=run.production_plan_id,
            production_episode_id=run.production_episode_id,
            payload={
                "series_id": series.id,
                "episode_id": episode.id,
                "target_duration_seconds": target_duration_seconds,
                "autostart_images": autostart_images,
                "run_type": run_type,
            },
        )
        return {
            "series": series,
            "episode": episode,
            "run": run,
            "steps": _steps(run.status, autostart_images, episode.storyboard_json.get("frame_count", 0)),
            "agency_trace_status": "partial",
            "agency_trace": {
                "style_lock": story_bible["style_lock"]["agency_trace"],
                "storyboard": storyboard["agency_trace"],
            },
            "background_reference_pending": True,
        }

    style_trace, storyboard_trace = await _run_one_sentence_expert_reviews(
        db,
        series=series,
        episode=episode,
        run=run,
        story_bible=story_bible,
        storyboard=storyboard,
    )
    story_bible["style_lock"]["agency_trace"] = style_trace
    storyboard["agency_trace"] = storyboard_trace
    series.story_bible_json = {
        **story_bible,
        "style_lock": dict(story_bible["style_lock"]),
    }
    episode.storyboard_json = dict(storyboard)
    flag_modified(series, "story_bible_json")
    flag_modified(episode, "storyboard_json")
    db.commit()
    db.refresh(series)
    db.refresh(episode)
    _raise_blocked_agency_gate(db, run, style_trace, storyboard_trace)
    _record_one_sentence_text_artifacts(
        db,
        series=series,
        episode=episode,
        run=run,
        prompt=clean_prompt,
        story_bible=story_bible,
        storyboard=storyboard,
    )

    if autostart_images:
        trace = dict(run.model_trace_json or {})
        trace["autopilot"] = {
            "enabled": True,
            "source": "one_sentence",
        }
        run.model_trace_json = trace
        db.commit()
        db.refresh(run)
        run = _mark_storyboard_ready_for_image_start(db, run)
        run = await production_run_service.start_image_stage(db, run.id)
    if not autostart_images and run.status == "draft":
        run = _mark_storyboard_ready_for_image_start(db, run)
    record_production_event(
        db,
        event_type="one_sentence.created",
        run_id=run.id,
        production_plan_id=run.production_plan_id,
        production_episode_id=run.production_episode_id,
        payload={
            "series_id": series.id,
            "episode_id": episode.id,
            "target_duration_seconds": target_duration_seconds,
            "autostart_images": autostart_images,
            "run_type": run_type,
        },
    )
    db.commit()
    db.refresh(run)
    return {
        "series": series,
        "episode": episode,
        "run": run,
        "steps": _steps(run.status, autostart_images, episode.storyboard_json.get("frame_count", 0)),
        "agency_trace_status": _agency_trace_status(style_trace, storyboard_trace),
        "agency_trace": {
            "style_lock": style_trace,
            "storyboard": storyboard_trace,
        },
        "background_reference_pending": False,
    }
