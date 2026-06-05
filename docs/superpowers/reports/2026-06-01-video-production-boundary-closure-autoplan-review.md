# AI 视频生产边界闭环 Autoplan 评审报告

## Review Target

- Spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-06-01-video-production-boundary-closure-design.md`
- Scope: 真实一键成片闭环、阶段审查闸门、长视频调度稳定性
- Explicitly out of scope: 3D 专家控制台、抖音发布、可视化时间线编辑
- Review date: 2026-06-01

## Verdict

**通过，但必须采用修订后的 spec。**

原始方向正确，但三路评审一致指出：如果不先补 Phase 0、原子预算 reservation、强制 ProviderStageTask、资产持久化后端硬闸门、真实 worker job graph 和 UI 状态矩阵，后续实现仍可能重复提交 provider、重复计费、审批未持久化资产，或者让真实 provider 执行变成后台暗箱。

修订已写回 spec。

## Consensus Table

| Dimension | CEO/Product | Engineering | Design/DX | Consensus |
|---|---|---|---|---|
| Scope focus | 主线正确，但要压住运维产品化 | 同意，先封付费和数据一致性风险 | 同意，不扩视觉和大屏 | Confirmed |
| Cost boundary | unknown cost 必须硬 cap | 必须原子 reservation | 启动前必须展示预算确认 | Confirmed |
| Provider idempotency | 必须避免重复扣费 | ProviderStageTask 必须强制 | stage task rail 必须可见 | Confirmed |
| Asset persistence | 入库视频必须可播放可控 | 后端必须拒绝未持久化审批 | UI 必须禁用并解释原因 | Confirmed |
| Long video | 不承诺全量真实 240 分钟付费生成 | 需要 per-job executor 和 job graph | 每步处理、阻断、修复要可见 | Confirmed |
| Operations | 完整运维产品化后置 | migration safety 要前置 | 需要 `/system/health` 当前状态入口 | Confirmed |

## Required Revisions Applied

1. Added `Autoplan Review Corrections`.
2. Added user-facing `Product Success Criteria`.
3. Added Phase 0 schema and safety gate.
4. Changed cost closure to atomic budget reservation and single actual-cost settlement per provider stage task.
5. Changed ProviderStageTask from optional suggestion to mandatory model.
6. Required Pixelle/provider payloads to carry `external_task_id`.
7. Added Provider/Pixelle response contract.
8. Added backend hard gate for `copy_status != persisted` and `status != review_pending`.
9. Added storage configuration policy.
10. Added per-job long-video executor and job graph materialization rules.
11. Added reject/retry/version rules.
12. Added `/system/health` as first system status route.
13. Added API contract examples.
14. Added UI State Contract matrix.
15. Added concurrency, replay, storage, permission, migration, and UI repair tests.
16. Added Decision Audit Trail.

## Not In Scope

- Full 3D expert control-room enhancement: user explicitly paused this line.
- Douyin publishing: unrelated to closing provider, review, and scheduling risk.
- Visual timeline editor: not required for one-click production closure.
- Full operations dashboard with trends: useful later, but first phase only needs current health and repair actions.
- Real 240-minute paid provider generation: first prove scheduler stability with mocked provider and real short paid smoke.

## What Already Exists

- `VideoProductionRun.run_type` already separates `real_short_e2e`, `mock_series_scale`, and `legacy_episode_run`.
- `mock_series_scale` already proves provider-free scheduling and queue stability.
- `ProductionJob` already has queue, lease, retry wait, pause/resume primitives.
- `ProductionCostEvent` and `production_cost_service` exist but are not wired into real video provider stages.
- `VideoProductionAsset` already has `copy_status` and `checksum`, but stage registration does not enforce persistence.
- `require_role` exists in auth dependencies, but video production routes mostly use `verify_admin_token`.
- Monitor and review pages exist, but repair routes and stage task states are not yet concrete enough.

## Critical Failure Modes

| Failure mode | Current risk | Required control |
|---|---|---|
| Concurrent workers both pass budget check | Provider cost can exceed cap | Atomic budget reservation |
| Provider accepted request but DB write failed | Retry can duplicate paid task | ProviderStageTask with external_task_id |
| Sync endpoint called repeatedly | Actual cost can be counted multiple times | One actual cost event per provider_stage_task_id |
| Provider URL expires before review | Approved asset becomes unavailable | Storage guard before review |
| User approves storage_failed asset via API | Final video can point to missing media | Backend approval rejection |
| Legacy run enters provider path without guards | Budget/idempotency bypass | Prohibit legacy provider path or force same guards |
| Long-video worker uses run-level batch submit | Cannot resume segment-level safely | Per-job stage executor |
| Alembic fails in staging/prod but app continues | Writes happen against wrong schema | Migration health startup block |
| Repair route is plain text | User sees blocked state but cannot recover | Clickable CTA and UI State Contract |

## Recommended Implementation Priority

P0: Schema and safety gate

- ProviderStageTask
- ProviderCostReservation
- storage fields
- review audit fields
- migration health startup policy

P1: Real paid risk closure

- Atomic budget reservation
- provider idempotency
- cost settlement once
- asset persistence hard gate
- real paid confirmation summary

P2: Review and retry closure

- reject/retry/version rules
- downstream job invalidation
- final approval role enforcement
- review payload storage fields

P3: Real worker foundation

- per-job executor
- provider polling/sync
- worker step response
- job graph materialization

P4: Protected operations

- `/system/health`
- config canary
- staging paid smoke report
- migration doctor command

## Final Gate

No user challenge remains. The requested boundary closure direction stands, with the reviewed constraints now embedded in the spec. The next correct step is to create an implementation plan from the revised spec.
