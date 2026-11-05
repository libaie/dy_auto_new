"""Bounded native System One requests and typed Jev response validation."""
import json
import math

import httpx

from app.services.decision_config import resolve_decision_config

MAX_REQUEST_BYTES = 64 * 1024
_PROBABILITY_SUM_TOLERANCE = 0.01


class DecisionRequestError(ValueError):
    """Invalid caller input; error text never includes input values."""


class DecisionServiceError(RuntimeError):
    """A safe, public error for an unavailable or invalid decision result."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def _content(value):
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, (dict, list)) and bool(value)


def validate_decision_request(payload):
    """Keep the device boundary native, finite JSON and within a fixed budget."""
    invalid = "Invalid decision request"
    if not isinstance(payload, dict) or set(payload) != {"state", "questions"}:
        raise DecisionRequestError(invalid)
    if not _content(payload["state"]):
        raise DecisionRequestError(invalid)
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        raise DecisionRequestError(invalid) from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise DecisionRequestError("Decision request exceeds size limit")

    questions = payload["questions"]
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 16:
        raise DecisionRequestError(invalid)
    for name, question in questions.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(question, dict):
            raise DecisionRequestError(invalid)
        if set(question) - {"type", "instructions", "criteria"} or not _content(question.get("instructions")):
            raise DecisionRequestError(invalid)
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind == "choice":
            if not isinstance(criteria, dict) or not 1 <= len(criteria) <= 255:
                raise DecisionRequestError(invalid)
            for option, description in criteria.items():
                if not isinstance(option, str) or not option.strip() or (description is not None and not _content(description)):
                    raise DecisionRequestError(invalid)
        elif kind == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10 or not all(_content(level) for level in criteria):
                raise DecisionRequestError(invalid)
        elif kind == "noul":
            if criteria is not None and (
                not isinstance(criteria, dict) or not criteria or set(criteria) - {"true", "false"}
                or not all(_content(description) for description in criteria.values())
            ):
                raise DecisionRequestError(invalid)
        else:
            raise DecisionRequestError(invalid)
    return payload


def _number(value, maximum=1):
    # bool is an int in Python. Do not coerce it, strings, or nonfinite floats.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid decision response")
    try:
        valid = math.isfinite(value) and 0 <= value <= maximum
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Invalid decision response")
    return value


def _probabilities(value, expected_keys):
    if not isinstance(value, dict) or set(value) != set(expected_keys):
        raise ValueError("Invalid decision response")
    probabilities = {key: _number(probability) for key, probability in value.items()}
    if not math.isclose(math.fsum(probabilities.values()), 1.0, rel_tol=0, abs_tol=_PROBABILITY_SUM_TOLERANCE):
        raise ValueError("Invalid decision response")
    return probabilities


def validate_decision_response(result, questions):
    """Require a complete answer set and publish only validated native fields."""
    if not isinstance(result, dict) or not isinstance(result.get("model"), str) or not result["model"].strip():
        raise ValueError("Invalid decision response")
    source = result.get("answers")
    if not isinstance(source, dict) or set(source) != set(questions):
        raise ValueError("Invalid decision response")
    answers = {}
    for name, question in questions.items():
        answer = source[name]
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ValueError("Invalid decision response")
        if kind == "noul":
            answers[name] = {"type": kind, "noul": _number(answer.get("noul"))}
            continue
        expected = question["criteria"] if kind == "choice" else [str(index) for index in range(len(question["criteria"]))]
        validated = {
            "type": kind,
            "confidence": _number(answer.get("confidence")),
            "probabilities": _probabilities(answer.get("probabilities"), expected),
        }
        if kind == "choice":
            choice = answer.get("choice")
            if not isinstance(choice, str) or choice not in question["criteria"]:
                raise ValueError("Invalid decision response")
            validated["choice"] = choice
        else:
            validated["score"] = _number(answer.get("score"), maximum=len(question["criteria"]) - 1)
            legend = answer.get("legend")
            expected_legend = {str(index): criterion for index, criterion in enumerate(question["criteria"])}
            if not isinstance(legend, dict) or legend != expected_legend:
                raise ValueError("Invalid decision response")
            validated["legend"] = legend
        answers[name] = validated
    # Gateways may resolve a model slug to a versioned alias. It is metadata, not
    # a reason to discard otherwise valid answers. Usage/extra fields stay private.
    return {"model": result["model"], "answers": answers}


async def request_decision(payload, db=None):
    payload = validate_decision_request(payload)
    try:
        config = resolve_decision_config(db)
    except ValueError:
        raise DecisionServiceError(503, "Decision service unavailable") from None
    if not config["enabled"] or not config["api_key"]:
        raise DecisionServiceError(503, "Decision service unavailable")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as client:
            response = await client.post(
                config["api_url"],
                headers={"Authorization": "Bearer " + config["api_key"], "Content-Type": "application/json"},
                json={"model": config["model"], "state": payload["state"], "questions": payload["questions"]},
            )
    except httpx.TimeoutException:
        raise DecisionServiceError(504, "Decision service timeout") from None
    except httpx.RequestError:
        raise DecisionServiceError(502, "Decision upstream unavailable") from None
    except (ValueError, ImportError):
        raise DecisionServiceError(503, "Decision service unavailable") from None
    if response.status_code != 200:
        raise DecisionServiceError(502, "Decision upstream returned an error")
    try:
        return validate_decision_response(response.json(), payload["questions"])
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise DecisionServiceError(502, "Invalid decision response") from None
