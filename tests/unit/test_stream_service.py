"""StreamServer (loopback güvenliği, WebSocket protokolü) ve ProjectService birim testleri."""

from __future__ import annotations

import asyncio
import json

from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer
import pytest

from src.core import app_settings, display_manager, input_injector, screen_capture
from src.services import project_service, stream_server


class _FakeGrabber:
    def __init__(self) -> None:
        self.counter = 0

    def grab(self, monitor: display_manager.MonitorInfo) -> screen_capture.RawFrame:
        self.counter += 1
        color = (self.counter * 37) % 255
        return screen_capture.RawFrame(64, 36, bytes([color, 100, 180] * (64 * 36)), "RGB")


def _fake_topology(preferred_index: int = 3) -> display_manager.DisplayTopologyResult:
    vd = display_manager.VirtualDesktopGeometry(left=0, top=0, width=5760, height=1080)
    mon_3 = display_manager.MonitorInfo(
        index=preferred_index, left=3840, top=0, width=1920, height=1080, is_primary=False
    )
    return display_manager.DisplayTopologyResult(
        virtual_desktop=vd,
        monitors=(mon_3,),
        selected_monitor=mon_3,
        is_third_screen_ready=True,
        warning_message=None,
    )


def test_validate_loopback_host_blocks_external_interfaces() -> None:
    assert stream_server.validate_loopback_host("127.0.0.1") == "127.0.0.1"
    assert stream_server.validate_loopback_host("localhost") == "localhost"

    # Olumsuz senaryo: dış ağa (0.0.0.0 veya LAN IP) açılmaya çalışılırsa ValueError fırlatmalı
    with pytest.raises(ValueError, match="Güvenlik ihlali"):
        stream_server.validate_loopback_host("0.0.0.0")
    with pytest.raises(ValueError, match="Güvenlik ihlali"):
        stream_server.validate_loopback_host("192.168.1.10")


def test_stream_server_http_and_websocket_flow() -> None:
    async def _run() -> None:
        emitted: list[input_injector.MouseCommand] = []
        cfg = app_settings.AppSettings(monitor_index=3, host="127.0.0.1", port=8765, target_fps=60)
        srv = stream_server.StreamServer(
            settings=cfg,
            capturer=screen_capture.ScreenCapturer(grabber=_FakeGrabber()),
            injector=input_injector.TouchInputInjector(sender=emitted.append, enabled=True),
            topology_provider=_fake_topology,
        )
        app = srv.create_app()

        async with TestServer(app) as test_srv:
            async with TestClient(test_srv) as client:
                # 1. Ana sayfa (index.html) kontrolü
                resp_index = await client.get("/")
                assert resp_index.status == 200
                html = await resp_index.text()
                assert "screenCanvas" in html

                # 2. Durum (/status) uç noktası kontrolü
                resp_status = await client.get("/status")
                assert resp_status.status == 200
                status_json = await resp_status.json()
                assert status_json["monitor_index"] == 3
                assert status_json["is_third_screen_ready"] is True

                # 3. WebSocket bağlantısı: meta + binary JPEG + touch + ping/pong + config
                async with client.ws_connect("/ws") as ws:
                    first_msg = await ws.receive(timeout=2.0)
                    assert first_msg.type == WSMsgType.TEXT
                    meta = json.loads(first_msg.data)
                    assert meta["type"] == "meta"
                    assert meta["monitor_index"] == 3

                    # Binary JPEG karesini bekle
                    got_binary = False
                    for _ in range(5):
                        msg = await ws.receive(timeout=2.0)
                        if msg.type == WSMsgType.BINARY:
                            assert msg.data.startswith(b"\xff\xd8")
                            got_binary = True
                            break
                    assert got_binary, "WebSocket üzerinden binary JPEG karesi gelmeli"

                    # Dokunmatik olay gönder
                    await ws.send_str(json.dumps({"type": "touch", "event": "tap", "x": 0.5, "y": 0.5}))
                    await ws.send_str(json.dumps({"type": "ping", "ts": 12345}))
                    await ws.send_str(json.dumps({"type": "config", "mode": "video", "touch_enabled": False}))

                    got_pong = False
                    for _ in range(10):
                        msg = await ws.receive(timeout=2.0)
                        if msg.type == WSMsgType.TEXT:
                            payload = json.loads(msg.data)
                            if payload.get("type") == "pong" and payload.get("ts") == 12345:
                                got_pong = True
                                break
                    assert got_pong, "Ping mesajına pong yanıtı dönmeli"
                    assert len(emitted) == 2
                    assert srv.settings.mode == "video"
                    assert srv.injector.enabled is False

    asyncio.run(_run())


def test_project_service_facade_preferences_and_snapshot() -> None:
    svc = project_service.ProjectService(
        capturer=screen_capture.ScreenCapturer(grabber=_FakeGrabber()),
        injector=input_injector.TouchInputInjector(sender=lambda _cmd: None, enabled=True),
    )
    updated = svc.update_preferences(monitor_index=2, mode="video", touch_enabled=False, scale_factor=0.75)
    assert updated.monitor_index == 2
    assert updated.mode == "video"
    assert updated.touch_enabled is False
    assert updated.scale_factor == 0.75

    snap = svc.get_snapshot()
    assert snap.is_running is False
    assert snap.mode == "video"
    assert snap.touch_enabled is False


def test_project_service_reapplies_mode_preset_over_stale_saved_values() -> None:
    # Eski sürümden kalan kayıtlı değerler (küçültülmüş ölçek, düşük kalite) yeni ön ayarı ezmemeli
    stale = app_settings.AppSettings(mode="auto", jpeg_quality=72, scale_factor=2 / 3, target_fps=30)
    app_settings.save_settings(stale)

    svc = project_service.ProjectService(
        capturer=screen_capture.ScreenCapturer(grabber=_FakeGrabber()),
        injector=input_injector.TouchInputInjector(sender=lambda _cmd: None, enabled=True),
    )
    preset_quality, preset_fps, preset_scale = app_settings.MODE_PRESETS["auto"]
    assert svc.settings.mode == "auto"
    assert (svc.settings.jpeg_quality, svc.settings.target_fps, svc.settings.scale_factor) == (
        preset_quality,
        preset_fps,
        preset_scale,
    )
