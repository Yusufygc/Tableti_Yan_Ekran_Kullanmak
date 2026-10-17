# Uygulama İçi Güncelleme

Paketlenmiş uygulama açılışta GitHub Releases'te yeni sürüm arar; varsa "Yeni sürüm var" penceresi çıkar. **Güncelle** denince kurulum dosyası indirilir, doğrulanır, uygulama kapanır ve kurulum sessizce üstüne yazar; uygulama kendiliğinden yeniden açılır. Yayın süreci: [[surum-yayinlama]]; exe/SAC arka planı: [[exe-dagitim-rehberi]]; kararlar: [[decisions]]; haritası: [[index]].

## Akış
1. **Yayın:** `vX.Y.Z` etiketi itilince `release.yml` `TabScreenUSB-Setup-X.Y.Z.exe` ve `.sha256` dosyalarını üretip Release'e yükler.
2. **Denetim:** `ControllerWindow.run()` pencere çizildikten 3 sn sonra `UpdateViewModel.startupCheck()` çağırır (kurucuda değil: testler ağa çıkmasın). Tek istek: `GET https://api.github.com/repos/Yusufygc/Tableti_Yan_Ekran_Kullanmak/releases/latest`, kimlik bilgisi yok. Ağ yok/hata/güncel → sessiz. Panelde **4. Güncellemeler** kartındaki *Güncellemeleri Denetle* her sonucu gösterir ve atlanan sürümü de teklif eder. Kapatma: kartta *Açılışta güncellemeleri denetle* kutusu ya da `TABSCREEN_NO_UPDATE_CHECK=1`.
3. **Karşılaştırma:** `update_service.release_to_update` etiketi sayısal olarak yüklü sürümle kıyaslar; taslak ve ön sürüm yok sayılır.
4. **İndirme:** arka plan iş parçacığı (`QThread`) + ilerleme çubuğu. Zorunlu doğrulama: adres yalnızca bu deponun `releases/download/` yolu (yönlendirme yalnızca `github.com`/`*.githubusercontent.com`, `https`); dosya adı `TabScreenUSB-Setup-X.Y.Z.exe` desenine uymalı; boyut ≤ 400 MB ve Release'teki boyutla birebir; SHA-256: GitHub asset `digest` alanı, yoksa Release'teki `.sha256` dosyası, **ikisi de yoksa güncelleme reddedilir**; uyuşmazlıkta dosya silinir. İndirme klasörü `%TEMP%\TabScreenUSBUpdate`.
5. **Kurulum:** `Setup.exe /SILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /LOG=<klasör>\install.log` bağımsız süreç (kabuk yok, `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`); sonra uygulama kapanır (`quitRequested` → `QGuiApplication.quit`), Inno kurar, `[Run]` ile yeniden açar.
6. **Windows başlatmayı engellerse:** önce `CreateProcess`; `WinError 4551/1260` gelirse `ShellExecuteW` (Gezgin yolu); ikisi de engelliyse `InstallerBlockedError`. `UpdateViewModel` 15 sn aralıkla en çok 40 kez (10 dk) yeniden dener ("Windows bekleniyor…", **Beklemeyi Bırak** düğmesi); süre dolarsa/vazgeçilirse dosya Gezgin'de seçili gösterilir ve **Sürüm Sayfası** düğmesi çıkar.

## Katmanlar
`UpdateDialog.qml` + 4. kart (`Main.qml`) → `UpdateViewModel` (`src/ui/update_viewmodel.py`) → `ProjectService` cephesi (`check_for_update`, `download_update`, `launch_update_installer`, `skip_update_version`, `set_update_check_on_startup`) → `update_service` (`src/services/update_service.py`; UI'dan bağımsız, ağ sahte `opener` ile birim testli). Tercihler: `~/.tabscreen_usb/updates.json` (açılış denetimi, atlanan sürüm). UI katmanı `src.core` import etmez ([[architecture]]).

## Güvenlik sınırı (bilerek kabul edildi)
Özet GitHub'dan gelir; GitHub hesabı ele geçirilirse sahte dosya + sahte özet yayınlanabilir ve imza olmadığı için fark yakalanamaz. İmzasız dağıtımın doğasıdır. Yerel yayın sunucusunun güvenliği (Host/Origin bekçisi) ayrıdır ([[architecture]]).

## Test ve doğrulama durumu
- Birim testleri: `tests/unit/test_update_service.py` (sürüm, Release ayrıştırma, adres/ad/boyut/SHA kuralları, yönlendirme, kurulum argümanları, SAC geri dönüşü), `tests/unit/test_update_viewmodel.py` (açılış/elle denetim, indirme→kurulum→çıkış, engel bekleme/yeniden deneme/vazgeçme) — bkz. [[testing]].
- **Doğrulanmadı:** gerçek bir Release üzerinden uçtan uca güncelleme (henüz Release yok). İlk iki sürüm yayınlandığında `0.1.0 → 0.1.1` güncellemesi elle denenip buraya işlenecek; ağ katmanı yalnızca sahte yanıtlarla test edildi.
- Sınırlar: yalnızca Windows; indirme sürerken pencere kapatılamaz; iptal düğmesi yok.
