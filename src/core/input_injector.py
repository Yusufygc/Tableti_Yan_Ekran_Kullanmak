"""Tabletten gelen dokunmatik olaylarını 3. ekran koordinatlarına uygulayan Win32 SendInput modülü."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import logging
from typing import Callable

from src.core.display_manager import MonitorInfo, VirtualDesktopGeometry

logger = logging.getLogger(__name__)

# Win32 SendInput sabitleri
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("mi", _MOUSEINPUT),
    ]


@dataclass(frozen=True)
class MouseCommand:
    """Birim testlerde ve Win32 çağrılarında kullanılan fare komutu."""

    norm_65535_x: int
    norm_65535_y: int
    desktop_x: int
    desktop_y: int
    flags: int
    mouse_data: int = 0


def clamp_unit(value: float) -> float:
    """0.0 ile 1.0 arasına sınırlar."""
    return max(0.0, min(1.0, float(value)))


def map_touch_to_desktop(
    norm_x: float,
    norm_y: float,
    monitor: MonitorInfo,
    virtual_desktop: VirtualDesktopGeometry,
) -> tuple[int, int, int, int]:
    """
    Tabletteki (0.0..1.0) dokunma noktasını:
    1) Hedef ekranın gerçek piksel koordinatına (desktop_x, desktop_y)
    2) Win32 MOUSEEVENTF_VIRTUALDESK (0..65535) mutlak koordinatına (abs_x, abs_y) dönüştürür.
    """
    cx = clamp_unit(norm_x)
    cy = clamp_unit(norm_y)

    desktop_x = monitor.left + int(round(cx * max(0, monitor.width - 1)))
    desktop_y = monitor.top + int(round(cy * max(0, monitor.height - 1)))

    vd_w = max(1, virtual_desktop.width - 1)
    vd_h = max(1, virtual_desktop.height - 1)

    abs_x = int(round(((desktop_x - virtual_desktop.left) * 65535) / vd_w))
    abs_y = int(round(((desktop_y - virtual_desktop.top) * 65535) / vd_h))

    abs_x = max(0, min(65535, abs_x))
    abs_y = max(0, min(65535, abs_y))
    return desktop_x, desktop_y, abs_x, abs_y


def _win32_send_mouse_command(cmd: MouseCommand) -> None:
    """Gerçek Windows SendInput çağrısını yürütür."""
    inp = _INPUT(
        type=INPUT_MOUSE,
        mi=_MOUSEINPUT(
            dx=cmd.norm_65535_x,
            dy=cmd.norm_65535_y,
            mouseData=ctypes.c_ulong(cmd.mouse_data & 0xFFFFFFFF).value,
            dwFlags=cmd.flags,
            time=0,
            dwExtraInfo=None,
        ),
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class TouchInputInjector:
    """3. ekrana özel dokunmatik -> fare enjektörü."""

    def __init__(
        self,
        sender: Callable[[MouseCommand], None] | None = None,
        enabled: bool = True,
    ) -> None:
        self._sender = sender or _win32_send_mouse_command
        self.enabled = enabled

    def _emit(
        self,
        norm_x: float,
        norm_y: float,
        monitor: MonitorInfo,
        virtual_desktop: VirtualDesktopGeometry,
        action_flags: int,
        mouse_data: int = 0,
    ) -> MouseCommand | None:
        if not self.enabled:
            return None
        desktop_x, desktop_y, abs_x, abs_y = map_touch_to_desktop(
            norm_x=norm_x,
            norm_y=norm_y,
            monitor=monitor,
            virtual_desktop=virtual_desktop,
        )
        base_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
        cmd = MouseCommand(
            norm_65535_x=abs_x,
            norm_65535_y=abs_y,
            desktop_x=desktop_x,
            desktop_y=desktop_y,
            flags=base_flags | action_flags,
            mouse_data=mouse_data,
        )
        self._sender(cmd)
        return cmd

    def handle_touch_event(
        self,
        event_type: str,
        norm_x: float,
        norm_y: float,
        monitor: MonitorInfo,
        virtual_desktop: VirtualDesktopGeometry,
        delta_y: int = 0,
    ) -> list[MouseCommand]:
        """
        İstemciden gelen dokunmatik olayı işler:
        - 'down': Sol tuş basılı + hareket
        - 'move': Sürükleme / imleç hareketi
        - 'up': Sol tuş bırakma
        - 'tap': Tıklama (down + up)
        - 'right_tap': Sağ tıklama (right down + right up)
        - 'scroll': Fare tekerleği kaydırma
        """
        if not self.enabled:
            return []

        commands: list[MouseCommand] = []

        if event_type == "down":
            cmd = self._emit(norm_x, norm_y, monitor, virtual_desktop, MOUSEEVENTF_LEFTDOWN)
            if cmd:
                commands.append(cmd)
        elif event_type == "move":
            cmd = self._emit(norm_x, norm_y, monitor, virtual_desktop, 0)
            if cmd:
                commands.append(cmd)
        elif event_type == "up":
            cmd = self._emit(norm_x, norm_y, monitor, virtual_desktop, MOUSEEVENTF_LEFTUP)
            if cmd:
                commands.append(cmd)
        elif event_type == "tap":
            down_cmd = self._emit(norm_x, norm_y, monitor, virtual_desktop, MOUSEEVENTF_LEFTDOWN)
            up_cmd = self._emit(norm_x, norm_y, monitor, virtual_desktop, MOUSEEVENTF_LEFTUP)
            if down_cmd:
                commands.append(down_cmd)
            if up_cmd:
                commands.append(up_cmd)
        elif event_type == "right_tap":
            rdown = self._emit(norm_x, norm_y, monitor, virtual_desktop, MOUSEEVENTF_RIGHTDOWN)
            rup = self._emit(norm_x, norm_y, monitor, virtual_desktop, MOUSEEVENTF_RIGHTUP)
            if rdown:
                commands.append(rdown)
            if rup:
                commands.append(rup)
        elif event_type == "scroll":
            wheel_cmd = self._emit(
                norm_x,
                norm_y,
                monitor,
                virtual_desktop,
                MOUSEEVENTF_WHEEL,
                mouse_data=int(delta_y),
            )
            if wheel_cmd:
                commands.append(wheel_cmd)
        else:
            logger.warning("Bilinmeyen dokunmatik olay tipi: %s", event_type)

        return commands
