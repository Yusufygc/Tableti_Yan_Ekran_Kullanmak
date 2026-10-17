"""Çalışma ortamına (geliştirme / PyInstaller paketi) göre kaynak ve kullanıcı verisi yolları."""

from __future__ import annotations

import os
from pathlib import Path
import sys

USER_DATA_ENV = "TABSCREEN_USB_HOME"  # Testler ve kurulum denemesi kullanıcı klasörüne dokunmasın diye yol değiştirir


def is_frozen() -> bool:
    """PyInstaller ile paketlenmiş çalışma zamanında mı?"""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """
    Salt-okunur kaynakların (istemci HTML'i, adb, VDD, .bat, simge) kök klasörü.
    Paketlenmişte PyInstaller'ın veri klasörü (`_internal`), geliştirmede depo kökü.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Ayar, günlük ve güncelleme tercihleri klasörü (`~/.tabscreen_usb`); ortam değişkeniyle değiştirilebilir."""
    override = os.environ.get(USER_DATA_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".tabscreen_usb"


def icon_path() -> Path:
    """Pencere ve exe simgesi (.ico)."""
    return resource_root() / "packaging" / "icons" / "app.ico"
