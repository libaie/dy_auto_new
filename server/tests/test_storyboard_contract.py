"""Contract test: dy_auto produces valid storyboard payload."""
import json
import pytest
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent.parent / "tests" / "contract" / "storyboard-schema.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_valid_minimal_payload(schema):
    from jsonschema import validate
    payload = {
        "mode": "storyboard",
        "title": "Test Episode",
        "frames": [{
            "index": 0,
            "narration": "Hello world",
            "image_prompt": "A beautiful landscape",
        }],
    }
    validate(instance=payload, schema=schema)


def test_missing_narration_fails(schema):
    from jsonschema import ValidationError, validate
    payload = {
        "mode": "storyboard",
        "title": "Test",
        "frames": [{"index": 0, "narration": "", "image_prompt": "x"}],
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)


def test_empty_frames_fails(schema):
    from jsonschema import ValidationError, validate
    payload = {"mode": "storyboard", "title": "Test", "frames": []}
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)


def test_invalid_audio_mode_fails(schema):
    from jsonschema import ValidationError, validate
    payload = {
        "mode": "storyboard",
        "title": "Test",
        "frames": [{
            "index": 0,
            "narration": "test",
            "image_prompt": "test",
            "audio_mode": "invalid_mode",
        }],
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)
