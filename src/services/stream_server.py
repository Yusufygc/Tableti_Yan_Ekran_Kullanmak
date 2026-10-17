"""127.0.0.1 üzerinde çalışan Binary WebSocket ekran yayın ve dokunmatik alıcı sunucusu."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

from aiohttp import WSMsgType, web

from src.core.app_settings import AppSettings, apply_mode_preset
from src.core.display_manager import DisplayTopologyResult, inspect_topology
from src.core.input_injector import TouchInputInjector
from src.core.screen_capture import AcquiredFrame, CaptureFrame, ScreenCapturer

logger = logging.getLogger(__name__)

ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
WS_CLOSE_REPLACED = 4001  # Aynı sunucuya yeni bir istemci bağlandı; eski istemci yeniden bağlanmamalı.
TOPOLOGY_CACHE_TTL_SEC = 1.0
MAX_SCROLL_DELTA = 1200
STATS_EMA_ALPHA = 0.2
IDLE_AFTER_SEC = 1.0  # Bu süre değişim yoksa yoklama hızı düşürülür (boşta CPU/GDI tasarrufu)
IDLE_POLL_FPS = 15


def default_static_dir() -> Path:
    """Varsayılan tablet web istemcisi klasörünü döndürür."""
    return Path(__file__).resolve().parents[1] / "ui" / "client_assets"


def validate_loopback_host(host: str) -> str:
    """Sunucunun yalnızca yerel loopback (127.0.0.1) üzerinde açılmasını zorunlu kılar."""
    cleaned = host.strip().lower()
    if cleaned not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(
            f"Güvenlik ihlali: Yayın sunucusu yalnızca {ALLOWED_LOOPBACK_HOSTS} adreslerinde "
            f"çalışabilir, '{host}' kabul edilmez."
        )
    return cleaned


def is_request_allowed(host_header: str | None, origin_header: str | None) -> bool:
    """
    DNS rebinding ve tarayıcı tabanlı çapraz kaynak (cross-origin) erişimini engeller:
    Host başlığı loopback olmalı; Origin başlığı varsa o da loopback üzerinden http(s) olmalıdır.
    Tarayıcı olmayan yerel istemciler Origin göndermez ve kabul edilir.
    """
    if not host_header:
        return False
    host_name = urlparse(f"//{host_header}").hostname
    if host_name not in ALLOWED_LOOPBACK_HOSTS:
        return False
    if origin_header is None:
        return True
    parsed = urlparse(origin_header)
    return parsed.scheme in ("http", "https") and parsed.hostname in ALLOWED_LOOPBACK_HOSTS


@web.middleware
async def loopback_guard_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    """Loopback dışı Host/Origin taşıyan her isteği 403 ile reddeder."""
    if not is_request_allowed(request.headers.get("Host"), request.headers.get("Origin")):
        logger.warning(
            "Reddedilen istek: Host=%r Origin=%r yol=%s",
            request.headers.get("Host"),
            request.headers.get("Origin"),
            request.path,
        )
        return web.Response(status=403, text="Yasak: yalnızca yerel istemciler kabul edilir.")
    return await handler(request)


class StreamServer:
    """Yerel HTTP + Binary WebSocket 3. ekran yayın sunucusu."""

    def __init__(
        self,
        settings: AppSettings,
        capturer: ScreenCapturer | None = None,
        injector: TouchInputInjector | None = None,
        topology_provider: Any = inspect_topology,
        static_dir: Path | None = None,
    ) -> None:
        validate_loopback_host(settings.host)
        self.settings = settings
        self.capturer = capturer or ScreenCapturer()
        self.injector = injector or TouchInputInjector(enabled=settings.touch_enabled)
        self._topology_provider = topology_provider
        self.static_dir = static_dir or default_static_dir()

        self._clients: set[web.WebSocketResponse] = set()
        self._frames_sent: int = 0
        self._last_fps: float = 0.0
        self._stream_task: asyncio.Task[None] | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._stopping = False
        # Event loop bloke olmasın diye iki tek-işçili havuz: GDI yakalama thread'e bağlıdır (grab),
        # JPEG kodlama ayrı thread'de (encode) çalışır; böylece N. kare kodlanırken N+1. kare yakalanır.
        self._grab_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TabScreenGrab")
        self._encode_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TabScreenEncode")
        self._topology_cache: tuple[float, int, DisplayTopologyResult] | None = None
        self._last_activity = time.monotonic()
        self._stats: dict[str, float] = {"grab_ms": 0.0, "encode_ms": 0.0, "send_ms": 0.0}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def frames_sent(self) -> int:
        return self._frames_sent

    def current_topology(self) -> DisplayTopologyResult:
        """Ekran dizilimini kısa süreli önbellekten döndürür (kare/dokunma başına mss açmamak için)."""
        now = time.monotonic()
        index = self.settings.monitor_index
        cached = self._topology_cache
        if cached is not None and cached[1] == index and (now - cached[0]) < TOPOLOGY_CACHE_TTL_SEC:
            return cached[2]
        topo = self._topology_provider(preferred_index=index)
        self._topology_cache = (now, index, topo)
        return topo

    def _record_stat(self, name: str, value: float) -> None:
        previous = self._stats[name]
        self._stats[name] = value if previous == 0.0 else previous + STATS_EMA_ALPHA * (value - previous)

    def create_app(self) -> web.Application:
        app = web.Application(middlewares=[loopback_guard_middleware])
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/status", self._handle_status)
        app.router.add_get("/ws", self._handle_ws)
        app.on_cleanup.append(self._on_cleanup)
        return app

    async def _on_cleanup(self, _app: web.Application) -> None:
        self._stopping = True
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
        for ws in list(self._clients):
            await ws.close()
        self._clients.clear()
        self._grab_pool.shutdown(wait=False, cancel_futures=True)
        self._encode_pool.shutdown(wait=False, cancel_futures=True)

    async def _handle_index(self, _request: web.Request) -> web.Response:
        index_file = self.static_dir / "index.html"
        if not index_file.exists():
            return web.Response(text="İstemci dosyası (index.html) bulunamadı.", status=404)
        html = index_file.read_text(encoding="utf-8")
        return web.Response(text=html, content_type="text/html", charset="utf-8")

    async def _handle_status(self, _request: web.Request) -> web.Response:
        topo = self.current_topology()
        mon = topo.selected_monitor
        payload = {
            "monitor_index": mon.index,
            "monitor_label": mon.label,
            "width": mon.width,
            "height": mon.height,
            "is_third_screen_ready": topo.is_third_screen_ready,
            "warning": topo.warning_message,
            "mode": self.settings.mode,
            "target_fps": self.settings.target_fps,
            "jpeg_quality": self.settings.jpeg_quality,
            "scale_factor": self.settings.scale_factor,
            "touch_enabled": self.injector.enabled,
            "clients": len(self._clients),
            "frames_sent": self._frames_sent,
            "last_fps": round(self._last_fps, 1),
            "grab_ms": round(self._stats["grab_ms"], 1),
            "encode_ms": round(self._stats["encode_ms"], 1),
            "send_ms": round(self._stats["send_ms"], 1),
        }
        return web.json_response(payload)

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=4 * 1024 * 1024, heartbeat=15.0)
        await ws.prepare(request)

        for old_ws in list(self._clients):
            self._clients.discard(old_ws)
            await old_ws.close(code=WS_CLOSE_REPLACED, message=b"replaced")
        self._clients.add(ws)
        self.capturer.reset_delta_state()
        logger.info("Tablet istemcisi bağlandı (aktif istemci: %d)", len(self._clients))

        await self._send_meta(ws)

        if self._stream_task is None or self._stream_task.done():
            self._stopping = False
            self._stream_task = asyncio.create_task(self._broadcast_loop())

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._process_client_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.warning("WebSocket bağlantı hatası: %s", ws.exception())
        finally:
            self._clients.discard(ws)
            logger.info("Tablet istemcisi ayrıldı (kalan istemci: %d)", len(self._clients))

        return ws

    async def _send_meta(self, ws: web.WebSocketResponse) -> None:
        topo = self.current_topology()
        mon = topo.selected_monitor
        meta = {
            "type": "meta",
            "monitor_index": mon.index,
            "width": mon.width,
            "height": mon.height,
            "mode": self.settings.mode,
            "target_fps": self.settings.target_fps,
            "jpeg_quality": self.settings.jpeg_quality,
            "touch_enabled": self.injector.enabled,
            "is_third_screen_ready": topo.is_third_screen_ready,
        }
        await ws.send_str(json.dumps(meta, ensure_ascii=False))

    async def _process_client_message(self, ws: web.WebSocketResponse, raw_text: str) -> None:
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Geçersiz istemci JSON mesajı: %s", exc)
            return
        if not isinstance(data, dict):
            logger.warning("Geçersiz istemci mesajı (nesne bekleniyordu): %s", type(data).__name__)
            return

        msg_type = data.get("type")
        if msg_type == "ping":
            await ws.send_str(json.dumps({"type": "pong", "ts": data.get("ts", 0)}))
        elif msg_type == "touch":
            self._handle_touch_message(data)
        elif msg_type == "config":
            await self._handle_config_message(data)

    def _handle_touch_message(self, data: dict[str, Any]) -> None:
        try:
            event_name = str(data.get("event", ""))
            norm_x = float(data.get("x", 0.0))
            norm_y = float(data.get("y", 0.0))
            delta_y = int(data.get("delta_y", 0))
        except (TypeError, ValueError, OverflowError) as exc:
            logger.warning("Geçersiz dokunmatik mesajı yok sayıldı: %s", exc)
            return
        delta_y = max(-MAX_SCROLL_DELTA, min(MAX_SCROLL_DELTA, delta_y))
        topo = self.current_topology()
        self.injector.handle_touch_event(
            event_type=event_name,
            norm_x=norm_x,
            norm_y=norm_y,
            monitor=topo.selected_monitor,
            virtual_desktop=topo.virtual_desktop,
            delta_y=delta_y,
        )

    async def _handle_config_message(self, data: dict[str, Any]) -> None:
        if "mode" in data:
            apply_mode_preset(self.settings, str(data["mode"]))
        if "touch_enabled" in data:
            self.injector.enabled = bool(data["touch_enabled"])
            self.settings.touch_enabled = self.injector.enabled
        if "monitor_index" in data:
            try:
                self.settings.monitor_index = max(1, int(data["monitor_index"]))
            except (TypeError, ValueError, OverflowError) as exc:
                logger.warning("Geçersiz monitor_index yok sayıldı: %s", exc)
        self.capturer.reset_delta_state()
        for client in list(self._clients):
            if not client.closed:
                await self._send_meta(client)

    async def _grab_next(self, delay: float) -> AcquiredFrame:
        """`delay` kadar bekleyip bir kareyi yakalama thread'inde yakalar (delta kararı dahil)."""
        if delay > 0:
            await asyncio.sleep(delay)
        monitor = self.current_topology().selected_monitor
        loop = asyncio.get_running_loop()
        adaptive = self.settings.mode == "auto"
        return await loop.run_in_executor(self._grab_pool, self.capturer.acquire, monitor, True, adaptive)

    async def _encode_frame(self, acquired: AcquiredFrame) -> CaptureFrame:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._encode_pool,
            lambda: self.capturer.encode(
                acquired,
                quality=self.settings.jpeg_quality,
                scale_factor=self.settings.scale_factor,
                mode=self.settings.mode,
            ),
        )

    async def _send_frame(self, jpeg_bytes: bytes) -> None:
        """Kareyi tüm canlı istemcilere gönderir; kopan istemcileri listeden çıkarır."""
        for ws in list(self._clients):
            if ws.closed:
                self._clients.discard(ws)
                continue
            try:
                await ws.send_bytes(jpeg_bytes)
            except (ConnectionError, RuntimeError) as exc:
                logger.debug("Kare gönderilemedi, istemci çıkarılıyor: %s", exc)
                self._clients.discard(ws)

    def _frame_interval(self) -> float:
        fps = max(5, min(60, int(self.settings.target_fps)))
        if time.monotonic() - self._last_activity > IDLE_AFTER_SEC:
            fps = min(fps, IDLE_POLL_FPS)
        return 1.0 / fps

    async def _broadcast_loop(self) -> None:
        """İki aşamalı hat: N. kare kodlanıp gönderilirken N+1. kare yakalama thread'inde yakalanır."""
        fps_window_start = time.monotonic()
        frames_in_window = 0
        started_at = time.monotonic()
        pending: asyncio.Future[AcquiredFrame] = asyncio.ensure_future(self._grab_next(0.0))

        try:
            while not self._stopping and self._clients:
                try:
                    acquired = await pending
                except Exception:
                    logger.exception("Ekran yakalama hatası, 0.5 sn sonra yeniden denenecek")
                    started_at = time.monotonic() + 0.5
                    pending = asyncio.ensure_future(self._grab_next(0.5))
                    continue

                next_start = max(time.monotonic(), started_at + self._frame_interval())
                started_at = next_start
                pending = asyncio.ensure_future(self._grab_next(next_start - time.monotonic()))

                self._record_stat("grab_ms", acquired.grab_ms)
                if acquired.changed:
                    if not acquired.sharp:
                        self._last_activity = time.monotonic()
                    frame = await self._encode_frame(acquired)
                    if frame.jpeg_bytes:
                        self._record_stat("encode_ms", frame.encode_ms)
                        send_start = time.perf_counter()
                        await self._send_frame(frame.jpeg_bytes)
                        self._record_stat("send_ms", (time.perf_counter() - send_start) * 1000.0)
                        self._frames_sent += 1
                        frames_in_window += 1

                now = time.monotonic()
                elapsed_window = now - fps_window_start
                if elapsed_window >= 1.0:
                    self._last_fps = frames_in_window / elapsed_window
                    fps_window_start = now
                    frames_in_window = 0
        finally:
            pending.cancel()

    async def start(self) -> None:
        """Sunucuyu 127.0.0.1 üzerinde başlatır."""
        validate_loopback_host(self.settings.host)
        app = self.create_app()
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self.settings.host, port=self.settings.port)
        await self._site.start()
        logger.info("Yayın sunucusu başlatıldı: http://%s:%d", self.settings.host, self.settings.port)

    async def stop(self) -> None:
        """Sunucuyu ve aktif bağlantıları güvenli şekilde kapatır."""
        self._stopping = True
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            logger.info("Yayın sunucusu durduruldu.")
