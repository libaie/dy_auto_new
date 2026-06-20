# Device Config Domain Imports Design

Date: 2026-06-20

## Goal

Remove device-operation imports of legacy prompt, selector, and template
service facades.

## Design

Update only clean device operation modules:

- `app.domains.device_operations.polling` imports `prompt_template_service`
  from `app.domains.prompt_management.prompt_template_service`.
- `app.domains.device_operations.polling` imports `selector_service` from
  `app.domains.selector_management.selector_service`.
- `app.domains.device_operations.script_assets` imports prompt, selector, and
  template helpers from `app.domains.prompt_management.prompt_template_service`,
  `app.domains.selector_management.selector_service`, and
  `app.domains.selector_management.template_service`.

Keep `app.services.prompt_template_service`, `app.services.selector_service`,
and `app.services.template_service` as compatibility facades for tests and
service modules whose owning domains have not moved.

## Verification

Add one boundary test proving the device modules use direct domain imports and
the three legacy facades still resolve to their domain module objects.
