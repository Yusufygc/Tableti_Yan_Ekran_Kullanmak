"""Otomatik kip: hareket karesi + ekran durulunca tek keskin kare durum makinesi ve kodlama testleri."""

from __future__ import annotations

from io import BytesIO

from PIL import Image
import pytest

from src.core import app_settings, display_manager, screen_capture

MON = display_manager.MonitorInfo(index=3, left=0, top=0, width=192, height=120, is_primary=False)


class _MutableGrabber:
    """Test boyunca içeriği değiştirilebilen sahte yakalayıcı (192x120, boyalı şeritli)."""

    def __init__(self) -> None:
        self.shade = 40

    def grab(self, monitor: display_manager.MonitorInfo) -> screen_capture.RawFrame:
        row = bytes([self.shade, 90, 160] * 192)
        data = bytearray(row * 120)
        # Keskinlik testi için ince 1 piksellik dikey çizgiler (4:2:0 ve küçültme bunları bozar)
        for y in range(120):
            for x in range(0, 192, 2):
                o = (y * 192 + x) * 3
                data[o : o + 3] = bytes([255, 0, 0])
        return screen_capture.RawFrame(192, 120, bytes(data), "RGB")


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [1000.0]
    monkeypatch.setattr(screen_capture.time, "monotonic", lambda: now[0])
    return now


def _capturer(grabber: _MutableGrabber) -> screen_capture.ScreenCapturer:
    return screen_capture.ScreenCapturer(
        grabber=grabber, cursor_provider=lambda: None, keyframe_interval_sec=1.5, settle_sec=0.2
    )


def test_adaptive_sends_motion_then_single_sharp_frame_when_screen_settles(clock: list[float]) -> None:
    grabber = _MutableGrabber()
    cap = _capturer(grabber)

    first = cap.acquire(MON, adaptive=True)
    assert first.changed is True and first.sharp is False  # ilk kare: hareket (küçük/hızlı) kademesi

    clock[0] += 0.1  # henüz durulmadı
    waiting = cap.acquire(MON, adaptive=True)
    assert waiting.changed is False

    clock[0] += 0.15  # toplam 0.25 sn değişmedi -> tek keskin kare
    sharp = cap.acquire(MON, adaptive=True)
    assert sharp.changed is True and sharp.sharp is True

    # Keskin kare bir kez gönderilir; durağan ekranda başka kare (keyframe dahil) gönderilmez
    for _ in range(10):
        clock[0] += 0.5
        assert cap.acquire(MON, adaptive=True).changed is False


def test_adaptive_new_motion_restarts_settle_cycle(clock: list[float]) -> None:
    grabber = _MutableGrabber()
    cap = _capturer(grabber)
    cap.acquire(MON, adaptive=True)
    clock[0] += 0.3
    assert cap.acquire(MON, adaptive=True).sharp is True

    grabber.shade = 200  # içerik değişti (kaydırma/yazma)
    clock[0] += 0.05
    motion = cap.acquire(MON, adaptive=True)
    assert motion.changed is True and motion.sharp is False

    grabber.shade = 210  # hareket sürüyor: keskin kare gönderilmemeli
    clock[0] += 0.05
    assert cap.acquire(MON, adaptive=True).sharp is False

    clock[0] += 0.25  # durulunca yeniden tek keskin kare
    again = cap.acquire(MON, adaptive=True)
    assert again.changed is True and again.sharp is True


def test_reset_delta_state_forces_motion_then_sharp(clock: list[float]) -> None:
    cap = _capturer(_MutableGrabber())
    cap.acquire(MON, adaptive=True)
    clock[0] += 0.3
    cap.acquire(MON, adaptive=True)  # keskin gönderildi

    cap.reset_delta_state()  # yeni tablet istemcisi bağlandı
    assert cap.acquire(MON, adaptive=True).changed is True
    clock[0] += 0.3
    assert cap.acquire(MON, adaptive=True).sharp is True


def test_non_adaptive_modes_keep_keyframe_behavior(clock: list[float]) -> None:
    cap = _capturer(_MutableGrabber())
    assert cap.acquire(MON, adaptive=False).changed is True
    clock[0] += 0.5
    assert cap.acquire(MON, adaptive=False).changed is False
    clock[0] += 1.2  # keyframe aralığı (1.5 sn) doldu
    assert cap.acquire(MON, adaptive=False).changed is True
    assert cap.acquire(MON, adaptive=False).sharp is False


def test_sharp_frame_is_full_resolution_444_and_motion_frame_is_scaled(clock: list[float]) -> None:
    cap = _capturer(_MutableGrabber())
    quality = app_settings.MODE_PRESETS["auto"][0]
    scale = 2 / 3  # küçültülmüş hareket kademesi (kullanıcı ayarıyla seçilebilir); ön ayar artık 1.0

    motion = cap.encode(cap.acquire(MON, adaptive=True), quality=quality, scale_factor=scale, mode="auto")
    assert (motion.width, motion.height) == (128, 80)  # 2/3 küçültme

    clock[0] += 0.3
    sharp = cap.encode(cap.acquire(MON, adaptive=True), quality=quality, scale_factor=scale, mode="auto")
    assert (sharp.width, sharp.height) == (192, 120)  # tam çözünürlük
    assert sharp.jpeg_bytes and motion.jpeg_bytes

    # Keskin kare 4:4:4 + yüksek kalite: ince kırmızı çizgi deseni hareket karesinden belirgin daha iyi korunmalı
    def red_contrast(jpeg: bytes) -> int:
        img = Image.open(BytesIO(jpeg)).convert("RGB")
        left = img.getpixel((img.width // 2, img.height // 2))[0]
        right = img.getpixel((img.width // 2 + 1, img.height // 2))[0]
        return abs(left - right)

    assert red_contrast(sharp.jpeg_bytes) > red_contrast(motion.jpeg_bytes)


def test_auto_preset_and_defaults() -> None:
    assert "auto" in app_settings.MODE_PRESETS
    cfg = app_settings.AppSettings()
    assert cfg.mode == "auto"
    assert app_settings.apply_mode_preset(cfg, "auto") is True
    assert cfg.scale_factor == 1.0  # tablet paralel çözme ile tam çözünürlüğü taşır
    assert app_settings.SHARP_JPEG_QUALITY > cfg.jpeg_quality
    assert "auto" in screen_capture.CHROMA_444_MODES  # hareket kademesi de 4:4:4: keskin kareye geçişte renk dalgalanması yok
