<!-- /autoplan restore point: C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260526-165613.md -->

# agency-agents-zh 专家 Skill 化与透明控制台重设方案

## Summary

本方案补全 dy_auto 现有“专家团队”能力：不扩容专家数量，继续保留当前 5 个核心专家 + 4 个支援专家，但每个专家必须 1:1 绑定 `jnMetaCode/agency-agents-zh` 中对应的原始 Markdown 专家定义。运行时不再只使用一两句 `mission/directives` 摘要，而是像调用内部 Skill 一样，按生产阶段加载相关专家原文、独立调用、汇总结论，并把每个专家的输入摘要、输出摘要、质量门槛和结果写入透明控制台。

透明控制台同步重设为“生产控制室”：左侧展示生产阶段，中心展示专家调用 DAG 和阶段产物，右侧展示 9 个专家档案与原文抽屉，底部展示决策日志与质量门禁。控制台只读、全中文展示，不打断一句话生成和自动生产流程。

## Goals

- 仅保留与自动视频生成相关的 9 个专家，不导入 215 个全量专家。
- 9 个专家必须来自 `jnMetaCode/agency-agents-zh`，并保留原始 Markdown 内容、源文件路径、源提交、内容哈希。
- 每个生产阶段只调用该阶段相关专家；多个专家采用“并行审阅 + 主责专家汇总 + QA 门禁”的编排方式。
- 专家调用要真实参与生产提示词和质量判断，不能只作为前端展示文案。
- 后台不得暗箱操作：控制台能看到专家调用、阶段输入输出、门禁结果、失败原因、持久化位置。
- 控制台 UI 重设为清晰的生产控制室，不再用松散卡片堆叠。

## Implementation Phasing

为了避免把“真实专家编排、审计持久化、3D 动漫角色地图”一次性做成不可验证的大重构，本方案按两个可验收阶段实施。

### Phase 1: Expert Runtime and 2D Control Room

第一阶段必须先打通真实专家能力：

- 9 个专家原文档案落地到项目内。
- `AgencySkillRuntime` 能按阶段独立调用专家。
- 专家调用记录能持久化、查询、脱敏展示。
- 风格锁定、自动分镜、文生图/图审、图生视频/视频审、合成至少有可追踪专家记录。
- 控制台展示生产阶段 DAG、专家调用流水、质量门禁、专家原文抽屉。

### Phase 2: Anime 3D Expert Map

第二阶段在 Phase 1 数据契约稳定后实现 3D 动漫专家地图：

- 使用 Phase 1 的 `stage_graph` 和 `expert_invocations`，不新增生产控制语义。
- 3D 视图只读，不能成为生产流程的唯一入口。
- 首版可用程序化低模或 2.5D 角色卡，后续可替换为完整 3D 模型。

这样保留用户要求的 3D 角色地图，但不让装饰性可视化阻塞“专家真实参与生产”这个核心目标。

## Measurable Product Bar

“专家真实参与”必须有可测标准：

- 同一阶段多个专家必须产生多条独立 `expert_invocation` 记录，不能只有一个合并 prompt。
- 主责专家的汇总输入必须引用 reviewer 输出 id。
- QA 门禁 blocked 时，阶段必须停止推进或进入人工处理状态，并给出修复建议。
- 控制台必须能从任一阶段追溯到：输入摘要、专家原文来源、专家输出、门禁结论、持久化位置。
- 一句话生成流程可以不进入控制台，但生产完成后控制台必须能回放专家参与过程。

## Cost and Latency Budget

专家编排增加 LLM 调用量，必须有明确预算：

- 默认每个阶段最多 4 个 reviewer + 1 个 lead + 1 个 QA 调用。
- 单个 run 内同阶段 reviewer 并发上限默认 3。
- 全局专家 LLM 并发上限从模型配置中心读取，默认 5。
- 超过并发上限的专家调用进入队列，不直接失败。
- 同一 run 的 lead 必须等 reviewer 完成后执行，QA 必须等 lead 完成后执行。
- 每个专家调用必须有 timeout；超时后根据 reviewer/lead/QA 角色映射为 warning、failed 或 blocked。
- 风格锁定和自动分镜可同步等待；长视频批量生产阶段应进入后台任务，不阻塞前端请求。
- 单次专家调用必须记录 tokens、排队耗时、执行耗时、模型配置摘要和失败原因。
- 同一 run 内专家原文文件读取可缓存；专家原文不得重复复制到下游汇总 prompt。
- 当 LLM 配置缺失、额度不足或超时，阶段返回明确 blocked/warn 状态，不静默退回摘要专家。

## Non-Goals

- 不导入全部 215 个专家。
- 不让用户在本期自由组队或创建自定义专家。
- 不把专家团队做成聊天窗口。
- 不新增人工审批节点；人工审查仍使用现有图片/视频审查流程。
- 不把完整 Prompt、API Key、provider 原始响应暴露给前端。
- 不替代模型配置中心；专家运行仍复用现有 LLM 配置。

## Source Baseline

源项目：[jnMetaCode/agency-agents-zh](https://github.com/jnMetaCode/agency-agents-zh)

本次核对的源提交：

```text
13b8800f6f666e8e10ac64f67f1194d2baeefbe0
```

源项目 README/AGENT-LIST 显示该库包含 215 个 AI 智能体。dy_auto 本期只内嵌与自动视频生产强相关的 9 个专家。

## Current Gap

当前 `server/app/services/video_agency_team.py` 已有 5 核心 + 4 支援的专家结构，但它把源专家能力压缩成了短 `mission/directives`，运行时主要传递摘要。这个实现可以解释“有哪些角色”，但不能等价于“实际调用了这些专家”。

当前 `AgencyConsolePage.vue` 已能显示专家团队和生产步骤，但页面更像信息卡片列表，缺少阶段化执行视角，也不能展开查看专家原文、专家单次调用记录、主责汇总结论和 QA 门禁证据。

## Expert Mapping

| dy_auto expert id | 中文名 | 类型 | agency-agents-zh 源文件 | 主要参与阶段 |
|---|---|---|---|---|
| `short_video_editing_coach` | 短视频剪辑指导师 | 核心 | `marketing/marketing-short-video-editing-coach.md` | 自动分镜、图生视频、后期合成 |
| `douyin_strategist` | 抖音策略师 | 核心 | `marketing/marketing-douyin-strategist.md` | 自动分镜、成片包装、发布适配 |
| `ai_engineer` | AI 工程师 | 核心 | `engineering/engineering-ai-engineer.md` | 风格锁定、模型调用、图像/视频生成 |
| `prompt_engineer` | 提示词工程师 | 核心 | `specialized/prompt-engineer.md` | 风格锁定、分镜提示词、视频提示词 |
| `software_architect` | 软件架构师 | 核心 | `engineering/engineering-software-architect.md` | 流程结构、持久化、可恢复性 |
| `image_prompt_engineer` | 图像提示词工程师 | 支援 | `design/design-image-prompt-engineer.md` | 参考图、文生图、视觉一致性 |
| `product_manager` | 产品经理 | 支援 | `product/product-manager.md` | 用户目标、范围控制、成片价值 |
| `model_qa_specialist` | 模型 QA 专家 | 支援 | `specialized/specialized-model-qa.md` | AI 审查、模型输出质量、漂移检查 |
| `reality_checker` | 现实检验者 | 支援 | `testing/testing-reality-checker.md` | 可拍性、证据要求、最终放行 |

## Expert Asset Model

新增一个项目内专家档案目录，仅保存 9 个源专家：

```text
server/app/data/agency_agents_zh/
  manifest.json
  marketing/marketing-short-video-editing-coach.md
  marketing/marketing-douyin-strategist.md
  engineering/engineering-ai-engineer.md
  specialized/prompt-engineer.md
  engineering/engineering-software-architect.md
  design/design-image-prompt-engineer.md
  product/product-manager.md
  specialized/specialized-model-qa.md
  testing/testing-reality-checker.md
```

`manifest.json` 记录：

- `source_repo`: `jnMetaCode/agency-agents-zh`
- `source_commit`: `13b8800f6f666e8e10ac64f67f1194d2baeefbe0`
- `team_version`: dy_auto 内部专家团队版本
- 每个专家的 `expert_id`、中文名、源路径、文件哈希、角色类型、参与阶段、主责阶段

数据库中不重复存完整 Markdown。`Series.story_bible_json.style_lock.agency_team` 只保存专家快照引用：专家 id、team version、source commit、source path、sha256、启用状态、阶段映射。这样既能证明 1:1 来源，又避免每个系列重复写入大文本。

## Expert Invocation Persistence

新增 `AgencyExpertInvocation` 持久化模型，避免把专家调用散落在多个 JSON blob 中。

建议字段：

```text
id
idempotency_key
attempt
retry_of_invocation_id
series_id
episode_id
run_id
production_plan_id
production_episode_id
production_segment_id
pipeline_run_id
stage
expert_id
role
execution_status
result_status
input_summary_json
output_summary_json
evidence_json
source_repo
source_commit
source_path
source_sha256
model_config_snapshot_json
token_usage_json
duration_ms
error_code
error_message
repair_action
repair_route
repair_target_type
repair_target_ids_json
retry_scope
created_at
started_at
finished_at
```

写入规则：

- `AgencyExpertInvocation` 是专家调用详情的唯一事实源。
- 新视频生产链路写 `AgencyExpertInvocation`，并同步写 `ProductionAuditEvent` 作为审计时间线镜像。
- `ProductionAuditEvent.payload_json` 必须携带 `agency_invocation_id`，用于从时间线跳回专家调用详情。
- LLM/provider 调用不得持有 DB transaction。运行时先短事务创建 queued/running invocation，再调用模型，最后短事务写入最终 invocation 和 audit 镜像。
- 最终 `AgencyExpertInvocation` 更新与对应 `ProductionAuditEvent` 必须在同一个 DB transaction 内写入；如果审计镜像写入失败，专家调用不能标记完成。
- legacy pipeline 可先写 `PipelineRun.layers_json.expert_invocations`，但必须提供迁移适配器，让控制台看到同一结构。
- `Series.story_bible_json.style_lock.agency_team` 只保存团队快照，不保存调用日志。
- `Episode.storyboard_json.agency_trace` 可保存轻量引用 id，不保存完整调用详情。
- `run_id` 指向 `video_production_runs.id`；`pipeline_run_id` 只用于 legacy `pipeline_runs.id`。同一条 invocation 至少有一个 run 归属，不能两个都为空。
- `idempotency_key` 必须由 `run identity + stage + expert_id + role + stage_input_hash` 生成。同一次请求重试不得产生重复专家调用。
- `attempt` 从 1 开始递增；重试记录使用新的 invocation，并通过 `retry_of_invocation_id` 指向原始失败记录。

状态字段：

```text
execution_status: queued | running | completed | failed | cancelled
result_status: pending | passed | warn | blocked | failed
```

`execution_status` 描述调用生命周期，供控制台展示 running/queued；`result_status` 描述专家结论，供阶段门禁使用。不得用一个字段同时表达“运行中”和“通过/阻断”。

查询规则：

- `GET /api/series/{series_id}/agency-console` 从 `AgencyExpertInvocation` 聚合最近一次生产过程。
- `GET /api/agency/experts/{expert_id}` 只读取源专家档案，不读取调用日志。
- 控制台需要查看单次调用详情时，通过 invocation id 获取脱敏详情。

索引：

```text
(series_id, created_at)
(series_id, run_id, stage)
(run_id, stage, created_at)
(pipeline_run_id, stage, created_at)
(production_plan_id, production_episode_id, stage)
(expert_id, result_status, created_at)
(error_code, created_at)
(idempotency_key)
```

迁移要求：

- 必须新增 Alembic revision 创建 `agency_expert_invocations`，不能只依赖 `Base.metadata.create_all`。
- SQLite 兼容层 `_migrate_add_columns()` 只能作为本地旧库补列兜底，不是主要迁移机制。
- 迁移必须包含索引创建和 downgrade。
- 测试库继续使用 `Base.metadata.create_all`，但必须有至少一个测试导入新模型并验证表结构字段。

保留策略：

- 默认长期保留专家 id、阶段、状态、source path、source hash、错误码、修复目标和时间戳。
- `input_summary_json`、`output_summary_json`、`evidence_json` 可以按项目配置保留周期或压缩策略。
- 禁止保存完整未脱敏 prompt、provider 原始响应、API key 或模型密钥。
- 未来清理只能清理大字段，不能清理 source provenance、status、error_code 这些审计字段。

## Skill-Like Runtime

新增两个内部服务层：

- `AgencySkillRuntime`：单个专家调用层，概念上类似调用 Skill，但它属于 dy_auto 后端服务，不依赖 Codex 外部 skill 系统。
- `AgencyOrchestrator`：唯一阶段编排入口，负责专家 DAG、并行 reviewer、主责汇总、QA 门禁、状态映射、成本记录和持久化。

Router 和业务 service 不直接拼专家 DAG，也不直接批量调用 `AgencySkillRuntime`。所有阶段入口都通过 `AgencyOrchestrator`：

```text
run_style_lock_review(...)
run_storyboard_review(...)
run_image_stage_review(...)
run_video_stage_review(...)
run_compose_review(...)
```

`style-lock`、`director/auto-plan`、one-sentence flow、video production staged flow、legacy pipeline 都必须接入这些阶段方法，避免不同路径产生不同专家行为。

一句话生成路径是硬性接入点：

- `create_one_sentence_video()` 创建 series/episode 后，必须调用 `AgencyOrchestrator.run_style_lock_review()`。
- storyboard scaffold 生成后，必须调用 `AgencyOrchestrator.run_storyboard_review()`，或把 scaffold 分镜送入专家审阅和 QA 门禁后再进入生产。
- 一句话生成 API 返回必须包含 `agency_trace_status`，让前端知道专家链路是否已记录。
- 控制台必须能从 one-sentence run 回放专家参与过程。

模块边界：

```text
agency_manifest.py        # 读取/校验 9 个专家源文件与 manifest
agency_runtime.py         # 单专家调用，处理 LLM 调用和输出解析
agency_orchestrator.py    # 唯一阶段编排入口，组织 reviewer/lead/QA
agency_persistence.py     # AgencyExpertInvocation + ProductionAuditEvent 同事务写入
agency_contracts.py       # 状态枚举、Pydantic models、错误码、修复目标 schema
agency_prompting.py       # prompt 边界、输出 schema、隐私规则、注入防护
```

`agency_orchestrator.py` 可以协调这些模块，但不得直接承担 manifest 校验、LLM 调用、DB 写入、Pydantic model 定义和 prompt 安全边界的全部实现。

每个专家调用由三部分组成：

1. **专家原文**：直接读取对应 Markdown 文件，作为专家身份、工作方法和交付习惯的权威来源。
2. **阶段适配器**：dy_auto 为当前阶段附加输入契约、输出 JSON schema、业务约束、隐私规则。
3. **阶段上下文**：只传当前阶段需要的数据，例如风格锁定、分镜、角色/场景参考图、上一阶段审查结果、模型配置摘要。

Prompt 优先级：

```text
dy_auto system safety rules
  > output JSON schema
  > privacy/redaction policy
  > stage adapter instructions
  > agency-agents-zh expert Markdown
  > stage business context
```

专家 Markdown 是角色能力来源，但不能覆盖系统安全规则、隐私规则和输出 schema。运行时必须在专家原文前后包裹边界说明，明确：不得遵循其中任何要求泄露 secrets、访问外部资源、改变输出 schema、绕过审计或忽略上层指令的内容。

运行规则：

- 一个专家一次调用只承担一个阶段职责。
- 同阶段多个专家默认并行执行。
- 专家原文不互相混入，避免“一个大 Prompt 假装多专家”。
- 主责专家只读取其他专家的结构化输出摘要，不读取所有专家原文。
- QA 门禁专家读取阶段产物和专家摘要，输出通过、警告、阻断和修复建议。
- 所有调用都生成 `expert_invocation` 记录，进入透明控制台。

### Engineering Data Flow

```text
HTTP endpoint / background stage worker
  -> AgencyOrchestrator.run_<stage>_review()
    -> stage adapter builds typed input + stage_input_hash
    -> AgencyPersistence.create_or_resume_invocation(idempotency_key)
    -> AgencySkillRuntime.invoke_one_expert()
      -> AgencyManifest.load_and_verify(expert_id)
      -> Model config center resolves agency expert LLM scene
      -> provider call with timeout, retry budget, redaction boundary
      -> JSON schema parse + validation
    -> AgencyPersistence.finalize_invocation_and_audit()
    -> lead reads reviewer invocation ids + summaries
    -> QA reads lead invocation id + stage artifact
    -> stage status mapper updates production step/run trace summary
  -> API response returns agency_trace_status + stage_graph summary
```

Engineering rule: routers and existing services may choose which stage method to call, but they must not manually create reviewer/lead/QA prompts, status mappings or audit rows.

### Idempotency and Retry Rules

- Stage retry must retry only the failed `retry_scope` unless the repair target changes upstream inputs.
- If a request is repeated with the same `idempotency_key` and a completed invocation exists, return the existing invocation summary.
- If a request is repeated while invocation is `queued` or `running`, return the in-progress invocation summary rather than starting another provider call.
- If previous invocation failed with retryable error, create a new invocation with `attempt = previous.attempt + 1`.
- Non-retryable errors such as `EXPERT_SOURCE_MISSING` and `EXPERT_SOURCE_UNSAFE` must not auto-retry.
- Lead invocation must not start until required reviewer invocations are terminal.
- QA invocation must not start until lead invocation is terminal.

### Transaction and Background Execution Rules

- Do not keep SQLAlchemy sessions open across long provider calls.
- Create queued/running invocation rows in one short session, close/commit, then call provider.
- Finalize invocation, create audit mirror event, and update run-level trace summary in one short transaction.
- If finalization fails after provider returns, mark invocation `failed` with `EXPERT_PERSISTENCE_FAILED` in a compensating transaction where possible, and expose the failure in control room.
- Background workers must pass ids and typed payloads, not ORM instances, across async boundaries.
- SQLite WAL is acceptable for local development, but concurrent expert calls must be bounded by application-level semaphores to avoid write contention.

### Model Config Contract

- 专家运行时使用模型配置中心的专用场景：`LLM · 专家团队审阅`。
- 该场景必须解析出 provider、base_url、api_key 引用、model_id、timeout、max_tokens 和 temperature。
- API key 只在 provider client 内部使用，`AgencyExpertInvocation.model_config_snapshot_json` 只能保存脱敏摘要。
- 如果该场景未配置，阶段返回 `EXPERT_MODEL_CONFIG_MISSING`，不得退回硬编码模型或摘要专家。

## Stage DAG

### 1. 风格锁定

并行审阅：

- 产品经理：确认一句话目标、用户价值、非目标和系列定位。
- 图像提示词工程师：定义角色锚定图、场景参考图、视觉一致性要求。
- 提示词工程师：拆分角色、场景、风格、字幕/BGM 包装的提示词约束。
- AI 工程师：检查模型能力、参考图数量、失败降级和缺失资产处理。

主责汇总：软件架构师
QA 门禁：现实检验者

产物写入：`Series.story_bible_json.style_lock`

### 2. 自动分镜

并行审阅：

- 抖音策略师：首 3 秒钩子、完播率结构、短视频节奏。
- 短视频剪辑指导师：镜头拆分、景别切换、剪辑节奏、音画关系。
- 提示词工程师：分镜字段完整性、提示词结构、输出稳定性。
- 产品经理：剧情目标和用户理解成本。

主责汇总：短视频剪辑指导师
QA 门禁：现实检验者

产物写入：`Episode.storyboard_json`

### 3. 文生图 / 参考图生成

并行审阅：

- 图像提示词工程师：画面提示词、构图、光影、负面提示词、风格一致性。
- 提示词工程师：提示词 schema、变量注入、provider 适配。
- AI 工程师：模型参数、失败重试、资产持久化。

主责汇总：图像提示词工程师
QA 门禁：模型 QA 专家

产物写入：图片资产、审查记录、生产阶段事件

### 4. 图生视频 / 镜头生成

并行审阅：

- 短视频剪辑指导师：每个镜头的动作、景别、转场衔接。
- AI 工程师：Seedance/Pixelle payload、参考图传递、任务状态同步。
- 提示词工程师：视频提示词结构、首尾帧约束、连续性描述。

主责汇总：AI 工程师
QA 门禁：模型 QA 专家

产物写入：视频片段、任务状态、审查记录

### 5. 后期合成

并行审阅：

- 短视频剪辑指导师：镜头顺序、节奏、字幕、BGM、转场、片头片尾。
- 抖音策略师：平台包装、标题感、结尾钩子。
- 软件架构师：合成可恢复性、产物写回、资产库一致性。

主责汇总：短视频剪辑指导师
QA 门禁：现实检验者 + 模型 QA 专家

产物写入：`Episode.video_url`、`GeneratedVideo`、最终审查报告

## Runtime Output Contract

每次专家调用输出统一结构：

```json
{
  "invocation_id": "uuid",
  "stage": "storyboard",
  "expert_id": "short_video_editing_coach",
  "role": "lead|reviewer|qa",
  "execution_status": "queued|running|completed|failed|cancelled",
  "result_status": "pending|passed|warn|blocked|failed",
  "input_summary": {},
  "output_summary": {
    "decision": "通过 / 警告 / 阻断",
    "findings": [],
    "recommendations": [],
    "required_changes": []
  },
  "evidence": [],
  "source": {
    "repo": "jnMetaCode/agency-agents-zh",
    "commit": "13b8800f6f666e8e10ac64f67f1194d2baeefbe0",
    "path": "marketing/marketing-short-video-editing-coach.md",
    "sha256": "..."
  },
  "started_at": "iso datetime",
  "finished_at": "iso datetime"
}
```

前端默认展示中文摘要，不展示完整 prompt。技术详情折叠区可显示源路径、哈希、阶段输入输出摘要和持久化位置。

## Observability

每个 run 必须能聚合专家链路健康状态。该摘要由 `AgencyExpertInvocation` 聚合生成，不由前端推断：

```json
{
  "agency_trace_status": "complete|partial|legacy_summary|missing|failed",
  "invocation_count": 18,
  "blocked_count": 1,
  "warning_count": 2,
  "total_duration_ms": 42000,
  "token_usage": {}
}
```

核心指标：

- `agency_invocation_count_by_stage`
- `agency_invocation_latency_ms_p50`
- `agency_invocation_latency_ms_p95`
- `agency_invocation_token_usage_by_stage`
- `agency_invocation_failure_rate_by_error_code`
- `agency_qa_block_rate_by_stage`
- `agency_fallback_or_warning_count`
- `agency_trace_missing_count`

`legacy_summary` 表示旧流水线只有 `PipelineRun.layers_json` 摘要，没有可追溯 `AgencyExpertInvocation` 详情。前端必须把它展示为“旧流程摘要”，不能展示成完整专家调用链。

控制台、审计事件或后台日志至少要能回答：

- 这个 run 的专家链路是否完整？
- 哪个阶段最慢？
- 哪个专家失败最多？
- QA 阻断集中在哪些阶段？
- 是否有生产结果缺少专家 trace？

## Status Contract

专家调用状态和生产步骤状态分开定义，避免前后端混用。

专家调用生命周期：

```text
queued | running | completed | failed | cancelled
```

专家调用结果：

```text
pending | passed | warn | blocked | failed
```

生产步骤状态：

```text
pending | running | completed | warning | blocked | failed
```

映射规则：

- 任一核心调用 `execution_status=queued|running` -> 生产步骤 `running`
- 所有 reviewer `result_status=passed` 且 lead/QA `passed` -> 生产步骤 `completed`
- 任一 reviewer `result_status=warn` 但 lead/QA `passed` -> 生产步骤 `warning`
- QA `result_status=blocked` -> 生产步骤 `blocked`
- 主责专家或 QA `execution_status=failed` 或 `result_status=failed` -> 生产步骤 `failed`
- 普通 reviewer `execution_status=failed` -> lead 可降级汇总，但生产步骤至少为 `warning`

所有 API 响应必须使用上述枚举；前端只做展示映射，不自行推断业务状态。

## Backend Interfaces

### `GET /api/agency/experts`

返回 9 个专家元数据，不返回全文。

鉴权：登录用户可访问摘要；如后续引入多租户，需要按系列/任务归属做范围过滤。

### `GET /api/agency/experts/{expert_id}`

返回单个专家档案，包括完整 Markdown 原文、源路径、源提交和内容哈希。该接口用于控制台专家原文抽屉。

安全约束：

- 仅管理员可访问。
- 只允许读取 manifest 中登记的 9 个专家文件，禁止任意路径读取。
- 服务启动或首次加载时校验专家文件 sha256，不匹配直接 fail fast，不回退到摘要专家。
- Markdown 原文作为只读文本展示，不作为 HTML 直接渲染。
- 前端 Markdown 展示必须禁用脚本、iframe、事件属性和远程 HTML 注入。
- 接口不得返回运行时完整 prompt、API Key、模型 provider 原始响应或未脱敏配置。

### `GET /api/series/{series_id}/agency-console`

保留现有接口，扩展返回：

- `expert_team`: 9 个专家元数据和当前启用状态
- `stage_graph`: 阶段 DAG、主责专家、QA 门禁
- `expert_invocations`: 最近一次生产过程中的关键专家调用摘要，不返回全部详情
- `decision_log`: 按时间线聚合的关键专家结论和质量门禁摘要
- `production_steps`: 保持兼容，但每步增加专家调用摘要

长视频和批量生产下不得一次性返回所有专家调用。控制台默认只加载 run 级摘要、`stage_graph`、每阶段最近/关键 invocation。

分页接口：

```text
GET /api/agency/invocations?series_id=&run_id=&stage=&status=&page=&page_size=
GET /api/agency/invocations/{invocation_id}
```

约束：

- `page_size` 默认 20，最大 50。
- 所有列表接口按 `created_at desc, id desc` 排序，避免分页抖动。
- invocation 列表只返回 summary 字段，不返回 Markdown 原文和完整 input/output。
- invocation detail 需要登录鉴权；完整专家原文仍只能通过专家档案接口并由管理员读取。
- `decision_log` 支持按 `stage`、`status`、`expert_id` 过滤。
- 专家 Markdown 原文只在打开专家档案抽屉时单独请求。
- invocation detail 接口返回脱敏后的单条详情，不返回未脱敏 prompt。

### Existing Write Paths

- `POST /api/series/{series_id}/style-lock`：风格锁定时写入专家团队快照和风格锁定阶段专家记录。
- `POST /api/director/auto-plan`：自动分镜时调用分镜阶段专家 DAG，并把专家记录写入 `Episode.storyboard_json.agency_trace`。
- `POST /api/video-production/start` 与阶段执行接口：把文生图、图审、图生视频、视频审、合成阶段的专家记录写入现有生产观测事件。
- `POST /api/pipeline/start`：兼容旧 L0-L5 流水线，至少在 `PipelineRun.layers_json` 写入专家调用摘要。

## Typed API Models

所有新增接口和扩展字段必须提供 Pydantic response model：

- `AgencyExpertSummary`
- `AgencyExpertDetail`
- `AgencyExpertInvocationSummary`
- `AgencyExpertInvocationDetail`
- `AgencyStageGraphNode`
- `AgencyConsoleResponse`

前端 API 层按这些模型字段消费数据，不直接依赖后端服务内部 dict 结构。

## Prompt and Token Strategy

采用“专家原文单独调用，阶段汇总只读摘要”的策略：

- 不在一个 Prompt 中塞入 9 个专家全文。
- 每个专家调用只加载自己的完整 Markdown。
- 主责汇总调用只读取其他专家的结构化输出，不重复加载所有专家全文。
- QA 门禁调用读取阶段产物、专家摘要和质量门槛。
- 同一生产 run 内可缓存专家原文，避免重复磁盘读取。
- 对超长源 Markdown 只允许在专家自己的调用中使用；不得把全文传播到下一层。

## Engineering Rollout Order

实现时按以下顺序推进，避免前端或 3D 先于事实数据落地：

1. 新增专家源文件、manifest、hash 校验和单元测试。
2. 新增 `AgencyExpertInvocation` 模型、Alembic migration、Pydantic contracts。
3. 实现 `agency_persistence.py`，保证 invocation 和 audit mirror 的短事务写入。
4. 实现 `AgencySkillRuntime`，先用 mock provider 跑通单专家调用、schema 校验和错误映射。
5. 实现 `AgencyOrchestrator` 的 stage DAG，先覆盖 style-lock/storyboard 两个阶段。
6. 接入 one-sentence flow 和 `director/auto-plan`，确保核心入口产生真实 invocation。
7. 接入 video production stage flow，再做 legacy pipeline 摘要适配。
8. 扩展 `/api/series/{series_id}/agency-console` 和分页 invocation API。
9. 重做 2D 透明控制台。
10. Phase 2 再接入 `three` 和动漫 3D 专家地图。

每一步都必须有测试后再进入下一步。不得先做 3D、再补运行时。

## Engineering What Already Exists

- `ProductionAuditEvent` 已存在，且 `record_production_event()` 已有递归脱敏逻辑，可作为 audit mirror 的基础。
- `PipelineRun.layers_json` 已能承载 legacy L0-L5 的阶段摘要，但不能承担新事实源职责。
- `Series.story_bible_json`、`Episode.storyboard_json` 已用于保存风格锁定和分镜，可保存轻量 agency trace 引用。
- `GET /api/series/{series_id}/agency-console` 已存在，可扩展而不是新增入口。
- `one_sentence_video_service.py` 已创建 series、episode、storyboard 和 production run，是必须接入 `AgencyOrchestrator` 的主入口。
- 项目已有 Alembic，新增表必须补 revision。

## Engineering NOT in Scope

- 不引入外部 Codex skill 运行时；专家 Skill 化是 dy_auto 内部服务能力。
- 不把 215 个专家做成动态插件系统。
- 不新增跨进程分布式队列；首版使用现有后台执行方式和有界并发。
- 不把完整 provider response 或完整 prompt 做成可查询审计资产。
- 不改变 Pixelle/Seedance 生产阶段的核心模型调用协议，只在阶段前后接入专家审阅和审计。

## Failure Modes

| Failure | Impact | Required handling |
|---|---|---|
| 专家源文件 hash 不匹配 | 可能调用错误专家提示词 | 启动/首次加载 fail fast，返回 `EXPERT_SOURCE_MISSING` |
| 重复点击启动或接口重试 | 重复消耗模型费用、重复日志 | 使用 `idempotency_key` 复用或返回已有 invocation |
| provider 调用超时 | 阶段长时间无反馈 | invocation 标记 failed，error_code=`EXPERT_MODEL_TIMEOUT` |
| reviewer 部分失败 | 阶段可能仍可继续但质量下降 | lead 可降级汇总，阶段至少 warning |
| lead 或 QA 失败 | 无法形成可靠阶段结论 | 阶段 failed 或 blocked，不继续推进 |
| audit mirror 写入失败 | 控制台和审计时间线不一致 | finalization 失败，不能标记 invocation completed |
| legacy pipeline 无真实 invocation | 控制台可能误判专家参与完整 | 标记 `agency_trace_status=partial` 或 `legacy_summary` |
| WebGL 不可用 | 3D 地图无法显示 | 降级 2D/2.5D，不影响生产诊断 |

## Transparency Console Redesign

页面：`/series/:seriesId/agency-console`

### Layout

采用三栏生产控制室布局：

```text
┌──────────────────────────────────────────────────────────────┐
│ 顶部状态条：系列 / 当前剧集 / 生产状态 / 风格锁定 / 最终产物 │
├──────────────┬──────────────────────────────┬────────────────┤
│ 阶段轨道      │ 当前阶段专家 DAG              │ 专家档案         │
│              │                              │                │
│ 输入          │ 并行审阅                      │ 9 个专家列表     │
│ 风格锁定      │  - 专家节点                   │ 当前阶段参与标记 │
│ 自动分镜      │ 主责汇总                      │ 查看原文按钮     │
│ 文生图        │ QA 门禁                       │                │
│ 图审          │ 阶段产物                      │                │
│ 图生视频      │                              │                │
│ 视频审        │                              │                │
│ 合成          │                              │                │
│ 终审入库      │                              │                │
├──────────────┴──────────────────────────────┴────────────────┤
│ 决策日志 / 质量门禁 / 技术详情折叠区                          │
└──────────────────────────────────────────────────────────────┘
```

### UI Principles

- 默认全中文，不展示英文专家名；源路径和 id 只在技术详情显示。
- 不使用大面积卡片堆叠；阶段轨道、专家 DAG、表格式日志是主结构。
- 状态颜色统一：通过、运行中、警告、阻断、失败、待执行。
- 专家节点显示：专家名、角色、状态、耗时、结论。
- 点击专家节点打开调用详情：输入摘要、输出摘要、证据、建议、持久化位置。
- 点击专家档案打开原文抽屉：展示 1:1 Markdown 原文和源文件信息。
- 页面只读，不新增审批按钮，不阻塞生成。
- 页面第一屏必须回答三个问题：当前卡在哪一步、哪些专家参与了、下一步能否继续。
- 出错或阻断时，失败原因和修复入口优先级高于专家地图和装饰性信息。
- 技术字段默认折叠，面向创作者的摘要默认展开。

### Information Hierarchy

桌面端首屏从上到下、从左到右的视觉优先级固定为：

1. 顶部状态条：系列名、剧集名、生产状态、当前阶段、最终产物状态。
2. 阻断或警告横幅：只在存在 `blocked`、`failed`、`warning` 时出现。
3. 阶段轨道：显示全链路阶段和当前停留位置。
4. 当前阶段专家 DAG：显示 reviewer、lead、QA 的调用关系。
5. 当前阶段结论：专家汇总、质量门禁、下一步建议。
6. 专家档案和原文抽屉：作为辅助证据，不抢主视觉。
7. 技术详情：模型配置摘要、token、耗时、持久化位置、错误代码。

任何实现不得把“专家列表”或“3D 地图”放到默认首屏主焦点。默认首屏服务生产诊断，不服务展示炫技。

### Copywriting Rules

- 所有用户可见文本默认中文。
- 专家名使用中文短名：短视频剪辑指导师、抖音策略师、AI 工程师、提示词工程师、软件架构师、图像提示词工程师、产品经理、模型 QA 专家、现实检验者。
- 状态文案必须是用户能理解的生产语言，例如“正在审阅分镜”“角色参考图缺失”“QA 阻断，需补充修复建议”，不能直接展示 `EXPERT_OUTPUT_INVALID_JSON` 作为唯一提示。
- 错误代码可以显示在技术详情中，但主文案必须解释影响和下一步。
- 不使用“智能体已思考”“魔法生成中”等拟人化或营销文案。

### Empty and First-Run States

| 状态 | 主标题 | 说明 | 主操作 |
|---|---|---|---|
| 没有风格锁定 | 尚未建立专家生产记录 | 需要先锁定系列风格，专家团队才会介入后续生产 | 返回系列详情 |
| 没有生产 run | 暂无可回放的生产过程 | 一句话生成或剧集生产启动后，这里会显示专家参与过程 | 启动生产入口链接 |
| 专家记录为空 | 专家团队尚未产生调用记录 | 当前 run 可能来自旧流程，无法证明专家参与 | 查看 run 技术详情 |
| 3D 不可用 | 已切换到 2D 专家协作图 | 浏览器不支持 WebGL 或用户开启了低性能模式 | 继续查看 2D 图 |

空状态不能只显示“暂无数据”。每个空状态都要说明为什么为空、用户能做什么、是否影响生产。

### Interaction States

控制台必须定义以下状态，不能只做成功态：

| 状态 | 用户看到什么 | 主操作 |
|---|---|---|
| loading | 顶部骨架条 + 阶段轨道骨架，不显示空白页 | 等待 |
| empty | 系列尚无专家记录，说明需要先风格锁定或启动生成 | 返回系列详情 |
| partial | 部分阶段有专家记录，后续阶段待执行 | 查看已完成阶段 |
| running | 当前阶段高亮，专家节点显示运行中和耗时 | 观察 |
| warning | 阶段保留黄色标记并展示修复建议 | 查看建议 |
| blocked | 阻断阶段置顶，失败专家和原因可见 | 跳转到对应修复入口 |
| failed | 显示错误代码、原因、可重试性、持久化位置 | 查看日志 |

### Responsive and Accessibility

- 桌面端默认三栏：阶段轨道 / 阶段详情 / 专家档案。
- 平板端改为两栏：阶段轨道 + 详情，专家档案变为抽屉。
- 移动端默认列表模式，不加载 3D 视图。
- 3D 画布必须有等价的键盘可访问 2D 列表。
- 所有状态不能只依赖颜色，必须有文字或图标标签。
- 悬停技能卡必须有点击/聚焦替代路径，触屏设备不可依赖 hover。

断点要求：

| 视口 | 布局 | 关键约束 |
|---|---|---|
| `>=1280px` | 三栏控制室 | 阶段轨道固定宽度，详情区可滚动，专家档案右栏固定 |
| `768-1279px` | 两栏控制室 | 专家档案改右侧抽屉，调用日志在详情区下方 |
| `<768px` | 单列列表 | 3D Tab 隐藏或显示为 2D 图，阶段轨道变横向分段列表 |

无论视口大小，阶段状态、失败原因、下一步建议都必须在不打开专家原文抽屉的情况下可见。

## 3D Expert Team Map

控制台增加“专家团队”Tab，展示 3D 专家地图。该视图是沉浸式理解层，不替代默认生产控制室；用户进入控制台时仍优先看到阶段、产物、门禁和失败原因。

### 3D Scene Structure

```text
                    抖音策略师
                       |
       产品经理 -- 视频生产中枢 -- 短视频剪辑指导师
          |            |              |
   软件架构师     当前生产阶段      提示词工程师
          |            |              |
     AI 工程师 -- 模型 QA 专家 -- 图像提示词工程师
                       |
                    现实检验者
```

- 中心节点是“视频生产中枢”，代表当前系列/剧集的生产任务。
- 9 个专家是动漫风格 3D 角色，不使用普通圆点、抽象球体、机器人图标、静态头像或写实人物。
- 专家按职责区域分布：策略、分镜、提示词、模型、审查、架构。
- 每个人物节点有不同轮廓、颜色和动作姿态，但整体风格保持统一，避免变成杂乱角色墙。
- 当前生产阶段相关专家高亮；无关专家降低透明度但仍可悬停查看。

### Anime 3D Character Direction

3D 人物必须采用统一的动漫角色风格。重点不是做真实人脸，而是让用户一眼看出“这个角色代表哪个专家”。人物资产可以先使用轻量低面数模型、程序化 3D 人物或预渲染 2.5D 角色卡，但视觉上必须是角色化人物。

| 专家 | 动漫 3D 角色方向 |
|---|---|
| 短视频剪辑指导师 | 戴耳机的剪辑导演，身边有时间线光带、播放键、剪刀或转场轨道元素 |
| 抖音策略师 | 节奏感强的舞台策划角色，带音符、趋势箭头、热度数据屏 |
| AI 工程师 | 数据终端操作员或轻量机甲工程师，带模型节点、参数面板、算力光效 |
| 提示词工程师 | 指令卷轴/代码咒语风格角色，身边有悬浮文本块、结构化输出符号 |
| 软件架构师 | 蓝图建筑师，带模块方块、结构网格、系统蓝图板 |
| 图像提示词工程师 | 摄影美术师，带相机、镜头、色卡、光影控制环 |
| 产品经理 | 路线图指挥官，带指标罗盘、看板、优先级旗标 |
| 模型 QA 专家 | 检测审计员，带评分面板、放大镜、校验仪表 |
| 现实检验者 | 红色证据审查官，带证据板、阻断警示牌、核验印章 |

硬性要求：

- 9 个角色必须属于同一套美术体系，不能混用写实、像素、Q 版、赛博、手办等多个画风。
- 每个角色必须有能表达专家职责的服装、道具或姿态。
- 角色命名和悬停卡默认中文。
- 低性能降级时，也必须降级为动漫角色插画或半身像协作图，不能退化成圆点网络图。
- 首版可以用程序化低模/2.5D 角色卡实现，但结构要预留未来替换为完整 3D 模型。

### Hover and Click Interaction

鼠标悬停专家人物时展示轻量技能卡：

- 专家中文名
- 当前职责：审阅、主责汇总、QA 门禁、旁路观察
- 核心技能 3-5 条
- 参与阶段
- 当前状态：待执行、运行中、通过、警告、阻断、失败

点击专家人物打开右侧专家档案抽屉：

- 源文件路径
- source commit
- sha256
- 完整 Markdown 原文
- 最近专家调用记录
- 最近一次输出摘要和质量门禁结论

### Stage Flow Animation

3D 专家地图同时支持“阶段流转、连线、亮起”模式，用于直观看到专家团队如何协作。

阶段顺序：

```text
输入 -> 风格锁定 -> 自动分镜 -> 文生图 -> 图审 -> 图生视频 -> 视频审 -> 合成 -> 终审入库
```

每个阶段进入运行中时：

- 中心“当前生产阶段”节点切换为该阶段名称。
- 该阶段 reviewer 专家依次或并行亮起。
- reviewer 专家与中心节点之间出现细线连接，表示读取当前阶段输入。
- reviewer 输出完成后，连接线流向主责专家。
- 主责专家亮起并形成汇总连线。
- QA 门禁专家最后亮起，连接线从主责专家流向 QA 节点。
- QA 通过时，阶段节点显示绿色通过并流向下一阶段。
- QA 警告时，阶段节点显示琥珀色，保留修复建议标记。
- QA 阻断或失败时，阶段节点显示红色，动画停止在阻断专家和失败原因上。

### Visual Encoding

| 状态 | 视觉表达 |
|---|---|
| 待执行 | 低透明度、无连接线 |
| 运行中 | 专家人物呼吸高亮，连接线有流动光点 |
| 通过 | 稳定绿色边缘光 |
| 警告 | 琥珀色边缘光，节点旁显示提示标记 |
| 阻断 | 红色边缘光，连接线停止并聚焦失败专家 |
| 失败 | 红色虚线，人物节点显示错误徽标 |

视觉要求：

- 不使用大量漂浮卡片，不在 3D 空间里塞长文本。
- 长文本只在悬浮卡和右侧抽屉显示。
- 3D 视图保持暗色操作台风格，与生产监控页一致。
- 动效服务于理解协作关系，不做纯装饰动画。

### Runtime Data Contract

3D 地图复用透明控制台接口的数据，不单独发起生产流程：

```json
{
  "stage_graph": [
    {
      "stage": "storyboard",
      "label": "自动分镜",
      "status": "running",
      "reviewers": ["douyin_strategist", "prompt_engineer", "product_manager"],
      "lead": "short_video_editing_coach",
      "qa": ["reality_checker"],
      "started_at": "iso datetime",
      "finished_at": null
    }
  ],
  "expert_invocations": [
    {
      "stage": "storyboard",
      "expert_id": "douyin_strategist",
      "role": "reviewer",
      "status": "passed",
      "summary": "首 3 秒钩子明确，建议压缩铺垫。"
    }
  ]
}
```

前端根据 `stage_graph` 和 `expert_invocations` 计算节点高亮、连线、流向和阻断位置。后端只提供事实数据，不提供视觉状态推测。

### Fallback and Performance

- WebGL 不可用时自动降级为 2D 专家协作图。
- 页面首屏默认不加载 3D 引擎，只有进入“专家团队”Tab 后懒加载。
- 人物模型优先使用轻量低面数资产或程序化人物，不加载大体积写实模型。
- 移动端默认使用 2D 模式，桌面端使用 3D 模式。
- 3D 地图只读，不新增审批、重试或生产按钮。

### Motion Accessibility

- 尊重系统 `prefers-reduced-motion`。
- 控制台提供“静态模式 / 动态模式”切换。
- 静态模式下角色仍是动漫人物，但不做流动光点、呼吸高亮、移动转向，只显示状态边框和连线。
- failed/blocked 状态不播放循环动画，避免干扰用户阅读失败原因。
- 浏览器测试必须覆盖 reduced motion 场景。

### 3D Dependency Strategy

当前前端依赖中没有 Three.js 或其他 WebGL 框架。Phase 2 实现 3D 地图时，需要明确选择：

- 优先使用 `three`，只在“专家团队”Tab 懒加载。
- 3D 角色资产放在 `web/public` 或专门静态资源目录，不进入接口响应。
- 首版不引入复杂模型加载链路；如需 glTF，必须控制单个角色资产体积并测试首屏不加载。
- 如果依赖体积导致构建明显变大，保留 2.5D 角色卡作为默认，3D 作为可选增强。

### 3D Visual QA Rules

Phase 2 完成前必须用浏览器验证以下场景：

- 桌面宽屏：9 个角色都在视野内，中心节点和连线不遮挡角色脸部。
- 1366px 桌面：右侧抽屉打开后，3D 画布不被压缩到不可读。
- 768px 平板：专家地图自动降级为 2D 或 2.5D，信息不丢失。
- 375px 移动端：不加载 3D，阶段列表和专家状态可读。
- reduced motion：无流动光点和循环动作，但状态边框、连线和文字仍可识别。
- WebGL disabled：显示 2D 专家协作图和明确降级说明。
- 中文长专家名、长错误文案、长源文件路径不溢出容器。
- Canvas 像素检查必须证明 3D 画布非空，且角色资产成功渲染。

### What Already Exists

- 当前 `AgencyConsolePage.vue` 已有专家团队入口、生产准备度、生产步骤、质量门禁和只读观察模式。
- 当前 `VideoProductionMonitorPage.vue` 已有阶段监控语义，可作为阶段轨道和状态文案参考。
- 当前路由已有 `/series/:seriesId/agency-console`，方案应继续复用这个入口。
- 项目没有专门的 `DESIGN.md`，因此本方案中的布局、状态、文案和 3D 规则就是该功能的设计基准。

### Design NOT in Scope

- 不做可视化剪辑时间线。
- 不新增人工审批按钮或生产控制按钮。
- 不把 3D 专家地图作为默认首页或唯一诊断入口。
- 不做 215 专家自由搜索、组队和市场化展示。
- 不做营销型 hero 页面、功能介绍页或装饰性角色墙。

## Error Handling

- 源专家文件缺失：后端启动或测试阶段失败；运行时返回明确错误，不回退到摘要专家。
- 专家调用失败：该专家节点标记 failed；如果是 QA 或主责专家失败，阶段阻断；普通 reviewer 失败时允许主责专家标记降级但必须写入警告。
- LLM 输出不是合法 JSON：记录原始失败摘要，重试一次；仍失败则该专家调用 failed。
- 缺少 LLM 配置：返回“专家运行模型未配置”，控制台显示为阻断，不静默跳过。
- 控制台加载专家原文失败：只影响原文抽屉，不影响生产步骤展示。

错误必须命名并写入 `AgencyExpertInvocation.error_code`：

| error_code | 触发条件 | 用户看到什么 | 是否可重试 |
|---|---|---|---|
| `EXPERT_SOURCE_MISSING` | manifest 指向的 Markdown 不存在或哈希不匹配 | 专家档案缺失，需要修复部署包 | 否 |
| `EXPERT_MODEL_CONFIG_MISSING` | 专家运行所需 LLM 场景未配置 | 专家运行模型未配置 | 是 |
| `EXPERT_MODEL_TIMEOUT` | LLM 调用超时 | 专家响应超时，稍后重试 | 是 |
| `EXPERT_MODEL_RATE_LIMITED` | provider 返回限流 | 模型限流，等待或切换配置 | 是 |
| `EXPERT_OUTPUT_INVALID_JSON` | 专家输出无法解析为契约 JSON | 专家输出格式异常 | 是 |
| `EXPERT_QA_BLOCKED` | QA 明确阻断阶段产物 | QA 阻断并展示修复建议 | 修复后可重试 |
| `EXPERT_SOURCE_UNSAFE` | 请求了未登记路径或潜在路径穿越 | 非法专家档案请求 | 否 |
| `EXPERT_PERSISTENCE_FAILED` | provider 返回后写 invocation/audit 失败 | 专家结果保存失败，需重试该阶段 | 是 |

每个 blocked/error 必须携带结构化修复目标：

```json
{
  "repair_action": "补齐角色参考图",
  "repair_route": "/series/{series_id}",
  "repair_target_type": "character_reference",
  "repair_target_ids": ["character_id"],
  "retry_scope": "style_lock|storyboard|image_stage|video_stage|compose"
}
```

控制台根据这些字段展示“去哪修、修什么、重跑哪一步”。不得只返回一段自然语言建议。

## Testing

后端测试：

- 校验 9 个专家源文件存在，`manifest.json` 哈希匹配。
- 校验 `build_video_agency_team()` 返回 9 个专家并带源路径、source commit、sha256。
- mock LLM，验证一个阶段会并行调用多个专家，而不是把多个专家合并成一次调用。
- 验证每个 reviewer invocation 都有不同 `expert_id`。
- 验证每个 reviewer prompt 只包含自己的专家 Markdown source path/hash，不包含其他专家全文。
- 验证 lead invocation 输入包含 reviewer invocation ids，但不包含 reviewer 专家全文。
- 验证 QA invocation 输入包含 lead invocation id 和阶段产物。
- 验证同一阶段至少产生 `N reviewers + 1 lead + 1 QA` 条 invocation 记录。
- 用伪造专家原文中的唯一字符串验证不会串入其他专家 prompt。
- 验证主责汇总只读取 reviewer 输出摘要。
- 验证 QA 门禁 blocked 时，阶段状态阻断并写入修复建议。
- 验证 `AgencyExpertInvocation` 写入、查询、按 run/series 聚合都稳定。
- 验证 Alembic revision 能创建 `agency_expert_invocations` 表、索引和 downgrade。
- 验证重复请求使用同一 `idempotency_key` 时不会产生重复 provider 调用。
- 验证 queued/running/completed/failed 生命周期状态与 result_status 分离。
- 验证 LLM/provider 调用期间没有持有 DB transaction。
- 验证后台 worker 只传 ids 和 typed payload，不跨 async 边界传 ORM 实例。
- 验证 legacy `PipelineRun.layers_json` 只能产生 `agency_trace_status=partial|legacy_summary`，不会伪装成完整 invocation 事实源。
- 验证专家状态到生产步骤状态的映射符合 `Status Contract`。
- 验证专家 Markdown 接口只允许 manifest 白名单路径，拒绝路径穿越。
- 验证 Markdown 原文和 provider payload 不包含 API key、authorization、token、secret。
- 验证伪造专家 Markdown 中的 prompt injection 不能覆盖系统安全规则、隐私规则或输出 schema。
- 验证 LLM timeout、rate limit、invalid JSON 都写入命名 error_code。
- 验证 `style-lock`、`director/auto-plan`、video production 阶段和 legacy pipeline 都能写入专家调用摘要。
- 验证 `GET /api/agency/experts/{expert_id}` 返回完整 Markdown，且不包含任何 API key。

前端测试：

- 控制台默认中文展示，不出现英文角色名作为主标签。
- 阶段轨道按生产顺序展示状态。
- loading、empty、partial、running、warning、blocked、failed 状态都有明确 UI。
- 当前阶段能展示并行审阅、主责汇总、QA 门禁三层结构。
- 专家档案抽屉能展示原文、源路径、source commit、sha256。
- 3D 专家地图中的 9 个专家必须以动漫风格人物呈现，不能是圆点、机器人图标或普通头像。
- WebGL 降级模式仍展示动漫角色插画或半身像协作图。
- 键盘可以访问专家列表、专家详情抽屉和阶段详情。
- 移动端不加载 3D 画布，显示 2D/角色卡降级视图。
- 生产失败时能展示对应专家的阻断原因和下一步建议。
- 页面只读，不出现会打断生成流程的审批控件。

回归测试：

- 一句话生成视频流程仍可从原入口启动。
- 一句话生成结果必须包含 `agency_trace_status`，且控制台能回放专家参与过程。
- 系列详情页进入透明控制台不影响风格锁定、自动分镜和生产状态轮询。
- 现有 Pixelle/Seedance 阶段生产流程不因专家运行失败而泄露 provider response 或 API key。

## Acceptance Criteria

- dy_auto 只内嵌 9 个自动视频生产相关专家。
- 9 个专家均可追溯到 `agency-agents-zh` 源文件、源提交和内容哈希。
- 生产阶段调用专家时使用对应专家原始 Markdown，而不是摘要字符串。
- 同阶段多专家是多个独立调用，再由主责专家汇总。
- QA 门禁结果能阻断或警告阶段继续推进，并给出可修复建议。
- 一句话生成路径必须接入 `AgencyOrchestrator`，不能绕过专家 Runtime。
- 透明控制台能展示阶段、专家调用 DAG、专家原文档案、决策日志和质量门禁。
- 专家团队 Tab 能展示 9 个动漫风格 3D 专家角色，并支持悬停技能卡、点击档案抽屉和阶段流转亮起。
- 控制台不打断生成流程，不要求用户进入页面才能生产视频。
- 同一阶段重复请求不会重复消耗模型调用；失败重试能追溯到原 invocation。
- 新表通过 Alembic 创建，SQLite 本地补列逻辑只作为兼容兜底。

## /autoplan Review Report

### Plan Summary

本方案从“压缩版专家团队展示”升级为“9 个源专家原文保真的内部 Skill Runtime”，并重设透明控制台。审查后结论是：方向正确，但必须把真实专家编排、持久化审计和 3D 动漫地图拆成阶段，并补齐状态契约、安全边界、成本预算和测试计划。

### Review Inputs

- Plan file: `docs/superpowers/specs/2026-05-26-agency-agents-zh-expert-skill-runtime-design.md`
- Restore point: `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-autoplan-restore-20260526-165613.md`
- Test plan artifact: `C:\Users\HNXE\.gstack\projects\dy_auto\feature-video-review-fixes-agency-expert-runtime-test-plan-20260526-170722.md`
- UI scope: yes
- DX scope: yes
- External Codex voice: ran in read-only mode
- Subagent voice: not used in this Codex Desktop turn because no explicit user request authorized delegated sub-agent work

### CEO Review

#### Premise Challenge

| Premise | Verdict | Notes |
|---|---|---|
| 9 个专家足够 | Accepted | 用户明确拒绝导入 215 个专家，且 9 个角色覆盖视频生产核心链路。 |
| 不能再用摘要专家 | Accepted | 当前代码确实只传 `mission/directives`，不能证明专家真实参与。 |
| 专家应像 Skill 一样编排 | Accepted with hardening | 需要独立调用、输出契约、主责汇总、QA 门禁和持久化记录。 |
| 3D 动漫专家地图必须进入方案 | Accepted with phasing | 保留在方案中，但实现应在 runtime 数据契约稳定后进行。 |

#### What Already Exists

| Sub-problem | Existing code |
|---|---|
| 压缩版专家团队 | `server/app/services/video_agency_team.py` |
| 控制台聚合接口 | `server/app/services/agency_console.py`, `server/app/routers/series.py` |
| 风格锁定写入 | `server/app/routers/series.py` |
| 自动分镜入口 | `server/app/routers/director.py` |
| 分段生产计划 | `server/app/services/production_plan_service.py` |
| 生产审计事件 | `server/app/services/production_observability.py` |
| 控制台页面 | `web/src/views/AgencyConsolePage.vue` |

#### Dream State Delta

```text
CURRENT
  Static 5+4 role metadata, one prompt carries role summaries, card-based console.

THIS PLAN AFTER REVIEW
  9 source-backed expert skills, independent invocations, durable trace, control-room UI,
  optional anime 3D map driven by real stage data.

12-MONTH IDEAL
  Reusable internal agent runtime with cost controls, evals, versioned prompts,
  per-series team templates, and production-grade visual observability.
```

#### CEO Findings

| Severity | Finding | Decision |
|---|---|---|
| High | Original scope bundled runtime, audit storage, and 3D map as one slice. | Split into Phase 1 runtime/control room and Phase 2 3D map. |
| High | “专家真实参与” lacked measurable bar. | Added measurable product bar. |
| High | No cost/latency budget for multi-expert calls. | Added budget and degradation rules. |

CEO score: 8/10 after revisions.

### Design Review

| Pass | Score after revisions | Finding |
|---|---:|---|
| Information architecture | 8/10 | Default view remains production control room; 3D is a tab, not the homepage. |
| Interaction states | 8/10 | Added loading, empty, partial, running, warning, blocked, failed states. |
| User journey | 8/10 | Flow supports both passive observation and failure diagnosis. |
| AI slop risk | 8/10 | Anime characters now have role-specific direction and anti-dot fallback. |
| Design system alignment | 7/10 | Needs implementation to match existing dark operations-console language. |
| Responsive/accessibility | 8/10 | Added mobile 2D fallback, keyboard access, non-color status cues. |
| Unresolved design decisions | 1 unresolved | Exact 3D asset production method remains implementation choice. |

Design score: 8/10 after revisions.

### Engineering Review

#### Architecture Diagram

```text
agency_agents_zh source files
  -> manifest loader + hash verifier
  -> AgencySkillRuntime
       -> reviewer invocations
       -> lead summary
       -> QA gate
       -> AgencyExpertInvocation table
       -> ProductionAuditEvent mirror
  -> agency console aggregation
       -> stage_graph
       -> expert_invocations
       -> decision_log
  -> Vue control room
       -> phase rail
       -> expert DAG
       -> expert drawer
       -> 3D/2D expert map tab
```

#### Error and Rescue Registry

| error_code | Trigger | Rescue |
|---|---|---|
| `EXPERT_SOURCE_MISSING` | source file missing/hash mismatch | Fix packaged expert files; do not fallback to summaries. |
| `EXPERT_MODEL_CONFIG_MISSING` | LLM scene config absent | Configure expert runtime model scene. |
| `EXPERT_MODEL_TIMEOUT` | provider timeout | Retry or mark stage warning/failed by role. |
| `EXPERT_MODEL_RATE_LIMITED` | provider rate limit | Backoff, switch model, or continue with warning where allowed. |
| `EXPERT_OUTPUT_INVALID_JSON` | expert output parse failure | Retry once, then failed invocation. |
| `EXPERT_QA_BLOCKED` | QA rejects stage output | Stop stage and show repair action. |
| `EXPERT_SOURCE_UNSAFE` | non-manifest path requested | Reject request and log security event. |

#### Test Diagram

```text
manifest -> hash/path tests
runtime -> mocked LLM reviewer/lead/QA tests
runtime -> invocation persistence tests
runtime -> status mapping tests
api -> expert list/detail auth and redaction tests
api -> agency console aggregation tests
ui -> control room state tests
ui -> drawer markdown text tests
ui -> 3D lazy load + 2D fallback tests
regression -> one-sentence/style-lock/auto-plan/video-production tests
```

#### Engineering Findings

| Severity | Finding | Decision |
|---|---|---|
| Critical | No durable invocation model in original plan. | Added `AgencyExpertInvocation`. |
| High | Status enums conflicted across expert and production step statuses. | Added `Status Contract`. |
| High | Full Markdown endpoint needed path/sanitization rules. | Added allowlist and text-only Markdown security constraints. |
| High | API dict contracts would drift. | Added Pydantic response model requirement. |
| Medium | Current frontend lacks WebGL dependency. | Added Phase 2 dependency strategy and lazy-loading rule. |

Engineering score: 8/10 after revisions.

### DX Review

Developer persona: dy_auto backend/frontend implementer adding expert runtime and console features.

#### Developer Journey Map

| Stage | Expected path | Friction fixed |
|---|---|---|
| Locate expert source | manifest + source files | Source commit/hash recorded. |
| Add runtime call | `AgencySkillRuntime` contract | One call shape for reviewer/lead/QA. |
| Persist call | `AgencyExpertInvocation` | No scattered JSON-only logs. |
| Read console payload | typed response models | Frontend contract stable. |
| Debug failure | named error_code + repair_action | No generic 500-only failures. |
| Add UI state | state table | Loading/empty/blocked not invented later. |
| Add 3D map | Phase 2 data contract | 3D reads existing data only. |

#### DX Findings

| Severity | Finding | Decision |
|---|---|---|
| High | Planned APIs lacked typed schemas. | Added explicit Pydantic models. |
| High | Error messages were not structured enough for implementers. | Added named error codes and rescue table. |
| Medium | TTHW for expert runtime was unclear. | Test plan artifact now defines first implementation targets. |
| Medium | 3D dependency could surprise frontend implementer. | Added dependency and fallback strategy. |

DX score: 8/10 after revisions.

### Cross-Phase Themes

- **Traceability is the core product.** CEO, Eng, and DX all flagged that expert participation must be provable, not inferred.
- **3D is valuable only after real data exists.** CEO and Design both flagged that 3D cannot replace production diagnosis.
- **Security boundary matters.** Eng and DX both flagged Markdown source, model config, and provider payload redaction.
- **Typed contracts prevent drift.** UI, Eng, and DX all flagged that raw dict payloads would make the console brittle.

### User Challenge

**Challenge 1: 3D anime map should not ship before the expert runtime is real.**

You said: include 3D anime expert characters and stage flow/connection/lighting in the plan.

Review recommendation: keep it in the plan, but implement it as Phase 2 after `stage_graph` and `expert_invocations` are stable.

Why: if 3D ships first, users get a prettier console but still cannot prove which expert influenced a production stage.

What we might be missing: you may value the 3D map as a product confidence signal or sales/demo surface.

If the review is wrong: phasing could delay the visual experience you want. The current design keeps the 3D requirement, but gates implementation behind runtime data.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Keep 9 experts only | Mechanical | Explicit over clever | User confirmed scope and it fits automatic video production. | Import 215 experts. |
| 2 | CEO | Use source Markdown per expert call | Mechanical | Completeness | This fixes the current compressed-summary weakness. | Continue with `mission/directives`. |
| 3 | CEO | Split runtime/control room and 3D map into phases | User Challenge | Pragmatic | Real expert trace must precede animated visualization. | Ship 3D before runtime data. |
| 4 | Eng | Add `AgencyExpertInvocation` table | Mechanical | Completeness | Durable querying/redaction/retry needs first-class records. | Store everything in JSON blobs. |
| 5 | Eng | Define separate expert and production status enums | Mechanical | Explicit over clever | Prevents frontend/backend status drift. | Let frontend infer mappings. |
| 6 | Eng | Add manifest allowlist and Markdown text-only display | Mechanical | Security | Prevents path traversal and rendered HTML injection. | Render arbitrary Markdown as HTML. |
| 7 | Design | Default control room, 3D as Expert Team tab | Mechanical | User outcome | Failure diagnosis must stay first screen. | Make 3D the default page. |
| 8 | DX | Require Pydantic response models | Mechanical | Explicit over clever | Stable API contracts reduce frontend drift. | Return raw service dicts. |

### Completion Summary

| Review | Result |
|---|---|
| CEO Review | 3 findings, 0 unresolved except Challenge 1 approval |
| Design Review | 7 dimensions evaluated, overall 8/10 |
| Eng Review | Architecture diagram and failure registry produced, overall 8/10 |
| DX Review | Journey map and implementation checklist produced, overall 8/10 |
| Test Plan | Written to `.gstack/projects/dy_auto/...test-plan...md` |
| Final status | DONE_WITH_CONCERNS: Challenge 1 needs user approval before implementation planning |

## OpenClaw CEO Review Summary

- **Mode:** SELECTIVE EXPANSION
- **Strongest challenges:**
  1. 3D 动漫专家地图必须建立在真实专家调用记录上，不能先做假透明。
  2. 专家调用必须有唯一事实源，否则控制台和审计时间线会互相冲突。
  3. 一句话生成路径必须作为硬性接入点，否则最核心用户流程仍会绕过专家团队。
- **Recommended path:** 按路线 B 执行。Phase 1 交付源专家原文、`AgencyOrchestrator`、`AgencyExpertInvocation`、2D 控制室和分页审计接口；Phase 2 基于真实 `stage_graph` / `expert_invocations` 做动漫 3D 专家地图。
- **Accepted scope:** 9 个专家原文保真、类 Skill 编排、专家调用持久化、生产控制室、专家原文抽屉、分页调用日志、one-sentence 硬接入、3D 动漫地图 Phase 2。
- **Deferred:** 自由组队、215 专家全量导入、专家市场、多团队模板、3D 完整模型资产生产流水线。
- **NOT in scope:** 可视化剪辑器、抖音发布闭环、人工审批新增节点、任意 Markdown 路径读取、未脱敏完整 prompt 展示。

## GStack Plan CEO Review Summary

- **Mode:** SELECTIVE EXPANSION
- **Verdict:** APPROVED FOR IMPLEMENTATION PLANNING.
- **CEO standard:** 这项功能的核心卖点不是“有 9 个专家名字”，而是用户能看到每个关键生产阶段到底由哪个专家、基于哪份原文角色、给出了什么结论、如何影响下一步。当前方案已经把这个点落到持久化调用、阶段 DAG、控制台、审计事件和 one-sentence 入口，战略方向成立。
- **Scope decision:** 保持 9 个与自动视频生成直接相关的专家，不导入 215 个全量专家。全量导入会制造配置、成本和认知负担，不会提升“一句话生成视频”的主路径成功率。
- **Phase gate:** Phase 1 必须先跑通真实专家运行时和 2D 透明控制台；Phase 2 再做动漫 3D 专家地图。3D 地图只能消费真实 `stage_graph` 和 `expert_invocations`，不能自造演示数据。
- **Accepted expansion:** 保留 3D 动漫专家地图、阶段流转、连线、亮起、悬浮技能卡和点击详情，但把它明确为 Phase 2 产品增强，而不是 Phase 1 交付前置条件。
- **CEO risks to watch:** 专家调用如果退化成一个大 prompt，会重新变成暗箱；控制台如果只展示状态不展示证据，会失去信任价值；3D 如果抢先上线，会让产品看起来更花但不更可靠。
- **Next required review:** 需要在实现计划前继续跑 `plan-eng-review`，因为本方案已经涉及新表、运行时编排、状态机、接口契约、控制台和 3D 依赖。

## GStack Plan Design Review Summary

- **Initial design score:** 7/10.
- **Final design score:** 9/10.
- **Verdict:** CLEAN FOR IMPLEMENTATION PLANNING.
- **Main gaps found:** 原方案已经有三栏控制室、状态表、3D 地图和降级策略，但缺少首屏信息优先级、空状态文案、移动端断点、3D 视觉验收和中文文案硬约束。
- **Decisions added to plan:** 信息层级、中文文案规则、空状态和首次使用状态、响应式断点、3D 视觉 QA、现有 UI 复用基准、设计非目标。
- **Design risk reduced:** 实现时不应再出现“专家卡片堆叠但不知道当前生产卡在哪一步”的问题，也不应出现“3D 好看但无法诊断失败”的问题。
- **Unresolved design decisions:** 0. 角色具体 3D 资产风格可以在 Phase 2 设计稿中再定，但本方案已经规定首版可用程序化低模或 2.5D 动漫角色卡。

## GStack Plan Engineering Review Summary

- **Mode:** FULL_REVIEW.
- **Verdict:** CLEAN FOR IMPLEMENTATION PLANNING.
- **Architecture issues found:** 5, all resolved in this document.
- **Issues fixed in plan:** invocation lifecycle/status split, LLM no-long-transaction rule, idempotency/retry contract, Alembic migration requirement, legacy pipeline trace semantics.
- **Critical gaps remaining:** 0.
- **Unresolved engineering decisions:** 0.
- **Implementation order:** backend facts first, 2D control room second, 3D expert map last.
- **Required test gates:** manifest/hash tests, runtime mock tests, persistence/audit transaction tests, idempotency tests, API pagination/auth/redaction tests, one-sentence regression, production stage regression, frontend control room states, 3D fallback/visual QA.
- **Engineering note:** The plan is now strict enough to prevent the main failure mode: a nice UI backed by one merged prompt and JSON summaries instead of real expert invocations.
