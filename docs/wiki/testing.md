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
