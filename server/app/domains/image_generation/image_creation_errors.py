"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_creation_errors 相关业务规则、状态转换和外部系统边界。
"""

from typing import Any

from fastapi import HTTPException


def image_error(
    status_code: int,
    error_code: str,
    message: str,
    repair_action: str,
    repair_route: str | None = None,
    retryable: bool = True,
    affected_ids: list[str] | None = None,
    details: dict[str, Any] | None = None,
    rescue_actions: list[dict[str, Any]] | None = None,
) -> HTTPException:
    """业务函数：处理 image_error 对应的业务流程、校验或数据转换。"""
    payload: dict[str, Any] = {
        "ok": False,
        "error_code": error_code,
        "message": message,
        "repair_action": repair_action,
        "repair_route": repair_route,
        "retryable": retryable,
        "affected_ids": affected_ids or [],
    }
    if details:
        payload["details"] = details
    if rescue_actions:
        payload["rescue_actions"] = rescue_actions
    return HTTPException(
        status_code=status_code,
        detail=payload,
    )
