"""Kullanıcı ayarları kalıcılık modülü (UTF-8 JSON)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AppSettings:
    """3. ekran yayın ve dokunmatik ayarları."""

    monitor_index: int = 3
    host: str = "127.0.0.1"
    port: int = 8765
    target_fps: int = 30
    jpeg_quality: int = 82
    scale_factor: float = 1.0
    touch_enabled: bool = True
    mode: str = "reading"  # "reading" veya "video"


def settings_path() -> Path:
    """Ayar dosyasının yolunu döndürür (testlerde conftest ile yalıtılır)."""
    return Path.home() / ".tabscreen_usb" / "settings.json"


def load_settings() -> AppSettings:
    """Ayarları diskten UTF-8 olarak okur; dosya yoksa veya bozuksa varsayılanları döndürür."""
    path = settings_path()
    if not path.exists():
        return AppSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ayar dosyası okunamadı, varsayılan ayarlar kullanılıyor: %s", exc)
        return AppSettings()

    defaults = asdict(AppSettings())
    filtered = {k: raw.get(k, v) for k, v in defaults.items()}
    return AppSettings(**filtered)


def save_settings(settings: AppSettings) -> Path:
    """Ayarları UTF-8 JSON olarak kaydeder."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(asdict(settings), indent=2, ensure_ascii=False)
    path.write_text(content + "\n", encoding="utf-8")
    return path
