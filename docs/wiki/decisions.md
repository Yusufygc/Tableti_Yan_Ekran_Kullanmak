# Mimari Kararlar (Decisions)

Bu sayfa projede alınan teknik kararları, gerekçelerini ve reddedilen seçenekleri kayıt altına alır. Genel yapı için [[index]] ve [[architecture]], tarihçe için [[log]] sayfasına bakın.

## Karar 1: Üçüncü Taraf Hazır Yazılımlar (Spacedesk / Scrcpy) Yerine Özel Yerel Yazılım
- **Seçilen:** Kendi özel, %100 yerel (`127.0.0.1`) açık kaynaklı Windows Host + Android İstemci yazılımımız.
- **Neden:** Üçüncü taraf kapalı kaynaklı ekran paylaşım yazılımlarının (örn. Spacedesk) ekran verilerini kaydetme/telemetri riski taşıması.
- **Reddedilen Seçenek:** Kapalı kaynaklı ticari ekran aktarım sürücüleri.

## Karar 2: İletişim Katmanı Olarak USB + ADB Reverse TCP Tüneli
- **Seçilen:** USB kablosu üzerinden `adb reverse tcp:8765 tcp:8765` ile `127.0.0.1` loopback tüneli.
- **Neden:** Wi-Fi ağına çıkmadan kablo hızında düşük gecikme sağlar, yerel ağdaki diğer cihazların ekran akışına erişmesini fiziksel ve yazılımsal olarak engeller, özel USB sürücüsü imzalama maliyetini ortadan kaldırır.
- **Reddedilen Seçenek:** Wi-Fi (`0.0.0.0`) üzerinden açık port yayını (hem gecikme/parazit hem de yerel ağ gizlilik riski nedeniyle reddedildi).

## Karar 3: Seçenek 1 Mimarisi (Python Host + Binary WebSocket + Tam Ekran HTML5 Canvas/Touch İstemcisi)
- **Seçilen:** Windows tarafında Python (`mss` + `Pillow` + `aiohttp` + Win32 `SendInput`), Android tablet tarafında USB tünelinden beslenen sıfır kurulumlu Tam Ekran HTML5 Canvas + Pointer Events istemcisi.
- **Neden:** Yan ekran, terminal izleme, kod/doküman okuma ve video izleme senaryoları için Android Studio/SDK derleme yükü olmadan hızlı, şeffaf ve dokunmatik destekli çözüm sunar. Durağan ekranlarda kare farkı (delta) kontrolü ile CPU tüketimi sıfıra yakın tutulur.
- **Reddedilen Seçenek:** C++/Rust UMDF sıfırdan sürücü + Native Kotlin APK (ilk aşamada EV Code Signing ve ağır Android SDK bağımlılığı getirdiği için reddedildi; 3. sanal ekran için açık kaynaklı imzalı VDD kullanılmasına karar verildi).

## Karar 5: İki Aşamalı Thread Hattı, Host/Origin Bekçisi ve Tek İstemci
- **Seçilen:** `StreamServer` yakalamayı (GDI, thread'e bağlı `mss`) ve JPEG kodlamayı iki ayrı tek-işçili `ThreadPoolExecutor`'da çalıştırır; event loop yalnızca WebSocket G/Ç ve dokunmatik mesajlarını işler. Her HTTP/WS isteğinde `Host` ve (varsa) `Origin` başlığı loopback olmalıdır. Aynı anda tek tablet istemcisi tutulur.
- **Neden:** Ölçüm (1920x1200): yakalama ≈20 ms, kodlama 7-10 ms; seri hat ≈28 FPS tavanı ve event loop bloke olduğu için 40-70 ms ping gecikmesi veriyordu. Tarayıcılar `ws://127.0.0.1` adresine same-origin kısıtı olmadan bağlanabildiğinden, kötü niyetli bir web sayfası ekran akışını okuyup fare enjekte edebilirdi. Çift istemci her kareyi iki kez gönderiyordu.
- **Reddedilen Seçenek:** DXGI Desktop Duplication (`dxcam`) — yakalamayı ≈5 ms'ye indirebilir ama `numpy` + yeni sürücü bağımlılığı getirir; yalnızca ölçüm yetersiz kalırsa değerlendirilecek. Oturum token'ı — Origin/Host kontrolü tarayıcı tabanlı saldırıyı kapattığı ve yerel süreçler zaten `SendInput` kullanabildiği için gereksiz bulundu (YAGNI).
- **Tablet çözme tavanı (TB330FU ölçümü):** JPEG çözme 1920x1200'de ≈47-51 ms (≈20 FPS), 1280x800'de ≈30 ms (≈30 FPS). Bu yüzden video modu 1280x800'e küçültülür (`MODE_PRESETS`), okuma modu keskinlik için tam çözünürlükte kalır. 20 FPS üstünde tam çözünürlük için seçenekler: H.264 + WebCodecs `VideoDecoder` (donanım çözme; PC tarafında kodlayıcı bağımlılığı gerekir, XL iş) veya yalnızca değişen bölgeleri gönderen dirty-rect protokolü (bayat kare atma ile çakışır, yeniden tasarım gerekir).
- İlgili: [[architecture]], [[log]].

## Karar 6: Otomatik Kip — Tam Çözünürlük + Durulunca Tek Yüksek Kalite Kare (Paralel Çözme ile)
- **Güncelleme (aynı gün, ölçümle):** İlk sürüm hareket varken 1280x800 gönderiyordu; video izlerken tüm ekran bulanık kalıyor ve kalite dalgalanıyordu. Tablet deneyi darboğazın tabletin gücü değil, istemcinin kareleri tek tek `await` etmesi olduğunu gösterdi: 4 karenin paralel çözülmesiyle 1920x1200 4:4:4 q88 19 → 44 FPS. Bu yüzden **tüm kipler tam çözünürlük** gönderir; küçültülmüş kademe kalktı. Kalan sınır USB 2.0 bant genişliği (≈16-26 MB/sn) olduğundan sunucu kalite denetimi (`next_quality_penalty`) ile atılan kare oranı yüksekse JPEG kalitesini en fazla 15 birim düşürür.
- **Seçilen:** Varsayılan kip `auto`: tam çözünürlük 4:4:4 q85 (40 FPS hedefi); ekran 0,2 sn değişmeyince tek q92 kare. Durağan ekranda sıfır trafik. Okuma q92/30 FPS, Video 4:2:0 q70/45 FPS.
- **Neden:** Tablet (TB330FU) 1920x1200 JPEG'i en fazla ≈20 FPS çözer; sürekli tam çözünürlük akıcılığı, sürekli küçültme keskinliği öldürür. İnsan gözü hareket sırasında ayrıntıyı seçemez, durulunca keskinlik ister; iki kademe ikisini birlikte verir.
- **Reddedilen Seçenekler:** (0) Hareket sırasında küçültme (ilk sürüm) — paralel çözme ile gereksizleşti. (1) Video kipini 1440x900 q85'e çıkarmak — ≈28 FPS tavanı ve hâlâ bulanık. (2) Dirty-rect/yama protokolü (bant genişliği tavanına çarpılırsa yeniden değerlendirilebilir: bant genişliği değişen alanla orantılı düşer) — "yalnızca en son kareyi çöz" bayat kare atma ile çakışır (atılan yama içeriği bozar), yeniden tasarım gerekir. (3) H.264 + WebCodecs donanım çözme — yalnızca sürekli tam çözünürlük video gerekirse (PC tarafı kodlayıcı bağımlılığı, XL).
- İlgili: [[architecture]], [[log]].

## Karar 4: İlk Gün Altyapı ve Bekçi Testleri
- **Seçilen:** `ruff` (`E9`, `F`), `pytest` (`EncodingWarning` hata modunda), kullanıcı verisi yalıtımı (`conftest.py`) ve AST tabanlı bekçi testler ([[testing]]).
- **Neden:** Geç eklenen lint, kodlama ve katman kurallarının sonradan toplu temizlik ve veri bozulması maliyeti yaratmasını ilk günden önlemek ([[rules]]).
