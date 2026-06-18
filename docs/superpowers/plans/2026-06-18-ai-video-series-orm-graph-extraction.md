# AI Video Series ORM Graph Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Physically move `ai_video_series` ORM class bodies only after the relationship graph, import order, Alembic model loading, and legacy facade behavior are proven with tests.

**Architecture:** Start from the shared `app.db.base.Base` and `app.db.models.ai_video_series` facade created by the server modularization plan. Map ownership for `Series`, `Episode`, `ProductionPlan`, `ProductionPlanVersion`, `ProductionEpisode`, `ProductionScene`, `ProductionShot`, `ProductionSegment`, `ProductionJob`, `AITextArtifact`, `AITextArtifactConsumer`, `ProductionAuditEvent`, `EpisodeScript`, `VideoProductionRun`, `series_characters`, and `series_scenes`. Do not move class bodies until the plan accounts for `Character.series_list`, `Scene.series_list`, Alembic imports, subprocess import order, and existing test fixtures.

**Tech Stack:** SQLAlchemy ORM, Alembic, Pytest, existing `app.db_models` compatibility facade.

---

## First Tasks

- [ ] Draw the ORM dependency graph for `Series`, `Character`, `Scene`, association tables, and production models.
- [ ] Decide whether `Character` and `Scene` move with `Series` or stay cross-domain with explicit late-bound relationships.
- [ ] Add subprocess import tests for `app.db_models`, `app.db.models.ai_video_series`, and Alembic metadata loading in both import orders.
- [ ] Move ORM class bodies only in dependency-safe batches after failing tests exist.
- [ ] Keep `app.db_models` re-exports until all legacy imports are retired by cleanup gates.
- [ ] Run model, migration-head, series API, and production start-flow tests after each batch.
