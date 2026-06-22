from app.domains.agency_operations.agency_debate_policy import (
    DEBATE_POLICIES,
    DEBATE_STAGES,
    debate_policy_for_stage,
)
from app.domains.agency_operations.agency_manifest import EXPERT_IDS
from app.domains.agency_operations.agency_orchestrator import STAGE_DAG


def test_debate_policy_covers_every_agency_stage():
    assert set(DEBATE_POLICIES) == set(STAGE_DAG)
    assert DEBATE_STAGES == set(STAGE_DAG)


def test_debate_policy_experts_exist_in_manifest():
    known_experts = set(EXPERT_IDS)
    for stage in STAGE_DAG:
        policy = debate_policy_for_stage(stage)
        assert policy.stage == stage
        assert policy.policy_id == f"{stage}.v1"
        assert policy.critic in known_experts
        assert policy.defender in known_experts
        assert policy.arbiter in known_experts
        assert policy.focus
