# Geliştirme Yol Haritası (Roadmap)

Bu sayfa [[index]] kapsamında projenin aşamalarını takip eder. Mimari detaylar için [[architecture]], geçmiş kayıtlar için [[log]] sayfasına bakın.

## Aşama 1: İlk Gün Altyapısı ve LLM Wiki Kurulumu (Tamamlandı)
- [x] `plan.md` oluşturulması ([[decisions]]).
- [x] `CLAUDE.md` ve `docs/wiki/` ([[index]], [[rules]], [[decisions]], [[architecture]], [[testing]], [[roadmap]], [[log]]) kurulumu.
- [x] Depo hijyeni (`.gitattributes`, `.editorconfig`, `.gitignore`, `LICENSE`, sabit `requirements*.txt`, `ruff.toml`, `pytest.ini`, `.github/workflows/ci.yml`).
- [x] Çekirdek loglama (`logging_config.py`), ayar yalıtımı (`app_settings.py`) ve bekçi testlerin (`test_wiki`, `test_layering`, `test_code_hygiene`, `test_logging_config`) doğrulanması.

## Aşama 2: Çekirdek Modüller (Ekran Yakalama, Dokunmatik Enjeksiyon ve ADB Tüneli) (Tamamlandı)
- [x] `src/core/display_manager.py`: 1., 2. ve 3. ekranların (monitör + laptop + sanal ekran) geometri ve durum tespiti.
- [x] `src/core/screen_capture.py`: `mss` + `Pillow` ile adaptif kare farkı (delta) destekli ekran yakalama.
- [x] `src/core/input_injector.py`: Win32 `SendInput` ile 3. ekran koordinatlarına dokunma, sürükleme, sağ tık ve kaydırma enjeksiyonu.
- [x] `src/core/adb_manager.py`: USB üzerinden `adb reverse tcp:8765 tcp:8765` tünel yönetimi.
- [x] Çekirdek modüllerin birim testleri (`tests/unit/test_core_modules.py`).

## Aşama 3: Yerel WebSocket Yayın Sunucusu ve Tablet Web İstemcisi (Tamamlandı)
- [x] `src/services/stream_server.py` ve `src/services/project_service.py`: `127.0.0.1` Binary WebSocket akış ve dokunmatik sunucusu.
- [x] `src/ui/client_assets/index.html`: Tam ekran HTML5 Canvas, WakeLock, dokunmatik algılama ve Okuma/Video modu arayüzü.
- [x] Sunucu ve protokol birim testleri (`tests/unit/test_stream_service.py`).

## Aşama 4: Windows Kontrol Arayüzü ve Canlı Cihaz Doğrulaması (Tamamlandı)
- [x] `src/ui/controller_app.py`, `main.py` ve `baslat.bat`: Ekran seçimi, ADB tünel durumu ve başlat/durdur kontrol paneli.
- [x] `tests/unit/test_ui_contrast.py`: WCAG AA (>= 4.5:1) kontrast, çevrimdışı HTML ve erişilebilirlik bekçi testleri.
- [x] 3. Sanal Ekran (VDD) kurulum/kontrol yardımcısı (`DisplaySwitch.exe /extend` + `README.md` rehberi).
