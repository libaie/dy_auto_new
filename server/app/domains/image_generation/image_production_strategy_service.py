from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion
from app.domains.image_generation.image_creation_errors import image_error
from app.services.production_observability import record_production_event


VALID_DESTINATION_ROLES = {
    "character_anchor_image",
    "scene_reference_image",
    "style_reference_image",
    "storyboard_first_frame",
    "image_to_video_input",
    "repaint_image",
    "fusion_image",
    "batch_story_images",
}
VALID_MODES = {
    "text_to_image",
    "image_to_image",
    "multi_reference_to_image",
    "text_to_image_set",
    "image_to_image_set",
    "multi_reference_to_image_set",
}
VALID_STATUSES = {"active", "archived", "disabled"}
POLICY_FIELDS = {
    "review_policy_version_id": "review",
    "cost_policy_version_id": "cost",
    "capacity_policy_version_id": "capacity",
    "ab_test_policy_version_id": "ab_test",
}


DEFAULT_STRATEGIES = [
    {
        "slug": "character-anchor-default",
        "name": "Default Character Anchor",
        "description": "Default strategy for character anchor reference images.",
        "destination_role": "character_anchor_image",
        "supported_modes": ["text_to_image", "text_to_image_set"],
        "common_parameters": {"count": 4},
        "provider_options": {},
    },
    {
        "slug": "image-to-video-input-default",
        "name": "Default Image To Video Input",
        "description": "Default strategy for image-to-video input images.",
        "destination_role": "image_to_video_input",
        "supported_modes": ["image_to_image", "multi_reference_to_image"],
        "common_parameters": {"count": 1},
        "provider_options": {},
    },
    {
        "slug": "storyboard-first-frame-default",
        "name": "Default Storyboard First Frame",
        "description": "Default strategy for storyboard first-frame images.",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image", "image_to_image"],
        "common_parameters": {"count": 1},
        "provider_options": {},
    },
]


def _default_policy(db: Session, policy_type: str, name: str, snapshot: dict[str, Any]) -> ImageProductionPolicyVersion:
    policy = (
        db.query(ImageProductionPolicyVersion)
        .filter(
            ImageProductionPolicyVersion.policy_type == policy_type,
            ImageProductionPolicyVersion.name == name,
            ImageProductionPolicyVersion.version == 1,
        )
        .first()
    )
    if policy:
        return policy
    policy = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=name,
        version=1,
        snapshot_json=snapshot,
        status="active",
    )
    db.add(policy)
    db.flush()
    return policy


def _strategy_snapshot(strategy: ImageProductionStrategy) -> dict[str, Any]:
    return {
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
        "status": strategy.status,
        "version": strategy.version,
    }


def _write_version(db: Session, strategy: ImageProductionStrategy) -> ImageProductionStrategyVersion:
    version = ImageProductionStrategyVersion(
        strategy_id=strategy.id,
        version=strategy.version,
        snapshot_json=_strategy_snapshot(strategy),
    )
    db.add(version)
    db.flush()
    return version


def _validate_strategy_input(payload: dict[str, Any]) -> None:
    if payload.get("destination_role") not in VALID_DESTINATION_ROLES:
        raise image_error(
            422,
            "IMAGE_STRATEGY_ROLE_INVALID",
            "Strategy destination role is invalid.",
            "Choose a supported destination role.",
            retryable=False,
        )
    modes = payload.get("supported_modes") or []
    if not isinstance(modes, list) or not modes:
        raise image_error(
            422,
            "IMAGE_STRATEGY_MODES_REQUIRED",
            "Strategy must support at least one mode.",
            "Choose at least one supported mode.",
            retryable=False,
        )
    if any(mode not in VALID_MODES for mode in modes):
        raise image_error(
            422,
            "IMAGE_STRATEGY_MODE_INVALID",
            "Strategy supported modes are invalid.",
            "Choose supported image production modes.",
            retryable=False,
        )


def _validate_policy_refs(db: Session, payload: dict[str, Any]) -> None:
    for field, expected_type in POLICY_FIELDS.items():
        policy_id = payload.get(field)
        if not policy_id:
            continue
        policy = db.query(ImageProductionPolicyVersion).filter(ImageProductionPolicyVersion.id == policy_id).first()
        if not policy:
            raise image_error(
                404,
                "IMAGE_POLICY_VERSION_NOT_FOUND",
                "Image production policy version was not found.",
                f"Choose an existing {expected_type} policy version.",
                retryable=False,
                affected_ids=[policy_id],
            )
        if policy.policy_type != expected_type:
            raise image_error(
                422,
                "IMAGE_POLICY_TYPE_INVALID",
                "Image production policy type does not match the strategy field.",
                f"Choose a {expected_type} policy for {field}.",
                retryable=False,
                affected_ids=[policy_id],
            )
        if policy.status != "active":
            raise image_error(
                422,
                "IMAGE_POLICY_VERSION_INACTIVE",
                "Image production policy version is not active.",
                "Choose an active policy version.",
                retryable=False,
                affected_ids=[policy_id],
            )


def _is_slug_conflict(exc: IntegrityError) -> bool:
    message = str(exc.orig).lower()
    return "uq_image_strategy_slug" in message or (
        "unique" in message
        and "image_production_strategies" in message
        and "slug" in message
    )


def _is_strategy_version_conflict(exc: IntegrityError) -> bool:
    message = str(exc.orig).lower()
    return "uq_image_strategy_version" in message or (
        "unique" in message
        and "image_production_strategy_versions" in message
    )


def _raise_integrity_error(exc: IntegrityError) -> None:
    raise image_error(
        409,
        "IMAGE_STRATEGY_INTEGRITY_ERROR",
        "Image production strategy could not be saved because related data is invalid.",
        "Reload the strategy configuration and verify referenced models and policies.",
        retryable=False,
    ) from exc


def seed_default_image_strategies(db: Session) -> None:
    review_policy = _default_policy(db, "review", "default-image-review", {"manual_required_for": ["image_to_video_input"]})
    cost_policy = _default_policy(db, "cost", "default-image-cost", {"confirmation_threshold_amount": 1})
    capacity_policy = _default_policy(db, "capacity", "default-image-capacity", {"mode": "preview_only"})

    for item in DEFAULT_STRATEGIES:
        strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.slug == item["slug"]).first()
        if strategy:
            existing_version = (
                db.query(ImageProductionStrategyVersion)
                .filter(
                    ImageProductionStrategyVersion.strategy_id == strategy.id,
                    ImageProductionStrategyVersion.version == strategy.version,
                )
                .first()
            )
            if not existing_version:
                _write_version(db, strategy)
            continue
        strategy = ImageProductionStrategy(
            slug=item["slug"],
            name=item["name"],
            description=item["description"],
            destination_role=item["destination_role"],
            supported_modes_json=item["supported_modes"],
            default_model_id=None,
            fallback_model_ids_json=[],
            common_parameters_json=item["common_parameters"],
            provider_options_json=item["provider_options"],
            review_policy_version_id=review_policy.id,
            cost_policy_version_id=cost_policy.id,
            capacity_policy_version_id=capacity_policy.id,
            status="active",
            version=1,
        )
        db.add(strategy)
        db.flush()
        _write_version(db, strategy)
    db.commit()


def list_strategies(
    db: Session,
    status: str | None = None,
    destination_role: str | None = None,
) -> list[ImageProductionStrategy]:
    query = db.query(ImageProductionStrategy)
    if status:
        query = query.filter(ImageProductionStrategy.status == status)
    if destination_role:
        query = query.filter(ImageProductionStrategy.destination_role == destination_role)
    return query.order_by(ImageProductionStrategy.destination_role.asc(), ImageProductionStrategy.name.asc()).all()


def get_strategy(db: Session, strategy_id: str) -> ImageProductionStrategy:
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(
            404,
            "IMAGE_STRATEGY_NOT_FOUND",
            "Image production strategy was not found.",
            "Choose another strategy.",
            retryable=False,
            affected_ids=[strategy_id],
        )
    return strategy


def create_strategy(db: Session, payload: dict[str, Any]) -> ImageProductionStrategy:
    _validate_strategy_input(payload)
    _validate_policy_refs(db, payload)
    strategy = ImageProductionStrategy(
        slug=payload["slug"],
        name=payload["name"],
        description=payload.get("description") or "",
        destination_role=payload["destination_role"],
        supported_modes_json=payload.get("supported_modes") or [],
        default_model_id=payload.get("default_model_id"),
        fallback_model_ids_json=payload.get("fallback_model_ids") or [],
        common_parameters_json=payload.get("common_parameters") or {},
        provider_options_json=payload.get("provider_options") or {},
        review_policy_version_id=payload.get("review_policy_version_id"),
        cost_policy_version_id=payload.get("cost_policy_version_id"),
        capacity_policy_version_id=payload.get("capacity_policy_version_id"),
        ab_test_policy_version_id=payload.get("ab_test_policy_version_id"),
        status="active",
        version=1,
    )
    db.add(strategy)
    try:
        db.flush()
        _write_version(db, strategy)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _is_slug_conflict(exc):
            _raise_integrity_error(exc)
        raise image_error(
            409,
            "IMAGE_STRATEGY_SLUG_CONFLICT",
            "Strategy slug already exists.",
            "Use a unique strategy slug.",
            retryable=False,
        ) from exc
    db.refresh(strategy)
    return strategy


def update_strategy(db: Session, strategy_id: str, payload: dict[str, Any]) -> ImageProductionStrategy:
    _validate_strategy_input(payload)
    _validate_policy_refs(db, payload)
    strategy = get_strategy(db, strategy_id)
    if int(payload.get("version") or 0) != strategy.version:
        raise image_error(
            409,
            "IMAGE_STRATEGY_VERSION_CONFLICT",
            "Strategy was changed by another editor.",
            "Reload the strategy and apply your changes again.",
            retryable=False,
            affected_ids=[strategy_id],
        )

    strategy.name = payload["name"]
    strategy.description = payload.get("description") or ""
    strategy.destination_role = payload["destination_role"]
    strategy.supported_modes_json = payload.get("supported_modes") or []
    strategy.default_model_id = payload.get("default_model_id")
    strategy.fallback_model_ids_json = payload.get("fallback_model_ids") or []
    strategy.common_parameters_json = payload.get("common_parameters") or {}
    strategy.provider_options_json = payload.get("provider_options") or {}
    strategy.review_policy_version_id = payload.get("review_policy_version_id")
    strategy.cost_policy_version_id = payload.get("cost_policy_version_id")
    strategy.capacity_policy_version_id = payload.get("capacity_policy_version_id")
    strategy.ab_test_policy_version_id = payload.get("ab_test_policy_version_id")
    strategy.version += 1
    strategy.updated_at = bj_now()
    try:
        _write_version(db, strategy)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_strategy_version_conflict(exc):
            raise image_error(
                409,
                "IMAGE_STRATEGY_VERSION_CONFLICT",
                "Strategy was changed by another editor.",
                "Reload the strategy and apply your changes again.",
                retryable=False,
                affected_ids=[strategy_id],
            ) from exc
        _raise_integrity_error(exc)
    db.refresh(strategy)
    return strategy


def set_strategy_status(db: Session, strategy_id: str, status: str) -> ImageProductionStrategy:
    if status not in VALID_STATUSES:
        raise image_error(
            422,
            "IMAGE_STRATEGY_STATUS_INVALID",
            "Strategy status is invalid.",
            "Choose active, disabled, or archived.",
            retryable=False,
            affected_ids=[strategy_id],
        )
    strategy = get_strategy(db, strategy_id)
    previous_status = strategy.status
    strategy.status = status
    strategy.updated_at = bj_now()
    record_production_event(
        db,
        event_type=f"image_strategy.{status}",
        payload={
            "strategy_id": strategy.id,
            "strategy_slug": strategy.slug,
            "strategy_version": strategy.version,
            "previous_status": previous_status,
            "next_status": status,
        },
    )
    db.commit()
    db.refresh(strategy)
    return strategy


def strategy_payload(strategy: ImageProductionStrategy) -> dict[str, Any]:
    return {
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
        "status": strategy.status,
        "version": strategy.version,
        "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
        "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
    }
