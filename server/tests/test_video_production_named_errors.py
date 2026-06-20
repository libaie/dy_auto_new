from app.domains.video_production.production_errors import (
    ProductionErrorCode,
    ProductionRepairableError,
    to_http_detail,
)


def test_repairable_error_serializes_contract():
    error = ProductionRepairableError(
        code=ProductionErrorCode.SEGMENT_PLAN_MISSING,
        message="No production segments exist for this episode.",
        repair_action="Generate shot segments",
        repair_route="/series/series-id",
        retryable=True,
        affected_ids=["episode-id"],
        cause="segments_missing",
    )

    assert to_http_detail(error) == {
        "code": "SEGMENT_PLAN_MISSING",
        "error_code": "SEGMENT_PLAN_MISSING",
        "message": "No production segments exist for this episode.",
        "cause": "segments_missing",
        "repair_action": "Generate shot segments",
        "repair_route": "/series/series-id",
        "retryable": True,
        "affected_ids": ["episode-id"],
    }


def test_repairable_error_keeps_legacy_positional_order():
    error = ProductionRepairableError(
        ProductionErrorCode.STORYBOARD_MISSING,
        "Storyboard is missing.",
        "Generate storyboard",
        "/series/series-id",
        True,
        ["episode-id"],
    )

    assert error.retryable is True
    assert error.affected_ids == ["episode-id"]
    assert error.cause is None
    assert to_http_detail(error)["cause"] is None
