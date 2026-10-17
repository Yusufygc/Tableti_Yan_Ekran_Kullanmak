"""Arayüz kontrastı (WCAG AA >= 4.5:1), erişilebilirlik ve CLI argüman testleri."""

from __future__ import annotations

from pathlib import Path

import main
from src.ui.controller_app import THEME_COLORS

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
