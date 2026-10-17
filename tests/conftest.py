"""Test yalıtımı: hiçbir test gerçek kullanıcı klasörüne yazmaz veya oradan okumaz; QML ekransız çalışır."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

# Ekransız QML çizimi ve gerçekçi yazı tipi metrikleri (proje-altyapi-rehberi.md Bölüm 4.2)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32" and Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")


@pytest.fixture(autouse=True)
def isolated_app_environment(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ayar dosyası ve log klasörünü her test için geçici klasöre yönlendirir."""
    from src.core import app_settings, logging_config

    base_dir = tmp_path_factory.mktemp("kullanici_verisi")
    logs_folder = base_dir / "logs"
    settings_file = base_dir / "settings.json"

    monkeypatch.setattr(logging_config, "log_dir", lambda: logs_folder)
    monkeypatch.setattr(app_settings, "settings_path", lambda: settings_file)
    # Güncelleme tercihleri ve diğer kullanıcı verisi de geçici klasöre gider; testler ağa güncelleme sorgusu atmaz
    monkeypatch.setenv("TABSCREEN_USB_HOME", str(base_dir))
    monkeypatch.setenv("TABSCREEN_NO_UPDATE_CHECK", "1")
