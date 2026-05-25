"""Classify audit responses into production gate decisions."""


def classify_audit_gate(result: dict, *, error: bool = False, approve_threshold: float = 0.85) -> dict:
    score = float((result or {}).get("score") or 0.0)
    issues = list((result or {}).get("issues") or [])
    raw_pass = bool((result or {}).get("pass_fail", False))

    if error:
        gate_status = "needs_human"
    elif issues and any("api key" in str(issue).lower() or "missing" in str(issue).lower() for issue in issues):
        gate_status = "needs_human"
    elif not raw_pass:
        gate_status = "needs_human"
    elif score < approve_threshold:
        gate_status = "needs_human"
    else:
        gate_status = "approved"

    return {
        **(result or {}),
        "score": score,
        "issues": issues,
        "gate_status": gate_status,
        "pass_fail": gate_status == "approved",
    }
