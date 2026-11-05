from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import uuid
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from app.config import bj_now
from app.db_models import (
    ImageCreationAsset,
    ImageCreationReviewRecord,
    ImageCreationTask,
    ImageProductionAbAttempt,
    ImageProductionAbGroup,
    ImageProductionStrategy,
    ImageSelectionPreview,
)
from app.services.image_creation_errors import image_error
from app.services.image_creation_storage import configured_public_base_url, save_output_bytes
from app.services.image_model_selection_service import resolve_image_model_selection
from app.services.image_production_cost_service import record_actual_cost_event, record_estimated_cost_event
from app.services.image_production_policy_runtime import estimate_image_cost, preview_image_capacity, preview_review_gate
from app.services.image_review_gate_service import asset_review_gate, review_gate_passed
from app.services.image_selection_preview_hash import selection_preview_hash_inputs, selection_preview_request_hash
from app.services.pixelle_stage_client import get_stage_task, submit_image_create
from app.services.runtime_model_config import (
    RuntimeModelConfigError,
    redact_runtime_model_config,
    resolve_image_model_for_capability,
)


MODE_TO_SCENE_CAPABILITY = {
    "text_to_image": ("image_generation", "text_to_image", "single"),
    "image_to_image": ("image_editing", "image_to_image", "single"),
    "multi_reference_to_image": ("image_editing", "multi_reference_to_image", "single"),
    "text_to_image_set": ("image_generation", "text_to_image_set", "image_set"),
    "image_to_image_set": ("image_editing", "image_to_image_set", "image_set"),
    "multi_reference_to_image_set": ("image_editing", "multi_reference_to_image_set", "image_set"),
}
DESTINATION_ROLES = {
    "character_anchor",
    "character_anchor_image",
    "scene_reference_image",
    "scene_reference",
    "style_reference_image",
    "style_reference",
    "storyboard_first_frame",
    "storyboard_frame",
    "image_to_video_input",
    "video_production_review_edit",
    "repaint_image",
    "fusion_image",
    "batch_story_images",
}
COMPLETE_STATUSES = {"completed", "success", "succeeded", "done"}
LOCAL_IMAGE_PATH_PREFIXES = ("/static/image-creation/", "/api/image-creation/pixelle-files/")
UNSAFE_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
}
PROTECTED_PROVIDER_OPTION_KEYS = {
    "access_token",
    "api_key",
    "api_secret",
    "authorization",
    "bearer_token",
    "client_secret",
    "model",
    "prompt",
    "image",
    "images",
    "n",
    "count",
    "input",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "source_image_url",
    "reference_images",
    "token",
    "x-api-key",
}


def _normalized_provider_option_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


NORMALIZED_PROTECTED_PROVIDER_OPTION_KEYS = {
    _normalized_provider_option_key(key) for key in PROTECTED_PROVIDER_OPTION_KEYS
}


def contains_protected_provider_option_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and _normalized_provider_option_key(key) in NORMALIZED_PROTECTED_PROVIDER_OPTION_KEYS:
                return True
            if contains_protected_provider_option_key(item):
                return True
    if isinstance(value, list):
        return any(contains_protected_provider_option_key(item) for item in value)
    return False


def normalized_request_hash(payload: dict[str, Any]) -> str:
    clean = {
        key: value
        for key, value in payload.items()
        if key not in {"idempotency_key", "cost_confirmation", "user_id"}
    }
    encoded = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_strategy_snapshot(
    db: Session,
    payload: dict[str, Any],
    mode: str,
) -> tuple[ImageProductionStrategy | None, dict[str, Any] | None, dict[str, Any]]:
    strategy_id = payload.get("strategy_id")
    if not strategy_id:
        return None, None, {}

    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "Image production strategy was not found.",
            "Choose another strategy.",
            retryable=False,
            affected_ids=[str(strategy_id)],
        )
    if strategy.status != "active":
        raise image_error(
            409,
            "IMAGE_STRATEGY_ARCHIVED",
            "Strategy is not active.",
            "Choose an active strategy.",
            retryable=False,
            affected_ids=[strategy.id],
        )
    if payload.get("strategy_version") is not None and int(payload["strategy_version"]) != strategy.version:
        raise image_error(
            409,
            "IMAGE_STRATEGY_VERSION_CONFLICT",
            "Strategy version is stale.",
            "Reload strategy preview.",
            retryable=False,
            affected_ids=[strategy.id],
        )
    if mode not in (strategy.supported_modes_json or []):
        raise image_error(
            422,
            "IMAGE_STRATEGY_MODE_UNSUPPORTED",
            "Strategy does not support this image mode.",
            "Choose another strategy or mode.",
            retryable=False,
            affected_ids=[strategy.id],
        )

    snapshot = {
        "id": strategy.id,
        "slug": strategy.slug,
        "name": strategy.name,
        "description": strategy.description or "",
        "destination_role": strategy.destination_role,
        "supported_modes": strategy.supported_modes_json or [],
        "default_model_id": strategy.default_model_id,
        "fallback_model_ids": strategy.fallback_model_ids_json or [],
        "common_parameters": strategy.common_parameters_json or {},
        "provider_options": strategy.provider_options_json or {},
        "review_policy_version_id": strategy.review_policy_version_id,
        "cost_policy_version_id": strategy.cost_policy_version_id,
        "capacity_policy_version_id": strategy.capacity_policy_version_id,
        "ab_test_policy_version_id": strategy.ab_test_policy_version_id,
        "version": strategy.version,
    }
    explanation = {
        "requested_mode": mode,
        "destination_role": payload.get("destination_role") or strategy.destination_role,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "selected_model_id": payload.get("model_id") or strategy.default_model_id,
        "selected_reason": "strategy_default_model"
        if strategy.default_model_id and not payload.get("model_id")
        else "manual_or_existing_resolution",
        "rejected_candidates": [],
    }
    return strategy, snapshot, explanation


def _selection_explanation_from_preview(
    selection_preview: ImageSelectionPreview | None,
    fallback: dict[str, Any] | None,
) -> dict[str, Any] | None:
    explanation = dict(fallback or {})
    if not selection_preview or not isinstance(selection_preview.response_json, dict):
        return explanation or None

    preview_explanation = selection_preview.response_json.get("selection_explanation")
    if isinstance(preview_explanation, dict):
        explanation.update(preview_explanation)

    for key in ("fallback_candidates", "warnings", "rescue_actions"):
        if key in selection_preview.response_json:
            explanation[key] = selection_preview.response_json.get(key) or []

    return explanation or None


def _selection_explanation_from_resolution(
    db: Session,
    *,
    fallback: dict[str, Any] | None,
    scene_key: str,
    capability_key: str,
    requested_model_id: str | None,
    strategy: ImageProductionStrategy | None,
) -> dict[str, Any] | None:
    explanation = dict(fallback or {})
    selection = resolve_image_model_selection(
        db,
        scene_key=scene_key,
        capability_key=capability_key,
        requested_model_id=requested_model_id,
        strategy=strategy,
    )
    selected_model = selection.get("selected_model") or {}
    explanation.update({
        "candidate_count": selection.get("candidate_count", 0),
        "rejected_candidates": selection.get("rejected_candidates") or [],
        "fallback_candidates": selection.get("fallback_candidates") or [],
        "warnings": selection.get("warnings") or [],
        "rescue_actions": selection.get("rescue_actions") or [],
    })
    if selected_model.get("model_id"):
        explanation["selected_model_id"] = selected_model["model_id"]
    if selection.get("selected_reason"):
        explanation["selected_reason"] = selection["selected_reason"]
    return explanation or None


def _apply_strategy_defaults(payload: dict[str, Any], strategy: ImageProductionStrategy | None) -> None:
    if not strategy:
        return
    if not payload.get("model_id") and strategy.default_model_id:
        payload["model_id"] = strategy.default_model_id
    if not payload.get("destination_role"):
        payload["destination_role"] = strategy.destination_role

    provider_options = dict(strategy.provider_options_json or {})
    provider_options.update(payload.get("provider_options") or {})
    payload["provider_options"] = provider_options

    for key, value in (strategy.common_parameters_json or {}).items():
        if payload.get(key) in (None, ""):
            payload[key] = value


def _preview_drift_error(preview: ImageSelectionPreview):
    return image_error(
        409,
        "IMAGE_SELECTION_PREVIEW_DRIFT",
        "Selection preview no longer matches this request.",
        "Run selection preview again.",
        retryable=False,
        affected_ids=[preview.id],
    )


def _get_selection_preview(db: Session, payload: dict[str, Any]) -> ImageSelectionPreview | None:
    preview_id = payload.get("selection_preview_id")
    if not preview_id:
        return None

    preview = db.query(ImageSelectionPreview).filter(ImageSelectionPreview.id == preview_id).first()
    if not preview:
        raise image_error(
            404,
            "IMAGE_SELECTION_PREVIEW_NOT_FOUND",
            "Selection preview was not found.",
            "Run selection preview again.",
            retryable=False,
            affected_ids=[str(preview_id)],
        )
    return preview


def _validate_selection_preview_scope(payload: dict[str, Any], preview: ImageSelectionPreview | None) -> None:
    if not preview:
        return
    if not payload.get("selection_preview_request_hash") or preview.request_hash != payload["selection_preview_request_hash"]:
        raise _preview_drift_error(preview)
    if preview.expires_at < bj_now():
        raise image_error(
            409,
            "IMAGE_SELECTION_PREVIEW_EXPIRED",
            "Selection preview expired.",
            "Run selection preview again.",
            retryable=False,
            affected_ids=[preview.id],
        )
    if preview.user_id and preview.user_id != payload.get("user_id"):
        raise image_error(
            403,
            "IMAGE_SELECTION_PREVIEW_FORBIDDEN",
            "Selection preview belongs to another user.",
            "Run selection preview again.",
            retryable=False,
            affected_ids=[preview.id],
        )
    if preview.mode != payload.get("mode"):
        raise _preview_drift_error(preview)
    if preview.strategy_id and preview.strategy_id != payload.get("strategy_id"):
        raise _preview_drift_error(preview)
    if preview.strategy_version is not None and (
        payload.get("strategy_version") is None
        or int(preview.strategy_version) != int(payload["strategy_version"])
    ):
        raise _preview_drift_error(preview)


def _validate_selection_preview_resolution(
    payload: dict[str, Any],
    preview: ImageSelectionPreview | None,
    *,
    requested_model_id: str | None,
    requested_destination_role: str | None,
    hash_payload: dict[str, Any],
    strategy: ImageProductionStrategy | None,
    model_config: dict[str, Any],
    provider_options: dict[str, Any],
) -> None:
    if not preview:
        return
    if preview.strategy_id != (strategy.id if strategy else None):
        raise _preview_drift_error(preview)
    if preview.strategy_version != (strategy.version if strategy else None):
        raise _preview_drift_error(preview)
    if preview.selected_model_id != model_config.get("model_id"):
        raise _preview_drift_error(preview)

    current_hash = selection_preview_request_hash(selection_preview_hash_inputs(
        payload={
            **hash_payload,
            "_requested_model_id": requested_model_id,
            "_requested_destination_role": requested_destination_role,
        },
        mode=payload["mode"],
        destination_role=payload.get("destination_role"),
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        selected_model_id=model_config.get("model_id"),
        selected_model_config_version=model_config.get("config_version", 1),
        provider_options=provider_options,
    ))
    if current_hash != preview.request_hash:
        raise _preview_drift_error(preview)


def _source(payload: dict[str, Any]) -> dict[str, Any]:
    source = dict(payload.get("source") or {})
    if payload.get("source_url") and not source.get("url"):
        source["url"] = payload["source_url"]
    if payload.get("source_asset_id") and not source.get("asset_id"):
        source["asset_id"] = payload["source_asset_id"]
    return source


def _is_usable_public_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith(("http://", "https://", "/static/", "/api/image-creation/pixelle-files/"))


def _is_local_image_path(value: str | None) -> bool:
    clean = str(value or "").strip()
    return any(clean.startswith(prefix) for prefix in LOCAL_IMAGE_PATH_PREFIXES)


def _is_internal_image_url(value: str | None) -> bool:
    clean = str(value or "").strip()
    if _is_local_image_path(clean):
        return True
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"}:
        return False
    base = urlparse(configured_public_base_url())
    return parsed.scheme == base.scheme and parsed.netloc == base.netloc and _is_local_image_path(parsed.path)


def _host_is_unsafe(hostname: str | None) -> bool:
    host = str(hostname or "").strip().strip("[]").lower().rstrip(".")
    if not host:
        return True
    if host in UNSAFE_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False
        return any(_ip_is_unsafe(result[4][0]) for result in resolved)
    return _ip_is_unsafe(str(ip))


def _ip_is_unsafe(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(str(value).strip().strip("[]"))
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_public_image_url(value: str | None, field_name: str) -> None:
    clean = str(value or "").strip()
    if not clean:
        return
    if _is_internal_image_url(clean):
        return
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise image_error(
            400,
            "IMAGE_URL_INVALID",
            f"{field_name} must be an http(s) image URL or a managed image asset URL.",
            "Use an uploaded/approved asset or a public image URL.",
            retryable=False,
        )
    if _host_is_unsafe(parsed.hostname):
        raise image_error(
            400,
            "IMAGE_URL_UNSAFE",
            f"{field_name} points to a private or unsupported host.",
            "Use an uploaded/approved asset or a public image URL.",
            retryable=False,
        )


def _usable_asset_url(asset: ImageCreationAsset) -> str | None:
    for value in (asset.url, asset.local_path, asset.storage_path):
        if _is_usable_public_url(value):
            return value
    return None


def _asset_matches_payload_user(asset: ImageCreationAsset, payload: dict[str, Any]) -> bool:
    if not asset.user_id:
        return True
    return payload.get("user_id") == asset.user_id


def _resolve_source_asset(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    source = _source(payload)
    asset_id = source.get("asset_id")
    if not asset_id:
        return source

    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset or not _asset_matches_payload_user(asset, payload):
        raise image_error(
            404,
            "SOURCE_ASSET_NOT_FOUND",
            "Source image asset was not found.",
            "Choose another source asset or upload a source image.",
            retryable=False,
            affected_ids=[str(asset_id)] if not asset else [],
        )
    resolved_url = _usable_asset_url(asset)
    if not resolved_url:
        raise image_error(
            400,
            "SOURCE_ASSET_URL_REQUIRED",
            "Source image asset does not have a usable public URL.",
            "Use an asset with a public URL or upload the source image again.",
            retryable=False,
            affected_ids=[asset.id],
        )

    source["asset_id"] = asset.id
    source["url"] = resolved_url
    source.setdefault("type", "asset")
    payload["source"] = source
    payload["source_asset_id"] = asset.id
    payload["source_url"] = resolved_url
    return source


def _resolve_reference_images(db: Session, payload: dict[str, Any]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for raw in payload.get("reference_images") or []:
        item = {"url": raw} if isinstance(raw, str) else dict(raw or {})
        asset_id = item.get("asset_id")
        if asset_id:
            asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
            if not asset or not _asset_matches_payload_user(asset, payload):
                raise image_error(
                    404,
                    "REFERENCE_ASSET_NOT_FOUND",
                    "Reference image asset was not found.",
                    "Choose another reference asset or upload a reference image.",
                    retryable=False,
                    affected_ids=[str(asset_id)] if not asset else [],
                )
            resolved_url = _usable_asset_url(asset)
            if not resolved_url:
                raise image_error(
                    400,
                    "REFERENCE_ASSET_URL_REQUIRED",
                    "Reference image asset does not have a usable public URL.",
                    "Use an asset with a public URL or upload the reference image again.",
                    retryable=False,
                    affected_ids=[asset.id],
                )
            item["asset_id"] = asset.id
            item["url"] = resolved_url
            item.setdefault("type", "asset")
        _validate_public_image_url(item.get("url"), "reference image")
        resolved.append(item)
    payload["reference_images"] = resolved
    return resolved


def _validate_payload(payload: dict[str, Any]) -> tuple[str, str, str]:
    mode = payload.get("mode")
    if mode not in MODE_TO_SCENE_CAPABILITY:
        raise image_error(
            400,
            "IMAGE_MODE_UNSUPPORTED",
            f"Unsupported image mode: {mode}",
            "Choose a supported image mode.",
            retryable=False,
        )
    if not str(payload.get("prompt") or "").strip():
        raise image_error(400, "IMAGE_PROMPT_REQUIRED", "Prompt is required.", "Enter a prompt.")
    destination_role = payload.get("destination_role")
    if destination_role and destination_role not in DESTINATION_ROLES:
        raise image_error(
            400,
            "DOWNSTREAM_DESTINATION_INVALID",
            "Unsupported destination role.",
            "Pick a supported destination or clear it.",
            retryable=False,
        )
    return MODE_TO_SCENE_CAPABILITY[mode]


def _image_reference_count(payload: dict[str, Any]) -> int:
    source = _source(payload)
    count = len(payload.get("reference_images") or [])
    if source.get("url") or source.get("asset_id"):
        count += 1
    return count


def _limit_int(limits: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(limits.get(key) or default)
    except (TypeError, ValueError):
        return default


def _validate_provider_limits(payload: dict[str, Any], model_config: dict[str, Any]) -> None:
    mode = payload["mode"]
    source = _source(payload)
    references = payload.get("reference_images") or []
    output_count = int(payload.get("count") or 1)
    limits = ((model_config.get("config") or {}).get("limits") or {})
    max_reference_images = _limit_int(limits, "max_reference_images", 14)
    max_output_images = _limit_int(limits, "max_output_images", 15)
    max_reference_plus_output = _limit_int(limits, "max_reference_plus_output_images", 15)

    if output_count < 1 or output_count > max_output_images:
        raise image_error(
            400,
            "IMAGE_OUTPUT_COUNT_INVALID",
            "Requested image count exceeds model limits.",
            "Lower the output count or choose another model.",
        )
    if output_count > 1 and not mode.endswith("_set"):
        raise image_error(
            400,
            "IMAGE_OUTPUT_MODE_INVALID",
            "Multiple outputs require an image-set mode.",
            "Switch to an image-set mode or reduce count to 1.",
        )
    if mode in {"image_to_image", "image_to_image_set"} and not (source.get("url") or source.get("asset_id")):
        raise image_error(
            400,
            "SOURCE_IMAGE_REQUIRED",
            "Image-to-image mode requires a source image.",
            "Upload or select a source image.",
        )
    if mode.startswith("multi_reference") and len(references) < 2:
        raise image_error(
            400,
            "REFERENCE_IMAGES_REQUIRED",
            "Multi-reference mode requires at least two reference images.",
            "Add more reference images.",
        )
    reference_count = _image_reference_count(payload)
    if reference_count > max_reference_images or reference_count + output_count > max_reference_plus_output:
        raise image_error(
            400,
            "REFERENCE_LIMIT_EXCEEDED",
            "Reference images and output count exceed model limits.",
            "Remove references or reduce output count.",
        )


def _validate_provider_options(provider_options: dict[str, Any], model_config: dict[str, Any]) -> dict[str, Any]:
    schema = ((model_config.get("config") or {}).get("provider_options_schema") or {})
    if not isinstance(schema, dict):
        schema = {}
    unknown = set(provider_options) - set(schema)
    if unknown or contains_protected_provider_option_key(provider_options):
        raise image_error(
            400,
            "IMAGE_PROVIDER_OPTIONS_INVALID",
            "Provider options contain unsupported fields.",
            "Use only the options exposed by the selected model configuration.",
            retryable=False,
        )

    for key, value in provider_options.items():
        spec = schema.get(key) or {}
        option_type = spec.get("type")
        if option_type == "boolean" and not isinstance(value, bool):
            raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} must be boolean.", "Fix provider options.", retryable=False)
        if option_type == "select" and value not in set(spec.get("options") or []):
            raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} is not an allowed option.", "Fix provider options.", retryable=False)
        if option_type == "number":
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} must be numeric.", "Fix provider options.", retryable=False) from exc
            if spec.get("min") is not None and numeric < float(spec["min"]):
                raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} is below the allowed minimum.", "Fix provider options.", retryable=False)
            if spec.get("max") is not None and numeric > float(spec["max"]):
                raise image_error(400, "IMAGE_PROVIDER_OPTIONS_INVALID", f"{key} exceeds the allowed maximum.", "Fix provider options.", retryable=False)
    return provider_options


def _capacity_block_error(capacity: dict[str, Any], affected_ids: list[str] | None = None):
    return image_error(
        409,
        "IMAGE_CAPACITY_BLOCKED",
        "Image generation capacity is currently full.",
        "Wait for active image tasks to finish or enable queueing for this strategy.",
        retryable=True,
        affected_ids=affected_ids or [],
        details={"capacity": capacity},
        rescue_actions=[
            {"type": "wait_for_capacity", "label": "Wait for capacity"},
            {"type": "reduce_queue", "label": "Reduce queue"},
        ],
    )


def _request_json_with_trust_fields(
    payload: dict[str, Any],
    *,
    capacity: dict[str, Any],
    review_gate: dict[str, Any],
    estimated_cost: dict[str, Any],
) -> dict[str, Any]:
    request_json = dict(payload)
    request_json["capacity"] = capacity
    request_json["review_gate"] = review_gate
    request_json["time_estimate"] = estimated_cost.get("time_estimate") or {}
    return request_json


def _pixelle_payload_for_task(task: ImageCreationTask) -> dict[str, Any]:
    return {
        "external_task_id": task.id,
        "mode": task.mode,
        "capability_key": task.capability_key,
        "output_mode": task.output_mode,
        "prompt": task.prompt,
        "negative_prompt": task.negative_prompt or "",
        "source_image_url": task.source_url or "",
        "reference_images": task.reference_images_json or [],
        "count": task.count,
        "size": task.size or "",
        "output_format": task.output_format or "",
        "response_format": task.response_format or "",
        "provider_options": task.provider_options_json or {},
        "context": _task_context(task),
    }


_SECRET_ERROR_PATTERNS = [
    re.compile(r"ark-[0-9A-Za-z-]+"),
    re.compile(
        r"['\"]?(?:authorization|access[_-]?token|client[_-]?secret|api\s*key|api[_-]?key|token)['\"]?"
        r"\s*[:=]\s*['\"]?(?:Bearer\s+)?[^'\"\s,}]+['\"]?",
        re.IGNORECASE,
    ),
    re.compile(r"\bBearer\s+[^'\"\s,}]+", re.IGNORECASE),
]


def _redact_provider_error(value: object) -> str:
    message = str(value or "Provider request failed.")
    for pattern in _SECRET_ERROR_PATTERNS:
        message = pattern.sub("[redacted]", message)
    return message[:500]


def _redact_provider_status_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in {"authorization", "access_token", "api_key", "api_secret", "bearer_token", "client_secret", "password", "private_key", "refresh_token", "secret", "token"}:
                continue
            if isinstance(item, str) and (
                key_text in {"error", "message", "detail", "reason"}
                or any(pattern.search(item) for pattern in _SECRET_ERROR_PATTERNS)
            ):
                redacted[key] = _redact_provider_error(item)
            else:
                redacted[key] = _redact_provider_status_payload(item)
        return redacted
    if isinstance(value, list):
        return [_redact_provider_status_payload(item) for item in value]
    return value


def _fallback_trace(
    db: Session,
    *,
    strategy: ImageProductionStrategy | None,
    scene_key: str,
    capability_key: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    fallback_candidates: list[dict[str, Any]] = []
    if strategy:
        selection = resolve_image_model_selection(
            db,
            scene_key=scene_key,
            capability_key=capability_key,
            requested_model_id=None,
            strategy=strategy,
        )
        fallback_candidates = selection.get("fallback_candidates") or []
    return {
        "error_code": error_code,
        "message": message,
        "fallback_candidates": fallback_candidates,
        "rescue_actions": [
            {
                "type": "retry_with_fallback_model",
                "label": "Retry with fallback model",
                "model_id": candidate["model_id"],
            }
            for candidate in fallback_candidates
        ],
    }


def _progress_value(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(float(value), 1.0))
    if isinstance(value, dict):
        for key in ("percentage", "percent"):
            if value.get(key) is not None:
                try:
                    numeric = float(value[key])
                except (TypeError, ValueError):
                    break
                return max(0.0, min(numeric / 100 if numeric > 1 else numeric, 1.0))
        current = value.get("current") or value.get("completed")
        total = value.get("total")
        try:
            if total:
                return max(0.0, min(float(current or 0) / float(total), 1.0))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    try:
        return max(0.0, min(float(fallback or 0.0), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _pixelle_file_path(value: str | None) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    marker = "/api/files/"
    if clean.startswith(marker):
        return unquote(clean[len(marker):].lstrip("/"))
    if clean.startswith("api/files/"):
        return unquote(clean[len("api/files/"):].lstrip("/"))
    if clean.startswith("output/"):
        return clean
    return None


def _dy_auto_pixelle_file_url(file_path: str) -> str:
    encoded = quote(file_path.strip("/"), safe="")
    return f"{configured_public_base_url().rstrip('/')}/api/image-creation/pixelle-files/{encoded}"


def _normalized_stage_asset_url(item: dict[str, Any]) -> str:
    raw_url = str(item.get("url") or "").strip()
    file_path = _pixelle_file_path(raw_url) or _pixelle_file_path(item.get("local_path")) or _pixelle_file_path(item.get("storage_path"))
    if file_path:
        return _dy_auto_pixelle_file_url(file_path)
    return raw_url


def _requires_external_copy(value: str | None) -> bool:
    clean = str(value or "").strip()
    if not clean or _is_internal_image_url(clean):
        return False
    parsed = urlparse(clean)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ab_hash_cost_confirmed(db: Session, payload: dict[str, Any]) -> bool:
    group_id = payload.get("ab_test_group_id")
    preview_hash = payload.get("selection_preview_request_hash")
    strategy_id = payload.get("strategy_id")
    strategy_version = payload.get("strategy_version")
    if not group_id or not preview_hash or not strategy_id or strategy_version is None:
        return False
    group = db.query(ImageProductionAbGroup).filter_by(id=group_id).first()
    if not group:
        return False
    payload_user_id = payload.get("user_id")
    if group.user_id != payload_user_id:
        return False
    current_request_hash = normalized_request_hash(payload)
    attempts = (
        db.query(ImageProductionAbAttempt)
        .filter(ImageProductionAbAttempt.group_id == group.id)
        .filter(ImageProductionAbAttempt.strategy_id == strategy_id)
        .all()
    )
    for attempt in attempts:
        try:
            version_matches = int(attempt.strategy_version) == int(strategy_version)
        except (TypeError, ValueError):
            version_matches = attempt.strategy_version == strategy_version
        if not version_matches:
            continue
        metrics = attempt.metrics_snapshot_json or {}
        if (
            metrics.get("selection_preview_request_hash") == preview_hash
            and metrics.get("ab_attempt_request_hash") == current_request_hash
            and metrics.get("ab_attempt_idempotency_key") == payload.get("idempotency_key")
        ):
            return True
    return False


def _task_idempotency_conflict(existing: ImageCreationTask, *, expose_existing_id: bool) -> HTTPException:
    return image_error(
        409,
        "IMAGE_TASK_CONFLICT",
        "Idempotency key was reused for a different image request.",
        "Use a new idempotency key or restore the original request.",
        retryable=False,
        affected_ids=[existing.id] if expose_existing_id else [],
    )


def _task_matches_payload_user(existing: ImageCreationTask, payload: dict[str, Any]) -> bool:
    return existing.user_id == payload.get("user_id")


def _recover_task_idempotency_integrity_error(
    db: Session,
    *,
    idempotency_key: str | None,
    payload: dict[str, Any],
    request_hash: str,
    exc: IntegrityError,
) -> ImageCreationTask:
    db.rollback()
    if idempotency_key:
        existing = db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == idempotency_key).first()
        if existing:
            if not _task_matches_payload_user(existing, payload):
                raise _task_idempotency_conflict(existing, expose_existing_id=False) from exc
            if existing.request_hash == request_hash:
                return existing
            raise _task_idempotency_conflict(existing, expose_existing_id=True) from exc
    raise exc


async def _copy_external_image(value: str) -> dict[str, Any]:
    _validate_public_image_url(value, "generated image")
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5), trust_env=False, follow_redirects=False) as client:
        response = await client.get(value)
    response.raise_for_status()
    return save_output_bytes(
        response.content,
        configured_public_base_url(),
        response.headers.get("content-type"),
        source_url=value,
    )


async def create_image_task(db: Session, payload: dict[str, Any]) -> ImageCreationTask:
    payload = dict(payload)
    requested_model_id = payload.get("model_id")
    requested_destination_role = payload.get("destination_role")
    hash_payload = dict(payload)
    scene_key, capability_key, output_mode = _validate_payload(payload)
    strategy, strategy_snapshot, selection_explanation = _resolve_strategy_snapshot(db, payload, payload["mode"])
    _apply_strategy_defaults(payload, strategy)
    selection_preview = _get_selection_preview(db, payload)
    source = _resolve_source_asset(db, payload)
    _validate_public_image_url(source.get("url"), "source image")
    _resolve_reference_images(db, payload)
    request_hash = normalized_request_hash(payload)
    idempotency_key = payload.get("idempotency_key")
    if idempotency_key:
        existing = db.query(ImageCreationTask).filter(ImageCreationTask.idempotency_key == idempotency_key).first()
        if existing:
            if not _task_matches_payload_user(existing, payload):
                raise _task_idempotency_conflict(existing, expose_existing_id=False)
            if existing.request_hash != request_hash:
                raise _task_idempotency_conflict(existing, expose_existing_id=True)
            return existing

    _validate_selection_preview_scope(payload, selection_preview)

    try:
        model_config = resolve_image_model_for_capability(db, scene_key, capability_key, payload.get("model_id"))
    except RuntimeModelConfigError as exc:
        raise image_error(
            400,
            "IMAGE_CAPABILITY_UNSUPPORTED",
            str(exc),
            "Choose a compatible model or change mode.",
            "/ai-config",
            retryable=False,
        ) from exc
    if selection_preview:
        selection_explanation = _selection_explanation_from_preview(selection_preview, selection_explanation)
    else:
        selection_explanation = _selection_explanation_from_resolution(
            db,
            fallback=selection_explanation,
            scene_key=scene_key,
            capability_key=capability_key,
            requested_model_id=requested_model_id,
            strategy=strategy,
        )
    if selection_explanation is not None:
        selection_explanation["selected_model_id"] = model_config.get("model_id")
        selection_explanation["resolved_scene_key"] = scene_key
        selection_explanation["resolved_capability_key"] = capability_key
    _validate_provider_limits(payload, model_config)

    provider_options = dict(payload.get("provider_options") or {})
    if payload.get("watermark") is not None:
        provider_options.setdefault("watermark", payload.get("watermark"))
    provider_options = _validate_provider_options(provider_options, model_config)
    _validate_selection_preview_resolution(
        payload,
        selection_preview,
        requested_model_id=requested_model_id,
        requested_destination_role=requested_destination_role,
        hash_payload=hash_payload,
        strategy=strategy,
        model_config=model_config,
        provider_options=provider_options,
    )

    estimated_cost = estimate_image_cost(db, payload=payload, strategy=strategy, model_config=model_config)
    if estimated_cost.get("requires_confirmation") and not payload.get("cost_confirmation"):
        raise image_error(
            409,
            "IMAGE_COST_CONFIRMATION_REQUIRED",
            "Image request cost requires confirmation.",
            "Confirm the task cost or reduce count/options.",
            retryable=False,
            details={"cost_estimate": estimated_cost},
        )
    ab_hash_confirmed = _ab_hash_cost_confirmed(db, payload)
    if estimated_cost.get("requires_confirmation") and payload.get("cost_confirmation") and not selection_preview and not ab_hash_confirmed:
        raise image_error(
            409,
            "IMAGE_COST_CONFIRMATION_PREVIEW_REQUIRED",
            "Image request cost confirmation requires a fresh selection preview.",
            "Run selection preview again and confirm the displayed cost.",
            retryable=False,
            details={"cost_estimate": estimated_cost},
        )

    capacity = preview_image_capacity(db, strategy, model_config.get("model_id"))
    review_gate = preview_review_gate(db, strategy, payload.get("destination_role"))
    if capacity.get("admission_action") == "block":
        raise _capacity_block_error(capacity)

    task = ImageCreationTask(
        user_id=payload.get("user_id"),
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        mode=payload["mode"],
        output_mode=output_mode,
        capability_key=capability_key,
        status="admission_pending",
        series_id=payload.get("series_id"),
        episode_id=payload.get("episode_id"),
        prompt=str(payload["prompt"]).strip(),
        negative_prompt=payload.get("negative_prompt") or "",
        source_type=source.get("type"),
        source="asset" if source.get("asset_id") else ("url" if source.get("url") else None),
        source_url=source.get("url"),
        source_asset_id=source.get("asset_id"),
        reference_images_json=payload.get("reference_images") or [],
        destination_role=payload.get("destination_role"),
        destination_context_json=payload.get("destination_context") or {},
        size=payload.get("size"),
        count=int(payload.get("count") or 1),
        output_format=payload.get("output_format"),
        response_format=payload.get("response_format"),
        watermark=payload.get("watermark"),
        provider_options_json=provider_options,
        estimated_cost_json=estimated_cost,
        cost_status="confirmed" if payload.get("cost_confirmation") else "estimated",
        requires_cost_confirmation=bool(estimated_cost.get("requires_confirmation")),
        review_policy=review_gate.get("status"),
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        strategy_snapshot_json=strategy_snapshot,
        ab_test_group_id=payload.get("ab_test_group_id"),
        selection_explanation_json=selection_explanation,
        selection_preview_id=payload.get("selection_preview_id"),
        selection_preview_request_hash=payload.get("selection_preview_request_hash"),
        fallback_trace_json={},
        storage_status="pending",
        model_scene_key=scene_key,
        model_scene=scene_key,
        provider=model_config.get("provider"),
        model_id=model_config.get("model_id"),
        external_task_id=None,
        target_count=int(payload.get("count") or 1),
        model_trace_json=redact_runtime_model_config(model_config),
        request_json=_request_json_with_trust_fields(
            payload,
            capacity=capacity,
            review_gate=review_gate,
            estimated_cost=estimated_cost,
        ),
    )
    db.add(task)
    try:
        db.flush()
    except IntegrityError as exc:
        return _recover_task_idempotency_integrity_error(
            db,
            idempotency_key=idempotency_key,
            payload=payload,
            request_hash=request_hash,
            exc=exc,
        )
    task.external_task_id = task.id

    capacity = preview_image_capacity(db, strategy, model_config.get("model_id"))
    review_gate = preview_review_gate(db, strategy, payload.get("destination_role"))
    if capacity.get("admission_action") == "block":
        db.rollback()
        raise _capacity_block_error(capacity)
    if capacity.get("admission_action") == "queue":
        task.status = "queued"
        task.queue_job_id = str(uuid.uuid4())
        task.capacity_lease_id = None
    else:
        task.status = "queued"
        task.queue_job_id = None
        task.capacity_lease_id = str(uuid.uuid4())

    task.review_policy = review_gate.get("status")
    task.request_json = _request_json_with_trust_fields(
        payload,
        capacity=capacity,
        review_gate=review_gate,
        estimated_cost=estimated_cost,
    )
    pixelle_payload = _pixelle_payload_for_task(task)
    task.pixelle_payload_json = {**pixelle_payload, "model_config": redact_runtime_model_config(model_config)}

    try:
        db.commit()
    except IntegrityError as exc:
        return _recover_task_idempotency_integrity_error(
            db,
            idempotency_key=idempotency_key,
            payload=payload,
            request_hash=request_hash,
            exc=exc,
        )

    db.refresh(task)
    record_estimated_cost_event(db, task)
    db.refresh(task)
    if task.queue_job_id and not task.capacity_lease_id:
        return task

    return await _submit_claimed_image_task(
        db, task, task.capacity_lease_id, model_config, pixelle_payload, strategy, scene_key, capability_key,
        error_code="PIXELLE_IMAGE_SUBMIT_FAILED",
    )


async def dispatch_queued_image_task(db: Session, task_id: str) -> ImageCreationTask:
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    if not task:
        raise image_error(
            404,
            "IMAGE_TASK_NOT_FOUND",
            "Image creation task not found.",
            "Reload the task list.",
            retryable=False,
            affected_ids=[task_id],
        )
    if task.status != "queued" or task.pixelle_task_id or task.provider_task_id or task.capacity_lease_id:
        raise image_error(
            409,
            "IMAGE_TASK_NOT_DISPATCHABLE",
            "Only queued image tasks without a Pixelle task can be dispatched.",
            "Choose a queued task that has not been submitted.",
            retryable=False,
            affected_ids=[task.id],
        )

    strategy = (
        db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == task.strategy_id).first()
        if task.strategy_id else None
    )
    scene_key = task.model_scene_key or task.model_scene or MODE_TO_SCENE_CAPABILITY.get(task.mode, ("image_generation", "", ""))[0]
    capability_key = task.capability_key or MODE_TO_SCENE_CAPABILITY.get(task.mode, ("", "text_to_image", ""))[1]
    try:
        model_config = resolve_image_model_for_capability(db, scene_key, capability_key, task.model_id)
    except RuntimeModelConfigError as exc:
        raise image_error(
            400,
            "IMAGE_CAPABILITY_UNSUPPORTED",
            str(exc),
            "Choose a compatible model or change mode.",
            "/ai-config",
            retryable=False,
            affected_ids=[task.id],
        ) from exc

    saved_payload = dict(task.pixelle_payload_json or {})
    saved_payload.pop("model_config", None)
    if not saved_payload:
        raise image_error(
            409,
            "IMAGE_QUEUE_PAYLOAD_MISSING",
            "Queued image task is missing its saved Pixelle payload.",
            "Create a new image task.",
            retryable=False,
            affected_ids=[task.id],
        )

    capacity = preview_image_capacity(db, strategy, task.model_id)
    review_gate = preview_review_gate(db, strategy, task.destination_role)
    estimated_cost = task.estimated_cost_json or {}
    if capacity.get("admission_action") != "submit_now":
        task.request_json = _request_json_with_trust_fields(
            task.request_json or {},
            capacity=capacity,
            review_gate=review_gate,
            estimated_cost=estimated_cost,
        )
        task.review_policy = review_gate.get("status")
        db.commit()
        db.refresh(task)
        return task

    claim_id = str(uuid.uuid4())
    external_task_id = task.external_task_id or saved_payload.get("external_task_id") or task.id
    saved_payload["external_task_id"] = external_task_id
    updated = db.query(ImageCreationTask).filter(
        ImageCreationTask.id == task.id,
        ImageCreationTask.status == "queued",
        ImageCreationTask.capacity_lease_id.is_(None),
        ImageCreationTask.pixelle_task_id.is_(None),
        ImageCreationTask.provider_task_id.is_(None),
    ).update({
        "capacity_lease_id": claim_id,
        "queue_job_id": None,
        "external_task_id": external_task_id,
        "pixelle_payload_json": {**saved_payload, "model_config": redact_runtime_model_config(model_config)},
        "request_json": _request_json_with_trust_fields(
            task.request_json or {}, capacity=capacity, review_gate=review_gate, estimated_cost=estimated_cost,
        ),
        "review_policy": review_gate.get("status"),
    }, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise _image_submission_conflict(task_id)
    # Commit the compare-and-set before awaiting the external provider.
    db.commit()
    db.refresh(task)
    return await _submit_claimed_image_task(
        db, task, claim_id, model_config, saved_payload, strategy, scene_key, capability_key,
        error_code="PIXELLE_IMAGE_DISPATCH_FAILED",
    )


def _image_submission_conflict(task_id: str):
    return image_error(
        409, "IMAGE_TASK_NOT_DISPATCHABLE",
        "Image task submission is already claimed or its state has changed.",
        "Reload the task and reconcile its existing submission before retrying.",
        retryable=False, affected_ids=[task_id],
    )


def _write_image_submission_result(db, task_id, claim_id, values):
    updated = db.query(ImageCreationTask).filter(
        ImageCreationTask.id == task_id,
        ImageCreationTask.status == "queued",
        ImageCreationTask.capacity_lease_id == claim_id,
        ImageCreationTask.pixelle_task_id.is_(None),
        ImageCreationTask.provider_task_id.is_(None),
    ).update(values, synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise _image_submission_conflict(task_id)
    db.commit()
    task = db.query(ImageCreationTask).filter_by(id=task_id).one()
    db.refresh(task)
    return task


async def _submit_claimed_image_task(
    db, task, claim_id, model_config, payload, strategy, scene_key, capability_key, *, error_code,
):
    task_id = task.id
    db.commit()
    try:
        result = await submit_image_create(db=db, model_config=model_config, **payload)
        provider_id = result.get("stage_task_id") or result.get("task_id") or result.get("id")
        if not provider_id:
            raise ValueError("Provider submission returned no task id")
    except Exception as exc:
        db.rollback()
        safe_message = _redact_provider_error(exc)
        # A timeout may mean the provider accepted the request. Preserve its external
        # identity and require reconciliation; failed tasks are not dispatchable.
        repair_action = "Reconcile the provider submission using external_task_id before retrying."
        fallback = _fallback_trace(
            db, strategy=strategy, scene_key=scene_key, capability_key=capability_key,
            error_code=error_code, message=safe_message,
        )
        _write_image_submission_result(db, task_id, claim_id, {
            "status": "failed", "capacity_lease_id": None, "error_code": error_code,
            "error_message": safe_message, "repair_action": repair_action,
            "fallback_trace_json": fallback,
        })
        raise image_error(
            502, error_code, "Pixelle image submission outcome requires reconciliation.",
            repair_action, retryable=True, affected_ids=[task_id],
        ) from exc
    return _write_image_submission_result(db, task_id, claim_id, {
        "provider_response_json": result, "pixelle_task_id": provider_id,
        "provider_task_id": provider_id, "status": "running",
    })


def _task_context(task: ImageCreationTask) -> dict[str, Any]:
    return {
        "series_id": task.series_id,
        "episode_id": task.episode_id,
        "source_asset_id": task.source_asset_id,
        "destination_role": task.destination_role,
        "destination_context": task.destination_context_json or {},
    }


def _task_timeline(task: ImageCreationTask) -> list[dict[str, Any]]:
    has_preview = bool(task.selection_preview_id)
    has_snapshot = bool(task.strategy_snapshot_json or task.request_json)
    status = task.status or "queued"
    generation_status = "failed" if status == "failed" else ("completed" if status == "completed" else status)
    review_status = "blocked" if status in {"failed", "rejected", "blocked"} else "pending"
    approval_status = "blocked" if status in {"failed", "rejected", "blocked"} else "pending"
    return [
        {"key": "preview", "label": "Selection preview", "status": "completed" if has_preview else "skipped"},
        {"key": "snapshot", "label": "Task snapshot", "status": "completed" if has_snapshot else "pending"},
        {"key": "queue", "label": "Queue", "status": "completed" if task.external_task_id else "pending"},
        {"key": "generation", "label": "Generation", "status": generation_status},
        {"key": "review", "label": "Review gate", "status": review_status},
        {"key": "approval", "label": "Approval gate", "status": approval_status},
    ]


def task_payload(task: ImageCreationTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "mode": task.mode,
        "capability_key": task.capability_key,
        "output_mode": task.output_mode,
        "status": task.status,
        "series_id": task.series_id,
        "episode_id": task.episode_id,
        "prompt": task.prompt,
        "model_scene_key": task.model_scene_key,
        "model_scene": task.model_scene,
        "provider": task.provider,
        "model_id": task.model_id,
        "pixelle_task_id": task.pixelle_task_id,
        "provider_task_id": task.provider_task_id,
        "external_task_id": task.external_task_id,
        "queue_job_id": task.queue_job_id,
        "capacity_lease_id": task.capacity_lease_id,
        "target_count": task.target_count,
        "completed_count": task.completed_count,
        "failed_count": task.failed_count,
        "ab_test_group_id": task.ab_test_group_id,
        "cost_status": task.cost_status,
        "estimated_cost": task.estimated_cost_json or {},
        "capacity": (task.request_json or {}).get("capacity") or {},
        "review_gate": (task.request_json or {}).get("review_gate") or {},
        "time_estimate": (task.request_json or {}).get("time_estimate") or (task.estimated_cost_json or {}).get("time_estimate") or {},
        "destination_role": task.destination_role,
        "destination_context": task.destination_context_json or {},
        "strategy": {
            "id": task.strategy_id,
            "version": task.strategy_version,
            "snapshot": task.strategy_snapshot_json or {},
        } if task.strategy_id else None,
        "selection_explanation": task.selection_explanation_json or {},
        "fallback_trace": task.fallback_trace_json or {},
        "timeline": _task_timeline(task),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _asset_action_task(asset: ImageCreationAsset, task: ImageCreationTask | None = None) -> ImageCreationTask | None:
    if task is not None or not asset.task_id:
        return task
    session = object_session(asset)
    if session is None:
        return None
    return session.query(ImageCreationTask).filter(ImageCreationTask.id == asset.task_id).first()


def _asset_allowed_actions(asset: ImageCreationAsset, task: ImageCreationTask | None = None) -> list[str]:
    actions = ["copy_as_new_task"]
    if asset.status in {"review_pending", "manual_review_pending"}:
        actions.extend(["approve", "reject", "repaint"])
    context = asset.destination_context_json or {}
    has_video_target = bool((context.get("video_run_id") or context.get("run_id")) and context.get("frame_id"))
    if has_video_target and review_gate_passed(_asset_action_task(asset, task), asset):
        actions.append("promote_to_video_asset")
    if asset.status in {"rejected", "blocked"}:
        actions.append("repaint")
    return actions


def ensure_image_asset_action_allowed(asset: ImageCreationAsset, action: str, asset_version: int | None) -> None:
    if asset_version is None:
        raise image_error(
            422,
            "ASSET_VERSION_REQUIRED",
            "Asset version is required for this action.",
            "Reload the asset and retry.",
            retryable=False,
        )
    if asset.version != asset_version:
        raise image_error(
            409,
            "STALE_ASSET_VERSION",
            "This action targets an older asset version.",
            "Reload latest asset.",
            retryable=False,
            affected_ids=[asset.id],
        )
    if action not in {"copy_as_new_task", "repaint"}:
        raise image_error(
            400,
            "IMAGE_ASSET_ACTION_INVALID",
            "Asset action must be copy_as_new_task or repaint.",
            "Choose an available asset action.",
            retryable=False,
        )
    if action not in _asset_allowed_actions(asset):
        raise image_error(
            409,
            "IMAGE_ASSET_ACTION_NOT_ALLOWED",
            "This asset action is not allowed for the asset state.",
            "Reload the asset and choose an available action.",
            retryable=False,
            affected_ids=[asset.id],
        )


def asset_payload(asset: ImageCreationAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "task_id": asset.task_id,
        "series_id": asset.series_id,
        "episode_id": asset.episode_id,
        "asset_type": asset.asset_type,
        "asset_kind": asset.asset_kind,
        "url": asset.url,
        "local_path": asset.local_path,
        "storage_path": asset.storage_path,
        "thumbnail_url": asset.thumbnail_url,
        "status": asset.status,
        "version": asset.version,
        "source_asset_id": asset.source_asset_id,
        "source_url": asset.source_url,
        "reference_images": asset.reference_images_json or [],
        "slot_key": asset.slot_key,
        "group_id": asset.group_id,
        "group_index": asset.group_index,
        "destination_role": asset.destination_role,
        "destination_context": asset.destination_context_json or {},
        "provider": asset.provider,
        "model_id": asset.model_id,
        "provider_task_id": asset.provider_task_id,
        "pixelle_task_id": asset.pixelle_task_id,
        "prompt_hash": asset.prompt_hash,
        "is_latest": asset.is_latest,
        "audit_status": asset.audit_status,
        "manual_review_status": asset.manual_review_status,
        "review_gate": (asset.metadata_json or {}).get("review_gate") or {},
        "allowed_actions": _asset_allowed_actions(asset),
        "metadata": asset.metadata_json or {},
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }


def review_payload(review: ImageCreationReviewRecord) -> dict[str, Any]:
    return {
        "id": review.id,
        "asset_id": review.asset_id,
        "task_id": review.task_id,
        "review_type": review.review_type,
        "reviewer_type": review.reviewer_type,
        "status": review.status,
        "action": review.action,
        "comment": review.comment,
        "asset_version": review.asset_version,
        "is_latest_asset_review": review.is_latest_asset_review,
        "report_json": review.report_json or {},
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


async def sync_image_task(db: Session, task_id: str) -> ImageCreationTask:
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == task_id).first()
    if not task:
        raise image_error(404, "IMAGE_TASK_NOT_FOUND", "Image creation task not found.", "Reload the task list.", retryable=False)
    if not task.pixelle_task_id:
        raise image_error(400, "PIXELLE_TASK_PENDING", "Pixelle task is not available yet.", "Sync again after task submission completes.")

    status = await get_stage_task(db, task.pixelle_task_id)
    stage_status = str(status.get("status") or "").lower()
    task.provider_response_json = _redact_provider_status_payload(status) if stage_status == "failed" else status
    if stage_status not in COMPLETE_STATUSES:
        task.status = "failed" if stage_status == "failed" else "running"
        raw_message = status.get("error") or status.get("message")
        task.error_message = _redact_provider_error(raw_message) if raw_message or stage_status == "failed" else None
        if stage_status == "failed":
            task.error_code = "PIXELLE_IMAGE_SYNC_FAILED"
            task.repair_action = "Open the task and retry with the suggested fallback model."
            strategy = (
                db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == task.strategy_id).first()
                if task.strategy_id else None
            )
            scene_key = task.model_scene_key or task.model_scene or MODE_TO_SCENE_CAPABILITY.get(task.mode, ("image_generation", "", ""))[0]
            capability_key = task.capability_key or MODE_TO_SCENE_CAPABILITY.get(task.mode, ("", "text_to_image", ""))[1]
            task.fallback_trace_json = _fallback_trace(
                db,
                strategy=strategy,
                scene_key=scene_key,
                capability_key=capability_key,
                error_code=task.error_code,
                message=task.error_message,
            )
        task.progress = _progress_value(status.get("progress"), task.progress or 0.0)
        db.commit()
        db.refresh(task)
        return task

    failures = 0
    for index, item in enumerate(status.get("assets") or []):
        if item.get("status") == "failed" or item.get("error"):
            failures += 1
            continue
        try:
            persisted = await _persist_stage_asset(db, task, item, index)
        except (httpx.HTTPError, ValueError) as exc:
            failures += 1
            task.error_message = f"Generated image could not be persisted: {exc}"
            continue
        if not persisted:
            failures += 1

    task.completed_count = db.query(ImageCreationAsset).filter(ImageCreationAsset.task_id == task.id).count()
    task.failed_count = failures
    task.status = "completed_with_warnings" if failures else "completed"
    task.progress = 1.0
    task.storage_status = "persisted" if failures == 0 else "partial"
    task.usage_json = status.get("usage") or {}
    task.completed_at = bj_now()
    record_actual_cost_event(db, task)
    db.commit()
    db.refresh(task)
    return task


async def _persist_stage_asset(db: Session, task: ImageCreationTask, item: dict[str, Any], index: int) -> bool:
    metadata = item.get("metadata") or {}
    group_id = metadata.get("group_id") or item.get("group_id") or task.pixelle_task_id
    group_index = metadata.get("group_index")
    if group_index is None:
        group_index = item.get("group_index")
    if group_index is None:
        group_index = index
    slot_key = str(metadata.get("slot_key") or item.get("slot_key") or f"{group_id}:{group_index}")
    existing = db.query(ImageCreationAsset).filter(
        ImageCreationAsset.task_id == task.id,
        ImageCreationAsset.slot_key == slot_key,
        ImageCreationAsset.version == 1,
    ).first()
    if existing:
        return True

    normalized_url = _normalized_stage_asset_url(item)
    local_path = item.get("local_path") or item.get("storage_path") or ""
    storage_path = item.get("storage_path") or item.get("local_path") or ""
    checksum = item.get("checksum")
    size_bytes = item.get("size_bytes")
    mime_type = item.get("mime_type")
    if _requires_external_copy(normalized_url):
        saved = await _copy_external_image(normalized_url)
        normalized_url = saved["url"]
        local_path = saved["local_path"]
        storage_path = saved["storage_path"]
        checksum = saved.get("checksum")
        size_bytes = saved.get("size_bytes")
        mime_type = saved.get("mime_type")

    if not normalized_url:
        return False

    review_gate = (task.request_json or {}).get("review_gate") or {}
    asset_status = "review_pending" if review_gate.get("required") else "approved"
    asset_metadata = {
        **metadata,
        "review_gate": review_gate,
        "strategy_snapshot": task.strategy_snapshot_json or {},
        "selection_explanation": task.selection_explanation_json or {},
    }
    db.add(ImageCreationAsset(
        task_id=task.id,
        user_id=task.user_id,
        series_id=task.series_id,
        episode_id=task.episode_id,
        asset_type="image",
        asset_kind=item.get("asset_kind") or item.get("asset_type") or "image",
        url=normalized_url,
        local_path=local_path,
        storage_path=storage_path,
        thumbnail_url=item.get("thumbnail_url"),
        mime_type=mime_type,
        width=item.get("width"),
        height=item.get("height"),
        seed=str(item.get("seed")) if item.get("seed") is not None else None,
        prompt=item.get("prompt") or task.prompt,
        checksum=checksum,
        size_bytes=size_bytes,
        status=asset_status,
        version=1,
        source_asset_id=task.source_asset_id,
        source_url=task.source_url,
        reference_images_json=task.reference_images_json or [],
        slot_key=slot_key,
        group_id=str(group_id),
        group_index=int(group_index),
        destination_role=metadata.get("destination_role") or task.destination_role,
        destination_context_json=metadata.get("destination_context") or task.destination_context_json or {},
        provider_task_id=item.get("provider_task_id") or task.provider_task_id,
        pixelle_task_id=task.pixelle_task_id,
        model_scene=task.model_scene,
        provider=task.provider,
        model_id=task.model_id,
        variant_index=index,
        prompt_hash=task.request_hash,
        is_latest=True,
        audit_status=review_gate.get("status"),
        manual_review_status="pending" if review_gate.get("manual_required") else None,
        metadata_json=asset_metadata,
        storage_status="persisted",
    ))
    return True


def list_image_assets(
    db: Session,
    status: str | None = None,
    destination_role: str | None = None,
    series_id: str | None = None,
    episode_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ImageCreationAsset], int]:
    query = db.query(ImageCreationAsset)
    if status:
        query = query.filter(ImageCreationAsset.status == status)
    if destination_role:
        query = query.filter(ImageCreationAsset.destination_role == destination_role)
    if series_id:
        query = query.filter(ImageCreationAsset.series_id == series_id)
    if episode_id:
        query = query.filter(ImageCreationAsset.episode_id == episode_id)
    total = query.count()
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    rows = (
        query.order_by(ImageCreationAsset.created_at.desc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
        .all()
    )
    return rows, total


def review_image_asset(
    db: Session,
    asset_id: str,
    action: str,
    comment: str = "",
    reviewer_user_id: str | None = None,
    asset_version: int | None = None,
    report_json: dict[str, Any] | None = None,
) -> tuple[ImageCreationAsset, list[ImageCreationReviewRecord]]:
    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(404, "SOURCE_ASSET_NOT_FOUND", "Image asset not found.", "Pick another asset.", retryable=False)
    if asset_version is None:
        raise image_error(422, "ASSET_VERSION_REQUIRED", "Asset version is required for review.", "Reload the asset and retry.", retryable=False)
    if asset.version != asset_version:
        raise image_error(409, "STALE_ASSET_VERSION", "This review targets an older asset version.", "Reload latest asset.", retryable=False)
    if action not in {"approve", "reject"}:
        raise image_error(400, "IMAGE_REVIEW_ACTION_INVALID", "Review action must be approve or reject.", "Choose approve or reject.", retryable=False)
    if action not in _asset_allowed_actions(asset):
        raise image_error(
            409,
            "IMAGE_REVIEW_ACTION_NOT_ALLOWED",
            "This review action is not allowed for the asset state.",
            "Reload the asset and choose an available action.",
            retryable=False,
            affected_ids=[asset.id],
        )

    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == asset.task_id).first()
    gate = asset_review_gate(task, asset)
    if action == "approve":
        asset.manual_review_status = "approved"
        if gate.get("status") == "blocked":
            gate["status"] = "blocked"
        elif gate.get("ai_required") and asset.audit_status != "approved":
            asset.status = "review_pending"
            gate["status"] = "ai_review_pending"
        else:
            asset.status = "approved"
            asset.audit_status = "approved"
            gate["status"] = "approved"
    else:
        asset.status = "rejected"
        asset.audit_status = "rejected"
        asset.manual_review_status = "rejected"
        gate["status"] = "blocked"
    metadata = dict(asset.metadata_json or {})
    metadata["review_gate"] = gate
    asset.metadata_json = metadata
    db.query(ImageCreationReviewRecord).filter(
        ImageCreationReviewRecord.asset_id == asset.id,
        ImageCreationReviewRecord.asset_version == asset.version,
    ).update({"is_latest_asset_review": False}, synchronize_session=False)
    review = ImageCreationReviewRecord(
        task_id=asset.task_id,
        asset_id=asset.id,
        review_type="human",
        reviewer_type="human",
        status=asset.status,
        action=action,
        comment=comment,
        reviewer_user_id=reviewer_user_id,
        asset_version=asset.version,
        is_latest_asset_review=True,
        report_json=report_json or {},
    )
    db.add(review)
    db.commit()
    db.refresh(asset)
    reviews = db.query(ImageCreationReviewRecord).filter(
        ImageCreationReviewRecord.asset_id == asset.id,
        ImageCreationReviewRecord.asset_version == asset.version,
    ).order_by(ImageCreationReviewRecord.created_at.asc()).all()
    return asset, reviews
