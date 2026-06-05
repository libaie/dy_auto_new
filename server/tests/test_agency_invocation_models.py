from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db_models import AgencyExpertInvocation
from app.services.agency_contracts import (
    AgencyConsoleResponse,
    AgencyDecisionLogItem,
    AgencyExecutionStatus,
    AgencyExpertSummary,
    AgencyInvocationDetail,
    AgencyInvocationResultStatus,
    AgencyInvocationSummary,
    AgencyStageGraphNode,
    AgencyStepStatus,
)


def test_agency_invocation_migration_depends_on_control_plane_convergence():
    server_dir = Path(__file__).resolve().parents[1]
    config = Config(str(server_dir / "alembic.ini"))
    config.set_main_option("script_location", str(server_dir / "alembic"))
    script = ScriptDirectory.from_config(config)

    agency_invocations_revision = script.get_revision("e5f6a7b8c9d0")
    control_plane_revision = script.get_revision("d4e5f6a7b8c9")

    assert agency_invocations_revision is not None
    assert agency_invocations_revision.down_revision == "d4e5f6a7b8c9"
    assert control_plane_revision is not None
    assert script.get_heads() == ["5e6f708192a3"]


def test_agency_invocation_table_shape(test_db):
    columns = {col["name"] for col in inspect(test_db).get_columns("agency_expert_invocations")}
    assert {
        "id",
        "idempotency_key",
        "attempt",
        "retry_of_invocation_id",
        "series_id",
        "run_id",
        "pipeline_run_id",
        "stage",
        "expert_id",
        "role",
        "execution_status",
        "result_status",
        "source_path",
        "source_sha256",
        "error_code",
        "created_at",
        "started_at",
        "finished_at",
    }.issubset(columns)


def test_agency_contract_enums_are_separate():
    assert AgencyExecutionStatus.running == "running"
    assert AgencyInvocationResultStatus.blocked == "blocked"
    assert AgencyStepStatus.warning == "warning"
    summary = AgencyInvocationSummary(
        id="inv-1",
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        execution_status="completed",
        result_status="warn",
        summary="compress the opening setup",
    )
    assert summary.result_status == AgencyInvocationResultStatus.warn


def test_agency_expert_summary_uses_manifest_api_fields():
    assert list(AgencyExpertSummary.model_fields) == [
        "expert_id",
        "name",
        "role_type",
        "source_path",
        "source_commit",
        "sha256",
        "phases",
        "legacy",
    ]
    expert = AgencyExpertSummary(
        expert_id="prompt_engineer",
        name="Prompt Engineer",
        role_type="core",
        source_path="specialized/prompt-engineer.md",
        source_commit="13b8800",
        sha256="abc123",
        phases=["storyboard"],
    )
    payload = expert.model_dump()
    assert payload["sha256"] == "abc123"
    assert payload["legacy"] is False
    assert "source_sha256" not in payload
    assert "invocation_count" not in payload


def test_agency_invocation_summary_uses_public_status_fields():
    assert list(AgencyInvocationSummary.model_fields) == [
        "id",
        "stage",
        "expert_id",
        "role",
        "execution_status",
        "result_status",
        "summary",
        "decision",
        "findings",
        "required_changes",
        "evidence",
        "next_action",
        "legacy",
        "display_scope",
        "duration_ms",
        "error_code",
    ]
    summary = AgencyInvocationSummary(
        id="inv-1",
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        execution_status="completed",
        result_status="passed",
    )
    assert summary.summary == ""
    assert summary.findings == []
    assert summary.required_changes == []
    assert summary.evidence == []
    assert summary.next_action == ""
    assert summary.legacy is False
    assert summary.display_scope == "current_team"
    assert summary.duration_ms == 0
    assert summary.error_code is None


def test_agency_invocation_detail_uses_api_names_not_db_json_names():
    assert list(AgencyInvocationDetail.model_fields) == [
        "id",
        "stage",
        "expert_id",
        "role",
        "execution_status",
        "result_status",
        "summary",
        "decision",
        "findings",
        "required_changes",
        "evidence",
        "next_action",
        "legacy",
        "display_scope",
        "duration_ms",
        "error_code",
        "input_summary",
        "output_summary",
        "source_repo",
        "source_commit",
        "source_path",
        "source_sha256",
        "model_config_snapshot",
        "token_usage",
        "repair_action",
        "repair_route",
        "repair_target_type",
        "repair_target_ids",
        "retry_scope",
    ]
    detail = AgencyInvocationDetail(
        id="inv-1",
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        execution_status="completed",
        result_status="warn",
        source_commit="13b8800",
        source_path="specialized/prompt-engineer.md",
        source_sha256="abc123",
    )
    payload = detail.model_dump()
    assert payload["input_summary"] == {}
    assert payload["output_summary"] == {}
    assert payload["evidence"] == []
    assert payload["source_repo"] == "jnMetaCode/agency-agents-zh"
    assert payload["model_config_snapshot"] == {}
    assert payload["token_usage"] == {}
    assert payload["repair_target_ids"] == []
    assert "input_summary_json" not in payload
    assert "output_summary_json" not in payload
    assert "evidence_json" not in payload
    assert "model_config_snapshot_json" not in payload
    assert "token_usage_json" not in payload
    assert "repair_target_ids_json" not in payload


def test_agency_decision_log_item_uses_current_historical_scope_contract():
    assert list(AgencyDecisionLogItem.model_fields) == [
        "id",
        "invocation_id",
        "stage",
        "expert_id",
        "role",
        "result_status",
        "decision",
        "findings",
        "required_changes",
        "evidence",
        "next_action",
        "error_code",
        "legacy",
        "display_scope",
    ]
    item = AgencyDecisionLogItem(
        id="inv-1",
        invocation_id="inv-1",
        stage="storyboard",
        expert_id="reality_checker",
        role="qa",
        result_status="blocked",
        decision="legacy decision",
        legacy=True,
        display_scope="historical_audit",
    )
    assert item.evidence == []
    assert item.display_scope == "historical_audit"


def test_agency_stage_graph_node_contract_fields():
    assert list(AgencyStageGraphNode.model_fields) == [
        "stage",
        "label",
        "status",
        "reviewers",
        "lead",
        "qa",
        "invocation_ids",
    ]
    node = AgencyStageGraphNode(stage="storyboard", label="Storyboard", status="running")
    assert node.reviewers == []
    assert node.lead is None
    assert node.qa == []
    assert node.invocation_ids == []
    assert node.status == AgencyStepStatus.running


def test_agency_console_response_contract_fields_and_defaults():
    assert list(AgencyConsoleResponse.model_fields) == [
        "ok",
        "series",
        "latest_run",
        "agency_trace_status",
        "expert_team",
        "stage_graph",
        "expert_invocations",
        "decision_log",
        "production_steps",
    ]
    response = AgencyConsoleResponse(
        series={"id": "series-1"},
        agency_trace_status="running",
        expert_team=[],
        stage_graph=[],
        expert_invocations=[],
        decision_log=[],
        production_steps=[],
    )
    assert response.ok is True
    assert response.latest_run is None
