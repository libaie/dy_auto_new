from app.db_models import (
    ProductionAuditEvent,
    ProviderCostReservation,
    ProviderStageTask,
    VideoProductionAsset,
    VideoReviewRecord,
)
from app.services.production_action_result import ProductionActionResult
from app.services.production_errors import ProductionErrorCode
from app.services.production_state_contract import (
    COST_ACTIVE_UNSUBMITTED,
    COST_RELEASED,
    COST_SETTLED,
    COST_STALE_NEEDS_REPAIR,
    COST_SUBMITTED,
    PROVIDER_TASK_CANCELLED,
    PROVIDER_TASK_FAILED,
    PROVIDER_TASK_MANUAL_REPAIR_REQUIRED,
    PROVIDER_TASK_RESERVED,
    PROVIDER_TASK_SUCCEEDED,
    PROVIDER_TASK_SYNC_REQUIRED,
    PROVIDER_TASK_TERMINAL_STATUSES,
    asset_is_reviewable,
    provider_task_is_active,
    validate_transition,
)


def test_provider_stage_task_and_cost_reservation_can_be_instantiated():
    task = ProviderStageTask(
        run_id="run-1",
        plan_id="plan-1",
        job_id="job-1",
        target_type="production_segment",
        target_id="segment-1",
        stage="image_generation",
        provider="pixelle",
        model_name="seedream",
        request_hash="abc123",
        idempotency_key="run-1:segment-1:image_generation",
        status=PROVIDER_TASK_RESERVED,
    )
    reservation = ProviderCostReservation(
        plan_id="plan-1",
        provider_stage_task_id="stage-task-1",
        status="active_unsubmitted",
        estimated_cost=0.2,
        reserved_cost=0.2,
        currency="CNY",
    )

    assert task.status == "reserved"
    assert task.idempotency_key == "run-1:segment-1:image_generation"
    assert reservation.provider_stage_task_id == "stage-task-1"
    assert reservation.currency == "CNY"


def test_existing_models_include_boundary_fields():
    for field_name in (
        "storage_path",
        "source_url",
        "storage_error_json",
        "provider_response_summary_json",
        "provider_stage_task_id",
    ):
        assert hasattr(VideoProductionAsset, field_name)

    for field_name in (
        "reviewer_role",
        "action",
        "asset_snapshot_json",
        "model_trace_summary_json",
    ):
        assert hasattr(VideoReviewRecord, field_name)

    assert hasattr(ProductionAuditEvent, "actor_user_id")
    assert hasattr(ProductionAuditEvent, "actor_role")


def test_blocked_action_result_serializes_http_detail():
    result = ProductionActionResult.blocked(
        code=ProductionErrorCode.ASSET_STORAGE_FAILED,
        message="asset storage failed",
        repair_action="retry storage",
        repair_route="/video-production/assets/asset-1/retry-storage",
        affected_ids=["asset-1"],
    )

    detail = result.to_http_detail()

    assert detail["code"] == "ASSET_STORAGE_FAILED"
    assert detail["error_code"] == "ASSET_STORAGE_FAILED"
    assert detail["repair_route"] == "/video-production/assets/asset-1/retry-storage"
    assert detail["affected_ids"] == ["asset-1"]


def test_success_action_result_serializes_http_detail():
    detail = ProductionActionResult.success(message="created").to_http_detail()

    assert detail["ok"] is True
    assert detail["code"] == "OK"
    assert detail["error_code"] == "OK"
    assert detail["message"] == "created"


def test_blocked_action_result_serializes_string_code():
    result = ProductionActionResult.blocked(
        code="CUSTOM_CODE",
        message="custom blocked",
        repair_action="repair manually",
        repair_route="/repair/custom",
        affected_ids=["custom-1"],
    )

    detail = result.to_http_detail()

    assert detail["code"] == "CUSTOM_CODE"
    assert detail["error_code"] == "CUSTOM_CODE"
    assert detail["repair_route"] == "/repair/custom"
    assert detail["affected_ids"] == ["custom-1"]


def test_provider_state_contract():
    assert provider_task_is_active("running") is True
    assert provider_task_is_active("succeeded") is False
    assert validate_transition("provider_stage_task", "reserved", "submitted") is True
    assert validate_transition("provider_stage_task", "succeeded", "running") is False


def test_provider_repair_states_are_active_and_terminal_states_are_inactive():
    assert provider_task_is_active(PROVIDER_TASK_SYNC_REQUIRED) is True
    assert provider_task_is_active(PROVIDER_TASK_MANUAL_REPAIR_REQUIRED) is True
    assert PROVIDER_TASK_TERMINAL_STATUSES == {
        PROVIDER_TASK_SUCCEEDED,
        PROVIDER_TASK_FAILED,
        PROVIDER_TASK_CANCELLED,
    }
    assert provider_task_is_active(PROVIDER_TASK_SUCCEEDED) is False
    assert provider_task_is_active(PROVIDER_TASK_FAILED) is False
    assert provider_task_is_active(PROVIDER_TASK_CANCELLED) is False


def test_cost_reservation_status_constants():
    assert COST_ACTIVE_UNSUBMITTED == "active_unsubmitted"
    assert COST_SUBMITTED == "submitted"
    assert COST_SETTLED == "settled"
    assert COST_RELEASED == "released"
    assert COST_STALE_NEEDS_REPAIR == "stale_needs_repair"


def test_cost_reservation_expiry_index_name_matches_contract():
    index_names = {index.name for index in ProviderCostReservation.__table__.indexes}

    assert "idx_provider_cost_reservations_expires" in index_names
    assert "idx_provider_cost_reservations_expires_status" not in index_names


def test_asset_reviewable_status_contract():
    assert asset_is_reviewable("review_pending") is True
    assert asset_is_reviewable("generated") is False
    assert asset_is_reviewable("stored") is False
    assert asset_is_reviewable("approved") is False
