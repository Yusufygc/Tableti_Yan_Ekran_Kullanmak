# Üçüncü Taraf Yazılım Bildirimleri (Third-Party Notices)

Bu proje (`TabScreen USB`), aşağıdaki açık kaynaklı kütüphaneleri kullanır (`requirements.txt`):

| Kütüphane | Sürüm | Lisans | Bağlantı |
|---|---|---|---|
| **PySide6-Essentials (Qt for Python)** | `6.12.0` | LGPL-3.0-only | https://wiki.qt.io/Qt_for_Python |
| **mss** | `10.2.0` | MIT | https://github.com/BoboTiG/python-mss |
| **Pillow** | `12.3.0` | MIT-CMU | https://python-pillow.org/ |
| **aiohttp** | `3.14.5` | Apache-2.0 | https://github.com/aio-libs/aiohttp |

## Qt / PySide6 LGPLv3 Bildirimi
PySide6 (Qt for Python) GNU Lesser General Public License v3 (LGPLv3) kapsamında dinamik olarak bağlanmıştır. Kullanıcılar kendi uyumlu PySide6/Qt paylaşımlı kütüphaneleriyle uygulamayı çalıştırma hakkına sahiptir.

## Pakete Dahil Edilen İkili Dosyalar (`third_party/`)
Kurulum dosyası aşağıdaki, kaynağı değiştirilmemiş üçüncü taraf dosyaları içerir:

| Bileşen | Dosyalar | Lisans | Kaynak |
|---|---|---|---|
| **Android SDK Platform-Tools 37.0.1 (adb)** | `third_party/platform-tools/` (`adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`, `NOTICE.txt`) | Apache-2.0 (bildirim: `NOTICE.txt`) | https://developer.android.com/tools/releases/platform-tools |
| **Virtual Display Driver (MttVDD)** | `third_party/vdd/VirtualDisplayDriver/` | MIT (`third_party/vdd/LICENSE-VirtualDisplayDriver.txt`) | https://github.com/VirtualDrivers/Virtual-Display-Driver |
| **nefcon** | `third_party/vdd/nefcon/x64/nefconc.exe` | MIT (`third_party/vdd/LICENSE-nefcon.txt`) | https://github.com/nefarius/nefcon |

`vdd_settings.xml` bu projeye özgü yapılandırmadır. Dosya özetleri ve sürüm notları `third_party/README.md` içindedir.
Exe paketleme için PyInstaller kullanılır (GPL-2.0 + önyükleyici istisnası: paketlenen uygulamaya lisans yükümlülüğü getirmez).
