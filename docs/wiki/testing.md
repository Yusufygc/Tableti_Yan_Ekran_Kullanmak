# Test Stratejisi ve Bekçi Testler (Testing)

Bu sayfa [[index]] içindeki test mimarisini ve [[rules]] kurallarını zorunlu kılan bekçi (guardian) testleri açıklar. Katman yapısı için [[architecture]] sayfasına bakın.

## 1. Çalıştırma ve Kodlama Koruması
- Tüm testler `pytest.ini` üzerinden `filterwarnings = error::EncodingWarning` ayarıyla koşar.
- Yerel ve CI koşularında `python -X warn_default_encoding -m pytest -q` komutu kullanılarak `encoding="utf-8"` unutulmuş her dosya işlemi anında yakalanır.

## 2. Kullanıcı Verisi Yalıtımı (`tests/conftest.py`)
- `autouse=True` olan `isolated_app_environment` fixture'ı ile `app_settings` ve `logging_config` yolları her testte `tmp_path_factory` altındaki geçici klasörlere yönlendirilir.
- Testler gerçek kullanıcı klasörüne (`~/.tabscreen_usb`) asla dokunmaz.

## 3. Mimari Bekçi Testleri (`tests/unit/`)
| Test Dosyası | Denetlediği Kural |
|---|---|
| `test_wiki.py` | `docs/wiki/` içinde kırık wiki bağlantısı, öksüz sayfa veya [[index]] eksiği olmadığını; `CLAUDE.md` dosyasının temel giriş noktalarını içerdiğini doğrular. |
| `test_layering.py` | AST analiziyle `src/core` katmanının `services`/`ui` import etmediğini ve `src/services` katmanının `ui` import etmediğini doğrular. |
| `test_code_hygiene.py` | Kaynak dosyalarda UTF-8 BOM olmadığını ve çıplak `except:` veya sessiz geniş `except Exception:` bulunmadığını AST ile denetler. |
| `test_logging_config.py` | Dosyaya loglamanın idempotent (tekrar çağrıldığında çift handler eklemeyen) çalıştığını ve istisna kancalarını doğrular. |

## 4. Yayın Hattı ve Güvenlik Testleri
| Test Dosyası | Denetlediği Kural |
|---|---|
| `test_stream_security_pipeline.py` | Yabancı `Origin`/`Host` → 403; yeni istemci eskiyi `4001` ile kapatır; bozuk JSON/dokunmatik/config mesajları bağlantıyı düşürmez; `/status` aşama sürelerini verir; topoloji önbelleği ekran indeksine göre geçersizleşir. |
| `test_capture_pipeline.py` | Satır imzası küçük değişimi (metin imleci) yakalar; `BGRX` kanal sırası doğru; tamsayı ölçekler `reduce` ile, diğerleri bilinear ile boyutlanır; iki aşamalı API aşama sürelerini ve aynı kareyi atlamayı doğrular; `MODE_PRESETS` tek kaynaktır. |
| `test_adaptive_mode.py` | Otomatik kip durum makinesi: ilk kare hareket → durulunca tek keskin kare → durağanda sessizlik; yeni hareket döngüyü yeniden başlatır; `reset_delta_state` hareket+keskin üretir; Okuma/Video keyframe davranışı korunur; keskin kare tam çözünürlük/4:4:4 ve hareket karesi 2/3 ölçeklidir. |
| `test_grabber_threading.py` | `MssRawGrabber` işçi thread değişiminde (yayını durdur/başlat) ve `ScreenShotError` sonrası GDI tutamaçlarını yeniler; yenilemeye rağmen başarısızsa hatayı gizlemez. |

Performans ölçümü (birim test değildir): gerçek `mss` + gerçek `StreamServer` ile loopback istemcisi FPS ve ping ölçer; sonuçlar [[log]] kaydındadır.
