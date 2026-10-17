"""UpdateViewModel: açılış/elle denetim davranışı, indirme-kurulum akışı, Windows engeli bekleme/yeniden deneme."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import time

from PySide6.QtCore import QCoreApplication
import pytest

from src.services.project_service import InstallerBlockedError, UpdateError, UpdateInfo
from src.ui import update_viewmodel as uvm


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def wait_for(predicate: Callable[[], bool], timeout: float = 3.0) -> None:
    app = _app()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Beklenen durum zamanında oluşmadı")


INFO = UpdateInfo(
    version="2.0.0", tag="v2.0.0", asset_name="TabScreenUSB-Setup-2.0.0.exe",
    download_url="https://github.com/x/y/releases/download/v2.0.0/a.exe", size=10, sha256="0" * 64,
    sha256_url=None, notes="Notlar", html_url="https://github.com/x/y/releases/tag/v2.0.0",
)


class FakeService:
    current_version = "1.0.0"
    release_page_url = "https://github.com/x/y/releases/latest"

    def __init__(self) -> None:
        self.allowed = True
        self.result: UpdateInfo | None = INFO
        self.check_error: Exception | None = None
        self.skipped: list[str] = []
        self.installer_errors: list[Exception] = []
        self.launched: list[Path] = []
        self.check_calls: list[bool] = []
        self.startup_pref: bool | None = None

    def update_check_allowed(self) -> bool:
        return self.allowed

    def set_update_check_on_startup(self, enabled: bool) -> None:
        self.startup_pref = enabled
        self.allowed = enabled

    def check_for_update(self, ignore_skipped: bool = False) -> UpdateInfo | None:
        self.check_calls.append(ignore_skipped)
        if self.check_error:
            raise self.check_error
        return self.result

    def skip_update_version(self, version: str) -> None:
        self.skipped.append(version)

    def download_update(self, info: UpdateInfo, progress: Callable[[int, int], None] | None = None) -> Path:
        if progress:
            progress(5, 10)
            progress(10, 10)
        return Path("C:/gecici/TabScreenUSB-Setup-2.0.0.exe")

    def launch_update_installer(self, installer: Path) -> None:
        if self.installer_errors:
            raise self.installer_errors.pop(0)
        self.launched.append(installer)


@pytest.fixture()
def vm(monkeypatch: pytest.MonkeyPatch) -> tuple[uvm.UpdateViewModel, FakeService]:
    _app()
    monkeypatch.setattr(uvm, "RETRY_INTERVAL_MS", 20)
    monkeypatch.setattr(uvm, "QUIT_DELAY_MS", 10)
    service = FakeService()
    model = uvm.UpdateViewModel(service)  # type: ignore[arg-type]
    model._retry_timer.setInterval(20)
    return model, service


def test_startup_check_opens_dialog_only_when_update_available(vm: tuple[uvm.UpdateViewModel, FakeService]) -> None:
    model, service = vm
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_AVAILABLE)
    assert model.dialogOpen is True and model.newVersion == "2.0.0" and model.notes == "Notlar"
    assert service.check_calls == [False]  # açılışta atlanan sürüm tekrar teklif edilmez


def test_startup_check_is_silent_when_up_to_date_failed_or_disabled(vm: tuple[uvm.UpdateViewModel, FakeService]) -> None:
    model, service = vm
    service.result = None
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_IDLE and not model._workers)
    assert model.dialogOpen is False

    service.check_error = UpdateError("ağ yok")
    model.startupCheck()
    wait_for(lambda: not model._workers)
    assert model.dialogOpen is False and model.state == uvm.STATE_IDLE

    service.allowed = False
    service.check_calls.clear()
    model.startupCheck()
    assert service.check_calls == []  # kapalıyken ağa çıkılmaz


def test_manual_check_shows_every_outcome(vm: tuple[uvm.UpdateViewModel, FakeService]) -> None:
    model, service = vm
    service.result = None
    model.checkNow()
    wait_for(lambda: model.state == uvm.STATE_UP_TO_DATE)
    assert model.dialogOpen is True and "Güncelsiniz" in model.message
    assert service.check_calls == [True]  # elle denetimde atlanan sürüm de teklif edilir

    model.closeDialog()
    service.check_error = UpdateError("sunucu yok")
    model.checkNow()
    wait_for(lambda: model.state == uvm.STATE_ERROR)
    assert "sunucu yok" in model.message


def test_update_flow_downloads_launches_installer_and_requests_quit(vm: tuple[uvm.UpdateViewModel, FakeService]) -> None:
    model, service = vm
    quits: list[bool] = []
    model.quitRequested.connect(lambda: quits.append(True))
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_AVAILABLE)

    model.startUpdate()
    wait_for(lambda: bool(service.launched))
    wait_for(lambda: bool(quits))
    assert model.state == uvm.STATE_INSTALLING
    assert model.progress == 1.0
    model.closeDialog()  # kurulum sürerken kapatılamaz
    assert model.dialogOpen is True


def test_windows_block_waits_retries_and_then_succeeds(vm: tuple[uvm.UpdateViewModel, FakeService]) -> None:
    model, service = vm
    service.installer_errors = [InstallerBlockedError("a"), InstallerBlockedError("b")]
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_AVAILABLE)
    model.startUpdate()
    wait_for(lambda: model.state == uvm.STATE_WAITING)
    assert "bekleniyor" in model.message
    wait_for(lambda: bool(service.launched), timeout=3.0)  # engel kalkınca otomatik başlar
    assert model._attempt == 2


def test_blocked_forever_gives_up_with_manual_instructions(vm: tuple[uvm.UpdateViewModel, FakeService], monkeypatch: pytest.MonkeyPatch) -> None:
    model, service = vm
    monkeypatch.setattr(uvm, "MAX_RETRIES", 2)
    revealed: list[bool] = []
    monkeypatch.setattr(model, "revealInstaller", lambda: revealed.append(True))
    service.installer_errors = [InstallerBlockedError("x")] * 10
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_AVAILABLE)
    model.startUpdate()
    wait_for(lambda: model.state == uvm.STATE_BLOCKED, timeout=4.0)
    assert revealed and "çift tıklayarak" in model.message
    assert not model._retry_timer.isActive()


def test_stop_waiting_and_other_installer_errors(vm: tuple[uvm.UpdateViewModel, FakeService], monkeypatch: pytest.MonkeyPatch) -> None:
    model, service = vm
    monkeypatch.setattr(model, "revealInstaller", lambda: None)
    service.installer_errors = [InstallerBlockedError("x")] * 5
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_AVAILABLE)
    model.startUpdate()
    wait_for(lambda: model.state == uvm.STATE_WAITING)
    model.stopWaiting()
    assert model.state == uvm.STATE_BLOCKED and not model._retry_timer.isActive()

    service.installer_errors = [UpdateError("başlatılamadı")]
    model._launch_installer()
    wait_for(lambda: model.state == uvm.STATE_ERROR)
    assert "başlatılamadı" in model.message


def test_skip_version_and_startup_preference(vm: tuple[uvm.UpdateViewModel, FakeService]) -> None:
    model, service = vm
    model.startupCheck()
    wait_for(lambda: model.state == uvm.STATE_AVAILABLE)
    model.skipVersion()
    assert service.skipped == ["2.0.0"] and model.dialogOpen is False

    model.setCheckOnStartup(False)
    assert service.startup_pref is False and model.checkOnStartup is False
