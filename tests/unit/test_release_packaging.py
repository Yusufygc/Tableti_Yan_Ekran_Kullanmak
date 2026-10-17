"""Yayın paketleme bekçileri: kararlı exe sabitleri, özet kapısı, tek sürüm kaynağı, Inno betiği, iş akışı, release.py."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
import sys

import pytest

import build_exe
import build_installer
from src import version
from src.core import app_paths

ROOT = Path(__file__).resolve().parents[2]

# Bu iki dosyanın içeriği exe özetine girer: DEĞİŞTİRME. Bilerek değişiyorsa docs/wiki/exe-dagitim-rehberi.md bölüm 8.
LAUNCHER_SHA256 = "4268e3a2cb4b5c9e325152905899f1030cc6fce8cba4e2ace84c8f80764b783b"
VERSION_INFO_SHA256 = "efbfc40dd3354173a7300d7156157b8f03c6e70e7547008e1ee991643c15a5b9"


def _lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_release_tool():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("release_tool", ROOT / "tools" / "release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- kararlı exe


def test_launcher_and_version_resource_are_pinned() -> None:
    assert _lf_sha256(ROOT / "packaging" / "launcher.py") == LAUNCHER_SHA256, (
        "packaging/launcher.py DEĞİŞMEMELİ (exe özetine girer). Bilerek değiştirdiysen rehber bölüm 8'i uygula "
        "ve bu sabit özeti güncelle."
    )
    assert _lf_sha256(ROOT / "packaging" / "launcher_version_info.txt") == VERSION_INFO_SHA256
    launcher = (ROOT / "packaging" / "launcher.py").read_text(encoding="utf-8")
    assert "from src.app import run" in launcher and launcher.rstrip().endswith("run()")


def test_version_resource_is_constant_and_not_the_product_version() -> None:
    text = (ROOT / "packaging" / "launcher_version_info.txt").read_text(encoding="utf-8")
    assert "filevers=(1, 0, 0, 0)" in text and "1.0.0.0" in text
    assert version.__version__ not in text or version.__version__ == "1.0.0"
    # Sürümle değişen başka exe kaynağı kökte olmamalı
    assert not (ROOT / "version_info.txt").exists()


def test_pyinstaller_arguments_keep_exe_stable() -> None:
    args = build_exe.pyinstaller_arguments(ROOT)
    for required in ("--onedir", "--windowed", "--noupx", "--debug=noarchive", "--noconfirm", "--clean"):
        assert required in args
    assert str(ROOT / "packaging" / "launcher.py") == args[0]
    assert any(a.startswith("--version-file=") and a.endswith("launcher_version_info.txt") for a in args)
    assert any(a.startswith("--icon=") and a.endswith("app.ico") for a in args)
    assert build_exe.LAUNCHER_EPOCH == 1700000000
    source = (ROOT / "build_exe.py").read_text(encoding="utf-8")
    assert 'os.environ["SOURCE_DATE_EPOCH"] = str(LAUNCHER_EPOCH)' in source
    # Çalışma zamanının ihtiyaç duyduğu veri dosyaları pakete girmeli
    data = " ".join(a for a in args if a.startswith("--add-data="))
    for needed in ("client_assets", "qml", "third_party", "3_ekran_kur.bat", "app.ico"):
        assert needed in data


def test_launcher_hash_gate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exe = tmp_path / "TabScreenUSB.exe"
    exe.write_bytes(b"ornek-exe")
    hash_file = tmp_path / "launcher.sha256"

    with pytest.raises(SystemExit):  # onay dosyası yok -> durur
        build_exe.check_launcher_hash(exe, hash_file=hash_file)

    build_exe.check_launcher_hash(exe, update=True, hash_file=hash_file)  # bilerek onayla
    build_exe.check_launcher_hash(exe, hash_file=hash_file)  # aynı özet -> geçer
    assert "onaylananla aynı" in capsys.readouterr().out

    exe.write_bytes(b"degisti")
    with pytest.raises(SystemExit):  # farklı özet -> durur
        build_exe.check_launcher_hash(exe, hash_file=hash_file)
    assert "DEĞİŞTİ" in capsys.readouterr().err


def test_approved_hash_file_is_committed_and_well_formed() -> None:
    line = (ROOT / "packaging" / "launcher.sha256").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{64} \*TabScreenUSB\.exe", line)


def test_release_workflow_cannot_skip_the_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "python build_installer.py" in workflow
    assert "--no-verify" not in workflow and "--update-launcher-hash" not in workflow
    assert 'tags:' in workflow and '"v*"' in workflow
    assert "--check-tag" in workflow and "--verify-tag" in workflow
    assert "env:" in workflow and "TAG: ${{ github.ref_name }}" in workflow  # enjeksiyon önlemi
    assert "${{ github.ref_name }}" not in workflow.replace("TAG: ${{ github.ref_name }}", "")
    assert 'python-version: "3.10"' in workflow
    assert "contents: write" in workflow


# ---------------------------------------------------------------- sürüm ve Inno


def test_single_version_source_and_release_repo() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
    assert version.APP_NAME == "TabScreenUSB"
    assert version.RELEASE_REPO == "Yusufygc/Tableti_Yan_Ekran_Kullanmak"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"badge/s%C3%BCr%C3%BCm-{version.__version__}-" in readme  # README rozeti src/version.py ile aynı
    assert build_installer.installer_path().name == f"{version.APP_NAME}-Setup-{version.__version__}.exe"


def test_inno_script_has_required_settings() -> None:
    iss = (ROOT / "packaging" / "TabScreenUSB.iss").read_text(encoding="utf-8")
    assert re.search(r"^AppId=\{\{[0-9A-F-]{36}\}$", iss, re.MULTILINE)  # sabit AppId
    for line in (
        "PrivilegesRequired=lowest",
        "CloseApplications=yes",
        "RestartApplications=no",
        "OutputBaseFilename=TabScreenUSB-Setup-{#AppVersion}",
        "SetupIconFile=icons\\app.ico",
        "Check: RelaunchAfterUpdate",
    ):
        assert line in iss
    assert "WizardSilent and not HasParam('/VERYSILENT')" in iss
    assert "WizardVerySilent" not in iss.replace("WizardVerySilent diye", "")  # böyle bir Inno işlevi yok


# ---------------------------------------------------------------- release.py


def test_release_tool_check_tag_and_version_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _load_release_tool()
    version_file = tmp_path / "version.py"
    version_file.write_text('__version__ = "1.2.3"\nAPP_NAME = "X"\n', encoding="utf-8")

    assert tool.check_tag("v1.2.3", version_file) == 0
    assert tool.check_tag("v1.2.4", version_file) == 1
    assert tool.check_tag("1.2.3", version_file) == 1  # 'v' öneki zorunlu
    assert tool.parse_new_version("2.0.0") == (2, 0, 0)
    with pytest.raises(SystemExit):
        tool.parse_new_version("2.0.0-rc1")

    readme = tmp_path / "README.md"
    readme.write_text("![Sürüm](https://img.shields.io/badge/s%C3%BCr%C3%BCm-1.2.3-38BDF8)\n", encoding="utf-8")
    monkeypatch.setattr(tool, "VERSION_FILE", version_file)
    monkeypatch.setattr(tool, "README", readme)
    tool.write_version((2, 0, 0))
    assert '__version__ = "2.0.0"' in version_file.read_text(encoding="utf-8")
    assert "s%C3%BCr%C3%BCm-2.0.0-" in readme.read_text(encoding="utf-8")
    assert tool.current_version(version_file) == (2, 0, 0)


def test_release_tool_never_pushes() -> None:
    source = (ROOT / "tools" / "release.py").read_text(encoding="utf-8")
    assert 'git("push"' not in source and "git push" not in source.replace("git push origin", "")
    assert "--follow-tags" not in source.replace("--follow-tags KULLANMA", "")


# ---------------------------------------------------------------- paketlenmiş çalışma ortamı


def test_app_paths_for_source_and_frozen_runtimes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert app_paths.resource_root() == ROOT
    assert (app_paths.resource_root() / "third_party" / "platform-tools" / "adb.exe").is_file()
    assert (app_paths.resource_root() / "3_ekran_kur.bat").is_file()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert app_paths.is_frozen() is True
    assert app_paths.resource_root() == tmp_path
    assert app_paths.icon_path() == tmp_path / "packaging" / "icons" / "app.ico"

    monkeypatch.setenv(app_paths.USER_DATA_ENV, str(tmp_path / "veri"))
    assert app_paths.user_data_dir() == tmp_path / "veri"
    monkeypatch.delenv(app_paths.USER_DATA_ENV)
    assert app_paths.user_data_dir() == Path.home() / ".tabscreen_usb"


def test_third_party_binaries_are_tracked_with_licenses() -> None:
    base = ROOT / "third_party"
    for rel in (
        "platform-tools/adb.exe", "platform-tools/AdbWinApi.dll", "platform-tools/AdbWinUsbApi.dll",
        "platform-tools/NOTICE.txt", "vdd/VirtualDisplayDriver/MttVDD.dll", "vdd/VirtualDisplayDriver/MttVDD.inf",
        "vdd/VirtualDisplayDriver/mttvdd.cat", "vdd/VirtualDisplayDriver/vdd_settings.xml",
        "vdd/nefcon/x64/nefconc.exe", "vdd/LICENSE-VirtualDisplayDriver.txt", "vdd/LICENSE-nefcon.txt", "README.md",
    ):
        assert (base / rel).is_file(), rel
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Platform-Tools" in notices and "nefcon" in notices and "Virtual Display Driver" in notices
    # .bat dosyaları paketlenen yolu kullanmalı (eski tools/ yolu CI'da yok)
    for bat in ("3_ekran_kur.bat", "3_ekran_kaldir.bat"):
        assert b"third_party" in (ROOT / bat).read_bytes() and b"tools\\vdd" not in (ROOT / bat).read_bytes()


def test_gitignore_keeps_release_tool_and_third_party_tracked() -> None:
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tools/" not in lines  # tools/release.py takip edilir
    assert "third_party/" not in lines and "dist/" in lines and "build/" in lines


def test_installer_discovery_and_checksum_file(tmp_path: Path) -> None:
    installer = tmp_path / "TabScreenUSB-Setup-0.0.1.exe"
    installer.write_bytes(b"x" * 100)
    checksum = build_installer.write_checksum(installer)
    assert checksum.name == installer.name + ".sha256"
    assert checksum.read_text(encoding="utf-8") == f"{hashlib.sha256(b'x' * 100).hexdigest()} *{installer.name}\n"
