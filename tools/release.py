"""
Sürüm yükseltir, commit atar ve etiket oluşturur; HİÇBİR ŞEY GÖNDERMEZ (push yok).

  python tools/release.py 0.2.0            # src/version.py + README rozeti -> "chore(release): v0.2.0" commit'i -> v0.2.0 etiketi
  python tools/release.py --check-tag v0.2.0   # CI: etiket ile src/version.py uyumunu denetler

Koşullar: çalışma ağacı temiz, dal `main`, yeni sürüm mevcuttan büyük, etiket yok. Etiketi itmek herkese güncelleme
penceresi çıkarır: yalnızca açık istekle `git push origin vX.Y.Z` (bkz. docs/wiki/surum-yayinlama.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "version.py"
README = ROOT / "README.md"
VERSION_RE = re.compile(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)
BADGE_RE = re.compile(r"(badge/s%C3%BCr%C3%BCm-)\d+\.\d+\.\d+(-)")
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def current_version(version_file: Path = VERSION_FILE) -> tuple[int, int, int]:
    match = VERSION_RE.search(version_file.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("HATA: src/version.py içinde __version__ = \"X.Y.Z\" bulunamadı.")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def parse_new_version(text: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text.strip())
    if not match:
        raise SystemExit(f"HATA: Sürüm 'MAJOR.MINOR.PATCH' biçiminde olmalı (ön sürüm yok): {text!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def check_tag(tag: str, version_file: Path = VERSION_FILE) -> int:
    """CI denetimi: etiket `v` + __version__ ile birebir aynı olmalı."""
    match = TAG_RE.match(tag)
    if not match:
        print(f"HATA: Etiket 'vX.Y.Z' biçiminde olmalı: {tag!r}", file=sys.stderr)
        return 1
    expected = tuple(int(part) for part in match.groups())
    actual = current_version(version_file)
    if expected != actual:
        print(
            f"HATA: Etiket {tag} ile src/version.py ({'.'.join(map(str, actual))}) farklı; yayın durduruldu.",
            file=sys.stderr,
        )
        return 1
    print(f"Etiket {tag} src/version.py ile uyumlu.")
    return 0


def write_version(version: tuple[int, int, int]) -> None:
    text = ".".join(map(str, version))
    content = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(VERSION_RE.sub(f'__version__ = "{text}"', content, count=1), encoding="utf-8", newline="\n")
    readme = README.read_text(encoding="utf-8")
    README.write_text(BADGE_RE.sub(rf"\g<1>{text}\g<2>", readme), encoding="utf-8", newline="\n")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        raise SystemExit(f"HATA: git {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sürüm yükseltir, commit atar, etiket oluşturur (itmez)")
    parser.add_argument("version", nargs="?", help="Yeni sürüm: MAJOR.MINOR.PATCH")
    parser.add_argument("--check-tag", metavar="vX.Y.Z", help="Etiket ile src/version.py uyumunu denetler (CI)")
    args = parser.parse_args(argv)

    if args.check_tag:
        return check_tag(args.check_tag)
    if not args.version:
        parser.error("Yeni sürüm gerekli (ör. 0.2.0)")

    new = parse_new_version(args.version)
    if new <= current_version():
        raise SystemExit(f"HATA: Yeni sürüm ({args.version}) mevcut sürümden büyük olmalı.")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise SystemExit("HATA: Yayın yalnızca `main` dalından yapılır.")
    if git("status", "--porcelain"):
        raise SystemExit("HATA: Çalışma ağacı temiz değil; önce commit/stash yap.")
    tag = f"v{args.version}"
    if git("tag", "--list", tag):
        raise SystemExit(f"HATA: {tag} etiketi zaten var. Yayınlanmış etiketi taşıma: yeni PATCH sürümü çıkar.")

    write_version(new)
    git("add", "src/version.py", "README.md")
    git("commit", "-m", f"chore(release): {tag}")
    git("tag", "-a", tag, "-m", f"TabScreen USB {args.version}")
    print(f"{tag} commit'i ve ek açıklamalı etiketi oluşturuldu (hiçbir şey gönderilmedi).")
    print(f"Sıradaki (açık istekle): git push origin main && git push origin {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
