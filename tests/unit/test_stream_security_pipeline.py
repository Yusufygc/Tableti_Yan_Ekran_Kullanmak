"""StreamServer güvenlik (Host/Origin), tek istemci, mesaj doğrulama, ölçüm ve önbellek testleri."""

from __future__ import annotations

import asyncio
import json

from aiohttp import WSMsgType, WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer
import pytest

from src.core import app_settings, display_manager, input_injector, screen_capture
from src.services import stream_server


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


def _make_server() -> stream_server.StreamServer:
    cfg = app_settings.AppSettings(monitor_index=3, host="127.0.0.1", port=8765, target_fps=60)
    return stream_server.StreamServer(
        settings=cfg,
        capturer=screen_capture.ScreenCapturer(grabber=_FakeGrabber()),
        injector=input_injector.TouchInputInjector(sender=lambda _cmd: None, enabled=True),
        topology_provider=_fake_topology,
    )


def test_request_guard_allows_only_loopback_host_and_origin() -> None:
    assert stream_server.is_request_allowed("127.0.0.1:8765", None) is True
    assert stream_server.is_request_allowed("localhost:8765", "http://127.0.0.1:8765") is True
    assert stream_server.is_request_allowed("[::1]:8765", None) is True

    # Olumsuz senaryo: kötü niyetli web sayfası (yabancı Origin), DNS rebinding (yabancı Host), eksik Host
    assert stream_server.is_request_allowed("127.0.0.1:8765", "https://evil.example") is False
    assert stream_server.is_request_allowed("127.0.0.1:8765", "null") is False
    assert stream_server.is_request_allowed("evil.example:8765", None) is False
    assert stream_server.is_request_allowed(None, None) is False


def test_websocket_rejects_foreign_origin_and_host() -> None:
    async def _run() -> None:
        srv = _make_server()
        async with TestServer(srv.create_app()) as test_srv, TestClient(test_srv) as client:
            with pytest.raises(WSServerHandshakeError) as origin_err:
                await client.ws_connect("/ws", headers={"Origin": "https://evil.example"})
            assert origin_err.value.status == 403

            with pytest.raises(WSServerHandshakeError) as host_err:
                await client.ws_connect("/ws", headers={"Host": "evil.example"})
            assert host_err.value.status == 403

            resp = await client.get("/status", headers={"Origin": "https://evil.example"})
            assert resp.status == 403
            assert srv.client_count == 0

    asyncio.run(_run())


def test_new_client_replaces_old_client_with_close_code_4001() -> None:
    async def _run() -> None:
        srv = _make_server()
        async with TestServer(srv.create_app()) as test_srv, TestClient(test_srv) as client:
            ws_old = await client.ws_connect("/ws")
            await ws_old.receive(timeout=2.0)  # meta
            ws_new = await client.ws_connect("/ws")
            await ws_new.receive(timeout=2.0)  # meta

            closed = False
            for _ in range(40):
                msg = await ws_old.receive(timeout=2.0)
                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                    closed = True
                    break
            assert closed, "Eski istemci kapatılmalı"
            assert ws_old.close_code == stream_server.WS_CLOSE_REPLACED
            assert srv.client_count == 1
            await ws_new.close()

    asyncio.run(_run())


def test_malformed_client_messages_do_not_drop_connection() -> None:
    async def _run() -> None:
        srv = _make_server()
        async with TestServer(srv.create_app()) as test_srv, TestClient(test_srv) as client:
            async with client.ws_connect("/ws") as ws:
                await ws.send_str(json.dumps({"type": "touch", "event": "tap", "x": "abc", "y": None}))
                await ws.send_str(json.dumps({"type": "config", "monitor_index": "xx"}))
                await ws.send_str(json.dumps([1, 2, 3]))
                await ws.send_str("{bozuk json")
                await ws.send_str(json.dumps({"type": "ping", "ts": 7}))

                got_pong = False
                for _ in range(60):
                    msg = await ws.receive(timeout=2.0)
                    if msg.type == WSMsgType.TEXT and json.loads(msg.data).get("type") == "pong":
                        got_pong = True
                        break
                assert got_pong, "Bozuk mesajlardan sonra bağlantı açık kalmalı"

    asyncio.run(_run())


def test_status_reports_stage_timings() -> None:
    async def _run() -> None:
        srv = _make_server()
        async with TestServer(srv.create_app()) as test_srv, TestClient(test_srv) as client:
            async with client.ws_connect("/ws") as ws:
                for _ in range(10):
                    msg = await ws.receive(timeout=2.0)
                    if msg.type == WSMsgType.BINARY:
                        break
                status = await (await client.get("/status")).json()
                assert status["grab_ms"] >= 0.0
                assert status["encode_ms"] > 0.0
                assert "send_ms" in status

    asyncio.run(_run())


def test_topology_is_cached_per_monitor_index() -> None:
    calls: list[int] = []

    def counting_topology(preferred_index: int = 3) -> display_manager.DisplayTopologyResult:
        calls.append(preferred_index)
        return _fake_topology(preferred_index)

    srv = _make_server()
    srv._topology_provider = counting_topology
    srv.current_topology()
    srv.current_topology()
    assert len(calls) == 1

    # Ekran indeksi değişince önbellek geçersiz olmalı
    srv.settings.monitor_index = 2
    srv.current_topology()
    assert len(calls) == 2
