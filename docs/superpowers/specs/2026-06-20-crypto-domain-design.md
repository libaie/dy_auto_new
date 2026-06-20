# Crypto Domain Design

## Goal

Move sensitive-setting encryption helpers from `app.services.crypto` into the
`system_configuration` domain while keeping the legacy import path working.

## Decision

Use `app.domains.system_configuration.crypto` as the canonical module. These
helpers encrypt provider and system configuration secrets; they are not auth
token or login behavior, so `identity_access` is the wrong owner.

## Scope

In scope:

- Create `server/app/domains/system_configuration/crypto.py` with the existing
  implementation.
- Replace `server/app/services/crypto.py` with a compatibility facade.
- Update domain-owned imports to use `app.domains.system_configuration.crypto`.
- Register the facade in the system-configuration README.
- Add tests for facade identity and domain import boundaries.

Out of scope:

- No key-derivation changes.
- No encrypted value migration.
- No changes to `SENSITIVE_KEYS`, `encrypt`, `decrypt`, or masking behavior.
- No cleanup of legacy imports in tests or service compatibility callers.

## Verification

The boundary test must prove:

- `app.domains.system_configuration.crypto` owns `encrypt`, `decrypt`,
  `is_sensitive_key`, and `SENSITIVE_KEYS`.
- `app.services.crypto` aliases the domain module.
- Domain modules no longer import `app.services.crypto`.
- Existing crypto behavior still round-trips a value.
