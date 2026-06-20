from app.db.models import Episode, GeneratedVideo, ProductionPlan, ProductionSegment, Series
from app.domains.video_production.production_collection_service import create_collection_from_approved_episodes
from app.domains.video_production.production_plan_service import create_episode_production_plan


def test_multi_episode_plan_retry_and_collection_mocked_e2e(db):
    series = Series(
        title="Mock Long Show",
        logline="Long form test",
        genre="drama",
        story_bible_json={"style_lock": {"locked": True, "version": 1, "style_anchors": ["https://cdn.test/style.png"]}},
    )
    db.add(series)
    db.flush()
    for episode_number in range(1, 4):
        db.add(Episode(
            series_id=series.id,
            episode_number=episode_number,
            title=f"Episode {episode_number}",
            storyboard_json={"frames": [{
                "frame_id": f"ep{episode_number}-frame-1",
                "scene_id": "scene-a",
                "character_ids": ["char-a"],
                "image_prompt": "consistent character",
                "video_prompt": "walk through scene",
                "duration": 12,
                "reference_urls": ["https://cdn.test/char.png"],
            }]},
        ))
    db.commit()

    episodes = db.query(Episode).order_by(Episode.episode_number).all()
    for episode in episodes:
        create_episode_production_plan(db, series.id, episode.id, target_duration_seconds=12, budget_limit=10.0)

    assert db.query(ProductionPlan).count() == 3
    assert db.query(ProductionSegment).count() == 6

    for episode in episodes:
        episode.status = "done"
        episode.video_url = f"episode-{episode.episode_number}.mp4"
        episode.duration_seconds = 12
        db.add(GeneratedVideo(
            keyword=series.title,
            title=episode.title,
            video_path=episode.video_url,
            duration=12,
            status="completed",
            pixelle_task_id=episode.id,
        ))
    db.commit()

    collection = create_collection_from_approved_episodes(db, series.id)

    assert len(collection.included_episode_ids) == 3
    assert collection.duration_seconds == 36
