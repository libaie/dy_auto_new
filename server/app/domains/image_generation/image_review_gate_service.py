"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_review_gate_service 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from app.db.models.image_production import ImageCreationAsset, ImageCreationTask


def asset_review_gate(task: ImageCreationTask | None, asset: ImageCreationAsset) -> dict[str, Any]:
    """业务函数：处理 asset_review_gate 对应的业务流程、校验或数据转换。"""
    task_gate = ((task.request_json or {}).get("review_gate") if task else None) or {}
    asset_gate = ((asset.metadata_json or {}).get("review_gate")) or {}
    gate = {**task_gate, **asset_gate}
    if not gate:
        if asset.destination_role == "image_to_video_input":
            if asset.status == "approved":
                gate = {"required": False, "manual_required": False, "ai_required": False, "status": "approved"}
            else:
                gate = {"required": True, "manual_required": True, "ai_required": False}
        else:
            gate = {"required": False, "manual_required": False, "ai_required": False, "status": "not_required"}

    manual_required = bool(gate.get("manual_required"))
    ai_required = bool(gate.get("ai_required"))
    manual_ok = not manual_required or asset.manual_review_status == "approved"
    ai_ok = not ai_required or asset.audit_status == "approved"

    gate["required"] = bool(gate.get("required"))
    gate["manual_required"] = manual_required
    gate["ai_required"] = ai_required
    if gate.get("status") == "blocked":
        gate["status"] = "blocked"
    elif asset.status == "approved" and manual_ok and ai_ok:
        gate["status"] = "approved"
    elif asset.status in {"rejected", "blocked"}:
        gate["status"] = "blocked"
    elif gate["required"] and manual_required and not manual_ok:
        gate["status"] = "manual_review_pending"
    elif gate["required"] and ai_required and not ai_ok:
        gate["status"] = "ai_review_pending"
    elif not gate["required"]:
        gate["status"] = gate.get("status") or "not_required"

    return gate


def review_gate_passed(task: ImageCreationTask | None, asset: ImageCreationAsset) -> bool:
    """业务函数：处理 review_gate_passed 对应的业务流程、校验或数据转换。"""
    gate = asset_review_gate(task, asset)
    if gate.get("status") == "blocked":
        return False
    if asset.status != "approved":
        return False
    if not gate.get("required"):
        return True
    if gate.get("manual_required") and asset.manual_review_status != "approved":
        return False
    if gate.get("ai_required") and asset.audit_status != "approved":
        return False
    return asset.status == "approved" and gate.get("status") == "approved"


def review_gate_rescue_actions(asset: ImageCreationAsset) -> list[dict[str, Any]]:
    """业务函数：处理 review_gate_rescue_actions 对应的业务流程、校验或数据转换。"""
    return [
        {"type": "manual_review_required", "asset_id": asset.id},
        {"type": "repaint_image", "asset_id": asset.id},
    ]
