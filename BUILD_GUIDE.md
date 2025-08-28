# CAN Depo Yönetim Sistemi - Build Rehberi

## 🚀 Tek EXE Build Adımları

### Gereksinimler
- Python 3.9+ 
- Sanal ortam (.venv) kurulumu
- PyInstaller

### Build İşlemi

1. **Projeyi hazırla:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Build scripti çalıştır:**
   ```bash
   build.bat
   ```

### Build.bat Ne Yapıyor?

1. **[0/6] Python Kontrolü**
   - Python versiyonu kontrol eder
   - PyInstaller yüklü mü kontrol eder, yoksa yükler

2. **[1/6] Temizlik**
   - Eski build dosyalarını temizler (`dist/`, `build/`)

3. **[2/6] Klasör Hazırlığı**
   - Gerekli klasörleri oluşturur (`fonts`, `sounds`, `labels`, `output`, `logs`)

4. **[3/6] Font Kontrolü**
   - `DejaVuSans.ttf` font dosyasını kontrol eder
   - Eksikse `app/fonts/`'tan kopyalar

5. **[4/6] Ses Kontrolü**
   - Ses dosyalarını (`ding.wav`, `bip.wav`, `error.wav`) kontrol eder
   - Eksikse `app/sounds/`'tan kopyalar

6. **[5/6] EXE Build**
   - PyInstaller ile tek dosya EXE oluşturur
   - Tüm bağımlılıkları dahil eder
   - GUI mode (konsol penceresi açmaz)

7. **[6/6] Sonuç Kontrolü**
   - Build başarısını kontrol eder
   - Dosya boyutunu gösterir
   - Test çalıştırma seçeneği sunar

## 📁 Build Sonucu

Build başarılı olursa:
- **Dosya:** `dist/CAN_Depo_Yonetim.exe`
- **Boyut:** ~80-120MB (tüm bağımlılıklar dahil)
- **Tip:** Tek dosya, taşınabilir EXE

## 🚀 Deployment

### Gerekli Dosyalar:
1. `CAN_Depo_Yonetim.exe` (ana uygulama)
2. `settings.json` (ayar dosyası)

### Environment Variables (Önemli!):
```bash
# Database bağlantısı için gerekli
set LOGO_SQL_SERVER=your_server
set LOGO_SQL_DB=your_database  
set LOGO_SQL_USER=your_username
set LOGO_SQL_PASSWORD=your_password

# API için (optional)
set API_SECRET=your_secret_key
set DB_CONN_TIMEOUT=10
```

### Çalıştırma:
```bash
# Doğrudan çalıştırma
CAN_Depo_Yonetim.exe

# Environment variables ile
set LOGO_SQL_SERVER=192.168.1.100 && CAN_Depo_Yonetim.exe
```

## 🔧 Build Sorun Giderme

### Yaygın Hatalar:

1. **"Python sanal ortami bulunamadi"**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **"PyInstaller hatasi"**
   ```bash
   pip install --upgrade pyinstaller
   pip install --upgrade setuptools
   ```

3. **"ModuleNotFoundError"**
   - `build.bat` içindeki `--hidden-import` listesine eksik modülü ekle

4. **"Font/Ses dosyası bulunamadi"**
   - `app/fonts/DejaVuSans.ttf` var mı kontrol et
   - `app/sounds/` klasöründe ses dosyaları var mı kontrol et

### Debug Build:
Debug için console mode'da build yapmak:
```bash
.venv\Scripts\python.exe -m PyInstaller --clean --onefile --console main.py
```

## 📊 Build Optimizasyonu

### Boyutu Küçültme:
- `--exclude-module` ile gereksiz modülleri dışla
- `--upx` ile sıkıştırma (UPX gerekir)
- `--strip` ile debug bilgilerini kaldır

### Hızlı Build:
- `--clean` yerine `--noconfirm` kullan (test için)
- Cache'i temizleme (`build/` klasörünü sakla)

## ✅ Test Checklist

Build sonrası test etmek için:

- [ ] EXE dosyası çalışıyor mu?
- [ ] Database bağlantısı kuruluyor mu?
- [ ] Scanner sayfası açılıyor mu?
- [ ] Barcode okuma çalışıyor mu?
- [ ] Ses dosyaları çalıyor mu?
- [ ] PDF oluşturma çalışıyor mu?
- [ ] Ayarlar kaydediliyor mu?

## 📞 Yardım

Sorun yaşarsan:
1. Build log'unu kontrol et
2. Console mode'da çalıştırıp hata mesajlarını oku
3. Environment variable'ların doğru set edildiğini kontrol et
4. Database sunucusuna erişim var mı kontrol et