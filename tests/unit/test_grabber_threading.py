"""MssRawGrabber: işçi thread değişimi ve GDI hatası sonrası tutamaç yenileme (yayını durdur/başlat regresyonu)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading

import mss
import pytest

from src.core import display_manager, screen_capture

MONITOR = display_manager.MonitorInfo(index=3, left=1920, top=0, width=8, height=4, is_primary=False)


class _ThreadBoundSct:
    """Gerçek mss GDI davranışı: tutamaçlar yalnızca oluşturan thread'de geçerlidir."""

    instances: list["_ThreadBoundSct"] = []
    always_fail = False

    def __init__(self) -> None:
        self.owner = threading.get_ident()
        self.closed = False
        type(self).instances.append(self)

    def grab(self, region: dict[str, int]) -> SimpleNamespace:
        if type(self).always_fail or threading.get_ident() != self.owner:
            raise mss.exception.ScreenShotError("Windows graphics function failed: BitBlt")
        size = region["width"] * region["height"] * 4
        return SimpleNamespace(width=region["width"], height=region["height"], bgra=bytearray(size))

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _fake_mss(monkeypatch: pytest.MonkeyPatch) -> None:
    _ThreadBoundSct.instances = []
    _ThreadBoundSct.always_fail = False
    monkeypatch.setattr(screen_capture.mss, "MSS", _ThreadBoundSct)


def test_grab_after_worker_thread_change_refreshes_handles() -> None:
    grabber = screen_capture.MssRawGrabber()
    for _ in range(3):  # Her tur = yayını durdur/başlat: yeni işçi thread
        pool = ThreadPoolExecutor(max_workers=1)
        frame = pool.submit(grabber.grab, MONITOR).result()
        pool.shutdown()
        assert (frame.width, frame.height, frame.raw_mode) == (8, 4, "BGRX")

    assert len(_ThreadBoundSct.instances) == 3
    assert all(inst.closed for inst in _ThreadBoundSct.instances[:-1])


def test_grab_reuses_handles_within_same_thread() -> None:
    grabber = screen_capture.MssRawGrabber()
    grabber.grab(MONITOR)
    grabber.grab(MONITOR)
    assert len(_ThreadBoundSct.instances) == 1


def test_grab_error_is_retried_once_then_propagates() -> None:
    grabber = screen_capture.MssRawGrabber()
    grabber.grab(MONITOR)

    # Olumsuz senaryo: yenilemeye rağmen yakalama başarısızsa hata gizlenmeden yukarı iletilmeli
    _ThreadBoundSct.always_fail = True
    with pytest.raises(mss.exception.ScreenShotError):
        grabber.grab(MONITOR)
    assert len(_ThreadBoundSct.instances) == 2  # tek yeniden deneme
