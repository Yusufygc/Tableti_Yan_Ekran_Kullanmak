"""AST tabanlı katman yönü (layering) bekçi testi."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"


def _imported_modules(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_core_does_not_import_services_or_ui() -> None:
    violations: list[str] = []
    for py_file in (SRC_DIR / "core").rglob("*.py"):
        for mod in _imported_modules(py_file):
            if mod.startswith(("src.services", "src.ui", "services", "ui")):
                violations.append(f"{py_file.relative_to(PROJECT_ROOT)} -> {mod}")
    assert not violations, f"Core katmanı üst katmanları import edemez: {violations}"


def test_services_do_not_import_ui() -> None:
    violations: list[str] = []
    for py_file in (SRC_DIR / "services").rglob("*.py"):
        for mod in _imported_modules(py_file):
            if mod.startswith(("src.ui", "ui")):
                violations.append(f"{py_file.relative_to(PROJECT_ROOT)} -> {mod}")
    assert not violations, f"Services katmanı UI katmanını import edemez: {violations}"


def test_ui_does_not_import_core_directly() -> None:
    violations: list[str] = []
    for py_file in (SRC_DIR / "ui").rglob("*.py"):
        for mod in _imported_modules(py_file):
            if mod.startswith(("src.core", "core")):
                violations.append(f"{py_file.relative_to(PROJECT_ROOT)} -> {mod}")
    assert not violations, f"UI katmanı Core katmanını doğrudan import edemez (ProjectService kullanmalı): {violations}"

