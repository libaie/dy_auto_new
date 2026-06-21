"""图片生成业务域模块。

图片生成业务域，负责图片任务创建、策略选择、审核门禁和生成资产入库。本文件负责 image_production_router 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.models.image_production import ImageProductionMetric, ImageProductionStrategy
from app.deps import require_role, verify_admin_token
from app.domains.image_generation.image_ab_test_service import (
    adopt_ab_winner,
    create_ab_group,
    get_ab_group,
    mark_ab_no_winner,
    preview_ab_group,
    recommend_ab_winner,
    refresh_ab_group,
    serialize_ab_group,
)
from app.domains.image_generation.image_asset_bridge_service import (
    promote_image_asset_to_video_asset,
    video_asset_payload,
)
from app.domains.image_generation.image_selection_preview_service import create_selection_preview
from app.domains.image_generation.image_production_metrics_service import (
    aggregate_strategy_metrics_payload,
    refresh_all_image_strategy_metrics,
)
from app.domains.image_generation.image_production_recommendation_service import strategy_recommendation_payload
from app.domains.image_generation.image_production_strategy_service import (
    create_strategy,
    get_strategy,
    list_strategies,
    seed_default_image_strategies,
    set_strategy_status,
    strategy_payload,
    update_strategy,
)


router = APIRouter(prefix="/api/image-production", tags=["image-production"])


def _auth_user_id(user) -> str | None:
    """业务函数：处理 _auth_user_id 对应的业务流程、校验或数据转换。"""
    return user[0] if isinstance(user, tuple) else None


def _metrics_by_strategy(
    db: Session,
    rows: list[ImageProductionStrategy],
) -> dict[tuple[str, int], list[ImageProductionMetric]]:
    """业务函数：处理 _metrics_by_strategy 对应的业务流程、校验或数据转换。"""
    if not rows:
        return {}
    strategy_ids = [row.id for row in rows]
    metrics = (
        db.query(ImageProductionMetric)
        .filter(ImageProductionMetric.strategy_id.in_(strategy_ids))
        .all()
    )
    grouped: dict[tuple[str, int], list[ImageProductionMetric]] = {}
    for metric in metrics:
        grouped.setdefault((metric.strategy_id, metric.strategy_version), []).append(metric)
    return grouped


def _strategy_payload_with_metric(
    strategy: ImageProductionStrategy,
    metrics: list[ImageProductionMetric],
) -> dict:
    """业务函数：处理 _strategy_payload_with_metric 对应的业务流程、校验或数据转换。"""
    payload = strategy_payload(strategy)
    payload["metrics"] = aggregate_strategy_metrics_payload(metrics)
    return payload


class StrategyRequest(BaseModel):
    """业务类：承载 StrategyRequest 相关的数据结构、状态或业务协作。"""
    slug: str | None = None
    name: str
    description: str = ""
    destination_role: str
    supported_modes: list[str] = Field(default_factory=list)
    default_model_id: str | None = None
    fallback_model_ids: list[str] = Field(default_factory=list)
    common_parameters: dict = Field(default_factory=dict)
    provider_options: dict = Field(default_factory=dict)
    review_policy_version_id: str | None = None
    cost_policy_version_id: str | None = None
    capacity_policy_version_id: str | None = None
    ab_test_policy_version_id: str | None = None
    version: int | None = None


class StrategyMetricsRefreshRequest(BaseModel):
    """业务类：承载 StrategyMetricsRefreshRequest 相关的数据结构、状态或业务协作。"""
    strategy_id: str | None = None
    strategy_version: int | None = None


class SelectionPreviewRequest(BaseModel):
    """业务类：承载 SelectionPreviewRequest 相关的数据结构、状态或业务协作。"""
    mode: str
    prompt: str | None = None
    negative_prompt: str | None = None
    destination_role: str | None = None
    strategy_id: str | None = None
    strategy_version: int | None = None
    model_id: str | None = None
    source: dict | None = None
    source_url: str | None = None
    source_asset_id: str | None = None
    reference: dict | None = None
    reference_images: list[dict] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    reference_asset_ids: list[str] = Field(default_factory=list)
    common: dict = Field(default_factory=dict)
    common_parameters: dict = Field(default_factory=dict)
    provider_options: dict = Field(default_factory=dict)
    size: str | None = None
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    count: int = 1
    reference_count: int = 0


class AbPreviewRequest(BaseModel):
    """业务类：承载 AbPreviewRequest 相关的数据结构、状态或业务协作。"""
    mode: str
    prompt: str | None = None
    negative_prompt: str | None = None
    destination_role: str | None = None
    model_id: str | None = None
    strategy_ids: list[str] = Field(default_factory=list)
    source: dict | None = None
    source_url: str | None = None
    source_asset_id: str | None = None
    reference_images: list[dict] = Field(default_factory=list)
    size: str | None = None
    count: int = 1
    output_format: str | None = None
    response_format: str | None = None
    watermark: bool | None = None
    provider_options: dict = Field(default_factory=dict)


class AbCreateRequest(AbPreviewRequest):
    """业务类：承载 AbCreateRequest 相关的数据结构、状态或业务协作。"""
    preview_request_hash: str | None = None
    cost_confirmation: bool = False
    idempotency_key: str | None = None


class AbDecisionRequest(BaseModel):
    """业务类：承载 AbDecisionRequest 相关的数据结构、状态或业务协作。"""
    reason: str = ""
    notes: str = ""


class PromoteImageAssetRequest(BaseModel):
    """业务类：承载 PromoteImageAssetRequest 相关的数据结构、状态或业务协作。"""
    run_id: str
    frame_id: str
    version: int | None = None
    asset_version: int | None = Field(None, ge=1)
    episode_id: str | None = None
    destination_role: str | None = None


@router.post("/strategies/seed-defaults")
def seed_defaults(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 seed_defaults 对应的业务流程、校验或数据转换。"""
    seed_default_image_strategies(db)
    return {"ok": True}


@router.get("/strategies")
def strategies(
    status: str | None = Query(None),
    destination_role: str | None = Query(None),
    include_metrics: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """业务函数：处理 strategies 对应的业务流程、校验或数据转换。"""
    rows = list_strategies(db, status=status, destination_role=destination_role)
    metric_map = _metrics_by_strategy(db, rows) if include_metrics else {}
    return {
        "ok": True,
        "strategies": [
            _strategy_payload_with_metric(
                row,
                metric_map.get((row.id, row.version), []),
            )
            if include_metrics
            else strategy_payload(row)
            for row in rows
        ],
    }


@router.post("/strategies")
def create(body: StrategyRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 create 对应的业务流程、校验或数据转换。"""
    payload = body.model_dump()
    if not payload.get("slug"):
        payload["slug"] = payload["name"].strip().lower().replace(" ", "-")
    strategy = create_strategy(db, payload)
    return {"ok": True, "strategy": strategy_payload(strategy)}


@router.post("/strategies/metrics/refresh")
def refresh_strategy_metrics(
    body: StrategyMetricsRefreshRequest,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """业务函数：处理 refresh_strategy_metrics 对应的业务流程、校验或数据转换。"""
    refreshed = refresh_all_image_strategy_metrics(
        db,
        strategy_id=body.strategy_id,
        strategy_version=body.strategy_version,
    )
    db.commit()
    return {"ok": True, "refreshed": refreshed}


@router.post("/selection-preview")
def selection_preview(body: SelectionPreviewRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    """业务函数：处理 selection_preview 对应的业务流程、校验或数据转换。"""
    user_id = user[0] if isinstance(user, tuple) else None
    return create_selection_preview(db, body.model_dump(), user_id=user_id)


@router.post("/ab-tests/preview")
def ab_preview(body: AbPreviewRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    """业务函数：处理 ab_preview 对应的业务流程、校验或数据转换。"""
    return preview_ab_group(db, body.model_dump(), user_id=_auth_user_id(user))


@router.post("/ab-tests")
async def ab_create(body: AbCreateRequest, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    """业务函数：处理 ab_create 对应的业务流程、校验或数据转换。"""
    group = await create_ab_group(db, body.model_dump(), user_id=_auth_user_id(user))
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.get("/ab-tests/{group_id}")
def ab_read(group_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    """业务函数：处理 ab_read 对应的业务流程、校验或数据转换。"""
    group = get_ab_group(db, group_id, user_id=_auth_user_id(user))
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.post("/ab-tests/{group_id}/refresh")
def ab_refresh(group_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    """业务函数：处理 ab_refresh 对应的业务流程、校验或数据转换。"""
    group = refresh_ab_group(db, group_id, user_id=_auth_user_id(user))
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.get("/ab-tests/{group_id}/winner-recommendation")
def ab_winner_recommendation(group_id: str, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    """业务函数：处理 ab_winner_recommendation 对应的业务流程、校验或数据转换。"""
    return {"ok": True, "recommendation": recommend_ab_winner(db, group_id, user_id=_auth_user_id(user))}


@router.post("/ab-tests/{group_id}/winner/{attempt_id}")
def ab_winner(
    group_id: str,
    attempt_id: str,
    body: AbDecisionRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 ab_winner 对应的业务流程、校验或数据转换。"""
    group = adopt_ab_winner(db, group_id, attempt_id, body.model_dump(), user_id=_auth_user_id(user))
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.post("/ab-tests/{group_id}/no-winner")
def ab_no_winner(
    group_id: str,
    body: AbDecisionRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 ab_no_winner 对应的业务流程、校验或数据转换。"""
    group = mark_ab_no_winner(db, group_id, body.model_dump(), user_id=_auth_user_id(user))
    return {"ok": True, "ab_group": serialize_ab_group(db, group)}


@router.post("/assets/{asset_id}/promote-to-video-asset")
def promote_asset(
    asset_id: str,
    body: PromoteImageAssetRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 promote_asset 对应的业务流程、校验或数据转换。"""
    payload = body.model_dump()
    if isinstance(user, tuple):
        payload["user_id"] = user[0]
    asset = promote_image_asset_to_video_asset(db, asset_id, payload)
    return {"ok": True, "video_asset": video_asset_payload(asset)}


@router.get("/strategies/{strategy_id}/recommendations")
def strategy_recommendations(strategy_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 strategy_recommendations 对应的业务流程、校验或数据转换。"""
    return {"ok": True, "recommendation": strategy_recommendation_payload(db, strategy_id)}


@router.get("/strategies/{strategy_id}")
def read(strategy_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 read 对应的业务流程、校验或数据转换。"""
    return {"ok": True, "strategy": strategy_payload(get_strategy(db, strategy_id))}


@router.put("/strategies/{strategy_id}")
def update(strategy_id: str, body: StrategyRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 update 对应的业务流程、校验或数据转换。"""
    strategy = update_strategy(db, strategy_id, body.model_dump())
    return {"ok": True, "strategy": strategy_payload(strategy)}


@router.post("/strategies/{strategy_id}/activate")
def activate(strategy_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 activate 对应的业务流程、校验或数据转换。"""
    return {"ok": True, "strategy": strategy_payload(set_strategy_status(db, strategy_id, "active"))}


@router.post("/strategies/{strategy_id}/archive")
def archive(strategy_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    """业务函数：处理 archive 对应的业务流程、校验或数据转换。"""
    return {"ok": True, "strategy": strategy_payload(set_strategy_status(db, strategy_id, "archived"))}
