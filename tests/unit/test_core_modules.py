"""Çekirdek modüllerin (display_manager, screen_capture, input_injector, adb_manager) birim testleri."""

from __future__ import annotations

import subprocess

from src.core import adb_manager, display_manager, input_injector, screen_capture


class _FakeGrabber:
    def __init__(self, width: int = 160, height: int = 90) -> None:
        self.width = width
        self.height = height
        self.payload = bytes([40, 80, 120] * (width * height))

    def grab(self, monitor: display_manager.MonitorInfo) -> screen_capture.RawFrame:
        return screen_capture.RawFrame(self.width, self.height, self.payload, "RGB")


def test_display_topology_three_screens_and_fallback() -> None:
    raw_three = [
        {"left": 0, "top": 0, "width": 5760, "height": 1080},     # Sanal masaüstü
        {"left": 0, "top": 0, "width": 1920, "height": 1080},     # 1. Ana Monitör
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},  # 2. Laptop Ekranı
        {"left": 3840, "top": 0, "width": 1920, "height": 1080},  # 3. Tablet/Sanal Ekran
    ]
    res_ok = display_manager.inspect_topology(preferred_index=3, raw_monitors=raw_three)
    assert res_ok.is_third_screen_ready is True
    assert res_ok.selected_monitor.index == 3
    assert res_ok.selected_monitor.left == 3840
    assert res_ok.warning_message is None

    # Olumsuz senaryo: Yalnızca 2 ekran varken 3. ekran istenirse uyarı üretip son ekrana düşmeli
    raw_two = raw_three[:3]
    res_warn = display_manager.inspect_topology(preferred_index=3, raw_monitors=raw_two)
    assert res_warn.is_third_screen_ready is False
    assert res_warn.selected_monitor.index == 2
    assert res_warn.warning_message is not None


def test_screen_capture_delta_skip_and_forced_frame() -> None:
    mon = display_manager.MonitorInfo(index=3, left=3840, top=0, width=160, height=90, is_primary=False)
    fake_grabber = _FakeGrabber(160, 90)
    capturer = screen_capture.ScreenCapturer(grabber=fake_grabber, keyframe_interval_sec=10.0)

    # 2. kare (ekran ve imleç değişmedi): skip_identical=True iken sıkıştırma atlanmalı
    cursor_state: list[tuple[int, int] | None] = [None]
    capturer = screen_capture.ScreenCapturer(
        grabber=fake_grabber,
        cursor_provider=lambda: cursor_state[0],
        keyframe_interval_sec=10.0,
    )
    frame_1 = capturer.capture_frame(mon, quality=85, mode="reading")
    assert frame_1.changed is True
    assert frame_1.jpeg_bytes is not None and frame_1.jpeg_bytes.startswith(b"\xff\xd8")

    frame_2 = capturer.capture_frame(mon, quality=85, mode="reading", skip_identical=True)
    assert frame_2.changed is False
    assert frame_2.jpeg_bytes is None

    # Sadece imleç 3. ekranın içine girdiğinde (3850, 20) yeni kare üretilmeli ve imleç çizilmeli
    cursor_state[0] = (3850, 20)
    frame_cursor = capturer.capture_frame(mon, quality=85, mode="reading", skip_identical=True)
    assert frame_cursor.changed is True
    assert frame_cursor.jpeg_bytes is not None

    # Ekran içeriği değiştiğinde yeni JPEG üretilmeli
    fake_grabber.payload = bytes([200, 10, 10] * (160 * 90))
    frame_3 = capturer.capture_frame(mon, quality=70, scale_factor=0.5, mode="video")
    assert frame_3.changed is True
    assert frame_3.width == 80
    assert frame_3.height == 45
    assert frame_3.jpeg_bytes is not None


def test_input_injector_maps_to_third_screen_and_respects_disabled() -> None:
    vd = display_manager.VirtualDesktopGeometry(left=0, top=0, width=5760, height=1080)
    mon_3 = display_manager.MonitorInfo(index=3, left=3840, top=0, width=1920, height=1080, is_primary=False)

    emitted: list[input_injector.MouseCommand] = []
    injector = input_injector.TouchInputInjector(sender=emitted.append, enabled=True)

    # 3. ekranın tam ortasına (0.5, 0.5) dokunma
    cmds = injector.handle_touch_event("tap", 0.5, 0.5, mon_3, vd)
    assert len(cmds) == 2
    assert 3840 + 950 <= cmds[0].desktop_x <= 3840 + 965
    assert 535 <= cmds[0].desktop_y <= 545
    assert cmds[0].norm_65535_x > 43000  # 3. ekran sanal masaüstünün son 1/3 diliminde

    # Scroll ve sağ tık kontrolü
    scroll_cmds = injector.handle_touch_event("scroll", 0.2, 0.2, mon_3, vd, delta_y=-120)
    assert len(scroll_cmds) == 1
    assert scroll_cmds[0]. flags & input_injector.MOUSEEVENTF_WHEEL

    # Olumsuz senaryo: dokunmatik devre dışıyken veya geçersiz olay tipinde komut gönderilmemeli
    before_count = len(emitted)
    injector.handle_touch_event("unknown_event", 0.5, 0.5, mon_3, vd)
    injector.enabled = False
    injector.handle_touch_event("tap", 0.5, 0.5, mon_3, vd)
    assert len(emitted) == before_count


def test_adb_manager_tunnel_success_and_unauthorized_failure() -> None:
    def fake_runner_ok(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1] == "devices":
            return subprocess.CompletedProcess(
                cmd, 0, stdout="List of devices attached\nR52T123456\tdevice\n\n", stderr=""
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="8765", stderr="")

    mgr_ok = adb_manager.AdbManager(adb_executable=r"C:\Android\adb.exe", runner=fake_runner_ok)
    status_ok = mgr_ok.setup_reverse_tunnel(port=8765)
    assert status_ok.success is True
    assert status_ok.device_serial == "R52T123456"
    assert mgr_ok.remove_reverse_tunnel(port=8765, serial="R52T123456") is True

    # Olumsuz senaryo: Cihaz 'unauthorized' ise tünel kurmayı reddetmeli ve açık mesaj dönmeli
    def fake_runner_unauth(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout="List of devices attached\nR52T123456\tunauthorized\n\n", stderr=""
        )

    mgr_unauth = adb_manager.AdbManager(adb_executable=r"C:\Android\adb.exe", runner=fake_runner_unauth)
    status_unauth = mgr_unauth.setup_reverse_tunnel(port=8765)
    assert status_unauth.success is False
    assert "unauthorized" in status_unauth.message
