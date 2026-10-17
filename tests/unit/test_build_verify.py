"""build_verify: gerçek kurulum kaydını koruma (yaşanmış kaza), exe deneme mantığı ve simge dosyaları."""

from __future__ import annotations

from pathlib import Path
import sys
import types

from PIL import Image
import pytest

import build_verify as bv

ROOT = Path(__file__).resolve().parents[2]


def test_app_id_is_read_from_inno_script() -> None:
    app_id = bv.read_app_id(ROOT / "packaging" / "TabScreenUSB.iss")
    assert app_id == "{C2E7A1B4-6F3D-4A9B-8E15-3D0F7B92A6C4}"
    assert bv.uninstall_key_path(app_id).endswith(r"Uninstall\{C2E7A1B4-6F3D-4A9B-8E15-3D0F7B92A6C4}_is1")


class FakeWinreg(types.SimpleNamespace):
    """Yalnızca kullanılan winreg işlevlerini taklit eder (gerçek kayıt defterine dokunmaz)."""

    def __init__(self, store: dict[str, list[tuple[str, object, int]]]) -> None:
        super().__init__(HKEY_CURRENT_USER="HKCU", KEY_SET_VALUE=2)
        self.store = store

    def OpenKey(self, _root: str, path: str):  # noqa: N802
        if path not in self.store:
            raise FileNotFoundError(path)
        outer = self

        class _Key:
            def __enter__(self_inner):  # noqa: N805
                return path

            def __exit__(self_inner, *_a):  # noqa: N805
                return False

        _ = outer
        return _Key()

    def EnumValue(self, path: str, index: int):  # noqa: N802
        values = self.store[path]
        if index >= len(values):
            raise OSError("bitti")
        return values[index]

    def CreateKeyEx(self, _root: str, path: str, _r: int, _access: int):  # noqa: N802
        self.store.setdefault(path, [])

        class _Key:
            def __enter__(self_inner):  # noqa: N805
                return path

            def __exit__(self_inner, *_a):  # noqa: N805
                return False

        return _Key()

    def SetValueEx(self, path: str, name: str, _r: int, kind: int, data: object) -> None:  # noqa: N802
        values = [v for v in self.store[path] if v[0] != name]
        values.append((name, data, kind))
        self.store[path] = values

    def DeleteKey(self, _root: str, path: str) -> None:  # noqa: N802
        self.store.pop(path, None)


def test_real_registration_is_restored_after_trial_install_overwrites_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_id = "{TEST-GUID}"
    path = bv.uninstall_key_path(app_id)
    real = [("InstallLocation", r"C:\Users\u\AppData\Local\Programs\TabScreenUSB", 1), ("DisplayVersion", "1.0.0", 1)]
    store = {path: list(real)}
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg(store))

    start_menu = tmp_path / "Programs" / "TabScreen USB"
    start_menu.mkdir(parents=True)
    (start_menu / "TabScreen USB.lnk").write_bytes(b"GERCEK-KISAYOL")

    saved = bv.save_registration(app_id, start_menu)

    # Deneme kurulumu aynı kaydı geçici klasöre çevirir ve kısayolu bozar
    store[path] = [("InstallLocation", r"C:\Temp\deneme", 1), ("DisplayVersion", "9.9.9", 1)]
    (start_menu / "TabScreen USB.lnk").write_bytes(b"DENEME-KISAYOLU")

    bv.restore_registration(app_id, saved, start_menu)
    assert dict((n, d) for n, d, _ in store[path])["InstallLocation"] == real[0][1]
    assert dict((n, d) for n, d, _ in store[path])["DisplayVersion"] == "1.0.0"
    assert (start_menu / "TabScreen USB.lnk").read_bytes() == b"GERCEK-KISAYOL"


def test_trial_leftovers_are_removed_when_no_real_install_existed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_id = "{TEST-GUID}"
    path = bv.uninstall_key_path(app_id)
    store: dict[str, list[tuple[str, object, int]]] = {}
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg(store))
    start_menu = tmp_path / "TabScreen USB"

    saved = bv.save_registration(app_id, start_menu)
    assert saved.registry_values is None and not saved.shortcut_files

    store[path] = [("InstallLocation", "x", 1)]  # deneme kurulumu bıraktı
    start_menu.mkdir()
    (start_menu / "k.lnk").write_bytes(b"x")
    bv.restore_registration(app_id, saved, start_menu)
    assert path not in store and not start_menu.exists()


def _batch(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_bytes(body.replace("\n", "\r\n").encode("ascii"))
    return path


def test_launch_check_reports_running_and_early_exit(tmp_path: Path) -> None:
    long_running = _batch(tmp_path, "uzun.bat", "@echo off\nping -n 30 127.0.0.1 >nul\n")
    assert bv.launch_check(long_running, seconds=1.0).ok is True

    crashing = _batch(tmp_path, "coker.bat", "@echo off\nexit /b 3\n")
    result = bv.launch_check(crashing, seconds=2.0)
    assert result.ok is False and "çıkış kodu 3" in result.detail

    missing = bv.launch_check(tmp_path / "yok.exe", seconds=1.0)
    assert missing.ok is False


def test_launch_check_passes_isolation_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeProc:
        pid = 1

        def poll(self) -> None:
            return None

    def fake_popen(args: list[str], env: dict[str, str], cwd: str) -> FakeProc:
        captured.update(env)
        return FakeProc()

    monkeypatch.setattr(bv.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(bv.subprocess, "run", lambda *a, **k: None)
    assert bv.launch_check(tmp_path / "x.exe", seconds=0.3).ok is True
    assert captured["TABSCREEN_NO_UPDATE_CHECK"] == "1"  # denemede ağ isteği olmasın
    assert "tabscreen_verify_home_" in str(captured["TABSCREEN_USB_HOME"])  # kullanıcı verisine dokunma


# ---------------------------------------------------------------- simgeler


def test_icon_set_has_all_sizes_and_multi_frame_ico() -> None:
    icons = ROOT / "packaging" / "icons"
    for size in (16, 24, 32, 48, 64, 96, 128, 192, 256, 512):
        image = Image.open(icons / f"icon_{size}.png")
        assert image.size == (size, size) and image.mode == "RGBA", size
        assert image.getpixel((0, 0))[3] < 32  # yuvarlak köşe: köşe (neredeyse) şeffaf
        assert image.getpixel((size // 2, size // 2))[3] == 255  # iç bölgede delik yok

    ico = Image.open(icons / "app.ico")
    assert sorted(ico.ico.sizes()) == [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    assert (ROOT / "src" / "ui" / "client_assets" / "icon-192.png").is_file()
    assert (ROOT / "packaging" / "icons" / "make_icons.py").is_file()
