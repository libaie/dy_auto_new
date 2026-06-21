"""剧本流水线业务域模块。

剧本流水线业务域，负责剧本、分镜节奏和文本生产阶段衔接。本文件负责 script_pipeline_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.script_pipeline import (
    EpisodeScript as DbEpisodeScript,
    PipelineRun,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
)
from app.db.models import (
    Episode,
)
from app.models.script import (
    DramaticBeatList,
    DramaticBeatType,
    EpisodeScript,
    PipelineStage,
    SceneOutlineList,
    VisualShotList,
)
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools
from app.domains.model_configuration.runtime_model_config import resolve_runtime_model_config
from app.domains.script_pipeline.storyboard_timing import (
    annotate_storyboard_with_timing,
    build_detailed_image_prompt,
    build_detailed_video_prompt,
    timed_storyboard_lines,
)


TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "prompts" / "templates"
SCRIPT_STATE_KEY = "script_generation"
MAX_STAGE_RETRIES = 2
STAGE_ORDER = [
    PipelineStage.DRAMATIC_BEATS,
    PipelineStage.SCENE_OUTLINES,
    PipelineStage.VISUAL_SHOTS,
]
MOCK_RUNTIME_CONFIG = {"provider": "mock", "model": "mock", "api_key": "test", "config": {}}


@dataclass(frozen=True)
class PromptPayload:
    system_prompt: str
    user_prompt: str


BEAT_CONSTRAINTS = {
    DramaticBeatType.HOOK: [
        "前3秒必须出现视觉冲突（如摔杯子、下跪、耳光或身份反差）",
        "台词字数不得超过15字",
        "语气必须极端",
    ],
    DramaticBeatType.CLIMAX: [
        "必须完成身份反转",
        "反派角色产生震惊、恐惧的视觉表现",
        "主角机位采用低角度仰拍以增强压迫感",
    ],
}

TAG_CONSTRAINTS = {
    "歪嘴战神": ["被压制的主角身份", "旁人公开轻蔑", "精准亮明权力或武力反差"],
    "都市逆袭": ["现代层级压力", "公开 stakes", "金钱或身份反差", "当场反转"],
    "主母黑化": ["家庭权力秩序", "背叛", "情绪冷转", "克制反击"],
}

TEMPLATE_NAMES = {
    PipelineStage.DRAMATIC_BEATS: "script_stage1_dramatic_beats.md",
    PipelineStage.SCENE_OUTLINES: "script_stage2_scene_outlines.md",
    PipelineStage.VISUAL_SHOTS: "script_stage3_visual_shots.md",
}


class DynamicPromptBuilder:
    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self.template_dir = template_dir

    def build(
        self,
        *,
        stage: PipelineStage,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        beat_types: list[DramaticBeatType] | None = None,
        previous_outputs: dict[str, Any] | None = None,
    ) -> PromptPayload:
        template = self._read_template(stage)
        system_prompt, user_prompt = self._split_template(template)
        rendered_user = self._render(
            user_prompt,
            source_prompt=source_prompt,
            tags="、".join(tags) if tags else "无",
            target_duration_seconds=str(target_duration_seconds),
            previous_outputs=json.dumps(previous_outputs or {}, ensure_ascii=False, sort_keys=True),
            constraints="\n".join(self._constraints(tags, beat_types or [])),
        )
        return PromptPayload(system_prompt=system_prompt.strip(), user_prompt=rendered_user.strip())

    def _read_template(self, stage: PipelineStage) -> str:
        return (self.template_dir / TEMPLATE_NAMES[stage]).read_text(encoding="utf-8")

    def _split_template(self, template: str) -> tuple[str, str]:
        system_marker = "## SYSTEM"
        user_marker = "## USER"
        if system_marker not in template or user_marker not in template:
            raise ValueError("script prompt template must contain ## SYSTEM and ## USER sections")
        system_part, user_part = template.split(user_marker, 1)
        return system_part.replace(system_marker, "", 1), user_part

    def _render(self, template: str, **values: str) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        return rendered

    def _constraints(self, tags: list[str], beat_types: list[DramaticBeatType]) -> list[str]:
        constraints: list[str] = []
        for beat_type in beat_types:
            constraints.extend(BEAT_CONSTRAINTS.get(beat_type, []))
        for tag in tags:
            constraints.extend(TAG_CONSTRAINTS.get(tag, [f"保留标签语境: {tag}"]))
        return constraints


class ScriptGenerationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        pipeline_run_id: str,
        attempts: int,
        error_code: str,
        human_intervention_required: bool = True,
    ):
        super().__init__(message)
        self.stage = stage
        self.pipeline_run_id = pipeline_run_id
        self.attempts = attempts
        self.error_code = error_code
        self.human_intervention_required = human_intervention_required


def _load_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("script model response must be a JSON object or JSON string")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("script model response must be a JSON object")
    return parsed


async def default_script_model_client(
    *,
    system_prompt: str,
    user_prompt: str,
    runtime_config: dict[str, Any],
) -> Any:
    return await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=runtime_config,
        tools=build_ai_video_tools(None, allowed_tools=["validate_json"]),
    )


async def default_gate_runner(
    db: Session,
    *,
    gate_name: str,
    series_id: str,
    episode_id: str,
    pipeline_run_id: str,
    stage_context: dict[str, Any],
    runtime_config: dict[str, Any],
) -> dict[str, Any]:
    orchestrator = AgencyOrchestrator()
    if gate_name in {PipelineStage.DRAMATIC_BEATS.value, PipelineStage.SCENE_OUTLINES.value}:
        return await orchestrator.run_story_planning_review(
            db,
            series_id=series_id,
            episode_id=episode_id,
            pipeline_run_id=pipeline_run_id,
            stage_context=stage_context,
            runtime_config=runtime_config,
        )
    if gate_name == PipelineStage.VISUAL_SHOTS.value:
        return await orchestrator.run_storyboard_review(
            db,
            series_id=series_id,
            episode_id=episode_id,
            pipeline_run_id=pipeline_run_id,
            stage_context=stage_context,
            runtime_config=runtime_config,
        )
    raise ValueError(f"unknown script gate: {gate_name}")


def _input_hash(
    *,
    stage: PipelineStage,
    source_prompt: str,
    tags: list[str],
    target_duration_seconds: int,
    previous_outputs: dict[str, Any],
) -> str:
    payload = {
        "stage": stage.value,
        "source_prompt": source_prompt,
        "tags": tags,
        "target_duration_seconds": target_duration_seconds,
        "previous_outputs": previous_outputs,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _script_state(run: PipelineRun) -> dict[str, Any]:
    layers = dict(run.layers_json or {})
    state = dict(layers.get(SCRIPT_STATE_KEY) or {})
    state.setdefault("current_stage", PipelineStage.DRAMATIC_BEATS.value)
    state.setdefault("human_intervention_required", False)
    state.setdefault("stages", {})
    layers[SCRIPT_STATE_KEY] = state
    run.layers_json = layers
    return state


def _persist_run_state(db: Session, run: PipelineRun) -> None:
    flag_modified(run, "layers_json")
    db.add(run)
    db.commit()
    db.refresh(run)


class ScriptGenerationPipeline:
    def __init__(
        self,
        *,
        model_client=default_script_model_client,
        gate_runner=default_gate_runner,
        prompt_builder: DynamicPromptBuilder | None = None,
    ):
        self.model_client = model_client
        self.gate_runner = gate_runner
        self.prompt_builder = prompt_builder or DynamicPromptBuilder()
        self.uses_default_model_client = model_client is default_script_model_client
        self.uses_default_gate_runner = gate_runner is default_gate_runner

    async def generate_stage(
        self,
        *,
        stage: PipelineStage,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        previous_outputs: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> DramaticBeatList | SceneOutlineList | VisualShotList:
        beat_types = self._beat_types(stage, previous_outputs)
        payload = self.prompt_builder.build(
            stage=stage,
            source_prompt=source_prompt,
            tags=tags,
            target_duration_seconds=target_duration_seconds,
            beat_types=beat_types,
            previous_outputs=previous_outputs,
        )
        raw = await self.model_client(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
            runtime_config=runtime_config,
        )
        data = _load_json_object(raw)
        return self._validate_stage_output(stage, data)

    def _validate_stage_output(
        self,
        stage: PipelineStage,
        data: dict[str, Any],
    ) -> DramaticBeatList | SceneOutlineList | VisualShotList:
        if stage == PipelineStage.DRAMATIC_BEATS:
            return DramaticBeatList.model_validate(data)
        if stage == PipelineStage.SCENE_OUTLINES:
            return SceneOutlineList.model_validate(data)
        return VisualShotList.model_validate(data)

    def _beat_types(self, stage: PipelineStage, previous_outputs: dict[str, Any]) -> list[DramaticBeatType]:
        if stage == PipelineStage.DRAMATIC_BEATS:
            return [DramaticBeatType.HOOK, DramaticBeatType.CLIMAX]
        beats = (previous_outputs.get(PipelineStage.DRAMATIC_BEATS.value) or {}).get("beats") or []
        result = []
        for beat in beats:
            try:
                result.append(DramaticBeatType(beat["beat_type"]))
            except (KeyError, ValueError, TypeError):
                continue
        return result


class PipelineManager:
    def __init__(self, *, pipeline: ScriptGenerationPipeline | None = None):
        self.pipeline = pipeline or ScriptGenerationPipeline()

    def get_or_create_run(self, db: Session, *, series_id: str, episode_id: str) -> PipelineRun:
        run = (
            db.query(PipelineRun)
            .filter(
                PipelineRun.series_id == series_id,
                PipelineRun.episode_id == episode_id,
                PipelineRun.mode == "script_generation",
            )
            .order_by(PipelineRun.created_at.desc())
            .first()
        )
        if run:
            return run
        run = PipelineRun(
            series_id=series_id,
            episode_id=episode_id,
            mode="script_generation",
            status="running",
            current_layer=1,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    async def start_or_resume(
        self,
        db: Session,
        *,
        series_id: str,
        episode_id: str,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        explicit_model_id: str | None = None,
        episode_asset_scope: dict[str, Any] | None = None,
    ) -> EpisodeScript:
        run = self.get_or_create_run(db, series_id=series_id, episode_id=episode_id)
        runtime_config = self._runtime_config(db, "script_generation", explicit_model_id, self.pipeline.uses_default_model_client)
        gate_runtime_config = self._runtime_config(db, "llm_agency_expert_review", None, self.pipeline.uses_default_gate_runner)
        previous: dict[str, Any] = {}

        beats = await self._run_stage(
            db,
            run,
            PipelineStage.DRAMATIC_BEATS,
            source_prompt,
            tags,
            target_duration_seconds,
            previous,
            runtime_config,
        )
        previous[PipelineStage.DRAMATIC_BEATS.value] = beats.model_dump(mode="json")
        await self._run_gate(db, run, PipelineStage.DRAMATIC_BEATS, series_id, episode_id, previous, gate_runtime_config)

        scenes = await self._run_stage(
            db,
            run,
            PipelineStage.SCENE_OUTLINES,
            source_prompt,
            tags,
            target_duration_seconds,
            previous,
            runtime_config,
        )
        previous[PipelineStage.SCENE_OUTLINES.value] = scenes.model_dump(mode="json")
        await self._run_gate(db, run, PipelineStage.SCENE_OUTLINES, series_id, episode_id, previous, gate_runtime_config)

        shots = await self._run_stage(
            db,
            run,
            PipelineStage.VISUAL_SHOTS,
            source_prompt,
            tags,
            target_duration_seconds,
            previous,
            runtime_config,
        )
        previous[PipelineStage.VISUAL_SHOTS.value] = shots.model_dump(mode="json")
        await self._run_gate(db, run, PipelineStage.VISUAL_SHOTS, series_id, episode_id, previous, gate_runtime_config)

        result = EpisodeScript(
            series_id=series_id,
            episode_id=episode_id,
            source_prompt=source_prompt,
            tags=tags,
            target_duration_seconds=target_duration_seconds,
            episode_asset_scope=episode_asset_scope or {},
            dramatic_beats=beats,
            scene_outlines=scenes,
            visual_shots=shots,
            agency_trace=self._agency_trace(run),
        )
        self._write_snapshots(db, run, result)
        return result

    def _runtime_config(
        self,
        db: Session,
        scene_key: str,
        explicit_model_id: str | None,
        needs_real_config: bool,
    ) -> dict[str, Any]:
        if not needs_real_config:
            return dict(MOCK_RUNTIME_CONFIG)
        return resolve_runtime_model_config(db, scene_key, explicit_model_id)

    async def _run_stage(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        previous_outputs: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> DramaticBeatList | SceneOutlineList | VisualShotList:
        state = _script_state(run)
        stages = state["stages"]
        input_hash = _input_hash(
            stage=stage,
            source_prompt=source_prompt,
            tags=tags,
            target_duration_seconds=target_duration_seconds,
            previous_outputs=previous_outputs,
        )
        record = stages.get(stage.value)
        if record and record.get("status") == "completed" and record.get("input_hash") == input_hash:
            return self.pipeline._validate_stage_output(stage, record["output"])
        if record and record.get("input_hash") != input_hash:
            self._invalidate_from_stage(state, stage)
            record = None

        record = record or {
            "status": "pending",
            "attempts": 0,
            "input_hash": input_hash,
            "output": None,
            "gate_trace": None,
            "error": None,
        }
        stages[stage.value] = record
        state["current_stage"] = stage.value
        run.status = "running"

        allowed_attempts = MAX_STAGE_RETRIES + 1
        last_error: Exception | None = None
        while int(record.get("attempts") or 0) < allowed_attempts:
            record["attempts"] = int(record.get("attempts") or 0) + 1
            record["status"] = "running"
            record["error"] = None
            _persist_run_state(db, run)
            state = _script_state(run)
            record = state["stages"][stage.value]
            try:
                output = await self.pipeline.generate_stage(
                    stage=stage,
                    source_prompt=source_prompt,
                    tags=tags,
                    target_duration_seconds=target_duration_seconds,
                    previous_outputs=previous_outputs,
                    runtime_config=runtime_config,
                )
            except Exception as exc:
                last_error = exc
                record["status"] = "failed"
                record["error"] = {"error_code": exc.__class__.__name__, "message": str(exc)}
                _persist_run_state(db, run)
                state = _script_state(run)
                record = state["stages"][stage.value]
                continue

            record["status"] = "completed"
            record["output"] = output.model_dump(mode="json")
            record["error"] = None
            _persist_run_state(db, run)
            return output

        state["human_intervention_required"] = True
        record["status"] = "failed"
        run.status = "failed"
        _persist_run_state(db, run)
        raise ScriptGenerationError(
            str(last_error or "script generation failed"),
            stage=stage.value,
            pipeline_run_id=run.id,
            attempts=int(record.get("attempts") or 0),
            error_code="SCRIPT_STAGE_RETRIES_EXHAUSTED",
        )

    async def _run_gate(
        self,
        db: Session,
        run: PipelineRun,
        stage: PipelineStage,
        series_id: str,
        episode_id: str,
        stage_context: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        state = _script_state(run)
        record = state["stages"].setdefault(stage.value, {})
        gate_trace = record.get("gate_trace") or {}
        if gate_trace.get("stage_status") == "completed":
            return gate_trace
        trace = await self.pipeline.gate_runner(
            db,
            gate_name=stage.value,
            series_id=series_id,
            episode_id=episode_id,
            pipeline_run_id=run.id,
            stage_context=stage_context,
            runtime_config=runtime_config,
        )
        state = _script_state(run)
        record = state["stages"].setdefault(stage.value, {})
        record["gate_trace"] = trace
        status = trace.get("stage_status")
        if status in {"blocked", "failed"}:
            state["human_intervention_required"] = True
            record["error"] = {
                "error_code": "SCRIPT_EXPERT_GATE_BLOCKED",
                "message": f"expert gate blocked: {stage.value}",
            }
        _persist_run_state(db, run)
        return trace

    def _invalidate_from_stage(self, state: dict[str, Any], stage: PipelineStage) -> None:
        start = STAGE_ORDER.index(stage)
        for invalid_stage in STAGE_ORDER[start:]:
            state["stages"].pop(invalid_stage.value, None)

    def _agency_trace(self, run: PipelineRun) -> dict[str, Any]:
        state = _script_state(run)
        traces = {}
        for stage_name, record in state.get("stages", {}).items():
            if record.get("gate_trace"):
                traces[stage_name] = record["gate_trace"]
        return traces

    def _write_snapshots(self, db: Session, run: PipelineRun, script: EpisodeScript) -> None:
        db_script = (
            db.query(DbEpisodeScript)
            .filter(
                DbEpisodeScript.pipeline_run_id == run.id,
                DbEpisodeScript.episode_id == script.episode_id,
            )
            .first()
        )
        if not db_script:
            db_script = DbEpisodeScript(
                series_id=script.series_id,
                episode_id=script.episode_id,
                pipeline_run_id=run.id,
                source_prompt=script.source_prompt,
                tags_json=list(script.tags),
                target_duration_seconds=script.target_duration_seconds,
                status="completed",
                agency_trace_json=script.agency_trace,
            )
            db.add(db_script)
            db.flush()
        else:
            db_script.source_prompt = script.source_prompt
            db_script.tags_json = list(script.tags)
            db_script.target_duration_seconds = script.target_duration_seconds
            db_script.status = "completed"
            db_script.agency_trace_json = script.agency_trace
            db.query(ScriptVisualShot).filter(ScriptVisualShot.script_id == db_script.id).delete()
            db.query(ScriptSceneOutline).filter(ScriptSceneOutline.script_id == db_script.id).delete()
            db.query(ScriptDramaticBeat).filter(ScriptDramaticBeat.script_id == db_script.id).delete()
            db.flush()

        for index, beat in enumerate(script.dramatic_beats.beats, start=1):
            db.add(ScriptDramaticBeat(
                script_id=db_script.id,
                order_index=index,
                beat_type=beat.beat_type.value,
                emotional_value=beat.emotional_value,
                plot_summary=beat.plot_summary,
            ))
        for scene in script.scene_outlines.scenes:
            db.add(ScriptSceneOutline(
                script_id=db_script.id,
                scene_number=scene.scene_number,
                dramatic_beat_type=scene.dramatic_beat_type.value,
                location=scene.location,
                characters_json=list(scene.characters),
                conflict=scene.conflict,
                emotional_turn=scene.emotional_turn,
                visual_mandate=scene.visual_mandate,
            ))
        for shot in script.visual_shots.shots:
            db.add(ScriptVisualShot(
                script_id=db_script.id,
                shot_number=shot.shot_number,
                scene_number=shot.scene_number,
                beat_type=shot.beat_type.value,
                narration=shot.narration,
                visual_prompt=shot.visual_prompt,
                video_prompt=shot.video_prompt,
                duration=shot.duration,
            ))

        episode = db.query(Episode).filter(Episode.id == script.episode_id).one()
        episode.script_json = self._script_snapshot(script, db_script.id)
        episode.storyboard_json = self._storyboard_snapshot(script)
        flag_modified(episode, "script_json")
        flag_modified(episode, "storyboard_json")
        self._write_ai_text_artifacts(db, run, episode, script)
        state = _script_state(run)
        state["current_stage"] = PipelineStage.VISUAL_SHOTS.value
        run.status = "completed"
        _persist_run_state(db, run)

    def _write_ai_text_artifacts(
        self,
        db: Session,
        run: PipelineRun,
        episode: Episode,
        script: EpisodeScript,
    ) -> None:
        service = AITextArtifactService(db)
        script_json = episode.script_json if isinstance(episode.script_json, dict) else {}
        storyboard_json = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
        frames = storyboard_json.get("frames") if isinstance(storyboard_json.get("frames"), list) else []
        dialogue_lines = [str(frame.get("narration")) for frame in frames if isinstance(frame, dict) and frame.get("narration")]
        image_prompts = [str(frame.get("image_prompt")) for frame in frames if isinstance(frame, dict) and frame.get("image_prompt")]
        video_prompts = [str(frame.get("video_prompt")) for frame in frames if isinstance(frame, dict) and frame.get("video_prompt")]
        storyboard_lines = timed_storyboard_lines(storyboard_json)
        specs = [
            ("episode_script", script_json, json.dumps(script_json, ensure_ascii=False)),
            ("storyboard", storyboard_json, "\n".join(storyboard_lines)),
            ("dialogue", {"lines": dialogue_lines}, "\n".join(dialogue_lines)),
            ("image_prompt", {"prompts": image_prompts}, "\n".join(image_prompts)),
            ("video_prompt", {"prompts": video_prompts}, "\n".join(video_prompts)),
        ]
        for artifact_type, content_json, content_text in specs:
            artifact = service.create_artifact(
                series_id=script.series_id,
                episode_id=script.episode_id,
                run_id=run.id,
                target_type="episode",
                target_id=script.episode_id,
                artifact_type=artifact_type,
                source_type="ai",
                input_json={
                    "source": "dramatic_script_pipeline",
                    "source_prompt": script.source_prompt,
                    "tags": list(script.tags),
                    "target_duration_seconds": script.target_duration_seconds,
                },
                content_json=content_json,
                content_text=content_text,
                model_trace_json={
                    "source": "dramatic_script_pipeline",
                    "pipeline_run_id": run.id,
                    "artifact_type": artifact_type,
                },
                review_trace_json=script.agency_trace,
                created_by="script_pipeline",
            )
            service.approve_artifact(artifact.id, actor_user_id="script_pipeline")

    def _script_snapshot(self, script: EpisodeScript, db_script_id: str) -> dict[str, Any]:
        return {
            "source": "dramatic_script_pipeline",
            "script_id": db_script_id,
            "source_prompt": script.source_prompt,
            "tags": script.tags,
            "target_duration_seconds": script.target_duration_seconds,
            "episode_asset_scope": dict(script.episode_asset_scope or {}),
            "dramatic_beats": script.dramatic_beats.model_dump(mode="json"),
            "scene_outlines": script.scene_outlines.model_dump(mode="json"),
            "visual_shots": script.visual_shots.model_dump(mode="json"),
            "agency_trace": script.agency_trace,
        }

    def _frame_asset_ids(self, script: EpisodeScript, shot: VisualShot) -> tuple[str, list[str]]:
        scope = script.episode_asset_scope if isinstance(script.episode_asset_scope, dict) else {}
        scene_ids = [str(value) for value in (scope.get("scene_ids") or []) if value]
        character_ids = [str(value) for value in (scope.get("character_ids") or []) if value]
        if not scene_ids or not character_ids:
            raise ScriptGenerationError(
                "Episode asset scope must include at least one scene and one character before storyboard export.",
                stage=PipelineStage.VISUAL_SHOTS.value,
                pipeline_run_id="",
                attempts=0,
                error_code="EPISODE_ASSET_SCOPE_MISSING",
            )
        scene_map = scope.get("scene_by_scene_number") if isinstance(scope.get("scene_by_scene_number"), dict) else {}
        mapped_scene_id = scene_map.get(str(shot.scene_number)) or scene_map.get(shot.scene_number)
        if len(scene_ids) > 1 and not mapped_scene_id:
            raise ScriptGenerationError(
                "Episode asset scope has multiple scenes; storyboard export requires scene_by_scene_number for every shot.",
                stage=PipelineStage.VISUAL_SHOTS.value,
                pipeline_run_id="",
                attempts=0,
                error_code="EPISODE_ASSET_SCOPE_MISSING",
            )
        return str(mapped_scene_id or scene_ids[0]), list(dict.fromkeys(character_ids))

    def _storyboard_snapshot(self, script: EpisodeScript) -> dict[str, Any]:
        frames = []
        for shot in script.visual_shots.shots:
            scene_id, character_ids = self._frame_asset_ids(script, shot)
            frame = {
                "frame_id": f"shot-{shot.shot_number:03d}",
                "image_prompt": shot.visual_prompt,
                "video_prompt": shot.video_prompt,
                "narration": shot.narration,
                "duration": shot.duration,
                "action": shot.beat_type.value,
                "emotion": shot.beat_type.value,
                "shot_type": "dramatic_script_pipeline",
                "scene_id": scene_id,
                "character_ids": character_ids,
            }
            frames.append(frame)
        storyboard = annotate_storyboard_with_timing({
            "source": "dramatic_script_pipeline",
            "frames": frames,
        })
        scenes_by_number = {scene.scene_number: scene for scene in script.scene_outlines.scenes}
        shot_type_by_beat = {
            DramaticBeatType.HOOK: "wide-to-close",
            DramaticBeatType.CONFLICT_1: "medium",
            DramaticBeatType.REVERSAL: "close_up",
            DramaticBeatType.CLIMAX: "low_angle_close_up",
            DramaticBeatType.CLIFFHANGER: "detail_close_up",
        }
        camera_by_beat = {
            DramaticBeatType.HOOK: "快速推进",
            DramaticBeatType.CONFLICT_1: "手持跟拍",
            DramaticBeatType.REVERSAL: "低角度推进",
            DramaticBeatType.CLIMAX: "压迫式推近",
            DramaticBeatType.CLIFFHANGER: "慢速悬停",
        }
        for frame, shot in zip(storyboard["frames"], script.visual_shots.shots):
            scene = scenes_by_number.get(shot.scene_number)
            subject = "、".join(scene.characters) if scene and scene.characters else "核心角色"
            location = scene.location if scene else "锁定场景"
            emotion = " / ".join(part for part in [
                shot.beat_type.value,
                scene.emotional_turn if scene else "",
            ] if part)
            continuity = scene.visual_mandate if scene else "承接上一镜头动作和情绪。"
            shot_type = shot_type_by_beat.get(shot.beat_type, "medium")
            camera_movement = camera_by_beat.get(shot.beat_type, "稳定跟拍")
            frame["shot_type"] = shot_type
            frame["camera_movement"] = camera_movement
            frame["action"] = shot.video_prompt
            frame["emotion"] = emotion
            image_prompt = build_detailed_image_prompt(
                time_range=frame["time_range"],
                subject=subject,
                scene=location,
                action=shot.video_prompt,
                shot_type=shot_type,
                emotion=emotion,
                raw_prompt=shot.visual_prompt,
                continuity=continuity,
            )
            video_prompt = build_detailed_video_prompt(
                time_range=frame["time_range"],
                subject=subject,
                scene=location,
                action=shot.video_prompt,
                shot_type=shot_type,
                camera_movement=camera_movement,
                emotion=emotion,
                raw_prompt=shot.video_prompt,
                continuity=continuity,
            )
            frame["raw_image_prompt"] = shot.visual_prompt
            frame["raw_video_prompt"] = shot.video_prompt
            frame["image_prompt"] = image_prompt
            frame["video_prompt"] = video_prompt
            frame["detailed_image_prompt"] = image_prompt
            frame["detailed_video_prompt"] = video_prompt
        return storyboard

    def mark_stage_completed_for_test(
        self,
        db: Session,
        *,
        run: PipelineRun,
        stage_name: str,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        output: dict[str, Any],
        gate_trace: dict[str, Any] | None = None,
    ) -> None:
        stage = PipelineStage(stage_name)
        state = _script_state(run)
        state["stages"][stage.value] = {
            "status": "completed",
            "attempts": 1,
            "input_hash": _input_hash(
                stage=stage,
                source_prompt=source_prompt,
                tags=tags,
                target_duration_seconds=target_duration_seconds,
                previous_outputs={},
            ),
            "output": output,
            "gate_trace": gate_trace,
            "error": None,
        }
        _persist_run_state(db, run)
