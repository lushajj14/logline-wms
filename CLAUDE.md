# WMS (Warehouse Management System) - Claude Project Memory

## 🎯 Proje Özeti
Türkçe PyQt5 tabanlı depo yönetim sistemi. Logo ERP entegrasyonu ile çalışır.

## 📁 Proje Yapısı

```
your_project2/
├── app/
│   ├── ui/pages/          # PyQt5 arayüz sayfaları
│   │   ├── scanner_page.py      # Barkod okutma ve sipariş işleme
│   │   ├── loader_page.py       # Paket yükleme
│   │   ├── backorders_page.py   # Eksik sipariş yönetimi
│   │   ├── picklist_page.py     # Pick-list oluşturma
│   │   ├── enhanced_picklist_page.py  # Gelişmiş pick-list
│   │   └── label_page.py        # Etiket basma
│   ├── dao/               # Veri erişim katmanı
│   │   └── logo.py              # Logo ERP veritabanı işlemleri
│   ├── services/          # İş servisleri
│   │   ├── picklist.py         # Pick-list PDF oluşturma
│   │   └── backorder_label_service.py  # Backorder etiketleme
│   ├── utils/             # Yardımcı fonksiyonlar
│   │   └── common.py            # Ortak utility fonksiyonları
│   ├── backorder.py      # Backorder iş mantığı
│   ├── shipment.py       # Sevkiyat yönetimi
│   └── shipment_safe_sync.py  # Güvenli paket senkronizasyonu
└── .env                   # Ortam değişkenleri

```

## 🗄️ Veritabanı Tabloları

### Logo ERP Tabloları
- `LG_025_01_ORFICHE` - Sipariş başlıkları (period-dependent)
- `LG_025_01_ORFLINE` - Sipariş satırları (period-dependent)
- `LG_025_ITEMS` - Stok kartları (period-independent)

### WMS Özel Tabloları
- `WMS_PICKQUEUE` - Geçici barkod okutma kuyruğu
- `shipment_header` - Sevkiyat başlıkları
- `shipment_lines` - Sevkiyat satırları (tek doğruluk kaynağı)
- `shipment_loaded` - Yüklenen paketler
- `backorders` - Eksik siparişler
- `USER_ACTIVITY` - Kullanıcı aktiviteleri

### Backorders Tablo Yapısı
```sql
CREATE TABLE backorders (
    id INT IDENTITY(1,1) PRIMARY KEY,
    order_no NVARCHAR(32),
    item_code NVARCHAR(64),
    qty_missing FLOAT,
    qty_scanned FLOAT DEFAULT 0,    -- Okutulan miktar
    scanned_by NVARCHAR(50),         -- Kim okuttu
    scanned_at DATETIME,             -- Ne zaman okutuldu
    fulfilled BIT DEFAULT 0,
    fulfilled_at DATETIME
)
```

## 🔄 Veri Akışları

### 1. Normal Scanner Akışı (SM Siparişler)
```
Barkod Okutma 
    ↓
WMS_PICKQUEUE (geçici)
    ↓
finish_order()
    ↓
shipment_lines (kalıcı) + backorders (eksikler)
    ↓
Logo STATUS = 4
```

### 2. Backorder Akışı (SO/SA/SE Siparişler)
```
Backorder Barkod Okutma
    ↓
mark_fulfilled(id, qty_scanned, scanned_by)
    ↓
backorders tablosu güncellenir
    ↓
shipment_lines'a yazılır (fulfilled olunca)
```

### 3. Geçmiş Görüntüleme
```
Scanner Geçmiş
    ↓
shipment_lines'dan SUM(qty_sent)
    ↓
Durum hesaplama (completion %)
```

## 🔧 Kritik Fonksiyonlar

### scanner_page.py
- `load_order()` - Sipariş yükleme
- `on_scan()` - Barkod okutma
- `finish_order()` - Sipariş tamamlama
- `_get_order_details_real()` - Geçmiş detayları

### backorder.py
- `mark_fulfilled(id, qty_scanned, scanned_by)` - Backorder tamamlama
- `insert_backorder()` - Eksik kaydetme
- `add_shipment()` - Sevkiyat kaydı

### shipment_safe_sync.py
- `safe_sync_packages(trip_id, new_pkg_total)` - Güvenli paket senkronizasyonu
  - Yüklenmiş paketleri korur
  - Sadece boş paketleri değiştirir

## 📊 Durum Mantığı

### Sipariş Durumları
- `STATUS = 1` - Taslak
- `STATUS = 2` - İşlemde (Pick-list oluşturuldu)
- `STATUS = 4` - Tamamlandı (Tam veya Eksik)

### Geçmiş Durum Gösterimi
- **✅ Tamamlandı** - %100 gönderildi
- **⚠️ Eksik Kapatıldı** - STATUS=4 ama %100'den az
- **🔄 İşlemde (%)** - Kısmen okutulmuş
- **⏳ Bekliyor** - Henüz başlanmamış

## 🐛 Bilinen Sorunlar ve Çözümler

### 1. Tablo İsimlendirme
- `ORFICHE`, `ORFLINE` → period-dependent (01 ile)
- `ITEMS` → period-independent (01 olmadan)
```python
_t('ORFICHE')  # LG_025_01_ORFICHE
_t('ITEMS', period_dependent=False)  # LG_025_ITEMS
```

### 2. Kolon İsimleri
- ORFLINE'da `LINENO_` (altçizgi ile)
- activity_log değil `USER_ACTIVITY`

### 3. Kalem Sayısı
- UI'de benzersiz ürün sayısı gösterilir
```sql
COUNT(DISTINCT CASE WHEN ol.CANCELLED = 0 AND ol.STOCKREF > 0 AND ol.AMOUNT > 0 THEN ol.STOCKREF END)
```

### 4. Çift Sayma Önleme
- Geçmiş sorgularında sadece shipment_lines kullan
- Backorder fulfilled olanlar zaten shipment_lines'da

## 🔐 Güvenlik Önlemleri

### 1. SQL Injection Koruması
- Tüm sorgular parametreli
- String concatenation yok

### 2. Race Condition Koruması
```sql
WITH (UPDLOCK, ROWLOCK)  -- Satır seviyesi kilitleme
```

### 3. Transaction Yönetimi
```python
with transaction_scope() as cursor:
    # Atomic işlemler
```

### 4. Paket Koruması
- Yüklenmiş paketler (loaded=1) silinemez
- max_loaded_pkg kontrolü yapılır

## 🚀 Komutlar ve Test

### Veritabanı Kontrolleri
```sql
-- Backorder kolonları kontrol
SELECT TOP 1 qty_scanned, scanned_by, scanned_at FROM backorders

-- Shipment_lines kontrol
SELECT * FROM shipment_lines WHERE order_no = 'XXX' ORDER BY id DESC

-- Geçmiş veri kontrol
SELECT * FROM shipment_lines sl
INNER JOIN backorders bo ON sl.order_no = bo.order_no
WHERE sl.order_no = 'XXX'
```

### Python Test
```python
# Backorder tamamlama
from app.backorder import mark_fulfilled
mark_fulfilled(backorder_id, qty_scanned=10, scanned_by='user')

# Paket senkronizasyonu
from app.shipment_safe_sync import safe_sync_packages
result = safe_sync_packages(trip_id, new_pkg_total)
print(result['message'])
```

## 📝 Son Güncellemeler (2025-08-30)

1. **Backorder Entegrasyonu**
   - qty_scanned, scanned_by, scanned_at kolonları eklendi
   - mark_fulfilled() shipment_lines'a yazıyor
   - Geçmiş görüntüleme düzeltildi

2. **UI İyileştirmeleri**
   - Kalem sayısı benzersiz ürün gösteriyor
   - Durum gösterimi completion % bazlı
   - Boş STOCKREF'ler filtreleniyor

3. **Güvenlik İyileştirmeleri**
   - safe_sync_packages merkezi fonksiyon
   - Transaction scope eklendi
   - Race condition koruması

## 🎯 Dikkat Edilecekler

1. **Sipariş Tipleri**
   - SM → Merkez siparişleri (depoda var)
   - SO/SA/SE → Müşteri siparişleri (backorder olabilir)

2. **Veri Bütünlüğü**
   - shipment_lines tek doğruluk kaynağı
   - WMS_PICKQUEUE geçici veri
   - backorders kalıcı eksik takibi

3. **Performance**
   - Connection pool kullanılıyor
   - Batch işlemler için transaction
   - Index'ler order_no ve item_code üzerinde

## 🏗️ Build ve Derleme (PyInstaller)

### Tek EXE Oluşturma
```batch
pyinstaller --clean --noconfirm wms.spec
```

### Önemli Build Konfigürasyonları

#### 1. Dosya Yolları ve WMS Klasör Yapısı
- **TÜM dosyalar** `C:\Users\[Kullanıcı]\Documents\WMS\` altında oluşturulur
- EXE yanında klasör oluşturulmaz, sadece Documents/WMS kullanılır
```
Documents/WMS/
├── labels/          # Etiketler
├── picklists/       # Sevkiyat listeleri  
├── reports/         # Raporlar
├── exports/         # Dışa aktarmalar
├── logs/            # Log dosyaları
├── backups/         # Yedekler
├── temp/            # Geçici dosyalar
└── settings.json    # Ayarlar
```

#### 2. Kritik Import Düzeltmeleri
- `app.utils.wms_paths` modülünde `get_resource_path()` fonksiyonu eklendi
- `loader_page.py`'ye `sys` import eklendi
- Tüm reportlab barcode modülleri wms.spec'e eklendi:
  - code128, code93, code39, common, dmtx
  - eanbc, ecc200datamatrix, fourstate, lto
  - qr, qrencoder, usps, **usps4s**, widgets

#### 3. wms.spec Konfigürasyonu
- 100+ hidden import tanımlı
- Font dosyaları: DejaVuSans.ttf dahil
- Ses dosyaları: .wav dosyaları dahil
- .env dosyası otomatik dahil edilir
- collect_submodules ile tüm app modülleri toplanır

#### 4. Path Yönetimi Düzeltmeleri
```python
# main.py - WMS logs kullanımı
from app.utils.wms_paths import get_wms_folders
wms_folders = get_wms_folders()
LOG_DIR = wms_folders['logs']

# settings_manager.py - Sabit WMS dizini
WMS_DIR = Path.home() / "Documents" / "WMS"
SETTINGS_FILE = WMS_DIR / "settings.json"

# build_config.py - Documents/WMS kullanımı
wms_dir = Path.home() / "Documents" / "WMS"
```

### Build Sorun Giderme

#### Python 3.13 Uyumluluk
- pandas ve numpy için sabit sürüm yerine latest kullan
- PyQt5-sip wheel sorunları için pip upgrade gerekli

#### Font ve Türkçe Karakter Desteği
- Tüm PDF servislerinde çoklu font path denemesi
- Frozen mode desteği (`sys._MEIPASS`)
- Helvetica fallback sistemi

#### Eksik Modül Hataları
- wms.spec hiddenimports listesine modül ekle
- collect_submodules kullan
- `__all__` export listesi ekle

### Dağıtım Gereksinimleri
1. .env dosyası exe yanında olmalı
2. ODBC Driver 17 for SQL Server kurulu olmalı
3. Visual C++ Redistributable 2015-2022 gerekebilir

## 📞 İletişim ve Destek

Sorun durumunda kontrol edilecekler:
1. .env dosyası doğru mu?
2. SQL Server bağlantısı var mı?
3. Tablolar oluşturulmuş mu?
4. Logo ERP STATUS değerleri doğru mu?
5. Documents/WMS klasörü oluşturuldu mu?
6. Tüm bağımlılıklar exe'ye dahil edildi mi?

---
*Son güncelleme: 2025-09-01*
*WMS Version: 2.0*
*Build System: PyInstaller 6.15.0*