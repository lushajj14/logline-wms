# 🚀 PROJE ÇALIŞTIRMA TALİMATLARI

## 📋 Gereksinimler

### 1. Python Kurulumu
- Python 3.10+ gerekli
- Kontrol: `python --version`

### 2. Bağımlılıkları Yükleme
```bash
# Virtual environment oluştur (önerilen)
python -m venv venv

# Aktif et
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

## 🔧 Yapılandırma

### 1. Environment Variables (.env dosyası)
`.env.example` dosyasını `.env` olarak kopyalayın ve düzenleyin:

```bash
# .env dosyası oluştur
copy .env.example .env

# Düzenle
notepad .env
```

Gerekli ayarlar:
```env
LOGO_SQL_SERVER=192.168.5.100,1433
LOGO_SQL_DB=logo
LOGO_SQL_USER=barkod1
LOGO_SQL_PASSWORD=your_password_here
```

## 🎯 ÇALIŞTIRMA KOMUTLARI

### 1. 🖥️ ANA UYGULAMA (PyQt5 Desktop)
```bash
# Ana pencereyi başlat
python main.py

# veya
python -m main
```

### 2. 🌐 API SERVER (FastAPI)
```bash
# API'yi başlat (port 8000)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# veya daha detaylı
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
```

API Endpoints:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

### 3. 🧪 TEST ÇALIŞTIRMA
```bash
# Tüm testleri çalıştır
pytest

# Coverage ile
pytest --cov=app --cov-report=html

# Belirli test
pytest tests/test_config.py -v
```

### 4. 🔒 GÜVENLİK TARAMASI
```bash
# Security scan
python scripts/security_scan.py

# Bandit ile kod analizi
bandit -r app/ -f json

# Dependency kontrolü
safety check
```

### 5. 🔍 ENVIRONMENT DOĞRULAMA
```bash
# Environment variables kontrolü
python -m app.config.validate_env

# Database bağlantı testi
python -c "from app.dao.logo import fetch_one; print(fetch_one('SELECT 1 as test'))"
```

## 📦 BUILD İŞLEMİ (EXE)

### Windows için EXE oluşturma:
```bash
# Build script ile
build.bat

# veya manuel PyInstaller
pyinstaller --onefile --windowed --name "WMS_Application" main.py
```

## 🏃 HIZLI BAŞLANGIÇ

### Minimum çalıştırma (development):
```bash
# 1. Environment variables ayarla
set LOGO_SQL_SERVER=192.168.5.100,1433
set LOGO_SQL_DB=logo
set LOGO_SQL_USER=barkod1
set LOGO_SQL_PASSWORD=Barkod14*

# 2. Ana uygulamayı başlat
python main.py
```

### Production için:
```bash
# 1. .env dosyasını düzenle
# 2. Environment'ı production yap
set ENVIRONMENT=production

# 3. API'yi production modda başlat
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

# 4. Ana uygulamayı başlat
python main.py
```

## 🐛 SORUN GİDERME

### "Module not found" hatası:
```bash
# PYTHONPATH ayarla
set PYTHONPATH=%PYTHONPATH%;C:\Users\User\Desktop\your_project2

# veya
export PYTHONPATH=$PYTHONPATH:/path/to/your_project2
```

### Database bağlantı hatası:
```bash
# Connection pool'u devre dışı bırak
set DB_USE_POOL=false

# Debug mode aç
set APP_DEBUG=true
set APP_LOG_LEVEL=DEBUG
```

### PyQt5 import hatası:
```bash
# PyQt5'i yeniden yükle
pip uninstall PyQt5 PyQt5-Qt5 PyQt5-sip -y
pip install PyQt5==5.15.*
```

## 📱 KULLANIM

### Ana Pencere Kısayolları:
- `F1` - Yardım
- `F5` - Yenile (Loader sayfasında)
- `Ctrl + D` - Koyu tema
- `Ctrl + +` - Yazı büyüt
- `Ctrl + -` - Yazı küçült
- `ESC` - İptal/Çıkış

### Sayfalar:
1. **Pick-List** - Sipariş hazırlama listesi
2. **Scanner** - Barkod okutma
3. **Back-Orders** - Bekleyen siparişler
4. **Rapor** - Excel raporları
5. **Etiket** - Etiket yazdırma
6. **Loader** - Yükleme takibi
7. **Sevkiyat** - Sevkiyat yönetimi
8. **Ayarlar** - Uygulama ayarları
9. **Görevler** - Task board
10. **Kullanıcılar** - Kullanıcı yönetimi

## 📊 PERFORMANS

### Connection Pool Durumu:
```python
# Pool bilgilerini kontrol et
python -c "from app.dao.logo import get_pool_info; print(get_pool_info())"
```

### Cache Temizleme:
```python
# Cache'i temizle
python -c "from app.utils.thread_safe_cache import get_global_cache; get_global_cache().clear()"
```

## 🔄 GÜNCELLEME

```bash
# Son değişiklikleri al
git pull

# Bağımlılıkları güncelle
pip install -r requirements.txt --upgrade

# Migration varsa çalıştır
python scripts/migrate.py
```

## 📝 NOTLAR

- **Development**: `.env` dosyası kullanılır
- **Production**: Environment variables sistem üzerinden ayarlanmalı
- **Logging**: Loglar `~/WMS/logs/` klasöründe
- **Settings**: Ayarlar `settings.json` dosyasında saklanır
- **Backup**: Her değişiklikte `settings.backup.json` oluşturulur

---

**Destek için**: GitHub Issues veya IT ekibi ile iletişime geçin.