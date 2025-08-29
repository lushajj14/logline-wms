# Pagination Implementation Guide

## 📊 Tamamlananlar

### ✅ 1. Backend Pagination Altyapısı
- `app/dao/pagination.py` - Pagination helper sınıfı
- SQL Server OFFSET/FETCH NEXT desteği
- Paginated DAO fonksiyonları:
  - `fetch_draft_orders_paginated()`
  - `fetch_picking_orders_paginated()`
  - `fetch_loaded_orders_paginated()`

### ✅ 2. UI Widget
- `app/ui/widgets/pagination_widget.py` - Reusable pagination kontrolü
- Önceki/Sonraki butonları
- Sayfa numarası girişi
- Sayfa boyutu seçimi (10, 25, 50, 100, 200)
- Toplam kayıt gösterimi

## 🎯 Kullanım Örneği

### Backend Kullanımı

```python
from app.dao.pagination import fetch_draft_orders_paginated

# Sayfalanmış veri getir
result = fetch_draft_orders_paginated(
    page=1,
    page_size=50,
    search="müşteri adı"
)

# Sonuç yapısı
data = result['data']  # Siparişler listesi
pagination = result['pagination']  # Pagination metadata
# {
#     'total_count': 500,
#     'page_size': 50,
#     'current_page': 1,
#     'total_pages': 10,
#     'has_next': True,
#     'has_previous': False,
#     'start_index': 1,
#     'end_index': 50
# }
```

### UI Entegrasyonu

```python
from app.ui.widgets.pagination_widget import PaginationWidget
from app.dao.pagination import fetch_picking_orders_paginated

class MyPage(QWidget):
    def __init__(self):
        super().__init__()
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Tablo
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        # Pagination widget
        self.pagination = PaginationWidget()
        self.pagination.pageChanged.connect(self.load_page)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)
        layout.addWidget(self.pagination)
        
        # İlk veriyi yükle
        self.load_page(1)
    
    def load_page(self, page_number):
        """Belirtilen sayfayı yükle."""
        result = fetch_picking_orders_paginated(
            page=page_number,
            page_size=self.pagination.get_page_size()
        )
        
        # Tabloyu güncelle
        self.update_table(result['data'])
        
        # Pagination kontrollerini güncelle
        self.pagination.update_pagination(result['pagination'])
    
    def on_page_size_changed(self, new_size):
        """Sayfa boyutu değiştiğinde ilk sayfaya dön."""
        self.load_page(1)
    
    def update_table(self, data):
        """Tabloyu yeni veriyle güncelle."""
        self.table.setRowCount(len(data))
        for row, item in enumerate(data):
            # Tablo hücrelerini doldur
            pass
```

## 🔧 Mevcut Sayfaları Güncelleme

### 1. PickList Sayfası
```python
# app/ui/pages/picklist_page.py

# Eski kod:
rows = fetch_draft_orders(limit=500)

# Yeni kod:
result = fetch_draft_orders_paginated(
    page=self.current_page,
    page_size=50
)
rows = result['data']
self.pagination_widget.update_pagination(result['pagination'])
```

### 2. Scanner Sayfası
```python
# app/ui/pages/scanner_page.py

# Eski kod:
orders = fetch_picking_orders(limit=200)

# Yeni kod:
result = fetch_picking_orders_paginated(
    page=1,
    page_size=50
)
orders = result['data']
```

### 3. Loader Sayfası
```python
# app/ui/pages/loader_page.py

# Eski kod:
orders = fetch_loaded_orders()

# Yeni kod:
result = fetch_loaded_orders_paginated(
    page=self.current_page,
    page_size=100,
    trip_date=today
)
orders = result['data']
```

## 📈 Performans İyileştirmeleri

### Öncesi
- Tüm kayıtlar memory'e yükleniyor
- 500+ kayıtta UI donuyor
- Memory kullanımı kontrolsüz

### Sonrası
- Sadece görünen sayfa yükleniyor
- Hızlı tablo güncellemeleri
- Kontrollü memory kullanımı
- Daha iyi kullanıcı deneyimi

## 🔍 API Endpoint Örnekleri

### FastAPI Entegrasyonu
```python
from fastapi import Query
from app.dao.pagination import fetch_picking_orders_paginated

@app.get("/api/orders/picking")
def get_picking_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    search: str = Query(None)
):
    """Paginated picking orders endpoint."""
    return fetch_picking_orders_paginated(
        page=page,
        page_size=page_size,
        search=search
    )
```

## ⚙️ Konfigürasyon

### Varsayılan Değerler
```python
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
MIN_PAGE_SIZE = 10
```

### Özelleştirme
```python
# Settings'e eklenebilir
PAGINATION_CONFIG = {
    'default_page_size': 50,
    'page_size_options': [10, 25, 50, 100, 200],
    'max_page_size': 500,
    'enable_infinite_scroll': False
}
```

## 🚀 Sonraki Adımlar

1. **Tüm sayfalara entegrasyon**
   - [ ] PickList sayfası
   - [ ] Scanner sayfası
   - [ ] Loader sayfası
   - [ ] Dashboard

2. **Gelişmiş özellikler**
   - [ ] Search/filter integration
   - [ ] Sort column support
   - [ ] Export current page/all pages
   - [ ] Keyboard shortcuts (PgUp/PgDn)

3. **Performance tuning**
   - [ ] Query optimization
   - [ ] Index recommendations
   - [ ] Cache implementation

## 💡 Best Practices

1. **Her zaman ORDER BY kullan** - SQL Server OFFSET için zorunlu
2. **Makul page size limitleri** - 10-200 arası
3. **Total count cache'le** - Her sayfada count query çalıştırma
4. **Loading state göster** - Kullanıcı beklerken feedback ver
5. **Error handling** - Network hataları için retry mekanizması