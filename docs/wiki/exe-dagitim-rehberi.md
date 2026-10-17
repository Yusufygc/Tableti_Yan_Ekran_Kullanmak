# Windows Exe Dağıtımı ve Kararlı Exe (Bu Projede)

Bu sayfa [[index]] kapsamında TabScreen USB'nin imzasız Windows exe + kurulum dosyası dağıtımını anlatır. Genel rehber (SAC kök nedeni, ölçümler, yapılmaması gerekenler): `D002-HazirPromptlar/Prod hazırlığı/exe-dagitim-rehberi.md`; bu sayfa o rehberin bu depoya uygulanmış hâlidir. Yayın adımları: [[surum-yayinlama]]; uygulama içi güncelleme: [[guncelleme-sistemi]]; kararlar: [[decisions]] (Karar 8); tarihçe: [[log]].

Yığın: Python 3.10, PySide6/QML, PyInstaller 6.22.3 (`--onedir`), Inno Setup 6, GitHub Actions + GitHub Releases. Kod imzalama **yok** (kullanıcı kararı).

## 1. Sorun: Akıllı Uygulama Denetimi (SAC)
Windows 11'de SAC açıksa imzasız her çalıştırılabilir dosya (exe, DLL, kurulum, kaldırıcı) dosya özetine (SHA-256) göre bulut itibarıyla değerlendirilir; karar dosya başına ve öngörülemezdir. Her sürümde yeni bir exe özeti, güncellemeden sonra uygulamanın açılmamasına yol açabilir. SAC'ı kapatmak önerilmez ve yapılmaz.

## 2. Çözüm: bayt bayt aynı ("kararlı") exe
| Parça | Dosya / ayar | Neden |
|---|---|---|
| Sabit giriş betiği | `packaging/launcher.py` (3 satır, `from src.app import run`; **asla değişmez**) | İçeriği exe'ye gömülür |
| Kod exe dışında | `--debug=noarchive`: `.pyc` modülleri `_internal` altında | Sürümle değişen kod exe'yi değiştirmez |
| Sabit zaman damgası | `SOURCE_DATE_EPOCH=1700000000` (`build_exe.LAUNCHER_EPOCH`) | PE zaman damgası özeti değiştirirdi |
| Sabit sürüm kaynağı | `packaging/launcher_version_info.txt` (hep `1.0.0.0`) | Ürün sürümü exe özetine girmesin |
| Diğer | `--noupx`, `--onedir`, `--windowed`, PyInstaller `==6.22.3` sabit, Python 3.10 (CI de), `.gitattributes` `eol=lf` | Özet bunlara bağlıdır |

Ürün sürümü (`src/version.py`) kurulum dosyasında, "Uygulamalar ve özellikler" kaydında ve pencere başlığında görünür. **Bedel:** Gezgin'de exe → Özellikler hep `1.0.0.0` gösterir.

### Onay kapısı
`build_exe.check_launcher_hash` derlenen exe özetini `packaging/launcher.sha256` ile karşılaştırır; farklıysa/dosya yoksa derleme ve yayın **durur**. Onaylı özet yalnızca **temiz venv'de** (CI ile aynı paket kümesi, `requirements-lock.txt`) üretilmelidir. Bilerek değiştirmek için `python build_installer.py --update-launcher-hash` (rehber bölüm 8: önce bu makinede aç, gerekirse yalnızca `LAUNCHER_EPOCH` değiştir). CI de aynı kapıdan geçer (`release.yml` kapıyı atlayamaz; `tests/unit/test_release_packaging.py` bunu denetler).

## 3. Ölçümler (2026-10-17, bu depo, Windows 11, SAC kapalı)
| Deney | Sonuç |
|---|---|
| Aynı kökte yeniden derleme (ana geliştirme venv'i) | exe SHA-256 aynı: `82d57543…f44b` (**sonradan geçersiz kılındı, bkz. aşağıdaki "CI özet farkı"**) |
| **Farklı kökte** (`%TEMP%\gx…\p`) ve `__version__` = `9.9.9` yapılarak derleme | **Aynı özet** (kaynak ve kök değişikliği exe'yi değiştirmiyor) |
| Derlenen exe 8 sn çalıştırıldı (`build_verify.launch_check`) | Çalıştı; pencere başlığı `TabScreenUSB v0.1.0 - 3. Ekran USB Kontrol Paneli` (QML paketlenmişte yüklendi) |
| `build_installer.py` tam akış | Inno derlemesi 34 sn; `TabScreenUSB-Setup-0.1.0.exe` 46,7 MB; sessiz kurulum + exe açılışı + kaldırıcı başarılı; deneme sonrası kayıt ve Başlat menüsü kalıntısı yok |
| Dağıtım klasörü | `dist/TabScreenUSB` ≈194 MB (Qt DLL'leri; `opengl32sw.dll` 20 MB, QML modülleri 12 MB) |

### CI özet farkı ve çözümü (2026-10-17, ilk Release denemesi)
`v0.1.0` etiketi itilince Release iş akışı kapıda **durdu** (Release oluşmadı): CI exe özeti `97e16ac4…1823`, yerelde onaylanan `82d57543…f44b`. Ayrıştırma deneyleri (hepsi Python 3.10.11, PyInstaller 6.22.3, aynı commit):
| Derleme ortamı | Dosyalar | Özet |
|---|---|---|
| Ana geliştirme venv'i (pip-audit + bağımlılıkları, `multidict==6.9.1`) | `git archive` ya da çalışma ağacı | `82d57543…` |
| Temiz venv (`requirements-dev` + `requirements-build`, `multidict==7.1.0`) | `git archive` ya da çalışma ağacı | `97e16ac4…` (= CI) |
| Yalnızca derleme bağımlılıkları (`requirements.txt` + PyInstaller) | `git archive` | `97e16ac4…` |
Sonuç: fark dosyalardan/satır sonlarından değil **Python ortamındaki paket kümesinden** geliyor (ana venv'de geçişli bağımlılık sürümleri ve ek paketler farklıydı). Çözüm: (1) `requirements-lock.txt` geçişli sürümleri sabitler, `release.yml` `-c requirements-lock.txt` ile kurar; (2) onaylı özet **temiz ortamda** üretilen `97e16ac4…` olarak güncellendi ve bu exe bu makinede denendi (açıldı, pencere başlığı doğru; tam `build_installer.py` akışı başarılı, 46,5 MB); (3) kural: özet onayı ve yayın derlemesi yalnızca temiz venv/CI'da yapılır (`python -m venv .venv-build; .venv-build\Scripts\pip install -r requirements.txt pyinstaller==6.22.3`).

**Doğrulandı (2026-10-18):** CI'da derlenen exe özeti yerelde (temiz venv) onaylananla aynı (`ea66a397…2fe3`; `v0.1.0` Release iş akışı kapıyı geçti).

**Doğrulanmadı:** bu makinede SAC kapalı (`VerifiedAndReputablePolicyState=0`); exe/kurulum dosyasının SAC'lı başka makinede açılacağı, CI'da derlenen exe özetinin yerelle aynı çıkacağı (ilk Release'te kapı günlüğüne bakılmalı) ve indirilmiş (MOTW'li) kurulum dosyasının SAC'lı makinede açılacağı **henüz denenmedi**. İlk yayından sonra bu üç madde elle doğrulanıp bu tabloya işlenecek.

## 4. Kurulum sihirbazı (`packaging/TabScreenUSB.iss`)
Sabit `AppId`, `PrivilegesRequired=lowest` (UAC yok, `%LOCALAPPDATA%\Programs\TabScreenUSB`; kullanıcı isterse tüm kullanıcılar seçebilir), `CloseApplications=yes`, sürümlü çıktı adı (`TabScreenUSB-Setup-X.Y.Z.exe`), Türkçe arayüz, isteğe bağlı masaüstü kısayolu. `/SILENT` (güncelleme) kurulum sonrası uygulamayı yeniden açar, `/VERYSILENT` (derleme sonrası deneme) açmaz (`Check: RelaunchAfterUpdate`). Kullanıcı verisi (`~/.tabscreen_usb`) kaldırıcıyla silinmez.

## 5. Paketlenmiş çalışma ortamı
- `src/core/app_paths.py`: `resource_root()` geliştirmede depo kökü, paketlenmişte PyInstaller `_internal`; `user_data_dir()` (`TABSCREEN_USB_HOME` ile değiştirilebilir; testler ve kurulum denemesi gerçek kullanıcı klasörüne dokunmaz).
- Pakete giren veriler (`build_exe.pyinstaller_arguments`): `src/ui/client_assets` (tablet istemcisi + `icon-192.png`), `src/ui/qml`, `packaging/icons/app.ico`, `third_party/` (adb + VDD), `3_ekran_kur.bat` / `3_ekran_kaldir.bat`, `THIRD_PARTY_NOTICES.md` (projenin kendi lisans dosyası yoktur; üçüncü taraf lisans metinleri `third_party/` altında kalır).
- adb: pakete dahil sürüm **önce** aranır (farklı sürüm adb sunucusu çalışan sunucuyu sonlandırır), sonra PATH. Üçüncü taraf dosyalar ve lisanslar: `third_party/README.md`, `THIRD_PARTY_NOTICES.md`.
- Konsolsuz (windowed) exe'de `stdout/stderr` `None` olur: `src/app.py` `_ensure_std_streams()` ile korunur.
- VDD kurulumu (`3_ekran_kur.bat`) yönetici izni ister; yalnızca kullanıcı "3. Sanal Ekranı Kur" dediğinde çalışır.

## 6. Simgeler
`packaging/icons/make_icons.py` (PIL, tekrarlanabilir) üretir: `icon_16…512.png` (10 boyut) ve çok çerçeveli `app.ico` (16, 24, 32, 48, 64, 128, 256; küçük çerçeveler büyük resimden küçültülmez, ayrı çizilir). Motif: koyu lacivert yuvarlak kare + yatay tablet + ekranda dokunma dalgası (istemcideki `touch-ripple`) + altında USB kablosu ipucu; ≤32 px'te ayrıntılar sadeleşir (amber "3" rozeti kullanıcı isteğiyle kaldırıldı). Kullanım: exe (`--icon`), Inno (`SetupIconFile`, `UninstallDisplayIcon`), Qt pencere simgesi, tablet sekmesi (`/icon-192.png`).

## 7. Yapılmaması gerekenler (genel rehberden, bu depoda da geçerli)
Her sürümde yeni exe özeti üretmek; "engellendi" diye derleyip şansa güvenmek; SAC'ı kapatmayı önermek; yeniden açma için ek exe/PowerShell eklemek; Inno kurulum dosyasını elle başlatıp öldürmek (deneme yalnızca sessiz + geçici dizin); deneme kurulumunda gerçek `AppId` kaydını yedeklememek (`build_verify.save_registration/restore_registration`); kaldırıcıyı denemeden bırakmak; yayınlanmış etiketi taşımak; `git push --follow-tags`; kapıyı atlamak; özetsiz güncelleme; kabuk heredoc'u ile kod yazmak. Ayrıntı ve gerekçeler genel rehberin bölüm 9'undadır.

## 8. Proje ayrıntıları ve ilke farkları
- `tools/` klasörü artık izlenir (`tools/release.py`); yerel eski kopyalar (`tools/platform-tools/`, `tools/vdd/`) `.gitignore`'dadır, yayına giren kopyalar `third_party/` altındadır.
- `requirements.txt` içindeki kullanılmayan `PySide6-Essentials` bağımlılığı UI QML'e geçince **kullanılır** hâle geldi; Tkinter bağımlılığı bekçi testle (`test_no_legacy_tkinter_imports`) yasaktır ve PyInstaller `--exclude-module=tkinter` ile dışlanır.
