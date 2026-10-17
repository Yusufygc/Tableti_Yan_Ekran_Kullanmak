"""TabScreen USB — Ana giriş noktası (Masaüstü Kontrol Paneli veya CLI kipi)."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from src.services.project_service import ProjectService
from src.ui.controller_app import ControllerWindow

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TabScreen USB — Android Tableti USB üzerinden 3. Ekran olarak kullanma aracı"
    )
    parser.add_argument("--cli", action="store_true", help="Arayüz olmadan doğrudan konsoldan başlatır")
    parser.add_argument("--monitor", type=int, default=None, help="Aktarılacak ekran numarası (varsayılan: 3)")
    parser.add_argument(
        "--mode",
        choices=["auto", "reading", "video"],
        default=None,
        help="Görüntü kipi: auto (önerilen), reading (hep keskin) veya video (hep akıcı)",
    )
    parser.add_argument("--no-touch", action="store_true", help="Tabletten dokunmatik kontrolü devre dışı bırakır")
    return parser.parse_args(argv)


def run_cli(service: ProjectService) -> int:
    tunnel_res = service.setup_usb_tunnel()
    print(f"[ADB USB] {tunnel_res.message}")

    topo = service.get_topology()
    for mon in topo.monitors:
        marker = "-> [SEÇİLİ]" if mon.index == topo.selected_monitor.index else "  "
        print(f"{marker} {mon.label}")
    if topo.warning_message:
        print(f"[UYARI] {topo.warning_message}")

    url = service.start_streaming()
    print(f"\n[AKTİF] Yayın başlatıldı: {url}")
    print("Android tabletinizin tarayıcısında http://127.0.0.1:8765 adresini açıp 'Tam Ekran'a dokunun.")
    print("Durdurmak için Ctrl+C tuşlarına basın.\n")

    stop_requested = False

    def _sig_handler(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _sig_handler)
    try:
        while not stop_requested:
            time.sleep(0.5)
    finally:
        service.stop_streaming()
        service.remove_usb_tunnel()
        print("\n[KAPATILDI] Yayın ve USB tüneli temizlendi.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    service = ProjectService()

    if args.monitor is not None or args.mode is not None or args.no_touch:
        service.update_preferences(
            monitor_index=args.monitor,
            mode=args.mode,
            touch_enabled=False if args.no_touch else None,
        )

    if args.cli:
        return run_cli(service)

    app = ControllerWindow(service=service)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
