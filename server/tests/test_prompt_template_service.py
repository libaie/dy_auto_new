import copy

import pytest

from app.services.prompt_template_service import (
    PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES,
    prompt_template_service,
)


def valid_template_content():
    return {
        "identity": {"role": "advisor", "constraints": ["stay safe"]},
        "disabledWords": "guarantee / cure",
        "semanticGuide": {
            "mission": "Classify useful comments.",
            "highValueSignals": ["specific need"],
            "lowValueSignals": ["empty praise"],
            "keyExamples": ["specific symptom -> high value"],
        },
        "analysis": {
            "intents": ["consult"],
            "scoringRules": ["consult = 40"],
            "replyRules": ["reply naturally"],
            "replyExample": {"good": "I can share a simple idea.", "bad": "No."},
        },
        "localFilter": {"exclude": ["game"], "include": ["health"]},
    }


def test_validate_rewrite_request_accepts_valid_content_and_trims_instruction():
    content = valid_template_content()

    instruction = prompt_template_service.validate_rewrite_request(
        content,
        "  make the tone warmer  ",
    )

    assert instruction == "make the tone warmer"


@pytest.mark.parametrize("instruction", ["", "   ", None, 123])
def test_validate_rewrite_request_rejects_empty_or_non_string_instruction(instruction):
    with pytest.raises(ValueError, match="instruction"):
        prompt_template_service.validate_rewrite_request(
            valid_template_content(),
            instruction,
        )


def test_validate_rewrite_request_rejects_long_instruction():
    with pytest.raises(ValueError, match="too long"):
        prompt_template_service.validate_rewrite_request(
            valid_template_content(),
            "x" * 2001,
        )


def test_validate_rewrite_request_rejects_invalid_current_content():
    content = valid_template_content()
    del content["analysis"]["replyRules"]

    with pytest.raises(ValueError, match="analysis.replyRules"):
        prompt_template_service.validate_rewrite_request(content, "make warmer")


def test_validate_rewrite_request_rejects_oversized_content():
    content = valid_template_content()
    content["semanticGuide"]["keyExamples"] = ["x" * PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES]

    with pytest.raises(ValueError, match="content is too large"):
        prompt_template_service.validate_rewrite_request(content, "make warmer")


def test_validate_rewrite_output_requires_full_valid_template():
    content = valid_template_content()
    output = copy.deepcopy(content)

    assert prompt_template_service.validate_rewrite_output(output) == output

    del output["semanticGuide"]["highValueSignals"]
    with pytest.raises(ValueError, match="semanticGuide.highValueSignals"):
        prompt_template_service.validate_rewrite_output(output)


def test_build_rewrite_prompt_contains_instruction_industry_and_current_json():
    content = valid_template_content()

    prompt = prompt_template_service.build_rewrite_prompt(
        "health",
        content,
        "soften dm stages",
    )

    assert "Industry: health" in prompt
    assert "soften dm stages" in prompt
    assert '"disabledWords": "guarantee / cure"' in prompt
    assert "Return the complete rewritten JSON object only." in prompt
