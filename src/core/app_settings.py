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
    jpeg_quality: int = 72
    scale_factor: float = 2 / 3
    touch_enabled: bool = True
    mode: str = "auto"  # "auto", "reading" veya "video"


# Mod -> (jpeg_quality, target_fps, scale_factor). Tek kaynak: sunucu ve servis aynı ön ayarı kullanır.
# Ölçüm (Lenovo TB330FU, Chrome): JPEG çözme 1920x1200'de ≈47-51 ms (≈20 FPS tavan), 1280x800'de ≈30 ms (30 FPS).
# Otomatik: hareket varken 1280x800 (akıcı), ekran durulunca tek tam çözünürlük keskin kare (kalite + FPS birlikte).
# Okuma: her zaman tam çözünürlük (keskin, ≈20 FPS tavan). Video: her zaman 1280x800 (akıcı).
MODE_PRESETS: dict[str, tuple[int, int, float]] = {
    "auto": (72, 30, 2 / 3),
    "reading": (88, 30, 1.0),
    "video": (72, 30, 2 / 3),
}

# Otomatik kip: ekran bu süre değişmeyince tam çözünürlük keskin kare gönderilir (4:4:4, yüksek kalite).
SETTLE_SEC = 0.2
SHARP_JPEG_QUALITY = 92


def apply_mode_preset(settings: AppSettings, mode: str) -> bool:
    """Geçerli bir mod ise ayarlara mod ön ayarını (kalite + FPS) uygular; geçersizse False döndürür."""
    preset = MODE_PRESETS.get(mode)
    if preset is None:
        return False
    settings.mode = mode
    settings.jpeg_quality, settings.target_fps, settings.scale_factor = preset
    return True


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
