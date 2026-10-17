# third_party — Pakete Dahil Üçüncü Taraf İkili Dosyalar

Kurulum dosyası (`TabScreenUSB-Setup-X.Y.Z.exe`) ve CI release derlemesi bu dosyaları depodan alır; böylece yerel ve CI derlemesi birebir aynı girdiyle çalışır. Dosyalar **değiştirilmemiştir**; yerelde `tools/` altına indirilen resmî paketlerden yalnızca gerekenler kopyalanmıştır.

| Klasör | İçerik | Kaynak | Lisans |
|---|---|---|---|
| `platform-tools/` | `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`, `NOTICE.txt` (SDK Platform-Tools 37.0.1) | developer.android.com | Apache-2.0 |
| `vdd/VirtualDisplayDriver/` | `MttVDD.dll`, `MttVDD.inf`, `mttvdd.cat`, `vdd_settings.xml` (proje yapılandırması) | github.com/VirtualDrivers/Virtual-Display-Driver | MIT |
| `vdd/nefcon/x64/` | `nefconc.exe` (sürücü kurulumu) | github.com/nefarius/nefcon | MIT |

## SHA-256 özetleri (sağlama için; 2026-10-17)

| Dosya | SHA-256 |
|---|---|
| `platform-tools/adb.exe` | `b4a6b455702684652cccf7b46258b29e653538904359a58fd4931cf3ef286b3f` |
| `platform-tools/AdbWinApi.dll` | `c1d653030b4bde65d3e07e4d0b0979e17be56df1436cdd15528630f27808050d` |
| `platform-tools/AdbWinUsbApi.dll` | `0710e894d9b40f71a670c13c694079d564c92c1279da382cfe4850983aaebe1b` |
| `vdd/VirtualDisplayDriver/MttVDD.dll` | `c9ca837f57a98fbd43bc416a7f535a95843626e7759eaf85cf0cd7ce334dbb05` |
| `vdd/VirtualDisplayDriver/MttVDD.inf` | `550d211fe481e74dfe3f9d724ed78be48b3a9113405965d683d9373e8d672f5d` |
| `vdd/VirtualDisplayDriver/mttvdd.cat` | `08a0093fc9b2e32b287a6f8a77ca4de0a31830d29fc33d2b13a918dc859468f6` |
| `vdd/VirtualDisplayDriver/vdd_settings.xml` | `c91fa0d9295d580c472a10c56c80db744a82237fb7dd38a3d441992c0963d8a4` |
| `vdd/nefcon/x64/nefconc.exe` | `bbcfab8eee0960fe455ea2fa8213f6f7fa17fa500137fc83dc57685486771cd7` |

Dosya güncellenirse: özetleri, `THIRD_PARTY_NOTICES.md` ve `docs/wiki/exe-dagitim-rehberi.md` kaydını birlikte güncelle. `adb.exe` yeni sürümü eski adb sunucusuyla çakışabilir: paketlenen adb uygulama içinde **önce** aranır (`adb_manager.find_safe_adb_executable`).
Sürücü (`MttVDD`) kurulumu yönetici izni ister; `3_ekran_kur.bat` UAC onayı ister ve yalnızca kullanıcı "3. Sanal Ekranı Kur" dediğinde çalışır.
