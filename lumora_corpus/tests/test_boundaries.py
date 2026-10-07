"""copilot only reads the generated files; it never imports the client's world."""

import ast
from pathlib import Path

COPILOT_SRC = Path(__file__).parents[2] / "copilot" / "src"
FORBIDDEN = ("mock_api", "lumora_corpus")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_copilot_does_not_import_the_client_packages() -> None:
    files = sorted(COPILOT_SRC.rglob("*.py"))
    assert files, "copilot sources not found"
    for path in files:
        for module in _imported_modules(path):
            assert module.split(".")[0] not in FORBIDDEN, f"{path} imports {module}"


def test_the_check_catches_a_forbidden_import(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("from mock_api.seed import dataset\nimport lumora_corpus.policies\n")
    assert {m.split(".")[0] for m in _imported_modules(bad)} == set(FORBIDDEN)
