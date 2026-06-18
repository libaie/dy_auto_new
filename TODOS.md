# TODOs

## Server Business Modularization Deferred Scope

Source: `/autoplan` review of `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md` on 2026-06-18.

- Device/content/account modularization. Keep out of the first `ai_video_series` vertical slice.
- Full `video_production_service.py` rewrite. Move only series-specific glue through legacy adapters first.
- Frontend UI implementation. Consume stable backend read models in a later PR.
- Schema-changing database migrations. Add only after a separate query/index review proves need.
- Compatibility facade removal. Retire facades only in dedicated cleanup PRs after callers/tests move.
- AI video series ORM graph extraction. Required child plan: `docs/superpowers/plans/2026-06-18-ai-video-series-orm-graph-extraction.md`; do not move ORM class bodies until the relationship/import graph is tested.
- Broad platform-wide rate limiting. Backend duplicate job/run/idempotency protection is in scope; global rate limiting is not.
