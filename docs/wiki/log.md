# Kronolojik İşlem Kayıt Defteri (Log)

Bu sayfa [[index]] kapsamında projede yapılan tüm önemli değişiklikleri en yeni kayıt en üstte olacak şekilde listeler. Kurallar için [[rules]] sayfasına bakın.

## [2026-10-17] UPDATE | Konsolsuz Başlatma (pythonw) ve Responsive/Dinamik Arayüz Yenilemesi
- `baslat.bat` içinde `start "" ... pythonw.exe` ve `adb_manager.py` içinde `CREATE_NO_WINDOW` kullanılarak arka planda siyah `cmd.exe` penceresinin açık kalması engellendi.
- `src/ui/controller_app.py` sabit `680x560` boyut yerine `grid` tabanlı esnek (responsive) yerleşim, tıklanabilir görsel ekran haritası (`[1] [2] [3]`), `<Configure>` ile dinamik metin kaydırma (`wraplength`) ve `winfo_reqwidth/reqheight` tabanlı otomatik başlangıç boyutlandırmasıyla yenilendi.

## [2026-10-17] UPDATE | 3. Ekranda Fare İmleci Görünürlüğü ve Hareket Algılama Eklendi
- `mss.grab()` donanımsal fare imlecini yakalamadığı için 3. ekrana geçen imlecin tablette görünmemesi sorunu tespit edildi.
- `src/core/screen_capture.py` içine `get_windows_cursor_pos`, `relative_cursor_in_monitor` ve `draw_cursor_pointer` eklendi; imleç 3. ekran (`1920, 0`) sınırları içindeyken hem kare farkı (delta) imzasına dahil ediliyor hem de kare üzerine yüksek görünürlüklü Windows imleci çiziliyor.

## [2026-10-17] UPDATE | Windows .bat Byte-Offset Kayması Düzeltildi ve Bekçi Test Eklendi
- `3_ekran_kur.bat` çalıştırıldığında `cmd.exe` içinde `chcp 65001` + LF + çok baytlı UTF-8 karakterler yüzünden oluşan byte-offset kayması (`echo` -> `ho`, `-NoProfile` -> `oProfile`) tespit edildi.
- Tüm `.bat` dosyaları (`3_ekran_kur.bat`, `3_ekran_kaldir.bat`, `baslat.bat`) saf ASCII ve `CRLF` (`\r\n`) olarak düzeltildi; `tests/unit/test_code_hygiene.py` içine `test_bat_files_use_crlf_and_pure_ascii` bekçi testi ve [[rules]] kaydı eklendi.

## [2026-10-17] UPDATE | Resmi ADB ve Sanal 3. Ekran (VDD) Araçları Kuruldu
- `tools/platform-tools/adb.exe` (Google Android Platform Tools v37.0.1) ve `tools/vdd/` (Virtual-Display-Driver + `nefcon`) yerel olarak indirildi (`.gitignore` ile hariç tutuldu).
- `3_ekran_kur.bat`, `3_ekran_kaldir.bat` ve `ControllerWindow` içine tek tıkla **"3. Sanal Ekranı Kur"** düğmesi eklendi.

## [2026-10-17] UPDATE | Aşama 4 Windows Kontrol Arayüzü, Başlatıcı ve Kontrast Testleri Eklendi
- `src/ui/controller_app.py` (WCAG AA >= 4.5:1 koyu tema, arka plan iş parçacıklı Tkinter kontrol paneli), `main.py` (GUI + `--cli` desteği), `baslat.bat` ve `README.md` (gizlilik ve kurulum rehberi) oluşturuldu.
- `tests/unit/test_ui_contrast.py` ve `test_ui_does_not_import_core_directly` eklendi; [[roadmap]] tamamlandı.

## [2026-10-17] UPDATE | Aşama 3 WebSocket Yayın Sunucusu ve Tablet İstemcisi Eklendi
- `src/services/stream_server.py` (loopback `127.0.0.1` zorunluluğu, Binary JPEG WebSocket yayını, dokunmatik/ping/config işleme) ve `src/services/project_service.py` (Tek Cephe / Facade servisi) tamamlandı.
- `src/ui/client_assets/index.html` ile tam ekran HTML5 Canvas, WakeLock, tek/iki parmak dokunmatik + uzun basma sağ tık + Okuma/Video modu HUD istemcisi oluşturuldu.
- `tests/unit/test_stream_service.py` eklendi ve [[roadmap]] güncellendi.

## [2026-10-17] UPDATE | Aşama 2 Çekirdek Modüller ve Birim Testleri Eklendi
- `src/core/display_manager.py` (3 ekranlı topoloji tespiti ve `DisplaySwitch.exe /extend` yardımcısı), `src/core/screen_capture.py` (sparse BLAKE2b delta kontrolü ve Okuma/Video JPEG sıkıştırma), `src/core/input_injector.py` (3. ekran `MOUSEEVENTF_VIRTUALDESK` dokunmatik enjeksiyonu) ve `src/core/adb_manager.py` (güvenli `adb.exe` tespiti ve `adb reverse` USB tüneli) kodlandı.
- `tests/unit/test_core_modules.py` ile olumlu ve olumsuz birim testleri eklendi; [[roadmap]] güncellendi.

## [2026-10-17] INGEST | İlk Gün Altyapısı, Plan ve LLM Wiki Kurulumu
- Kullanıcının 3 ekranlı (1: Ana Monitör, 2: Laptop, 3: USB Android Tablet) ve dokunmatik destekli özel yazılım talebi doğrultusunda `plan.md` oluşturuldu.
- `proje-altyapi-rehberi.md` ve `LLM-wiki.md` standartlarına uygun olarak `CLAUDE.md` ve `docs/wiki/` bilgi tabanı ([[index]], [[rules]], [[decisions]], [[architecture]], [[testing]], [[roadmap]], [[log]]) kuruldu.
- İlk gün depo hijyeni (`.gitattributes`, `.editorconfig`, `.gitignore`, `LICENSE`), sabit bağımlılık dosyaları, `ruff.toml`, `pytest.ini`, CI iş akışı, loglama/ayar çekirdeği ve AST bekçi testleri eklendi.
