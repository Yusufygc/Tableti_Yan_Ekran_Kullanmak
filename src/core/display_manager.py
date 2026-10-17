"""Çoklu ekran (1: Ana Monitör, 2: Laptop, 3: Tablet/Sanal Ekran) tespit ve yönetim modülü."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import subprocess
from typing import Callable, Sequence

import mss

from src.core import app_paths

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorInfo:
    """Tek bir ekranın sanal masaüstü koordinatları ve meta verisi."""

    index: int
    left: int
    top: int
    width: int
    height: int
    is_primary: bool

    @property
    def label(self) -> str:
        role = "Ana Ekran" if self.is_primary else f"{self.index}. Ekran"
        return f"Ekran {self.index} ({role}) - {self.width}x{self.height} @ ({self.left},{self.top})"


@dataclass(frozen=True)
class VirtualDesktopGeometry:
    """Tüm ekranları kapsayan birleşik sanal masaüstü alanı."""

    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class DisplayTopologyResult:
    """Mevcut ekran dizilimi ve 3. ekran hazırlık durumu."""

    virtual_desktop: VirtualDesktopGeometry
    monitors: tuple[MonitorInfo, ...]
    selected_monitor: MonitorInfo
    is_third_screen_ready: bool
    warning_message: str | None = None


def list_monitors(raw_monitors: Sequence[dict[str, int]] | None = None) -> tuple[VirtualDesktopGeometry, list[MonitorInfo]]:
    """MSS ekran listesini ayrıştırarak sanal masaüstü ve fiziksel/sanal ekranları döndürür."""
    if raw_monitors is None:
        with mss.MSS() as sct:
            raw_monitors = list(sct.monitors)

    if not raw_monitors:
        fallback_vd = VirtualDesktopGeometry(left=0, top=0, width=1920, height=1080)
        fallback_mon = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080, is_primary=True)
        return fallback_vd, [fallback_mon]

    vd_raw = raw_monitors[0]
    virtual_desktop = VirtualDesktopGeometry(
        left=int(vd_raw["left"]),
        top=int(vd_raw["top"]),
        width=max(1, int(vd_raw["width"])),
        height=max(1, int(vd_raw["height"])),
    )

    monitors: list[MonitorInfo] = []
    for idx, mon in enumerate(raw_monitors[1:], start=1):
        left = int(mon["left"])
        top = int(mon["top"])
        is_primary = left == 0 and top == 0
        monitors.append(
            MonitorInfo(
                index=idx,
                left=left,
                top=top,
                width=max(1, int(mon["width"])),
                height=max(1, int(mon["height"])),
                is_primary=is_primary,
            )
        )

    if not monitors:
        monitors.append(
            MonitorInfo(
                index=1,
                left=virtual_desktop.left,
                top=virtual_desktop.top,
                width=virtual_desktop.width,
                height=virtual_desktop.height,
                is_primary=True,
            )
        )

    return virtual_desktop, monitors


def inspect_topology(
    preferred_index: int = 3,
    raw_monitors: Sequence[dict[str, int]] | None = None,
) -> DisplayTopologyResult:
    """Hedef ekranı (varsayılan 3. ekran) seçer ve 3 ekranlı kurulum durumunu raporlar."""
    virtual_desktop, monitors = list_monitors(raw_monitors=raw_monitors)
    is_third_ready = len(monitors) >= 3

    selected = next((m for m in monitors if m.index == preferred_index), None)
    warning: str | None = None

    if selected is None:
        selected = monitors[-1]
        warning = (
            f"İstenen {preferred_index}. ekran bulunamadı (algılanan ekran sayısı: {len(monitors)}). "
            f"Geçici olarak Ekran {selected.index} seçildi. Bağımsız 3. ekran için Sanal Ekran Sürücüsü (VDD) "
            "etkinleştirilmeli ve Windows 'Masaüstünü bu ekrana genişlet' modunda olmalıdır."
        )
        logger.warning(warning)
    elif not is_third_ready and preferred_index < 3:
        warning = (
            f"Sistemde şu an {len(monitors)} ekran algılandı. 3 ekranlı kurulum için sanal ekran sürücüsü "
            "eklenebilir."
        )

    return DisplayTopologyResult(
        virtual_desktop=virtual_desktop,
        monitors=tuple(monitors),
        selected_monitor=selected,
        is_third_screen_ready=is_third_ready,
        warning_message=warning,
    )


def extend_displays_windows(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    """Windows yerleşik DisplaySwitch.exe aracıyla ekranları 'Uzalt (Extend)' moduna geçirir."""
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    display_switch = Path(sys_root) / "System32" / "DisplaySwitch.exe"
    if not display_switch.exists():
        logger.warning("DisplaySwitch.exe bulunamadı: %s", display_switch)
        return False

    try:
        proc = runner(
            [str(display_switch), "/extend"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("DisplaySwitch /extend çalıştırılamadı: %s", exc)
        return False


def install_virtual_display_windows(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    """Proje kökündeki 3_ekran_kur.bat betiğini (UAC yönetici onayıyla) çalıştırarak 3. sanal ekranı kurar."""
    script_path = app_paths.resource_root() / "3_ekran_kur.bat"
    if not script_path.is_file():
        logger.warning("3_ekran_kur.bat bulunamadı: %s", script_path)
        return False
    try:
        proc = runner(
            ["cmd.exe", "/c", str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Sanal ekran kurulum betiği çalıştırılamadı: %s", exc)
        return False

