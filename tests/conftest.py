"""Test yalıtımı: hiçbir test gerçek kullanıcı klasörüne yazmaz veya oradan okumaz."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_app_environment(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ayar dosyası ve log klasörünü her test için geçici klasöre yönlendirir."""
    from src.core import app_settings, logging_config

    base_dir = tmp_path_factory.mktemp("kullanici_verisi")
    logs_folder = base_dir / "logs"
    settings_file = base_dir / "settings.json"

    monkeypatch.setattr(logging_config, "log_dir", lambda: logs_folder)
    monkeypatch.setattr(app_settings, "settings_path", lambda: settings_file)
