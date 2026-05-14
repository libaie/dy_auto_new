# ADR-0002: Seedance 合并为 Pipeline L4 的第二 Provider

**Date**: 2026-05-14
**Status**: accepted
**Deciders**: xxy2026

## Context

Seedance 2.0（火山方舟 Ark API）在 seedance.py 中作为独立路由实现，完全在 pipeline 编排之外。这意味着：
- Seedance 视频生成无 checkpoint 恢复、无重试策略、无幂等性检查
- 前端 VideoStudio.vue 的 "Seedance 2.0" Tab 使用完全不同的代码路径
- Seedance 生成的视频无法被 pipeline 的后处理层（L5 postproduction）自动处理
- 维护两套视频生成的提交/轮询/错误处理逻辑

Pipeline 当前有 6 个固定层（L0-L5），全部硬编码调用 Pixelle-Video 端点。L4（视频生成）只支持 Pixelle-Video 的 `/api/video/generate/async`。

## Decision

**将 Seedance 合并为 Pipeline L4 的第二个 provider。** Pipeline 的 L4 层支持双后端路由：
- `videoModel: "auto"` 或 `"pixelle"` → 走 Pixelle-Video `/api/video/generate/async`
- `videoModel: "seedance"` → 走 Seedance Ark API submit + poll

PipelineLayerConfig 的 `videoModel` 字段控制路由。Seedance 的提交和轮询逻辑纳入 `_run_all_layers` 流程，继承 pipeline 的 checkpoint、重试、幂等性。

## Alternatives Considered

### Alternative 1: Seedance 保持独立
- **Pros**: 不增加 pipeline 复杂度，seedance.py 独立可测
- **Cons**: 两套代码路径无共享编排能力，无 checkpoint/重试/幂等性，前端维护两套交互
- **Why not**: 双路径维护成本 > 合并复杂度

### Alternative 2: 仅给 Seedance 加 checkpoint
- **Pros**: seedance.py 获得最基本的状态持久化
- **Cons**: 仍无 pipeline 编排收益，无法被 L5 后处理自动消费
- **Why not**: 半吊子方案 — 增加了 seedance.py 的复杂度却没解决核心问题

## Consequences

### Positive
- Seedance 视频生成获得 pipeline 的 checkpoint 恢复、重试、幂等性
- Pipeline L5（postproduction）可以自动处理 Seedance 生成的视频
- 前端可统一通过 pipeline API 管理所有视频生成流程
- 减少 seedance.py 的独立轮询/状态管理代码

### Negative
- pipeline.py `_run_all_layers` 增加条件分支（L4 provider dispatch）
- Seedance API key 管理需要从 seedance.py 提取到共享模块

### Risks
- Pixelle-Video 和 Seedance 的提交/轮询 API 不同，L4 需要适配两种响应格式
  - **Mitigation**: L4 内部定义统一的 VideoTaskHandle 接口（submit + poll），两个 provider 分别实现
