"""LLM Wiki bütünlük, bağlantı, indeks ve CLAUDE.md bekçi testleri."""

from __future__ import annotations

from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIKI_DIR = PROJECT_ROOT / "docs" / "wiki"
WIKI_LINK_RE = re.compile(r"\[\[([a-zA-Z0-9_-]+)\]\]")


def test_claude_md_points_to_wiki_entrypoints() -> None:
    claude_md = PROJECT_ROOT / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md mevcut olmalı"
    text = claude_md.read_text(encoding="utf-8")
    for required in ("docs/wiki/index.md", "docs/wiki/rules.md", "docs/wiki/decisions.md", "docs/wiki/log.md"):
        assert required in text, f"CLAUDE.md içinde '{required}' referansı eksik"


def test_wiki_links_and_no_orphan_pages() -> None:
    assert WIKI_DIR.exists(), "docs/wiki klasörü mevcut olmalı"
    pages = {p.stem: p for p in WIKI_DIR.glob("*.md")}
    assert "index" in pages, "docs/wiki/index.md mevcut olmalı"

    inbound_links: dict[str, set[str]] = {name: set() for name in pages}
    broken_links: list[str] = []

    for name, path in pages.items():
        content = path.read_text(encoding="utf-8")
        targets = WIKI_LINK_RE.findall(content)
        assert targets, f"'{name}.md' sayfası en az bir [[sayfa]] bağlantısı içermeli"
        for target in targets:
            if target not in pages:
                broken_links.append(f"{name}.md -> [[{target}]]")
            elif target != name:
                inbound_links[target].add(name)

    assert not broken_links, f"Kırık wiki bağlantıları bulundu: {broken_links}"

    index_content = pages["index"].read_text(encoding="utf-8")
    index_targets = set(WIKI_LINK_RE.findall(index_content))
    for page_name in pages:
        if page_name == "index":
            continue
        assert page_name in index_targets, f"'{page_name}.md' index.md içinde listelenmemiş"
        assert inbound_links[page_name], f"'{page_name}.md' öksüz (hiçbir sayfadan bağlantı almıyor)"


def test_wiki_log_has_valid_entry_header() -> None:
    log_path = WIKI_DIR / "log.md"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert re.search(r"^## \[\d{4}-\d{2}-\d{2}\] (INGEST|QUERY|LINT|UPDATE) \| .+", content, re.MULTILINE)
