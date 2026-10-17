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
    target_fps: int = 40
    jpeg_quality: int = 85
    scale_factor: float = 1.0
    touch_enabled: bool = True
    mode: str = "auto"  # "auto", "reading" veya "video"


# Mod -> (jpeg_quality, target_fps, scale_factor). Tek kaynak: sunucu ve servis aynı ön ayarı kullanır.
# Ölçüm (Lenovo TB330FU, Chrome): tek tek (seri) JPEG çözme 1920x1200'de ≈50 ms (≈20 FPS), ama istemci 4 kareyi
# paralel çözünce (boru hattı) 4:4:4 q88 için ≈44 FPS. Bu yüzden tüm kipler tam çözünürlüktür; tavanı artık
# PC'deki ekran yakalama (≈20 ms, ≈47 FPS) belirler.
# Otomatik: tam çözünürlük 4:4:4 q85 + ekran durulunca tek q92 kare. Okuma: en yüksek kalite (q92, 30 FPS).
# Video: 4:2:0 q70, 45 FPS (daha küçük kareler, daha yüksek akıcılık).
MODE_PRESETS: dict[str, tuple[int, int, float]] = {
    "auto": (85, 40, 1.0),
    "reading": (92, 30, 1.0),
    "video": (70, 45, 1.0),
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
