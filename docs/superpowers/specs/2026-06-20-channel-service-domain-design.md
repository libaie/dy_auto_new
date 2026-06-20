# Channel Service Domain Design

Date: 2026-06-20

## Goal

Move channel creation, item claiming, completion, stale recovery, quota/risk
control, and channel stats from `app.services.channel_service` into
`app.domains.account_operations.channel_service` without changing channel API,
task service, device reporting, or task operations behavior.

## Approved Approach

Move `server/app/services/channel_service.py` to
`server/app/domains/account_operations/channel_service.py`.

Keep `app.services.channel_service` as a `sys.modules` compatibility facade.
`account_operations.adapters` imports the domain service directly. `task_service`,
`task_operations`, and `device_operations.reporting` keep the legacy import path
until those domains get their own cleanup slices.

## Boundaries

- Preserve `ChannelService`, `channel_service`, `MAX_KEYWORDS`,
  `_busy_account_ids`, `_unique_nonempty`, `_inject_nurture_keyword_matrix`,
  `_resolve_nurture_subtask_templates`, and `_get_active_accounts`.
- Preserve channel creation, item queueing, item claim, stale recovery,
  cooldown, quota, risk-control, cancel/pause/resume, soft delete, batch edit,
  and stats behavior.
- Preserve lazy `content_service` usage for nurture comment template injection.
- Do not move `task_service`, task operations, device reporting, content
  service, route behavior, ORM models, or websocket ownership in this slice.

## Verification

- Add a boundary test proving spec/plan coverage, domain file existence,
  facade thinness, module identity, parent package import identity, direct
  account operations adapter import, and documented cleanup gates.
- Run channel service, channel API, task API, task operations, and device
  reporting compatibility tests after migration.
