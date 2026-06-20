import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "server/app"

EXPECTED_DOMAIN_SERVICE_IMPORTS = set()


def test_domain_service_import_inventory_matches_allowlist():
    assert _domain_service_imports() == EXPECTED_DOMAIN_SERVICE_IMPORTS


def _domain_service_imports() -> set[tuple[str, str]]:
    imports: set[tuple[str, str]] = set()
    for path in APP_ROOT.rglob("*.py"):
        if path.relative_to(APP_ROOT).parts[:1] == ("services",):
            continue
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            imports.update(_service_imports_from_node(relative_path, node))
    return imports


def _service_imports_from_node(relative_path: str, node: ast.AST) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == "app.services":
            for alias in node.names:
                found.add((relative_path, alias.name))
        elif module.startswith("app.services."):
            found.add((relative_path, module.split(".")[2]))
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith("app.services."):
                found.add((relative_path, alias.name.split(".")[2]))
    return found
