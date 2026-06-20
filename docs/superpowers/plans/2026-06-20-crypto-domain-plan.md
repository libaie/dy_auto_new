# Crypto Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move sensitive-setting crypto helpers into `app.domains.system_configuration` with a legacy facade.

**Architecture:** Copy the current implementation into `server/app/domains/system_configuration/crypto.py`, shrink `server/app/services/crypto.py` to a `sys.modules` facade, then update domain imports to the canonical path.

**Tech Stack:** Python, cryptography Fernet, pytest.

---

## Files

- Create: `server/app/domains/system_configuration/crypto.py`
- Modify: `server/app/services/crypto.py`
- Modify: `server/app/domains/system_configuration/README.md`
- Modify: `server/app/domains/model_configuration/ai_models_router.py`
- Modify: `server/app/domains/model_configuration/model_registry.py`
- Modify: `server/app/domains/model_configuration/runtime_model_config.py`
- Modify: `server/app/domains/pixelle_integration/pixelle_router.py`
- Modify: `server/app/domains/quality_audit/audit_router.py`
- Create: `server/tests/test_system_configuration_crypto_facade.py`

### Task 1: Boundary Test

- [x] **Step 1: Write the failing test**

```python
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-06-20-crypto-domain-design.md"
PLAN_PATH = REPO_ROOT / "docs/superpowers/plans/2026-06-20-crypto-domain-plan.md"
DOMAIN_CRYPTO_PATH = REPO_ROOT / "server/app/domains/system_configuration/crypto.py"
LEGACY_CRYPTO_PATH = REPO_ROOT / "server/app/services/crypto.py"
README_PATH = REPO_ROOT / "server/app/domains/system_configuration/README.md"
DOMAIN_IMPORT_PATHS = [
    REPO_ROOT / "server/app/domains/model_configuration/ai_models_router.py",
    REPO_ROOT / "server/app/domains/model_configuration/model_registry.py",
    REPO_ROOT / "server/app/domains/model_configuration/runtime_model_config.py",
    REPO_ROOT / "server/app/domains/pixelle_integration/pixelle_router.py",
    REPO_ROOT / "server/app/domains/quality_audit/audit_router.py",
]


def test_crypto_spec_and_plan_document_boundary():
    spec = SPEC_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    for term in [
        "app.domains.system_configuration.crypto",
        "app.services.crypto",
        "encrypt",
        "decrypt",
        "SENSITIVE_KEYS",
    ]:
        assert term in spec
        assert term in plan


def test_crypto_implementation_lives_in_system_configuration_domain():
    domain_text = DOMAIN_CRYPTO_PATH.read_text(encoding="utf-8")
    assert "def encrypt" in domain_text
    assert "def decrypt" in domain_text
    assert "SENSITIVE_KEYS" in domain_text

    legacy_text = LEGACY_CRYPTO_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_configuration" in legacy_text
    assert "sys.modules[_LEGACY_MODULE_NAME]" in legacy_text
    assert "def encrypt" not in legacy_text
    assert "SENSITIVE_KEYS" not in legacy_text


def test_legacy_crypto_facade_resolves_to_domain_module():
    domain = importlib.import_module("app.domains.system_configuration.crypto")
    legacy = importlib.import_module("app.services.crypto")
    assert legacy is domain
    assert legacy.encrypt is domain.encrypt
    assert legacy.decrypt is domain.decrypt
    token = legacy.encrypt("secret-value")
    assert legacy.decrypt(token) == "secret-value"


def test_domain_modules_import_crypto_from_domain_path():
    for path in DOMAIN_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "app.domains.system_configuration.crypto" in text
        assert "app.services.crypto" not in text


def test_system_configuration_readme_registers_crypto_facade():
    text = README_PATH.read_text(encoding="utf-8")
    assert "app.domains.system_configuration.crypto" in text
    assert "app.services.crypto" in text
```

- [x] **Step 2: Verify RED**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_crypto_facade.py -q
```

Expected: fails because the domain crypto module is not present and domain
callers still import `app.services.crypto`.

### Task 2: Minimal Migration

- [x] **Step 1: Copy implementation**

Run:

```powershell
Copy-Item -LiteralPath 'server/app/services/crypto.py' -Destination 'server/app/domains/system_configuration/crypto.py'
```

- [x] **Step 2: Replace legacy file with facade**

```python
"""Compatibility facade for system configuration crypto helpers."""

import sys

from app.domains.system_configuration import crypto as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
```

- [x] **Step 3: Update domain imports**

Replace `from app.services.crypto import ...` with:

```python
from app.domains.system_configuration.crypto import ...
```

- [x] **Step 4: Register facade**

Add this README row:

```markdown
| `app.services.crypto` | `app.domains.system_configuration.crypto` | Sensitive-setting crypto compatibility; remove after production callers use the domain path. |
```

- [x] **Step 5: Verify GREEN**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_system_configuration_crypto_facade.py server/tests/test_ai_config.py server/tests/test_runtime_model_config.py -q
```

Expected: all tests pass.

### Task 3: Final Checks

- [x] **Step 1: Scan domain imports**

Run:

```powershell
rg -n "from app\.services\.crypto|app\.services\.crypto" server/app/domains -g "*.py"
```

Expected: no matches.

- [x] **Step 2: Import app**

Run from `server`:

```powershell
..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

Expected: exits 0.

- [x] **Step 3: Commit target files only**

Run:

```powershell
git add -f docs/superpowers/specs/2026-06-20-crypto-domain-design.md docs/superpowers/plans/2026-06-20-crypto-domain-plan.md server/tests/test_system_configuration_crypto_facade.py server/app/domains/system_configuration/crypto.py server/app/services/crypto.py server/app/domains/system_configuration/README.md server/app/domains/model_configuration/ai_models_router.py server/app/domains/model_configuration/model_registry.py server/app/domains/model_configuration/runtime_model_config.py server/app/domains/pixelle_integration/pixelle_router.py server/app/domains/quality_audit/audit_router.py
git commit --only docs/superpowers/specs/2026-06-20-crypto-domain-design.md docs/superpowers/plans/2026-06-20-crypto-domain-plan.md server/tests/test_system_configuration_crypto_facade.py server/app/domains/system_configuration/crypto.py server/app/services/crypto.py server/app/domains/system_configuration/README.md server/app/domains/model_configuration/ai_models_router.py server/app/domains/model_configuration/model_registry.py server/app/domains/model_configuration/runtime_model_config.py server/app/domains/pixelle_integration/pixelle_router.py server/app/domains/quality_audit/audit_router.py -m "refactor: move crypto helpers into system configuration"
```
