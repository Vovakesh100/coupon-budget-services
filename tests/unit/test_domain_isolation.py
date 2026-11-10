"""The domain layer must not import I/O frameworks (CLAUDE.md rule)."""

import ast
from pathlib import Path

FORBIDDEN = {"fastapi", "redis", "sqlalchemy", "asyncpg"}
DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "coupon_budget" / "domain"


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_has_no_io_imports() -> None:
    offenders: dict[str, set[str]] = {}
    for path in DOMAIN_DIR.rglob("*.py"):
        bad = _imported_roots(path) & FORBIDDEN
        if bad:
            offenders[str(path.relative_to(DOMAIN_DIR))] = bad
    assert offenders == {}
