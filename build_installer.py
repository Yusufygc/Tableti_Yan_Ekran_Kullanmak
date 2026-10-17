"""
Tek komutla yayın dosyaları: exe (kapıdan geçer) -> exe denemesi -> Inno kurulum dosyası -> .sha256 -> kurulum denemesi.

Kullanım:
  python build_installer.py                       # tam akış
  python build_installer.py --skip-build          # mevcut dist/ ile yalnızca Inno + özet
  python build_installer.py --no-verify           # bu makinede deneme yapma
  python build_installer.py --update-launcher-hash  # exe'yi BİLEREK değiştirdiysen yeni özeti onayla

`CI` ortam değişkeni varsa deneme atlanır (CI'da Akıllı Uygulama Denetimi yoktur).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

import build_exe
import build_verify
from src.version import APP_NAME, __version__

ROOT = Path(__file__).resolve().parent
ISS_FILE = ROOT / "packaging" / "TabScreenUSB.iss"
INSTALLER_DIR = ROOT / "dist" / "installer"
DISPLAY_NAME = "TabScreen USB"  # Başlat menüsü klasörü (Inno [Setup] DefaultGroupName ile aynı)


def find_iscc() -> str | None:
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return found
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def installer_path(version: str = __version__) -> Path:
    return INSTALLER_DIR / f"{APP_NAME}-Setup-{version}.exe"


def write_checksum(installer: Path) -> Path:
    checksum = build_exe.sha256_of(installer)
    target = installer.with_name(installer.name + ".sha256")
    target.write_text(f"{checksum} *{installer.name}\n", encoding="utf-8", newline="\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TabScreenUSB kurulum dosyasını üretir")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--update-launcher-hash", action="store_true")
    args = parser.parse_args(argv)

    verify = not args.no_verify and not os.environ.get("CI")
    iscc = find_iscc()
    if iscc is None:
        print("HATA: Inno Setup 6 (ISCC.exe) bulunamadı. Kur: choco install innosetup -y", file=sys.stderr)
        return 1

    if args.skip_build:
        exe = build_exe.executable_path()
        if not exe.is_file():
            print(f"HATA: {exe} yok; --skip-build için önce derle.", file=sys.stderr)
            return 1
    else:
        exe = build_exe.build_executable(update_hash=args.update_launcher_hash)

    if verify:
        result = build_verify.launch_check(exe)
        print(f"[deneme] exe: {'BAŞARILI' if result.ok else 'BAŞARISIZ'} - {result.detail}")
        if not result.ok:
            print(
                "HATA: Derlenen exe bu makinede açılmadı. Yeniden derlemek aynı exe'yi verir (döngü yok); "
                "docs/wiki/exe-dagitim-rehberi.md bölüm 8'e bak (LAUNCHER_EPOCH yolu).",
                file=sys.stderr,
            )
            return 1

    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    # `//D` yalnızca git-bash içindir; subprocess'e doğrudan verildiği için `/D` doğrudur
    subprocess.run([iscc, f"/DAppVersion={__version__}", str(ISS_FILE)], check=True)
    installer = installer_path()
    if not installer.is_file():
        print(f"HATA: kurulum dosyası oluşmadı: {installer}", file=sys.stderr)
        return 1
    checksum_file = write_checksum(installer)
    print(f"[yayın] {installer.name} ({installer.stat().st_size / 1_048_576:.1f} MB), özet: {checksum_file.name}")

    if verify:
        result = build_verify.installer_check(installer, ISS_FILE, DISPLAY_NAME, f"{build_exe.APP_EXE_NAME}.exe")
        label = "BAŞARILI" if result.ok else "UYARI"
        print(f"[deneme] kurulum dosyası: {label} - {result.detail}")
        if not result.ok:
            print(
                "UYARI: Kurulum dosyası bu makinede denenemedi; her sürümde yeni olan tek çalıştırılabilir dosya budur. "
                "Uygulama içi güncelleme engelde bekler/yeniden dener. Release'e yüklemeden önce elle aç.",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
