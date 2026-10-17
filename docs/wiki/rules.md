# Çalışma Düzeni ve Kurallar

Bu sayfa [[index]] içindeki geliştirme, altyapı ve LLM Wiki yönetim kurallarını tanımlar. Mimari detaylar için [[architecture]], test kuralları için [[testing]] sayfasına bakın.

## 1. LLM Wiki Operasyon Kuralları
1. **Önce Oku (No Zero-Context):** Her görevden önce [[index]] ve [[log]] okunur.
2. **Proaktif Güncelleme (Bookkeeping):** Yeni bir modül, kütüphane veya karar eklendiğinde [[decisions]], [[architecture]] ve [[log]] aynı turda güncellenir.
3. **Bağlantısallık:** Hiçbir sayfa öksüz (orphan) bırakılmaz; tüm sayfalar [[index]] içinde listelenir ve `tests/unit/test_wiki.py` ile doğrulanır.
4. **Operasyon Komutları:**
   - `[INGEST]`: Yeni kaynağı analiz et, özet sayfasını aç/güncelle, [[index]] ve [[log]] dosyalarına işle.
   - `[QUERY]`: Önce [[index]] üzerinden ilgili sayfaları oku, sentezlenmiş yanıt üret.
   - `[LINT]`: Tüm `docs/wiki/` klasörünü kırık bağlantı, öksüz sayfa ve çelişkiler için denetle.

## 2. Kodlama ve Depo Hijyeni Kuralları
- **UTF-8 Zorunluluğu:** Tüm `open()`, `read_text()`, `write_text()` çağrılarında `encoding="utf-8"` açıkça verilir. Kaynak dosyalarda UTF-8 BOM bulunmaz (`test_source_files_have_no_utf8_bom`).
- **Windows `.bat` Hijyeni:** Windows `cmd.exe` içinde `chcp 65001` + LF satır sonu + çok baytlı UTF-8 karakterler kullanıldığında byte-offset kayması (komutların ortadan bölünmesi: `echo` -> `ho`) yaşandığından tüm `.bat` dosyaları saf ASCII ve `CRLF` (`\r\n`) olmak zorundadır (`test_bat_files_use_crlf_and_pure_ascii`).
- **Sessiz Hata Yutma Yok:** Çıplak `except:` veya loglamadan/sonuca yazmadan istisna yutan geniş `except Exception:` blokları yasaktır (`test_no_bare_except_and_no_silent_broad_except`).
- **Katman Yönü:** `src/core` → `src/services` → `src/ui` tek yönlü bağımlılık kuralına uyar (`test_layering`).
- **Ağ ve Gizlilik:** Yayın sunucusu yalnızca `127.0.0.1` (loopback) adresini dinler; dış ağa veya telemetri sunucularına veri gönderilmez.

## 3. Süreç ve Git Kuralları
- Çok aşamalı işlerde (bkz. [[roadmap]]) her aşama sonunda rapor verilir ve kullanıcı onayı beklenir.
- Commit yalnızca kullanıcı açıkça `"commit at"` dediğinde atılır; mesajlar Türkçe `tip(kapsam): özet` biçimindedir ve AI/Co-Authored-By satırı içermez.
