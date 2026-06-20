from app.db.models import (
    AgencyCreativePatch,
    AgencyExpertInvocation,
    AITextArtifact,
    Episode,
    ProductionEpisode,
    ProductionPlan,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    Series,
    VideoProductionRun,
)
from app.domains.agency_operations.agency_creative_patch_service import (
    apply_approved_patches,
    apply_patch,
    create_patches_for_invocation,
    creative_patch_summary,
    unresolved_patch_gate,
)


SOURCE = {
    "source_repo": "jnMetaCode/agency-agents-zh",
    "source_commit": "13b8800",
    "source_path": "specialized/prompt-engineer.md",
    "source_sha256": "a" * 64,
}


def test_agency_creative_patch_row_can_be_persisted(db):
    series = Series(title="创作台", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": []})
    db.add(episode)
    db.flush()

    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="强化钩子",
        reason="前三秒缺少冲突。",
        before_json={"image_prompt": "原"},
        after_json={"image_prompt": "新"},
        status="proposed",
        priority="high",
    )
    db.add(patch)
    db.commit()

    stored = db.query(AgencyCreativePatch).filter_by(id=patch.id).one()
    assert stored.series_id == series.id
    assert stored.status == "proposed"
    assert stored.after_json == {"image_prompt": "新"}


def _series_episode_run(db):
    series = Series(title="导演台", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        script_json={"hook": "原钩子"},
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原图", "video_prompt": "原视频"}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="draft",
        current_stage="draft",
        storyboard_json=episode.storyboard_json,
        edit_manifest_json={"subtitle_style": {"position": "bottom"}},
    )
    db.add(run)
    db.flush()
    invocation = AgencyExpertInvocation(
        idempotency_key="creative-patch-test",
        series_id=series.id,
        episode_id=episode.id,
        run_id=run.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        execution_status="completed",
        result_status="warn",
        input_summary_json={},
        output_summary_json={},
        **SOURCE,
    )
    db.add(invocation)
    db.commit()
    return series, episode, run, invocation


def _production_segment(db, series, episode, run):
    plan = ProductionPlan(series_id=series.id, status="running")
    db.add(plan)
    db.flush()
    production_episode = ProductionEpisode(plan_id=plan.id, episode_id=episode.id)
    db.add(production_episode)
    db.flush()
    production_scene = ProductionScene(episode_plan_id=production_episode.id, scene_id="scene-001")
    db.add(production_scene)
    db.flush()
    shot = ProductionShot(scene_plan_id=production_scene.id, shot_id="shot-001", action="原动作")
    db.add(shot)
    db.flush()
    segment = ProductionSegment(
        shot_plan_id=shot.id,
        segment_id="segment-001",
        image_prompt="原图像提示词",
        video_prompt="原视频提示词",
    )
    db.add(segment)
    run.production_plan_id = plan.id
    run.production_episode_id = production_episode.id
    db.flush()
    return segment


def test_create_patches_for_invocation_validates_target_and_persists(db):
    series, _, run, invocation = _series_episode_run(db)
    output = {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "storyboard",
            "title": "强化钩子",
            "reason": "前三秒不够强。",
            "before": {"image_prompt": "原图"},
            "after": {"image_prompt": "新图", "unexpected": "dropped"},
            "apply_policy": "requires_human_approval",
            "priority": "high",
        }],
    }

    patches = create_patches_for_invocation(db, invocation, output)

    assert len(patches) == 1
    assert patches[0].series_id == series.id
    assert patches[0].run_id == run.id
    assert patches[0].after_json == {"image_prompt": "新图"}
    assert patches[0].status == "proposed"


def test_missing_target_does_not_create_operational_patch(db):
    _, _, _, invocation = _series_episode_run(db)
    output = {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "missing-shot",
            "stage": "storyboard",
            "title": "缺失目标",
            "reason": "目标不存在。",
            "before": {},
            "after": {"image_prompt": "新图"},
            "apply_policy": "requires_human_approval",
        }],
    }

    patches = create_patches_for_invocation(db, invocation, output)

    assert patches == []
    assert db.query(AgencyCreativePatch).count() == 0


def test_production_segment_patch_must_belong_to_invocation_plan_scope(db):
    first_series, first_episode, first_run, invocation = _series_episode_run(db)
    _production_segment(db, first_series, first_episode, first_run)
    second_series = Series(title="另一个导演台", logline="一句话", genre="drama")
    db.add(second_series)
    db.flush()
    second_episode = Episode(
        series_id=second_series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "别的图"}]},
    )
    db.add(second_episode)
    db.flush()
    second_run = VideoProductionRun(
        series_id=second_series.id,
        episode_id=second_episode.id,
        status="draft",
        current_stage="draft",
        storyboard_json=second_episode.storyboard_json,
    )
    db.add(second_run)
    db.flush()
    other_segment = _production_segment(db, second_series, second_episode, second_run)
    invocation.production_plan_id = first_run.production_plan_id
    invocation.production_episode_id = first_run.production_episode_id
    invocation.production_segment_id = None
    db.commit()

    patches = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "image_prompt_patch",
            "target_type": "production_segment",
            "target_id": other_segment.id,
            "stage": "image_stage",
            "title": "跨计划误改",
            "reason": "不应允许改到别的生产计划。",
            "before": {"image_prompt": "原"},
            "after": {"image_prompt": "新"},
            "apply_policy": "requires_human_approval",
        }],
    })

    assert patches == []
    assert db.query(AgencyCreativePatch).count() == 0


def test_production_segment_patch_allows_same_plan_scope_without_segment_scope(db):
    series, episode, run, invocation = _series_episode_run(db)
    segment = _production_segment(db, series, episode, run)
    invocation.production_plan_id = run.production_plan_id
    invocation.production_episode_id = run.production_episode_id
    invocation.production_segment_id = None
    db.commit()

    patches = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "image_prompt_patch",
            "target_type": "production_segment",
            "target_id": segment.id,
            "stage": "image_stage",
            "title": "同计划改稿",
            "reason": "同一生产计划内允许改稿。",
            "before": {"image_prompt": "原"},
            "after": {"image_prompt": "新"},
            "apply_policy": "requires_human_approval",
        }],
    })

    assert len(patches) == 1
    assert patches[0].target_id == segment.id


def test_apply_storyboard_patch_updates_episode_and_run_storyboard(db):
    _, episode, run, invocation = _series_episode_run(db)
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "storyboard",
            "title": "强化钩子",
            "reason": "前三秒不够强。",
            "before": {"image_prompt": "原图"},
            "after": {"image_prompt": "新图", "video_prompt": "新视频"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    result = apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(episode)
    db.refresh(run)
    assert result["status"] == "applied"
    assert episode.storyboard_json["frames"][0]["image_prompt"] == "新图"
    assert run.storyboard_json["frames"][0]["video_prompt"] == "新视频"
    artifacts = {
        artifact.artifact_type: artifact
        for artifact in db.query(AITextArtifact)
        .filter_by(series_id=run.series_id, episode_id=episode.id, target_type="episode", target_id=episode.id)
        .all()
    }
    assert set(artifacts) >= {"storyboard", "image_prompt", "video_prompt"}
    assert artifacts["storyboard"].status == "approved"
    assert artifacts["storyboard"].source_type == "agency_patch"
    assert artifacts["image_prompt"].content_json["prompts"] == ["新图"]
    assert artifacts["video_prompt"].content_json["prompts"] == ["新视频"]


def test_apply_run_only_storyboard_patch_records_run_storyboard_artifact(db):
    _, episode, run, invocation = _series_episode_run(db)
    episode.storyboard_json = {
        "frames": [{"frame_id": "episode-shot", "image_prompt": "集旧图"}],
    }
    run.storyboard_json = {
        "frames": [{"frame_id": "run-shot", "image_prompt": "生产旧图", "video_prompt": "生产旧视频"}],
    }
    db.commit()
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "run-shot",
            "stage": "storyboard",
            "title": "只改生产分镜",
            "reason": "生产 run 内镜头需要修正。",
            "before": {"image_prompt": "生产旧图"},
            "after": {"image_prompt": "生产新图"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(run)
    assert run.storyboard_json["frames"][0]["image_prompt"] == "生产新图"
    run_artifact = db.query(AITextArtifact).filter_by(
        series_id=run.series_id,
        episode_id=episode.id,
        target_type="video_production_run",
        target_id=run.id,
        artifact_type="storyboard",
    ).one()
    assert run_artifact.content_json["frames"][0]["frame_id"] == "run-shot"
    assert run_artifact.content_json["frames"][0]["image_prompt"] == "生产新图"
    assert db.query(AITextArtifact).filter_by(
        series_id=run.series_id,
        episode_id=episode.id,
        target_type="episode",
        target_id=episode.id,
        artifact_type="storyboard",
    ).count() == 0


def test_apply_prompt_patch_updates_production_segment(db):
    series, episode, run, invocation = _series_episode_run(db)
    segment = _production_segment(db, series, episode, run)
    invocation.production_plan_id = run.production_plan_id
    invocation.production_episode_id = run.production_episode_id
    invocation.production_segment_id = segment.id
    db.commit()
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "image_prompt_patch",
            "target_type": "production_segment",
            "target_id": segment.id,
            "stage": "image_stage",
            "title": "优化图像提示词",
            "reason": "人物锚点不够清楚。",
            "before": {"image_prompt": "原图像提示词"},
            "after": {"image_prompt": "新图像提示词"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    result = apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(segment)
    assert result["status"] == "applied"
    assert segment.image_prompt == "新图像提示词"


def test_apply_prompt_patch_updates_linked_run_storyboard_frame(db):
    series, episode, run, invocation = _series_episode_run(db)
    segment = _production_segment(db, series, episode, run)
    run.storyboard_json = {
        "frames": [{
            "frame_id": "shot-001",
            "production_segment_id": segment.id,
            "image_prompt": "原图像提示词",
            "video_prompt": "原视频提示词",
        }],
    }
    invocation.production_plan_id = run.production_plan_id
    invocation.production_episode_id = run.production_episode_id
    invocation.production_segment_id = segment.id
    db.commit()
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "video_prompt_patch",
            "target_type": "production_segment",
            "target_id": segment.id,
            "stage": "video_stage",
            "title": "优化视频提示词",
            "reason": "动作衔接不够清楚。",
            "before": {"video_prompt": "原视频提示词"},
            "after": {"video_prompt": "新视频提示词", "expected_end_state": "主角站稳回头"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    result = apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(segment)
    db.refresh(run)
    assert result["status"] == "applied"
    assert segment.video_prompt == "新视频提示词"
    assert segment.expected_end_state == "主角站稳回头"
    assert run.storyboard_json["frames"][0]["video_prompt"] == "新视频提示词"
    artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        episode_id=episode.id,
        target_type="production_segment",
        target_id=segment.id,
        artifact_type="video_prompt",
    ).one()
    assert artifact.status == "approved"
    assert artifact.source_type == "agency_patch"
    assert artifact.content_json["video_prompt"] == "新视频提示词"
    assert artifact.content_json["expected_end_state"] == "主角站稳回头"


def test_apply_prompt_patch_keeps_continuity_notes_out_of_segment_end_state(db):
    series, episode, run, invocation = _series_episode_run(db)
    segment = _production_segment(db, series, episode, run)
    segment.expected_end_state = "原结束状态"
    run.storyboard_json = {
        "frames": [{
            "frame_id": "shot-001",
            "production_segment_id": segment.id,
            "video_prompt": "原视频提示词",
        }],
    }
    invocation.production_plan_id = run.production_plan_id
    invocation.production_episode_id = run.production_episode_id
    invocation.production_segment_id = segment.id
    db.commit()
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "video_prompt_patch",
            "target_type": "production_segment",
            "target_id": segment.id,
            "stage": "video_stage",
            "title": "补充连续性备注",
            "reason": "需要说明动作接续。",
            "before": {"continuity_notes": ""},
            "after": {"continuity_notes": "镜头接上一段的回头动作"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(segment)
    db.refresh(run)
    assert segment.expected_end_state == "原结束状态"
    assert run.storyboard_json["frames"][0]["continuity_notes"] == "镜头接上一段的回头动作"
    artifact = db.query(AITextArtifact).filter_by(
        series_id=series.id,
        episode_id=episode.id,
        target_type="production_segment",
        target_id=segment.id,
        artifact_type="video_prompt",
    ).one()
    assert artifact.status == "approved"
    assert artifact.source_type == "agency_patch"
    assert artifact.content_json["continuity_notes"] == "镜头接上一段的回头动作"
    assert artifact.content_text == "镜头接上一段的回头动作"


def test_apply_edit_manifest_patch_merges_run_manifest(db):
    _, _, run, invocation = _series_episode_run(db)
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "edit_manifest_patch",
            "target_type": "edit_manifest",
            "target_id": run.id,
            "stage": "compose_preflight",
            "title": "调整字幕节奏",
            "reason": "字幕需要更靠近短视频节奏。",
            "before": {"subtitle_style": {"position": "bottom"}},
            "after": {"subtitle_style": {"position": "center"}, "rhythm_notes": "前三秒加快字幕节奏"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(run)
    assert run.edit_manifest_json["subtitle_style"] == {"position": "center"}
    assert run.edit_manifest_json["rhythm_notes"] == "前三秒加快字幕节奏"


def test_apply_approved_patches_rolls_back_when_later_patch_fails(db):
    _, episode, run, invocation = _series_episode_run(db)
    valid_patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [
            {
                "patch_type": "storyboard_patch",
                "target_type": "storyboard_frame",
                "target_id": "shot-001",
                "stage": "storyboard",
                "title": "有效补丁",
                "reason": "先改有效帧。",
                "before": {"image_prompt": "原图"},
                "after": {"image_prompt": "新图"},
                "apply_policy": "requires_human_approval",
            },
        ],
    })[0]
    invalid_patch = AgencyCreativePatch(
        series_id=run.series_id,
        episode_id=episode.id,
        run_id=run.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="missing-shot",
        title="稍后失败",
        reason="模拟批量中途失败。",
        before_json={"image_prompt": "缺失"},
        after_json={"image_prompt": "不应落库"},
        status="approved",
        priority="high",
    )
    db.add(invalid_patch)
    valid_patch.status = "approved"
    db.commit()

    try:
        apply_approved_patches(db, run_id=run.id, reviewer_user_id="test-user-id")
    except ValueError:
        db.rollback()
    else:
        raise AssertionError("batch apply should fail")

    db.refresh(episode)
    db.refresh(valid_patch)
    db.refresh(invalid_patch)
    assert episode.storyboard_json["frames"][0]["image_prompt"] == "原图"
    assert valid_patch.status == "approved"
    assert invalid_patch.status == "approved"
    assert db.query(AITextArtifact).filter_by(series_id=run.series_id, source_type="agency_patch").count() == 0


def test_unresolved_patch_gate_blocks_pending_run_patch(db):
    _, _, run, invocation = _series_episode_run(db)
    create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "image_stage",
            "title": "提交前改图",
            "reason": "画面提示词需要先确认。",
            "before": {"image_prompt": "原图"},
            "after": {"image_prompt": "新图"},
            "apply_policy": "requires_human_approval",
        }],
    })

    gate = unresolved_patch_gate(db, run, stage="image_stage")

    assert gate["blocked"] is True
    assert gate["blocking_count"] == 1
    assert gate["repair_route"] == f"/series/{run.series_id}/agency-console?tab=workbench"


def test_summary_counts_patch_statuses(db):
    _, _, run, invocation = _series_episode_run(db)
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "image_stage",
            "title": "提交前改图",
            "reason": "画面提示词需要先确认。",
            "before": {},
            "after": {"image_prompt": "新图"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "rejected"
    db.commit()

    summary = creative_patch_summary(db, series_id=run.series_id, run_id=run.id)

    assert summary["total"] == 1
    assert summary["rejected"] == 1
    assert summary["blocking"] == 0
