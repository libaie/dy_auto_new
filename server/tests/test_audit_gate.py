from app.services.audit_gate import classify_audit_gate


def test_missing_audit_config_needs_human():
    result = classify_audit_gate({"score": 0.0, "pass_fail": False, "issues": ["missing api key"]})
    assert result["gate_status"] == "needs_human"
    assert result["pass_fail"] is False


def test_low_score_needs_human_by_default():
    result = classify_audit_gate({"score": 0.62, "pass_fail": True, "issues": []})
    assert result["gate_status"] == "needs_human"
    assert result["pass_fail"] is False


def test_high_score_approved():
    result = classify_audit_gate({"score": 0.93, "pass_fail": True, "issues": []})
    assert result["gate_status"] == "approved"
    assert result["pass_fail"] is True


def test_exception_result_needs_human():
    result = classify_audit_gate({"score": 0.0, "pass_fail": False, "issues": ["timeout"], "raw": ""}, error=True)
    assert result["gate_status"] == "needs_human"
    assert result["pass_fail"] is False
