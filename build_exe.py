"""
PyInstaller ile TabScreenUSB.exe derler ("kararlı exe": her sürümde bayt bayt aynı çıktı).

Kararlı exe yalnızca sabit başlatıcıyı (`packaging/launcher.py`) içerir; uygulama kodu `_internal` altında `.pyc`
olarak durur (`--debug=noarchive`). `SOURCE_DATE_EPOCH` ve sabit sürüm kaynağı PE zaman damgasını/sürüm bilgisini
sabitler. Çıktının SHA-256 özeti `packaging/launcher.sha256` ile karşılaştırılır; farklıysa derleme DURUR
(bkz. docs/wiki/exe-dagitim-rehberi.md bölüm 3 ve 8).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
APP_EXE_NAME = "TabScreenUSB"
LAUNCHER_EPOCH = 1700000000  # DEĞİŞTİRME (bilerek yeni özet denemenin tek yolu)
HASH_FILE = ROOT / "packaging" / "launcher.sha256"


def executable_path() -> Path:
    return ROOT / "dist" / APP_EXE_NAME / f"{APP_EXE_NAME}.exe"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pyinstaller_arguments(root: Path = ROOT) -> list[str]:
    """Özeti belirleyen bağımsız değişkenler (testle sabitlenir)."""
    sep = os.pathsep
    return [
        str(root / "packaging" / "launcher.py"),
        f"--paths={root}",  # giriş betiği packaging/ altında: uygulama paketi (src) kökten bulunur
        f"--name={APP_EXE_NAME}",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--noupx",  # UPX DLL imzalarını bozar, antivirüs yanlış pozitifini artırır
        "--debug=noarchive",  # modüller .pyc olarak _internal altında: sürümle değişen kod exe'yi değiştirmez
        "--exclude-module=tkinter",  # arayüz PySide6/QML; eski Tkinter bağımlılığı yok
        f"--icon={root / 'packaging' / 'icons' / 'app.ico'}",
        f"--version-file={root / 'packaging' / 'launcher_version_info.txt'}",
        f"--distpath={root / 'dist'}",
        f"--workpath={root / 'build'}",
        f"--specpath={root / 'build'}",
        f"--add-data={root / 'src' / 'ui' / 'client_assets'}{sep}src/ui/client_assets",
        f"--add-data={root / 'src' / 'ui' / 'qml'}{sep}src/ui/qml",
        f"--add-data={root / 'packaging' / 'icons' / 'app.ico'}{sep}packaging/icons",
        f"--add-data={root / 'third_party'}{sep}third_party",
        f"--add-data={root / '3_ekran_kur.bat'}{sep}.",
        f"--add-data={root / '3_ekran_kaldir.bat'}{sep}.",
        f"--add-data={root / 'LICENSE'}{sep}.",
        f"--add-data={root / 'THIRD_PARTY_NOTICES.md'}{sep}.",
    ]


def check_launcher_hash(exe: Path, update: bool = False, hash_file: Path = HASH_FILE) -> None:
    """Derlenen exe özetini onaylanmışla karşılaştırır; farklıysa/dosya yoksa derlemeyi durdurur (`sys.exit(1)`)."""
    actual = sha256_of(exe)
    line = f"{actual} *{exe.name}\n"
    if update:
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(line, encoding="utf-8", newline="\n")
        print(f"[kapı] Onaylı exe özeti güncellendi: {actual}")
        return

    if not hash_file.is_file():
        print(
            "HATA: packaging/launcher.sha256 yok.\n"
            "  İlk kez derliyorsan: exe'yi bu makinede aç (build_verify.launch_check), sonra\n"
            "  `python build_installer.py --update-launcher-hash` ile özeti onayla ve commit'le.",
            file=sys.stderr,
        )
        sys.exit(1)

    approved = hash_file.read_text(encoding="utf-8").split()[0].lower()
    if approved != actual.lower():
        print(
            "HATA: Kararlı exe özeti DEĞİŞTİ; derleme ve yayın durduruldu.\n"
            f"  onaylanan: {approved}\n  derlenen : {actual}\n"
            "  Nedenleri: PyInstaller/Python sürümü, satır sonları, simge, sürüm kaynağı, giriş betiği.\n"
            "  Bilerek değiştirdiysen docs/wiki/exe-dagitim-rehberi.md bölüm 8'i uygula; bilmeden değiştiyse nedenini bul.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[kapı] Kararlı exe özeti onaylananla aynı: {actual}")


def build_executable(update_hash: bool = False) -> Path:
    """PyInstaller'ı çalıştırır, özet kapısından geçirir ve exe yolunu döndürür."""
    import PyInstaller.__main__

    os.environ["SOURCE_DATE_EPOCH"] = str(LAUNCHER_EPOCH)  # PyInstaller'ı çalıştırmadan hemen önce
    PyInstaller.__main__.run(pyinstaller_arguments())
    exe = executable_path()
    if not exe.is_file():
        print(f"HATA: exe oluşmadı: {exe}", file=sys.stderr)
        sys.exit(1)
    check_launcher_hash(exe, update=update_hash)
    return exe


if __name__ == "__main__":
    build_executable(update_hash="--update-launcher-hash" in sys.argv)
