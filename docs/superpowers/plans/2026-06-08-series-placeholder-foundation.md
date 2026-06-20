# Series Placeholder Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a one-sentence series persist as a real multi-episode series and give the UI a repair path when existing series have fewer persisted episodes than `Series.total_episodes`.

**Architecture:** Add a small `series_planning_service` for idempotent placeholder creation and completion semantics. Reuse it from the one-sentence creation path and expose a narrow `POST /api/series/{series_id}/ensure-episodes` endpoint. Update the series detail UI so missing placeholders are repairable and completed pilot episodes do not make a 30-episode series look finished.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vitest.

---

## File Map

- Create `server/app/services/series_planning_service.py`
  - Owns `ensure_episode_placeholders`, `is_series_completed`, and `next_episode_number`.
- Modify `server/app/services/one_sentence_video_service.py`
  - Default one-sentence series to 30 episodes.
  - Create E02..EN placeholders after E01 is created.
- Modify `server/app/routers/series.py`
  - Add `POST /api/series/{series_id}/ensure-episodes`.
  - Return repair metadata in `GET /api/series/{series_id}`.
- Modify `server/tests/test_one_sentence_video.py`
  - Add a failing test proving one-sentence creates 30 persisted episodes.
- Create `server/tests/test_series_planning_service.py`
  - Add service tests for idempotent repair and completion semantics.
- Modify `server/tests/test_series_api.py`
  - Add API test for `ensure-episodes`.
- Modify `web/src/api/series.js`
  - Add `ensureSeriesEpisodes(seriesId)`.
- Modify `web/src/views/SeriesDetailPage.vue`
  - Show `补齐剧集占位` when persisted episodes are below target.
  - After placeholders exist, show `生成第 N 集`.
- Modify `web/src/__tests__/series-detail-agency.test.js`
  - Add failing UI tests for repair action and next-episode wording.

## Task 1: Backend Placeholder Service

**Files:**

- Create: `server/app/services/series_planning_service.py`
- Test: `server/tests/test_series_planning_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
from app.db_models import Episode, Series
from app.services.series_planning_service import (
    ensure_episode_placeholders,
    is_series_completed,
    next_episode_number,
)


def test_ensure_episode_placeholders_creates_missing_episodes_idempotently(db):
    series = Series(title="Broken", total_episodes=3, status="draft")
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="done"))
    db.commit()

    result = ensure_episode_placeholders(db, series.id)
    assert result.created_episode_numbers == [2, 3]

    again = ensure_episode_placeholders(db, series.id)
    assert again.created_episode_numbers == []
    numbers = [
        ep.episode_number
        for ep in db.query(Episode).filter(Episode.series_id == series.id).order_by(Episode.episode_number)
    ]
    assert numbers == [1, 2, 3]


def test_series_completion_requires_all_target_episodes_done(db):
    series = Series(title="Pilot only", total_episodes=3, status="draft")
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="done"))
    db.commit()

    assert is_series_completed(db, series.id) is False
    assert next_episode_number(db, series.id) == 2
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
pytest server/tests/test_series_planning_service.py -q
```

Expected: FAIL because `app.services.series_planning_service` does not exist.

- [ ] **Step 3: Implement minimal service**

Implement:

```python
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db_models import Episode, Series


FINISHED_EPISODE_STATUSES = {"done", "completed"}


@dataclass(frozen=True)
class EpisodePlaceholderResult:
    series_id: str
    target_episode_count: int
    existing_episode_numbers: list[int]
    created_episode_numbers: list[int]


def ensure_episode_placeholders(db: Session, series_id: str) -> EpisodePlaceholderResult:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")
    target = max(1, int(series.total_episodes or 1))
    existing_rows = (
        db.query(Episode)
        .filter(Episode.series_id == series_id)
        .order_by(Episode.episode_number)
        .all()
    )
    existing = {int(ep.episode_number) for ep in existing_rows}
    created = []
    for number in range(1, target + 1):
        if number in existing:
            continue
        db.add(Episode(series_id=series_id, episode_number=number, title=f"Episode {number}", status="pending"))
        created.append(number)
    if created:
        db.commit()
    return EpisodePlaceholderResult(series_id, target, sorted(existing), created)


def is_series_completed(db: Session, series_id: str) -> bool:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")
    episodes = db.query(Episode).filter(Episode.series_id == series_id).all()
    if len(episodes) < int(series.total_episodes or 1):
        return False
    return bool(episodes) and all(ep.status in FINISHED_EPISODE_STATUSES for ep in episodes)


def next_episode_number(db: Session, series_id: str) -> int | None:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("series_not_found")
    episodes = db.query(Episode).filter(Episode.series_id == series_id).all()
    done = {ep.episode_number for ep in episodes if ep.status in FINISHED_EPISODE_STATUSES}
    for number in range(1, int(series.total_episodes or 1) + 1):
        if number not in done:
            return number
    return None
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
pytest server/tests/test_series_planning_service.py -q
```

Expected: PASS.

## Task 2: One-Sentence Series Creates All Placeholders

**Files:**

- Modify: `server/tests/test_one_sentence_video.py`
- Modify: `server/app/services/one_sentence_video_service.py`

- [ ] **Step 1: Write the failing test**

Add assertions to `test_one_sentence_video_creates_locked_storyboard_and_run`:

```python
episodes = db.query(Episode).filter_by(series_id=series.id).order_by(Episode.episode_number).all()
assert series.total_episodes == 30
assert [ep.episode_number for ep in episodes] == list(range(1, 31))
assert episodes[0].id == episode.id
assert all(ep.status == "pending" for ep in episodes[1:])
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
pytest server/tests/test_one_sentence_video.py::test_one_sentence_video_creates_locked_storyboard_and_run -q
```

Expected: FAIL because only one episode exists and `total_episodes` is 1.

- [ ] **Step 3: Implement minimal code**

Change one-sentence creation:

```python
from app.services.series_planning_service import ensure_episode_placeholders

series = Series(
    ...
    total_episodes=30,
    ...
)

...
db.add(episode)
db.flush()
ensure_episode_placeholders(db, series.id)
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
pytest server/tests/test_one_sentence_video.py::test_one_sentence_video_creates_locked_storyboard_and_run -q
```

Expected: PASS.

## Task 3: Repair API

**Files:**

- Modify: `server/app/routers/series.py`
- Modify: `server/tests/test_series_api.py`

- [ ] **Step 1: Write the failing API test**

Add a test that creates a series with `total_episodes=3` and only E01, posts to `/api/series/{id}/ensure-episodes`, and expects E02/E03 to be created.

- [ ] **Step 2: Verify RED**

Run:

```powershell
pytest server/tests/test_series_api.py::TestSeriesAPI::test_ensure_episode_placeholders_repairs_missing_episodes -q
```

Expected: FAIL with 404.

- [ ] **Step 3: Implement endpoint**

Use `ensure_episode_placeholders`; return:

```python
{
    "ok": True,
    "series_id": series_id,
    "target_episode_count": result.target_episode_count,
    "existing_episode_numbers": result.existing_episode_numbers,
    "created_episode_numbers": result.created_episode_numbers,
}
```

- [ ] **Step 4: Verify GREEN**

Run the same pytest command. Expected: PASS.

## Task 4: Series Detail UI Repair and Next Episode

**Files:**

- Modify: `web/src/api/series.js`
- Modify: `web/src/views/SeriesDetailPage.vue`
- Modify: `web/src/__tests__/series-detail-agency.test.js`

- [ ] **Step 1: Write failing UI tests**

Add tests:

```javascript
it('offers to repair missing episode placeholders instead of stranding a pilot-only series', async () => {
  // total_episodes: 30, episodes: [E01 completed]
  // expect button text contains '补齐剧集占位'
})

it('shows the next episode number when placeholders exist', async () => {
  // total_episodes: 30, episodes: [E01 completed, E02 pending]
  // expect button text contains '生成第 2 集'
})
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
npm --prefix web test -- series-detail-agency.test.js --runInBand
```

Expected: FAIL until UI is implemented.

- [ ] **Step 3: Implement minimal UI**

Add `ensureSeriesEpisodes` to `web/src/api/series.js`. In the component:

- `hasMissingEpisodePlaceholders = episodes.length < Number(series.total_episodes || 0)`
- button text returns `补齐剧集占位` when missing placeholders and no runnable episode exists
- clicking repair button calls API then reloads
- when `runnableEpisode` exists, return `生成第 ${runnableEpisode.episode_number} 集`

- [ ] **Step 4: Verify GREEN**

Run the Vitest target again. Expected: PASS.

## Self-Review

Spec coverage for this plan:

- Covered: multi-episode placeholders, idempotent repair, pilot does not complete series, repair API, UI repair action, next-episode wording.
- Not covered in this plan: AI text artifact ledger, approval workflow, stale downstream propagation, artifact workbench, migration/backfill. These require separate plans and TDD slices.

Placeholder scan:

- No TODO/TBD/implement-later placeholders are used as task content.
