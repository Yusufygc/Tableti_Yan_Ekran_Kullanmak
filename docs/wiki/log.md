# Kronolojik İşlem Kayıt Defteri (Log)

Bu sayfa [[index]] kapsamında projede yapılan tüm önemli değişiklikleri en yeni kayıt en üstte olacak şekilde listeler. Kurallar için [[rules]] sayfasına bakın.

## [2026-10-18] INGEST | İlk Release v0.1.0 Yayınlandı
- `main` `feb2be1`'e itildi (CI yeşil); yayınlanmamış `v0.1.0` etiketi (eski `7ee586d`'den) `feb2be1`'e taşınıp zorla itildi (Release yoktu, kimse tüketmemişti). Release iş akışı geçti: etiket/sürüm denetimi, ruff, pytest, Inno, **exe özet kapısı** ("Kararlı exe özeti onaylananla aynı: `ea66a397…2fe3`"), `gh release create`.
- Çıktı: `TabScreenUSB-Setup-0.1.0.exe` (46,9 MB, digest `43b7849f…950f`) ve `.sha256`; ön sürüm/taslak değil. Güncelleme sistemi yayını `releases/latest` üzerinden görür ([[guncelleme-sistemi]]).
- Hâlâ doğrulanmadı: indirilen kurulum dosyasının SAC'lı makinede açılması; `0.1.0 → 0.1.1` uygulama içi güncelleme (ikinci bir sürüm gerekir). [[surum-yayinlama]], [[exe-dagitim-rehberi]], [[roadmap]] güncellendi.

## [2026-10-18] UPDATE | Proje Lisans Dosyası Kaldırıldı ve İkondaki "3" Rozeti Çıkarıldı
- Kullanıcı isteğiyle `LICENSE` (MIT) silindi; `LicenseFile` (Inno), `--add-data LICENSE` (PyInstaller) ve `plan.md`/[[roadmap]] referansları temizlendi. Projenin kendi lisansı yoktur. Üçüncü taraf lisans metinleri (`third_party/vdd/LICENSE-*.txt`, adb `NOTICE.txt`) yeniden dağıtım gereği olduğundan **kalır**.
- İkondan amber "3" rozeti kaldırıldı (`packaging/icons/make_icons.py`); simgeler yeniden üretildi. İkon exe'ye gömüldüğünden exe özeti değişti: onaylı özet temiz ortamda `ea66a397…2fe3` olarak güncellendi, exe ve kurulum dosyası (46,4 MB) bu makinede denendi (sessiz kurulum + kaldırıcı başarılı). Önceki `97e16ac4…` kaydı tarihçe olarak kalır.

## [2026-10-17] REVIEW | İlk Release Denemesi: CI Exe Özeti Kapıda Durdu; Neden: Python Ortam Farkı
- `main` `7ee586d`'ye ilerletildi ve itildi (CI yeşil, 95 test); `v0.1.0` etiketi itildi. Release iş akışı lint/test/Inno adımlarını geçti, `Kurulum dosyasını derle` adımında kapı yayını durdurdu (Release oluşmadı): CI `97e16ac4…1823` ≠ onaylı `82d57543…f44b`.
- Ayrıştırma: temiz venv (dev+build) ve yalnızca-build venv, hem `git archive` hem çalışma ağacıyla CI ile aynı `97e16ac4…`; ana geliştirme venv'i her zaman `82d57543…`. Fark: ana venv'de ek paketler (pip-audit zinciri) ve farklı geçişli sürümler (`multidict` 6.9.1 / 7.1.0). Dosya, satır sonu ve kök klasörden kaynaklanmıyor.
- Çözüm: `requirements-lock.txt` (geçişli bağımlılık sabitleri), `release.yml` `-c requirements-lock.txt`, onaylı özet `97e16ac4…` olarak güncellendi; bu exe ve kurulum dosyası bu makinede denendi (açıldı, sessiz kurulum + kaldırıcı başarılı, 46,5 MB). `.venv-build/` ignore'a eklendi; test sayısı 96. [[exe-dagitim-rehberi]], [[surum-yayinlama]] güncellendi.
- Hâlâ doğrulanmadı: SAC'lı makinede açılış (bu makinede SAC kapalı), gerçek Release ile uçtan uca güncelleme.

## [2026-10-17] INGEST | Exe Dağıtımı, Sürüm Yayını ve Uygulama İçi Güncelleme Sistemi (Prod Hazırlığı Rehberlerine Göre)
- Kaynaklar: `D002-HazirPromptlar/Prod hazırlığı/` altındaki üç rehber (exe dağıtımı, güncelleme sistemi, sürüm yayınlama). Bu projeye uyarlandı: PySide6/QML yığını, `TabScreenUSB` adı, `Yusufygc/Tableti_Yan_Ekran_Kullanmak` deposu. Yeni sayfalar: [[exe-dagitim-rehberi]], [[surum-yayinlama]], [[guncelleme-sistemi]]; [[decisions]] Karar 8, [[roadmap]] Aşama 5.
- Simgeler: `packaging/icons/make_icons.py` ile 16-512 px PNG (10 boyut) ve 7 çerçeveli `app.ico`; tasarım: tablet + dokunma dalgası + amber "3" rozeti; tablet web sekmesi için `icon-192.png` ve `/icon-192.png` rotası.
- Kararlı exe: `packaging/launcher.py`, `launcher_version_info.txt`, `build_exe.py` (özet kapısı, `packaging/launcher.sha256` = `82d57543…f44b`). Ölçüm: yeniden derleme, farklı kök ve `__version__ = 9.9.9` ile aynı özet; exe 8 sn çalıştı, pencere başlığı doğru (QML paketlenmişte yüklendi).
- Kurulum: `packaging/TabScreenUSB.iss`, `build_installer.py`, `build_verify.py` (gerçek kaydı yedekleyen sessiz kurulum + kaldırıcı denemesi). Tam akış başarılı: `TabScreenUSB-Setup-0.1.0.exe` 46,7 MB.
- Yol çözümleme: `src/core/app_paths.py`; `src/app.py` (`run()`), `main.py` ince sarmalayıcı; adb `third_party` içinden önce aranır; `3_ekran_*.bat` `third_party\vdd` yolunu kullanır; `third_party/` (adb + VDD + lisanslar, ≈11 MB) repoya eklendi, `THIRD_PARTY_NOTICES.md` genişletildi.
- Güncelleme: `update_service` (güvenlik kuralları), `ProjectService` cephesi, `UpdateViewModel`, `UpdateDialog.qml`, panelde "4. Güncellemeler" kartı; açılış denetimi `ControllerWindow.run()` içinde 3 sn sonra.
- Yayın: `tools/release.py` (itmez), `.github/workflows/release.yml`; `.gitignore` `tools/` yerine yerel kopyaları dışlar; `requirements-build.txt` PyInstaller 6.22.3.
- Testler 47 → 95 (`test_release_packaging`, `test_build_verify`, `test_update_service`, `test_update_viewmodel`). **Doğrulanmadı:** SAC'lı makinede açılış (bu makinede SAC kapalı), CI'da derlenen exe özetinin yerelle eşitliği, gerçek Release ile uçtan uca güncelleme (henüz etiket itilmedi).

## [2026-10-17] UPDATE | Kapsamlı README, Sıfırdan PySide6/QML Masaüstü Arayüzü, Çoklu Monitör Merkezleme ve Bağımlılık Temizliği
- `README.md` projenin uçtan uca çalışma mantığını (3 ekranlı sanal masaüstü, USB ADB reverse tüneli, 3 aşamalı `acquire -> encode -> send` boru hattı, `auto` kip ve `DECODE_DEPTH=4` paralel çözme, `MOUSEEVENTF_VIRTUALDESK` dokunmatik enjeksiyonu ve güvenlik mimarisi) anlatacak şekilde baştan yazıldı.
- Eski Tkinter arayüzü tamamen kaldırılarak `src/ui/controller_app.py` (`ControllerViewModel`, `_BackgroundTaskWorker(QThread)`) ve `src/ui/qml/Main.qml` ile sıfırdan **PySide6 + QML** arayüzü kuruldu; `THIRD_PARTY_NOTICES.md` ve `test_no_legacy_tkinter_imports` AST bekçisi eklendi.
- `requirements.txt` içinde tam `PySide6` meta-paketi (kullanılmayan `WebEngine`/`Pdf`/`Addons` ~250 MB) yerine yalnızca QML/Quick için gerekli olan hafif `PySide6-Essentials==6.12.0` sabitlendi; `venv` içinden gereksiz eklenti paketleri temizlendi ([[decisions]] Karar 7).
- Çoklu monitörlü (negatif koordinatlı sol monitör + ana ekran + sanal 3. ekran) kurulumda pencerenin ekran dışında veya sanal ekranda açılması sorunu `_center_and_show_on_primary_screen` ile giderildi (`app.primaryScreen().availableGeometry()` içine sığdırılıp tam ortalanarak açılır).
- Monitör boyutuna göre QML kartlarının bozulması/sündürülmesi sorunu giderildi: `ScrollView` + `anchors.fill: parent` döngüsel yükseklik bağlaması kaldırılıp doğrudan `Flickable` + üstten bağlı `ColumnLayout` (`maxWidth: 1020px`, ortalanmış) ve `isCompact` (`width < 740`) `GridLayout` (`columns: isCompact ? 1 : 3`) kırılımı eklendi.
- `tests/conftest.py` (`QT_QPA_PLATFORM=offscreen`, `QT_QPA_FONTDIR`) ve `tests/unit/test_ui_contrast.py` (`QAccessibleInterface`, ana ekran merkezleme, `640x540`/`860x660`/`1600x1000` esnek yerleşim ve ViewModel köprüsü) güncellendi.

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
