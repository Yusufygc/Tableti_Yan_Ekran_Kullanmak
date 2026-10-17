"""Kaynak dosya hijyeni: UTF-8 BOM yokluğu ve sessiz hata yutma yasağı bekçi testleri."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UTF8_BOM = b"\xef\xbb\xbf"


def _iter_tracked_text_files() -> list[Path]:
    extensions = {".py", ".qml", ".md", ".toml", ".ini", ".yml", ".yaml", ".json", ".html", ".css", ".js"}
    ignored_dirs = {"venv", ".venv", ".git", ".pytest_cache", ".ruff_cache", "__pycache__", "build", "dist"}
    result: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.suffix.lower() in extensions:
            result.append(path)
    return result


def test_source_files_have_no_utf8_bom() -> None:
    bom_files = [
        str(p.relative_to(PROJECT_ROOT))
        for p in _iter_tracked_text_files()
        if p.read_bytes().startswith(UTF8_BOM)
    ]
    assert not bom_files, f"UTF-8 BOM içeren dosyalar bulundu: {bom_files}"


def _handler_Only_swallows(handler: ast.ExceptHandler) -> bool:
    """Except bloğunun yalnızca pass / ... içerip sessizce hata yutup yutmadığını kontrol eder."""
    meaningful = [
        stmt
        for stmt in handler.body
        if not isinstance(stmt, ast.Pass)
        and not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
    ]
    return len(meaningful) == 0


def test_no_bare_except_and_no_silent_broad_except() -> None:
    violations: list[str] = []
    for folder in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
        for py_file in folder.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            rel = py_file.relative_to(PROJECT_ROOT)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                if node.type is None:
                    violations.append(f"{rel}:{node.lineno} çıplak 'except:' yasak")
                elif _handler_Only_swallows(node):
                    violations.append(f"{rel}:{node.lineno} sessiz hata yutan except bloğu yasak")
    assert not violations, f"Hata yönetimi ihlalleri: {violations}"


def test_bat_files_use_crlf_and_pure_ascii() -> None:
    """
    Windows cmd.exe içinde chcp 65001 + LF + çok baytlı UTF-8 karakterler kullanıldığında
    byte-offset kayması (komutların ortadan bölünmesi: 'echo' -> 'ho') yaşanır.
    Bu bekçi test tüm .bat dosyalarının saf ASCII ve CRLF olmasını zorunlu kılar.
    """
    violations: list[str] = []
    for bat_file in PROJECT_ROOT.glob("*.bat"):
        raw = bat_file.read_bytes()
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            violations.append(f"{bat_file.name}: ASCII dışı karakter içeriyor (cmd.exe byte kaymasına yol açar)")
        if b"\r\n" not in raw or b"\n" in raw.replace(b"\r\n", b""):
            violations.append(f"{bat_file.name}: Satır sonları CRLF (\\r\\n) olmalı")
    assert not violations, f".bat dosya hijyeni ihlalleri: {violations}"

