# Sürüm Yayınlama Süreci

Yeni sürüm **etiket** ile yayınlanır: `vX.Y.Z` etiketi itilince GitHub Actions testleri koşar, kararlı exe kapısından geçirir, Inno kurulum dosyasını derler ve GitHub Releases'e yükler. Kurulu uygulamalar açılışta bu yayını görüp güncelleme teklif eder ([[guncelleme-sistemi]]). Exe ve kapı ayrıntıları: [[exe-dagitim-rehberi]]; kararlar: [[decisions]]; tarihçe: [[log]]; sayfa haritası: [[index]].

## Sürüm numarası
- Biçim `MAJOR.MINOR.PATCH` (`0.2.0`), etiket `v` önekli (`v0.2.0`). Güncelleyici yalnızca bu biçimi tanır ve sayısal karşılaştırır (`0.10.0 > 0.9.0`); ön sürümler (`-rc1`) yok sayılır.
- **Tek kaynak:** `src/version.py` (`__version__`, `APP_NAME`, `RELEASE_REPO`). README rozeti `tools/release.py` ile aynı değere çekilir (`test_single_version_source_and_release_repo`). exe'nin Windows sürüm kaynağı **bilerek** yükseltilmez ([[exe-dagitim-rehberi]]).
- Artış: hata düzeltme → PATCH; özellik → MINOR; geriye dönük uyumsuz veri/ayar değişikliği → MAJOR.

## Yayın adımları
Ön koşul: yayınlanacak commit `main` üzerinde, CI yeşil (`ruff`, `pytest`), çalışma ağacı temiz. (Şu an geliştirme `perf/otomatik-kalite-modu` dalındadır; yayın öncesi `main`e birleştirilmelidir.)

```powershell
python tools/release.py 0.2.0     # src/version.py + README rozeti, "chore(release): v0.2.0" commit'i, ek açıklamalı v0.2.0 etiketi (İTMEZ)
git push origin main
git push origin v0.2.0            # --follow-tags KULLANMA: hafif etiketleri göndermez
gh run watch
gh release view v0.2.0            # kurulum dosyası ve .sha256 var mı
```

`.github/workflows/release.yml` sırayla: (1) etiket ↔ `src/version.py` denetimi (`tools/release.py --check-tag`; etiket adı ortam değişkeniyle verilir, komut enjeksiyonu olmasın), (2) `ruff` + `pytest`, (3) Inno Setup yoksa `choco install innosetup`, (4) `python build_installer.py` (exe özet kapısı: `packaging/launcher.sha256` ile farklıysa **yayın durur**; CI'da SAC denemesi atlanır), (5) `gh release create ... --generate-notes --verify-tag` (`-` içeren etiket ön sürüm olur). Sürüm notları commit mesajlarından üretilir: mesajlar Türkçe ve anlaşılır yazılır.

## Yerelde deneme
`python build_installer.py` (≈2-3 dk): exe derle + kapı + exe'yi 8 sn aç + Inno derle + `.sha256` yaz + kurulum dosyasını geçici dizine sessizce kur, aç, kaldır. Deneme gerçek kurulum kaydını yedekleyip geri yazar (`build_verify`). `--skip-build`, `--no-verify`, `--update-launcher-hash` seçenekleri vardır.

## Kontrol listesi
- [ ] CI yeşil; davranış değişikliği varsa README ve wiki güncel.
- [ ] `tools/release.py` çalıştırıldı; etiket `v` + `__version__`.
- [ ] CI günlüğünde "Kararlı exe özeti onaylananla aynı".
- [ ] Release'te `TabScreenUSB-Setup-X.Y.Z.exe` ve `.sha256` var.
- [ ] **İndirilmiş (MOTW'li) kurulum dosyası SAC'lı gerçek bir makinede açıldı** (CI'daki Windows'ta SAC yoktur; CI'da derlenen dosya hiç denenmemiştir).
- [ ] Önceki sürümden uygulama içi güncelleme denendi (pencere, kurulum, yeniden açılış, yeni sürüm numarası).

## Hata ve geri alma
| Durum | Yapılacak |
|---|---|
| Etiket ↔ sürüm farklı, iş akışı durdu (yayın yok) | Düzelt, commit'le, etiketi taşı (`git tag -f`, `git push -f origin vX.Y.Z`) |
| Kapı "özet DEĞİŞTİ" dedi | [[exe-dagitim-rehberi]] bölüm 2-3; nedenini bul, bilerek değiştirdiysen rehber bölüm 8 |
| Yayın oluştu ama sürüm hatalı | **Yayınlanmış etiketi taşıma**; yeni PATCH çıkar. Acilse `gh release delete vX.Y.Z --cleanup-tag` |
| `git push` etiketi göndermedi | `git push origin vX.Y.Z` ayrıca |
| Kurulu kullanıcıda güncelleme başlamadı | `%TEMP%\TabScreenUSBUpdate\install.log` |

## Güvenlik ve sınırlar
- Yayın tüm kurulu kullanıcılara güncelleme penceresi çıkarır: **yapay zekâ asistanları kullanıcının açık isteği olmadan etiket oluşturmaz veya itmez.** (`tools/release.py` itmez; test bunu denetler.)
- İndirme adresi yalnızca `https://github.com/Yusufygc/Tableti_Yan_Ekran_Kullanmak/releases/download/...` olabilir; boyut ve SHA-256 doğrulanır, özet yoksa güncelleme reddedilir; bu kontroller kaldırılmaz.
- Kurulum dosyası imzasızdır: SmartScreen/SAC engeli olabilir. Yalnızca Windows.
- **Durum:** henüz hiç Release yayınlanmadı (sürüm `0.1.0` yerelde derlendi ve denendi; GitHub'a etiket itilmedi).
