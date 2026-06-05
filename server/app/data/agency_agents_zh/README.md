# Agency Agents zh Embedded Experts

This directory contains the embedded expert profiles used by dy_auto video production.

- Current production experts are listed in `manifest.json` and must match `app.services.agency_manifest.EXPERT_IDS` exactly.
- `testing/testing-reality-checker.md` is retained only for historical read-only audit detail.
- When editing an expert markdown file, update the matching sha256 in `manifest.json` and run `pytest server/tests/test_agency_manifest.py -q`.
- Do not add dynamic expert registry behavior in this directory. The current phase uses a strict manifest contract.
