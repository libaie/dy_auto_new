# Multi-resolution Locator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有三层架构中实现可验证、向后兼容的跨分辨率元素定位。

**Architecture:** 新增设备几何模块，集中处理区域、坐标与偏移；现有定位和业务模块消费该契约。服务端校验及 Vue 表单提供同一契约的可编辑入口。

**Tech Stack:** AutoJS6 / Rhino ES5.1, Node runtime simulation tests, FastAPI/Pydantic, Vue 3/Vitest.

**Spec:** `docs/superpowers/specs/2026-11-05-multi-resolution-locator-design.md`

## Global Constraints

- 设备生产代码保持 AutoJS6 / Rhino ES5.1：var、普通 function、CommonJS；不引入依赖或 setScreenMetrics。
- 无障碍 bounds 已为屏幕像素，禁止按分辨率再次缩放。
- 兼容旧坐标/偏移含义；只以明确新字段启用新行为，不批量改写记录。
- 不修改数据库结构，不修改任务授权/调度，不自动重发结果未知的消息。
- 独立工作树，分离文件所有权，根代理统一提交/发布；各实现者不运行 git add/commit/reset，也不创建下级代理。

## Review Focus

1. 键盘出现或窗口移动后原定位点不再有效：几何层与执行器验证新 signature、遮挡区域。
2. 图片坐标源尺寸/旋转不确定：明确变换或失败，不将原始截图点直接点击。
3. 旧 image 偏移和 coordinate 比例同名但语义不同：按类型测试兼容，不二次偏移。
4. 无障碍集合里第一个候选离屏/在错误容器：选择可用区域中的候选，不无条件 first。
5. 点击发送后的状态未知：返回未确认并避免再次发送，不记为成功。

### Task 1: Screen context and coordinate math (root)

**Files:** Create `device/core/screen-context.js`, `device/test/screen-context.node-test.js`.

**Interfaces:** Implements exact exports/fields from spec; consumed by Tasks 2/3/5.

- [x] Add failing tests for normalized mapping across four resolutions, dp offsets, legacy per-type offset meanings, capture resize/crop/rotation round trip, unknown aspect failure, blocked/stale areas, invalid finite values.
- [x] Run `node --test device/test/screen-context.node-test.js`, record expected missing behavior.
- [x] Implement pure geometry and guarded runtime discovery without module-load AutoJS calls.
- [x] Run focused tests; inspect runtime API assumptions against official docs.

### Task 2: Locator and action integration

**Files:** Modify only `device/core/ui-operator.js`; may create `device/core/image-locator.js`; tests `device/test/ui-operator.node-test.js` and `device/test/image-locator.node-test.js`.

**Interfaces:** Consume all geometry exports from spec. Preserve raw UiObject returns, attach signature to point results. Add `clickAction(actionName, timeout, options?) -> boolean`, optional `{click_mode:"press", press_duration:150}`. Keep existing API signatures compatible.

- [x] Add failing tests for scale factors (not pixel dimensions), equal x/y scales, fixed thresholds, bounded region conversion, edge 0, invalid point/offset rejection, press coordinate double-offset regression, coordinate-only page detection rejection, stale point rejection and fresh `clickAction`.
- [x] Wire geometry, anchor/region filtering, explicit/legacy units, image matching bounded by region, per-call display state and capture dimensions.
- [x] Use at most five scale attempts per candidate, avoid stretched templates and lowered thresholds, recycle screenshots/templates/scaled copies exactly once.
- [x] Make click/input helpers return actual actuation results and check target visibility immediately before action. Existing semantic node consumers must still work.
- [x] Run focused tests then report exact commands, results, concerns to `.superpowers/sdd/multi-resolution/task-2-report.md`.

### Task 3: Handler positioning and observed results

**Files:** Modify only `device/handlers/search-base.js`, `device/handlers/reply-comment.js`, `device/handlers/comment-utils.js`, optional new `device/core/ocr-locator.js`; tests `device/test/handler-positioning.node-test.js`, `device/test/ocr-locator.node-test.js`.

**Interfaces:** Consume geometry exports and `uiOperator.clickAction` (see Task 2). Avoid editing shared ui-operator/screen-context. Real UiObject bounds are screen pixels.

- [x] Add failing tests for text-only OCR never causing guessed taps, structured OCR mapping into scoped region, multiple OCR candidates rejection, follow retry re-location, failed/unknown send not reported as success, capture-clipped avatar bounds and list-local gestures.
- [x] Scope search input/tab and list traversal to known content/container bounds with dp-aware minimums, avoiding fixed parent().parent() for clickable targets.
- [x] Remove blind follow/ordering fallback; fresh click each retry and explicit followed-state evidence.
- [x] Sending performs at most one submission when success is uncertain; verify a concrete postcondition and return false/unknown otherwise. Do not silently send again through Enter after an attempted click.
- [x] Run focused tests then report to `.superpowers/sdd/multi-resolution/task-3-report.md`.

### Task 4: Configuration validation and UI

**Files:** Modify `server/app/routers/selectors.py`, create `server/app/services/selector_validation.py` if useful; modify `web/src/components/StrategyCard.vue`, `web/src/views/SelectorsPage.vue`; tests `server/tests/test_selector_strategy_validation.py`, `web/src/__tests__/selector-strategy-coordinates.test.js` (optional small helpers in web/src/utils).

**Interfaces:** Follow spec coordinate contract verbatim. No DB schema migration. Validate effective purpose+strategies on updates as well as creation. Preserve unrelated existing selector types/conditions/chain data.

- [x] Add failing API tests for explicit positions, offsets, regions, anchors, template scale metadata and invalid/nonfinite/range values. For page_detect reject coordinate evidence; legacy valid configurations continue passing.
- [x] Add UI tests proving zero retained, legacy type-specific labels and new explicit position/offset/region controls emit exact contract, switching types does not leak legacy coordinate values as node offsets.
- [x] Implement validation and form controls; use form labels/inline help instead of requiring JSON for core new fields. New coordinate default content_normalized; loaded legacy remains screen 0–1 until explicitly changed.
- [x] Run focused Python/Vitest commands then report to `.superpowers/sdd/multi-resolution/task-4-report.md`.

### Task 5: Geometry refresh and reliable calibration (root)

**Files:** Modify `device/core/selector-loader.js`, `device/core/calibrator.js`, `device/core/api-client.js`, server device router/models/selector service; add calibration service and focused calibration/live-geometry/unknown-DM tests. Update the existing data-center pending status label; no DB migration.

- [x] Add failing tests for reselecting profiles after screen-size change and excluding coordinate-only templates from unattended calibration.
- [x] Preserve server distribution contract, reselect/refetch on changed geometry, use live resolution.
- [x] Crop observed semantic bounds via shared capture transform; skip unknown/wrong page/ambiguous mappings. Keep existing calibration upload API compatible.
- [x] Guard calibration with source identity/revision and target app version, immutable asset names, and complete pre-publication validation.
- [x] Preserve unknown DM outcomes beyond the legacy orphan timeout using the existing status column and a backward-compatible optional claim flag.
- [x] Run tests and document boundaries of physical-device validation.

### Task 6: Integration, review, delivery (root)

**Files:** `docs/operations/2026-11-05-multi-resolution-locator.md`, spec/plan progress.

- [x] Review all changes together, including ES5.1 parse/runtime and existing script load-order tests.
- [x] Run all Node device tests, full backend pytest, full frontend Vitest and production build. Use fresh isolated test DB with empty external-provider keys.
- [x] Independent whole-branch review; address concrete findings with reproducing tests.
- [ ] Commit and publish a new branch and reviewable PR through authorized GitHub connection, verify remote tree equals tested code. Do not merge or deploy this new PR automatically.
- [ ] Provide Chinese implementation/configuration guide, test results, known real-device limits, PR link.
