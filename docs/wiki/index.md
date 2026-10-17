# P029 LLM Wiki — İçerik Haritası (Index)

Bu sayfa, **P029 Tablet Ekranı Kullanımı** projesinin bilgi tabanının (LLM Wiki) tek giriş noktasıdır. Tüm sayfalar birbirine Obsidian stili çift köşeli parantez bağlantılarıyla (örn. [[rules]]) bağlıdır.

## 1. Yönetim ve Kurallar
- [[rules]] — Geliştirme, kodlama standartları, LLM Wiki operasyon komutları (`INGEST`, `QUERY`, `LINT`) ve git çalışma düzeni.
- [[decisions]] — Alınan mimari kararlar, seçilen teknolojiler ve reddedilen alternatiflerin gerekçeleri.
- [[log]] — Kronolojik işlem ve değişiklik kayıt defteri (en yeni kayıt en üstte).

## 2. Teknik Mimari ve Doğrulama
- [[architecture]] — 3 ekranlı (Monitör + Laptop + USB Android Tablet) sistem mimarisi, katman kuralları ve yerel ADB tünel protokolü.
- [[testing]] — Birim testleri, kullanıcı verisi yalıtımı ve AST tabanlı mimari bekçi (guardian) testleri.
- [[roadmap]] — Aşamalı geliştirme planı ve tamamlanma durumu.

## 3. Dağıtım, Yayın ve Güncelleme
- [[exe-dagitim-rehberi]] — İmzasız Windows exe dağıtımı: Akıllı Uygulama Denetimi, kararlı exe + özet kapısı, Inno kurulum dosyası, paketlenmiş çalışma ortamı, simgeler.
- [[surum-yayinlama]] — `vX.Y.Z` etiketiyle GitHub Release süreci, `tools/release.py`, kontrol listesi ve geri alma.
- [[guncelleme-sistemi]] — Uygulama içi güncelleme: denetim, doğrulamalı indirme, sessiz kurulum, Windows engeli bekleme.
