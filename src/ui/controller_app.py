"""Windows masaüstü kontrol paneli (PySide6 + QML): ViewModel, QThread işçileri ve uygulama sarmalayıcısı."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Callable
import webbrowser

from PySide6.QtCore import Property, QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from src.services.project_service import ProjectService, ServiceRuntimeSnapshot
from src.ui.update_viewmodel import UpdateViewModel
from src.version import APP_NAME, __version__

logger = logging.getLogger(__name__)

# WCAG AA (>= 4.5:1) uyumlu koyu tema renk paleti (test_ui_contrast ile doğrulanır)
THEME_COLORS: dict[str, tuple[str, str]] = {
    # (ön_plan_metin, arka_plan)
    "primary_text_on_bg": ("#F8FAFC", "#0B0F19"),      # Kontrast: ~18.5:1
    "secondary_text_on_card": ("#E2E8F0", "#161F30"),  # Kontrast: ~12.6:1
    "status_ok_on_card": ("#4ADE80", "#161F30"),       # Kontrast: ~8.6:1
    "status_warn_on_card": ("#FBBF24", "#161F30"),     # Kontrast: ~9.5:1
    "button_primary": ("#0B0F19", "#38BDF8"),          # Kontrast: ~9.1:1
}

MODE_LABELS = {"auto": "Otomatik", "reading": "Okuma", "video": "Video"}


STARTUP_UPDATE_CHECK_DELAY_MS = 3000  # pencere çizildikten sonra (testler ve CI ağa çıkmasın diye `run()` içinde)


def app_icon_path() -> Path:
    """Pencere simgesi: geliştirmede depo kökü, paketlenmişte PyInstaller veri klasörü (aynı göreli yol)."""
    return Path(__file__).resolve().parents[2] / "packaging" / "icons" / "app.ico"


def qml_file_path() -> Path:
    """Ana QML dosyasının yolunu döndürür."""
    return Path(__file__).resolve().parent / "qml" / "Main.qml"


class _BackgroundTaskWorker(QThread):
    """Ağır işlemleri UI iş parçacığı dışında yürüten QThread işçisi."""

    taskFinished = Signal(str, bool, str)

    def __init__(self, task_name: str, action: Callable[[], tuple[bool, str]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._task_name = task_name
        self._action = action

    def run(self) -> None:
        try:
            ok, msg = self._action()
            self.taskFinished.emit(self._task_name, ok, msg)
        except Exception as exc:
            logger.error("Arka plan görevi başarısız (%s): %s", self._task_name, exc)
            self.taskFinished.emit(self._task_name, False, str(exc))


class ControllerViewModel(QObject):
    """QML arayüzünü ProjectService cephesine bağlayan reaktif ViewModel."""

    topologyChanged = Signal()
    preferencesChanged = Signal()
    statusChanged = Signal()
    metricsChanged = Signal()

    def __init__(self, service: ProjectService | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = service or ProjectService()

        self._monitors_model: list[dict[str, object]] = []
        self._selected_monitor_index: int = self.service.settings.monitor_index
        self._is_third_screen_ready: bool = False
        self._topology_message: str = ""
        self._adb_status_text: str = "USB ADB tüneli henüz kurulmadı."
        self._status_text: str = f"Hazır — USB üzerinden http://{self.service.settings.host}:{self.service.settings.port}"
        self._live_metrics_text: str = "Durum: Beklemede · Bağlı Tablet: 0 · Gönderilen Kare: 0"
        self._active_workers: list[_BackgroundTaskWorker] = []

        self.refreshTopology()
        self._update_live_metrics()

    @Property(str, constant=True)
    def windowTitle(self) -> str:
        return f"{APP_NAME} v{__version__} — 3. Ekran USB Kontrol Paneli"

    @Property("QVariantList", notify=topologyChanged)
    def monitorsModel(self) -> list[dict[str, object]]:
        return self._monitors_model

    @Property(int, notify=topologyChanged)
    def selectedMonitorIndex(self) -> int:
        return self._selected_monitor_index

    @Property(bool, notify=topologyChanged)
    def isThirdScreenReady(self) -> bool:
        return self._is_third_screen_ready

    @Property(str, notify=topologyChanged)
    def topologyMessage(self) -> str:
        return self._topology_message

    @Property(str, notify=preferencesChanged)
    def mode(self) -> str:
        return self.service.settings.mode

    @Property(bool, notify=preferencesChanged)
    def touchEnabled(self) -> bool:
        return self.service.settings.touch_enabled

    @Property(str, notify=statusChanged)
    def adbStatusText(self) -> str:
        return self._adb_status_text

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(bool, notify=statusChanged)
    def isRunning(self) -> bool:
        return self.service.is_running

    @Property(str, notify=metricsChanged)
    def liveMetricsText(self) -> str:
        return self._live_metrics_text

    def _start_worker(self, task_name: str, action: Callable[[], tuple[bool, str]]) -> None:
        worker = _BackgroundTaskWorker(task_name, action, parent=self)
        worker.taskFinished.connect(self._on_worker_finished)
        self._active_workers.append(worker)
        worker.start()

    @Slot(str, bool, str)
    def _on_worker_finished(self, task_name: str, ok: bool, message: str) -> None:
        self._active_workers = [w for w in self._active_workers if w.isRunning()]
        if task_name == "tunnel":
            self._adb_status_text = message
        elif task_name == "stream":
            if " :: " in message:
                adb_msg, stream_msg = message.split(" :: ", 1)
                self._adb_status_text = adb_msg
                self._status_text = stream_msg
            else:
                self._status_text = message
        else:
            self._status_text = message
            self.refreshTopology()

        self.statusChanged.emit()
        self._update_live_metrics()

    @Slot()
    def refreshTopology(self) -> None:
        snap: ServiceRuntimeSnapshot = self.service.get_snapshot()
        self._selected_monitor_index = snap.selected_monitor.index
        self._is_third_screen_ready = snap.is_third_screen_ready

        items: list[dict[str, object]] = []
        for mon in snap.monitors:
            role_txt = (
                "Ana Ekran"
                if mon.is_primary
                else ("Tablet / 3. Ekran" if mon.index == 3 else f"{mon.index}. Ekran")
            )
            items.append(
                {
                    "index": mon.index,
                    "role": role_txt,
                    "resolution": f"{mon.width}x{mon.height}",
                    "label": mon.label,
                    "selected": mon.index == snap.selected_monitor.index,
                }
            )
        self._monitors_model = items

        if snap.is_third_screen_ready:
            self._topology_message = (
                f"3 ekranlı dizilim aktif! Seçili ekran: Ekran {snap.selected_monitor.index} "
                f"({snap.selected_monitor.width}x{snap.selected_monitor.height})"
            )
        else:
            self._topology_message = snap.topology_warning or ""

        self.topologyChanged.emit()

    @Slot(int)
    def selectMonitor(self, index: int) -> None:
        self.service.update_preferences(monitor_index=int(index))
        self.refreshTopology()

    @Slot(str)
    def setMode(self, mode_key: str) -> None:
        self.service.update_preferences(mode=str(mode_key))
        self.preferencesChanged.emit()
        self._update_live_metrics()

    @Slot(bool)
    def setTouchEnabled(self, enabled: bool) -> None:
        self.service.update_preferences(touch_enabled=bool(enabled))
        self.preferencesChanged.emit()

    @Slot()
    def extendDisplays(self) -> None:
        self._status_text = "Windows 'Masaüstünü Uzat' komutu uygulanıyor..."
        self.statusChanged.emit()

        def _job() -> tuple[bool, str]:
            ok = self.service.extend_displays_on_windows()
            msg = "Windows 'Masaüstünü Uzat' komutu uygulandı." if ok else "DisplaySwitch çalıştırılamadı."
            return ok, msg

        self._start_worker("extend", _job)

    @Slot()
    def installVirtualDisplay(self) -> None:
        self._status_text = "3. Sanal Ekran (VDD) kuruluyor (Yönetici iznini onaylayın)..."
        self.statusChanged.emit()

        def _job() -> tuple[bool, str]:
            ok = self.service.install_virtual_display()
            msg = "3. Sanal Ekran kuruldu ve uzatıldı!" if ok else "3. Sanal Ekran kurulumu tamamlanamadı."
            return ok, msg

        self._start_worker("vdd", _job)

    @Slot()
    def setupUsbTunnel(self) -> None:
        self._adb_status_text = "USB ADB cihazı ve tünel kontrol ediliyor..."
        self.statusChanged.emit()

        def _job() -> tuple[bool, str]:
            res = self.service.setup_usb_tunnel()
            return res.success, res.message

        self._start_worker("tunnel", _job)

    @Slot()
    def toggleStreaming(self) -> None:
        if self.service.is_running:
            self.service.stop_streaming()
            self._status_text = "Yayın durduruldu."
            self.statusChanged.emit()
            self._update_live_metrics()
            return

        self._status_text = "Yayın sunucusu başlatılıyor..."
        self.statusChanged.emit()

        def _job() -> tuple[bool, str]:
            tunnel_res = self.service.setup_usb_tunnel()
            url = self.service.start_streaming()
            if tunnel_res.success:
                self.service.open_on_tablet(serial=tunnel_res.device_serial)
            return True, f"{tunnel_res.message} :: Yayın Aktif! Tablette otomatik açıldı: {url}"

        self._start_worker("stream", _job)

    @Slot()
    def openBrowserPreview(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.service.settings.port}")

    @Slot()
    def _update_live_metrics(self) -> None:
        snap = self.service.get_snapshot()
        state_str = "Yayın Aktif" if snap.is_running else "Beklemede"
        self._live_metrics_text = (
            f"Durum: {state_str} · Bağlı Tablet: {snap.connected_clients} · "
            f"Gönderilen Kare: {snap.frames_sent} · Mod: {MODE_LABELS.get(snap.mode, snap.mode)}"
        )
        self.metricsChanged.emit()

    def shutdown(self) -> None:
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(1500)
        if self.service.is_running:
            self.service.stop_streaming()
        self.service.remove_usb_tunnel()


class ControllerWindow:
    """PySide6 + QML uygulama penceresi sarmalayıcısı (ViewModel referansını canlı tutar)."""

    def __init__(self, service: ProjectService | None = None) -> None:
        QQuickStyle.setStyle("Basic")
        existing_app = QGuiApplication.instance()
        self.app: QGuiApplication = existing_app if isinstance(existing_app, QGuiApplication) else QGuiApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setApplicationVersion(__version__)
        icon_file = app_icon_path()
        if icon_file.is_file():
            self.app.setWindowIcon(QIcon(str(icon_file)))
        self.service = service or ProjectService()
        # ÖNEMLİ: QML context property zayıf referanstır; Python tarafında canlı tutulur
        self.view_model = ControllerViewModel(service=self.service)
        self.update_view_model = UpdateViewModel(self.service)
        self.update_view_model.quitRequested.connect(self.app.quit)
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("viewModel", self.view_model)
        self.engine.rootContext().setContextProperty("updateViewModel", self.update_view_model)

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.view_model._update_live_metrics)
        self._timer.start()

        self.app.aboutToQuit.connect(self._on_quit)
        self.engine.load(QUrl.fromLocalFile(str(qml_file_path())))
        roots = self.engine.rootObjects()
        if not roots:
            raise RuntimeError("QML arayüzü (Main.qml) yüklenemedi.")

        root_win = roots[0]
        if isinstance(root_win, QWindow):
            self._center_and_show_on_primary_screen(root_win)

    def _center_and_show_on_primary_screen(self, window: QWindow) -> None:
        """
        Çoklu monitör diziliminde (örn. sol ekran -2560, sağ sanal ekran +1920)
        pencerenin ekran dışında veya sanal 3. ekranda açılmasını engeller;
        ana ekranın (primaryScreen) kullanılabilir alanına sığdırıp tam ortalar.
        """
        screen = self.app.primaryScreen()
        if screen is not None:
            window.setScreen(screen)
            avail = screen.availableGeometry()
            target_w = min(max(760, int(avail.width() * 0.54)), max(620, avail.width() - 60))
            target_h = min(max(640, int(avail.height() * 0.76)), max(520, avail.height() - 60))
            pos_x = avail.x() + max(10, (avail.width() - target_w) // 2)
            pos_y = avail.y() + max(10, (avail.height() - target_h) // 2)
            window.setGeometry(pos_x, pos_y, target_w, target_h)
        window.show()
        window.raise_()
        window.requestActivate()

    def _on_quit(self) -> None:
        self._timer.stop()
        self.update_view_model.shutdown()
        self.view_model.shutdown()

    def run(self) -> int:
        # Açılış güncelleme denetimi burada planlanır: kurucu içinde değil (testler ağa çıkmasın)
        QTimer.singleShot(STARTUP_UPDATE_CHECK_DELAY_MS, self.update_view_model.startupCheck)
        return int(self.app.exec())
