"""Ekran yakalama, imleç çizimi, adaptif kare farkı (delta) tespiti ve JPEG sıkıştırma modülü."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
import hashlib
import io
import logging
import threading
import time
from typing import Callable, Protocol

import mss
from PIL import Image, ImageDraw

from src.core.app_settings import SETTLE_SEC, SHARP_JPEG_QUALITY
from src.core.display_manager import MonitorInfo

logger = logging.getLogger(__name__)

# 4:4:4 (tam renk çözünürlüğü, keskin metin) kullanan kipler; "video" 4:2:0 ile daha küçük kare üretir.
CHROMA_444_MODES = ("reading", "auto", "sharp")


@dataclass(frozen=True)
class RawFrame:
    """Yakalanan ham piksel tamponu. raw_mode: 'RGB' (3 bayt/piksel) veya 'BGRX' (mss yerel biçimi, 4 bayt/piksel)."""

    width: int
    height: int
    data: bytes | bytearray
    raw_mode: str = "RGB"

    @property
    def bytes_per_pixel(self) -> int:
        return 3 if self.raw_mode == "RGB" else 4


class RawGrabber(Protocol):
    """Test edilebilir ekran yakalayıcı arayüzü."""

    def grab(self, monitor: MonitorInfo) -> RawFrame:
        """Hedef ekranı yakalayıp ham piksel tamponu döndürür."""


class MssRawGrabber:
    """
    MSS tabanlı gerçek ekran yakalayıcı (BGRA tamponu RGB'ye kopyalamadan döndürür).

    mss GDI tutamaçları (DC) onları oluşturan thread'e bağlıdır: yayın durdurulup yeniden başlatılınca
    yeni işçi thread eski tutamaçlarla `BitBlt` yapamaz; ekran dizilimi değişince (sanal ekran kur/kaldır)
    tutamaçlar geçersizleşir. Bu yüzden thread değişiminde veya `ScreenShotError`'da tutamaçlar yenilenir.
    """

    def __init__(self) -> None:
        self._sct: mss.base.MSSBase | None = None
        self._owner_thread: int | None = None

    def _open(self) -> mss.base.MSSBase:
        self.close()
        self._sct = mss.MSS()
        self._owner_thread = threading.get_ident()
        return self._sct

    def grab(self, monitor: MonitorInfo) -> RawFrame:
        region = {
            "left": monitor.left,
            "top": monitor.top,
            "width": monitor.width,
            "height": monitor.height,
        }
        sct = self._sct
        if sct is None or self._owner_thread != threading.get_ident():
            sct = self._open()
        try:
            shot = sct.grab(region)
        except mss.exception.ScreenShotError as exc:
            logger.warning("Ekran yakalama başarısız (%s); GDI tutamaçları yenilenip bir kez daha denenecek", exc)
            shot = self._open().grab(region)
        return RawFrame(width=shot.width, height=shot.height, data=shot.bgra, raw_mode="BGRX")

    def close(self) -> None:
        sct, self._sct, self._owner_thread = self._sct, None, None
        if sct is None:
            return
        try:
            sct.close()
        except (mss.exception.ScreenShotError, OSError) as exc:
            logger.debug("Eski mss tutamaçları serbest bırakılamadı (yok sayıldı): %s", exc)


@dataclass(frozen=True)
class CaptureFrame:
    """Yakalanan ve sıkıştırılan tek bir ekran karesi (süreler milisaniye)."""

    width: int
    height: int
    changed: bool
    jpeg_bytes: bytes | None
    timestamp: float
    grab_ms: float = 0.0
    encode_ms: float = 0.0


@dataclass(frozen=True)
class AcquiredFrame:
    """Yakalama aşamasının çıktısı: ham kare + delta kararı (kodlama aşamasına girdi)."""

    raw: RawFrame
    rel_cursor: tuple[int, int] | None
    changed: bool
    timestamp: float
    grab_ms: float
    sharp: bool = False  # Otomatik kip: ekran durulduktan sonra gönderilen tam çözünürlük keskin kare


def get_windows_cursor_pos() -> tuple[int, int] | None:
    """Windows masaüstündeki küresel fare imleci koordinatlarını (x, y) döndürür."""
    pt = ctypes.wintypes.POINT()
    ok = ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    if not ok:
        return None
    return int(pt.x), int(pt.y)


def relative_cursor_in_monitor(
    monitor: MonitorInfo,
    cursor_pos: tuple[int, int] | None,
) -> tuple[int, int] | None:
    """İmleç hedef ekranın içindeyse ekran içi (rel_x, rel_y) koordinatını, değilse None döndürür."""
    if cursor_pos is None:
        return None
    cx, cy = cursor_pos
    if monitor.left <= cx < monitor.left + monitor.width and monitor.top <= cy < monitor.top + monitor.height:
        return cx - monitor.left, cy - monitor.top
    return None


def draw_cursor_pointer(image: Image.Image, rel_x: int, rel_y: int) -> None:
    """
    MSS ekran görüntüsü donanımsal fare imlecini içermediği için,
    imleç 3. ekrandayken görünür bir Windows ok imleci çizer.
    """
    draw = ImageDraw.Draw(image)
    x, y = int(rel_x), int(rel_y)
    # Klasik Windows imleç oku poligon noktaları
    arrow = [
        (x, y),
        (x, y + 18),
        (x + 4, y + 14),
        (x + 8, y + 22),
        (x + 11, y + 20),
        (x + 7, y + 12),
        (x + 13, y + 12),
    ]
    draw.polygon(arrow, fill=(255, 255, 255), outline=(0, 0, 0))


def compute_sparse_signature(
    frame: RawFrame,
    rel_cursor: tuple[int, int] | None = None,
    row_step: int = 8,
) -> bytes:
    """
    Durağan ekranı ve imleç hareketini hızlıca tespit etmek için BLAKE2b özeti üretir.
    Her `row_step`. satır tam genişlikte örneklenir; en az `row_step` piksel yüksekliğindeki
    her değişim (metin imleci, satır güncellemesi) yakalanır.
    """
    if not frame.data:
        return b""
    stride = frame.width * frame.bytes_per_pixel
    view = memoryview(frame.data)
    hasher = hashlib.blake2b(digest_size=16)
    step = max(1, row_step)
    for row in range(0, frame.height, step):
        hasher.update(view[row * stride : (row + 1) * stride])
    if rel_cursor is not None:
        hasher.update(f":{rel_cursor[0]},{rel_cursor[1]}".encode("utf-8"))
    return hasher.digest()


def _scale_image(image: Image.Image, scale: float) -> Image.Image:
    """Ölçek 1/k (k tamsayı) ise hızlı kutu ortalaması (`reduce`), değilse bilinear küçültme uygular."""
    inv = 1.0 / scale
    k = round(inv)
    if k >= 2 and abs(inv - k) < 0.02:
        return image.reduce(k)
    out_w = max(1, round(image.width * scale))
    out_h = max(1, round(image.height * scale))
    return image.resize((out_w, out_h), Image.Resampling.BILINEAR)


def encode_frame_to_jpeg(
    frame: RawFrame,
    quality: int = 82,
    scale_factor: float = 1.0,
    mode: str = "reading",
    rel_cursor: tuple[int, int] | None = None,
) -> tuple[int, int, bytes]:
    """Ham tamponu (ve varsa 3. ekran üzerindeki fare imlecini) JPEG'e kodlar."""
    clamped_quality = max(30, min(95, int(quality)))
    clamped_scale = max(0.25, min(1.0, float(scale_factor)))

    if frame.raw_mode == "RGB":
        image = Image.frombytes("RGB", (frame.width, frame.height), bytes(frame.data))
    else:
        image = Image.frombuffer("RGB", (frame.width, frame.height), frame.data, "raw", frame.raw_mode)
    if rel_cursor is not None:
        draw_cursor_pointer(image, rel_cursor[0], rel_cursor[1])

    if clamped_scale < 0.999:
        image = _scale_image(image, clamped_scale)

    subsampling = 0 if mode in CHROMA_444_MODES else 2

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=clamped_quality, subsampling=subsampling, optimize=False)
    return image.width, image.height, buf.getvalue()


class ScreenCapturer:
    """Adaptif kare farkı (delta) ve imleç çizimi destekli ekran yakalayıcı (tek çalışan thread'den kullanılır)."""

    def __init__(
        self,
        grabber: RawGrabber | None = None,
        cursor_provider: Callable[[], tuple[int, int] | None] = get_windows_cursor_pos,
        keyframe_interval_sec: float = 1.5,
        settle_sec: float = SETTLE_SEC,
    ) -> None:
        self._grabber: RawGrabber = grabber or MssRawGrabber()
        self._cursor_provider = cursor_provider
        self._keyframe_interval_sec = keyframe_interval_sec
        self._state_lock = threading.Lock()
        self._settle_sec = settle_sec
        self._last_signature: bytes | None = None
        self._last_keyframe_ts: float = 0.0
        self._last_change_ts: float = 0.0
        self._sharp_pending = False

    def reset_delta_state(self) -> None:
        """Yeni istemci bağlandığında ilk karenin zorunlu gönderilmesi için önbelleği sıfırlar."""
        with self._state_lock:
            self._last_signature = None
            self._last_keyframe_ts = 0.0
            self._last_change_ts = 0.0
            self._sharp_pending = False

    def _decide(self, sig: bytes, now: float, skip_identical: bool, adaptive: bool) -> tuple[bool, bool]:
        """(gönderilsin_mi, keskin_kare_mi) kararını verir ve delta durumunu günceller (kilit altında çağrılır)."""
        changed_signature = self._last_signature != sig
        if adaptive:
            if changed_signature or not skip_identical:
                self._last_change_ts = now
                self._sharp_pending = True
                send, sharp = True, False
            elif self._sharp_pending and (now - self._last_change_ts) >= self._settle_sec:
                self._sharp_pending = False
                send, sharp = True, True
            else:
                send, sharp = False, False
        else:
            is_same = (
                skip_identical
                and not changed_signature
                and (now - self._last_keyframe_ts) < self._keyframe_interval_sec
            )
            send, sharp = not is_same, False
        if send:
            self._last_signature = sig
            self._last_keyframe_ts = now
        return send, sharp

    def acquire(self, monitor: MonitorInfo, skip_identical: bool = True, adaptive: bool = False) -> AcquiredFrame:
        """
        Aşama 1: ekranı yakalar, imleç konumunu alır ve kare farkı (delta) kararını verir.
        `adaptive=True` (Otomatik kip): hareket karesi + ekran `settle_sec` durulunca tek keskin kare.
        """
        t_start = time.perf_counter()
        now = time.monotonic()
        raw = self._grabber.grab(monitor)
        rel_cursor = relative_cursor_in_monitor(monitor, self._cursor_provider())
        sig = compute_sparse_signature(raw, rel_cursor=rel_cursor)
        grab_ms = (time.perf_counter() - t_start) * 1000.0

        with self._state_lock:
            send, sharp = self._decide(sig, now, skip_identical, adaptive)
        return AcquiredFrame(
            raw=raw, rel_cursor=rel_cursor, changed=send, timestamp=now, grab_ms=grab_ms, sharp=sharp
        )

    @staticmethod
    def encode(
        acquired: AcquiredFrame,
        quality: int = 82,
        scale_factor: float = 1.0,
        mode: str = "reading",
    ) -> CaptureFrame:
        """Aşama 2: değişen kareyi JPEG'e kodlar; değişim yoksa sıkıştırmayı atlar."""
        raw = acquired.raw
        if not acquired.changed:
            return CaptureFrame(
                width=raw.width,
                height=raw.height,
                changed=False,
                jpeg_bytes=None,
                timestamp=acquired.timestamp,
                grab_ms=acquired.grab_ms,
            )

        if acquired.sharp:
            quality, scale_factor, mode = SHARP_JPEG_QUALITY, 1.0, "sharp"

        t_enc = time.perf_counter()
        out_w, out_h, jpeg_data = encode_frame_to_jpeg(
            raw,
            quality=quality,
            scale_factor=scale_factor,
            mode=mode,
            rel_cursor=acquired.rel_cursor,
        )
        return CaptureFrame(
            width=out_w,
            height=out_h,
            changed=True,
            jpeg_bytes=jpeg_data,
            timestamp=acquired.timestamp,
            grab_ms=acquired.grab_ms,
            encode_ms=(time.perf_counter() - t_enc) * 1000.0,
        )

    def capture_frame(
        self,
        monitor: MonitorInfo,
        quality: int = 82,
        scale_factor: float = 1.0,
        mode: str = "reading",
        skip_identical: bool = True,
    ) -> CaptureFrame:
        """Tek çağrıda yakalama + kodlama (iki aşamalı hat kullanılmayan yerler ve testler için)."""
        acquired = self.acquire(monitor, skip_identical=skip_identical)
        return self.encode(acquired, quality=quality, scale_factor=scale_factor, mode=mode)
