# P029 — Android Tablet 3. Ekran (USB Kablolu & %100 Yerel) Proje Planı

## 1. Projenin Amacı ve Kapsamı

Windows bilgisayar (1. Ekran: Harici Monitör, 2. Ekran: Laptop Ekranı) ile Android tablet arasında **USB kablosu üzerinden**, üçüncü taraf bulut/telemetri servislerine hiçbir veri göndermeden **%100 yerel (`127.0.0.1` loopback)** çalışan, dokunmatik destekli bir **3. Ekran (Genişletilmiş Masaüstü / Extended Display)** yazılımı geliştirmek.

### Kullanım Senaryoları
- **Yan Ekran & Terminal İzleme:** Log akışları, sistem monitörü, derleme çıktıları.
- **Kod & Doküman Okuma:** PDF, teknik dokümantasyon, LLM Wiki ve kod inceleme (yüksek metin keskinliği, durağan ekranda ~%0 CPU tüketimi).
- **Video İzleme:** Hareket algılandığında dinamik olarak 30–60 FPS akıcı kare hızına geçiş.
- **Dokunmatik Kontrol:** Tabletten yapılan dokunuş, sürükleme, sağ tık (uzun basma / çift dokunma) ve kaydırma (scroll) hareketlerinin Windows'ta 3. ekranın koordinatlarına aktarılması.

---

## 2. Sistem Mimarisi (Seçenek 1: Python Host + ADB USB Tüneli + Tam Ekran Web Canvas)

```mermaid
flowchart LR
    subgraph Windows["Windows Laptop (Host)"]
        Mon1["1. Ana Monitör"]
        Mon2["2. Laptop Ekranı"]
        VDD["3. Sanal Ekran (VDD / Extended)"]
        Core["src/core\n- display_manager (Ekran Tespiti)\n- screen_capture (MSS + Turbo/Pillow)\n- input_injector (Win32 SendInput)\n- adb_manager (ADB Reverse TCP)"]
        Service["src/services\n- project_service (Tek Cephe)\n- stream_server (aiohttp + Binary WS)"]
        UI["src/ui\n- Masaüstü / CLI Kontrol Arayüzü"]
        VDD --> Core
        Core --> Service
        Service --> UI
    end

    subgraph USB["USB Kablo (ADB Tüneli)"]
        Tunnel["adb reverse tcp:8765 tcp:8765\n(Yalnızca 127.0.0.1 Loopback)"]
    end

    subgraph Tablet["Android Tablet (3. Ekran İstemcisi)"]
        Client["Tam Ekran HTML5 Canvas + WebSocket\n- Binary Blob -> ImageBitmap Çizimi\n- Pointer/Touch -> Koordinat Gönderimi\n- WakeLock (Ekran Kapanmasını Önleme)"]
    end

    Service <-->|Görüntü (Binary Frame)\n+ Dokunmatik (JSON)| Tunnel
    Tunnel <--> Client
```

### Temel Güvenlik ve Gizlilik İlkeleri
1. **Sıfır Telemetri & Sıfır Dış Ağ:** Sunucu yalnızca `127.0.0.1` (localhost) üzerinde açılır; yerel Wi-Fi (`0.0.0.0`) veya internete kesinlikle açılmaz.
2. **USB ADB Reverse Tüneli:** Tablet, USB kablosu üzerinden `http://127.0.0.1:8765` adresine bağlanır. `adb.exe` yalnızca güvenli sistem yolu doğrulamasıyla çağrılır.
3. **Veri Yalıtımı:** Ayarlar ve dönen log dosyaları (`RotatingFileHandler`, 1 MB × 3) kullanıcı klasöründe tutulur; testlerde `conftest.py` ile tamamen yalıtılır.

---

## 3. Katmanlı Kod Yapısı (`proje-altyapi-rehberi.md` Uyumlu)

```text
P029-Tablet_Ekrani_Kullanimi/
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .github/workflows/ci.yml
├── CLAUDE.md
├── LICENSE
├── plan.md
├── pytest.ini
├── ruff.toml
├── requirements.txt
├── requirements-dev.txt
├── requirements-build.txt
├── docs/
│   └── wiki/
│       ├── index.md          # Tüm wiki'nin içerik haritası
│       ├── rules.md          # Çalışma, kodlama, test ve git kuralları
│       ├── decisions.md      # Mimari kararlar ve reddedilen alternatifler
│       ├── architecture.md   # Katmanlar, USB tüneli ve protokol tasarımı
│       ├── testing.md        # Test stratejisi ve bekçi (guardian) testler
│       ├── roadmap.md        # Aşamalı geliştirme yol haritası
│       └── log.md            # Kronolojik işlem kayıt defteri (en yeni üstte)
├── src/
│   ├── __init__.py
│   ├── version.py            # Sürüm tek kaynak (Single Source of Truth)
│   ├── core/                 # Alt katman (servis ve ui import ETMEZ)
│   │   ├── __init__.py
│   │   ├── logging_config.py # RotatingFileHandler + excepthook
│   │   ├── app_settings.py   # UTF-8 JSON ayar yönetimi
│   │   ├── display_manager.py# Çoklu ekran (1, 2, 3) geometri ve sanal ekran tespiti
│   │   ├── adb_manager.py    # ADB USB cihaz kontrolü ve tcp reverse tüneli
│   │   ├── screen_capture.py # MSS ekran yakalama + Adaptive Delta JPEG kodlama
│   │   └── input_injector.py # Win32 SendInput ile 3. ekrana dokunmatik/fare enjeksiyonu
│   ├── services/             # Orta katman (ui import ETMEZ)
│   │   ├── __init__.py
│   │   ├── stream_server.py  # aiohttp yerel WebSocket yayın ve dokunmatik alıcı
│   │   └── project_service.py# UI ve CLI için tek cephe (Facade) servisi
│   └── ui/                   # Üst katman (Web istemcisi + Masaüstü kontrol paneli)
│       ├── __init__.py
│       ├── client_assets/    # Tablette çalışacak tam ekran HTML5/JS/CSS istemcisi
│       └── controller_app.py # Windows tarafı durum, ekran seçimi ve başlat/durdur paneli
└── tests/
    ├── conftest.py           # Kullanıcı verisi ve log yalıtımı (autouse)
    └── unit/
        ├── test_wiki.py      # Wiki kırık link, öksüz sayfa ve CLAUDE.md testi
        ├── test_layering.py  # AST tabanlı katman yönü testi
        ├── test_code_hygiene.py # BOM, çıplak/sessiz except bekçi testleri
        └── test_logging_config.py # İdempotent loglama ve excepthook testi
```

---

## 4. Uygulama Aşamaları (Her Aşama Sonunda Rapor Verilir ve Onay Beklenir)

### Aşama 1: İlk Gün Altyapısı ve LLM Wiki Kurulumu *(Mevcut Aşama)*
- Git deposu başlatılması, `.gitattributes`, `.editorconfig`, `.gitignore`, `LICENSE` (MIT).
- Sabit sürümlü `requirements.txt`, `requirements-dev.txt`, `requirements-build.txt`.
- `ruff.toml`, `pytest.ini` (`EncodingWarning` hataya çevrilmiş), `.github/workflows/ci.yml`.
- `CLAUDE.md` ve `docs/wiki/` (index, rules, decisions, architecture, testing, roadmap, log) kurulumu.
- `src/core/logging_config.py`, `src/core/app_settings.py`, `src/version.py`.
- Bekçi testlerin (`test_wiki`, `test_layering`, `test_code_hygiene`, `test_logging_config`) yazılıp `ruff` + `pytest` ile doğrulanması.

### Aşama 2: Çekirdek Modüller (Ekran Yakalama, Dokunmatik Enjeksiyon ve ADB Tüneli)
- `display_manager.py`: Bağlı monitörlerin (1. Ana Monitör, 2. Laptop, 3. Sanal/Ekran) koordinat ve çözünürlüklerinin tespiti; 3. sanal ekran kurulum/kontrol yardımcısı.
- `screen_capture.py`: Seçilen ekranın yakalanması, değişmeyen karelerin atlanması (Adaptive FPS / Delta) ve düşük gecikmeli JPEG sıkıştırması.
- `input_injector.py`: Tabletten gelen `(x, y)` dokunma, sürükleme, sağ tık ve kaydırma olaylarının 3. ekranın masaüstü koordinatlarına Win32 `SendInput` ile uygulanması.
- `adb_manager.py`: USB ile bağlı Android cihazın tespiti ve `adb reverse tcp:8765 tcp:8765` tünelinin otomatik kurulması.
- Tüm çekirdek modüllerin birim testleri (gerçek ağa ve gerçek fareye dokunmayan yalıtılmış testler).

### Aşama 3: Yerel WebSocket Yayın Sunucusu ve Tablet Dokunmatik Web İstemcisi
- `stream_server.py` & `project_service.py`: Yalnızca `127.0.0.1` üzerinde çalışan Binary WebSocket akış sunucusu.
- `client_assets/`: Android tablette tam ekran (Fullscreen API + Screen WakeLock API) çalışan, dokunmatik olaylarını yakalayan, FPS/gecikme göstergeli ve kalite/mod seçicili (Okuma Modu / Video Modu) modern istemci.
- Sunucu ve protokol birim/entegrasyon testleri.

### Aşama 4: Windows Kontrol Arayüzü, Sanal 3. Ekran Rehberi ve Canlı Cihaz Doğrulaması
- Windows üzerinde tek tıkla 3. ekranı seçip ADB tünelini ve yayını başlatan kontrol arayüzü (`controller_app.py`) ve başlatıcı betik.
- Fiziksel 3. ekran (Sanal Monitör - VDD) kurulum/aktif etme otomasyonu ve tablet ile canlı uçtan uca test.
