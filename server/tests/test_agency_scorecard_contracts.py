from app.domains.agency_operations.agency_scorecard_contracts import normalize_scorecard, scorecard_blocks_stage


def test_normalize_scorecard_derives_weighted_overall_and_verdict():
    card = normalize_scorecard({
        "dimensions": [
            {"key": "story", "score": 90, "threshold": 80, "weight": 0.75},
            {"key": "motion", "score": 60, "threshold": 80, "weight": 0.25},
        ],
        "pass_threshold": 80,
    })

    assert card["schema_version"] == "agency.scorecard.v1"
    assert card["overall_score"] == 82.5
    assert card["verdict"] == "pass"
    assert card["repair_intent"] == "none"


def test_scorecard_blocks_stage_for_fail_or_under_threshold():
    fail = normalize_scorecard({"overall_score": 59, "pass_threshold": 80, "verdict": "fail"})
    block = normalize_scorecard({"overall_score": 79, "pass_threshold": 80})
    warn = normalize_scorecard({"overall_score": 80, "pass_threshold": 80, "verdict": "warn"})

    assert scorecard_blocks_stage(fail) is True
    assert scorecard_blocks_stage(block) is True
    assert scorecard_blocks_stage(warn) is False
