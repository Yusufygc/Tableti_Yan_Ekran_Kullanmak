"""Arayüz kontrastı (WCAG AA >= 4.5:1), QML yerleşim/erişilebilirlik ve CLI argüman testleri."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtGui import QAccessible

import main
from src.services.project_service import ProjectService
from src.ui.controller_app import THEME_COLORS, ControllerWindow

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _srgb_channel_luminance(value_255: int) -> float:
    s = value_255 / 255.0
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    cleaned = hex_color.lstrip("#")
    r = int(cleaned[0:2], 16)
    g = int(cleaned[2:4], 16)
    b = int(cleaned[4:6], 16)
    return (
        0.2126 * _srgb_channel_luminance(r)
        + 0.7152 * _srgb_channel_luminance(g)
        + 0.0722 * _srgb_channel_luminance(b)
    )


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    lum1 = _relative_luminance(fg_hex)
    lum2 = _relative_luminance(bg_hex)
    brightest = max(lum1, lum2)
    darkest = min(lum1, lum2)
    return (brightest + 0.05) / (darkest + 0.05)


def test_theme_colors_meet_wcag_aa_contrast() -> None:
    for pair_name, (fg, bg) in THEME_COLORS.items():
        ratio = contrast_ratio(fg, bg)
        assert ratio >= 4.5, f"'{pair_name}' ({fg} / {bg}) kontrast oranı yetersiz: {ratio:.2f}:1 (< 4.5:1)"


def test_tablet_html_accessibility_and_offline_readiness() -> None:
    html_path = PROJECT_ROOT / "src" / "ui" / "client_assets" / "index.html"
    content = html_path.read_text(encoding="utf-8")

    # Erişilebilirlik öznitelikleri ve klavye odak halkası kontrolü
    assert 'aria-label="3. Ekran Kontrolleri"' in content
    assert ":focus-visible" in content
    assert 'tabindex="0"' in content

    # Dış ağ / CDN bağımlılığı olmamalı (%100 yerel USB çalışması)
    assert "http://" not in content and "https://" not in content


def test_main_cli_arg_parsing() -> None:
    args = main.parse_args(["--cli", "--monitor", "3", "--mode", "reading", "--no-touch"])
    assert args.cli is True
    assert args.monitor == 3
    assert args.mode == "reading"
    assert args.no_touch is True


def test_qml_layout_viewmodel_bridge_and_accessibility() -> None:
    """
    proje-altyapi-rehberi.md Bölüm 4.5:
    - QML ekransız çizimle yüklenir, kart boyutları ve üst üste binmeme doğrulanır.
    - ViewModel <-> QML veri köprüsü doğrulanır.
    - QAccessible.setActive(True) + queryAccessibleInterface ile Accessible.name doğrulanır.
    """
    QAccessible.setActive(True)
    svc = ProjectService()
    win = ControllerWindow(service=svc)
    try:
        roots = win.engine.rootObjects()
        assert len(roots) == 1
        root_obj = roots[0]
        win.app.processEvents()

        # 1. Ana ekran (primaryScreen) ortalama kontrolü
        primary = win.app.primaryScreen()
        if primary is not None:
            avail = primary.availableGeometry()
            win_x = int(root_obj.property("x"))
            win_y = int(root_obj.property("y"))
            win_w = int(root_obj.property("width"))
            win_h = int(root_obj.property("height"))
            assert win_x >= avail.x()
            assert win_y >= avail.y()
            assert win_x + win_w <= avail.x() + avail.width()
            assert win_y + win_h <= avail.y() + avail.height()

        # 2. Kartların boyut ve farklı monitör/pencere boyutlarında (dar, normal, geniş) yerleşim kontrolü
        display_card = root_obj.findChild(QObject, "displayCard")
        options_card = root_obj.findChild(QObject, "optionsCard")
        action_card = root_obj.findChild(QObject, "actionCard")
        assert display_card is not None and options_card is not None and action_card is not None

        for test_w, test_h in ((640, 540), (860, 660), (1600, 1000)):
            root_obj.setProperty("width", test_w)
            root_obj.setProperty("height", test_h)
            win.app.processEvents()

            for card in (display_card, options_card, action_card):
                c_w = float(card.property("width"))
                c_h = float(card.property("height"))
                assert 300 < c_w <= 1020, f"Kart genişliği sınır dışı ({test_w}x{test_h}): {c_w}"
                assert c_h > 80, f"Kart yüksekliği yetersiz ({test_w}x{test_h}): {c_h}"

            y1 = float(display_card.property("y"))
            h1 = float(display_card.property("height"))
            y2 = float(options_card.property("y"))
            h2 = float(options_card.property("height"))
            y3 = float(action_card.property("y"))
            assert y2 >= y1 + h1, f"displayCard ve optionsCard çakıştı ({test_w}x{test_h})"
            assert y3 >= y2 + h2, f"optionsCard ve actionCard çakıştı ({test_w}x{test_h})"

        # 3. Erişilebilirlik (QAccessible) ve Klavye Odak (activeFocusOnTab) Kontrolü
        interactive_names = [
            "refreshMonitorsButton",
            "extendDisplaysButton",
            "installVddButton",
            "modeAutoButton",
            "modeReadingButton",
            "modeVideoButton",
            "touchToggleButton",
            "setupTunnelButton",
            "toggleStreamButton",
            "previewBrowserButton",
        ]
        for obj_name in interactive_names:
            item = root_obj.findChild(QObject, obj_name)
            assert item is not None, f"QML öğesi bulunamadı: {obj_name}"
            assert bool(item.property("activeFocusOnTab")) is True, f"{obj_name} Tab ile odaklanabilmeli"
            iface = QAccessible.queryAccessibleInterface(item)
            assert iface is not None, f"{obj_name} için QAccessibleInterface alınamadı"
            acc_name = iface.text(QAccessible.Text.Name)
            assert acc_name and len(acc_name.strip()) > 0, f"{obj_name} Accessible.name boş olmamalı"

        # 4. ViewModel <-> ProjectService veri köprüsü kontrolü
        win.view_model.setMode("video")
        win.view_model.setTouchEnabled(False)
        win.app.processEvents()
        assert svc.settings.mode == "video"
        assert svc.settings.touch_enabled is False
    finally:
        win._on_quit()
