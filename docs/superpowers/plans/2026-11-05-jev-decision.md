# Jev 决策接入实施计划

Spec: `docs/superpowers/specs/2026-11-05-jev-decision-design.md`

## Global Constraints

- Model: `typesafe-ai/jev`; exact POST URL: `https://ai-gateway.vercel.sh/typesafe/v1/systemone`.
- No credential in Git, docs, logs, responses or device config; no Chat Completions request for Jev.
- Device production code is ES5.1. Existing locator and send-confirmation protections remain intact.
- Enabled Jev failures never fall back to legacy classification; generation stays with the existing provider.
- Work on `feat/multi-resolution-locator-20261105`, append to draft PR #2; no merge or deployment.

## Tasks

- [x] 1. Server: dedicated config resolver, strict System One adapter, authenticated proxy and all pairing/register/poll handshakes; focused tests and independent review approved.
- [x] 2. Device: typed decision client and business mapping, live config application, decision-only collection and skip-reply paths, current share-link templates and relevance routing; Node tests and independent review approved.
- [x] 3. Settings: encrypted/masked key, effective configuration API, admin form and env example; backend and UI tests; recovery-path review finding fixed and re-reviewed.
- [x] 4. Integration: synthetic provider check HTTP 200, complete regression/build, independent review and fixes including initial configuration readiness and in-flight cancellation fencing.
- [ ] 5. Delivery: usage/validation guide, secret scan, commit and publish to existing draft PR with exact tree verification.

## Ownership

Server implementer owns new `server/app/services/decision_config.py`, `decision_service.py`, device proxy/handshakes in `server/app/routers/device.py` and `devices.py`, and new decision server tests. Device implementer owns device modules and tests. Controller owns settings router/UI/tests, docs, local credential configuration and Git publication. No implementer changes settings or performs Git mutations.

## Verified outcome

- Device: 170 tests passed; backend: 1,722 passed; frontend: 310 passed in 50 files; production build passed.
- ES5: 15 full device production files and the main startup/pairing/configuration prefix passed.
- Provider: one synthetic native System One request returned HTTP 200 with all three expected types; the captured response passed the final adapter validator.
- Final independent spec and quality review approved with no open Critical/Important issues. Physical Android/AutoJS6 and production deployment remain separate acceptance steps.
