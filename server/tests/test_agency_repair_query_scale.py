from sqlalchemy import inspect


def test_production_job_repair_indexes_exist(db):
    indexes = {item["name"] for item in inspect(db.bind).get_indexes("production_jobs")}

    assert "idx_production_jobs_plan_stage_status" in indexes
    assert "idx_production_jobs_stage_created_at" in indexes
