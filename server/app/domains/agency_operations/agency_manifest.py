"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_manifest 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "agency_agents_zh"
MANIFEST_PATH = DATA_ROOT / "manifest.json"

EXPERT_IDS = (
    "story_generator",
    "narrative_designer",
    "visual_storyteller",
    "image_prompt_engineer",
    "prompt_engineer",
    "short_video_editing_coach",
    "douyin_strategist",
    "video_optimization_specialist",
    "style_lock_quality_reviewer",
    "storyboard_quality_reviewer",
    "image_stage_quality_reviewer",
    "image_review_quality_reviewer",
    "video_stage_quality_reviewer",
    "video_review_quality_reviewer",
    "compose_quality_reviewer",
)

LEGACY_EXPERT_PATHS = {
    "reality_checker": ("历史审计角色", "testing/testing-reality-checker.md"),
}


class AgencyManifestError(RuntimeError):
    pass


class AgencyExpertSource(BaseModel):
    expert_id: str
    name_zh: str
    role_type: str
    source_path: str
    sha256: str
    phases: list[str] = Field(default_factory=list)


class AgencyManifest(BaseModel):
    source_repo: str
    source_commit: str
    team_version: str
    experts: list[AgencyExpertSource]

    @model_validator(mode="after")
    def validate_expert_team(self) -> "AgencyManifest":
        expert_ids = [expert.expert_id for expert in self.experts]
        if expert_ids != list(EXPERT_IDS):
            raise ValueError(f"manifest experts must match expected team: {list(EXPERT_IDS)}")
        return self


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expert_path(expert: AgencyExpertSource) -> Path:
    path = (DATA_ROOT / expert.source_path).resolve()
    data_root = DATA_ROOT.resolve()
    if path != data_root and data_root not in path.parents:
        raise AgencyManifestError(f"expert path escapes data root: {expert.source_path}")
    return path


@lru_cache(maxsize=1)
def load_manifest() -> AgencyManifest:
    if not MANIFEST_PATH.exists():
        raise AgencyManifestError(f"agency manifest not found: {MANIFEST_PATH}")
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return AgencyManifest.model_validate(data)
    except AgencyManifestError:
        raise
    except Exception as exc:
        raise AgencyManifestError(f"invalid agency manifest: {exc}") from exc


def list_experts() -> list[AgencyExpertSource]:
    return load_manifest().experts


def get_expert(expert_id: str) -> AgencyExpertSource:
    for expert in list_experts():
        if expert.expert_id == expert_id:
            return expert
    raise AgencyManifestError(f"unknown agency expert: {expert_id}")


def get_legacy_expert(expert_id: str) -> AgencyExpertSource:
    legacy = LEGACY_EXPERT_PATHS.get(expert_id)
    if not legacy:
        raise AgencyManifestError(f"unknown agency expert: {expert_id}")
    name_zh, source_path = legacy
    path = _safe_expert_path(source_path)
    if not path.is_file():
        raise AgencyManifestError(f"legacy expert markdown not found: {source_path}")
    return AgencyExpertSource(
        expert_id=expert_id,
        name_zh=name_zh,
        role_type="legacy",
        source_path=source_path,
        sha256=_sha256(path),
        phases=[],
    )


def _safe_expert_path(source_path: str) -> Path:
    path = (DATA_ROOT / source_path).resolve()
    data_root = DATA_ROOT.resolve()
    if path != data_root and data_root not in path.parents:
        raise AgencyManifestError(f"expert path escapes data root: {source_path}")
    return path


def read_expert_markdown(expert_id: str) -> str:
    expert = get_expert(expert_id)
    path = _expert_path(expert)
    if not path.is_file():
        raise AgencyManifestError(f"expert markdown not found: {expert.source_path}")
    actual_sha256 = _sha256(path)
    if actual_sha256 != expert.sha256:
        raise AgencyManifestError(f"expert markdown hash mismatch: {expert.source_path}")
    return path.read_text(encoding="utf-8")


def read_legacy_expert_markdown(expert_id: str) -> str:
    expert = get_legacy_expert(expert_id)
    path = _expert_path(expert)
    return path.read_text(encoding="utf-8")


def verify_manifest() -> dict:
    errors = []
    checked_count = 0
    try:
        experts = list_experts()
    except AgencyManifestError as exc:
        return {"ok": False, "checked_count": 0, "errors": [str(exc)]}

    for expert in experts:
        try:
            path = _expert_path(expert)
            if not path.is_file():
                raise AgencyManifestError(f"missing markdown: {expert.source_path}")
            actual_sha256 = _sha256(path)
            if actual_sha256 != expert.sha256:
                raise AgencyManifestError(f"hash mismatch: {expert.source_path}")
            checked_count += 1
        except AgencyManifestError as exc:
            errors.append(str(exc))

    return {"ok": not errors, "checked_count": checked_count, "errors": errors}
