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
