import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "server/app"
ALEMBIC_ROOT = REPO_ROOT / "server/alembic"

EXPECTED_PRODUCTION_DB_MODELS_IMPORTS = set()


def test_production_db_models_import_inventory_matches_allowlist():
    assert _production_db_models_imports() == EXPECTED_PRODUCTION_DB_MODELS_IMPORTS


def _production_db_models_imports() -> set[str]:
    imports = set()
    for root in (APP_ROOT, ALEMBIC_ROOT):
        for path in root.rglob("*.py"):
            if root == APP_ROOT and path.relative_to(APP_ROOT).as_posix() == "db_models.py":
                continue
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            if any(_imports_legacy_db_models(node) for node in ast.walk(tree)):
                imports.add(relative_path)
    return imports


def _imports_legacy_db_models(node: ast.AST) -> bool:
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == "app.db_models":
            return True
        if module == "app":
            return any(alias.name == "db_models" for alias in node.names)
    if isinstance(node, ast.Import):
        return any(alias.name == "app.db_models" for alias in node.names)
    return False
