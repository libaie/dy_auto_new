# LangChain Business Debate Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the AI video agency debate flow from one fixed critic/defender pair to stage-specific LangChain-backed debate policies with a final arbiter.

**Architecture:** Keep the existing `AgencyOrchestrator`, `AgencySkillRuntime`, invocation persistence, and provider-stage tools. Add one focused debate policy module, then update `agency_debate_audit.py` to look up the policy, run two critic/defender rounds, run one arbiter turn, and persist `agency.debate.v2` trace fields.

**Tech Stack:** Python, FastAPI domain services, SQLAlchemy ORM, pytest, existing LangChain `LangChainAgentRunner`.

---

## Scope Check

This is one implementation slice. It does not change provider submit/query tools, route contracts, database schema, or frontend screens.

## File Structure

- Create `server/app/domains/agency_operations/agency_debate_policy.py`
  - Owns the stage-specific debate policy table.
  - Exports `DebatePolicy`, `DEBATE_POLICIES`, `DEBATE_STAGES`, and `debate_policy_for_stage`.
- Modify `server/app/domains/agency_operations/agency_debate_audit.py`
  - Replaces hard-coded debate experts with policy lookup.
  - Adds the arbiter turn and `agency.debate.v2` trace fields.
- Modify `server/app/domains/agency_operations/agency_orchestrator.py`
  - Imports `DEBATE_STAGES` from the policy module so `story_planning` is debated.
- Modify `server/app/domains/agency_operations/README.md`
  - Documents the new policy module.
- Add `server/tests/test_agency_debate_policy.py`
  - Verifies policy coverage and manifest validity.
- Modify `server/tests/test_agency_debate_audit.py`
  - Verifies stage-specific roles, arbiter pass/block, v2 trace fields, and repair events.
- Modify `server/tests/test_agency_orchestrator.py`
  - Verifies `story_planning` enters debate when debate is enabled.

---

### Task 1: Add Stage Debate Policy

**Files:**
- Create: `server/app/domains/agency_operations/agency_debate_policy.py`
- Test: `server/tests/test_agency_debate_policy.py`

- [ ] **Step 1: Write the failing policy coverage test**

Create `server/tests/test_agency_debate_policy.py`:

```python
from app.domains.agency_operations.agency_manifest import EXPERT_IDS
from app.domains.agency_operations.agency_orchestrator import STAGE_DAG
from app.domains.agency_operations.agency_debate_policy import (
    DEBATE_POLICIES,
    DEBATE_STAGES,
    debate_policy_for_stage,
)


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
```

- [ ] **Step 2: Run the failing policy test**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_debate_policy.py -q`

Expected: FAIL with import error for `agency_debate_policy`.

- [ ] **Step 3: Implement the policy module**

Create `server/app/domains/agency_operations/agency_debate_policy.py`:

```python
"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_debate_policy 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DebatePolicy:
    """业务类：承载 DebatePolicy 相关的数据结构、状态或业务协作。

    类参数：arbiter、critic、defender、focus、policy_id、stage 承载该类的业务配置、状态或数据字段。
    """
    stage: str
    policy_id: str
    critic: str
    defender: str
    arbiter: str
    focus: tuple[str, ...]


DEBATE_POLICIES: dict[str, DebatePolicy] = {
    "story_planning": DebatePolicy(
        stage="story_planning",
        policy_id="story_planning.v1",
        critic="narrative_designer",
        defender="story_generator",
        arbiter="douyin_strategist",
        focus=("整季主线", "逐集差异", "连续性台账", "锁定角色和场景"),
    ),
    "style_lock": DebatePolicy(
        stage="style_lock",
        policy_id="style_lock.v1",
        critic="visual_storyteller",
        defender="image_prompt_engineer",
        arbiter="style_lock_quality_reviewer",
        focus=("角色规则", "场景规则", "参考图准备度", "视觉继承"),
    ),
    "storyboard": DebatePolicy(
        stage="storyboard",
        policy_id="storyboard.v1",
        critic="visual_storyteller",
        defender="narrative_designer",
        arbiter="storyboard_quality_reviewer",
        focus=("可执行分镜", "角色场景锚点", "连续性", "镜头时长"),
    ),
    "image_stage": DebatePolicy(
        stage="image_stage",
        policy_id="image_stage.v1",
        critic="visual_storyteller",
        defender="image_prompt_engineer",
        arbiter="image_stage_quality_reviewer",
        focus=("提示词完整性", "参考图继承", "provider 约束", "风格漂移风险"),
    ),
    "image_review": DebatePolicy(
        stage="image_review",
        policy_id="image_review.v1",
        critic="image_prompt_engineer",
        defender="visual_storyteller",
        arbiter="image_review_quality_reviewer",
        focus=("角色身份", "场景一致", "图片可用性", "图生视频准备度"),
    ),
    "video_stage": DebatePolicy(
        stage="video_stage",
        policy_id="video_stage.v1",
        critic="visual_storyteller",
        defender="short_video_editing_coach",
        arbiter="video_stage_quality_reviewer",
        focus=("片段时长", "动作意图", "首帧继承", "连续性"),
    ),
    "video_review": DebatePolicy(
        stage="video_review",
        policy_id="video_review.v1",
        critic="video_optimization_specialist",
        defender="short_video_editing_coach",
        arbiter="video_review_quality_reviewer",
        focus=("身份漂移", "运动稳定", "镜头意图", "合成准备度"),
    ),
    "compose_preflight": DebatePolicy(
        stage="compose_preflight",
        policy_id="compose_preflight.v1",
        critic="douyin_strategist",
        defender="video_optimization_specialist",
        arbiter="compose_quality_reviewer",
        focus=("剧集完整度", "节奏", "平台适配", "缺失资产"),
    ),
    "compose": DebatePolicy(
        stage="compose",
        policy_id="compose.v1",
        critic="douyin_strategist",
        defender="short_video_editing_coach",
        arbiter="compose_quality_reviewer",
        focus=("最终交付", "剪辑节奏", "音频字幕", "发布适配"),
    ),
}
DEBATE_STAGES = set(DEBATE_POLICIES)


def debate_policy_for_stage(stage: str) -> DebatePolicy:
    """业务函数：处理 debate_policy_for_stage 对应的业务流程、校验或数据转换。

    入参：stage 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        return DEBATE_POLICIES[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported agency debate stage: {stage}") from exc
```

- [ ] **Step 4: Run the policy test**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_debate_policy.py -q`

Expected: PASS.

- [ ] **Step 5: Commit policy module**

```powershell
git add server/app/domains/agency_operations/agency_debate_policy.py server/tests/test_agency_debate_policy.py
git commit -m "feat: add stage debate policy"
```

---

### Task 2: Upgrade Debate Audit To Policy And Arbiter

**Files:**
- Modify: `server/app/domains/agency_operations/agency_debate_audit.py`
- Modify: `server/tests/test_agency_debate_audit.py`

- [ ] **Step 1: Update debate audit tests for arbiter behavior**

Modify `server/tests/test_agency_debate_audit.py`:

```python
class DebateRuntimeResult:
    def __init__(self, status: str, score: float, verdict: str, expert_id: str):
        self.result_status = status
        self.output_summary = {
            "decision": verdict,
            "findings": [expert_id],
            "recommendations": [],
            "required_changes": [],
            "scorecard": {
                "overall_score": score,
                "pass_threshold": 80,
                "verdict": verdict,
                "dimensions": [{"key": "quality", "score": score}],
            },
        }
        self.evidence = []
        self.token_usage = {}
        self.model_config_snapshot = {"provider": "mock"}
```

Update `test_debate_blocks_when_second_round_still_disagrees`:

```python
    calls = []

    async def fake_runtime(**kwargs):
        calls.append((kwargs["role"], kwargs["expert_id"]))
        if kwargs["role"] == "arb":
            return DebateRuntimeResult("failed", 45, "fail", kwargs["expert_id"])
        if kwargs["role"] == "crit":
            return DebateRuntimeResult("failed", 45, "fail", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 92, "pass", kwargs["expert_id"])
```

Add assertions to that test:

```python
    assert trace["debate"]["schema_version"] == "agency.debate.v2"
    assert trace["debate"]["critic_expert_id"] == "visual_storyteller"
    assert trace["debate"]["defender_expert_id"] == "short_video_editing_coach"
    assert trace["debate"]["arbiter_expert_id"] == "video_stage_quality_reviewer"
    assert trace["debate"]["arbiter_invocation_id"]
    assert calls == [
        ("crit", "visual_storyteller"),
        ("def", "short_video_editing_coach"),
        ("crit", "visual_storyteller"),
        ("def", "short_video_editing_coach"),
        ("arb", "video_stage_quality_reviewer"),
    ]
    assert db.query(AgencyExpertInvocation).filter_by(role="arb").count() == 1
```

Update `test_debate_passes_when_second_round_reaches_consensus`:

```python
    assert trace["debate"]["schema_version"] == "agency.debate.v2"
    assert trace["debate"]["arbiter_scorecard"]["verdict"] == "pass"
    assert len(calls) == 5
```

Add a new test:

```python
@pytest.mark.asyncio
async def test_debate_blocks_when_arbiter_passes_without_scorecard(db):
    series = Series(title="Debate Missing Arbiter", logline="case", genre="drama")
    db.add(series)
    db.commit()

    async def fake_runtime(**kwargs):
        if kwargs["role"] == "arb":
            return DebateRuntimeResultWithoutScorecard("passed", kwargs["expert_id"])
        return DebateRuntimeResult("passed", 91, "pass", kwargs["expert_id"])

    trace = await run_debate_audit(
        db,
        series_id=series.id,
        stage="style_lock",
        stage_context={"style_lock": {"locked": True}},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
        runtime_invoke=fake_runtime,
    )

    assert trace["stage_status"] == "blocked"
    assert trace["debate"]["status"] == "consensus_fail"
    assert trace["debate"]["final_verdict"] == "block"
    assert trace["debate"]["missing_scorecards"] == ["arbiter"]
    assert "arbiter" in trace["debate"]["downgrade_reason"]
```

- [ ] **Step 2: Run the updated debate tests to verify failure**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_debate_audit.py -q`

Expected: FAIL because audit still emits v1 trace, four invocations, and fixed defender.

- [ ] **Step 3: Replace hard-coded debate experts with policy lookup**

Modify the imports and constants in `server/app/domains/agency_operations/agency_debate_audit.py`:

```python
from app.domains.agency_operations.agency_debate_policy import (
    DEBATE_STAGES,
    DebatePolicy,
    debate_policy_for_stage,
)
```

Set:

```python
DEBATE_SCHEMA_VERSION = "agency.debate.v2"
```

Remove the old local `DEBATE_STAGES`, `CRITIC_EXPERT_ID`, and `DEFENDER_EXPERT_ID` constants.

- [ ] **Step 4: Add policy and arbiter invocation to `run_debate_audit`**

At the start of `run_debate_audit`, after `common` is built, add:

```python
    policy = debate_policy_for_stage(stage)
```

Use `policy.critic` for critic invocations and `policy.defender` for defender invocations. After `second_defender`, add:

```python
    arbiter = await _invoke_debate_role(
        db,
        orchestrator,
        common,
        stage_context=stage_context,
        round_number=3,
        expert_id=policy.arbiter,
        role="arb",
        opponent_summary={
            "critic": _summary_for_invocation(db, second_critic["id"]),
            "defender": _summary_for_invocation(db, second_defender["id"]),
        },
        policy=policy,
    )
```

Set:

```python
    invocations = [first_critic, first_defender, second_critic, second_defender, arbiter]
```

Read arbiter scorecard:

```python
    arbiter_card, arbiter_has_scorecard = _scorecard_for_invocation(
        db,
        arbiter["id"],
        arbiter["result_status"],
    )
    arbiter_blocks = _result_blocks(arbiter, arbiter_card, arbiter_has_scorecard)
```

Build `missing_scorecards` from `critic`, `defender`, and `arbiter`. Set final state:

```python
    debate_status = "consensus_fail" if arbiter_blocks else "consensus_pass"
    stage_status = "blocked" if arbiter_blocks else "completed"
    final_verdict = "block" if arbiter_blocks else "pass"
```

Add these v2 fields in `trace["debate"]`:

```python
            "policy_id": policy.policy_id,
            "critic_expert_id": policy.critic,
            "defender_expert_id": policy.defender,
            "arbiter_expert_id": policy.arbiter,
            "arbiter_invocation_id": arbiter["id"],
            "arbiter_scorecard": arbiter_card,
```

- [ ] **Step 5: Pass policy into debate role context**

Change `_invoke_debate_role` signature:

```python
    policy: DebatePolicy,
```

Inside its `context["debate"]`, use:

```python
            "role": {"crit": "critic", "def": "defender", "arb": "arbiter"}[role],
            "policy_id": policy.policy_id,
            "critic_expert_id": policy.critic,
            "defender_expert_id": policy.defender,
            "arbiter_expert_id": policy.arbiter,
            "focus": list(policy.focus),
```

Pass `policy=policy` to every `_invoke_debate_role` call.

- [ ] **Step 6: Update downgrade reason for arbiter**

Keep `_downgrade_reason` small:

```python
    if missing_scorecards:
        roles = ", ".join(missing_scorecards)
        return f"{stage} debate missing required scorecard from {roles}"
    return f"{stage} debate arbiter blocked the stage"
```

- [ ] **Step 7: Run debate audit tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_debate_audit.py -q`

Expected: PASS.

- [ ] **Step 8: Commit debate audit upgrade**

```powershell
git add server/app/domains/agency_operations/agency_debate_audit.py server/tests/test_agency_debate_audit.py
git commit -m "feat: arbitrate agency debate by stage policy"
```

---

### Task 3: Wire Orchestrator Debate Stage Coverage

**Files:**
- Modify: `server/app/domains/agency_operations/agency_orchestrator.py`
- Modify: `server/tests/test_agency_orchestrator.py`

- [ ] **Step 1: Add orchestrator story-planning debate test**

First update the existing `test_story_planning_review_uses_story_team_without_debate_roles` so it remains a no-debate unit test:

```python
    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=False)
```

Then update `test_stage_appends_two_round_debate_by_default` to expect the stage policy defender and arbiter:

```python
    assert result["debate"]["schema_version"] == "agency.debate.v2"
    assert calls[-5:] == [
        ("crit", "visual_storyteller"),
        ("def", "narrative_designer"),
        ("crit", "visual_storyteller"),
        ("def", "narrative_designer"),
        ("arb", "storyboard_quality_reviewer"),
    ]
```

Append this test to `server/tests/test_agency_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_story_planning_runs_policy_debate_when_enabled(db):
    calls = []

    async def fake_runtime(**kwargs):
        calls.append((kwargs["stage"], kwargs["role"], kwargs["expert_id"]))
        return RuntimeResult("passed")

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime, enable_debate=True)

    result = await orchestrator.run_story_planning_review(
        db,
        series_id="series-1",
        stage_context={"story_plan": {"episode_count": 3}},
        runtime_config={"provider": "mock", "model": "mock", "api_key": "x"},
    )

    assert result["stage_status"] == "completed"
    assert result["debate"]["schema_version"] == "agency.debate.v2"
    assert ("story_planning", "crit", "narrative_designer") in calls
    assert ("story_planning", "def", "story_generator") in calls
    assert ("story_planning", "arb", "douyin_strategist") in calls
```

- [ ] **Step 2: Run the single orchestrator test to verify failure**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_orchestrator.py::test_story_planning_runs_policy_debate_when_enabled -q`

Expected: FAIL if `story_planning` is still not in `DEBATE_STAGES`.

- [ ] **Step 3: Import debate stages from the policy module**

Modify `server/app/domains/agency_operations/agency_orchestrator.py` inside `_run_stage`:

```python
            from app.domains.agency_operations.agency_debate_policy import DEBATE_STAGES
```

This replaces the current import from `agency_debate_audit`.

- [ ] **Step 4: Run orchestrator tests**

Run: `.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_orchestrator.py::test_story_planning_runs_policy_debate_when_enabled server/tests/test_agency_orchestrator.py::test_orchestrator_runs_reviewers_lead_and_qa_in_order -q`

Expected: PASS.

- [ ] **Step 5: Commit orchestrator coverage**

```powershell
git add server/app/domains/agency_operations/agency_orchestrator.py server/tests/test_agency_orchestrator.py
git commit -m "feat: debate story planning stage"
```

---

### Task 4: Document The Policy Module

**Files:**
- Modify: `server/app/domains/agency_operations/README.md`

- [ ] **Step 1: Add the module summary**

Add this bullet under Current Modules:

```markdown
- `agency_debate_policy.py` owns stage-specific debate role policies for
  critic, defender, arbiter, and business focus checklists.
```

- [ ] **Step 2: Run markdown and status checks**

Run: `git diff -- server/app/domains/agency_operations/README.md`

Expected: diff shows only the new bullet.

- [ ] **Step 3: Commit docs**

```powershell
git add server/app/domains/agency_operations/README.md
git commit -m "docs: document agency debate policy module"
```

---

### Task 5: Final Verification

**Files:**
- Verify: `server/app/domains/agency_operations/agency_debate_policy.py`
- Verify: `server/app/domains/agency_operations/agency_debate_audit.py`
- Verify: `server/app/domains/agency_operations/agency_orchestrator.py`
- Verify: `server/tests/test_agency_debate_policy.py`
- Verify: `server/tests/test_agency_debate_audit.py`
- Verify: `server/tests/test_agency_orchestrator.py`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_debate_policy.py server/tests/test_agency_debate_audit.py server/tests/test_agency_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Chinese comment checker**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts/check_chinese_comments.py --scope all --strict-risk
```

Expected: PASS with zero missing module, risk, declaration, or contract comments.

- [ ] **Step 3: Compile backend domain code**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m compileall server/app/domains/agency_operations
```

Expected: PASS with no syntax errors.

- [ ] **Step 4: Check git state**

Run: `git status --short`

Expected: clean working tree.

## Plan Self-Review

- Spec coverage: Task 1 covers policy matrix and all stages. Task 2 covers LangChain-backed persisted debate invocations, arbiter decision, v2 trace, and repair events. Task 3 covers `story_planning` stage entry. Task 4 covers domain docs. Task 5 covers verification.
- Incomplete-marker scan: no incomplete markers are used as implementation instructions.
- Type consistency: `DebatePolicy.stage`, `policy_id`, `critic`, `defender`, `arbiter`, and `focus` are used consistently across tests and implementation.
