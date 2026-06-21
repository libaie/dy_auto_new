# Business Code Chinese Comments Design

## Context

The project now has a large business surface:

- backend production Python under `server/app`, especially `server/app/domains`;
- frontend production UI and state code under `web/src`;
- device automation production scripts under `device/core`, `device/handlers`, `device/utils`, `device/main.js`, and `device/config.js`.

Across these areas, business rules are concentrated in AI video production, multi-agent review, provider execution, image generation, content collection, device automation, and operational control pages. Comments are currently uneven: some files explain domain intent, while many complex workflows require reading the implementation to understand the business contract.

The user request is: all business code should have standard Chinese comments.

## Decision

Add standard Chinese comments to all production business code in batches. Do not mechanically comment every line. A comment is required only when it helps a maintainer understand business ownership, workflow state, side effects, constraints, or non-obvious decisions.

This keeps the final state broad enough for "all business code" while avoiding noisy comments that repeat syntax.

## Scope

Included production business code:

- `server/app/domains/**/*.py`
- `server/app/main.py`
- `server/app/models/**/*.py`
- `server/app/utils/**/*.py` when the file contains business behavior rather than generic plumbing
- `web/src/**/*.vue`
- `web/src/**/*.js`
- `web/src/**/*.ts`
- `web/src/**/*.tsx`
- `device/main.js`
- `device/config.js`
- `device/core/**/*.js`
- `device/handlers/**/*.js`
- `device/utils/**/*.js`

Excluded non-business or non-production code:

- tests under `server/tests`, `web/src/__tests__`, `tests`, and `device/test`
- spike or scratch code under `device/spike`
- build, package, lock, generated, archive, static asset, and cache files
- docs and reports, except this design and any implementation plan

## Chinese Comment Standard

Use concise Simplified Chinese. Comments should explain business meaning, not code mechanics.

Required comment locations:

1. Module header for every included business file.
   - Python: module docstring at the top of the file.
   - Vue/JS/TS: leading block or line comment before business imports or component logic.
2. Public service functions, route handlers, jobs, workers, and orchestration entry points.
   - Explain what business action the function performs.
   - Mention important inputs, outputs, and persistence side effects when relevant.
3. State machines, queues, retries, idempotency, approval gates, budget gates, and provider calls.
   - Explain the state transition and why the guard exists.
4. Device automation flows.
   - Explain the user-visible Douyin action, safety boundary, and fallback condition.
5. Frontend workflow pages and composables.
   - Explain which backend workflow or user task the component coordinates.

Forbidden comment styles:

- comments that translate syntax, such as "遍历列表" above a `for` loop;
- stale roadmap notes without an owner or current decision;
- duplicate comments that say the same thing as a function name;
- large prose blocks inside hot code paths when a short docstring is enough;
- comments that expose secrets, provider keys, account data, or private user data.

## Examples

Good Python module header:

```python
"""视频生产任务执行服务。

负责把已审核的分镜、图片、视频和合成任务推进到 provider 阶段，并把外部任务状态落回本地生产作业。
"""
```

Good business guard comment:

```python
# 生产作业必须先占用预算再提交 provider，避免外部任务成功但本地无法结算。
```

Bad comment:

```python
# 遍历 jobs 列表
for job in jobs:
    ...
```

Good frontend comment:

```js
// 生产控制台聚合 run、job、asset 三层状态，页面只展示后端已归一化的业务进度。
```

Good device comment:

```js
// 评论采集在进入用户主页前先做本地过滤，减少无效跳转和账号操作风险。
```

## Rollout Plan

Batch 1: backend high-risk production flows.

- `server/app/domains/ai_video_series`
- `server/app/domains/agency_operations`
- `server/app/domains/video_production`
- `server/app/domains/image_generation`
- `server/app/domains/pixelle_integration`
- `server/app/domains/seedance_integration`
- `server/app/domains/model_configuration`
- `server/app/domains/quality_audit`

Batch 2: remaining backend domains and business utilities.

- content collection, device operations, creative library, prompt management, selector management, reporting, system operations, identity access, and related service files.

Batch 3: frontend production workflows.

- Vue pages, business components, API clients, workflow composables, constants that encode business labels or states.
- Exclude tests and pure styling files unless a style token has business meaning.

Batch 4: device automation production scripts.

- `device/core`, `device/handlers`, `device/utils`, `device/main.js`, and `device/config.js`.
- Exclude `device/test` and `device/spike`.

## Verification

Add a small repository script or test that checks the final contract:

1. Included business files have a Chinese module-level comment.
2. High-risk files have comments near provider calls, queue workers, approval gates, idempotency, retry loops, and device side effects.
3. Excluded directories are not scanned.
4. The checker flags obvious placeholder comments and English-only module headers in included files.

The checker should be advisory during early batches and become blocking after all batches are complete.

Manual review remains necessary for comment quality. The checker proves coverage, not usefulness.

## Risks

Risk: adding comments mechanically can make the code harder to read.

Mitigation: only add comments at module, public entry point, side-effect, and complex rule boundaries.

Risk: comments drift when behavior changes.

Mitigation: keep comments short and close to the code they explain.

Risk: full repository coverage is too large for one change.

Mitigation: ship in batches with independent verification after each batch.

## Acceptance Criteria

- Every included business production file has a concise Chinese module-level comment.
- Complex business functions and workflow entry points have Chinese docstrings or comments.
- Provider calls, paid execution, queue workers, idempotency, approval, retry, and device side effects have nearby Chinese business comments.
- Tests, spike code, generated files, static assets, package files, and docs are excluded from mandatory coverage.
- A verification script or test reports remaining coverage gaps by file.
- Existing automated tests for each touched domain continue to pass.

## Self-Review

- No placeholder sections remain.
- Scope keeps the user's full "all business code" target while excluding non-business files.
- The standard avoids low-value syntax comments.
- The rollout is small enough to implement safely in separate commits.
