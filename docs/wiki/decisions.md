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

## Karar 4: İlk Gün Altyapı ve Bekçi Testleri
- **Seçilen:** `ruff` (`E9`, `F`), `pytest` (`EncodingWarning` hata modunda), kullanıcı verisi yalıtımı (`conftest.py`) ve AST tabanlı bekçi testler ([[testing]]).
- **Neden:** Geç eklenen lint, kodlama ve katman kurallarının sonradan toplu temizlik ve veri bozulması maliyeti yaratmasını ilk günden önlemek ([[rules]]).
