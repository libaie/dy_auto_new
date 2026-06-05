from app.db_models import ImageCreationTask, ImageProductionCostEvent
from app.services.image_production_cost_service import record_actual_cost_event, record_estimated_cost_event


def _task(db):
    row = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        status="running",
        prompt="cost task",
        count=2,
        target_count=2,
        provider="seedance",
        model_id="model-1",
        provider_task_id="provider-task-1",
        estimated_cost_json={"amount": 2.5, "currency": "CNY", "units": {"images": 2}},
    )
    db.add(row)
    db.commit()
    return row


def test_record_estimated_cost_event_is_idempotent(db):
    task = _task(db)

    first = record_estimated_cost_event(db, task)
    second = record_estimated_cost_event(db, task)

    assert first.id == second.id
    rows = db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).all()
    assert len(rows) == 1
    assert rows[0].event_type == "estimate"
    assert rows[0].estimated_cost == 2.5


def test_record_actual_cost_event_reads_provider_usage(db):
    task = _task(db)
    task.provider_task_id = "x" * 120
    task.provider_response_json = {"usage": {"actual_cost": 3.0, "currency": "CNY", "images": 2}}
    db.commit()

    event = record_actual_cost_event(db, task)

    assert event.event_type == "actual"
    assert event.actual_cost == 3.0
    assert event.units_json["images"] == 2
    assert len(event.event_key) > 160


def test_record_actual_cost_event_records_zero_cost(db):
    task = _task(db)
    task.provider_response_json = {"usage": {"actual_cost": 0, "currency": "CNY", "images": 1}}
    db.commit()

    event = record_actual_cost_event(db, task)

    assert event is not None
    assert event.event_type == "actual"
    assert event.actual_cost == 0.0


def test_record_actual_cost_event_skips_when_usage_has_no_cost(db):
    task = _task(db)
    task.provider_response_json = {"usage": {"images": 2}}
    db.commit()

    assert record_actual_cost_event(db, task) is None
    assert db.query(ImageProductionCostEvent).filter(ImageProductionCostEvent.task_id == task.id).count() == 0
