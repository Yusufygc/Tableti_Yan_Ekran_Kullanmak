"""Uygulama içi güncelleme ViewModel'i (PySide6): denetim, indirme, kurulum ve Windows engeli bekleme/yeniden deneme."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
from typing import Callable
import webbrowser

from PySide6.QtCore import Property, QObject, QThread, QTimer, Signal, Slot

from src.services.project_service import InstallerBlockedError, ProjectService, UpdateError, UpdateInfo

logger = logging.getLogger(__name__)

RETRY_INTERVAL_MS = 15_000  # Windows engeli: 15 sn aralıkla
MAX_RETRIES = 40            # en çok 40 kez (10 dk)
QUIT_DELAY_MS = 1_500       # kurulum başladıktan sonra uygulama kapanmadan önce kısa bekleme

STATE_IDLE = "idle"
STATE_CHECKING = "checking"
STATE_UP_TO_DATE = "uptodate"
STATE_AVAILABLE = "available"
STATE_DOWNLOADING = "downloading"
STATE_INSTALLING = "installing"
STATE_WAITING = "waiting"      # Windows kurulum dosyasını engelledi; otomatik yeniden deneniyor
STATE_BLOCKED = "blocked"      # bekleme bitti: kullanıcı dosyayı elle çalıştırmalı
STATE_ERROR = "error"


class _ServiceWorker(QThread):
    """Ağ/disk işlemini UI iş parçacığı dışında yürütür; sonucu ya da hatayı sinyalle bildirir."""

    succeeded = Signal(object)
    failed = Signal(object)
    progress = Signal(int, int)

    def __init__(self, job: Callable[[Callable[[int, int], None]], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        try:
            self.succeeded.emit(self._job(lambda done, total: self.progress.emit(done, total)))
        except Exception as exc:  # noqa: BLE001 - her hata kullanıcıya iletilir ve loglanır
            logger.warning("Güncelleme işlemi başarısız: %s", exc)
            self.failed.emit(exc)


class UpdateViewModel(QObject):
    """QML `UpdateDialog` ve ayar kartını ProjectService güncelleme cephesine bağlar."""

    changed = Signal()
    quitRequested = Signal()

    def __init__(self, service: ProjectService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._state = STATE_IDLE
        self._dialog_open = False
        self._message = ""
        self._progress = 0.0
        self._info: UpdateInfo | None = None
        self._installer: Path | None = None
        self._attempt = 0
        self._manual = False
        self._workers: list[_ServiceWorker] = []
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(RETRY_INTERVAL_MS)
        self._retry_timer.timeout.connect(self._retry_install)

    # ------------------------------------------------------------ özellikler

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(bool, notify=changed)
    def dialogOpen(self) -> bool:
        return self._dialog_open

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Property(float, notify=changed)
    def progress(self) -> float:
        return self._progress

    @Property(str, constant=True)
    def currentVersion(self) -> str:
        return self._service.current_version

    @Property(str, notify=changed)
    def newVersion(self) -> str:
        return self._info.version if self._info else ""

    @Property(str, notify=changed)
    def notes(self) -> str:
        return self._info.notes if self._info else ""

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._state in (STATE_CHECKING, STATE_DOWNLOADING, STATE_INSTALLING)

    @Property(bool, notify=changed)
    def checkOnStartup(self) -> bool:
        return self._service.update_check_allowed()

    @Property(str, notify=changed)
    def statusLine(self) -> str:
        """Ayar kartında gösterilen kısa durum."""
        if self._state == STATE_CHECKING:
            return "Güncellemeler denetleniyor..."
        if self._state == STATE_UP_TO_DATE:
            return f"Güncelsiniz (sürüm {self._service.current_version})."
        if self._state == STATE_ERROR:
            return self._message
        if self._info is not None and self._state == STATE_AVAILABLE:
            return f"Yeni sürüm var: {self._info.version}"
        return f"Yüklü sürüm: {self._service.current_version}"

    # ------------------------------------------------------------ yardımcılar

    def _set(self, state: str, message: str = "") -> None:
        self._state = state
        self._message = message
        self.changed.emit()

    def _start(
        self,
        job: Callable[[Callable[[int, int], None]], object],
        on_ok: Callable[[object], None],
        on_fail: Callable[[object], None],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        worker = _ServiceWorker(job, parent=self)
        worker.succeeded.connect(on_ok)
        worker.failed.connect(on_fail)
        if on_progress is not None:
            worker.progress.connect(on_progress)
        worker.finished.connect(lambda w=worker: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(worker)
        worker.start()

    # ------------------------------------------------------------ denetim

    @Slot()
    def startupCheck(self) -> None:
        """Pencere çizildikten sonra çağrılır; hata ya da güncel sürümde sessiz kalır."""
        if not self._service.update_check_allowed():
            return
        self._manual = False
        self._begin_check(ignore_skipped=False)

    @Slot()
    def checkNow(self) -> None:
        """"Şimdi Denetle": her sonucu (güncel, hata, yeni sürüm) gösterir; atlanan sürüm de teklif edilir."""
        if self.busy:
            return
        self._manual = True
        self._dialog_open = True
        self._begin_check(ignore_skipped=True)

    def _begin_check(self, ignore_skipped: bool) -> None:
        self._set(STATE_CHECKING, "Güncellemeler denetleniyor...")
        self._start(
            lambda _progress: self._service.check_for_update(ignore_skipped=ignore_skipped),
            self._on_check_done,
            self._on_check_failed,
        )

    def _on_check_done(self, result: object) -> None:
        if isinstance(result, UpdateInfo):
            self._info = result
            self._dialog_open = True
            self._set(STATE_AVAILABLE)
        elif self._manual:
            self._set(STATE_UP_TO_DATE, f"Güncelsiniz (sürüm {self._service.current_version}).")
        else:
            self._set(STATE_IDLE)

    def _on_check_failed(self, exc: object) -> None:
        if self._manual:
            self._set(STATE_ERROR, f"Denetlenemedi: {exc}")
        else:
            logger.info("Açılış güncelleme denetimi sessizce atlandı: %s", exc)
            self._set(STATE_IDLE)

    # ------------------------------------------------------------ indirme + kurulum

    @Slot()
    def startUpdate(self) -> None:
        if self._info is None or self.busy:
            return
        info = self._info
        self._progress = 0.0
        self._set(STATE_DOWNLOADING, f"{info.version} indiriliyor...")
        self._start(
            lambda progress: self._service.download_update(info, progress=progress),
            self._on_download_done,
            self._on_download_failed,
            on_progress=self._on_progress,
        )

    def _on_progress(self, done: int, total: int) -> None:
        self._progress = (done / total) if total else 0.0
        self.changed.emit()

    def _on_download_done(self, path: object) -> None:
        self._installer = Path(str(path))
        self._attempt = 0
        self._launch_installer()

    def _on_download_failed(self, exc: object) -> None:
        self._set(STATE_ERROR, f"İndirme başarısız: {exc}")

    def _launch_installer(self) -> None:
        installer = self._installer
        if installer is None:
            return
        self._set(STATE_INSTALLING, "Kurulum başlatılıyor...")
        self._start(
            lambda _progress: self._service.launch_update_installer(installer),
            self._on_install_started,
            self._on_install_failed,
        )

    def _on_install_started(self, _result: object) -> None:
        self._retry_timer.stop()
        self._set(STATE_INSTALLING, "Kurulum başladı; uygulama kapanıyor ve yeni sürüm kendiliğinden açılacak.")
        QTimer.singleShot(QUIT_DELAY_MS, self.quitRequested.emit)

    def _on_install_failed(self, exc: object) -> None:
        if isinstance(exc, InstallerBlockedError):
            self._attempt += 1
            if self._attempt > MAX_RETRIES:
                self._give_up_waiting()
                return
            self._set(
                STATE_WAITING,
                f"Windows kurulum dosyasını şimdilik engelledi; bekleniyor ({self._attempt}/{MAX_RETRIES}). "
                "Engel kalkınca kurulum kendiliğinden başlayacak.",
            )
            self._retry_timer.start()
            return
        self._retry_timer.stop()
        message = str(exc) if isinstance(exc, UpdateError) else f"Kurulum başlatılamadı: {exc}"
        self._set(STATE_ERROR, message)

    def _retry_install(self) -> None:
        if self._state == STATE_WAITING:
            self._launch_installer()

    @Slot()
    def stopWaiting(self) -> None:
        """"Beklemeyi Bırak": kurulum dosyasını Gezgin'de gösterir, elle çalıştırma yolunu açar."""
        self._give_up_waiting()

    def _give_up_waiting(self) -> None:
        self._retry_timer.stop()
        self.revealInstaller()
        self._set(
            STATE_BLOCKED,
            "Windows kurulum dosyasını şimdilik engelledi. Dosya Gezgin'de seçili; çift tıklayarak kurabilirsiniz, "
            "olmazsa birkaç dakika sonra yeniden deneyin.",
        )

    @Slot()
    def revealInstaller(self) -> None:
        if self._installer is not None and self._installer.is_file():
            try:
                subprocess.Popen(["explorer.exe", f"/select,{self._installer}"])  # noqa: S603, S607 - sabit komut, kabuk yok
            except OSError as exc:
                logger.warning("Gezgin açılamadı: %s", exc)

    # ------------------------------------------------------------ diğer eylemler

    @Slot()
    def skipVersion(self) -> None:
        if self._info is not None:
            self._service.skip_update_version(self._info.version)
        self.closeDialog()

    @Slot()
    def closeDialog(self) -> None:
        if self._state in (STATE_DOWNLOADING, STATE_INSTALLING):
            return  # indirme/kurulum sürerken kapatılamaz
        self._retry_timer.stop()
        self._dialog_open = False
        if self._state != STATE_AVAILABLE:
            self._state = STATE_IDLE
        self.changed.emit()

    @Slot()
    def openReleasePage(self) -> None:
        url = self._info.html_url if self._info else self._service.release_page_url
        webbrowser.open(url)

    @Slot(bool)
    def setCheckOnStartup(self, enabled: bool) -> None:
        self._service.set_update_check_on_startup(bool(enabled))
        self.changed.emit()

    def shutdown(self) -> None:
        self._retry_timer.stop()
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(1500)
