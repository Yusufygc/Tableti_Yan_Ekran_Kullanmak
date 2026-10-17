"""Loglama ve ayar kalıcılığı birim testleri."""

from __future__ import annotations

import logging

from src.core import app_settings, logging_config


def test_setup_logging_is_idempotent() -> None:
    log_file_1 = logging_config.setup_logging("DEBUG")
    log_file_2 = logging_config.setup_logging("INFO")
    assert log_file_1 == log_file_2
    assert log_file_1.exists()

    root = logging.getLogger()
    tagged = [h for h in root.handlers if getattr(h, "_tabscreen_tag", None) is not None]
    assert len(tagged) == 1, "setup_logging tekrar çağrıldığında çift handler eklememeli"


def test_app_settings_roundtrip_and_corrupt_fallback() -> None:
    default_cfg = app_settings.load_settings()
    assert default_cfg.monitor_index == 3
    assert default_cfg.host == "127.0.0.1"

    custom = app_settings.AppSettings(monitor_index=2, target_fps=60, jpeg_quality=90, mode="video")
    saved_path = app_settings.save_settings(custom)
    assert saved_path.exists()

    loaded = app_settings.load_settings()
    assert loaded.monitor_index == 2
    assert loaded.target_fps == 60
    assert loaded.jpeg_quality == 90
    assert loaded.mode == "video"

    # Bozuk JSON durumunda sessizce çökmemeli, loglayıp varsayılana dönmeli
    saved_path.write_text("{bozuk_json", encoding="utf-8")
    fallback = app_settings.load_settings()
    assert fallback.monitor_index == 3
