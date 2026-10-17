"""
Derlenen exe ve kurulum dosyasını BU makinede dener (yalnızca standart kitaplık; başka projeye kopyalanabilir).

- `launch_check`: exe'yi başlatır, süre sonunda hâlâ çalışıyorsa kapatır. Windows engeli (WinError 4551/1260) = başarısız.
- `installer_check`: geçici klasöre SESSİZCE kurar, kurulan exe'yi açar, kaldırıcıyı da çalıştırır ve temizler.
  Deneme kurulumu gerçek kurulumla aynı AppId'yi kullanır: Inno aynı Uninstall kaydını ve Başlat menüsü kısayolunu
  yazar/siler. Bu yüzden deneme öncesi kayıt ve kısayol yedeklenir, `try/finally` ile HER durumda geri yazılır.

Not: CI'daki Windows'ta Akıllı Uygulama Denetimi (SAC) yoktur; bu denemeler yalnızca yerelde anlamlıdır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

BLOCKED_WINERRORS = (4551, 1260)
VERIFY_ENV = {"TABSCREEN_NO_UPDATE_CHECK": "1"}  # denemede ağ isteği olmasın


@dataclass
class CheckResult:
    ok: bool
    detail: str


def launch_check(exe: Path, seconds: float = 8.0) -> CheckResult:
    """exe'yi başlatır; `seconds` sonra hâlâ çalışıyorsa başarılı sayar ve süreç ağacını kapatır."""
    home = Path(tempfile.mkdtemp(prefix="tabscreen_verify_home_"))
    env = {**os.environ, **VERIFY_ENV, "TABSCREEN_USB_HOME": str(home)}  # kullanıcı ayar/günlüğüne dokunma
    try:
        try:
            proc = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent))
        except OSError as exc:
            if getattr(exc, "winerror", None) in BLOCKED_WINERRORS:
                return CheckResult(False, f"Windows engelledi (WinError {exc.winerror}): Akıllı Uygulama Denetimi")
            return CheckResult(False, f"Başlatılamadı: {exc}")
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            code = proc.poll()
            if code is not None:
                return CheckResult(False, f"Süreç {seconds:.0f} sn dolmadan çıktı (çıkış kodu {code})")
            time.sleep(0.25)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
        return CheckResult(True, f"{seconds:.0f} sn boyunca çalıştı")
    finally:
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- gerçek kurulumu koruma


def read_app_id(iss_file: Path) -> str:
    """Inno betiğindeki AppId (`{{GUID}`) değerini döndürür (kayıt anahtarı adı için)."""
    match = re.search(r"^AppId=\{\{([0-9A-Fa-f-]+)\}", iss_file.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError(f"AppId bulunamadı: {iss_file}")
    return "{" + match.group(1) + "}"


def uninstall_key_path(app_id: str) -> str:
    return rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_id}_is1"


@dataclass
class SavedRegistration:
    registry_values: list[tuple[str, object, int]] | None
    shortcut_dir: Path | None
    shortcut_files: dict[str, bytes] = field(default_factory=dict)


def save_registration(app_id: str, start_menu_dir: Path) -> SavedRegistration:
    """Gerçek kurulumun kayıt değerlerini ve Başlat menüsü kısayol baytlarını yedekler."""
    values: list[tuple[str, object, int]] | None = None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key_path(app_id)) as key:
            values = []
            index = 0
            while True:
                try:
                    values.append(winreg.EnumValue(key, index))
                except OSError:
                    break
                index += 1
    except (OSError, ImportError):
        values = None  # gerçek kurulum yok: geri yazılacak bir şey de yok

    files: dict[str, bytes] = {}
    if start_menu_dir.is_dir():
        for item in start_menu_dir.iterdir():
            if item.is_file():
                files[item.name] = item.read_bytes()
    return SavedRegistration(values, start_menu_dir if files else None, files)


def restore_registration(app_id: str, saved: SavedRegistration, start_menu_dir: Path) -> None:
    """Yedeği geri yazar; deneme kurulumunun bıraktığı kayıt/kısayol kalıntısını gerçek kayıtla değiştirir."""
    try:
        import winreg

        path = uninstall_key_path(app_id)
        if saved.registry_values is not None:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                for name, data, kind in saved.registry_values:
                    winreg.SetValueEx(key, name, 0, kind, data)
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except OSError:
                pass  # zaten yok
    except ImportError:
        pass

    if saved.shortcut_files:
        start_menu_dir.mkdir(parents=True, exist_ok=True)
        for name, data in saved.shortcut_files.items():
            (start_menu_dir / name).write_bytes(data)
    elif start_menu_dir.is_dir():
        shutil.rmtree(start_menu_dir, ignore_errors=True)  # gerçek kurulum yoktu: deneme kısayolunu temizle


def start_menu_dir_for(app_name: str) -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / app_name


def installer_check(installer: Path, iss_file: Path, app_name: str, exe_name: str) -> CheckResult:
    """Kurulum dosyasını geçici klasöre sessizce kurar, exe'yi açar, kaldırıcıyı da çalıştırır."""
    app_id = read_app_id(iss_file)
    start_menu = start_menu_dir_for(app_name)
    saved = save_registration(app_id, start_menu)
    target = Path(tempfile.mkdtemp(prefix="tabscreen_verify_install_"))
    log = target.parent / f"{target.name}.log"
    try:
        try:
            proc = subprocess.run(
                [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                 f"/DIR={target}", f"/LOG={log}"],
                capture_output=True, timeout=300, check=False,
            )
        except OSError as exc:
            if getattr(exc, "winerror", None) in BLOCKED_WINERRORS:
                return CheckResult(False, f"Kurulum dosyasını Windows engelledi (WinError {exc.winerror})")
            return CheckResult(False, f"Kurulum başlatılamadı: {exc}")
        except subprocess.TimeoutExpired:
            return CheckResult(False, "Kurulum 300 sn içinde bitmedi")
        if proc.returncode != 0:
            return CheckResult(False, f"Kurulum çıkış kodu {proc.returncode} (günlük: {log})")

        installed_exe = target / exe_name
        if not installed_exe.is_file():
            return CheckResult(False, f"Kurulan exe bulunamadı: {installed_exe}")
        launch = launch_check(installed_exe, seconds=6.0)
        if not launch.ok:
            return CheckResult(False, f"Kurulan exe açılmadı: {launch.detail}")

        uninstaller = target / "unins000.exe"
        if not uninstaller.is_file():
            return CheckResult(False, "Kaldırıcı (unins000.exe) bulunamadı")
        try:
            removal = subprocess.run(
                [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                capture_output=True, timeout=120, check=False,
            )
        except OSError as exc:
            if getattr(exc, "winerror", None) in BLOCKED_WINERRORS:
                return CheckResult(False, f"Kaldırıcıyı Windows engelledi (WinError {exc.winerror})")
            return CheckResult(False, f"Kaldırıcı başlatılamadı: {exc}")
        if removal.returncode != 0:
            return CheckResult(False, f"Kaldırıcı çıkış kodu {removal.returncode}")
        return CheckResult(True, "sessiz kurulum, exe açılışı ve kaldırıcı başarılı")
    finally:
        try:
            restore_registration(app_id, saved, start_menu)
        finally:
            shutil.rmtree(target, ignore_errors=True)
            log.unlink(missing_ok=True)
