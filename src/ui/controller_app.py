"""Windows masaüstü kontrol paneli (Tkinter): Responsive, dinamik, yüksek kontrastlı modern arayüz."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable
import webbrowser

from src.services.project_service import ProjectService, ServiceRuntimeSnapshot
from src.version import APP_NAME, __version__

logger = logging.getLogger(__name__)

# WCAG AA (>= 4.5:1) uyumlu koyu tema renk paleti (test_ui_contrast ile doğrulanır)
THEME_COLORS: dict[str, tuple[str, str]] = {
    # (ön_plan_metin, arka_plan)
    "primary_text_on_bg": ("#F8FAFC", "#0B0F19"),      # Kontrast: ~18.5:1
    "secondary_text_on_card": ("#E2E8F0", "#161F30"),  # Kontrast: ~12.6:1
    "status_ok_on_card": ("#4ADE80", "#161F30"),       # Kontrast: ~8.6:1
    "status_warn_on_card": ("#FBBF24", "#161F30"),     # Kontrast: ~9.5:1
    "button_primary": ("#0B0F19", "#38BDF8"),          # Kontrast: ~9.1:1
}

CARD_BORDER_COLOR = "#26334D"
MODE_LABELS = {"auto": "Otomatik", "reading": "Okuma", "video": "Video"}


class ControllerWindow:
    """3. Ekran (USB Tablet) Windows Kontrol Paneli — Responsive ve Dinamik Yerleşim."""

    def __init__(self, service: ProjectService | None = None) -> None:
        self.service = service or ProjectService()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{__version__} — 3. Ekran USB Kontrol Paneli")

        fg_main, bg_main = THEME_COLORS["primary_text_on_bg"]
        self.root.configure(bg=bg_main)

        self.monitor_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self.service.settings.mode)
        self.touch_var = tk.BooleanVar(value=self.service.settings.touch_enabled)
        self.status_var = tk.StringVar(value="Hazır — USB üzerinden 127.0.0.1:8765")
        self.adb_status_var = tk.StringVar(value="USB ADB tüneli kontrol ediliyor...")
        self.topology_warn_var = tk.StringVar(value="")
        self.live_metrics_var = tk.StringVar(value="Durum: Beklemede · Bağlı Tablet: 0 · Gönderilen Kare: 0")

        self._monitor_map: dict[str, int] = {}
        self._wrap_labels: list[tk.Label] = []

        self._configure_styles()
        self._build_ui()
        self.refresh_topology()
        self._apply_dynamic_initial_geometry()
        self._schedule_live_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError as exc:
            logger.debug("Varsayılan ttk teması kullanılıyor: %s", exc)
        style.configure(
            "TCombobox",
            fieldbackground="#0F172A",
            background="#334155",
            foreground="#F8FAFC",
            arrowcolor="#38BDF8",
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#0F172A")],
            foreground=[("readonly", "#F8FAFC")],
            selectbackground=[("readonly", "#1E293B")],
            selectforeground=[("readonly", "#38BDF8")],
        )

    # --- Yerleşim yardımcıları (tekrarlanan widget kurulumunu tek yerde toplar) ---

    def _make_card(self, parent: tk.Frame, row: int) -> tk.Frame:
        _, bg_card = THEME_COLORS["secondary_text_on_card"]
        card = tk.Frame(
            parent,
            bg=bg_card,
            padx=18,
            pady=14,
            highlightthickness=1,
            highlightbackground=CARD_BORDER_COLOR,
        )
        card.grid(row=row, column=0, sticky="ew", pady=6)
        card.columnconfigure(0, weight=1)
        return card

    def _make_card_title(self, card: tk.Frame, text: str, columnspan: int = 1, pady: tuple[int, int] = (0, 0)) -> None:
        fg_main, _ = THEME_COLORS["primary_text_on_bg"]
        _, bg_card = THEME_COLORS["secondary_text_on_card"]
        tk.Label(
            card,
            text=text,
            font=("Segoe UI", 12, "bold"),
            fg=fg_main,
            bg=bg_card,
            anchor="w",
        ).grid(row=0, column=0, columnspan=columnspan, sticky="w", pady=pady)

    def _make_button(
        self,
        parent: tk.Frame,
        text: str,
        command: Callable[[], None],
        primary: bool = False,
        bold: bool = False,
        pady: int = 6,
    ) -> tk.Button:
        fg_main, _ = THEME_COLORS["primary_text_on_bg"]
        btn_fg, btn_bg = THEME_COLORS["button_primary"]
        fg = btn_fg if primary else fg_main
        return tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 12, "bold" if bold else "normal"),
            fg=fg,
            bg=btn_bg if primary else "#26334D",
            activebackground="#7DD3FC" if primary else "#334155",
            activeforeground=fg,
            relief=tk.FLAT,
            pady=pady,
            cursor="hand2",
            command=command,
        )

    def _make_status_label(
        self,
        parent: tk.Frame,
        variable: tk.StringVar,
        fg: str,
        bold: bool = False,
        wrap: bool = True,
    ) -> tk.Label:
        _, bg_card = THEME_COLORS["secondary_text_on_card"]
        lbl = tk.Label(
            parent,
            textvariable=variable,
            font=("Segoe UI", 12, "bold" if bold else "normal"),
            fg=fg,
            bg=bg_card,
            justify=tk.LEFT,
            anchor="w",
        )
        if wrap:
            self._wrap_labels.append(lbl)
        return lbl

    def _choice_style(self) -> dict[str, object]:
        fg_main, _ = THEME_COLORS["primary_text_on_bg"]
        fg_sec, bg_card = THEME_COLORS["secondary_text_on_card"]
        return {
            "font": ("Segoe UI", 12),
            "fg": fg_sec,
            "bg": bg_card,
            "selectcolor": "#0B0F19",
            "activebackground": bg_card,
            "activeforeground": fg_main,
            "anchor": "w",
            "command": self._on_options_changed,
        }

    # --- Ana yerleşim ---

    def _build_ui(self) -> None:
        _, bg_main = THEME_COLORS["primary_text_on_bg"]

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = tk.Frame(self.root, bg=bg_main, padx=22, pady=18)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)

        self._build_header(main_frame)
        self._build_display_card(main_frame)
        self._build_options_card(main_frame)
        self._build_action_card(main_frame)

        self.root.bind("<Configure>", self._on_window_configure)

    def _build_header(self, main_frame: tk.Frame) -> None:
        fg_main, bg_main = THEME_COLORS["primary_text_on_bg"]
        fg_sec, _ = THEME_COLORS["secondary_text_on_card"]

        header = tk.Frame(main_frame, bg=bg_main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="TabScreen USB — 3. Ekran (Android Tablet) Yöneticisi",
            font=("Segoe UI", 15, "bold"),
            fg=fg_main,
            bg=bg_main,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="%100 Yerel (127.0.0.1 Loopback) · Sıfır Telemetri · Dokunmatik ve İmleç Destekli",
            font=("Segoe UI", 12),
            fg=fg_sec,
            bg=bg_main,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_display_card(self, main_frame: tk.Frame) -> None:
        """1. KART: Ekran topolojisi ve seçimi."""
        _, bg_card = THEME_COLORS["secondary_text_on_card"]
        card = self._make_card(main_frame, row=1)
        self._make_card_title(card, "1. Aktarılacak Ekran Seçimi ve Çoklu Monitör Dizilimi")

        # Görsel Ekran Haritası (Tıklanabilir Ekran Kartları)
        self.monitor_strip = tk.Frame(card, bg=bg_card)
        self.monitor_strip.grid(row=1, column=0, sticky="ew", pady=(8, 8))

        # Tam genişlikte Combobox (Asla sağdaki butonları sıkıştırmaz)
        self.monitor_combo = ttk.Combobox(
            card,
            textvariable=self.monitor_var,
            state="readonly",
            font=("Segoe UI", 12),
        )
        self.monitor_combo.grid(row=2, column=0, sticky="ew", pady=(2, 8))
        self.monitor_combo.bind("<<ComboboxSelected>>", self._on_monitor_selected)

        # Eşit genişlikte 3'lü responsive buton ızgarası
        btn_grid = tk.Frame(card, bg=bg_card)
        btn_grid.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        for col_idx in range(3):
            btn_grid.columnconfigure(col_idx, weight=1, uniform="mon_btns")

        self.refresh_btn = self._make_button(btn_grid, "Ekranları Yenile", self.refresh_topology)
        self.refresh_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.extend_btn = self._make_button(btn_grid, "Masaüstünü Uzat (Extend)", self._on_extend_clicked)
        self.extend_btn.grid(row=0, column=1, sticky="ew", padx=6)

        self.vdd_btn = self._make_button(
            btn_grid, "3. Sanal Ekranı Kur (VDD)", self._on_install_vdd_clicked, primary=True, bold=True
        )
        self.vdd_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        self.warn_lbl = self._make_status_label(
            card, self.topology_warn_var, fg=THEME_COLORS["status_warn_on_card"][0]
        )
        self.warn_lbl.grid(row=4, column=0, sticky="ew", pady=(6, 0))

    def _build_options_card(self, main_frame: tk.Frame) -> None:
        """2. KART: Görüntü modu ve dokunmatik ayarları."""
        card = self._make_card(main_frame, row=2)
        card.columnconfigure(1, weight=1)
        self._make_card_title(card, "2. Görüntü Modu ve Dokunmatik Kontrol", columnspan=2, pady=(0, 6))

        style = self._choice_style()
        tk.Radiobutton(
            card,
            text="Otomatik (Önerilen): hareket varken akıcı, ekran durulunca piksel keskin",
            variable=self.mode_var,
            value="auto",
            **style,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)

        tk.Radiobutton(
            card,
            text="Okuma / Kod Modu (Hep Tam Çözünürlük, ~20 FPS)",
            variable=self.mode_var,
            value="reading",
            **style,
        ).grid(row=2, column=0, sticky="ew", pady=2)

        tk.Radiobutton(
            card,
            text="Video / Akıcı Mod (Hep 1280x800, ~30 FPS)",
            variable=self.mode_var,
            value="video",
            **style,
        ).grid(row=2, column=1, sticky="ew", pady=2)

        self.chk_touch = tk.Checkbutton(
            card,
            text="Tabletten Dokunmatik Kontrol (Tıklama, Sürükleme, Uzun Basma Sağ Tık, İki Parmak Kaydırma)",
            variable=self.touch_var,
            justify=tk.LEFT,
            **style,
        )
        self.chk_touch.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _build_action_card(self, main_frame: tk.Frame) -> None:
        """3. KART: USB ADB tüneli ve yayın kontrolü."""
        fg_sec, bg_card = THEME_COLORS["secondary_text_on_card"]
        card = self._make_card(main_frame, row=3)
        self._make_card_title(card, "3. USB ADB Tüneli ve Yayın Kontrolü")

        self._make_status_label(card, self.adb_status_var, fg=fg_sec).grid(
            row=1, column=0, sticky="ew", pady=(6, 2)
        )
        self._make_status_label(
            card, self.status_var, fg=THEME_COLORS["status_ok_on_card"][0], bold=True
        ).grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self._make_status_label(card, self.live_metrics_var, fg=fg_sec, wrap=False).grid(
            row=3, column=0, sticky="ew", pady=(0, 10)
        )

        btn_grid = tk.Frame(card, bg=bg_card)
        btn_grid.grid(row=4, column=0, sticky="ew")
        for col_idx in range(3):
            btn_grid.columnconfigure(col_idx, weight=1, uniform="act_btns")

        self.tunnel_btn = self._make_button(
            btn_grid, "1) USB ADB Tünelini Kur", self._on_setup_tunnel_clicked, bold=True, pady=8
        )
        self.tunnel_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.start_btn = self._make_button(
            btn_grid,
            "2) Yayını Başlat (127.0.0.1:8765)",
            self._on_toggle_server_clicked,
            primary=True,
            bold=True,
            pady=8,
        )
        self.start_btn.grid(row=0, column=1, sticky="ew", padx=6)

        self.preview_btn = self._make_button(
            btn_grid,
            "Tarayıcıda Test Et",
            lambda: webbrowser.open(f"http://127.0.0.1:{self.service.settings.port}"),
            pady=8,
        )
        self.preview_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _on_window_configure(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if event.widget is not self.root:
            return
        wrap_px = max(420, event.width - 88)
        for lbl in self._wrap_labels:
            lbl.configure(wraplength=wrap_px)
        self.chk_touch.configure(wraplength=wrap_px)

    def _apply_dynamic_initial_geometry(self) -> None:
        """İçeriğin gerçek boyutunu ölçerek hiçbir elemanın kırpılmadığı başlangıç boyutu verir."""
        self.root.update_idletasks()
        req_w = max(840, self.root.winfo_reqwidth() + 36)
        req_h = max(620, self.root.winfo_reqheight() + 24)
        self.root.minsize(780, req_h)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(20, (screen_w - req_w) // 2)
        pos_y = max(20, (screen_h - req_h) // 2)
        self.root.geometry(f"{req_w}x{req_h}+{pos_x}+{pos_y}")

    def _rebuild_monitor_strip(self, snap: ServiceRuntimeSnapshot) -> None:
        for child in self.monitor_strip.winfo_children():
            child.destroy()

        fg_main, _ = THEME_COLORS["primary_text_on_bg"]
        btn_fg, btn_bg = THEME_COLORS["button_primary"]

        for col_idx, mon in enumerate(snap.monitors):
            self.monitor_strip.columnconfigure(col_idx, weight=1, uniform="mon_cards")
            is_sel = mon.index == snap.selected_monitor.index
            role_txt = "Ana Ekran" if mon.is_primary else ("Tablet / 3. Ekran" if mon.index == 3 else f"{mon.index}. Ekran")
            card_bg = btn_bg if is_sel else "#0F172A"
            card_fg = btn_fg if is_sel else fg_main

            btn = tk.Button(
                self.monitor_strip,
                text=f"[{mon.index}] {role_txt}\n{mon.width}x{mon.height}",
                font=("Segoe UI", 12, "bold" if is_sel else "normal"),
                fg=card_fg,
                bg=card_bg,
                activebackground="#7DD3FC" if is_sel else "#1E293B",
                activeforeground=card_fg,
                relief=tk.FLAT,
                pady=8,
                cursor="hand2",
                command=lambda idx=mon.index: self._select_monitor_by_index(idx),
            )
            btn.grid(row=0, column=col_idx, sticky="ew", padx=4)

    def _select_monitor_by_index(self, idx: int) -> None:
        self.service.update_preferences(monitor_index=idx)
        self.refresh_topology()

    def refresh_topology(self) -> None:
        snap: ServiceRuntimeSnapshot = self.service.get_snapshot()
        self._monitor_map.clear()
        labels: list[str] = []
        selected_label = ""

        for mon in snap.monitors:
            self._monitor_map[mon.label] = mon.index
            labels.append(mon.label)
            if mon.index == snap.selected_monitor.index:
                selected_label = mon.label

        self.monitor_combo["values"] = labels
        if selected_label:
            self.monitor_var.set(selected_label)

        if snap.is_third_screen_ready:
            self.topology_warn_var.set(
                f"3 ekranlı dizilim aktif! Seçili ekran: Ekran {snap.selected_monitor.index} "
                f"({snap.selected_monitor.width}x{snap.selected_monitor.height})"
            )
            self.warn_lbl.configure(fg=THEME_COLORS["status_ok_on_card"][0])
        else:
            self.topology_warn_var.set(snap.topology_warning or "")
            self.warn_lbl.configure(fg=THEME_COLORS["status_warn_on_card"][0])

        self._rebuild_monitor_strip(snap)

    def _schedule_live_refresh(self) -> None:
        snap = self.service.get_snapshot()
        state_str = "Yayın Aktif" if snap.is_running else "Beklemede"
        self.live_metrics_var.set(
            f"Durum: {state_str} · Bağlı Tablet: {snap.connected_clients} · "
            f"Gönderilen Kare: {snap.frames_sent} · Mod: {MODE_LABELS.get(snap.mode, snap.mode)}"
        )
        self.root.after(1000, self._schedule_live_refresh)

    def _on_monitor_selected(self, _event: object = None) -> None:
        label = self.monitor_var.get()
        idx = self._monitor_map.get(label)
        if idx is not None:
            self._select_monitor_by_index(idx)

    def _on_options_changed(self) -> None:
        self.service.update_preferences(
            mode=self.mode_var.get(),
            touch_enabled=self.touch_var.get(),
        )

    def _on_extend_clicked(self) -> None:
        def _worker() -> None:
            ok = self.service.extend_displays_on_windows()
            msg = "Windows 'Masaüstünü Uzat' komutu uygulandı." if ok else "DisplaySwitch çalıştırılamadı."
            self.root.after(400, lambda: (self.status_var.set(msg), self.refresh_topology()))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_install_vdd_clicked(self) -> None:
        self.status_var.set("3. Sanal Ekran (VDD) kuruluyor (Yönetici iznini onaylayın)...")

        def _worker() -> None:
            ok = self.service.install_virtual_display()
            msg = "3. Sanal Ekran kuruldu ve uzatıldı!" if ok else "3. Sanal Ekran kurulumu tamamlanamadı."
            self.root.after(1000, lambda: (self.status_var.set(msg), self.refresh_topology()))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_setup_tunnel_clicked(self) -> None:
        self.adb_status_var.set("USB ADB cihazı ve tünel kontrol ediliyor...")

        def _worker() -> None:
            res = self.service.setup_usb_tunnel()
            self.root.after(0, lambda: self.adb_status_var.set(res.message))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_toggle_server_clicked(self) -> None:
        if self.service.is_running:
            self.service.stop_streaming()
            self.start_btn.configure(text="2) Yayını Başlat (127.0.0.1:8765)", bg="#38BDF8")
            self.status_var.set("Yayın durduruldu.")
            return

        self.status_var.set("Yayın sunucusu başlatılıyor...")

        def _worker() -> None:
            try:
                tunnel_res = self.service.setup_usb_tunnel()
                url = self.service.start_streaming()
                if tunnel_res.success:
                    self.service.open_on_tablet(serial=tunnel_res.device_serial)
                msg = f"Yayın Aktif! Tablette otomatik açıldı: {url}"
                self.root.after(
                    0,
                    lambda: (
                        self.adb_status_var.set(tunnel_res.message),
                        self.start_btn.configure(text="Yayını Durdur", bg="#FBBF24"),
                        self.status_var.set(msg),
                    ),
                )
            except RuntimeError as exc:
                err_msg = str(exc)
                self.root.after(0, lambda: self.status_var.set(err_msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_close(self) -> None:
        if self.service.is_running:
            self.service.stop_streaming()
        self.service.remove_usb_tunnel()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
