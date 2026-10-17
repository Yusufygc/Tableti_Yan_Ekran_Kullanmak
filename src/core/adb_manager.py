"""USB üzerinden Android ADB cihaz tespiti ve localhost (adb reverse) tünel yönetimi."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from src.core import app_paths

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdbDevice:
    """ADB üzerinden algılanan Android cihaz bilgisi."""

    serial: str
    state: str  # "device", "unauthorized", "offline"

    @property
    def is_ready(self) -> bool:
        return self.state == "device"


@dataclass(frozen=True)
class AdbTunnelStatus:
    """ADB USB tünel kurulum sonucu."""

    success: bool
    adb_path: str | None
    device_serial: str | None
    port: int
    message: str


def find_safe_adb_executable() -> str | None:
    """
    Geçerli çalışma klasörünü (CWD) dışlayarak sistem PATH'inden veya standart
    Android SDK konumlarından güvenli adb.exe yolunu bulur.
    """
    raw_path = os.environ.get("PATH", "")
    cwd_resolved = Path.cwd().resolve()

    safe_paths: list[str] = []
    for entry in raw_path.split(os.pathsep):
        cleaned = entry.strip()
        if not cleaned:
            continue
        try:
            if Path(cleaned).resolve() == cwd_resolved:
                continue
        except OSError as exc:
            logger.debug("PATH girdisi çözümlenemedi (%s): %s", cleaned, exc)
            continue
        safe_paths.append(cleaned)

    # Pakete dahil adb önce aranır: sistemdeki farklı sürüm adb sunucusu, çalışan sunucuyu sonlandırabilir.
    bundled_adb = app_paths.resource_root() / "third_party" / "platform-tools" / "adb.exe"
    if bundled_adb.is_file():
        return str(bundled_adb.resolve())

    found = shutil.which("adb", path=os.pathsep.join(safe_paths))
    if found:
        return str(Path(found).resolve())

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path(r"C:\Android\platform-tools\adb.exe"),
        Path(r"C:\platform-tools\adb.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    return None


def parse_adb_devices_output(stdout: str) -> list[AdbDevice]:
    """'adb devices' çıktısını ayrıştırıp cihaz listesini döndürür."""
    devices: list[AdbDevice] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append(AdbDevice(serial=parts[0], state=parts[1]))
    return devices


class AdbManager:
    """USB ADB cihaz sorgulama ve 'adb reverse tcp:PORT tcp:PORT' tünel yöneticisi."""

    def __init__(
        self,
        adb_executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._adb_executable = adb_executable or find_safe_adb_executable()
        self._runner = runner
        self._no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    @property
    def adb_path(self) -> str | None:
        return self._adb_executable

    def list_devices(self) -> list[AdbDevice]:
        """Bağlı Android cihazları listeler."""
        if not self._adb_executable:
            return []
        try:
            proc = self._runner(
                [self._adb_executable, "devices"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
                creationflags=self._no_window_flag,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("adb devices komutu çalıştırılamadı: %s", exc)
            return []

        if proc.returncode != 0:
            logger.warning("adb devices hata kodu döndürdü (%s): %s", proc.returncode, proc.stderr)
            return []
        return parse_adb_devices_output(proc.stdout)

    def setup_reverse_tunnel(self, port: int = 8765, serial: str | None = None) -> AdbTunnelStatus:
        """
        USB üzerinden 'adb reverse tcp:<port> tcp:<port>' tünelini kurar.
        Böylece tablette http://127.0.0.1:<port> açıldığında doğrudan Windows localhost'a bağlanır.
        """
        if not self._adb_executable:
            return AdbTunnelStatus(
                success=False,
                adb_path=None,
                device_serial=None,
                port=port,
                message="Sistemde 'adb.exe' bulunamadı. Android Platform Tools kurulmalı veya PATH'e eklenmeli.",
            )

        devices = self.list_devices()
        if not devices:
            return AdbTunnelStatus(
                success=False,
                adb_path=self._adb_executable,
                device_serial=None,
                port=port,
                message="USB ile bağlı Android tablet algılanamadı. Tablette 'USB Hata Ayıklama' (USB Debugging) açık olmalı.",
            )

        target: AdbDevice | None = None
        if serial:
            target = next((d for d in devices if d.serial == serial), None)
        else:
            target = next((d for d in devices if d.is_ready), devices[0])

        if target is None:
            return AdbTunnelStatus(
                success=False,
                adb_path=self._adb_executable,
                device_serial=None,
                port=port,
                message=f"Belirtilen cihaz ({serial}) bağlı değil.",
            )

        if not target.is_ready:
            return AdbTunnelStatus(
                success=False,
                adb_path=self._adb_executable,
                device_serial=target.serial,
                port=port,
                message=(
                    f"Cihaz ({target.serial}) durumu '{target.state}'. "
                    "Lütfen tablet ekranındaki 'USB Hata Ayıklamaya İzin Ver' onayını kabul edin."
                ),
            )

        spec = f"tcp:{int(port)}"
        cmd = [self._adb_executable, "-s", target.serial, "reverse", spec, spec]
        try:
            proc = self._runner(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
                creationflags=self._no_window_flag,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("adb reverse komutu başarısız: %s", exc)
            return AdbTunnelStatus(
                success=False,
                adb_path=self._adb_executable,
                device_serial=target.serial,
                port=port,
                message=f"ADB tünel komutu çalıştırılamadı: {exc}",
            )

        if proc.returncode != 0:
            err_text = (proc.stderr or proc.stdout or "").strip()
            return AdbTunnelStatus(
                success=False,
                adb_path=self._adb_executable,
                device_serial=target.serial,
                port=port,
                message=f"ADB reverse tüneli kurulamadı: {err_text}",
            )

        return AdbTunnelStatus(
            success=True,
            adb_path=self._adb_executable,
            device_serial=target.serial,
            port=port,
            message=f"USB tüneli hazır ({target.serial} -> 127.0.0.1:{port})",
        )

    def remove_reverse_tunnel(self, port: int = 8765, serial: str | None = None) -> bool:
        """Kurulan USB port yönlendirmesini temizler."""
        if not self._adb_executable:
            return False
        cmd = [self._adb_executable]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(["reverse", "--remove", f"tcp:{int(port)}"])
        try:
            proc = self._runner(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
                creationflags=self._no_window_flag,
            )
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("ADB reverse tüneli kaldırılamadı: %s", exc)
            return False

    def open_url_on_device(self, url: str = "http://127.0.0.1:8765", serial: str | None = None) -> bool:
        """Tabletteki varsayılan tarayıcıda yerel yayın adresini otomatik olarak açar."""
        if not self._adb_executable:
            return False
        devices = [d for d in self.list_devices() if d.is_ready]
        if not devices:
            return False
        target_serial = serial or devices[0].serial
        cmd = [
            self._adb_executable,
            "-s",
            target_serial,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            url,
        ]
        try:
            proc = self._runner(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6,
                check=False,
                creationflags=self._no_window_flag,
            )
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Tablette URL açılamadı: %s", exc)
            return False

