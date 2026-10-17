# Sistem Mimarisi (Architecture)

Bu sayfa [[index]] kapsamında P029'un 3 ekranlı topolojisini, katmanlı yazılım mimarisini ve iletişim protokolünü açıklar. Alınan kararların gerekçeleri için [[decisions]], doğrulama yapısı için [[testing]] sayfasına bakın.

## 1. 3 Ekranlı Çalışma Topolojisi
1. **1. Ekran (Ana Ekran):** Harici Monitör.
2. **2. Ekran (İkincil Ekran):** Windows Laptopun dahili ekranı.
3. **3. Ekran (Tablet Ekranı):** Windows üzerinde genişletilmiş (Extend) 3. masaüstü alanı (Sanal Ekran Sürücüsü / VDD ile oluşturulur) yakalanarak USB kablosu (`adb reverse`) üzerinden Android tablete gerçek zamanlı aktarılır.

## 2. Katmanlı Mimari ve Bağımlılık Yönü
Kod tabanı [[rules]] uyarınca sıkı bir şekilde 3 katmana ayrılmıştır (`test_layering` ile denetlenir):

- **`src/core/` (Alt Katman):**
  - `logging_config.py`: `RotatingFileHandler` (1 MB × 3) ve yakalanmayan istisna kancaları (`sys.excepthook`, `threading.excepthook`).
  - `app_settings.py`: Kullanıcı tercihlerinin (seçili ekran indeksi, port, JPEG kalitesi, FPS hedefi, dokunmatik durumu) UTF-8 JSON olarak saklanması.
  - `display_manager.py`: Windows üzerindeki tüm ekranların (1, 2, 3) koordinat ve boyutlarının tespiti.
  - `adb_manager.py`: USB ile bağlı Android cihazın doğrulanması ve `adb reverse tcp:8765 tcp:8765` tünelinin yönetimi.
  - `screen_capture.py`: Seçili ekranın yakalanması, kare farkı (delta) tespiti ve JPEG sıkıştırması.
  - `input_injector.py`: Normalize edilmiş `(x, y)` dokunmatik olaylarının 3. ekranın sanal masaüstü koordinatlarına Win32 `SendInput` ile enjekte edilmesi.
- **`src/services/` (Orta Katman):**
  - `stream_server.py`: `127.0.0.1` üzerinde çalışan Binary WebSocket akış ve dokunmatik alıcı sunucusu.
  - `project_service.py`: Tüm alt servisleri tek bir cephede (Facade) birleştiren ana servis.
- **`src/ui/` (Üst Katman):**
  - `client_assets/`: Android tablette tam ekran çalışan HTML5 Canvas + Pointer Events istemcisi.
  - `controller_app.py`: Windows tarafında ekran seçimi, tünel durumu ve başlat/durdur kontrol arayüzü.

## 3. Yayın Hattı (Pipeline) ve Güvenlik Sınırı
- **Aşamalar:** `ScreenCapturer.acquire` (yakalama thread'i: `mss` BGRA → `RawFrame`, imleç konumu, satır tabanlı BLAKE2b delta kararı) → `ScreenCapturer.encode` (kodlama thread'i: `BGRX`→JPEG, imleç çizimi, ölçekleme) → `StreamServer._send_frame` (event loop). N. kare kodlanıp gönderilirken N+1. kare yakalanır; hedef FPS aralığı `target_fps` ile korunur ([[decisions]] Karar 5).
- **Ölçüm:** `/status` uç noktası `grab_ms`, `encode_ms`, `send_ms` (hareketli ortalama) ve `last_fps` döndürür; tablet HUD'ı alınan FPS, RTT, kare çözme süresi ve atılan kare sayısını gösterir.
- **Otomatik kip:** `ScreenCapturer.acquire(adaptive=True)` her imza değişiminde hareket karesi (küçük, hızlı) üretir; ekran `SETTLE_SEC` değişmeyince tek `sharp` kare (tam çözünürlük, 4:4:4, `SHARP_JPEG_QUALITY`) üretir ve durağanken başka kare göndermez. Değişim olmadan 1 sn sonra yoklama `IDLE_POLL_FPS` (15) hızına iner ([[decisions]] Karar 6).
- **İstemci:** yalnızca en son kare çözülür (eski kareler atılır); `4001` kapanış kodu "başka oturum açıldı" demektir ve yeniden bağlanma yapılmaz. Canvas sabit boyutludur (ekranın doğal çözünürlüğü); küçük hareket kareleri ve tam boyutlu keskin kareler aynı yüzeye ölçeklenerek çizilir.
- **Güvenlik:** `loopback_guard_middleware` `Host` ve `Origin` başlıklarını doğrular (DNS rebinding ve tarayıcıdan çapraz kaynak erişimi → 403). Mod ön ayarları (`MODE_PRESETS`) `app_settings.py` içinde tek kaynaktır.
