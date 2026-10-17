# TabScreen USB — Android Tablet 3. Ekran Aracı

Windows bilgisayarınız (1. Ekran: Harici Monitör, 2. Ekran: Laptop Ekranı) ile Android tabletiniz arasında **USB kablosu üzerinden**, üçüncü taraf sunuculara hiçbir veri göndermeden **%100 yerel (`127.0.0.1` loopback)** çalışan, dokunmatik destekli 3. ekran yazılımı.

## Hızlı Başlangıç

1. **Android Tablette USB Hata Ayıklamayı Açın:**
   - Tabletinizin *Ayarlar > Telefon/Tablet Hakkında > Yapım Numarası* satırına 7 kez dokunarak *Geliştirici Seçenekleri*ni açın.
   - *Geliştirici Seçenekleri > USB Hata Ayıklama (USB Debugging)* seçeneğini etkinleştirin ve tableti USB kablosuyla bilgisayara bağlayın.
2. **3. Sanal Ekranı Hazırlayın (Fiziksel 1. ve 2. Ekrana Ek Olarak):**
   - Windows'un fiziksel kablosu olmayan 3. bir masaüstü alanı oluşturması için açık kaynaklı **[Virtual-Display-Driver (VDD)](https://github.com/VirtualDisplay/Virtual-Display-Driver/releases)** kurulu olmalı ve Windows *Görüntü Ayarları*nda **"Masaüstünü bu ekrana genişlet (Extend)"** seçilmelidir.
3. **Uygulamayı Başlatın:**
   - `baslat.bat` dosyasına çift tıklayın (veya terminalden `.\venv\Scripts\python.exe main.py` çalıştırın).
   - Kontrol panelinde **"1) USB ADB Tünelini Kur"** ve ardından **"2) Yayını Başlat (127.0.0.1:8765)"** düğmelerine tıklayın.
4. **Tabletten Bağlanın:**
   - Tabletteki tarayıcıdan (Chrome/Brave/Edge) **`http://127.0.0.1:8765`** adresine gidin ve sağ üstteki **"Tam Ekran"** düğmesine dokunun.

## Gizlilik ve Ağ Güvenliği İlkeleri

- **Sıfır Dış Ağ İsteği:** Bu uygulama internete veya üçüncü taraf sunuculara **hiçbir ağ isteği yapmaz** ve telemetri toplamaz.
- **Yalnızca `127.0.0.1` (Loopback):** Yayın sunucusu yerel Wi-Fi ağınıza (`0.0.0.0`) bile açılmaz; `validate_loopback_host` koruması sayesinde yalnızca `127.0.0.1` üzerinden USB ADB tüneliyle erişilebilir.
- **Kapatma:** Pencere kapatıldığında veya `Ctrl+C` yapıldığında hem yerel sunucu hem de `adb reverse` USB tüneli otomatik olarak kaldırılır.
