from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.db_models import (
    AgencyCreativePatch,
    AgencyExpertInvocation,
    AITextArtifact,
    Episode,
    ProductionAuditEvent,
    ProductionEpisode,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoProductionRun,
)
from app.domains.agency_operations.agency_creative_patch_contracts import CreativePatchProposal, normalize_patch_payload


BLOCKING_STATUSES = {"proposed", "edited", "approved"}
PATCH_STATUS_COUNTS = ("proposed", "edited", "approved", "applied", "rejected")


def create_patches_for_invocation(
    db: Session,
    invocation: AgencyExpertInvocation,
    output_summary: dict[str, Any],
) -> list[AgencyCreativePatch]:
    created: list[AgencyCreativePatch] = []
    for raw in output_summary.get("creative_patches") or []:
        if not isinstance(raw, dict):
            _record_invalid_patch(db, invocation, "补丁不是 JSON 对象", raw)
            continue
        try:
            proposal = normalize_patch_payload(CreativePatchProposal.model_validate(raw))
        except Exception as exc:
            _record_invalid_patch(db, invocation, str(exc), raw)
            continue
        if not _target_exists(db, invocation, proposal.target_type.value, proposal.target_id):
            _record_invalid_patch(db, invocation, "补丁目标不存在或不属于当前生产范围", raw)
            continue
        patch = AgencyCreativePatch(
            series_id=invocation.series_id,
            episode_id=invocation.episode_id,
            run_id=invocation.run_id,
            production_plan_id=invocation.production_plan_id,
            production_episode_id=invocation.production_episode_id,
            production_segment_id=(
                proposal.target_id
                if proposal.target_type.value == "production_segment"
                else invocation.production_segment_id
            ),
            source_invocation_id=invocation.id,
            stage=proposal.stage,
            expert_id=invocation.expert_id,
            patch_type=proposal.patch_type.value,
            target_type=proposal.target_type.value,
            target_id=proposal.target_id,
            title=proposal.title,
            reason=proposal.reason,
            before_json=proposal.before,
            after_json=proposal.after,
            status=proposal.status.value,
            priority=proposal.priority.value,
        )
        db.add(patch)
        db.flush()
        created.append(patch)
        _record_patch_event(db, "agency_creative_patch.created", patch, {"source_invocation_id": invocation.id})
    return created


def update_patch_after(
    db: Session,
    patch_id: str,
    after: dict[str, Any],
    *,
    reviewer_user_id: str | None = None,
) -> AgencyCreativePatch:
    patch = _patch_or_raise(db, patch_id)
    if patch.status not in {"proposed", "edited"}:
        raise ValueError("creative patch is not editable")
    proposal = CreativePatchProposal.model_validate({
        "patch_type": patch.patch_type,
        "target_type": patch.target_type,
        "target_id": patch.target_id,
        "stage": patch.stage,
        "title": patch.title,
        "reason": patch.reason,
        "before": patch.before_json or {},
        "after": after,
        "apply_policy": "requires_human_approval",
        "priority": patch.priority,
    })
    normalized = normalize_patch_payload(proposal)
    patch.after_json = normalized.after
    patch.status = "edited"
    patch.reviewer_user_id = reviewer_user_id
    _record_patch_event(db, "agency_creative_patch.edited", patch, {"reviewer_user_id": reviewer_user_id})
    db.commit()
    db.refresh(patch)
    return patch


def approve_patch(db: Session, patch_id: str, *, reviewer_user_id: str | None = None) -> AgencyCreativePatch:
    patch = _patch_or_raise(db, patch_id)
    if patch.status not in {"proposed", "edited", "approved"}:
        raise ValueError("creative patch cannot be approved from current status")
    patch.status = "approved"
    patch.reviewer_user_id = reviewer_user_id
    _record_patch_event(db, "agency_creative_patch.approved", patch, {"reviewer_user_id": reviewer_user_id})
    db.commit()
    db.refresh(patch)
    return patch


def reject_patch(
    db: Session,
    patch_id: str,
    *,
    reason: str,
    reviewer_user_id: str | None = None,
) -> AgencyCreativePatch:
    patch = _patch_or_raise(db, patch_id)
    if patch.status == "applied":
        raise ValueError("applied creative patch cannot be rejected")
    patch.status = "rejected"
    patch.reviewer_user_id = reviewer_user_id
    patch.rejected_at = bj_now()
    _record_patch_event(
        db,
        "agency_creative_patch.rejected",
        patch,
        {"reviewer_user_id": reviewer_user_id, "reason": reason},
    )
    db.commit()
    db.refresh(patch)
    return patch


def apply_patch(
    db: Session,
    patch_id: str,
    *,
    reviewer_user_id: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    patch = _patch_or_raise(db, patch_id)
    if patch.status == "applied":
        return {"id": patch.id, "status": patch.status}
    if patch.status != "approved":
        raise ValueError("creative patch must be approved before apply")
    if patch.patch_type == "storyboard_patch":
        _apply_storyboard_patch(db, patch)
    elif patch.patch_type == "script_patch":
        _apply_script_patch(db, patch)
    elif patch.patch_type in {"image_prompt_patch", "video_prompt_patch"}:
        _apply_segment_prompt_patch(db, patch)
    elif patch.patch_type == "edit_manifest_patch":
        _apply_edit_manifest_patch(db, patch)
    else:
        raise ValueError("unsupported creative patch type")
    patch.status = "applied"
    patch.reviewer_user_id = reviewer_user_id
    patch.applied_at = bj_now()
    _record_patch_event(db, "agency_creative_patch.applied", patch, {"reviewer_user_id": reviewer_user_id})
    _record_applied_patch_text_artifacts(db, patch)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(patch)
    return {"id": patch.id, "status": patch.status}


def apply_approved_patches(
    db: Session,
    *,
    run_id: str | None = None,
    series_id: str | None = None,
    stage: str | None = None,
    reviewer_user_id: str | None = None,
) -> dict[str, Any]:
    query = db.query(AgencyCreativePatch).filter(AgencyCreativePatch.status == "approved")
    if run_id:
        query = query.filter(AgencyCreativePatch.run_id == run_id)
    if series_id:
        query = query.filter(AgencyCreativePatch.series_id == series_id)
    if stage:
        query = query.filter(AgencyCreativePatch.stage == stage)
    order = {
        "script_patch": 0,
        "storyboard_patch": 1,
        "image_prompt_patch": 2,
        "video_prompt_patch": 3,
        "edit_manifest_patch": 4,
    }
    rows = sorted(query.all(), key=lambda item: (order.get(item.patch_type, 99), item.created_at, item.id))
    applied = []
    try:
        for row in rows:
            applied.append(apply_patch(db, row.id, reviewer_user_id=reviewer_user_id, commit=False))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"applied": applied, "count": len(applied)}


def creative_patch_summary(
    db: Session,
    *,
    series_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, int]:
    query = db.query(AgencyCreativePatch)
    if series_id:
        query = query.filter(AgencyCreativePatch.series_id == series_id)
    if run_id:
        query = query.filter(AgencyCreativePatch.run_id == run_id)
    rows = query.all()
    summary = {"total": len(rows), "blocking": 0}
    for status in PATCH_STATUS_COUNTS:
        summary[status] = 0
    for row in rows:
        if row.status in summary:
            summary[row.status] += 1
        if row.status in BLOCKING_STATUSES:
            summary["blocking"] += 1
    return summary


def unresolved_patch_gate(db: Session, run: VideoProductionRun, *, stage: str) -> dict[str, Any]:
    rows = (
        db.query(AgencyCreativePatch)
        .filter(AgencyCreativePatch.run_id == run.id)
        .filter(AgencyCreativePatch.stage == stage)
        .filter(AgencyCreativePatch.status.in_(list(BLOCKING_STATUSES)))
        .all()
    )
    return {
        "blocked": bool(rows),
        "blocking_count": len(rows),
        "patch_ids": [row.id for row in rows],
        "repair_action": "打开短视频导演台处理专家改稿补丁",
        "repair_route": f"/series/{run.series_id}/agency-console?tab=workbench",
    }


def _patch_or_raise(db: Session, patch_id: str) -> AgencyCreativePatch:
    patch = db.query(AgencyCreativePatch).filter(AgencyCreativePatch.id == patch_id).first()
    if not patch:
        raise ValueError("creative patch not found")
    return patch


def _target_exists(db: Session, invocation: AgencyExpertInvocation, target_type: str, target_id: str) -> bool:
    if target_type == "episode_script":
        return bool(invocation.episode_id and target_id in {invocation.episode_id, "episode_script", "script"})
    if target_type == "storyboard_frame":
        episode = db.query(Episode).filter(Episode.id == invocation.episode_id).first() if invocation.episode_id else None
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == invocation.run_id).first() if invocation.run_id else None
        return (
            _frame_index((episode.storyboard_json if episode else None) or {}, target_id) is not None
            or _frame_index((run.storyboard_json if run else None) or {}, target_id) is not None
        )
    if target_type == "production_segment":
        segment = db.query(ProductionSegment).filter(ProductionSegment.id == target_id).first()
        if not segment:
            return False
        if invocation.production_segment_id:
            return segment.id == invocation.production_segment_id
        scope_plan_id = invocation.production_plan_id
        if not scope_plan_id and invocation.run_id:
            run = db.query(VideoProductionRun).filter(VideoProductionRun.id == invocation.run_id).first()
            scope_plan_id = run.production_plan_id if run else None
        if scope_plan_id:
            return _segment_belongs_to_plan(db, segment.id, scope_plan_id)
        if invocation.production_episode_id:
            return _segment_belongs_to_episode_plan(db, segment.id, invocation.production_episode_id)
        return False
    if target_type == "edit_manifest":
        return bool(invocation.run_id and target_id in {invocation.run_id, "edit_manifest", "compose"})
    return False


def _segment_belongs_to_plan(db: Session, segment_id: str, plan_id: str) -> bool:
    return bool(
        db.query(ProductionSegment.id)
        .join(ProductionShot, ProductionShot.id == ProductionSegment.shot_plan_id)
        .join(ProductionScene, ProductionScene.id == ProductionShot.scene_plan_id)
        .join(ProductionEpisode, ProductionEpisode.id == ProductionScene.episode_plan_id)
        .filter(ProductionSegment.id == segment_id, ProductionEpisode.plan_id == plan_id)
        .first()
    )


def _segment_belongs_to_episode_plan(db: Session, segment_id: str, episode_plan_id: str) -> bool:
    return bool(
        db.query(ProductionSegment.id)
        .join(ProductionShot, ProductionShot.id == ProductionSegment.shot_plan_id)
        .join(ProductionScene, ProductionScene.id == ProductionShot.scene_plan_id)
        .filter(ProductionSegment.id == segment_id, ProductionScene.episode_plan_id == episode_plan_id)
        .first()
    )


def _frame_index(storyboard: dict, target_id: str) -> int | None:
    frames = storyboard.get("frames") or []
    for index, frame in enumerate(frames):
        if str(frame.get("frame_id") or frame.get("shot_id") or "") == target_id:
            return index
    return None


def _record_invalid_patch(db: Session, invocation: AgencyExpertInvocation, reason: str, raw: Any) -> None:
    db.add(ProductionAuditEvent(
        event_type="agency_creative_patch.invalid",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload_json={
            "invocation_id": invocation.id,
            "reason": reason,
            "raw_patch": raw if isinstance(raw, dict) else str(raw),
        },
    ))


def _record_patch_event(
    db: Session,
    event_type: str,
    patch: AgencyCreativePatch,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(ProductionAuditEvent(
        event_type=event_type,
        run_id=patch.run_id,
        production_plan_id=patch.production_plan_id,
        production_episode_id=patch.production_episode_id,
        production_segment_id=patch.production_segment_id,
        payload_json={"patch_id": patch.id, **(payload or {})},
    ))


def _apply_script_patch(db: Session, patch: AgencyCreativePatch) -> None:
    episode = db.query(Episode).filter(Episode.id == patch.episode_id).first()
    if not episode:
        raise ValueError("episode not found for script patch")
    script = dict(episode.script_json or {})
    script.update(patch.after_json or {})
    episode.script_json = script
    flag_modified(episode, "script_json")


def _apply_storyboard_patch(db: Session, patch: AgencyCreativePatch) -> None:
    episode = db.query(Episode).filter(Episode.id == patch.episode_id).first() if patch.episode_id else None
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == patch.run_id).first() if patch.run_id else None
    applied = False
    if episode and _update_storyboard_frame(episode.storyboard_json or {}, patch.target_id, patch.after_json or {}):
        flag_modified(episode, "storyboard_json")
        applied = True
    if run and _update_storyboard_frame(run.storyboard_json or {}, patch.target_id, patch.after_json or {}):
        flag_modified(run, "storyboard_json")
        applied = True
    if not applied:
        raise ValueError("storyboard frame not found for patch")


def _update_storyboard_frame(storyboard: dict, target_id: str, after: dict[str, Any]) -> bool:
    index = _frame_index(storyboard, target_id)
    if index is None:
        return False
    frames = storyboard.get("frames") or []
    frames[index] = {**frames[index], **after}
    storyboard["frames"] = frames
    return True


def _apply_segment_prompt_patch(db: Session, patch: AgencyCreativePatch) -> None:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == patch.target_id).first()
    if not segment:
        raise ValueError("production segment not found for prompt patch")
    after = patch.after_json or {}
    storyboard_updates: dict[str, Any] = {}
    if "image_prompt" in after:
        value = str(after["image_prompt"])
        segment.image_prompt = value
        storyboard_updates["image_prompt"] = value
    if "video_prompt" in after:
        value = str(after["video_prompt"])
        segment.video_prompt = value
        storyboard_updates["video_prompt"] = value
    if "expected_end_state" in after:
        value = str(after["expected_end_state"])
        segment.expected_end_state = value
        storyboard_updates["expected_end_state"] = value
    if "continuity_notes" in after:
        value = str(after["continuity_notes"])
        storyboard_updates["continuity_notes"] = value
    if "duration" in after:
        value = float(after["duration"])
        segment.duration_seconds = value
        storyboard_updates["duration"] = value
    for key in ("negative_prompt", "reference_instructions"):
        if key in after:
            storyboard_updates[key] = str(after[key])
    _sync_run_storyboard_frame_for_segment(db, patch, segment, storyboard_updates)


def _sync_run_storyboard_frame_for_segment(
    db: Session,
    patch: AgencyCreativePatch,
    segment: ProductionSegment,
    updates: dict[str, Any],
) -> None:
    if not updates or not patch.run_id:
        return
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == patch.run_id).first()
    if not run or not isinstance(run.storyboard_json, dict):
        return
    frames = list(run.storyboard_json.get("frames") or [])
    if not frames:
        return
    shot = db.query(ProductionShot).filter(ProductionShot.id == segment.shot_plan_id).first()
    match_ids = {segment.id, segment.segment_id, patch.target_id}
    if shot:
        match_ids.add(shot.shot_id)
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        if not _frame_matches_segment(frame, match_ids):
            continue
        frames[index] = {**frame, **updates}
        run.storyboard_json = {**run.storyboard_json, "frames": frames}
        flag_modified(run, "storyboard_json")
        return


def _frame_matches_segment(frame: dict[str, Any], match_ids: set[str]) -> bool:
    frame_values = {
        str(frame.get("production_segment_id") or ""),
        str(frame.get("frame_id") or ""),
        str(frame.get("segment_id") or ""),
        str(frame.get("shot_id") or ""),
    }
    return bool(frame_values & {str(value) for value in match_ids if value})


def _apply_edit_manifest_patch(db: Session, patch: AgencyCreativePatch) -> None:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == patch.run_id).first()
    if not run:
        raise ValueError("run not found for edit manifest patch")
    manifest = dict(run.edit_manifest_json or {})
    manifest.update(patch.after_json or {})
    run.edit_manifest_json = manifest
    flag_modified(run, "edit_manifest_json")


def _record_applied_patch_text_artifacts(db: Session, patch: AgencyCreativePatch) -> None:
    if patch.patch_type == "script_patch":
        episode = db.query(Episode).filter(Episode.id == patch.episode_id).first() if patch.episode_id else None
        if episode and isinstance(episode.script_json, dict):
            _create_approved_text_artifact(
                db,
                patch,
                target_type="episode",
                target_id=episode.id,
                artifact_type="episode_script",
                content_json=episode.script_json,
                content_text=json.dumps(episode.script_json, ensure_ascii=False),
            )
    elif patch.patch_type == "storyboard_patch":
        episode = db.query(Episode).filter(Episode.id == patch.episode_id).first() if patch.episode_id else None
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == patch.run_id).first() if patch.run_id else None
        if (
            episode
            and isinstance(episode.storyboard_json, dict)
            and _frame_index(episode.storyboard_json, patch.target_id) is not None
        ):
            _record_storyboard_text_artifacts(db, patch, "episode", episode.id, episode.storyboard_json)
        if (
            run
            and isinstance(run.storyboard_json, dict)
            and _frame_index(run.storyboard_json, patch.target_id) is not None
        ):
            _record_storyboard_text_artifacts(db, patch, "video_production_run", run.id, run.storyboard_json)
    elif patch.patch_type in {"image_prompt_patch", "video_prompt_patch"}:
        segment = db.query(ProductionSegment).filter(ProductionSegment.id == patch.target_id).first()
        if segment:
            _record_segment_prompt_text_artifacts(db, patch, segment)


def _record_storyboard_text_artifacts(
    db: Session,
    patch: AgencyCreativePatch,
    target_type: str,
    target_id: str,
    storyboard: dict[str, Any],
) -> None:
    dialogue_lines = _storyboard_lines(storyboard, "narration")
    image_prompts = _storyboard_lines(storyboard, "image_prompt")
    video_prompts = _storyboard_lines(storyboard, "video_prompt")
    specs = [
        ("storyboard", storyboard, "\n".join(dialogue_lines)),
        ("dialogue", {"lines": dialogue_lines}, "\n".join(dialogue_lines)),
        ("image_prompt", {"prompts": image_prompts}, "\n".join(image_prompts)),
    ]
    if video_prompts:
        specs.append(("video_prompt", {"prompts": video_prompts}, "\n".join(video_prompts)))
    for artifact_type, content_json, content_text in specs:
        _create_approved_text_artifact(
            db,
            patch,
            target_type=target_type,
            target_id=target_id,
            artifact_type=artifact_type,
            content_json=content_json,
            content_text=content_text,
        )


def _record_segment_prompt_text_artifacts(
    db: Session,
    patch: AgencyCreativePatch,
    segment: ProductionSegment,
) -> None:
    after = patch.after_json or {}
    text_fields = ("image_prompt", "video_prompt", "expected_end_state", "continuity_notes", "negative_prompt", "reference_instructions")
    changed_text = {
        key: str(after[key])
        for key in text_fields
        if key in after and after[key] is not None
    }
    created_prompt_artifact = False
    for artifact_type in ("image_prompt", "video_prompt"):
        if artifact_type not in after:
            continue
        content_json = {
            "production_segment_id": segment.id,
            artifact_type: str(after[artifact_type]),
        }
        for key in ("expected_end_state", "continuity_notes", "negative_prompt", "reference_instructions"):
            if key in after:
                content_json[key] = str(after[key])
        _create_approved_text_artifact(
            db,
            patch,
            target_type="production_segment",
            target_id=segment.id,
            artifact_type=artifact_type,
            content_json=content_json,
            content_text=str(after[artifact_type]),
        )
        created_prompt_artifact = True
    if changed_text and not created_prompt_artifact:
        artifact_type = "video_prompt" if patch.patch_type == "video_prompt_patch" else "image_prompt"
        _create_approved_text_artifact(
            db,
            patch,
            target_type="production_segment",
            target_id=segment.id,
            artifact_type=artifact_type,
            content_json={
                "production_segment_id": segment.id,
                **changed_text,
            },
            content_text="\n".join(changed_text.values()),
        )


def _storyboard_lines(storyboard: dict[str, Any], key: str) -> list[str]:
    frames = storyboard.get("frames") or []
    if not isinstance(frames, list):
        return []
    return [str(frame[key]) for frame in frames if isinstance(frame, dict) and frame.get(key)]


def _create_approved_text_artifact(
    db: Session,
    patch: AgencyCreativePatch,
    *,
    target_type: str,
    target_id: str,
    artifact_type: str,
    content_json: dict[str, Any],
    content_text: str,
) -> AITextArtifact:
    now = bj_now()
    version = _next_text_artifact_version(db, target_type, target_id, artifact_type)
    active = (
        db.query(AITextArtifact)
        .filter(
            AITextArtifact.target_type == target_type,
            AITextArtifact.target_id == target_id,
            AITextArtifact.artifact_type == artifact_type,
            AITextArtifact.status.in_(("draft", "review_pending", "approved")),
        )
        .all()
    )
    for artifact in active:
        artifact.status = "superseded"
        artifact.superseded_at = now
    artifact = AITextArtifact(
        series_id=patch.series_id,
        episode_id=patch.episode_id,
        run_id=patch.run_id,
        production_plan_id=patch.production_plan_id,
        target_type=target_type,
        target_id=target_id,
        artifact_type=artifact_type,
        version=version,
        status="approved",
        source_type="agency_patch",
        input_json={
            "source": "agency_creative_patch",
            "patch_id": patch.id,
            "patch_type": patch.patch_type,
            "stage": patch.stage,
            "title": patch.title,
            "reason": patch.reason,
            "before": patch.before_json or {},
            "after": patch.after_json or {},
        },
        content_json=content_json,
        content_text=content_text,
        model_trace_json={
            "source": "agency_creative_patch",
            "source_invocation_id": patch.source_invocation_id,
            "expert_id": patch.expert_id,
            "artifact_type": artifact_type,
        },
        review_trace_json={
            "reviewer_user_id": patch.reviewer_user_id,
            "status": patch.status,
            "applied_at": patch.applied_at.isoformat() if patch.applied_at else None,
        },
        created_by=patch.reviewer_user_id or "agency_patch",
        approved_at=now,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _next_text_artifact_version(db: Session, target_type: str, target_id: str, artifact_type: str) -> int:
    latest = (
        db.query(AITextArtifact.version)
        .filter(
            AITextArtifact.target_type == target_type,
            AITextArtifact.target_id == target_id,
            AITextArtifact.artifact_type == artifact_type,
        )
        .order_by(AITextArtifact.version.desc())
        .first()
    )
    return int(latest[0]) + 1 if latest else 1
