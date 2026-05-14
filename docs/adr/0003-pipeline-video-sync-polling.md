# ADR-0003: Pipeline 视频生成层改为同步轮询

**Date**: 2026-05-14
**Status**: accepted
**Deciders**: xxy2026

## Context

Pipeline L4（`/api/video/generate/async`）当前是 fire-and-forget 模式：提交异步视频生成任务后立即标记 completed，无论视频是否真正完成渲染。这导致：

- L5（postproduction）可能在视频完成前执行，对空视频或无视频做后处理
- 前端无法从 pipeline status 得知视频生成的真实进度
- Pipeline 无法区分"已提交"和"已完成"

前端 VideoStudio.vue 目前通过 `pollTask` 独立轮询，但这是前端逻辑，pipeline 状态不反映实际进度。

## Decision

**Pipeline L4 在 `_run_all_layers` 内同步轮询视频生成任务直到完成或超时。**

- L4 调用视频生成 API 后，进入轮询循环
- 轮询间隔：10 秒
- 超时上限按 videoModel 差异化：
  - Seedance: 180 次轮询（30 分钟）
  - Kling/其他: 120 次轮询（20 分钟）
  - Pixelle 默认: 120 次轮询（20 分钟）
- 每次轮询更新 `layers_json[4].progress` 供前端读取
- 超时视为失败，标记 `status = "failed"`，支持 resume

Pipeline 前端查询 API（`/runs/{series_id}/{run_id}`）返回 layers_json 中的实时进度。

## Alternatives Considered

### Alternative 1: Webhook 回调
- **Pros**: 不占用 pipeline 连接，精确完成通知
- **Cons**: 需要 Pixelle-Video 支持回调（目前不支持），需要 dy_auto 暴露公网端点
- **Why not**: 基础设施依赖太重，不适合当前架构

### Alternative 2: 保持 fire-and-forget + 前端轮询
- **Pros**: 无后端改动
- **Cons**: Pipeline 状态不反映真实进度，L5 可能在视频完成前执行
- **Why not**: 这破坏了 pipeline 编排的核心价值

## Consequences

### Positive
- Pipeline 状态精确反映视频生成进度
- L5 后处理始终在视频完成后执行
- 前端可移除独立的视频轮询逻辑，统一从 pipeline status 读取

### Negative
- L4 执行时间从秒级变到分钟级（15-30 分钟），pipeline 总耗时显著增加
- `_run_all_layers` 的 asyncio task 生命周期更长

### Risks
- 超长轮询可能触发 HTTP 中间件或代理的超时
  - **Mitigation**: `_run_all_layers` 在后台 asyncio task 中运行，不受 HTTP 请求超时影响
- Pixelle-Video 重启导致轮询中断
  - **Mitigation**: pixelle_client 已有 retry 机制，轮询失败 3 次后标记任务失败
