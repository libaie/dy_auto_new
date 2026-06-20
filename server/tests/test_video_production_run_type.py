import pytest

from app.db.models import Episode, Series, VideoProductionRun
from app.domains.video_production.video_production_run_types import (
    LEGACY_EPISODE_RUN,
    MOCK_SERIES_SCALE,
    REAL_SHORT_E2E,
    assert_run_type,
    get_run_type,
    is_mock_scale_run,
    is_real_provider_run,
    set_run_type,
    validate_run_type,
)


def _run():
    return VideoProductionRun(series_id="series-1", episode_id="episode-1")


def test_video_production_run_type_defaults_to_legacy(db):
    series = Series(title="Run Type", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()

    run = VideoProductionRun(series_id=series.id, episode_id=episode.id)
    db.add(run)
    db.flush()

    assert run.run_type == LEGACY_EPISODE_RUN
    assert get_run_type(run) == LEGACY_EPISODE_RUN


def test_set_run_type_rejects_unknown():
    run = _run()

    with pytest.raises(ValueError, match="Unsupported video production run type: unknown"):
        set_run_type(run, "unknown")


def test_validate_run_type_rejects_unknown():
    assert validate_run_type(None) == LEGACY_EPISODE_RUN
    assert validate_run_type("") == LEGACY_EPISODE_RUN

    with pytest.raises(ValueError, match="Unsupported video production run type: unknown"):
        validate_run_type("unknown")


def test_assert_run_type_accepts_allowed_type():
    run = _run()
    set_run_type(run, REAL_SHORT_E2E)

    assert_run_type(run, [REAL_SHORT_E2E, MOCK_SERIES_SCALE])


def test_assert_run_type_rejects_disallowed_type():
    run = _run()
    set_run_type(run, MOCK_SERIES_SCALE)

    with pytest.raises(ValueError) as exc_info:
        assert_run_type(run, [REAL_SHORT_E2E])

    message = str(exc_info.value)
    assert MOCK_SERIES_SCALE in message
    assert REAL_SHORT_E2E in message


def test_get_run_type_rejects_malformed_persisted_value():
    run = _run()
    run.run_type = "bad-persisted-value"

    with pytest.raises(ValueError, match="Unsupported video production run type: bad-persisted-value"):
        get_run_type(run)


def test_get_run_type_rejects_object_without_run_type():
    with pytest.raises(ValueError, match="Video production run object is missing run_type"):
        get_run_type(object())


def test_is_real_provider_run_matches_real_run_types():
    run = _run()
    set_run_type(run, REAL_SHORT_E2E)

    assert is_real_provider_run(run) is True
    assert is_mock_scale_run(run) is False


def test_is_mock_scale_run_matches_mock_run_types():
    run = _run()
    set_run_type(run, MOCK_SERIES_SCALE)

    assert is_mock_scale_run(run) is True
    assert is_real_provider_run(run) is False
