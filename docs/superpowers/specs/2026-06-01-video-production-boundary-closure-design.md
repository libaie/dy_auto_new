# AI 视频生产边界闭环设计

## Summary

本方案用于补齐当前 AI 视频生产链路中尚未闭合的工程边界。下一阶段目标不是继续扩展 3D 专家控制台、抖音发布或可视化时间线编辑，而是让真实一键成片、阶段审查闸门和长视频调度具备生产级约束。

当前系统已经具备 `run_type` 分流、真实短片与 mock 长剧路径隔离、图像/视频/最终视频人工审查闸门、队列 lease 和 mock scale 调度能力。未闭合部分集中在真实费用、provider 幂等、视频资产持久化、真实长视频 worker、审批权限、staging/canary 和迁移健康检查。

## Autoplan Review Corrections

2026-06-01 autoplan 审查后，本方案做出以下收敛：

- 范围保持不扩张：继续只服务真实一键成片闭环、阶段审查闸门、长视频调度稳定性。
- 将完整运维产品化后置：migration doctor、canary、staging smoke 作为真实付费运行保护边界进入规划，但不在第一阶段建设完整运维大屏。
- 将 schema 和启动安全前置为 Phase 0：ProviderStageTask、成本 reservation、资产持久化字段、审查审计字段和 staging/prod migration 阻断必须先落地。
- 将成本边界改为原子预算 reservation：仅校验 `current_cost` 不足以防止并发超卖和重复计费。
- 将 ProviderStageTask 改为强制模型：不得作为可选建议。
- 将资产持久化改为后端硬闸门：前端隐藏按钮不够，服务层必须拒绝未持久化资产审批和最终入库。
- 将真实长视频 worker 明确为 per-job executor：不能复用现有 run-level 批量提交函数直接跑长视频。

## Product Success Criteria

真实一键成片成功不是“后台跑完一次 provider 调用”，而是用户可以完成以下闭环：

1. 用户从一句话或已锁定风格的剧集发起真实短片生产。
2. 启动前看到预算上限、预计费用、最大时长、shot 上限、模型配置和将自动推进到哪个审查闸门。
3. 系统真实提交 provider，但每次提交都有预算 reservation、ProviderStageTask、可见状态和可恢复错误。
4. 系统在图像、视频片段、最终视频三个阶段停在人工审查闸门。
5. 用户可以批准、拒绝、重试和查看新版本影响范围。
6. 最终视频只有在持久化成功并完成最终人工审批后，才写回 `Episode` 和 `GeneratedVideo`，并且可播放。

## Goals

- 真实 provider 调用不会因重复点击、网络抖动或服务重启而重复扣费。
- 每次真实 provider 提交都受预算、模型配置、幂等记录和审查状态约束。
- 进入审查和最终入库的视频资产必须已经持久化到 dy_auto 可控存储。
- 长视频真实调度可以按分段执行、暂停、恢复、重试和停止，不再只停留在 mock 演练。
- 图像、视频片段、最终视频的人工审查动作有明确权限和可追溯审计。
- 上线前有受保护的 staging smoke/canary 流程，数据库迁移失败不能被静默掩盖。

## Non Goals

- 不建设 3D 专家控制台新能力。
- 不建设抖音发布闭环。
- 不建设可视化时间线编辑器。
- 不把真实 240 分钟视频一次性提交给 provider。
- 不绕过人工审查闸门做自动最终审批。
- 不新增独立的媒体库产品，继续复用现有视频生产和资产模型，只有现有结构无法表达边界时才加迁移。

## NOT in Scope

本次工程审查明确排除以下工作，防止实施阶段继续扩张边界：

- 3D 专家人物、房间和动画控制台优化：不影响真实付费提交、审查闸门和长视频调度安全。
- 抖音发布、账号投放和发布后数据回流：属于分发闭环，不是当前生产闭环。
- 可视化时间线、手动剪辑器和轨道编辑器：当前目标是自动生产和审查闸门，不引入编辑器产品。
- 完整运维大屏和长期趋势分析：本阶段只做 migration health、provider canary、paid smoke 和必要监控入口。
- 一次性超长 provider 生成：长视频必须拆成 segment/job 执行，不能绕过分段审查和可恢复调度。
- 自动最终审批：AI 审查只给建议，最终写回 `Episode` 和 `GeneratedVideo` 前必须人工审批。

## Current Baseline

已闭合边界：

- `VideoProductionRun.run_type` 已区分 `real_short_e2e`、`mock_series_scale` 和 `legacy_episode_run`。
- `mock_series_scale` 已禁止进入真实 provider stage。
- 图像、视频片段、最终视频都有人工审查闸门。
- AI 审查只作为建议，最终视频必须人工审批后才写回 `Episode` 和 `GeneratedVideo`。
- 队列已有 `claim_next_job`、lease、`mark_job_completed`、retry wait 和 expired lease 释放能力。
- mock scheduler 可以验证 240 分钟及更长规模的调度稳定性，且不消耗 provider 费用。

未闭合边界：

- 视频生产链路只有正预算校验，没有按阶段记录实际费用和停止超预算任务。
- provider stage 提交缺少强幂等 reservation，异常重试可能重复提交。
- `VideoProductionAsset` 有 `copy_status/checksum` 字段，但 image/video/final 阶段登记时未强制持久化成功。
- 长视频真实 worker 尚未建设，真实 provider 执行仍是短片路径和手动 stage 驱动。
- 审批权限目前偏粗，最终审批、批量审批和普通审查没有独立角色策略。
- provider smoke 是脚本级 opt-in，没有 staging/canary 运行证据和迁移健康阻断。

## What Already Exists And Reuse

以下能力已经存在，实施时应复用或收敛到新边界，避免重复造一套生产系统：

| 已有能力 | 当前用途 | 本方案处理方式 |
|---|---|---|
| `VideoProductionRun.run_type` | 隔离真实短片、mock 长剧和 legacy episode run | 继续作为入口准入和 provider 调用防线，不新建并行 run 类型体系 |
| `ProductionJob` lease/retry wait | 支撑队列领取、失败重试和 expired lease 恢复 | 扩展为 per-job executor 驱动真实长视频，不复用 run-level 批量 provider 提交 |
| 图像、视频、最终视频审查闸门 | 已有人审流转和最终写回前 gate | 增加权限、asset persisted 硬检查、版本影响范围和审计，不重建审查中心 |
| `VideoProductionAsset.copy_status/checksum` | 已有资产持久化字段雏形 | 强制所有可审批 asset 先通过 storage guard，再进入 review |
| 模型配置中心 | 管理 provider、model 和场景配置 | 增加 capability gate 和 real paid canary，不为视频生产另建模型配置页 |
| Pixelle/Seedance provider 客户端 | 已能触发部分外部执行路径 | 只能由 `ProviderStageExecutor` 统一调用，不允许路由或旧 stage 函数直接调用 |
| 生产监控页和 segment detail | 展示 run、tree、review、cost 的部分状态 | 改造成 bounded summary + selected segment detail，避免长视频全量加载 |
| `Episode` 和 `GeneratedVideo` | 最终内容资产库写回目标 | 只允许 final human approval 之后写回，失败时保留可修复状态 |

## Target Architecture

真实视频生产路径必须经过以下边界：

```text
One sentence / Series episode
  -> ProductionPlan
  -> ProductionJob
  -> cost_guard
  -> model_config_guard
  -> provider_stage_task reservation
  -> provider submit or provider sync
  -> asset persistence
  -> AI audit recommendation
  -> human review gate
  -> next stage
  -> final human approval
  -> Episode + GeneratedVideo writeback
```

关键原则：

- 没有预算额度，不提交真实 provider。
- 没有幂等 reservation，不提交真实 provider。
- 已提交但未完成的 provider task，重试时只同步结果，不重复提交。
- 没有持久化成功的资产，不进入人工审查。
- 没有人工审批，不推进下一阶段或最终入库。
- mock 任务永远不能进入真实 provider client。
- 所有真实 provider 调用必须收敛到统一的 `ProviderStageExecutor` 或等价服务；路由、run-level stage 和 worker-step 只能调用该执行边界，不得直接调用 provider client。

### State Ownership Matrix

为避免多套状态互相覆盖，真实生产链路必须遵守以下状态所有权：

| 状态对象 | 拥有者 | 允许推进的状态 | 不允许做的事 | 推进下一层的硬条件 |
|---|---|---|---|---|
| `ProviderStageTask` | `ProviderStageExecutor` | `reserved`、`submitted`、`running`、`sync_required`、`succeeded`、`failed`、`manual_repair_required` | 不得直接把 `ProductionJob` 标记为 completed；不得直接让 asset 进入 review | terminal success、provider asset 可解析、cost 可记录或进入费用 fallback |
| `VideoProductionAsset` | storage guard / asset persistence service | `registered`、`storage_failed`、`review_pending`、`approved`、`rejected`、`superseded` | 不得绕过 `copy_status=persisted` 进入审查；不得覆盖旧版本 | `copy_status=persisted`、checksum/size/storage_path 写入成功 |
| `VideoReviewRecord` | review service | `approve`、`reject`、`regenerate`、`final_approve` | 不得修改 provider task 状态；不得审批 superseded 或未持久化 asset | reviewer role 合法、asset 仍是 latest version、asset 可审查 |
| `ProductionJob` | queue / worker service | `queued`、`leased`、`retry_wait`、`blocked`、`completed`、`failed`、`superseded` | 不得在 asset 未持久化、AI audit 未记录、review gate 未进入时 completed | 当前阶段所有硬条件完成，并且没有下游 gate 阻断 |
| `VideoProductionRun` | run state aggregation service | `draft`、`running`、`image_review_pending`、`video_review_pending`、`final_review_pending`、`completed`、`failed`、`paused` | 不得直接覆盖子状态；不得跳过 review gate 汇总成 completed | 所有必要 job/asset/review 状态满足当前阶段完成条件 |

状态推进规则：

- `ProviderStageTask=succeeded` 只代表外部任务成功，不代表 `ProductionJob=completed`。
- `ProductionJob=completed` 必须等待 provider terminal success、cost recorded、asset persisted、AI audit recorded 和对应 gate 状态写入完成。
- `VideoProductionRun` 是汇总状态，必须从 job、asset、review record 聚合得出，不得作为子状态的唯一事实来源。
- `superseded` asset 不可审批；审批接口必须返回 stale/superseded 错误。
- final writeback 只能由 final approval 后的 run aggregation 触发，且必须再次确认 final asset 已持久化。

### State Contract Implementation

实现时必须集中管理状态常量和转换规则，避免在路由、服务和前端中散落字符串。

要求：

- 新增或扩展统一的 `production_status` / `production_state_contract` 模块，集中定义 `Run`、`Plan`、`Job`、`ProviderStageTask`、`ProviderCostReservation`、`Asset`、`Review` 的状态常量。
- 状态契约必须包含 terminal 状态集合、active 状态集合、可重试状态集合、可审批状态集合和允许转换表。
- 新代码不得在 route handler 中直接写状态字符串；状态推进必须通过状态契约校验函数或专用 service 方法。
- `VideoProductionRun` 汇总状态、`ProductionJob` 执行状态、`VideoProductionAsset` 审查状态不得复用同一个裸字符串集合表达不同语义。
- `ProductionErrorCode` 必须同步扩展本方案新增错误码，例如 `BUDGET_BLOCKED`、`PROVIDER_STAGE_TASK_SYNC_REQUIRED`、`ASSET_STORAGE_FAILED`、`REVIEW_GATE_BLOCKED`、`MIGRATION_HEALTH_BLOCKED`。
- 前端 API adapter 应消费后端返回的状态枚举和 repair action，不在页面组件中重新发明状态判断表。

### Service Organization

新边界服务必须按职责拆分，避免继续把核心逻辑堆进 `video_production_service.py`。

建议文件边界：

- `production_action_result.py`：统一 `ProductionActionResult`、`ProductionRepairableError` 转换和 HTTP detail 序列化。
- `production_state_contract.py`：统一状态常量、状态集合、允许转换表和校验函数。
- `provider_stage_executor.py`：真实 provider 两阶段短事务执行，统一调用 budget、stage task、provider client、storage guard 和 audit。
- `provider_stage_task_service.py`：`ProviderStageTask` 创建/读取、request hash 冲突检测、状态转换和人工补录。
- `provider_capability_service.py`：模型能力矩阵解析、真实付费准入、provider config canary 能力结果。
- `provider_cost_reservation_service.py`：预算 reservation 原子创建、结算、释放、过期和 stale repair 成本统计。
- `asset_storage_guard.py`：外部 URL / Pixelle local path 的安全落库、MIME sniff、checksum、atomic rename 和 retry。
- `production_gate_evaluator.py`：阶段 fan-in 聚合、run 汇总状态和下游 job materialize 判定。
- `production_worker_service.py`：worker-step 入口，负责 lease、batch、调用 executor 和返回 step summary。

`video_production_service.py` 只保留现有兼容编排入口，并逐步委托上述服务；新真实 provider 核心逻辑不得继续直接写入该文件。

### Legacy Stage Function Guard

Phase 1 必须处理现有 run-level stage 函数，避免旧入口绕过新边界。

要求：

- `start_image_stage`、`start_video_stage`、`start_compose_stage` 在真实 provider run type 下只能作为兼容 wrapper 调用 `ProviderStageExecutor`。
- 上述函数不得继续直接调用 Pixelle/provider client，不得直接创建 provider task，不得直接把 provider 原始 URL 写入 asset 或 final writeback。
- 无法安全迁移到 `ProviderStageExecutor` 的旧真实路径必须返回 `INVALID_RUN_TYPE`、`PROVIDER_STAGE_EXECUTOR_REQUIRED` 或等价可修复错误。
- `mock_series_scale` 必须继续走 mock scheduler，且 guard 必须防止 mock run 进入真实 provider client。
- Phase 1 测试必须覆盖旧 API 调用真实 run 时不会绕过 budget/idempotency/storage guard。

## Boundary 1: Cost Closure

### Design

扩展现有 `production_cost_service`，把它从独立工具函数接入真实视频生产阶段。

每个真实 provider stage 执行前：

- 创建原子预算 reservation，而不是只读取 `ProductionPlan.current_cost` 后在内存中判断。
- reservation 写入 `estimated_cost`、`reserved_cost`、`currency`、`provider_stage_task_id`、`expires_at` 和 `status`。
- 读取 `ProductionPlan.budget_limit`、`current_cost` 和所有有效 reservation。
- 根据阶段、模型、帧数、时长和 provider 配置生成 `estimated_cost`。
- 调用预算检查。若 `current_cost + active_reserved_cost + estimated_cost > budget_limit`，阻断 stage，记录 `budget.blocked` 事件，暂停未开始 job。
- 对所有真实 provider run type 执行同一套预算规则。若保留 `legacy_episode_run` 的 provider 兼容路径，它也必须走 budget/idempotency/storage guard；否则必须禁止 legacy run 进入 provider stage。

原子性要求：

- `ProviderStageTask` 和 `ProviderCostReservation` 必须在同一个数据库事务中创建或读取。
- 预算检查、active reservation 汇总、reservation 写入必须处在同一个不可拆分的临界区内。
- MySQL 生产环境必须锁定对应 `ProductionPlan` 行，例如 `SELECT ... FOR UPDATE`，再计算 `current_cost + active_reserved_cost + estimated_cost`。
- SQLite 开发环境必须使用 `BEGIN IMMEDIATE` 或服务层串行锁模拟同一临界区，避免并发测试误判。
- `provider_stage_task_id` 在 reservation 表中必须唯一；同一个 ProviderStageTask 只能有一个 active reservation。
- reservation 状态只允许 `reserved -> settled`、`reserved -> released`、`reserved -> expired`、`reserved -> blocked` 的单向流转，不得从 terminal 状态回到 active。

reservation 生命周期：

- `reserved` 且 `ProviderStageTask` 尚未提交 provider、没有 `provider_task_id` 时，允许由 worker-step 或 sweeper 根据 `expires_at` 自动转为 `expired`。
- plan pause、job cancel 或用户停止任务时，只有尚未提交 provider 的 reservation 可以转为 `released`。
- 一旦 provider 已提交，或 `ProviderStageTask.provider_task_id` 已存在，reservation 不得静默过期或释放。
- 已提交 provider 但尚未结算费用的 reservation 必须保持 active，或转入 `manual_repair_required`，并计入 `stale_needs_repair_cost`。
- provider terminal success 后，reservation 只能转为 `settled`。
- provider terminal failed 且 provider 明确无费用时，reservation 可以转为 `released_after_terminal_no_cost`。
- 每次 `expired`、`released`、`released_after_terminal_no_cost` 或 `manual_repair_required` 都必须写 `ProductionAuditEvent`。
- 监控页必须区分 `active_reserved_cost`、`settled_cost`、`stale_needs_repair_cost` 和 `released_cost`。

每个真实 provider stage 完成后：

- 从 provider/Pixelle 响应中读取 usage 或 cost。
- 写入 `ProductionCostEvent`。
- 累加 `ProductionPlan.current_cost`。
- 将对应 budget reservation 标记为 `settled`。
- 同一个 `provider_stage_task_id` 只能记录一次 actual cost event。重复 sync 必须返回已有 cost event，不得再次累加 `ProductionPlan.current_cost`。
- 如果实际费用超过预算，暂停后续未开始任务并要求用户处理。

如果 provider 无法返回统一 usage 字段，第一版可以使用估算费用作为实际费用的保守 fallback，但必须把 provider response 中的 usage snapshot 脱敏保存，方便后续校准。

### Required States

- `budget_status=ok`
- `budget_status=unknown_estimate_requires_cap`
- `budget_status=blocked`
- `budget_status=exhausted_after_actual_cost`

`unknown_estimate_requires_cap` 不允许静默提交真实 provider。只有用户设置显式硬预算、确认最大 duration、shot 上限和本阶段最大可消耗额度后，才允许继续。

### UX

监控页显示：

- 当前预算上限
- 已消耗费用
- 本阶段预计费用
- 已 reservation 但尚未结算的费用
- 阻断原因
- 修复动作：提高预算、减少分段、切换模型或停止任务

## Boundary 2: Provider Idempotency

### Design

引入 provider stage task reservation。`ProviderStageTask` 是强制数据模型，不是可选建议。现有 `ProductionJob.idempotency_key` 只能保证入队幂等，不能表达 provider request、provider task 状态、request hash 冲突、成本 reservation 和 task id 写库失败恢复。

强制结构：

```text
ProviderStageTask
  id
  run_id
  production_plan_id
  production_job_id
  stage
  target_type
  target_id
  asset_version
  model_config_id
  model_config_version
  idempotency_key
  provider
  model_name
  provider_task_id
  status
  request_hash
  request_snapshot_json
  response_summary_json
  error_code
  error_message
  manual_repair_required
  created_at
  updated_at
```

幂等键规则：

```text
run_id + stage + target_type + target_id + asset_version + model_config_id + model_config_version + request_hash
```

约束：

- `idempotency_key` 必须唯一。
- `run_id + stage + target_type + target_id + asset_version + model_config_id + model_config_version + request_hash` 必须唯一或在服务层做强冲突检测。
- 同一个 `ProviderStageTask` 只能关联一个 active provider task。
- Pixelle/provider 请求必须携带 `external_task_id = ProviderStageTask.id` 或等价 client request id。
- Pixelle stage client 的 image/video/compose payload 必须传递该 external task id，不能只传 `external_run_id`。
- 真实付费 provider 必须支持按 `external_task_id` 或等价 client request id 查询，或至少支持人工补录 `provider_task_id` 后继续 sync；两者都不支持的 provider 不能进入真实付费链路，只能用于 mock、dry-run 或受限 smoke。

提交流程：

1. 先创建或读取 reservation。
2. 如果 reservation 已有 `provider_task_id`，只同步 provider 状态。
3. 如果 reservation 是 terminal success，直接复用结果。
4. 如果 reservation 是 terminal failed 且 retryable，创建新版本或按 retry 策略重试。
5. 只有 reservation 成功落库且状态为 `reserved` 时才允许调用 provider。
6. provider 返回 task id 后立即更新 reservation。

### Failure Handling

- DB reservation 失败：不调用 provider。
- provider 已返回 task id 但写库失败：下一次启动必须能通过 `external_task_id` 查询或进入可见的人工补录流程，不能再次提交 provider。
- provider 429/5xx：进入 retry wait，不重复创建任务。
- provider 4xx：标记 failed，需要用户修复 prompt/model 参数。
- provider 不支持 external task 查询且无法人工补录：provider config canary 必须标记为 `blocked_for_real_provider`，真实生产入口不得选择该配置。

### Provider Recovery Admission

真实 provider 准入必须满足以下恢复能力：

1. 调用 provider 前，`ProviderStageTask` 必须已经落库并处于 `reserved`。
2. provider 请求必须携带 `external_task_id=ProviderStageTask.id` 或 provider 支持的等价幂等键。
3. provider 返回 `provider_task_id` 后，必须立即在同一恢复流程中写回 `ProviderStageTask`。
4. 如果 `provider_task_id` 写库失败，任务必须进入 `manual_repair_required`，并在监控页显示补录入口。
5. 人工补录 `provider_task_id` 后，只允许 sync 该 provider task，不允许重新 submit。
6. 若 provider 不能按 external id 查询，也不支持补录后查询 task，则该 provider 配置不得用于真实付费 run。

### ProviderStageExecutor Transaction Model

`ProviderStageExecutor` 必须使用短事务两阶段执行，外部网络 I/O 不得发生在预算锁、plan 行锁或 stage task 行锁持有期间。

第一阶段，事务内：

- 锁定 `ProductionPlan`，计算预算并创建或读取 `ProviderCostReservation`。
- 创建或读取 `ProviderStageTask`，校验 request hash、asset version、model config version 和 run type。
- 将 task 状态推进到 `reserved` 或读取已有 terminal/sync 状态。
- 提交事务，释放数据库锁。

第二阶段，事务外：

- 对 `reserved` 且无 `provider_task_id` 的 task，先按 `external_task_id` 查询 provider 是否已有任务；查到则进入 sync，不查到才 submit。
- 调用 provider submit/sync，并携带 `external_task_id=ProviderStageTask.id`。
- provider 返回后开启新事务，写回 `provider_task_id`、`status`、`response_summary_json`、cost event 和后续 asset persistence 状态。

恢复规则：

- 第一阶段完成但第二阶段未执行：下次 worker 可继续处理该 `reserved` task。
- provider 调用成功但写回失败：下次 worker 必须先按 `external_task_id` 查询或进入人工补录，不得直接重新 submit。
- 任意外部 timeout 不得导致数据库事务长时间占锁；错误写回使用新事务记录为 `retry_wait` 或 `manual_repair_required`。

### Provider/Pixelle Response Contract

`get_stage_task` 和 stage submit 响应必须规范化为以下摘要，供成本、幂等、worker 和前端统一消费：

```json
{
  "provider_task_id": "task-id",
  "external_task_id": "provider-stage-task-id",
  "status": "queued|running|succeeded|failed|cancelled",
  "terminal": true,
  "retryable": false,
  "usage": {
    "estimated_cost": 0.12,
    "actual_cost": 0.1,
    "currency": "CNY",
    "units": {"frames": 4, "seconds": 20}
  },
  "assets": [],
  "error": {
    "code": "PROVIDER_RATE_LIMITED",
    "message": "sanitized message"
  }
}
```

缺少 usage 时必须返回 `estimate_status=unknown` 和原因；缺少 terminal 状态时不得标记 job completed。

### Provider Capability Gate

每个可用于视频生产的模型配置必须声明能力矩阵。真实生产入口、worker 和 `ProviderStageExecutor` 都必须以能力矩阵作为准入依据，不能只检查 API key、base URL 和 model id 是否存在。

建议能力字段：

```json
{
  "provider": "volcengine_ark",
  "model_identifier": "doubao-seedance-2.0",
  "supports_external_task_id": true,
  "supports_task_query": true,
  "supports_cancel": true,
  "returns_usage": false,
  "returns_asset_url": true,
  "supports_text_to_image": false,
  "supports_image_to_image": false,
  "supports_image_to_video": true,
  "supports_video_compose": false,
  "max_duration_seconds": 15,
  "max_reference_images": 9,
  "max_concurrent_tasks": 2,
  "real_paid_allowed": true,
  "real_paid_block_reason": ""
}
```

Stage 准入规则：

- `image_generation` 必须满足 `supports_text_to_image` 或对应图像生成场景能力，且 `returns_asset_url=true`。
- `video_generation` 必须满足 `supports_image_to_video=true`、`returns_asset_url=true`，并且 `max_duration_seconds` 覆盖当前 segment duration。
- `compose` 必须满足 `supports_video_compose=true`；若最终合成由 Pixelle 本地执行，则 Pixelle adapter 必须声明等价能力。
- 所有真实付费 stage 必须满足 `real_paid_allowed=true`、`supports_external_task_id=true`，并且 `supports_task_query=true` 或支持人工补录后 sync。
- `returns_usage=false` 时不得静默放行，必须进入 `estimate_status=unknown` 或使用显式硬预算 fallback。

前端和后端规则：

- 一句话成片和剧集生产入口只展示满足当前 stage 必需能力的模型配置。
- 不满足能力的模型配置可以用于 mock、dry-run、配置测试或受限 smoke，但不得进入真实付费 run。
- provider config canary 必须输出能力矩阵检查结果和 `real_paid_block_reason`，系统状态页展示阻断原因。

## Boundary 3: Asset Persistence

### Design

视频生产资产必须经过 storage guard。

provider 返回 image/video/final asset 后：

- 将 URL 或 Pixelle local path 复制到 dy_auto 受控目录。
- 计算 checksum 和 size。
- 写入 `local_path`、`storage_path`、`checksum`、`size_bytes`、`copy_status`、`source_url`、`provider_response_summary_json`。
- 只有 `copy_status=persisted` 的资产才能进入 `review_pending`。
- provider 原始 URL 只作为 source 保存，不得直接写入 `Episode.video_url` 或作为最终库资产路径。
- AI audit、human review、compose input 和 final writeback 都只能使用 dy_auto storage-backed URL/path。
- 服务层必须拒绝审批 `copy_status != persisted` 或 `status != review_pending` 的所有 asset 类型。前端隐藏或禁用按钮只是体验层，不是安全边界。

失败处理：

- provider 返回空 URL：资产状态 `failed`，不进入审查。
- copy 失败：资产状态 `storage_failed`，提供重试持久化动作。
- checksum 失败：资产状态 `storage_failed`，不得审批。
- final video 持久化失败：不得写回 `Episode.video_url` 或 `GeneratedVideo`。

### Storage Policy

建议路径：

```text
server/app/static/video-production/
  runs/{run_id}/
    image/{frame_id}/v{version}.png
    video/{segment_id}/v{version}.mp4
    final/v{version}.mp4
```

路径是默认策略，不是硬编码唯一策略。需要配置：

- storage root
- public URL prefix
- 允许的 MIME 类型
- 单文件 size 上限
- checksum 算法，默认 sha256
- 持久化重试次数和幂等策略
- 孤儿文件清理策略

### Storage Guard Protocol

资产持久化不得直接把 provider URL 或 Pixelle local path 写为最终资产路径，必须经过安全落库协议。

下载和复制规则：

- 外部 URL 只允许 `https://`，除非本地开发显式开启 `http://localhost` allowlist。
- 禁止下载内网地址、本机地址、`file://`、相对路径和未配置 allowlist 的协议。
- Pixelle local path 必须解析为绝对路径，并且必须位于配置的 Pixelle output root 内；路径解析后若越界，直接标记 `storage_failed`。
- 下载必须设置连接超时、读取超时、最大字节数、最大重定向次数和允许 MIME 类型。
- 下载到临时文件，先校验 `Content-Type`、MIME sniff、扩展名、文件大小、checksum 和可读性。
- provider 返回 HTML、JSON 错误页、空文件或 MIME 与 stage 不匹配时，不得入库。
- 校验通过后使用 atomic rename 移动到最终 `storage_path`，再写入 `copy_status=persisted`。
- 同一 asset version 的持久化重试必须复用同一目标路径或清理旧临时文件，避免孤儿文件堆积。
- 持久化失败必须写入 `storage_error_json`，包含脱敏 URL/path、错误码、可重试性和下一步修复动作。

只有临时文件完整校验通过并完成 atomic rename 后，资产才允许进入 `review_pending`。

## Boundary 4: Real Long Video Worker

### Design

在 mock scheduler 的 queue/lease 基础上建设真实 worker。它不是一次性生成长视频，而是按分段推进。

真实 worker 不复用当前 run-level `start_image_stage`、`start_video_stage`、`start_compose_stage` 批量提交函数。需要新增 per-job stage executor，一次只处理一个 segment 或有限 segment batch。

Worker 循环：

```text
release_expired_leases
claim_next_job(plan_id, stage)
  -> check plan status
  -> check budget
  -> check review gate
  -> reserve provider stage task
  -> submit or sync provider task
  -> persist asset
  -> AI audit
  -> stop at human gate
  -> mark job completed or retry_wait
```

长视频阶段：

- storyboard segmentation
- image generation jobs
- image review gate
- video generation jobs
- video review gate
- compose jobs
- final review gate
- final writeback

Job graph 规则：

- storyboard/shot/segment 生成后，先 materialize image generation jobs。
- image job 完成条件：provider terminal success、cost recorded、asset persisted、AI audit recorded、asset 进入 review gate。
- image review 通过后，才 materialize 对应 segment 的 video generation job。
- image 被拒绝时，旧 asset 进入 rejected，相关下游 video/compose job 必须保持 blocked 或 superseded，不得继续使用旧资产。
- video job 完成条件：provider terminal success、cost recorded、asset persisted、AI audit recorded、asset 进入 review gate。
- video review 通过后，才允许 materialize compose job。
- compose job 完成条件：final video terminal success、cost recorded、asset persisted、AI audit recorded、进入 final review gate。
- final approval 通过后才 writeback。
- 未审批 segment 不得生成 video 或 compose job。

### Aggregate Gate Evaluator

长视频每个阶段都必须由 aggregate gate evaluator 判定是否允许推进下一阶段，不能由单个 job 完成事件直接推进 run。

聚合输入：

- 当前 plan/run/stage 的 required target 数量。
- 每个 `ProductionJob` 的 `queued`、`leased`、`retry_wait`、`blocked`、`failed`、`completed`、`superseded` 状态。
- 每个目标对应 `ProviderStageTask` 的 terminal 状态。
- 每个目标对应 asset 的 `copy_status`、`status`、`version`、`latest` 标记。
- 每个目标对应 review record 的最新人工决策。

推进规则：

- 只有当前阶段所有 required targets 都满足通过条件，才允许 materialize 下一阶段 jobs。
- 任一 required target 处于 `storage_failed`、`manual_repair_required`、`retry_wait`、`blocked` 或 `failed` 时，run 不得进入下一阶段。
- 部分完成时，run 必须进入 `*_partial`、`*_blocked` 或等价可见状态，而不是标记为阶段完成。
- 被 `superseded` 的旧 target 不计入通过条件，但必须有 latest version 接替；否则该 target 仍然阻断。
- 监控页必须显示阻塞 segment/asset/job 列表、阻断原因和下一步修复动作。
- aggregate evaluator 的结果必须写入 `ProductionAuditEvent` 或等价可追踪事件，方便定位 run 为何未推进。

### Operating Model

第一版 worker 可以是 API/manual step 驱动，后续再接后台 daemon。设计上必须保证：

- 每次 step 只处理有限 batch。
- 每个 job 都可重试。
- plan 可暂停和恢复。
- leased job crash 后可释放。
- 任何阶段不得越过审查 gate。
- 每次 step 返回 processed、blocked、retry_wait、failed、next_gate、next_repair_action。

### Scale

真实长视频不以“直接生成 240 分钟”为目标，而以多 episode、多 scene、多 segment 的可恢复调度为目标。240 分钟漫剧应拆成大量分段和 episode-level compose。

第一版真实 provider 只承诺最小 segment 样本和 60-90 秒短片闭环。240 分钟及以上规模继续用 mocked provider 验证调度稳定性，不承诺全量真实付费生成。

## Boundary 5: Review Permissions And Audit

### Design

保留现有审查记录，但强化权限语义。

角色建议：

- `video_reviewer`: 可审查 image 和 video segment。
- `final_video_approver`: 可最终审批并入库。
- `production_admin`: 可批量处理 mock 审查、暂停/恢复计划、修改预算。

规则：

- real run 禁止批量 approve。
- final video 永远禁止批量 approve。
- final approval 必须有 `final_video_approver` 或 `production_admin`。
- 审查记录必须保存 reviewer id、role、action、comment、asset snapshot、model trace summary。

第一版不要求完整 RBAC 管理 UI，但后端必须有硬校验：

- `video_reviewer` 或 `production_admin` 可审批 image/video segment。
- `final_video_approver` 或 `production_admin` 可最终审批 final video。
- 本地开发环境可让 admin 拥有全部权限。
- staging/prod 不允许仅凭普通登录 token 执行 final approval。

### Reject, Retry, Version Rules

- 拒绝 image asset 后，该 frame/segment 的 video job 和 compose job 必须保持 blocked 或 superseded。
- 拒绝 video segment 后，compose job 必须保持 blocked 或 superseded。
- 拒绝 final video 后，run 回到 `video_segments_approved` 或等价状态，允许重新 compose。
- 重试必须创建新 asset version，不得覆盖旧 asset。
- 新 version 必须使用新的 ProviderStageTask idempotency key，但可继承同一 production segment 和 reference context。
- 重试仍消耗预算，必须重新做 budget reservation。
- 已被 superseded 的 asset 不可审批，审批接口必须返回 stale/superseded 错误。
- 审查记录必须保存 `reviewer_role`、`action`、`asset_snapshot_json`、`model_trace_summary_json`。

## Boundary 6: Staging, Canary, Migration Health

本边界的第一版目标是保护真实付费运行，不是建设完整运维产品。完整趋势图、历史对比和独立运维大屏后置。

### Provider Smoke

真实 provider smoke 必须满足：

- staging 环境标记。
- `DY_AUTO_ALLOW_REAL_PROVIDER_E2E=1`。
- 显式预算上限。
- 显式最大 shot 数。
- 显式最大 duration。
- 只允许测试白名单模型配置。
- 输出 smoke report，包含 run id、provider task ids、费用、资产持久化状态、审查状态。

### Canary

Canary 不自动消费大额 provider 费用。建议分层：

- config canary: 检查模型配置、base URL、API key 存在性和 schema。
- dry-run canary: 不调用 provider，只生成 request payload 和预算估算。
- paid smoke: 显式人工触发，最小 shot，最小预算。

### Migration Health

启动时 Alembic 失败不能只 warning 后继续生产写入。建议：

- 开发环境允许 warning + create_all。
- staging/prod 环境 migration 失败直接阻断启动。
- 新增 migration doctor 命令，输出当前 revision、head revision、缺失列、未知 revision 和修复建议。

开发落地：

- 命令：`python -m app.scripts.migration_doctor --json`。
- 输出字段：`database_url_type`、`current_revision`、`head_revision`、`is_at_head`、`missing_tables`、`missing_columns`、`unknown_revision`、`startup_policy`、`repair_actions`。
- 环境策略：`DY_AUTO_ENV=dev` 允许 warning；`DY_AUTO_ENV=staging|prod` 必须阻断启动。
- 前端第一版入口：系统状态页 `/system/health`，只显示 migration health、provider config canary、最近一次 paid smoke report，不做趋势大屏。

## API Surface

新增或调整：

- `GET /api/video-production/runs/{run_id}/costs`
  - 返回 actual cost、estimated next cost、budget status、block reason。
- `POST /api/video-production/runs/{run_id}/worker-step`
  - 真实 worker step，受权限保护，支持 batch size。
- `GET /api/video-production/runs/{run_id}/stage-tasks`
  - 查看 provider stage task reservation 和 provider task 状态。
- `POST /api/video-production/assets/{asset_id}/persist-retry`
  - 重试资产持久化。
- `POST /api/video-production/smoke/real-provider`
  - staging 受保护 smoke，不用于普通用户生产入口。
- `GET /api/system/migration-health`
  - 返回 migration health summary。

### Performance Boundaries

长视频链路的所有列表和轨道 API 必须有明确分页、过滤和索引要求，避免 240 分钟及更长内容把监控页或 worker 拖垮。

API 上限：

- `page_size` 默认 50。
- 普通列表最大 `page_size=100`。
- 仅系统内部 worker 或 smoke 可使用最大 `page_size=200`，且必须显式传参。
- 生产树、stage task rail、review items、audit events、cost events、asset history 都必须分页，不得提供无上限全量返回。
- 监控页不得一次性拉全量 segment、stage task 或审计事件；默认只拉当前页、当前阻塞项和被选中 segment 详情。

Phase 0 migration 必须补核心索引：

- `ProductionJob(plan_id, status, stage, scheduled_at, retry_after)`
- `ProductionJob(lease_id, leased_until)`
- `ProviderStageTask(run_id, stage, status, target_id)`
- `ProviderStageTask(idempotency_key)` unique
- `ProviderStageTask(provider_task_id)`
- `ProviderCostReservation(plan_id, status, provider_stage_task_id)`
- `ProviderCostReservation(expires_at, status)`
- `VideoProductionAsset(run_id, asset_type, status, is_latest, production_segment_id)`
- `VideoProductionAsset(provider_stage_task_id)`
- `VideoReviewRecord(run_id, asset_id, created_at)`
- `ProductionAuditEvent(run_id, event_type, created_at)`

查询规则：

- gate evaluator 只能按阶段和 required targets 做聚合查询，不得逐 segment 触发 N+1 asset/review 查询。
- stage task rail 默认只返回当前 stage 和异常 task；查看全部 task 必须分页。
- cost rail 使用聚合查询或增量 summary，不得每次扫描全量 cost event 后再在 Python 中汇总。
- segment detail 才加载 asset history 和 review history，生产树列表只返回摘要。

### Provider Throttle And Backoff

worker 必须按 provider、model 和 stage 做并发控制，避免长视频分段批量触发时把真实 provider 打爆或造成成本抖动。

并发规则：

- provider capability 中的 `max_concurrent_tasks` 是真实 submit 的硬上限。
- `ProviderStageExecutor` 在 submit 前必须统计同 provider、model、stage 的 active `ProviderStageTask` 数量。
- active task 包含 `submitted`、`running`、`sync_required`、`manual_repair_required` 中尚未 terminal 的任务。
- 超过上限时，不得创建新的 provider task；对应 job 进入 `retry_wait`，并返回 `PROVIDER_THROTTLED` 或等价可修复结果。
- worker-step 的 `batch_size` 不能绕过 provider/model 并发上限。
- 不同 provider/model 的并发额度独立计算，避免低成本 mock 或 dry-run 占用真实付费 provider 配额。

退避规则：

- provider 429、限流错误和临时 5xx 使用指数退避加 jitter。
- 已有 `ProviderStageTask` 的重试只允许 sync 或等待，不得重新 submit。
- 退避状态必须写入 job 的 `retry_after`、stage task 的 `error_code/error_message` 和审计事件。
- 连续超出 provider 限流阈值时，run/plan 进入可见的 provider throttle 状态，等待用户降低并发、切换模型或暂停任务。

前端可见性：

- 监控页必须显示 provider throttle 状态、当前 active task 数、能力矩阵并发上限、下一次 retry 时间和修复动作。
- worker-step 返回中必须区分 `retry_wait` 是预算阻断、provider 限流还是人工修复阻断。

### API Contracts

`POST /api/video-production/runs/{run_id}/worker-step`

请求：

```json
{
  "batch_size": 5,
  "stage": "image_generation",
  "dry_run": false
}
```

响应：

```json
{
  "ok": true,
  "lease_id": "server-generated-lease",
  "processed": 2,
  "blocked": 1,
  "retry_wait": 1,
  "failed": 0,
  "next_gate": "image_review",
  "next_repair_action": "打开图像审查",
  "events": []
}
```

`GET /api/video-production/runs/{run_id}/stage-tasks`

响应：

```json
{
  "ok": true,
  "items": [
    {
      "id": "provider-stage-task-id",
      "stage": "image_generation",
      "target_id": "segment-id",
      "status": "reserved|submitted|running|sync_required|succeeded|failed|manual_repair_required",
      "provider_task_id": "task-id",
      "estimated_cost": 0.12,
      "actual_cost": 0.1,
      "retryable": true,
      "repair_action": "同步供应商结果",
      "repair_route": "/video-production/{run_id}"
    }
  ]
}
```

`POST /api/video-production/assets/{asset_id}/persist-retry`

响应：

```json
{
  "ok": true,
  "asset_id": "asset-id",
  "copy_status": "persisted",
  "storage_path": "runs/run-id/video/segment-id/v2.mp4",
  "checksum": "sha256:..."
}
```

`GET /api/system/migration-health`

响应：

```json
{
  "ok": true,
  "status": "ok|warning|blocked",
  "current_revision": "revision-id",
  "head_revision": "head-id",
  "missing_columns": [],
  "repair_actions": []
}
```

## Data Flow

```text
start production
  -> create ProductionPlan
  -> create ProductionJobs
  -> worker-step
      -> budget estimate
      -> stage task reservation
      -> provider submit/sync
      -> cost event
      -> asset persistence
      -> AI audit record
      -> review_pending
  -> human review
  -> next stage worker-step
  -> final human approval
  -> library writeback
```

## Error Model

必须使用可修复错误格式：

```json
{
  "code": "BUDGET_BLOCKED",
  "message": "当前预算不足，无法继续提交真实模型。",
  "cause": "estimated_cost_exceeds_budget",
  "repair_action": "提高预算、减少分段或切换低成本模型。",
  "repair_route": "/video-production/{run_id}",
  "affected_ids": ["..."],
  "retryable": true
}
```

建议错误码：

- `BUDGET_BLOCKED`
- `BUDGET_EXHAUSTED_AFTER_ACTUAL_COST`
- `PROVIDER_STAGE_TASK_EXISTS`
- `PROVIDER_STAGE_TASK_SYNC_REQUIRED`
- `PROVIDER_SUBMIT_FAILED`
- `ASSET_STORAGE_FAILED`
- `REVIEW_PERMISSION_DENIED`
- `REVIEW_GATE_BLOCKED`
- `MIGRATION_HEALTH_BLOCKED`

### Unified Action Result

所有新执行边界必须返回统一结果模型，避免各服务各自拼 error payload、audit payload 和前端 CTA。

建议结构：

```json
{
  "ok": false,
  "code": "ASSET_STORAGE_FAILED",
  "message": "资产持久化失败，不能进入审查。",
  "cause": "mime_type_mismatch",
  "repair_action": "重新持久化资产或重新生成该片段。",
  "repair_route": "/video-production/{run_id}",
  "affected_ids": ["asset-id"],
  "retryable": true,
  "severity": "warning|blocked|failed",
  "audit_event_type": "asset.storage_failed",
  "details": {}
}
```

适用范围：

- `ProviderStageExecutor`
- budget reservation service
- storage guard
- aggregate gate evaluator
- review service
- worker-step
- migration health / provider canary

规则：

- `ProductionRepairableError` 和 `ProductionActionResult` 必须共享同一字段语义。
- 后端审计事件、API 错误响应和前端 repair CTA 必须从同一结果模型派生。
- route handler 不得直接拼接新的错误 shape；只能转换统一结果模型为 HTTP response。
- 前端组件不解析 provider 原始错误，只展示统一结果中的 message、repair_action、repair_route 和 affected_ids。

## Frontend Requirements

一键成片页：

- 显示预算上限、预计费用、真实 provider 风险说明。
- 真实模式必须要求预算，不允许隐藏成本风险。
- 真实模式提交前必须显示确认摘要：预算上限、最大 duration、shot 上限、模型配置、预计费用、自动推进到哪个 gate、停止入口。
- 用户确认前不得自动提交真实 provider。

监控页：

- 显示 cost rail、stage task rail、asset persistence 状态。
- 明确区分 provider submitted、provider running、asset persisted、review pending。
- 预算阻断、存储失败、provider 同步失败必须有修复动作。
- `repair_route` 必须渲染为可点击 CTA，不得只显示为纯文本。
- 每次 worker step 必须显示处理数、跳过原因、下一个阻塞点和下一步动作。

审查页：

- `copy_status != persisted` 的资产不能显示通过按钮。
- 后端也必须拒绝 `copy_status != persisted` 的审批请求。
- final approval 使用独立按钮和权限提示。
- real run 不显示批量 approve。

系统状态页：

- 第一版固定为 `/system/health`。
- 显示 migration health、provider config canary、最近 paid smoke report。
- 使用红黄绿状态：ok、warning、blocked。
- 只展示当前状态、最近报告和修复动作，不建设趋势大屏。

### UI State Contract

| Source State | 用户可见文案 | 主动作 | 禁用条件 | Repair CTA | API | 测试 |
|---|---|---|---|---|---|---|
| `budget_status=unknown_estimate_requires_cap` | 费用未知，需要设置硬预算 | 设置预算并确认 | 未设置预算或 shot 上限 | 打开预算设置 | `GET /runs/{id}/costs` | 监控页预算阻断测试 |
| `budget_status=blocked` | 预算不足，已暂停真实提交 | 调整预算或减少分段 | 无 admin 权限 | 调整预算 | `GET /runs/{id}/costs` | repair route 可点击 |
| `provider_task.status=reserved` | 已预留供应商任务，尚未提交 | 提交或 worker step | plan paused | 继续 worker | `POST /worker-step` | stage rail reserved |
| `provider_task.status=running` | 供应商生成中 | 同步结果 | task 未到可同步时间 | 同步供应商 | `GET /stage-tasks` | stage rail running |
| `provider_task.status=sync_required` | 需要同步供应商结果 | 同步结果 | 缺少 provider_task_id | 人工补录 task id | `GET /stage-tasks` | sync required 显示 CTA |
| `asset.copy_status=storage_failed` | 资产持久化失败，不能审查 | 重试持久化 | 缺少 source URL/path | 重试持久化 | `POST /assets/{id}/persist-retry` | 禁用通过按钮 |
| `asset.copy_status=registered` | 资产尚未持久化 | 等待或重试持久化 | 无 source | 重试持久化 | `POST /persist-retry` | 禁用通过按钮 |
| `review_gate=image_review` | 图像待人工审查 | 打开图像审查 | 无 reviewer 权限 | 打开审查 | `/ai-video-review?gate=image` | gate tab 测试 |
| `review_gate=video_review` | 视频片段待人工审查 | 打开视频审查 | 无 reviewer 权限 | 打开审查 | `/ai-video-review?gate=video` | gate tab 测试 |
| `review_gate=final_review` | 最终视频待终审 | 终审通过并入库 | 无 final approver 权限或未持久化 | 请求终审权限 | `/ai-video-review?gate=final` | final 权限测试 |
| `migration_health=blocked` | 数据库迁移异常，生产启动被阻断 | 查看修复建议 | 非 staging/prod 可弱化为 warning | 打开系统状态 | `/system/health` | 运维页 blocked 测试 |

## Test Plan

后端单测：

- 预算不足时 provider submit 不会被调用。
- 并发预算 reservation 不会超卖。
- 同一个 `provider_stage_task_id` 重复 sync 不会重复记录 actual cost。
- legacy provider path 要么被禁止，要么强制走 budget/idempotency/storage guard。
- provider task reservation 失败时不会调用 provider。
- 同一 idempotency key 重试只同步旧 provider task。
- provider task id 写库失败后，可以通过 `external_task_id` 同步或进入人工补录流程，不会重复提交 provider。
- provider submit 成功但 asset storage 失败时不会进入审查。
- `copy_status != persisted` 的 image/video/final 审批都被后端拒绝。
- `copy_status != persisted` 的 final video 不能写回 Episode 和 GeneratedVideo。
- real run 禁止批量 approve。
- final approval 权限不足返回 `REVIEW_PERMISSION_DENIED`。
- 拒绝 image/video/final 后，下游 job 被 blocked 或 superseded。
- 重试创建新 asset version，并重新做 budget reservation 和 ProviderStageTask。
- worker step crash 后 expired lease 可恢复。
- migration health 在 staging/prod 模式下阻断失败迁移。

后端测试矩阵：

| 测试文件 | 覆盖边界 | 必测场景 |
|---|---|---|
| `server/tests/test_provider_cost_reservation_service.py` | 成本 reservation 原子性和生命周期 | active reservation 计入预算；两个 worker 同时预留同一 plan 时只有一个成功；失败方返回 `BUDGET_BLOCKED` 或 retryable blocked；失败方不得调用 provider submit；不得创建第二个 active reservation；不得增加 `ProductionPlan.current_cost`；terminal reservation 不可回 active；provider 未提交时可 expired/released；provider 已提交后不得静默释放；repeated sync 不重复记 actual cost |
| `server/tests/test_provider_stage_executor.py` | 真实 provider 两阶段执行和恢复 | reservation DB 失败时不调用 provider；`ProviderStageTask=reserved` 且无 `provider_task_id` 时先按 `external_task_id` 查询再决定 submit；provider submit 成功但写回 `provider_task_id` 失败后，下次 worker 不重新 submit；provider 支持 external id 查询时下次能 sync 原任务；provider 不支持 external id 查询且无补录能力时 config canary 标记 `blocked_for_real_provider`；人工补录 `provider_task_id` 后只能 sync 不允许重新 submit；provider 调用不得发生在 DB 锁持有期间 |
| `server/tests/test_provider_throttle_and_backoff.py` | provider/model/stage 并发限流和退避 | active task 统计包含 `submitted`、`running`、`sync_required`、`manual_repair_required`；超过 `max_concurrent_tasks` 时不得创建 provider task，job 进入 `retry_wait` 并返回 `PROVIDER_THROTTLED`；不同 provider/model 配额独立；worker `batch_size` 不能绕过并发上限；provider 429/临时 5xx 写入指数退避和 audit event；已有 `ProviderStageTask` 的重试只 sync 或等待，不重新 submit |
| `server/tests/test_asset_storage_guard.py` | 资产安全落库和审批硬门禁 | 拒绝 `file://`、相对路径、内网地址、本机地址、非 allowlist 协议；Pixelle local path 越过 output root 时拒绝；超过 size 上限时中断并标记 `storage_failed`；MIME sniff 与 stage 不匹配时拒绝，例如 HTML 错误页伪装成图片；下载到临时文件，校验通过后才 atomic rename；checksum 写入正确；checksum 或 rename 失败时不能进入 `review_pending`；retry 不产生孤儿文件，或孤儿文件被记录/清理；`copy_status != persisted` 的 asset 审批接口返回拒绝 |
| `server/tests/test_production_gate_evaluator.py` | 长视频阶段 fan-in 聚合闸门 | 10 个 image jobs 中 9 个 approved、1 个 `storage_failed` 时不得 materialize video jobs；所有 image approved 后才创建 video jobs；rejected image 会 supersede 下游 video/compose jobs；superseded asset 不可审批，latest version 接替后才解除阻断；119/120 segment 通过时 run 保持 `*_partial` 或 `*_blocked`；final approval 前不得 writeback `Episode` 和 `GeneratedVideo`；evaluator 每次阻断都写 audit event，并返回阻塞 segment 列表 |
| `server/tests/test_video_production_performance_boundaries.py` | 长视频分页、索引和查询形态 | tree、review-items、stage-task、audit、asset-history 和 cost API 默认 `page_size=50`；普通请求超过 100 时被 clamp 或拒绝；内部 worker/smoke 超过 200 时被拒绝；`GET /runs/{run_id}` 不返回无上限全量 assets；生产树只返回当前页摘要，不携带全部 history；gate evaluator 使用聚合查询而非逐 segment N+1；Phase 0 migration 包含性能边界要求的核心索引；大 run fixture 下接口响应 payload 不随全量 segment 线性膨胀 |

后端集成测试：

- real_short_e2e mocked provider: cost -> idempotency -> persistence -> review gates -> final writeback。
- long video worker mocked provider: 多 segment 分批推进、暂停、恢复、重试、审查 gate。

前端测试：

- 真实模式提交前显示预算、时长、shot、模型、自动推进 gate 的确认摘要。
- 用户未确认前不提交真实 provider。
- 预算阻断显示修复动作。
- repair route 渲染为可点击 CTA。
- stage task rail 正确展示 submitted/running/sync required。
- storage failed asset 不可审批。
- `copy_status != persisted` 禁用通过按钮并显示原因。
- final approval 无权限时隐藏或禁用。
- real run 不显示批量 approve。
- 运维页显示 migration blocked、provider config canary 和最近 smoke report。

前端测试矩阵：

| 测试文件 | 覆盖页面 | 必测场景 |
|---|---|---|
| `web/src/__tests__/video-production-monitor-boundary-states.test.js` | 视频生产监控页 | `repair_route` 渲染为可点击 CTA 而不是纯文本；stage task rail 展示 `reserved`、`running`、`sync_required`、`manual_repair_required`；cost rail 展示 `active_reserved_cost`、`stale_needs_repair_cost`、`settled_cost`；worker-step 返回 `blocked`、`retry_wait`、`next_repair_action` 时页面显示下一步；storage failed 显示 persist retry 入口；provider capability blocked 显示修复入口 |
| `web/src/__tests__/video-production-monitor-performance.test.js` | 视频生产监控页 | 进入监控页只请求 bounded tree page、run summary、readiness 和 cost summary；不默认拉取全部 stage task、audit event、asset history 或所有 segment detail；切换分页/筛选只加载对应页；只在用户选择某个 segment 后加载该 segment 详情；provider throttle 和阻塞项使用摘要接口展示，不触发全量列表请求 |
| `web/src/__tests__/ai-video-review-boundary-gates.test.js` | AI 视频审查中心 | `copy_status != persisted` 的 asset 禁用通过按钮并显示原因；final approval 无权限时禁用并显示权限提示；real run 不显示批量 approve；superseded asset 不可审批；review API 返回 `REVIEW_PERMISSION_DENIED` 时展示统一 repair message |
| `web/src/__tests__/system-health-page.test.js` | `/system/health` | 显示 migration blocked、provider capability block、最近 paid smoke report；红黄绿状态与 API status 对齐；repair action 可点击；无 smoke report 时显示可操作空状态 |

手工 smoke：

- staging paid smoke 只允许最小 duration、最小 shot、显式预算。
- smoke report 必须包含费用、provider task id、资产持久化状态和最终审查状态。

## Failure Modes Review

| 新代码路径 | 生产故障方式 | 测试覆盖 | 错误处理 | 用户可见性 | Critical gap |
|---|---|---|---|---|---|
| 成本 reservation | 两个 worker 同时为同一 plan 预留预算，导致超卖并触发真实 provider | `test_provider_cost_reservation_service.py` 并发 reservation 场景 | `BUDGET_BLOCKED`、retryable blocked、不得调用 provider | 监控页显示预算阻断和修复动作 | 否 |
| ProviderStageExecutor | provider submit 成功但 `provider_task_id` 写库失败，下次重试重复扣费 | `test_provider_stage_executor.py` submit 成功写回失败恢复场景 | `sync_required`、external id 查询或人工补录后 sync | stage task rail 显示 sync required 和补录入口 | 否 |
| Provider throttle/backoff | 长视频分段批量提交触发 429，worker 继续新建外部任务 | `test_provider_throttle_and_backoff.py` 并发上限和 429/5xx 退避场景 | `PROVIDER_THROTTLED`、`retry_wait`、指数退避和 audit event | 监控页显示 active task、并发上限和下一次 retry | 否 |
| AssetStorageGuard | provider URL 过期、返回 HTML 或 Pixelle path 越权，资产被误审批 | `test_asset_storage_guard.py` 协议、路径、MIME、checksum、atomic rename 场景 | `ASSET_STORAGE_FAILED`、禁止进入 `review_pending` | 审查页禁用通过按钮，监控页显示 persist retry | 否 |
| AggregateGateEvaluator | 120 个 segment 中 119 个通过后提前 materialize 下游 video/compose | `test_production_gate_evaluator.py` partial、blocked、superseded 场景 | `REVIEW_GATE_BLOCKED`、阶段保持 partial/blocked | 监控页显示阻塞 segment 列表和下一步动作 | 否 |
| Final writeback | 最终视频未人工审批或未持久化就写回 `Episode`/`GeneratedVideo` | gate evaluator 和真实短片 mocked E2E | final approval 前拒绝 writeback，asset persisted 硬检查 | 审查页显示最终审批要求，run 保持 blocked | 否 |
| Migration health | staging/prod 缺列但服务继续启动，真实付费链路写入失败 | migration health 阻断测试和 paid smoke | `MIGRATION_HEALTH_BLOCKED`、启动或 smoke 阻断 | 系统状态页显示缺失列和修复动作 | 否 |

Critical gaps after this revision: 0。剩余风险主要是 provider usage 字段差异和实际外部模型稳定性，需要通过 staging paid smoke 验证，而不是继续扩大设计范围。

## Implementation Diagram Comments

实现时以下文件应写入简短 ASCII 图注释，帮助后续维护者看清状态流和不可绕过边界：

| 文件 | 建议图示内容 |
|---|---|
| `server/app/services/production_state_contract.py` | run/job/stage task/asset/review 的状态所有权和合法转换 |
| `server/app/services/provider_stage_executor.py` | reservation 短事务 -> provider I/O -> 写回短事务 -> asset persistence 的两阶段执行 |
| `server/app/services/provider_cost_reservation_service.py` | unsubmitted reservation、submitted reservation、settled、released、stale repair 的生命周期 |
| `server/app/services/asset_storage_guard.py` | source URL/path -> temp file -> MIME/checksum -> atomic rename -> persisted asset |
| `server/app/services/production_gate_evaluator.py` | image/video/final 三个阶段的 fan-in 闸门和 partial blocked 流转 |
| `server/app/services/production_worker_service.py` | claim job -> capability gate -> throttle/backoff -> executor -> aggregate gate |

## Rollout Plan

Phase 0: Schema and safety gate

- 明确真实 provider run type 策略：`real_short_e2e` 是唯一新真实 provider 入口；`legacy_episode_run` 要么禁止进入 provider stage，要么必须走同一套 budget/idempotency/storage guard。
- 明确统一 provider 执行边界：所有真实 provider 调用必须经过 `ProviderStageExecutor`，并强制执行 budget reservation、ProviderStageTask、provider submit/sync、asset persistence 和 audit。
- 在 staging/prod 中，Alembic 失败必须阻断启动；开发环境才允许 warning + create_all。
- 新增 `ProviderStageTask`。
- 新增 `ProviderCostReservation` 或等价字段，保证预算 reservation 原子性。
- 补充 `VideoProductionAsset.storage_path`、`source_url`、`storage_error_json`、`provider_response_summary_json`。
- 补充 `VideoReviewRecord.reviewer_role`、`action`、`asset_snapshot_json`、`model_trace_summary_json`。
- 补充 `ProductionAuditEvent.actor_user_id`、`actor_role` 或等价审计字段。
- 输出 migration health 基础检查和 staging/prod 启动阻断策略。

Phase 1: 真实付费风险封口

- 接入 production cost 到 image/video/compose。
- 新增 provider stage task reservation。
- 强制视频生产资产持久化。
- 补真实短片 mocked E2E。
- 补真实付费启动确认摘要。
- 补 UI State Contract 中 P0 状态。

Phase 2: 真实长视频 worker

- 新增真实 worker step。
- 接入 queue lease、retry wait、pause/resume。
- 支持 provider polling 和 sync required。
- 补长视频 mocked provider 调度测试。
- 补 reject/retry/version 对 job graph 的影响。

Phase 3: 生产运维边界

- 审查权限拆分。
- staging smoke API 和报告。
- provider config canary。
- migration doctor 和环境级启动策略。
- `/system/health` 当前状态页。

Phase 4: 运维产品化后置

- migration doctor API 完整修复流。
- canary 趋势统计。
- paid smoke 历史对比。
- 后台常驻 daemon。
- 更细的 operator rail 和历史事件分析。

## Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| Phase 0 schema/state contract | `server/alembic/`, `server/app/db_models.py`, `server/app/services/production_state_contract.py` | 无 |
| Provider execution and cost guard | `server/app/services/`, `server/app/routers/video_production.py` | Phase 0 |
| Asset persistence guard | `server/app/services/`, media storage config | Phase 0 |
| Review gate and final writeback | `server/app/services/`, `server/app/routers/video_production.py` | Phase 0, asset persistence guard |
| Worker scheduler and throttle/backoff | `server/app/services/`, `server/app/routers/video_production.py` | Phase 0, provider execution, gate evaluator |
| Frontend transparency surfaces | `web/src/views/`, `web/src/api/`, `web/src/__tests__/` | API contract stubs from Phase 0 and Phase 1 |
| Smoke, canary and migration health | `server/scripts/`, `server/app/routers/`, `server/tests/` | Phase 0, provider execution |

Parallel lanes:

- Lane A: Phase 0 schema/state contract first. This is the shared foundation and should land before other lanes.
- Lane B: Provider execution, cost guard and throttle/backoff. Sequential inside the lane because the same executor owns paid submit.
- Lane C: Asset persistence guard plus review gate/final writeback. Can start after Phase 0 and merge before long-video worker.
- Lane D: Frontend transparency surfaces. Can run in parallel once API payload contracts are stubbed.
- Lane E: Smoke/canary/migration health. Can run in parallel with Lane B after Phase 0, but paid smoke depends on executor behavior.

Execution order: land Lane A, then run Lane B + Lane C + Lane D + Lane E in parallel worktrees with explicit API contract sync. Merge B and C before worker scheduler, then finish long-video worker and E2E tests.

Conflict flags:

- Lane B and Lane C both touch `server/app/routers/video_production.py`; keep route changes thin and delegate to services to reduce merge conflict.
- Lane B, C and worker scheduler all touch `server/app/services/`; avoid adding new logic to `video_production_service.py` so service boundaries stay mergeable.
- Lane D depends on stable error/action result payloads; do not let frontend invent separate repair payload shapes.

## Risks

- 真实 provider usage 字段不统一，可能无法准确拿到实际费用。第一版允许估算费用 + provider usage snapshot 并存。
- 资产下载可能受 provider URL 过期影响。必须尽快持久化，不应等人工审查时再拉取。
- 长视频 worker 如果直接后台常驻，调试和恢复成本高。第一版先做有限 batch 的 manual/API step。
- 权限拆分会影响现有单人本地使用。开发环境可默认 admin 拥有全部权限，staging/prod 严格执行。

## Open Decisions

本设计已做以下取舍：

- 选择生产级边界闭环，而不是只补短片或先做长视频 worker。
- 真实长视频采用分段 worker，不采用一次性长视频 provider 调用。
- 第一版 worker 可以 API/manual step 驱动，后台 daemon 后置。
- 资产持久化是进入审查的前置条件，而不是最终入库时才检查。
- staging/prod migration 失败必须阻断，开发环境保留宽松策略。

## Acceptance Criteria

- 真实短片链路证明不会重复提交 provider，不会超过预算继续跑，最终入库视频来自 dy_auto 可控存储。
- 用户可从一句话或 episode 发起真实短片，看到真实付费确认摘要，在 image/video/final 三个 gate 完成人工审查，并最终得到可播放入库视频。
- 长视频链路证明多分段任务可以暂停、恢复、失败重试，并且每个阶段都卡在人工审查闸门。
- 所有真实 provider 提交都有 stage task reservation、成本事件、审计事件和可查状态。
- 所有可审批资产都有 checksum、size、storage path 和 persisted 状态。
- 任何真实 provider 调用、同步、持久化、审查阻断都必须在监控页或系统状态页有可追踪事件和可恢复入口。
- staging paid smoke 可生成可审查报告，且默认 CI 不调用真实 provider。

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | 保持真实一键成片、审查闸门、长视频调度稳定性的范围，不扩 3D、抖音发布、时间线编辑 | Hold scope | Focus beats breadth | 用户已经明确暂停 3D，当前核心风险是生产闭环边界 | 把运维大屏、发布闭环或编辑器并入本阶段 |
| 2 | CEO | 将完整运维产品化后置，只保留真实付费保护所需的 health/smoke/migration 边界 | Scope reduction | Ship the smallest safe system | migration/canary 必须保护真实付费，但趋势大屏不是当前闭环必需 | 第一阶段建设完整运维产品 |
| 3 | Engineering | 增加 Phase 0 schema and safety gate | Critical safety | Schema before workflow | 后续阶段依赖 ProviderStageTask、reservation、storage 字段和 migration 阻断 | 把 migration doctor 和 schema 安全放到最后 |
| 4 | Engineering | 成本闭环必须使用原子预算 reservation | Critical safety | Prevent irreversible spend | 单纯读取 current_cost 不能防并发超卖和重复 sync 重复计费 | 只在 stage 前做正预算检查 |
| 5 | Engineering | ProviderStageTask 改为强制模型，并要求 external_task_id | Critical safety | Idempotency before provider call | 只有强制 reservation 才能防重复提交和支持写库失败恢复 | 继续只用 run_id 或 ProductionJob idempotency_key |
| 6 | Engineering | 资产持久化必须是后端审批和入库硬闸门 | Critical safety | Backend is source of truth | 前端隐藏按钮不能防接口绕过，最终入库不能依赖 provider 原始 URL | 只在前端禁用未持久化资产 |
| 7 | Engineering | 真实长视频 worker 使用 per-job executor，不复用 run-level 批量提交函数 | Architecture | Segment-level recovery | 长视频需要按 segment 暂停、恢复、重试和过 gate | 直接复用当前批量 stage 函数 |
| 8 | Design/DX | 增加 UI State Contract 和 repair CTA 要求 | Transparency | No hidden production work | 用户必须知道每个真实 provider、存储、审查阻断发生在哪里以及如何恢复 | 只显示泛化错误文本 |
| 9 | Design/DX | 真实模式提交前必须显示付费确认摘要 | User control | Paid action requires explicit consent | 预算、shot、模型和自动推进 gate 必须在消耗前可见 | 提交后一边后台推进一边提示 |
| 10 | QA | 增加并发、重放、写库失败恢复、未持久化审批拒绝和 staging migration 阻断测试 | Test rigor | Test the failure modes that spend money | 剩余风险都集中在不可逆 provider 成本和数据一致性 | 只保留 happy-path mocked E2E |
| 11 | Engineering | 增加状态所有权矩阵 | Architecture | One owner per state transition | Run、Job、ProviderStageTask、Asset、ReviewRecord 必须各自拥有清晰状态边界，避免 provider 成功但资产失败时被误标 completed | 让各服务自由读写彼此状态 |
| 12 | Engineering | 明确成本 reservation 的事务与锁策略 | Critical safety | Atomic spend control | 预算检查和 reservation 写入如果不在同一临界区，并发 worker 仍会超卖预算并触发真实 provider 消耗 | 只写“原子 reservation”但不规定锁和状态流转 |
| 13 | Engineering | 增加 provider 恢复能力准入 | Critical safety | Recover paid external tasks | provider 已扣费但 task id 写库失败是最高风险路径，真实 provider 必须支持 external id 查询或人工补录后 sync | 所有配置好的 provider 都默认可进入真实付费链路 |
| 14 | Engineering | 明确 ProviderStageExecutor 两阶段短事务模型 | Critical safety | Never hold DB locks during network I/O | 预算锁和 plan 行锁如果包住外部 provider 调用，会在超时或慢响应时拖死 worker 与长视频调度 | 在一个长事务中完成 reservation、provider submit 和结果写回 |
| 15 | Engineering | 增加 provider 能力矩阵准入 | Architecture | Capability gates before paid execution | 模型配置存在不代表适合真实付费链路，必须在入口和执行器同时校验 external id、task query、usage、asset URL、stage 能力和时长上限 | 只凭 provider、API key、base URL 和 model id 判断可用 |
| 16 | Engineering | 增加安全落库协议 | Critical safety | Treat provider assets as untrusted input | provider URL 和 Pixelle local path 都是不可信输入，必须限制协议、路径、大小、MIME、checksum，并用临时文件加 atomic rename 入库 | 直接复制 URL/path 到最终资产位置 |
| 17 | Engineering | 明确 reservation 生命周期与释放规则 | Critical safety | Never release possibly paid work silently | worker 崩溃后需要释放未提交的预算，但已提交 provider 的 reservation 不能静默过期，否则会低估真实成本并继续提交 | 只设置 expires_at，不区分未提交和已提交 provider |
| 18 | Engineering | 增加阶段聚合闸门 | Architecture | Fan-in before stage promotion | 长视频多分段会出现部分成功和部分失败，必须由 aggregate evaluator 汇总判定下一阶段是否可 materialize | 单个 job completed 事件直接推进 run 或创建下游 job |
| 19 | Engineering | 集中状态契约和错误码 | Code quality | State transitions are API contracts | 当前状态字符串分散在多个服务中，新边界必须用统一状态常量、转换表和错误码，避免实现与文档状态矩阵漂移 | 在 route/service/frontend 中继续直接拼状态字符串 |
| 20 | Engineering | 增加统一执行结果模型 | Code quality | One repair contract everywhere | provider、storage、review、worker、health 都会产生可修复错误，必须共享同一 action result，避免 API、审计和前端 CTA 三套结构分叉 | 每个服务各自拼 error payload 和 repair CTA |
| 21 | Engineering | 明确服务文件组织边界 | Code quality | Small services around hard boundaries | `video_production_service.py` 已承载大量阶段逻辑，新真实闭环应按 provider、storage、cost、gate、worker 拆出边界服务 | 继续把新核心逻辑追加到大 service 文件 |
| 22 | Engineering | 增加旧 stage 函数迁移 guard | Code quality | Compatibility wrappers must not bypass safety | 现有 run-level stage API 仍可能被前端或旧调用方使用，真实 run 下必须委托 ProviderStageExecutor 或明确拒绝 | 新执行器之外保留旧真实 provider 提交路径 |
| 23 | QA | 增加成本 reservation 并发与生命周期测试矩阵 | Test rigor | Prove spend safety under concurrency | 真实成本风险集中在并发预留、重复 sync 和已提交 provider 的 reservation 释放路径，必须有专门测试文件覆盖 | 只保留预算不足的普通单测 |
| 24 | QA | 增加 ProviderStageExecutor 恢复测试矩阵 | Test rigor | Prove no paid task is submitted twice | Provider submit 成功但写库失败是最危险路径，必须验证 external id 查询、人工补录、短事务和不重复 submit | 只测 provider happy path 返回 succeeded |
| 25 | QA | 增加 asset storage guard 安全测试矩阵 | Test rigor | Treat media ingestion as hostile input | provider URL 和 Pixelle path 都可携带安全风险，必须测试协议、路径、大小、MIME、checksum、atomic rename 和审批硬门禁 | 只测试 provider 返回正常图片或视频 URL |
| 26 | QA | 增加 production gate evaluator fan-in 测试矩阵 | Test rigor | Prove partial success cannot promote stages | 长视频阶段推进必须等全部 required targets 满足条件，部分成功、storage failed、superseded 或未终审都不能推进下游 | 只测试全部成功的阶段推进 happy path |
| 27 | QA | 增加前端边界状态测试矩阵 | Test rigor | Make hidden backend work visible | 真实生产边界只有在监控页、审查页和系统状态页可见且可恢复，才满足“后台不得暗箱操作”的产品要求 | 只测页面 happy path 渲染 |
| 28 | Engineering | 增加长视频分页、索引和查询边界 | Performance | Scale rails by page, not by project size | 240 分钟及更长内容会产生大量 segment、task、asset 和 audit event，监控页和 worker 必须分页、聚合并依赖索引 | 允许生产树、stage task、audit 或 cost API 无上限全量返回 |
| 29 | Engineering | 增加 provider 并发限流和退避规则 | Performance | Backpressure before paid provider submit | 长视频分段批量提交会触发 provider 429、成本抖动和队列雪崩，submit 前必须按 provider/model/stage 控制 active task 并退避 | 只靠 worker batch_size 控制真实 provider 并发 |
| 30 | QA | 增加长视频性能边界测试矩阵 | Test rigor | Performance contracts need regression tests | 分页、索引和无 N+1 只有写入测试才不会在后续监控页或 worker 改造中退化，尤其是 240 分钟及更长项目 | 只在方案中描述性能边界，不要求后端和前端测试证明 |
| 31 | QA | 增加 provider 限流退避测试矩阵 | Test rigor | Prove throttling before paid submit | 并发限流的失败代价是真实 provider 被打爆或重复扣费，必须用测试证明超过额度不会创建外部任务且重试只等待或 sync | 只依赖人工代码审查确认限流逻辑 |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not logged | 已由方案内 `Autoplan Review Corrections` 和 `Decision Audit Trail` 记录范围收敛 |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not run | 无 |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 4 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | score: 7.6/10 -> 8.9/10, 5 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | 无 |

- UNRESOLVED: 0
- VERDICT: ENG + DESIGN CLEARED。可以进入实施，但实施时必须按本方案的 provider 执行边界、审查闸门、性能测试和 paid smoke 验证闭环。
