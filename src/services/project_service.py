"""Arayüz ve CLI için tüm alt sistemleri birleştiren tek cephe (Facade) servisi."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import threading

from src.core import adb_manager, app_settings, display_manager, input_injector, logging_config, screen_capture
from src.services.stream_server import StreamServer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceRuntimeSnapshot:
    """Arayüzde gösterilecek anlık çalışma durumu özeti."""

    is_running: bool
    server_url: str
    connected_clients: int
    frames_sent: int
    selected_monitor: display_manager.MonitorInfo
    monitors: tuple[display_manager.MonitorInfo, ...]
    is_third_screen_ready: bool
    topology_warning: str | None
    mode: str
    touch_enabled: bool


class ProjectService:
    """
    proje-altyapi-rehberi.md Bölüm 4.3 ve 11 uyarınca:
    Arayüz katmanı alt modülleri doğrudan çağırmaz, yalnızca ProjectService cephesini kullanır.
    """

    def __init__(
        self,
        adb_mgr: adb_manager.AdbManager | None = None,
        capturer: screen_capture.ScreenCapturer | None = None,
        injector: input_injector.TouchInputInjector | None = None,
    ) -> None:
        logging_config.setup_logging()
        self._settings = app_settings.load_settings()
        # Kalite/FPS/ölçek arayüzden ayarlanamaz; kayıtlı eski ön ayarlar (ör. küçültülmüş ölçek) yeni ön ayarı ezmesin.
        app_settings.apply_mode_preset(self._settings, self._settings.mode)
        self._adb = adb_mgr or adb_manager.AdbManager()
        self._capturer = capturer or screen_capture.ScreenCapturer()
        self._injector = injector or input_injector.TouchInputInjector(enabled=self._settings.touch_enabled)

        self._server: StreamServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def settings(self) -> app_settings.AppSettings:
        return self._settings

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_topology(self) -> display_manager.DisplayTopologyResult:
        """Mevcut ekran dizilimini ve 3. ekran durumunu döndürür."""
        return display_manager.inspect_topology(preferred_index=self._settings.monitor_index)

    def extend_displays_on_windows(self) -> bool:
        """Windows ekranlarını 'Uzat (Extend)' kipine geçirir."""
        return display_manager.extend_displays_windows()

    def install_virtual_display(self) -> bool:
        """3. Sanal Ekran (VDD) sürücüsünü kurup etkinleştirir."""
        return display_manager.install_virtual_display_windows()

    def list_usb_devices(self) -> list[adb_manager.AdbDevice]:
        """USB üzerinden bağlı Android cihazları döndürür."""
        return self._adb.list_devices()

    def setup_usb_tunnel(self, serial: str | None = None) -> adb_manager.AdbTunnelStatus:
        """USB üzerinden adb reverse tcp:<port> tcp:<port> tünelini kurar."""
        return self._adb.setup_reverse_tunnel(port=self._settings.port, serial=serial)

    def remove_usb_tunnel(self, serial: str | None = None) -> bool:
        """USB tünelini kaldırır."""
        return self._adb.remove_reverse_tunnel(port=self._settings.port, serial=serial)

    def open_on_tablet(self, serial: str | None = None) -> bool:
        """Tablette http://127.0.0.1:<port> ekranını otomatik açar."""
        url = f"http://{self._settings.host}:{self._settings.port}"
        return self._adb.open_url_on_device(url=url, serial=serial)

    def update_preferences(
        self,
        monitor_index: int | None = None,
        mode: str | None = None,
        touch_enabled: bool | None = None,
        target_fps: int | None = None,
        jpeg_quality: int | None = None,
        scale_factor: float | None = None,
    ) -> app_settings.AppSettings:
        """Kullanıcı tercihlerini günceller, diske kaydeder ve aktif sunucuya uygular."""
        if monitor_index is not None:
            self._settings.monitor_index = max(1, int(monitor_index))
        if mode is not None:
            app_settings.apply_mode_preset(self._settings, mode)  # açık kalite/FPS değerleri aşağıda üzerine yazar
        if touch_enabled is not None:
            self._settings.touch_enabled = bool(touch_enabled)
            self._injector.enabled = self._settings.touch_enabled
        if target_fps is not None:
            self._settings.target_fps = max(5, min(60, int(target_fps)))
        if jpeg_quality is not None:
            self._settings.jpeg_quality = max(30, min(95, int(jpeg_quality)))
        if scale_factor is not None:
            self._settings.scale_factor = max(0.25, min(1.0, float(scale_factor)))

        app_settings.save_settings(self._settings)
        self._capturer.reset_delta_state()
        return self._settings

    def start_streaming(self) -> str:
        """Arka plan iş parçacığında yerel WebSocket yayın sunucusunu başlatır."""
        with self._lock:
            if self.is_running:
                return f"http://{self._settings.host}:{self._settings.port}"

            ready_event = threading.Event()
            startup_error: list[BaseException] = []

            def _run_loop() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
                self._server = StreamServer(
                    settings=self._settings,
                    capturer=self._capturer,
                    injector=self._injector,
                )
                try:
                    loop.run_until_complete(self._server.start())
                    ready_event.set()
                    loop.run_forever()
                except BaseException as exc:
                    logger.error("Yayın sunucusu başlatılamadı: %s", exc)
                    startup_error.append(exc)
                    ready_event.set()
                finally:
                    if self._server is not None:
                        loop.run_until_complete(self._server.stop())
                    loop.close()

            self._thread = threading.Thread(target=_run_loop, name="TabScreenStreamThread", daemon=True)
            self._thread.start()
            ready_event.wait(timeout=5.0)

            if startup_error:
                raise RuntimeError(f"Sunucu başlatılamadı: {startup_error[0]}") from startup_error[0]

            return f"http://{self._settings.host}:{self._settings.port}"

    def stop_streaming(self) -> None:
        """Arka planda çalışan yayın sunucusunu güvenli şekilde durdurur."""
        with self._lock:
            if not self.is_running or self._loop is None:
                return
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5.0)
            self._thread = None
            self._loop = None
            self._server = None

    def get_snapshot(self) -> ServiceRuntimeSnapshot:
        """Anlık çalışma durumunu arayüz için paketler."""
        topo = self.get_topology()
        clients = self._server.client_count if self._server else 0
        frames = self._server.frames_sent if self._server else 0
        return ServiceRuntimeSnapshot(
            is_running=self.is_running,
            server_url=f"http://{self._settings.host}:{self._settings.port}",
            connected_clients=clients,
            frames_sent=frames,
            selected_monitor=topo.selected_monitor,
            monitors=topo.monitors,
            is_third_screen_ready=topo.is_third_screen_ready,
            topology_warning=topo.warning_message,
            mode=self._settings.mode,
            touch_enabled=self._injector.enabled,
        )
