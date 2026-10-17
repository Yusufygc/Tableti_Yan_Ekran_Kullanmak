"""Yakalama hattı: satır imzası, BGRX kanal sırası, ölçekleme, aşama süreleri ve mod ön ayarları testleri."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from src.core import app_settings, display_manager, screen_capture


class _FixedGrabber:
    def __init__(self, width: int = 160, height: int = 90) -> None:
        self.frame = screen_capture.RawFrame(width, height, bytes([40, 80, 120] * (width * height)), "RGB")

    def grab(self, monitor: display_manager.MonitorInfo) -> screen_capture.RawFrame:
        return self.frame


def test_signature_detects_small_text_caret_like_change() -> None:
    width, height = 320, 200
    base = bytearray([30, 30, 30] * (width * height))
    sig_a = screen_capture.compute_sparse_signature(screen_capture.RawFrame(width, height, bytes(base), "RGB"))

    # 2 piksel genişliğinde, 16 piksel yüksekliğinde metin imleci benzeri değişim
    for row in range(100, 116):
        for col in (50, 51):
            offset = (row * width + col) * 3
            base[offset : offset + 3] = bytes([255, 255, 255])
    sig_b = screen_capture.compute_sparse_signature(screen_capture.RawFrame(width, height, bytes(base), "RGB"))
    assert sig_a != sig_b

    # BGRX (4 bayt/piksel) tamponunda da imza hesaplanabilmeli; boş tampon boş imza vermeli
    bgrx = screen_capture.RawFrame(16, 16, bytes([1, 2, 3, 0] * 256), "BGRX")
    assert len(screen_capture.compute_sparse_signature(bgrx)) == 16
    assert screen_capture.compute_sparse_signature(screen_capture.RawFrame(0, 0, b"", "RGB")) == b""


def test_encode_bgrx_buffer_swaps_channels_correctly() -> None:
    # mss BGRA düzeni: B=200, G=100, R=50 -> JPEG'de RGB (50, 100, 200) görünmeli
    frame = screen_capture.RawFrame(16, 16, bytes([200, 100, 50, 0] * 256), "BGRX")
    out_w, out_h, jpeg = screen_capture.encode_frame_to_jpeg(frame, quality=95, mode="reading")
    assert (out_w, out_h) == (16, 16)
    pixel = Image.open(BytesIO(jpeg)).convert("RGB").getpixel((8, 8))
    assert abs(pixel[0] - 50) <= 6
    assert abs(pixel[1] - 100) <= 6
    assert abs(pixel[2] - 200) <= 6


def test_scale_uses_fast_reduce_for_integer_factors_and_bilinear_otherwise() -> None:
    frame = screen_capture.RawFrame(120, 60, bytes([10, 20, 30] * (120 * 60)), "RGB")
    assert screen_capture.encode_frame_to_jpeg(frame, scale_factor=0.5)[:2] == (60, 30)
    assert screen_capture.encode_frame_to_jpeg(frame, scale_factor=0.3333)[:2] == (40, 20)
    assert screen_capture.encode_frame_to_jpeg(frame, scale_factor=0.75)[:2] == (90, 45)


def test_two_stage_capture_reports_timings_and_skips_identical() -> None:
    mon = display_manager.MonitorInfo(index=3, left=0, top=0, width=160, height=90, is_primary=False)
    capturer = screen_capture.ScreenCapturer(
        grabber=_FixedGrabber(), cursor_provider=lambda: None, keyframe_interval_sec=10.0
    )
    acquired = capturer.acquire(mon)
    assert acquired.changed is True
    assert acquired.grab_ms >= 0.0
    frame = capturer.encode(acquired, quality=80, mode="video")
    assert frame.changed is True
    assert frame.encode_ms > 0.0
    assert frame.jpeg_bytes

    # Aynı içerik: kodlama atlanmalı
    again = capturer.encode(capturer.acquire(mon))
    assert again.changed is False
    assert again.jpeg_bytes is None
    assert again.encode_ms == 0.0


def test_mode_presets_are_single_source_of_truth() -> None:
    cfg = app_settings.AppSettings()
    assert app_settings.apply_mode_preset(cfg, "video") is True
    assert (cfg.mode, cfg.jpeg_quality, cfg.target_fps, cfg.scale_factor) == (
        "video",
        *app_settings.MODE_PRESETS["video"],
    )
    assert cfg.scale_factor < 1.0  # video: tablet çözme tavanı için küçültülür
    assert app_settings.apply_mode_preset(cfg, "reading") is True
    assert cfg.jpeg_quality == app_settings.MODE_PRESETS["reading"][0]
    assert cfg.scale_factor == 1.0  # okuma: tam çözünürlük

    # Olumsuz senaryo: bilinmeyen mod ayarları değiştirmemeli
    assert app_settings.apply_mode_preset(cfg, "turbo") is False
    assert cfg.mode == "reading"
