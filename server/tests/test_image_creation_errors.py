from app.services.image_creation_errors import image_error


def test_image_error_carries_details_and_rescue_actions():
    exc = image_error(
        409,
        "IMAGE_REVIEW_GATE_BLOCKED",
        "Blocked.",
        "Approve or repaint.",
        retryable=False,
        affected_ids=["asset-1"],
        details={"review_gate": {"status": "manual_review_pending"}},
        rescue_actions=[{"type": "manual_review_required", "label": "Approve asset."}],
    )

    assert exc.status_code == 409
    assert exc.detail["error_code"] == "IMAGE_REVIEW_GATE_BLOCKED"
    assert exc.detail["affected_ids"] == ["asset-1"]
    assert exc.detail["details"]["review_gate"]["status"] == "manual_review_pending"
    assert exc.detail["rescue_actions"][0]["type"] == "manual_review_required"


def test_image_error_keeps_existing_payload_shape():
    exc = image_error(400, "IMAGE_PROMPT_REQUIRED", "Prompt is required.", "Enter a prompt.")

    assert exc.detail["ok"] is False
    assert exc.detail["repair_route"] is None
    assert exc.detail["retryable"] is True
    assert exc.detail["affected_ids"] == []
    assert "details" not in exc.detail
    assert "rescue_actions" not in exc.detail
