# P029 — Tablet Ekranı Kullanımı (CLAUDE.md & AI Anayasası)

Sen bu projenin baş geliştiricisi ve `docs/wiki/` klasöründeki bilgi tabanının (LLM Wiki) tek yöneticisisin.

## Zorunlu İlk Adım (No Zero-Context)
Her oturumda kod yazmadan, mimari karar vermeden veya soruları yanıtlamadan önce **MUTLAKA** şu giriş noktalarını oku:
- `docs/wiki/index.md` — Bilgi tabanı içerik haritası
- `docs/wiki/rules.md` — Çalışma, kodlama, test ve git kuralları
- `docs/wiki/decisions.md` — Alınan mimari kararlar ve gerekçeleri
- `docs/wiki/log.md` — Kronolojik işlem kayıt defteri

## Temel Komutlar
- **Lint kontrolü:** `python -m ruff check .`
- **Test koşumu (UTF-8 zorlamalı):** `python -X warn_default_encoding -m pytest -q`
- **Güvenlik taraması:** `python -m pip_audit -r requirements.txt`

## Kritik Kurallar Özeti
1. **Kod + Test + Wiki Birlikte:** Her kod değişikliği aynı turda ilgili testleri ve `docs/wiki/` sayfalarını (`log.md` dahil) günceller.
2. **Katman Yönü:** `src/core` alt katmandır (`services` veya `ui` import etmez). `src/services` orta katmandır (`ui` import etmez). Arayüz yalnızca `ProjectService` cephesini çağırır.
3. **Kodlama & Hata Yönetimi:** Tüm dosya işlemlerinde `encoding="utf-8"` zorunludur. Çıplak `except:` veya sessiz hata yutma yasaktır.
4. **Git & Süreç:** Commit yalnızca kullanıcı `"commit at"` dediğinde atılır. Çok aşamalı işlerde her aşama sonunda rapor verilir ve onay beklenir.
