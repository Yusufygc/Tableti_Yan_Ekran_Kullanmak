"""Ekran yakalama, imleç çizimi, adaptif kare farkı (delta) tespiti ve JPEG sıkıştırma modülü."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
import hashlib
import io
import time
from typing import Callable, Protocol

import mss
from PIL import Image, ImageDraw

from src.core.display_manager import MonitorInfo


class RawGrabber(Protocol):
    """Test edilebilir ekran yakalayıcı arayüzü."""

    def grab_rgb(self, monitor: MonitorInfo) -> tuple[int, int, bytes]:
        """Hedef ekranı yakalayıp (genişlik, yükseklik, RGB_bytes) döndürür."""


class MssRawGrabber:
    """MSS tabanlı gerçek ekran yakalayıcı."""

    def __init__(self) -> None:
        self._sct: mss.base.MSSBase | None = None

    def grab_rgb(self, monitor: MonitorInfo) -> tuple[int, int, bytes]:
        if self._sct is None:
            self._sct = mss.MSS()
        region = {
            "left": monitor.left,
            "top": monitor.top,
            "width": monitor.width,
            "height": monitor.height,
        }
        shot = self._sct.grab(region)
        return shot.width, shot.height, shot.rgb

    def close(self) -> None:
        if self._sct is not None:
            self._sct.close()
            self._sct = None


@dataclass(frozen=True)
class CaptureFrame:
    """Yakalanan ve sıkıştırılan tek bir ekran karesi."""

    width: int
    height: int
    changed: bool
    jpeg_bytes: bytes | None
    timestamp: float


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
    rgb_bytes: bytes,
    rel_cursor: tuple[int, int] | None = None,
    step: int = 256,
) -> bytes:
    """Durağan ekranı ve imleç hareketini hızlıca tespit etmek için BLAKE2b özeti üretir."""
    if not rgb_bytes:
        return b""
    sampled = rgb_bytes[:: max(1, step)]
    hasher = hashlib.blake2b(sampled, digest_size=16)
    if rel_cursor is not None:
        hasher.update(f":{rel_cursor[0]},{rel_cursor[1]}".encode("utf-8"))
    return hasher.digest()


def encode_rgb_to_jpeg(
    rgb_bytes: bytes,
    width: int,
    height: int,
    quality: int = 82,
    scale_factor: float = 1.0,
    mode: str = "reading",
    rel_cursor: tuple[int, int] | None = None,
) -> tuple[int, int, bytes]:
    """Ham RGB tamponunu (ve varsa 3. ekran üzerindeki fare imlecini) JPEG'e kodlar."""
    clamped_quality = max(30, min(95, int(quality)))
    clamped_scale = max(0.25, min(1.0, float(scale_factor)))

    image = Image.frombytes("RGB", (width, height), rgb_bytes)
    if rel_cursor is not None:
        draw_cursor_pointer(image, rel_cursor[0], rel_cursor[1])

    out_w, out_h = width, height
    if clamped_scale < 0.999:
        out_w = max(1, int(width * clamped_scale))
        out_h = max(1, int(height * clamped_scale))
        image = image.resize((out_w, out_h), Image.Resampling.BILINEAR)

    subsampling = 0 if mode == "reading" else 2

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=clamped_quality, subsampling=subsampling, optimize=False)
    return out_w, out_h, buf.getvalue()


class ScreenCapturer:
    """Adaptif kare farkı (delta) ve imleç çizimi destekli ekran yakalayıcı."""

    def __init__(
        self,
        grabber: RawGrabber | None = None,
        cursor_provider: Callable[[], tuple[int, int] | None] = get_windows_cursor_pos,
        keyframe_interval_sec: float = 1.5,
    ) -> None:
        self._grabber: RawGrabber = grabber or MssRawGrabber()
        self._cursor_provider = cursor_provider
        self._keyframe_interval_sec = keyframe_interval_sec
        self._last_signature: bytes | None = None
        self._last_keyframe_ts: float = 0.0

    def reset_delta_state(self) -> None:
        """Yeni istemci bağlandığında ilk karenin zorunlu gönderilmesi için önbelleği sıfırlar."""
        self._last_signature = None
        self._last_keyframe_ts = 0.0

    def capture_frame(
        self,
        monitor: MonitorInfo,
        quality: int = 82,
        scale_factor: float = 1.0,
        mode: str = "reading",
        skip_identical: bool = True,
    ) -> CaptureFrame:
        """Ekranı ve 3. ekrandaki fare imlecini yakalar; değişim yoksa sıkıştırmayı atlar."""
        now = time.monotonic()
        raw_w, raw_h, rgb = self._grabber.grab_rgb(monitor)
        rel_cursor = relative_cursor_in_monitor(monitor, self._cursor_provider())
        sig = compute_sparse_signature(rgb, rel_cursor=rel_cursor)

        time_since_keyframe = now - self._last_keyframe_ts
        is_same = (
            skip_identical
            and self._last_signature == sig
            and time_since_keyframe < self._keyframe_interval_sec
        )

        if is_same:
            return CaptureFrame(
                width=raw_w,
                height=raw_h,
                changed=False,
                jpeg_bytes=None,
                timestamp=now,
            )

        out_w, out_h, jpeg_data = encode_rgb_to_jpeg(
            rgb_bytes=rgb,
            width=raw_w,
            height=raw_h,
            quality=quality,
            scale_factor=scale_factor,
            mode=mode,
            rel_cursor=rel_cursor,
        )
        self._last_signature = sig
        self._last_keyframe_ts = now
        return CaptureFrame(
            width=out_w,
            height=out_h,
            changed=True,
            jpeg_bytes=jpeg_data,
            timestamp=now,
        )
