# Kronolojik İşlem Kayıt Defteri (Log)

Bu sayfa [[index]] kapsamında projede yapılan tüm önemli değişiklikleri en yeni kayıt en üstte olacak şekilde listeler. Kurallar için [[rules]] sayfasına bakın.

## [2026-10-17] REVIEW | Kalite Dalgalanması: Paralel Çözme, Tam Çözünürlük ve Bağlantıya Duyarlı Kalite (`perf/otomatik-kalite-modu`)
- Belirti (YouTube videosu oynarken): Otomatik kip tüm ekranı sürekli 1280px'te tutuyor, durağan sayfa bulanık; kısa duraklarda keskin kareye, sonra yumuşağa dönerek kalite dalgalanıyor, FPS 20-30 arasında oynuyor.
- Kök neden bulgusu (tablet deneyi): istemci kareleri tek tek `await` ettiği için tabletin 8 çekirdeği boştaydı. `createImageBitmap` boru hattı derinliği 1 → 4 olunca 1920x1200 4:4:4 q88: 19 → 44 FPS, 4:2:0 q72: 17 → 48 FPS, 1280x800: 30 → 83 FPS. Derinlik 2-6 arası farklar küçük (4 seçildi).
- Değişiklikler: `index.html` 4 kare paralel çözer, çizim sırayla yapılır, çözmeye başlanmamış kareler arasında yalnızca en yenisi tutulur (HUD `gecikme` artık kuyruk + çözme gecikmesi). `MODE_PRESETS` hepsi tam çözünürlük: Otomatik 4:4:4 q85/40 FPS + durulunca q92, Okuma q92/30 FPS, Video 4:2:0 q70/45 FPS (`CHROMA_444_MODES`). Küçültülmüş hareket kademesi kalktı (ayar olarak durur).
- Sunucu: gönderim kodlamadan ayrıldı (`_sender_loop`/`_publish_frame`, en yeni kare kazanır); bağlantıya duyarlı kalite denetimi (`next_quality_penalty`: atılan kare oranı >%15 ise kalite 5 birim düşer, en fazla 15; kayıpsızken saniyede 1 birim toparlanır; taban 50). `/status`: `frames_dropped`, `quality_penalty`. Soket `SO_SNDBUF` büyütme denendi, fark etmedi ve gecikme riski taşıdığı için geri alındı.
- Ölçüm (gerçek sunucu + sentetik ağır içerik [647-829 KB kareler], TB330FU): sınır USB ≈16-26 MB/sn (gönderim sırasında), seri kodla+gönder döngüsünde 24-26 FPS → kalite denetimiyle Otomatik 27-31, Okuma 27-28, Video 35-37 FPS; hepsi 1920px, dalgalanma yok. Gerçek ekranlar daha hafif (≈300 KB) olduğundan daha yüksek FPS beklenir; tavan USB 2.0.
- Kritik: kullanıcının kayıtlı `settings.json` dosyası eski `scale_factor=0.667`, `jpeg_quality=72`, `target_fps=30` tutuyordu ve yeni ön ayarı eziyordu (HUD'da 1280px bu yüzden görülüyordu). `ProjectService.__init__` artık açılışta kayıtlı kipin ön ayarını uygular (kalite/FPS/ölçek arayüzden ayarlanamadığı için).
- Testler: 45 (kalite cezası, en yeni kare kazanır, `/status` alanları, eski kayıtlı ayarın ön ayarı ezmemesi). [[decisions]] Karar 6 güncellendi, [[architecture]] ve [[testing]] güncel.

## [2026-10-17] INGEST | Otomatik Kip: Hareket Sırasında Akıcı, Ekran Durulunca Piksel Keskin (`perf/otomatik-kalite-modu`)
- Sorun: Video kipi 1280x800 büyütülerek bulanıktı; tam çözünürlük ise tablet çözme tavanı yüzünden ≈20 FPS. Çözüm: iki kademeli akış — hareket varken 1280x800 q72 4:2:0 (≈30 FPS), ekran `SETTLE_SEC` (0,2 sn) değişmeyince tek tam çözünürlük q92 4:4:4 keskin kare.
- `screen_capture.py`: `ScreenCapturer.acquire(adaptive=True)` durum makinesi (`_decide`), `AcquiredFrame.sharp`, keskin kare `encode` içinde tam çözünürlük/4:4:4/`SHARP_JPEG_QUALITY`. `app_settings.py`: `"auto"` ön ayarı (varsayılan kip), `SETTLE_SEC`, `SHARP_JPEG_QUALITY`.
- `stream_server.py`: Otomatik kipte `adaptive` yakalama; değişim yokken (1 sn sonra) yoklama 15 FPS'e düşer (`IDLE_POLL_FPS`). `index.html`: canvas sabit (ekran doğal boyutu), küçük/büyük kareler aynı yüzeye ölçeklenerek çizilir; mod düğmesi Otomatik/Okuma/Video; HUD'da son kare genişliği (`…px`). `controller_app.py`/`main.py`: Otomatik seçeneği.
- Ölçüm (gerçek sunucu + sentetik kod/metin kaydırma, TB330FU Chrome, Chrome DevTools ile HUD okundu): Otomatik kaydırma 25-26 FPS (1280px), durunca 1920px; Okuma 19 FPS (çöz 54 ms); Video 29 FPS (çöz 27 ms). Tablet ekran görüntüsü karşılaştırması: Otomatik (durulmuş) = Okuma keskinliğinde, Video belirgin bulanık.
- Not: kayıtlı `settings.json` eski kipi (okuma/video) tutar; tablet HUD'ındaki Mod düğmesiyle Otomatik'e geçilir. Yeni testler: `tests/unit/test_adaptive_mode.py` (41 test). [[decisions]] Karar 6, [[architecture]], [[testing]] güncellendi.

## [2026-10-17] REVIEW | Tablet (TB330FU) Çözme Ölçümü ve Mod Ön Ayarları
- Kullanıcı HUD'u: 15-17 FPS, çöz 100-120 ms, atılan 10-20. Geçici ölçüm sayfaları (repo dışı) ADB üzerinden tablet Chrome'unda koşuldu (Helio G80/MT8786, Chrome 155, ekran 1920x1200 @ dpr 1.5).
- Bulgular: USB/ADB tüneli darboğaz değil (15-32 MB/s, ≥96 kare/sn). Darboğaz tablet JPEG çözmesi: 1920x1200 4:2:0 q72 ≈47 ms (≈21 FPS), 4:4:4 q88 ≈51 ms, 1440x900 ≈34 ms (27.7 FPS), 1280x800 ≈30 ms (29.6 FPS), 960x600 ≈21 ms. `bitmaprenderer`, `<img>.decode()`, WebP ve `resizeWidth` seçeneği daha hızlı değil (WebP/resize daha yavaş).
- Hata (önceki turda benim eklediğim): `createImageBitmap(blob, {colorSpaceConversion:"none", premultiplyAlpha:"none"})` çözmeyi 47 → 64 ms'ye yavaşlatıyordu; seçenekler kaldırıldı.
- `MODE_PRESETS` artık `(kalite, FPS, ölçek)`: okuma 88/30/1.0 (keskin, ≈20 FPS tavan, durağan içerik için yeterli), video 72/30/2⁄3 (1280x800, ≈30 FPS). `_scale_image` `round()` kullanır (2⁄3 ölçeğinde 799 piksel riski). Tablet çözme tavanını aşmak için daha fazlası H.264 (WebCodecs donanım çözme) gerektirir; [[decisions]] Karar 5'te alternatif olarak not edildi.

## [2026-10-17] REVIEW | Regresyon: Yayın Durdur/Başlat Sonrası Sıfır Kare (BitBlt Hatası) Düzeltildi
- Belirti: uygulamada "Gönderilen Kare: 0"; log'da `ScreenShotError ... BitBlt`. Kök neden: `mss` GDI tutamaçları oluşturan thread'e bağlıdır; yayın durdurulup başlatılınca yeni işçi thread eski tutamaçlarla `BitBlt` yapamıyordu (ayrıca sanal ekran kur/kaldır tutamaçları geçersizleştirir). Önceki FPS turunda ölçüm yalnızca tek başlatma senaryosunu kapsadığı için kaçmıştı.
- `MssRawGrabber.grab`: thread değişiminde `mss.MSS()` yeniden açılır; `ScreenShotError`'da tutamaçlar yenilenip bir kez yeniden denenir, hâlâ başarısızsa hata loglanıp yukarı iletilir.
- Doğrulama: gerçek `mss` ile 3 ardışık durdur/başlat turunda 88-90 kare/3 sn; regresyon testi `tests/unit/test_grabber_threading.py` (35 test). [[testing]] güncellendi.

## [2026-10-17] REVIEW | FPS Optimizasyonu ve Güvenlik Denetimi Bulguları Giderildi
- Denetim (V2 şablonu) 12 bulgu çıkardı; hepsi uygulandı. Ölçüm (1920x1200, loopback, gerçek `mss`): sunucu tavanı 27.9 → 38 FPS (video), ping 72 → 0.3 ms (event loop artık bloke değil); `scale_factor=0.75` 21 → 35 FPS. Tablet tarafı (TB330FU) ölçülmedi.
- `screen_capture.py`: `RawFrame` (mss BGRA doğrudan `BGRX` olarak okunur, ≈5-8 ms RGB dönüşümü kalktı), iki aşamalı `acquire` + `encode`, satır tabanlı delta imzası (her 8. satır tam genişlik; metin imleci gibi küçük değişimler artık yakalanır), tamsayı ölçeklerde `Image.reduce`, `CaptureFrame.grab_ms/encode_ms`.
- `stream_server.py`: yakalama ve kodlama iki ayrı işçi thread'de (N. kare kodlanırken N+1. yakalanır), Host/Origin bekçisi (`loopback_guard_middleware`, yabancı Origin/Host → 403), tek istemci politikası (yeni bağlantı eskiyi `4001` ile kapatır), bozuk mesaj doğrulaması, topoloji önbelleği (1 sn), `/status` içinde `grab_ms/encode_ms/send_ms`.
- `index.html`: `backdrop-filter` kaldırıldı, yalnızca en son kare çözülür (backpressure), HUD'a çözme süresi ve atılan kare sayısı eklendi, `4001` kodunda yeniden bağlanma yapılmaz.
- `app_settings.py`: `MODE_PRESETS` tek kaynak (video hedefi 45 → 60 FPS); `input_injector.py`: `TOUCH_ACTIONS` tablosu (if/elif zinciri kalktı); `controller_app.py`: `_build_ui` 312 satırdan 4 küçük yapı metoduna bölündü (widget sayısı ve pencere boyutu değişmedi).
- Yeni testler: `test_stream_security_pipeline.py`, `test_capture_pipeline.py` (21 → 32 test). [[decisions]] Karar 5, [[architecture]] ve [[testing]] güncellendi.

## [2026-10-17] UPDATE | Bağımlılık Güvenlik Yükseltmesi (pip-audit)
- CI `pip-audit` taramasında `pillow==11.3.0` ve `aiohttp==3.12.15` sürümlerinde bildirilen güvenlik açıkları giderildi.
- `requirements.txt` içinde sürümler `mss==10.2.0`, `pillow==12.3.0` ve `aiohttp==3.14.5` olarak sabitlendi; `.github/workflows/ci.yml` içinde `pip-audit==2.10.1` sürümüne güncellendi.

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
