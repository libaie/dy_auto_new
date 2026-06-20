# TODOs

## Server Business Modularization Deferred Scope

Source: `/autoplan` review of `docs/superpowers/specs/2026-06-17-server-business-modularization-design.md` on 2026-06-18.

- Frontend UI implementation. Consume stable backend read models in a later PR.
- Schema-changing database migrations. Add only after a separate query/index review proves need.
- Broad platform-wide rate limiting. Backend duplicate job/run/idempotency protection is in scope; global rate limiting is not.

## Required Follow-up Plans After ai_video_series

The server-side business domains now live under `server/app/domains`, ORM models live under `server/app/db/models`, and the old compatibility facades have been removed. Remaining items are outside the backend modularization cleanup.

- Frontend consumption plan: update UI only after backend read models are stable and covered by API contract tests.
- Platform rate limiting plan: design broad cross-domain throttling only after product requirements and deployment limits are clear.
