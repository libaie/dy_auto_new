"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_selection_preview_hash 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _source_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """业务函数：处理 _source_identity 对应的业务流程、校验或数据转换。

    入参：payload 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    source = dict(payload.get("source") or {})
    if payload.get("source_url") and not source.get("url"):
        source["url"] = payload["source_url"]
    if payload.get("source_asset_id") and not source.get("asset_id"):
        source["asset_id"] = payload["source_asset_id"]
    asset_id = source.get("asset_id")
    return {
        "asset_id": asset_id,
        "url": None if asset_id else source.get("url"),
        "type": source.get("type"),
    }


def _reference_identities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """业务函数：处理 _reference_identities 对应的业务流程、校验或数据转换。

    入参：payload 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    items = []
    for raw in payload.get("reference_images") or []:
        item = {"url": raw} if isinstance(raw, str) else dict(raw or {})
        asset_id = item.get("asset_id")
        items.append({
            "asset_id": asset_id,
            "url": None if asset_id else item.get("url"),
            "type": item.get("type"),
            "role": item.get("role"),
        })
    return items


def selection_preview_hash_inputs(
    *,
    payload: dict[str, Any],
    mode: str,
    destination_role: str | None,
    strategy_id: str | None,
    strategy_version: int | None,
    selected_model_id: str | None,
    selected_model_config_version: int | None,
    provider_options: dict[str, Any],
) -> dict[str, Any]:
    """业务函数：处理 selection_preview_hash_inputs 对应的业务流程、校验或数据转换。

    入参：payload、mode、destination_role、strategy_id、strategy_version、selected_model_id、selected_model_config_version、provider_options 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return {
        "mode": mode,
        "destination_role": payload.get("_requested_destination_role", destination_role),
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "model_id": selected_model_id,
        "requested_model_id": payload.get("_requested_model_id", payload.get("model_id")),
        "prompt": payload.get("prompt") or "",
        "negative_prompt": payload.get("negative_prompt") or "",
        "source": _source_identity(payload),
        "source_asset_ids": payload.get("source_asset_ids") or [],
        "source_url": payload.get("source_url"),
        "source_asset_id": payload.get("source_asset_id"),
        "reference": payload.get("reference"),
        "reference_images": _reference_identities(payload),
        "reference_asset_ids": payload.get("reference_asset_ids") or [],
        "common": payload.get("common") or {},
        "common_parameters": payload.get("common_parameters") or {},
        "provider_options": provider_options,
        "count": int(payload.get("count") or 1),
        "size": payload.get("size"),
        "output_format": payload.get("output_format"),
        "response_format": payload.get("response_format"),
        "watermark": bool(payload.get("watermark")),
        "reference_count": int(payload.get("reference_count") or 0),
        "selected_model_config_version": selected_model_config_version or 1,
    }


def selection_preview_request_hash(hash_inputs: dict[str, Any]) -> str:
    """业务函数：处理 selection_preview_request_hash 对应的业务流程、校验或数据转换。

    入参：hash_inputs 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    stable = json.dumps(hash_inputs, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(stable).hexdigest()
