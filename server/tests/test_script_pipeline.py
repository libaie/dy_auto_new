from app.db_models import (
    Episode,
    EpisodeScript as DbEpisodeScript,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
    Series,
)


def test_script_sqlalchemy_tables_persist_structured_rows(db):
    series = Series(title="逆袭短剧", logline="她被羞辱后反转身份", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="第一集")
    db.add(episode)
    db.flush()

    script = DbEpisodeScript(
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags_json=["都市逆袭"],
        target_duration_seconds=60,
        status="completed",
    )
    db.add(script)
    db.flush()
    db.add(ScriptDramaticBeat(
        script_id=script.id,
        order_index=1,
        beat_type="HOOK",
        emotional_value="震惊",
        plot_summary="反派摔杯逼女主下跪。",
    ))
    db.add(ScriptSceneOutline(
        script_id=script.id,
        scene_number=1,
        dramatic_beat_type="HOOK",
        location="豪门门口",
        characters_json=["女主", "反派"],
        conflict="反派逼女主下跪。",
        emotional_turn="从羞辱到压迫。",
        visual_mandate="前3秒摔杯。",
    ))
    db.add(ScriptVisualShot(
        script_id=script.id,
        shot_number=1,
        scene_number=1,
        beat_type="HOOK",
        narration="震惊！你竟敢让我跪下？",
        visual_prompt="女主站在雨夜门口，破碎茶杯在脚边。",
        video_prompt="镜头快速推近，女主抬眼。",
        duration=3.0,
    ))
    db.commit()

    saved = db.query(DbEpisodeScript).filter_by(id=script.id).one()
    assert saved.tags_json == ["都市逆袭"]
    assert db.query(ScriptDramaticBeat).filter_by(script_id=script.id).count() == 1
    assert db.query(ScriptSceneOutline).filter_by(script_id=script.id).count() == 1
    assert db.query(ScriptVisualShot).filter_by(script_id=script.id).count() == 1
