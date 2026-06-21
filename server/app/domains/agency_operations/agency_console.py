"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_console 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import object_session

from app.db.models.video_library import GeneratedVideo
from app.db.models.agency_operations import AgencyCreativePatch, AgencyExpertInvocation
from app.db.models import (
    Episode,
    PipelineRun,
    ProductionJob,
    ProductionPlan,
    Series,
    VideoProductionRun,
)
from app.domains.agency_operations.agency_creative_patch_service import creative_patch_summary
from app.domains.agency_operations.agency_manifest import list_experts, load_manifest
from app.domains.agency_operations.agency_orchestrator import STAGE_DAG
from app.domains.agency_operations.video_agency_team import ensure_video_agency_team, summarize_video_agency_team


ROLE_LABELS = {
    "narrative_designer": "叙事设计师",
    "visual_storyteller": "视觉叙事师",
    "image_prompt_engineer": "图像提示词工程师",
    "prompt_engineer": "提示词工程师",
    "short_video_editing_coach": "短视频剪辑指导师",
    "douyin_strategist": "抖音策略师",
    "video_optimization_specialist": "视频优化专家",
    "reality_checker": "历史审计角色",
}

QUALITY_GATE_LABELS = {
    "style_lock": [
        "\u89d2\u8272\u8eab\u4efd\u3001\u5916\u89c2\u3001\u670d\u88c5\u3001\u58f0\u97f3\u7b56\u7565\u548c\u53c2\u8003\u56fe\u5df2\u9501\u5b9a\u3002",
        "\u573a\u666f\u4f4d\u7f6e\u3001\u5149\u7ebf\u3001\u6c1b\u56f4\u548c\u53c2\u8003\u56fe\u5df2\u9501\u5b9a\u3002",
        "\u7f3a\u5931\u7d20\u6750\u5df2\u660e\u786e\u6807\u8bb0\u4e3a\u963b\u65ad\u6216\u98ce\u9669\u3002",
    ],
    "storyboard": [
        "\u6bcf\u4e2a\u5206\u955c\u90fd\u5305\u542b\u89d2\u8272\u3001\u573a\u666f\u3001\u53c2\u8003\u56fe\u3001\u753b\u9762\u63d0\u793a\u8bcd\u3001\u65c1\u767d\u3001\u65f6\u957f\u3001\u97f3\u9891\u6a21\u5f0f\u548c\u8fde\u7eed\u6027\u8bf4\u660e\u3002",
        "\u9996\u4e2a\u5206\u955c\u5177\u5907\u660e\u786e\u7684\u77ed\u89c6\u9891\u94a9\u5b50\u3002",
        "\u5206\u955c\u6cbf\u7528\u5df2\u9501\u5b9a\u7684\u89d2\u8272\u548c\u573a\u666f\u8bbe\u5b9a\u3002",
    ],
    "image_stage": [
        "\u6bcf\u4e2a\u56fe\u50cf\u8bf7\u6c42\u90fd\u5e26\u5165\u5206\u955c\u53c2\u8003\u56fe\u548c\u9501\u5b9a\u98ce\u683c\u7ea6\u675f\u3002",
        "\u56fe\u50cf\u63d0\u793a\u8bcd\u4e0e\u65c1\u767d\u548c\u8fde\u7eed\u6027\u8bf4\u660e\u4fdd\u6301\u4e00\u81f4\u3002",
        "\u56fe\u50cf\u751f\u6210\u8bf7\u6c42\u7ed3\u6784\u7a33\u5b9a\u4e14\u53ef\u6062\u590d\u3002",
    ],
    "image_review": [
        "图像已保持角色身份、场景氛围和锁定视觉风格。",
        "不通过的图像已给出可执行的改图或重绘要求。",
        "没有证据表明参考图被尊重时，不允许进入视频生成。",
    ],
    "video_stage": [
        "\u6bcf\u4e2a\u89c6\u9891\u8bf7\u6c42\u90fd\u5e26\u5165\u5df2\u786e\u8ba4\u7684\u56fe\u50cf\u53c2\u8003\u548c\u9501\u5b9a\u98ce\u683c\u7ea6\u675f\u3002",
        "\u89c6\u9891\u63d0\u793a\u8bcd\u4e0e\u65c1\u767d\u548c\u8fde\u7eed\u6027\u8bf4\u660e\u4fdd\u6301\u4e00\u81f4\u3002",
        "\u89c6\u9891\u751f\u6210\u8bf7\u6c42\u7ed3\u6784\u7a33\u5b9a\u4e14\u53ef\u6062\u590d\u3002",
    ],
    "video_review": [
        "视频片段已保持动作连续性、角色身份和镜头意图。",
        "不通过的片段已给出可执行的重生成要求。",
        "存在形变、漂移或运动异常时，不允许进入合成。",
    ],
    "compose": [
        "\u5b57\u5e55\u3001\u80cc\u666f\u97f3\u3001\u7247\u5934\u7247\u5c3e\u3001\u6c34\u5370\u548c\u8f93\u51fa\u89c4\u683c\u6765\u81ea\u9501\u5b9a\u5305\u88c5\u7b56\u7565\u3002",
        "\u526a\u8f91\u4fdd\u6301\u7ad6\u5c4f\u77ed\u89c6\u9891\u8282\u594f\uff0c\u907f\u514d\u65e0\u6548\u505c\u987f\u3002",
        "\u6700\u7ec8\u89c6\u9891\u5df2\u56de\u5199\u5230\u5267\u96c6\u548c\u89c6\u9891\u8d44\u4ea7\u5e93\u3002",
    ],
}

LAYER_LABELS = {
    0: ("layer_0_assets", "L0 图像资产生成", "render"),
    1: ("layer_1_narration", "L1 旁白生成", "storyboard"),
    2: ("layer_2_title", "L2 标题生成", "storyboard"),
    3: ("layer_3_image_prompt", "L3 图像提示词生成", "image_stage"),
    4: ("layer_4_render", "L4 视频渲染", "video_stage"),
    5: ("layer_5_postproduction", "L5 后期剪辑", "compose"),
}

STAGE_LABELS = {
    "story_planning": "故事规划",
    "style_lock": "\u98ce\u683c\u9501\u5b9a",
    "storyboard": "\u5206\u955c\u811a\u672c",
    "image_stage": "\u56fe\u50cf\u751f\u6210",
    "image_review": "图像审查",
    "video_stage": "\u89c6\u9891\u751f\u6210",
    "video_review": "视频审查",
    "compose_preflight": "合成预检",
    "compose": "\u5408\u6210\u4ea4\u4ed8",
}

LEGACY_LAYER_PHASES = {
    "layer_3_image_prompt": "image_stage",
    "layer_4_render": "video_stage",
    "layer_5_postproduction": "compose",
    "episode_writeback": "compose",
    "video_library_writeback": "compose",
}


def _safe_text(value: Any, limit: int = 160) -> str:
    """业务函数：处理 _safe_text 对应的业务流程、校验或数据转换。"""
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _localized_role(role: dict) -> dict:
    """业务函数：处理 _localized_role 对应的业务流程、校验或数据转换。"""
    role_id = role.get("id", "")
    return {
        "id": role_id,
        "name": ROLE_LABELS.get(role_id, "\u4e13\u5bb6\u89d2\u8272"),
        "source_role": role.get("source_role", ""),
        "source_path": role.get("source_path", ""),
        "source_commit": role.get("source_commit", ""),
        "source_sha256": role.get("source_sha256", ""),
        "phase": list(role.get("phase") or []),
    }


def _localized_quality_gates(team: dict) -> dict:
    """业务函数：处理 _localized_quality_gates 对应的业务流程、校验或数据转换。"""
    quality_gates = team.get("quality_gates") or {}
    return {
        phase: QUALITY_GATE_LABELS.get(phase, ["\u5b8c\u6210\u8be5\u9636\u6bb5\u8d28\u91cf\u68c0\u67e5\u3002"] * len(items))
        for phase, items in quality_gates.items()
        if isinstance(items, list)
    }


def _localized_agency_team(team: dict) -> dict:
    """业务函数：处理 _localized_agency_team 对应的业务流程、校验或数据转换。"""
    return {
        "enabled": bool(team.get("enabled")),
        "version": team.get("version", ""),
        "source": "agency-agents-zh \u89d2\u8272\u5339\u914d",
        "operating_model": "\u5185\u7f6e\u4e13\u5bb6\u56e2\u961f",
        "core_roles": [_localized_role(role) for role in team.get("core_roles") or []],
        "support_roles": [_localized_role(role) for role in team.get("support_roles") or []],
        "quality_roles": [_localized_role(role) for role in team.get("quality_roles") or []],
        "quality_gates": _localized_quality_gates(team),
    }


def _gate_list(team: dict, phase: str) -> list[str]:
    """业务函数：处理 _gate_list 对应的业务流程、校验或数据转换。"""
    gates = team.get("quality_gates") or {}
    return list(gates.get(phase, []))


def _roles_for_phase(team: dict, phase: str) -> list[str]:
    """业务函数：处理 _roles_for_phase 对应的业务流程、校验或数据转换。"""
    roles: list[str] = []
    for role in (
        list(team.get("core_roles") or []) +
        list(team.get("support_roles") or []) +
        list(team.get("quality_roles") or [])
    ):
        if phase in (role.get("phase") or []):
            rid = role.get("id")
            if rid:
                roles.append(rid)
    return roles


def _step(step_id: str, label: str, status: str, phase: str, team: dict,
          input_summary: dict | None = None, output_summary: dict | None = None,
          persistence: list[str] | None = None, error: str = "") -> dict:
    """业务函数：处理 _step 对应的业务流程、校验或数据转换。"""
    input_summary = input_summary or {}
    output_summary = output_summary or {}
    gates = _gate_list(team, phase)
    summary = _step_summary(label, status, input_summary, output_summary, error)
    return {
        "id": step_id,
        "label": label,
        "status": status,
        "phase": phase,
        "agency_roles": _roles_for_phase(team, phase),
        "quality_gates": gates,
        "gate_results": _gate_results(gates, status),
        "summary": summary,
        "next_action": _next_action(step_id, status, error),
        "input_summary": input_summary,
        "output_summary": output_summary,
        "persistence": persistence or [],
        "error": _safe_text(error, 500),
    }


def _step_summary(label: str, status: str, input_summary: dict, output_summary: dict, error: str) -> str:
    """业务函数：处理 _step_summary 对应的业务流程、校验或数据转换。"""
    if status == "failed":
        return f"{label}失败，系统已记录失败原因和建议操作。"
    if status == "running":
        frame_count = input_summary.get("frame_count")
        if frame_count:
            return f"{label}正在处理 {frame_count} 个分镜帧。"
        return f"{label}正在执行。"
    if status == "completed":
        video_path = output_summary.get("video_path") or output_summary.get("video_url")
        if video_path:
            return f"{label}已完成，产出视频 {video_path}。"
        frame_count = output_summary.get("frame_count") or output_summary.get("frame_result_count")
        if frame_count:
            return f"{label}已完成，产出 {frame_count} 个结果。"
        return f"{label}已完成。"
    return f"{label}尚未执行。"


def _next_action(step_id: str, status: str, error: str = "") -> str:
    """业务函数：处理 _next_action 对应的业务流程、校验或数据转换。"""
    if status == "completed":
        return "无需处理"
    if status == "running":
        return "等待当前步骤完成"
    if status == "failed":
        return _recovery_action(error)
    actions = {
        "input": "先填写系列标题和一句话故事",
        "style_lock": "先完成风格锁定",
        "auto_plan": "先生成自动分镜",
        "episode_writeback": "等待后期剪辑完成后写回剧集",
        "video_library_writeback": "等待最终视频写入资产库",
    }
    return actions.get(step_id, "等待流水线执行到该步骤")


def _recovery_action(error: str) -> str:
    """业务函数：处理 _recovery_action 对应的业务流程、校验或数据转换。"""
    text = (error or "").lower()
    if "timeout" in text or "超时" in text:
        return "检查外部视频服务状态后从失败层重试"
    if "api_key" in text or "unauthorized" in text or "401" in text:
        return "检查模型 API Key 和服务权限"
    if "reference" in text or "asset" in text or "参考" in text:
        return "补齐角色/场景参考资产后重新生成"
    return "查看失败摘要，修复配置或素材后重试"


def _gate_results(gates: list[str], status: str) -> list[dict]:
    """业务函数：处理 _gate_results 对应的业务流程、校验或数据转换。"""
    if not gates:
        return []
    gate_status = "passed" if status == "completed" else "failed" if status == "failed" else "warn"
    return [{
        "label": gate,
        "status": gate_status,
        "message": "已满足" if gate_status == "passed" else "失败步骤需修复" if gate_status == "failed" else "等待该步骤完成后确认",
    } for gate in gates]


def _readiness_check(check_id: str, label: str, status: str, message: str, next_action: str) -> dict:
    """业务函数：处理 _readiness_check 对应的业务流程、校验或数据转换。"""
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "message": message,
        "next_action": next_action,
    }


def _build_readiness(series: Series, style_lock: dict, current_episode: Episode | None) -> dict:
    """业务函数：处理 _build_readiness 对应的业务流程、校验或数据转换。"""
    missing_assets = style_lock.get("missing_assets") or []
    characters = style_lock.get("characters") or []
    scenes = style_lock.get("scenes") or []
    storyboard = current_episode.storyboard_json if current_episode else {}
    frames = storyboard.get("frames", []) if isinstance(storyboard, dict) else []
    checks = [
        _readiness_check(
            "series_input",
            "系列一句话",
            "passed" if series.logline else "blocked",
            "已填写一句话故事" if series.logline else "缺少一句话故事，无法生成系列内容",
            "填写系列一句话" if not series.logline else "无需处理",
        ),
        _readiness_check(
            "style_lock",
            "风格锁定",
            "passed" if style_lock.get("locked") else "blocked",
            f"风格已锁定 v{style_lock.get('version', 0)}" if style_lock.get("locked") else "尚未锁定角色、场景和包装规则",
            "先完成风格锁定" if not style_lock.get("locked") else "无需处理",
        ),
        _readiness_check(
            "reference_assets",
            "参考资产",
            "warn" if missing_assets else "passed",
            f"仍有 {len(missing_assets)} 个待补资产" if missing_assets else f"角色 {len(characters)} 个，场景 {len(scenes)} 个",
            "补齐待补资产或重新锁定风格" if missing_assets else "无需处理",
        ),
        _readiness_check(
            "storyboard",
            "自动分镜",
            "passed" if frames else "warn",
            f"已有 {len(frames)} 个分镜帧" if frames else "还没有保存自动分镜，启动流水线前会自动生成",
            "启动前生成自动分镜" if not frames else "无需处理",
        ),
    ]
    status = "blocked" if any(c["status"] == "blocked" for c in checks) else "warning" if any(c["status"] == "warn" for c in checks) else "ready"
    return {"status": status, "checks": checks}


def _build_quality_report(steps: list[dict], generated_video: GeneratedVideo | None, current_episode: Episode | None) -> dict:
    """业务函数：处理 _build_quality_report 对应的业务流程、校验或数据转换。"""
    if generated_video and generated_video.video_path and current_episode and current_episode.video_url:
        return {
            "status": "pass",
            "score": 90,
            "summary": "最终视频已生成，并已写回剧集和视频资产库。",
        }
    if any(step["status"] == "failed" for step in steps):
        return {
            "status": "failed",
            "score": 35,
            "summary": "生产流程存在失败步骤，需要按失败建议处理后重试。",
        }
    if any(step["status"] == "running" for step in steps):
        return {
            "status": "running",
            "score": 60,
            "summary": "生产流程正在执行，质量结果会在最终视频生成后确认。",
        }
    if any(step["status"] == "pending" for step in steps):
        return {
            "status": "pending",
            "score": 45,
            "summary": "生产流程尚未完成，当前只能检查准备度和已保存资产。",
        }
    return {"status": "warn", "score": 70, "summary": "流程已执行，但缺少最终视频写回信息。"}


def _expert_team() -> list[dict]:
    """业务函数：处理 _expert_team 对应的业务流程、校验或数据转换。"""
    manifest = load_manifest()
    return [{
        "expert_id": expert.expert_id,
        "name": expert.name_zh,
        "role_type": expert.role_type,
        "source_path": expert.source_path,
        "source_commit": manifest.source_commit,
        "sha256": expert.sha256,
        "phases": expert.phases,
    } for expert in list_experts()]


def _invocation_summary(row: AgencyExpertInvocation) -> dict:
    """业务函数：处理 _invocation_summary 对应的业务流程、校验或数据转换。"""
    output = row.output_summary_json or {}
    is_legacy = row.expert_id == "reality_checker"
    decision = output.get("decision") or output.get("summary") or row.error_message or ""
    next_action = output.get("next_action") or output.get("recommendation")
    if not next_action:
        recommendations = output.get("recommendations")
        if isinstance(recommendations, list):
            next_action = "；".join(_redact_user_list(recommendations))
    return {
        "id": row.id,
        "stage": row.stage,
        "expert_id": row.expert_id,
        "role": row.role,
        "execution_status": row.execution_status,
        "result_status": row.result_status,
        "summary": _redact_user_text(decision),
        "decision": _redact_user_text(output.get("decision") or decision),
        "findings": _redact_user_list(output.get("findings")),
        "required_changes": _redact_user_list(output.get("required_changes")),
        "evidence": _redact_user_list(row.evidence_json, limit=3),
        "next_action": _redact_user_text(next_action or ""),
        "duration_ms": row.duration_ms,
        "error_code": row.error_code,
        "legacy": is_legacy,
        "display_scope": "historical_audit" if is_legacy else "current_team",
    }


def _redact_user_text(value: Any) -> str:
    """业务函数：处理 _redact_user_text 对应的业务流程、校验或数据转换。"""
    text = _safe_text(value, 500)
    lowered = text.lower()
    if "authorization" in lowered or "bearer " in lowered or "api_key" in lowered or "api key" in lowered:
        return "模型服务授权失败，请检查模型配置。"
    return text


def _redact_user_list(value: Any, *, limit: int = 5) -> list[str]:
    """业务函数：处理 _redact_user_list 对应的业务流程、校验或数据转换。"""
    if not value:
        return []
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values[:limit]:
        if isinstance(item, dict):
            frame_id = item.get("frame_id") or item.get("shot_id") or item.get("id")
            reason = item.get("reason") or item.get("summary") or item.get("message") or item.get("text")
            if frame_id and reason:
                text = f"{frame_id}: {reason}"
            elif reason:
                text = str(reason)
            else:
                text = "；".join(f"{key}: {value}" for key, value in item.items() if value)
        else:
            text = str(item)
        redacted = _redact_user_text(text)
        if redacted:
            result.append(redacted)
    return result


def _current_stage_assignments() -> set[tuple[str, str, str]]:
    """业务函数：处理 _current_stage_assignments 对应的业务流程、校验或数据转换。"""
    assignments: set[tuple[str, str, str]] = set()
    for stage, config in STAGE_DAG.items():
        for expert_id in config.get("reviewers") or []:
            assignments.add((stage, expert_id, "reviewer"))
        lead = config.get("lead")
        if lead:
            assignments.add((stage, lead, "lead"))
        for expert_id in config.get("qa") or []:
            assignments.add((stage, expert_id, "qa"))
    return assignments


def _current_latest_invocations(rows: list[AgencyExpertInvocation]) -> list[AgencyExpertInvocation]:
    """业务函数：处理 _current_latest_invocations 对应的业务流程、校验或数据转换。"""
    assignments = _current_stage_assignments()
    latest_by_assignment: dict[tuple[str, str, str], AgencyExpertInvocation] = {}
    for row in rows:
        if row.expert_id == "reality_checker":
            continue
        key = (row.stage, row.expert_id, row.role)
        if key not in assignments:
            continue
        latest_by_assignment[key] = row
    return sorted(
        latest_by_assignment.values(),
        key=lambda row: (row.created_at, row.id),
    )


def _style_lock_trace(series: Series) -> dict | None:
    """业务函数：处理 _style_lock_trace 对应的业务流程、校验或数据转换。"""
    story_bible = series.story_bible_json or {}
    if not isinstance(story_bible, dict):
        return None
    style_lock = story_bible.get("style_lock")
    if not isinstance(style_lock, dict):
        return None
    trace = style_lock.get("agency_trace")
    return trace if isinstance(trace, dict) else None


def _style_lock_trace_invocation_ids(series: Series) -> set[str] | None:
    """业务函数：处理 _style_lock_trace_invocation_ids 对应的业务流程、校验或数据转换。"""
    trace = _style_lock_trace(series)
    return _trace_invocation_ids(trace)


def _storyboard_trace(episode: Episode | None) -> dict | None:
    """业务函数：处理 _storyboard_trace 对应的业务流程、校验或数据转换。"""
    storyboard = episode.storyboard_json if episode else None
    if not isinstance(storyboard, dict):
        return None
    trace = storyboard.get("agency_trace")
    return trace if isinstance(trace, dict) else None


def _trace_invocation_ids(trace: dict | None) -> set[str] | None:
    """业务函数：处理 _trace_invocation_ids 对应的业务流程、校验或数据转换。"""
    if not trace or "invocation_ids" not in trace:
        return None
    invocation_ids = trace.get("invocation_ids") or []
    if not isinstance(invocation_ids, list):
        return set()
    return {str(invocation_id) for invocation_id in invocation_ids if invocation_id}


def _storyboard_trace_invocation_ids(episode: Episode | None) -> set[str] | None:
    """业务函数：处理 _storyboard_trace_invocation_ids 对应的业务流程、校验或数据转换。"""
    return _trace_invocation_ids(_storyboard_trace(episode))


def _front_stage_trace_invocation_ids(series: Series, current_episode: Episode | None) -> set[str]:
    """业务函数：处理 _front_stage_trace_invocation_ids 对应的业务流程、校验或数据转换。"""
    invocation_ids: set[str] = set()
    for ids in (
        _style_lock_trace_invocation_ids(series),
        _storyboard_trace_invocation_ids(current_episode),
    ):
        if ids:
            invocation_ids.update(ids)
    return invocation_ids


def _filter_current_front_stage_rows(
    rows: list[AgencyExpertInvocation],
    series: Series,
    current_episode: Episode | None,
) -> list[AgencyExpertInvocation]:
    """业务函数：处理 _filter_current_front_stage_rows 对应的业务流程、校验或数据转换。"""
    style_lock_trace_ids = _style_lock_trace_invocation_ids(series)
    storyboard_trace_ids = _storyboard_trace_invocation_ids(current_episode)
    filtered = rows
    if style_lock_trace_ids is not None:
        filtered = [
            row for row in filtered
            if row.stage != "style_lock" or row.id in style_lock_trace_ids
        ]
    if storyboard_trace_ids is not None:
        filtered = [
            row for row in filtered
            if row.stage != "storyboard" or row.id in storyboard_trace_ids
        ]
    return filtered


def _load_agency_invocation_rows(
    series: Series,
    current_episode: Episode | None,
    latest_run: PipelineRun | VideoProductionRun | None,
    run_type: str | None,
) -> list[AgencyExpertInvocation]:
    """业务函数：处理 _load_agency_invocation_rows 对应的业务流程、校验或数据转换。"""
    db = object_session(series)
    if db is None:
        return []
    query = db.query(AgencyExpertInvocation).filter(AgencyExpertInvocation.series_id == series.id)
    if latest_run:
        if run_type == "video_production":
            run_query = query.filter(AgencyExpertInvocation.run_id == latest_run.id)
        else:
            run_query = query.filter(AgencyExpertInvocation.pipeline_run_id == latest_run.id)
        rows = run_query.order_by(AgencyExpertInvocation.created_at.asc(), AgencyExpertInvocation.id.asc()).all()
        front_stage_ids = _front_stage_trace_invocation_ids(series, current_episode)
        if front_stage_ids:
            front_rows = (
                query.filter(AgencyExpertInvocation.id.in_(front_stage_ids))
                .order_by(AgencyExpertInvocation.created_at.asc(), AgencyExpertInvocation.id.asc())
                .all()
            )
            rows_by_id = {row.id: row for row in [*front_rows, *rows]}
            rows = sorted(rows_by_id.values(), key=lambda row: (row.created_at, row.id))
        return rows
    rows = query.order_by(AgencyExpertInvocation.created_at.asc(), AgencyExpertInvocation.id.asc()).limit(100).all()
    return _filter_current_front_stage_rows(rows, series, current_episode)


def _load_agency_invocations(
    series: Series,
    current_episode: Episode | None,
    latest_run: PipelineRun | VideoProductionRun | None,
    run_type: str | None,
) -> list[AgencyExpertInvocation]:
    """业务函数：处理 _load_agency_invocations 对应的业务流程、校验或数据转换。"""
    return _current_latest_invocations(_load_agency_invocation_rows(series, current_episode, latest_run, run_type))


def _load_legacy_reality_checker_rows(series: Series, *, limit: int = 50) -> list[AgencyExpertInvocation]:
    """业务函数：处理 _load_legacy_reality_checker_rows 对应的业务流程、校验或数据转换。"""
    db = object_session(series)
    if db is None:
        return []
    return (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.expert_id == "reality_checker",
        )
        .order_by(AgencyExpertInvocation.created_at.desc(), AgencyExpertInvocation.id.desc())
        .limit(limit)
        .all()
    )


def _load_decision_log_invocations(
    series: Series,
    current_episode: Episode | None,
    latest_run: PipelineRun | VideoProductionRun | None,
    run_type: str | None,
) -> list[AgencyExpertInvocation]:
    """业务函数：处理 _load_decision_log_invocations 对应的业务流程、校验或数据转换。"""
    rows = _load_agency_invocation_rows(series, current_episode, latest_run, run_type)
    legacy_rows = _load_legacy_reality_checker_rows(series, limit=50)
    merged = {row.id: row for row in [*rows, *legacy_rows]}
    return sorted(merged.values(), key=lambda row: (row.created_at, row.id))


def _agency_trace_status(
    invocations: list[AgencyExpertInvocation],
    legacy_layers: dict | None,
    style_lock_trace: dict | None = None,
) -> str:
    """业务函数：处理 _agency_trace_status 对应的业务流程、校验或数据转换。"""
    if invocations:
        if any(row.execution_status == "failed" or row.result_status == "failed" for row in invocations):
            return "failed"
        if any(row.result_status == "blocked" for row in invocations):
            return "blocked"
        if any(row.result_status == "warn" for row in invocations):
            return "warning"
        return "complete"
    layer_statuses = []
    for layer in (legacy_layers or {}).values():
        if not isinstance(layer, dict) or not isinstance(layer.get("agency_trace"), dict):
            continue
        trace = layer["agency_trace"]
        status = trace.get("stage_status") or trace.get("agency_trace_status")
        if trace.get("error_code") and status != "failed":
            status = "blocked"
        if status == "completed":
            status = "complete"
        if status:
            layer_statuses.append(status)
    if layer_statuses:
        if "failed" in layer_statuses:
            return "failed"
        if "blocked" in layer_statuses:
            return "blocked"
        if "warning" in layer_statuses or "warn" in layer_statuses:
            return "warning"
        if "partial" in layer_statuses:
            return "partial"
        if all(status == "complete" for status in layer_statuses):
            return "complete"
    if style_lock_trace:
        status = style_lock_trace.get("stage_status") or style_lock_trace.get("agency_trace_status")
        if style_lock_trace.get("error_code") and status != "failed":
            return "blocked"
        if status == "completed":
            return "complete"
        if status:
            return status
    if legacy_layers and any((layer or {}).get("agency_roles") for layer in legacy_layers.values()):
        return "legacy_summary"
    return "missing"


def _stage_status(rows: list[AgencyExpertInvocation]) -> str:
    """业务函数：处理 _stage_status 对应的业务流程、校验或数据转换。"""
    if not rows:
        return "pending"
    if any(row.execution_status == "failed" or row.result_status == "failed" for row in rows):
        return "failed"
    if any(row.result_status == "blocked" for row in rows):
        return "blocked"
    if any(row.result_status == "warn" for row in rows):
        return "warning"
    if all(row.execution_status == "completed" for row in rows):
        return "completed"
    return "running"


def _stage_graph(invocations: list[AgencyExpertInvocation]) -> list[dict]:
    """业务函数：处理 _stage_graph 对应的业务流程、校验或数据转换。"""
    by_stage: dict[str, list[AgencyExpertInvocation]] = {}
    for row in invocations:
        by_stage.setdefault(row.stage, []).append(row)
    graph = []
    for stage, config in STAGE_DAG.items():
        rows = by_stage.get(stage, [])
        graph.append({
            "stage": stage,
            "label": STAGE_LABELS.get(stage, stage),
            "status": _stage_status(rows),
            "reviewers": list(config.get("reviewers") or []),
            "lead": config.get("lead"),
            "qa": list(config.get("qa") or []),
            "invocation_ids": [row.id for row in rows],
        })
    return graph


def _decision_log(invocations: list[AgencyExpertInvocation]) -> list[dict]:
    """业务函数：处理 _decision_log 对应的业务流程、校验或数据转换。"""
    entries = []
    for row in invocations:
        summary = _invocation_summary(row)
        decision = summary.get("decision") or summary.get("summary")
        if not decision:
            continue
        entries.append({
            "id": row.id,
            "invocation_id": row.id,
            "stage": row.stage,
            "expert_id": row.expert_id,
            "role": row.role,
            "result_status": row.result_status,
            "decision": decision,
            "findings": summary["findings"],
            "required_changes": summary["required_changes"],
            "evidence": summary["evidence"],
            "next_action": summary["next_action"],
            "error_code": row.error_code,
            "legacy": summary["legacy"],
            "display_scope": summary["display_scope"],
        })
    return entries


def _style_lock_trace_decision_log(series: Series, existing_entries: list[dict]) -> list[dict]:
    """业务函数：处理 _style_lock_trace_decision_log 对应的业务流程、校验或数据转换。"""
    trace = _style_lock_trace(series)
    if not trace:
        return []
    status = str(trace.get("stage_status") or trace.get("agency_trace_status") or "")
    error_code = _safe_text(trace.get("error_code"), 120)
    error_message = _safe_text(
        trace.get("error_message") or trace.get("message") or trace.get("error") or "",
        500,
    )
    if not error_code and status not in {"failed", "blocked"}:
        return []
    if any(entry.get("stage") == "style_lock" and entry.get("display_scope") == "current_team" for entry in existing_entries):
        return []

    result_status = "failed" if status == "failed" else "blocked"
    recovery_action = _recovery_action(" ".join(item for item in [error_message, error_code] if item))
    lowered = f"{error_code} {error_message}".lower()
    if "timeout" in lowered or "超时" in lowered:
        decision = "风格锁专家审查超时，生产轨迹已阻断。"
    else:
        decision = "风格锁专家审查存在阻断，生产轨迹需要人工确认。"
    findings = [error_message or "风格锁专家轨迹记录了阻断状态。"]
    evidence = []
    if error_code:
        evidence.append(error_code)
    if status:
        evidence.append(f"stage_status={status}")
    return [{
        "id": f"style_lock_trace:{series.id}",
        "invocation_id": f"style_lock_trace:{series.id}",
        "stage": "style_lock",
        "expert_id": "style_lock_quality_reviewer",
        "role": "qa",
        "result_status": result_status,
        "decision": decision,
        "findings": findings,
        "required_changes": [recovery_action],
        "evidence": evidence,
        "next_action": recovery_action,
        "error_code": error_code or None,
        "legacy": False,
        "display_scope": "current_team",
    }]


def _repair_summary_for_series(series: Series, latest_run: PipelineRun | VideoProductionRun | None) -> dict:
    """业务函数：处理 _repair_summary_for_series 对应的业务流程、校验或数据转换。"""
    db = object_session(series)
    if db is None:
        return {"total": 0, "queued": 0, "running": 0, "completed": 0, "failed": 0, "manual_required": 0, "recheck_required": 0}
    query = (
        db.query(ProductionJob)
        .join(ProductionPlan, ProductionPlan.id == ProductionJob.plan_id)
        .filter(ProductionPlan.series_id == series.id)
        .filter(ProductionJob.stage.like("agency_auto_repair%"))
    )
    if isinstance(latest_run, VideoProductionRun) and latest_run.production_plan_id:
        query = query.filter(ProductionJob.plan_id == latest_run.production_plan_id)
    rows = query.all()
    summary = {"total": len(rows), "queued": 0, "running": 0, "completed": 0, "failed": 0, "manual_required": 0, "recheck_required": 0}
    for row in rows:
        if row.status in summary:
            summary[row.status] += 1
        if row.status in {"leased", "running", "retry_wait"}:
            summary["running"] += 1
        if row.status in {"failed", "blocked"}:
            summary["manual_required"] += 1
    return summary


def _empty_creative_patch_summary() -> dict:
    """业务函数：处理 _empty_creative_patch_summary 对应的业务流程、校验或数据转换。"""
    return {"total": 0, "blocking": 0, "proposed": 0, "edited": 0, "approved": 0, "applied": 0, "rejected": 0}


def _creative_patch_summary_for_series(series: Series, latest_run: PipelineRun | VideoProductionRun | None) -> dict:
    """业务函数：处理 _creative_patch_summary_for_series 对应的业务流程、校验或数据转换。"""
    db = object_session(series)
    if db is None:
        return _empty_creative_patch_summary()
    return creative_patch_summary(
        db,
        series_id=series.id,
        run_id=latest_run.id if isinstance(latest_run, VideoProductionRun) else None,
    )


def _creative_patch_items_for_series(series: Series, latest_run: PipelineRun | VideoProductionRun | None, *, limit: int = 20) -> list[dict]:
    """业务函数：处理 _creative_patch_items_for_series 对应的业务流程、校验或数据转换。"""
    db = object_session(series)
    if db is None:
        return []
    query = db.query(AgencyCreativePatch).filter(AgencyCreativePatch.series_id == series.id)
    if isinstance(latest_run, VideoProductionRun):
        query = query.filter(AgencyCreativePatch.run_id == latest_run.id)
    rows = (
        query.order_by(AgencyCreativePatch.created_at.desc(), AgencyCreativePatch.id.desc())
        .limit(limit)
        .all()
    )
    return [{
        "id": row.id,
        "stage": row.stage,
        "expert_id": row.expert_id,
        "patch_type": row.patch_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "title": row.title,
        "status": row.status,
        "priority": row.priority,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]


def build_agency_console_payload(series: Series, episodes: list[Episode],
                                 latest_run: PipelineRun | VideoProductionRun | None,
                                 generated_video: GeneratedVideo | None,
                                 run_type: str | None = None) -> dict:
    """业务函数：处理 build_agency_console_payload 对应的业务流程、校验或数据转换。"""
    if latest_run and not run_type:
        run_type = "video_production" if isinstance(latest_run, VideoProductionRun) else "pipeline"
    story_bible = series.story_bible_json or {}
    style_lock = story_bible.get("style_lock", {}) if isinstance(story_bible, dict) else {}
    team = ensure_video_agency_team(style_lock if isinstance(style_lock, dict) else {})
    current_episode = episodes[0] if episodes else None
    if latest_run and latest_run.episode_id:
        current_episode = next((ep for ep in episodes if ep.id == latest_run.episode_id), current_episode)

    steps = [
        _step(
            "input",
            "输入系列一句话",
            "completed" if series.logline else "pending",
            "style_lock",
            team,
            output_summary={"title": series.title, "logline": _safe_text(series.logline)},
            persistence=["Series.title", "Series.logline"],
        ),
        _step(
            "style_lock",
            "风格锁定",
            "completed" if bool(style_lock.get("locked")) else "pending",
            "style_lock",
            team,
            input_summary={"genre": series.genre, "target_duration": series.target_duration},
            output_summary={
                "version": style_lock.get("version", 0),
                "character_count": len(style_lock.get("characters") or []),
                "scene_count": len(style_lock.get("scenes") or []),
                "missing_asset_count": len(style_lock.get("missing_assets") or []),
            },
            persistence=["Series.story_bible_json.style_lock"],
        ),
    ]

    storyboard = current_episode.storyboard_json if current_episode else {}
    frames = storyboard.get("frames", []) if isinstance(storyboard, dict) else []
    steps.append(_step(
        "auto_plan",
        "自动分镜",
        "completed" if frames else "pending",
        "storyboard",
        team,
        input_summary={"style_lock_version": style_lock.get("version", 0), "target_duration": series.target_duration},
        output_summary={"frame_count": len(frames), "total_duration": storyboard.get("total_duration", 0) if isinstance(storyboard, dict) else 0},
        persistence=["Episode.storyboard_json"],
    ))

    layers = (latest_run.layers_json or {}) if latest_run and run_type == "pipeline" else {}
    invocations = _load_agency_invocations(series, current_episode, latest_run, run_type)
    decision_log_invocations = _load_decision_log_invocations(series, current_episode, latest_run, run_type)
    trace_status = _agency_trace_status(invocations, layers, _style_lock_trace(series))
    expert_invocations = [_invocation_summary(row) for row in invocations]
    decision_log = _decision_log(decision_log_invocations)
    decision_log.extend(_style_lock_trace_decision_log(series, decision_log))
    stage_graph = _stage_graph(invocations)
    for index, (step_id, label, phase) in LAYER_LABELS.items():
        layer = layers.get(str(index)) or {}
        step = _step(
            step_id,
            label,
            layer.get("status") or ("running" if latest_run and run_type == "pipeline" and latest_run.current_layer == index else "pending"),
            LEGACY_LAYER_PHASES.get(step_id, phase),
            team,
            input_summary=layer.get("input_summary") or {},
            output_summary=layer.get("output_summary") or {},
            persistence=["PipelineRun.layers_json"],
            error=layer.get("error") or "",
        )
        if layer.get("agency_roles"):
            step["agency_roles"] = layer["agency_roles"]
        if layer.get("quality_gates"):
            step["quality_gates"] = layer["quality_gates"]
            step["gate_results"] = _gate_results(layer["quality_gates"], step["status"])
        if layer.get("user_message"):
            step["summary"] = layer["user_message"]
        if layer.get("next_action"):
            step["next_action"] = layer["next_action"]
        steps.append(step)

    steps.append(_step(
        "episode_writeback",
        "写回剧集",
        "completed" if current_episode and current_episode.video_url else "pending",
        "compose",
        team,
        output_summary={"video_url": current_episode.video_url if current_episode else "", "status": current_episode.status if current_episode else ""},
        persistence=["Episode.video_url", "Episode.duration_seconds", "Episode.status"],
    ))
    steps.append(_step(
        "video_library_writeback",
        "写入视频资产库",
        "completed" if generated_video and generated_video.video_path else "pending",
        "compose",
        team,
        output_summary={"video_path": generated_video.video_path if generated_video else "", "status": generated_video.status if generated_video else ""},
        persistence=["GeneratedVideo"],
    ))

    readiness = _build_readiness(series, style_lock, current_episode)
    quality_report = _build_quality_report(steps, generated_video, current_episode)

    return {
        "ok": True,
        "series": {"id": series.id, "title": series.title, "logline": series.logline},
        "style_lock": {
            "locked": bool(style_lock.get("locked")),
            "version": style_lock.get("version", 0),
            "missing_assets": style_lock.get("missing_assets", []),
        },
        "agency_team": _localized_agency_team(team),
        "agency_team_status": summarize_video_agency_team(team),
        "agency_trace_status": trace_status,
        "expert_team": _expert_team(),
        "stage_graph": stage_graph,
        "expert_invocations": expert_invocations,
        "decision_log": decision_log,
        "repair_summary": _repair_summary_for_series(series, latest_run),
        "creative_patch_summary": _creative_patch_summary_for_series(series, latest_run),
        "creative_patches": _creative_patch_items_for_series(series, latest_run),
        "readiness": readiness,
        "quality_report": quality_report,
        "current_episode": {
            "id": current_episode.id,
            "episode_number": current_episode.episode_number,
            "title": current_episode.title,
            "status": current_episode.status,
        } if current_episode else None,
        "latest_run": {
            "type": run_type,
            "id": latest_run.id,
            "status": latest_run.status,
            **({"current_layer": latest_run.current_layer} if run_type == "pipeline" else {}),
            **({"current_stage": latest_run.current_stage} if run_type == "video_production" else {}),
        } if latest_run else None,
        "production_steps": steps,
        "generated_video": {
            "id": generated_video.id,
            "video_path": generated_video.video_path,
            "status": generated_video.status,
        } if generated_video else None,
    }
