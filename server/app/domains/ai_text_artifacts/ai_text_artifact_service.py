"""AI 文本产物业务域模块。

AI 文本产物业务域，负责剧本、分镜、规划等文本产物的版本和审查状态。本文件负责 ai_text_artifact_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer
from app.db.models import Episode, Series, VideoProductionRun


SERIES_RUN_ARTIFACT_TYPES = ("series_bible", "series_story_plan", "season_arc", "continuity_ledger")
EPISODE_RUN_ARTIFACT_TYPES = (
    "episode_outline",
    "episode_script",
    "storyboard",
    "dialogue",
    "image_prompt",
    "video_prompt",
)
ARTIFACT_CONSUMPTION_ORDER = {
    artifact_type: index
    for index, artifact_type in enumerate(SERIES_RUN_ARTIFACT_TYPES + EPISODE_RUN_ARTIFACT_TYPES)
}


class AITextArtifactService:
    """业务类：承载 AITextArtifactService 相关的数据结构、状态或业务协作。"""
    def __init__(self, db: Session):
        """初始化业务对象依赖，保存后续流程需要的运行上下文。"""
        self.db = db

    def create_artifact(
        self,
        *,
        series_id: str,
        target_type: str,
        target_id: str,
        artifact_type: str,
        source_type: str,
        episode_id: str | None = None,
        run_id: str | None = None,
        production_plan_id: str | None = None,
        parent_artifact_id: str | None = None,
        input_json: dict[str, Any] | None = None,
        content_json: dict[str, Any] | None = None,
        content_text: str | None = None,
        model_trace_json: dict[str, Any] | None = None,
        review_trace_json: dict[str, Any] | None = None,
        created_by: str | None = None,
        status: str = "review_pending",
        commit: bool = True,
    ) -> AITextArtifact:
        """业务函数：处理 create_artifact 对应的业务流程、校验或数据转换。"""
        version = self._next_version(target_type, target_id, artifact_type)
        artifact = AITextArtifact(
            series_id=series_id,
            episode_id=episode_id,
            run_id=run_id,
            production_plan_id=production_plan_id,
            target_type=target_type,
            target_id=target_id,
            artifact_type=artifact_type,
            version=version,
            status=status,
            source_type=source_type,
            parent_artifact_id=parent_artifact_id,
            input_json=input_json or {},
            content_json=content_json or {},
            content_text=content_text,
            model_trace_json=model_trace_json or {},
            review_trace_json=review_trace_json or {},
            created_by=created_by,
        )
        self.db.add(artifact)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(artifact)
        return artifact

    def edit_artifact(
        self,
        artifact_id: str,
        *,
        content_json: dict[str, Any] | None = None,
        content_text: str | None = None,
        actor_user_id: str | None = None,
    ) -> AITextArtifact:
        """业务函数：处理 edit_artifact 对应的业务流程、校验或数据转换。"""
        parent = self._get_artifact(artifact_id)
        return self.create_artifact(
            series_id=parent.series_id,
            episode_id=parent.episode_id,
            run_id=parent.run_id,
            production_plan_id=parent.production_plan_id,
            target_type=parent.target_type,
            target_id=parent.target_id,
            artifact_type=parent.artifact_type,
            source_type="human_edit",
            parent_artifact_id=parent.id,
            input_json=parent.input_json or {},
            content_json=content_json or {},
            content_text=content_text,
            model_trace_json=parent.model_trace_json or {},
            review_trace_json=parent.review_trace_json or {},
            created_by=actor_user_id,
        )

    def regenerate_artifact(
        self,
        artifact_id: str,
        *,
        input_json: dict[str, Any] | None = None,
        content_json: dict[str, Any] | None = None,
        content_text: str | None = None,
        model_trace_json: dict[str, Any] | None = None,
        actor_user_id: str | None = None,
    ) -> AITextArtifact:
        """业务函数：处理 regenerate_artifact 对应的业务流程、校验或数据转换。"""
        parent = self._get_artifact(artifact_id)
        return self.create_artifact(
            series_id=parent.series_id,
            episode_id=parent.episode_id,
            run_id=parent.run_id,
            production_plan_id=parent.production_plan_id,
            target_type=parent.target_type,
            target_id=parent.target_id,
            artifact_type=parent.artifact_type,
            source_type="ai_regenerate",
            parent_artifact_id=parent.id,
            input_json=input_json or parent.input_json or {},
            content_json=content_json or {},
            content_text=content_text,
            model_trace_json=model_trace_json or {},
            review_trace_json={},
            created_by=actor_user_id,
        )

    async def regenerate_artifact_with_ai(
        self,
        artifact_id: str,
        *,
        input_json: dict[str, Any] | None = None,
        actor_user_id: str | None = None,
    ) -> AITextArtifact:
        """业务函数：处理 regenerate_artifact_with_ai 对应的业务流程、校验或数据转换。"""
        from app.domains.model_configuration.ai_generator import ai_generator

        parent = self._get_artifact(artifact_id)
        request_input = dict(input_json or {})
        effective_input = {
            **request_input,
            "parent_artifact_id": parent.id,
            "parent_version": parent.version,
            "artifact_type": parent.artifact_type,
        }
        raw_output = await ai_generator.generate_custom(
            self.db,
            self._regenerate_system_prompt(parent),
            self._regenerate_user_prompt(parent, effective_input),
            max_tokens=4096,
            temperature=0.7,
        )
        raw_text = str(raw_output or "").strip()
        parsed_json = self._parse_model_json(raw_text)
        return self.create_artifact(
            series_id=parent.series_id,
            episode_id=parent.episode_id,
            run_id=parent.run_id,
            production_plan_id=parent.production_plan_id,
            target_type=parent.target_type,
            target_id=parent.target_id,
            artifact_type=parent.artifact_type,
            source_type="ai_regenerate",
            parent_artifact_id=parent.id,
            input_json=effective_input,
            content_json=parsed_json if isinstance(parsed_json, dict) else {},
            content_text=raw_text,
            model_trace_json={
                "source": "ai_regenerate",
                "parent_artifact_id": parent.id,
                "parent_version": parent.version,
                "raw_output": raw_text,
            },
            review_trace_json={},
            created_by=actor_user_id,
        )

    def approve_artifact(
        self,
        artifact_id: str,
        *,
        actor_user_id: str | None = None,
        commit: bool = True,
    ) -> AITextArtifact:
        """业务函数：处理 approve_artifact 对应的业务流程、校验或数据转换。"""
        artifact = self._get_artifact(artifact_id)
        latest = self.latest_version(
            target_type=artifact.target_type,
            target_id=artifact.target_id,
            artifact_type=artifact.artifact_type,
        )
        if latest and latest.id != artifact.id:
            raise ValueError("stale_artifact_version")
        now = bj_now()
        others = (
            self.db.query(AITextArtifact)
            .filter(
                AITextArtifact.target_type == artifact.target_type,
                AITextArtifact.target_id == artifact.target_id,
                AITextArtifact.artifact_type == artifact.artifact_type,
                AITextArtifact.id != artifact.id,
                AITextArtifact.status.in_(("draft", "review_pending", "approved")),
            )
            .all()
        )
        for other in others:
            other.status = "superseded"
            other.superseded_at = now
        artifact.status = "approved"
        artifact.approved_at = now
        artifact.created_by = artifact.created_by or actor_user_id
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(artifact)
        return artifact

    def latest_approved(
        self,
        *,
        target_type: str,
        target_id: str,
        artifact_type: str,
    ) -> AITextArtifact | None:
        """业务函数：处理 latest_approved 对应的业务流程、校验或数据转换。"""
        return (
            self.db.query(AITextArtifact)
            .filter(
                AITextArtifact.target_type == target_type,
                AITextArtifact.target_id == target_id,
                AITextArtifact.artifact_type == artifact_type,
                AITextArtifact.status == "approved",
            )
            .order_by(AITextArtifact.version.desc())
            .first()
        )

    def latest_version(
        self,
        *,
        target_type: str,
        target_id: str,
        artifact_type: str,
    ) -> AITextArtifact | None:
        """业务函数：处理 latest_version 对应的业务流程、校验或数据转换。"""
        return (
            self.db.query(AITextArtifact)
            .filter(
                AITextArtifact.target_type == target_type,
                AITextArtifact.target_id == target_id,
                AITextArtifact.artifact_type == artifact_type,
            )
            .order_by(AITextArtifact.version.desc())
            .first()
        )

    def list_versions(
        self,
        *,
        target_type: str,
        target_id: str,
        artifact_type: str,
    ) -> list[AITextArtifact]:
        """业务函数：处理 list_versions 对应的业务流程、校验或数据转换。"""
        return (
            self.db.query(AITextArtifact)
            .filter(
                AITextArtifact.target_type == target_type,
                AITextArtifact.target_id == target_id,
                AITextArtifact.artifact_type == artifact_type,
            )
            .order_by(AITextArtifact.version.asc())
            .all()
        )

    def lineage(self, artifact_id: str) -> list[AITextArtifact]:
        """业务函数：处理 lineage 对应的业务流程、校验或数据转换。"""
        artifact = self._get_artifact(artifact_id)
        return self.list_versions(
            target_type=artifact.target_type,
            target_id=artifact.target_id,
            artifact_type=artifact.artifact_type,
        )

    def bind_consumer(
        self,
        artifact_id: str,
        *,
        consumer_type: str,
        consumer_id: str,
        run_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> AITextArtifactConsumer:
        """业务函数：处理 bind_consumer 对应的业务流程、校验或数据转换。"""
        artifact = self._get_artifact(artifact_id)
        existing = (
            self.db.query(AITextArtifactConsumer)
            .filter(
                AITextArtifactConsumer.artifact_id == artifact.id,
                AITextArtifactConsumer.consumer_type == consumer_type,
                AITextArtifactConsumer.consumer_id == consumer_id,
            )
            .first()
        )
        if existing:
            return existing
        consumer = AITextArtifactConsumer(
            artifact_id=artifact.id,
            consumer_type=consumer_type,
            consumer_id=consumer_id,
            series_id=artifact.series_id,
            episode_id=artifact.episode_id,
            run_id=run_id or artifact.run_id,
            metadata_json=metadata_json or {},
        )
        self.db.add(consumer)
        self.db.commit()
        self.db.refresh(consumer)
        return consumer

    def bind_latest_approved_for_episode_run(
        self,
        *,
        series_id: str,
        episode_id: str,
        run_id: str,
        production_plan_id: str | None = None,
    ) -> list[AITextArtifactConsumer]:
        """业务函数：处理 bind_latest_approved_for_episode_run 对应的业务流程、校验或数据转换。"""
        bindings: list[AITextArtifactConsumer] = []
        for artifact_type in SERIES_RUN_ARTIFACT_TYPES:
            artifact = self.latest_approved(
                target_type="series",
                target_id=series_id,
                artifact_type=artifact_type,
            )
            if artifact:
                bindings.append(self._bind_run_artifact(artifact, run_id, production_plan_id))
        for artifact_type in EPISODE_RUN_ARTIFACT_TYPES:
            artifact = self.latest_approved(
                target_type="episode",
                target_id=episode_id,
                artifact_type=artifact_type,
            )
            if artifact:
                bindings.append(self._bind_run_artifact(artifact, run_id, production_plan_id))
        return bindings

    def consumed_artifacts_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """业务函数：处理 consumed_artifacts_for_run 对应的业务流程、校验或数据转换。"""
        rows = (
            self.db.query(AITextArtifactConsumer, AITextArtifact)
            .join(AITextArtifact, AITextArtifactConsumer.artifact_id == AITextArtifact.id)
            .filter(
                AITextArtifactConsumer.consumer_type == "video_production_run",
                AITextArtifactConsumer.consumer_id == run_id,
            )
            .all()
        )
        payloads = [
            {
                "consumer_id": consumer.id,
                "artifact_id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "version": artifact.version,
                "status": artifact.status,
                "source_type": artifact.source_type,
                "target_type": artifact.target_type,
                "target_id": artifact.target_id,
                "series_id": artifact.series_id,
                "episode_id": artifact.episode_id,
                "run_id": consumer.run_id,
                "production_plan_id": artifact.production_plan_id,
                "metadata_json": consumer.metadata_json or {},
                "content_json": artifact.content_json or {},
                "content_text": artifact.content_text,
                "approved_at": artifact.approved_at.isoformat() if artifact.approved_at else None,
                "created_at": consumer.created_at.isoformat() if consumer.created_at else None,
            }
            for consumer, artifact in rows
        ]
        return sorted(
            payloads,
            key=lambda item: (
                ARTIFACT_CONSUMPTION_ORDER.get(item["artifact_type"], 999),
                item["artifact_type"],
                item["version"],
            ),
        )

    def _bind_run_artifact(
        self,
        artifact: AITextArtifact,
        run_id: str,
        production_plan_id: str | None,
    ) -> AITextArtifactConsumer:
        """业务函数：处理 _bind_run_artifact 对应的业务流程、校验或数据转换。"""
        return self.bind_consumer(
            artifact.id,
            consumer_type="video_production_run",
            consumer_id=run_id,
            run_id=run_id,
            metadata_json={
                "source": "start_episode_production",
                "artifact_type": artifact.artifact_type,
                "version": artifact.version,
                "production_plan_id": production_plan_id,
            },
        )

    def backfill_run_text_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """业务函数：处理 backfill_run_text_artifacts 对应的业务流程、校验或数据转换。"""
        run = self.db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
        if not run:
            raise ValueError("run_not_found")
        series = self.db.query(Series).filter(Series.id == run.series_id).first()
        if not series:
            raise ValueError("series_not_found")
        episode = self.db.query(Episode).filter(Episode.id == run.episode_id).first() if run.episode_id else None
        if not episode:
            raise ValueError("episode_not_found")

        storyboard = run.storyboard_json if isinstance(run.storyboard_json, dict) else {}
        if not storyboard.get("frames") and isinstance(episode.storyboard_json, dict):
            storyboard = episode.storyboard_json
        dialogue_lines = self._storyboard_dialogue_lines(storyboard)
        image_prompts = self._storyboard_prompt_lines(storyboard, "image_prompt")
        video_prompts = self._storyboard_prompt_lines(storyboard, "video_prompt")
        specs = [
            {
                "artifact_type": "series_bible",
                "target_type": "series",
                "target_id": series.id,
                "episode_id": None,
                "content_json": series.story_bible_json if isinstance(series.story_bible_json, dict) else {},
                "content_text": series.logline or series.title,
            },
            {
                "artifact_type": "continuity_ledger",
                "target_type": "series",
                "target_id": series.id,
                "episode_id": None,
                "content_json": self._legacy_continuity_ledger(series, episode),
                "content_text": series.logline or series.title,
            },
            {
                "artifact_type": "episode_outline",
                "target_type": "episode",
                "target_id": episode.id,
                "episode_id": episode.id,
                "content_json": self._legacy_episode_outline(series, episode),
                "content_text": episode.title or series.logline or series.title,
            },
        ]
        if isinstance(episode.script_json, dict) and episode.script_json:
            specs.append({
                "artifact_type": "episode_script",
                "target_type": "episode",
                "target_id": episode.id,
                "episode_id": episode.id,
                "content_json": episode.script_json,
                "content_text": json.dumps(episode.script_json, ensure_ascii=False),
            })
        specs.extend([
           {
                "artifact_type": "storyboard",
                "target_type": "episode",
                "target_id": episode.id,
                "episode_id": episode.id,
                "content_json": storyboard,
                "content_text": "\n".join(dialogue_lines),
            },
            {
                "artifact_type": "dialogue",
                "target_type": "episode",
                "target_id": episode.id,
                "episode_id": episode.id,
                "content_json": {"lines": dialogue_lines},
                "content_text": "\n".join(dialogue_lines),
            },
            {
                "artifact_type": "image_prompt",
                "target_type": "episode",
                "target_id": episode.id,
                "episode_id": episode.id,
                "content_json": {"prompts": image_prompts},
                "content_text": "\n".join(image_prompts),
            },
            {
                "artifact_type": "video_prompt",
                "target_type": "episode",
                "target_id": episode.id,
                "episode_id": episode.id,
                "content_json": {"prompts": video_prompts},
                "content_text": "\n".join(video_prompts),
            },
        ])
        for spec in specs:
            artifact = self._ensure_approved_legacy_artifact(
                series_id=series.id,
                episode_id=spec["episode_id"],
                target_type=spec["target_type"],
                target_id=spec["target_id"],
                artifact_type=spec["artifact_type"],
                content_json=spec["content_json"],
                content_text=spec["content_text"],
            )
            if artifact:
                self.bind_consumer(
                    artifact.id,
                    consumer_type="video_production_run",
                    consumer_id=run.id,
                    run_id=run.id,
                    metadata_json={
                        "source": "legacy_run_backfill",
                        "artifact_type": artifact.artifact_type,
                        "version": artifact.version,
                        "production_plan_id": run.production_plan_id,
                    },
                )
        return self.consumed_artifacts_for_run(run.id)

    def _ensure_approved_legacy_artifact(
        self,
        *,
        series_id: str,
        episode_id: str | None,
        target_type: str,
        target_id: str,
        artifact_type: str,
        content_json: dict[str, Any],
        content_text: str,
    ) -> AITextArtifact | None:
        """业务函数：处理 _ensure_approved_legacy_artifact 对应的业务流程、校验或数据转换。"""
        approved = self.latest_approved(
            target_type=target_type,
            target_id=target_id,
            artifact_type=artifact_type,
        )
        if approved:
            return approved
        if self.latest_version(target_type=target_type, target_id=target_id, artifact_type=artifact_type):
            return None
        artifact = self.create_artifact(
            series_id=series_id,
            episode_id=episode_id,
            target_type=target_type,
            target_id=target_id,
            artifact_type=artifact_type,
            source_type="legacy_run_backfill",
            input_json={"source": "legacy_run_backfill"},
            content_json=content_json,
            content_text=content_text,
            model_trace_json={"source": "legacy_run_backfill", "stage": "run_text_artifact_backfill"},
            created_by="system",
        )
        return self.approve_artifact(artifact.id, actor_user_id="system")

    def _storyboard_prompt_lines(self, storyboard: dict[str, Any], key: str) -> list[str]:
        """业务函数：处理 _storyboard_prompt_lines 对应的业务流程、校验或数据转换。"""
        frames = storyboard.get("frames") or []
        if not isinstance(frames, list):
            return []
        return [str(frame.get(key) or "") for frame in frames if isinstance(frame, dict) and frame.get(key)]

    def _storyboard_dialogue_lines(self, storyboard: dict[str, Any]) -> list[str]:
        """业务函数：处理 _storyboard_dialogue_lines 对应的业务流程、校验或数据转换。"""
        frames = storyboard.get("frames") or []
        lines: list[str] = []
        if not isinstance(frames, list):
            return lines
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            for key in ("dialogue", "narration", "voiceover"):
                value = frame.get(key)
                if isinstance(value, str) and value:
                    lines.append(value)
                elif isinstance(value, list):
                    lines.extend(str(item) for item in value if item)
        return lines

    def _legacy_episode_outline(self, series: Series, episode: Episode) -> dict[str, Any]:
        """业务函数：处理 _legacy_episode_outline 对应的业务流程、校验或数据转换。"""
        return {
            "schema_version": "series.episode_outline.v1",
            "episode_number": int(episode.episode_number),
            "title": episode.title or f"Episode {episode.episode_number}",
            "episode_goal": episode.title or series.logline or series.title,
            "previous_episode_handoff": "" if int(episode.episode_number) == 1 else f"承接第 {int(episode.episode_number) - 1} 集。",
            "central_conflict": series.logline or series.title,
        }

    def _legacy_continuity_ledger(self, series: Series, episode: Episode) -> dict[str, Any]:
        """业务函数：处理 _legacy_continuity_ledger 对应的业务流程、校验或数据转换。"""
        return {
            "schema_version": "series.continuity_ledger.v1",
            "series_id": series.id,
            "total_episodes": int(series.total_episodes or 1),
            "mainline": series.logline or series.title,
            "episode_timeline": [{
                "episode_number": int(episode.episode_number),
                "title": episode.title or f"Episode {episode.episode_number}",
                "handoff_to_next": "legacy_run_backfill",
            }],
        }

    def _regenerate_system_prompt(self, artifact: AITextArtifact) -> str:
        """业务函数：处理 _regenerate_system_prompt 对应的业务流程、校验或数据转换。"""
        if artifact.content_json:
            return (
                "你是短剧生产系统的文字产物再生成助手。"
                "必须根据用户要求重新生成同一类文本产物，并尽量保持原 JSON schema。"
                "只输出可解析的 JSON，不要解释。"
            )
        return (
            "你是短剧生产系统的文字产物再生成助手。"
            "必须根据用户要求重新生成同一类文本产物，只输出新文本，不要解释。"
        )

    def _regenerate_user_prompt(self, artifact: AITextArtifact, input_json: dict[str, Any]) -> str:
        """业务函数：处理 _regenerate_user_prompt 对应的业务流程、校验或数据转换。"""
        return "\n".join([
            f"artifact_type: {artifact.artifact_type}",
            f"target_type: {artifact.target_type}",
            f"target_id: {artifact.target_id}",
            "regenerate_request:",
            json.dumps(input_json, ensure_ascii=False, indent=2),
            "current_content_json:",
            json.dumps(artifact.content_json or {}, ensure_ascii=False, indent=2),
            "current_content_text:",
            artifact.content_text or "",
        ])

    def _parse_model_json(self, raw_text: str) -> dict[str, Any] | list[Any] | None:
        """业务函数：处理 _parse_model_json 对应的业务流程、校验或数据转换。"""
        if not raw_text:
            return None
        candidates = [raw_text]
        if "```" in raw_text:
            fenced = raw_text.strip()
            if fenced.startswith("```"):
                fenced = fenced.strip("`").strip()
                if fenced.startswith("json"):
                    fenced = fenced[4:].strip()
                candidates.append(fenced)
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if 0 <= start < end:
            candidates.append(raw_text[start:end + 1])
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, (dict, list)):
                return parsed
        return None

    def _next_version(self, target_type: str, target_id: str, artifact_type: str) -> int:
        """业务函数：处理 _next_version 对应的业务流程、校验或数据转换。"""
        current = (
            self.db.query(func.max(AITextArtifact.version))
            .filter(
                AITextArtifact.target_type == target_type,
                AITextArtifact.target_id == target_id,
                AITextArtifact.artifact_type == artifact_type,
            )
            .scalar()
        )
        return int(current or 0) + 1

    def _get_artifact(self, artifact_id: str) -> AITextArtifact:
        """业务函数：处理 _get_artifact 对应的业务流程、校验或数据转换。"""
        artifact = self.db.query(AITextArtifact).filter(AITextArtifact.id == artifact_id).first()
        if not artifact:
            raise ValueError("artifact_not_found")
        return artifact
