import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Episode,
    ImageCreationAsset,
    ImageCreationReviewRecord,
    ImageCreationTask,
    Series,
)


def _create_series_episode(db):
    series = Series(title="Image Workbench Test", logline="A visual test story", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="Pilot")
    db.add(episode)
    db.flush()
    return series, episode


def test_image_creation_task_asset_review_roundtrip(db):
    series, episode = _create_series_episode(db)
    task = ImageCreationTask(
        mode="text_to_image",
        capability_key="doubao_image_generation",
        series_id=series.id,
        episode_id=episode.id,
        prompt="Generate a warm apartment establishing shot.",
        destination_role="episode_cover",
        storage_status="pending",
    )
    db.add(task)
    db.flush()

    asset = ImageCreationAsset(
        task_id=task.id,
        series_id=series.id,
        episode_id=episode.id,
        url="https://cdn.test/image-001.png",
        group_id="cover",
        group_index=0,
        destination_role="episode_cover",
        storage_status="persisted",
    )
    db.add(asset)
    db.flush()

    review = ImageCreationReviewRecord(
        asset_id=asset.id,
        task_id=task.id,
        review_type="ai",
        status="approved",
        score=0.91,
        comment="Composition matches the requested scene.",
        asset_version=asset.version,
    )
    db.add(review)
    db.commit()

    saved = db.query(ImageCreationAsset).filter_by(group_id="cover", group_index=0).one()
    assert saved.destination_role == "episode_cover"
    assert saved.task_id == task.id
    assert saved.storage_status == "persisted"
    assert db.query(ImageCreationReviewRecord).filter_by(asset_id=saved.id).one().status == "approved"


def test_image_creation_tables_include_canonical_contract_columns(test_db):
    inspector = inspect(test_db)
    task_columns = {col["name"] for col in inspector.get_columns("image_creation_tasks")}
    asset_columns = {col["name"] for col in inspector.get_columns("image_creation_assets")}
    review_columns = {col["name"] for col in inspector.get_columns("image_creation_review_records")}

    assert {
        "user_id",
        "source",
        "model_scene",
        "provider",
        "model_id",
        "provider_task_id",
        "external_task_id",
        "progress",
        "target_count",
        "completed_count",
        "failed_count",
        "review_policy",
        "selected_asset_id",
        "selected_asset_version",
        "pixelle_payload_json",
        "request_json",
        "provider_response_json",
    }.issubset(task_columns)
    assert {
        "user_id",
        "asset_kind",
        "storage_path",
        "mime_type",
        "width",
        "height",
        "seed",
        "prompt",
        "model_scene",
        "provider",
        "model_id",
        "variant_index",
        "is_selected",
        "audit_status",
        "ai_score",
        "ai_report_json",
        "manual_review_status",
    }.issubset(asset_columns)
    assert {"reviewer_type", "action", "report_json"}.issubset(review_columns)


def test_image_creation_tables_include_required_fks_and_indexes(test_db):
    inspector = inspect(test_db)
    task_fks = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in inspector.get_foreign_keys("image_creation_tasks")
    }
    asset_fks = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in inspector.get_foreign_keys("image_creation_assets")
    }
    task_indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("image_creation_tasks")
    }
    asset_indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("image_creation_assets")
    }
    review_indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("image_creation_review_records")
    }

    assert task_fks[("user_id",)] == "users"
    assert asset_fks[("user_id",)] == "users"
    assert task_indexes["idx_image_tasks_user"] == ("user_id",)
    assert task_indexes["idx_image_tasks_status_created"] == ("status", "created_at")
    assert asset_indexes["idx_image_assets_task_version"] == ("task_id", "version")
    assert asset_indexes["idx_image_assets_audit_status"] == ("audit_status",)
    assert asset_indexes["idx_image_assets_group"] == ("group_id", "group_index")
    assert asset_indexes["idx_image_assets_source"] == ("source_asset_id",)
    assert review_indexes["idx_image_review_task"] == ("task_id",)
    assert review_indexes["idx_image_review_latest"] == ("asset_id", "asset_version", "is_latest_asset_review")


def test_image_creation_asset_unique_group_slot(db):
    series, episode = _create_series_episode(db)
    task = ImageCreationTask(
        mode="text_to_image",
        capability_key="doubao_image_generation",
        series_id=series.id,
        episode_id=episode.id,
        prompt="Generate a quiet morning street scene.",
    )
    db.add(task)
    db.flush()

    db.add(ImageCreationAsset(
        task_id=task.id,
        slot_key="group-1:1",
        group_id="shot-001",
        group_index=0,
        version=1,
        url="https://cdn.test/shot-001-v1.png",
    ))
    db.commit()

    db.add(ImageCreationAsset(
        task_id=task.id,
        slot_key="group-1:1",
        group_id="shot-001",
        group_index=0,
        version=1,
        url="https://cdn.test/shot-001-v1-duplicate.png",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_image_creation_asset_unique_canonical_group_slot(db):
    series, episode = _create_series_episode(db)
    task = ImageCreationTask(
        mode="text_to_image",
        capability_key="doubao_image_generation",
        series_id=series.id,
        episode_id=episode.id,
        prompt="Generate two grouped image variants.",
    )
    db.add(task)
    db.flush()

    db.add(ImageCreationAsset(
        task_id=task.id,
        slot_key="group-a:0",
        group_id="group-a",
        group_index=0,
        version=1,
        url="https://cdn.test/group-a-slot-a.png",
    ))
    db.commit()

    db.add(ImageCreationAsset(
        task_id=task.id,
        slot_key="different-slot-key",
        group_id="group-a",
        group_index=0,
        version=1,
        url="https://cdn.test/group-a-slot-b.png",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_image_creation_review_latest_unique_per_asset_version(db):
    series, episode = _create_series_episode(db)
    task = ImageCreationTask(
        mode="text_to_image",
        capability_key="doubao_image_generation",
        series_id=series.id,
        episode_id=episode.id,
        prompt="Generate a reviewable concept image.",
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(
        task_id=task.id,
        slot_key="review-slot",
        version=1,
        url="https://cdn.test/review-slot-v1.png",
    )
    db.add(asset)
    db.flush()

    db.add(ImageCreationReviewRecord(
        asset_id=asset.id,
        task_id=task.id,
        review_type="ai",
        reviewer_type="ai",
        status="needs_changes",
        action="request_revision",
        asset_version=1,
        is_latest_asset_review=False,
    ))
    db.add(ImageCreationReviewRecord(
        asset_id=asset.id,
        task_id=task.id,
        review_type="ai",
        reviewer_type="ai",
        status="needs_changes",
        action="request_revision",
        asset_version=1,
        is_latest_asset_review=False,
    ))
    db.add(ImageCreationReviewRecord(
        asset_id=asset.id,
        task_id=task.id,
        review_type="human",
        reviewer_type="human",
        status="approved",
        action="approve",
        asset_version=1,
        is_latest_asset_review=True,
    ))
    db.commit()

    db.add(ImageCreationReviewRecord(
        asset_id=asset.id,
        task_id=task.id,
        review_type="ai",
        reviewer_type="ai",
        status="approved",
        action="approve",
        is_latest_asset_review=True,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_image_creation_asset_unique_default_slot(db):
    series, episode = _create_series_episode(db)
    task = ImageCreationTask(
        mode="text_to_image",
        capability_key="doubao_image_generation",
        series_id=series.id,
        episode_id=episode.id,
        prompt="Generate a single character portrait.",
    )
    db.add(task)
    db.flush()

    db.add(ImageCreationAsset(
        task_id=task.id,
        slot_key="default",
        version=1,
        url="https://cdn.test/default-v1.png",
    ))
    db.commit()

    db.add(ImageCreationAsset(
        task_id=task.id,
        slot_key="default",
        version=1,
        url="https://cdn.test/default-v1-duplicate.png",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
