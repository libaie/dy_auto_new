# ADR-0004: Director 作为 Pipeline 前置步骤

**Date**: 2026-05-14
**Status**: accepted
**Deciders**: xxy2026

## Context

`director.py` 的 POST `/api/director/plan` 接口接收分镜数据（镜头类型、景别、运镜、光照、色彩等），组装为结构化的 JSON 分镜表返回。但此分镜表：

- 不触发任何下游执行 — 用户需要手工将分镜数据传递给 pipeline
- 无持久化存储 — 分镜表不在数据库中，刷新即丢失
- 与 pipeline 的 `LAYER_ENDPOINTS` 无连接

Pipeline 目前从 `common = {"series_id": ..., "episode_id": ...}` 起步，没有任何分镜上下文。Pixelle-Video 的各层 API 接收这些通用参数，但无法按逐帧分镜执行精细化渲染。

## Decision

**Director 作为 Pipeline 的可选前置步骤（pre-step），不改变 director 的核心职责。**

1. `director.py` POST `/api/director/plan` 保持不变 — 仍返回分镜表 JSON
2. `pipeline.py` POST `/api/pipeline/start` 新增可选参数 `director_plan: dict | None`
3. 当 `director_plan` 传入时，`_run_all_layers` 按每帧执行：
   - 对分镜中的每个 frame，使用 frame 的 `image_prompt`/`shot_type`/`camera_movement` 等参数调用 L0/L3/L4
   - 逐帧生成图片 → 逐帧生成视频片段 → L5 合成
4. 当 `director_plan` 为空时，行为与现在完全一致（全局模式）

## Alternatives Considered

### Alternative 1: Director 保持现状（不接入 pipeline）
- **Pros**: 零额外开发
- **Cons**: director 的价值永远停留在 JSON 输出，无闭环能力
- **Why not**: 浪费了已有代码，用户需要手工搬运分镜数据

### Alternative 2: 将 director 合并进 pipeline.py
- **Pros**: 少一个路由文件
- **Cons**: pipeline.py 复杂度增大，director 失去独立演进的灵活性
- **Why not**: 合并不等于简化 — director 未来可能独立发展（如分镜预览、A/B 方案对比）

## Consequences

### Positive
- 分镜表从静态 JSON 变为可执行的视频生成计划
- Pipeline 获得逐帧精细化控制能力
- 用户流程闭环：填写分镜 → 一键跑 pipeline → 得到逐帧视频

### Negative
- Pipeline 逻辑从 6 个固定层扩展到 N×6 潜在步骤（N = 分镜帧数）
- Pipeline start API 增加一个可选参数

### Risks
- 逐帧执行可能大幅增加 pipeline 总耗时（N 帧 × 每层延迟）
  - **Mitigation**: 第一版不做逐帧并行优化（保留给后续 ADR）。对首帧执行完整 6 层，后续帧跳过已完成的 narration/title 层
