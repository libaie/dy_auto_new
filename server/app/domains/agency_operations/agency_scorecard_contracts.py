from __future__ import annotations

from typing import Any


SCORECARD_SCHEMA_VERSION = "agency.scorecard.v1"
ALLOWED_SCORECARD_VERDICTS = {"pass", "warn", "fail", "block"}
BLOCKING_SCORECARD_VERDICTS = {"fail", "block"}
ALLOWED_REPAIR_INTENTS = {
    "none",
    "prompt_tune",
    "inpainting",
    "regenerate_image",
    "regenerate_video",
    "backtrack_storyboard",
}


def normalize_scorecard(raw: dict[str, Any] | None) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    dimensions = [_normalize_dimension(item) for item in payload.get("dimensions") or [] if isinstance(item, dict)]
    pass_threshold = _clamp_score(payload.get("pass_threshold"), default=80.0)
    overall_score = _overall_score(payload.get("overall_score"), dimensions)
    verdict = _normalize_verdict(payload.get("verdict"), overall_score, pass_threshold)
    repair_intent = str(payload.get("repair_intent") or "none")
    if repair_intent not in ALLOWED_REPAIR_INTENTS:
        repair_intent = "none"

    return {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "overall_score": overall_score,
        "pass_threshold": pass_threshold,
        "verdict": verdict,
        "dimensions": dimensions,
        "repair_intent": repair_intent,
        "confidence": _clamp_unit(payload.get("confidence"), default=0.0),
    }


def scorecard_blocks_stage(scorecard: dict[str, Any] | None) -> bool:
    card = normalize_scorecard(scorecard)
    return (
        card["verdict"] in BLOCKING_SCORECARD_VERDICTS
        or float(card["overall_score"]) < float(card["pass_threshold"])
    )


def _normalize_dimension(raw: dict[str, Any]) -> dict[str, Any]:
    key = str(raw.get("key") or "quality").strip() or "quality"
    threshold = _clamp_score(raw.get("threshold"), default=80.0)
    score = _clamp_score(raw.get("score"), default=0.0)
    return {
        "key": key,
        "label": str(raw.get("label") or key),
        "score": score,
        "threshold": threshold,
        "weight": max(0.0, _float(raw.get("weight"), 1.0)),
        "finding": str(raw.get("finding") or ""),
        "evidence": [str(item) for item in raw.get("evidence") or []],
        "recommendation": str(raw.get("recommendation") or ""),
    }


def _overall_score(raw_score: Any, dimensions: list[dict[str, Any]]) -> float:
    if raw_score is not None:
        return _clamp_score(raw_score, default=0.0)
    if not dimensions:
        return 0.0
    total_weight = sum(float(item.get("weight") or 0.0) for item in dimensions)
    if total_weight <= 0:
        return round(sum(float(item["score"]) for item in dimensions) / len(dimensions), 2)
    weighted = sum(float(item["score"]) * float(item.get("weight") or 0.0) for item in dimensions)
    return round(weighted / total_weight, 2)


def _normalize_verdict(raw_verdict: Any, overall_score: float, pass_threshold: float) -> str:
    verdict = str(raw_verdict or "").strip().lower()
    if verdict in BLOCKING_SCORECARD_VERDICTS:
        return verdict
    if verdict == "warn":
        return "warn"
    if overall_score < pass_threshold:
        return "fail"
    return "pass"


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: Any, default: float) -> float:
    return round(min(100.0, max(0.0, _float(value, default))), 2)


def _clamp_unit(value: Any, default: float) -> float:
    return round(min(1.0, max(0.0, _float(value, default))), 4)
