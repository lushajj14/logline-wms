# LOGLine Depo Yönetim Sistemi - Teknik ve İşlevsel Döküman

## 1. Özet

LOGLine WMS, Logo ERP entegrasyonlu bir depo yönetim sistemidir. Masaüstü (PyQt5), Mobil API (FastAPI) ve Merkezi Konfigürasyon sunucularından oluşan 3-katmanlı mimari üzerine kuruludur. Depo operatörleri barkodla sipariş toplama, paketleme ve sevkiyat yönetimi yaparken, kargo sürücüleri mobil uygulama üzerinden teslimat takibi yapar, yöneticiler ise raporlama ve analiz araçlarını kullanır. Sistem, çoklu kullanıcı desteği ile eşzamanlı operasyonlarda veri tutarlılığını database-level lock mekanizmaları ve atomic transaction'lar ile sağlar.

## 2. Ekranlar & İş Akışları

| Ekran | Kullanıcı | Amaç | Ana Adımlar | Hatalar/Edge Case |
|-------|-----------|------|-------------|-------------------|
| **Sipariş Hazırlama** (scanner_page) | Depo Operatörü | STATUS=2 siparişleri barkodla toplama | 1. Sipariş seçimi (combo)<br>2. Ürün barkodu okutma<br>3. qty_sent artışı (atomic)<br>4. Tamamla → Sevkiyat oluştur | • Yanlış ürün: Kırmızı uyarı + ses<br>• Eksik stok: Backorder kaydı<br>• Fazla okutma: Tolerance kontrolü<br>• Eşzamanlı okutma: sp_getapplock ile kilit |
| **Kargo Etiketi** (label_page) | Depo Operatörü | 100x100mm etiket basımı | 1. Sipariş seç<br>2. Paket sayısı gir<br>3. PDF oluştur (Code128)<br>4. Yazıcıya gönder | • Yazıcı hatası: Retry mekanizması<br>• Türkçe karakter: DejaVuSans font<br>• Çoklu paket: Her biri için ayrı sayfa |
| **Yükleme** (loader_page) | Depo Operatörü | Araç yükleme takibi | 1. QR/Barkod okut<br>2. Paketleri tara<br>3. shipment_loaded güncelle<br>4. Otomatik kapanış | • Eksik paket: Uyarı listesi<br>• Fazla paket: Red ile işaretle<br>• Çift okutma: MERGE ile önleme |
| **Picklist** (enhanced_picklist_page) | Depo Sorumlusu | Toplama listesi PDF'i | 1. Tarih aralığı seç<br>2. Siparişleri işaretle<br>3. PDF oluştur<br>4. WMS_PICKQUEUE'ya ekle | • Büyük liste: Pagination (50'li)<br>• Logo bağlantı hatası: Fallback cache<br>• PDF boyutu: >10MB uyarısı |
| **Kullanıcı Yönetimi** (user_management_page) | Admin | RBAC yetkilendirme | 1. Kullanıcı ekle/düzenle<br>2. Rol ata (admin/operator)<br>3. Şifre sıfırla<br>4. Aktivite logları | • Şifre politikası: Min 8 karakter<br>• Başarısız giriş: 5 deneme sonrası kilit<br>• Oturum süresi: 120 dakika JWT |
| **Dashboard** | Yönetici | KPI takibi | 1. Günlük/haftalık özet<br>2. Performans metrikleri<br>3. Canlı durum takibi | • Veri yenileme: 30sn auto-refresh<br>• Ağır sorgu: Background worker<br>• Grafik hatası: Fallback tablo görünümü |
| **Mobil Teslimat** (API) | Kargo Sürücüsü | Teslimat onayı | 1. QR okut (trip_id)<br>2. Paketleri tara<br>3. Teslimat notu gir<br>4. GPS konum kaydet | • Offline mod: Local queue + sync<br>• GPS hatası: Manuel adres girişi<br>• Çoklu teslimat: Bulk update |

### Çoklu Kullanıcı Eşzamanlılık Kontrolü

| Senaryo | Çözüm | Teknik Detay |
|---------|-------|--------------|
| 2 operatör aynı siparişi tarar | Application lock | `sp_getapplock('WMS_SCAN_{order}_{item}', 'Exclusive', 5000)` |
| Aynı anda order completion | Completion lock | `WMS_COMPLETE_{order_id}` kilidi, 5sn timeout |
| Race condition qty_sent update | Row-level lock | `WITH (UPDLOCK, ROWLOCK)` + MERGE statement |
| Concurrent shipment creation | Atomic upsert | `sp_wms_safe_sync_packages` ile idempotent işlem |
| Audit trail | WMS_SCAN_AUDIT | Her atomic işlem user, timestamp, version ile loglanır |

## 3. Kimlik Doğrulama & Yetkilendirme (RBAC)

| Rol | Masaüstü İzinleri | API İzinleri | Özel Yetkiler |
|-----|-------------------|--------------|---------------|
| **Admin** | Tüm ekranlar + ayarlar | Tüm endpointler | • Kullanıcı yönetimi<br>• Sistem konfig<br>• Veri silme |
| **Supervisor** | Operasyon ekranları | Raporlama + teslimat | • Picklist onayı<br>• Backorder yönetimi |
| **Operator** | Scanner, Label, Loader | - | • Sipariş toplama<br>• Etiket basma |
| **Viewer** | Dashboard, Raporlar | GET endpointler | • Sadece görüntüleme |
| **Driver** | - | Mobil teslimat API | • GPS tracking<br>• Teslimat onayı |

**Güvenlik Özellikleri:**
- **Şifre**: bcrypt hash (salt: auto-generated)
- **JWT Token**: HS256, 120dk expiry
- **Failed Login**: 5 deneme → 30dk kilit
- **Audit Log**: `WMS_KULLANICILAR_LOG` tablosunda tüm işlemler
- **Session**: Desktop Windows auth fallback, API JWT zorunlu

## 4. API Sözleşmesi

| Metod | URL | Auth | İstek | Yanıt | Hata Kodları |
|-------|-----|------|-------|--------|--------------|
| **POST** | `/auth/login` | - | `{username, password}` | `{access_token, user: {id, name, role}}` | 401: Invalid credentials<br>423: Account locked |
| **GET** | `/trips` | JWT | - | `[{trip_id, customer, pkgs_total, pkgs_loaded}]` | 401: Unauthorized<br>404: No trips found |
| **POST** | `/scan/qr` | JWT | `{qr_code}` | `{trip_id, customer_name, packages}` | 400: Invalid QR<br>404: Trip not found |
| **POST** | `/load_pkgs` | JWT | `{pkgs: [{barcode, delivered}]}` | `{loaded: 5, failed: [], auto_closed: true}` | 409: Already loaded<br>422: Invalid barcode |
| **POST** | `/set_delivery_note` | JWT | `{trip_id, note, delivered_to}` | `{success: true, updated_count: 1}` | 404: Trip not found<br>400: Already closed |
| **GET** | `/stats` | JWT | - | `{total_trips, delivered, pending, rate: 85.5}` | 500: Database error |
| **POST** | `/gps/track` | JWT | `{trip_id, lat, lon, timestamp}` | `{logged: true, distance_km: 12.5}` | 400: Invalid coordinates |

### Örnek Request/Response

**Sipariş Toplama Başlatma:**
```json
// Request: POST /api/order/start-picking
{
  "order_no": "ORF-2024-001234",
  "user_id": 42,
  "warehouse": "SM"
}

// Response:
{
  "queue_id": "QUE-20240115-0834",
  "order_lines": [
    {"item_code": "MAL001", "description": "Ürün A", "qty_ordered": 10, "qty_sent": 0},
    {"item_code": "MAL002", "description": "Ürün B", "qty_ordered": 5, "qty_sent": 0}
  ],
  "total_items": 2,
  "session_lock": "WMS_SCAN_ORF-2024-001234"
}
```

**Barkod Okutma (Atomic):**
```json
// Request: POST /api/scan/barcode
{
  "order_no": "ORF-2024-001234",
  "barcode": "8690123456789",
  "user_id": 42
}

// Response (Success):
{
  "matched_item": "MAL001",
  "qty_updated": 1,
  "total_scanned": 1,
  "remaining": 9,
  "audio": "success.wav"
}

// Response (Error):
{
  "error": "ITEM_NOT_IN_ORDER",
  "message": "Bu ürün siparişte yok",
  "audio": "error.wav",
  "suggestions": ["MAL001", "MAL002"]
}
```

## 5. Veri Modeli & SQL

### Logo ERP Tabloları (Okuma)

| Tablo | Açıklama | Kritik Alanlar |
|-------|----------|----------------|
| `LG_025_01_ORFICHE` | Sipariş ana | LOGICALREF, FICHENO, STATUS, CLIENTREF, DATE_ |
| `LG_025_01_ORFLINE` | Sipariş satırları | STOCKREF, AMOUNT, PRICE, SHIPPEDAMOUNT |
| `LG_025_01_STLINE` | Stok hareketleri | STOCKREF, IOCODE, AMOUNT, DATE_, INVOICEREF |
| `LG_025_CLCARD` | Müşteri kartları | CODE, DEFINITION_, ADDR1, CITY, COUNTRY |
| `LG_025_ITEMS` | Stok kartları | CODE, NAME, UNITSETREF, VAT |

### WMS Özel Tabloları

| Tablo | Açıklama | Transaction/Lock Stratejisi |
|-------|----------|-----------------------------|
| `WMS_PICKQUEUE` | Aktif toplama kuyruğu | MERGE + version stamp, 5dk TTL |
| `WMS_KULLANICILAR` | Kullanıcı yönetimi | bcrypt hash, failed_attempts counter |
| `WMS_SCAN_AUDIT` | Eşzamanlı işlem logu | INSERT only, 30 gün retention |
| `shipment_header` | Sevkiyat başlıkları | UPSERT with safe_sync procedure |
| `shipment_loaded` | Yüklenen paketler | MERGE prevent duplicates |
| `barcode_xref` | Özel barkod eşlemeleri | READ with NOLOCK for performance |

### Trigger'lar

| Trigger | Tablo | Tetiklenme | İşlev |
|---------|-------|------------|--------|
| `trg_NetMaliyet` | STLINE | INSERT/UPDATE | Net maliyet hesaplama (KDV düşümü) |
| `trg_DepoCorrection` | ORFLINE | UPDATE AMOUNT | Depo miktarı otomatik düzeltme |
| `trg_AuditLog` | WMS_KULLANICILAR | INSERT/UPDATE/DELETE | Kullanıcı değişiklik logu |
| `trg_VersionStamp` | WMS_PICKQUEUE | UPDATE | Optimistic concurrency version artışı |

### Eşzamanlı Stok Toplama Stratejisi

```sql
-- sp_wms_atomic_scan prosedürü
BEGIN TRAN
  -- 1. Application lock al
  EXEC sp_getapplock @Resource = 'WMS_SCAN_ORDER_ITEM',
                     @LockMode = 'Exclusive',
                     @LockTimeout = 5000

  -- 2. Row-level lock ile oku
  SELECT @current_qty = qty_sent
  FROM WMS_PICKQUEUE WITH (UPDLOCK, ROWLOCK)
  WHERE order_no = @order AND item_code = @item

  -- 3. Over-scan kontrolü
  IF @current_qty + 1 > @qty_ordered + @tolerance
    ROLLBACK; RETURN -1

  -- 4. Atomic güncelleme
  UPDATE WMS_PICKQUEUE
  SET qty_sent = @current_qty + 1,
      version = version + 1,
      last_scan_user = @user,
      last_scan_time = GETDATE()
  WHERE order_no = @order AND item_code = @item

  -- 5. Audit log
  INSERT INTO WMS_SCAN_AUDIT (...) VALUES (...)

COMMIT TRAN
```

## 6. Barkod & Etiketleme

| Özellik | Detay | Konfigürasyon |
|---------|-------|---------------|
| **Barkod Türleri** | EAN-13, Code128, QR Code | `app/services/barcode_service.py` |
| **Donanım** | USB Scanner (HID), El Terminali (Serial) | Auto-detect via PyQt5 |
| **Prefix Routing** | SM→Ana Depo, SA→Depo A, SO→Online | `WAREHOUSE_PREFIXES` dict |
| **Özel Eşleme** | `barcode_xref` tablosu, multiplier desteği | Örn: 1 barkod = 12 adet |
| **Etiket Boyutu** | 100mm × 100mm | ReportLab canvas |
| **Yazıcı** | ZPL (Zebra), PDF (Laser) | `app/utils/printer_utils.py` |
| **Şablon Alanları** | `{ORDER_NO}`, `{CUSTOMER}`, `{DATE}`, `{PKG_NO}` | Jinja2 template |
| **Yazdırma Kuyruğu** | Windows Spooler integration | win32print API |
| **Retry Logic** | 3 deneme, 2sn ara | Exponential backoff |

### Kargo Entegrasyonu Alanları

| Kargo Firması | Özel Alanlar | Format |
|---------------|--------------|--------|
| MNG Kargo | Gonderi No, Referans | 12 haneli numerik |
| Yurtiçi | Takip No, Musteri No | Prefix + 9 hane |
| Aras | Sefer No, Alıcı Tel | Barcode128 zorunlu |
| PTT | Posta Kodu, Desi | 5+5 format |

## 7. Raporlama

| Rapor | Format | Zamanlama | İçerik |
|-------|--------|-----------|--------|
| **Günlük Özet** | Excel/PDF | Her gün 18:00 | Toplanan/sevk edilen siparişler, performans |
| **Stok Durumu** | Excel | Haftalık | Logo stok - WMS hareketi karşılaştırması |
| **Backorder** | PDF | Anlık | Eksik kalan ürünler, tedarikçi bazlı |
| **Teslimat Performansı** | Dashboard | Real-time | GPS bazlı rota analizi, yakıt tüketimi |
| **Kullanıcı Aktivitesi** | CSV | Günlük | Login/logout, işlem sayıları, hatalar |
| **Kargo Takip** | Excel | 2x gün | Teslim edilmeyen, iade, hasarlı |

## 8. Zamanlanmış Görevler & Entegrasyonlar

| Görev | Zaman | Script/Procedure | Hata Bildirimi |
|-------|-------|------------------|----------------|
| **Logo Sync** | Her 15dk | `sync_logo_orders.py` | Email + SMS |
| **TCMB Kur** | 09:00, 15:00 | `fetch_exchange_rates.py` | Fallback: önceki gün |
| **OEM Stok** | Her saat | `oem_integration.py` | Webhook to Slack |
| **Yedekleme** | 02:00 | SQL Agent Job | Admin email |
| **Queue Temizleme** | Her 30dk | `sp_wms_cleanup_queue` | Log only |
| **Session Cleanup** | Her 5dk | `cleanup_expired_sessions.py` | - |
| **GPS Aggregate** | Gece 01:00 | `aggregate_gps_data.sql` | Dashboard alert |

### Logo ERP Entegrasyon Noktaları

| İşlem | Okuma | Yazma | Rollback |
|-------|-------|-------|----------|
| Sipariş Import | ORFICHE/ORFLINE | - | - |
| Status Update | - | ORFICHE.STATUS=4 | Transaction rollback |
| Stok Kontrolü | ITEMS, STLINE | - | - |
| Fatura Oluşturma | - | INVOICE, STLINE | sp_rollback_invoice |
| Müşteri Bilgisi | CLCARD | CLCARD.ADDR1 (GPS) | - |

## 9. Konfigürasyon & Ortamlar

### Environment Variables (.env keys - değerler gizli)

| Key | Açıklama | Dev | Prod |
|-----|----------|-----|------|
| `LOGO_SQL_SERVER` | Logo DB sunucusu | localhost | 192.168.5.100,1433 |
| `LOGO_SQL_DB` | Veritabanı adı | logo_test | logo |
| `LOGO_COMPANY_NR` | Firma kodu | 025 | 025 |
| `LOGO_PERIOD_NR` | Dönem | 01 | 01 |
| `API_SECRET` | JWT secret key | dev-secret | [REDACTED] |
| `DB_POOL_MIN` | Min connection | 1 | 2 |
| `DB_POOL_MAX` | Max connection | 5 | 10 |
| `CONFIG_SERVER` | Config URL | http://localhost:8001 | http://192.168.5.100:8001 |
| `UI_AUTO_REFRESH` | Saniye | 60 | 30 |
| `SCANNER_TOLERANCE` | Fazla okutma | 2 | 0 |
| `ENABLE_GPS` | GPS tracking | false | true |

### Yazıcı & Network Paylaşımları

| Ayar | Konum | Format |
|------|-------|--------|
| Label Printer | `\\\\PRINT-SERVER\\Zebra-ZT410` | ZPL |
| PDF Printer | `\\\\PRINT-SERVER\\HP-LaserJet` | PDF |
| Backup Path | `\\\\NAS\\WMS-Backup\\` | SQL BAK |
| Log Share | `\\\\LOG-SERVER\\WMS\\` | Rolling files |

## 10. Bağımlılıklar

| Paket | Versiyon | Amaç | Lisans |
|-------|----------|------|--------|
| **PyQt5** | 5.15.10 | Desktop UI framework | GPL v3 |
| **FastAPI** | 0.109.0 | REST API backend | MIT |
| **pyodbc** | 5.0.1 | SQL Server connection | MIT |
| **reportlab** | 4.0.9 | PDF generation | BSD |
| **python-jose** | 3.3.0 | JWT authentication | MIT |
| **bcrypt** | 4.1.2 | Password hashing | Apache 2.0 |
| **qrcode** | 7.4.2 | QR code generation | MIT |
| **pandas** | 2.1.4 | Data processing | BSD |
| **uvicorn** | 0.27.0 | ASGI server | BSD |
| **Pillow** | 10.2.0 | Image processing | HPND |
| **openpyxl** | 3.1.2 | Excel reports | MIT |
| **PyInstaller** | 6.3.0 | EXE build | GPL |
| **python-dotenv** | 1.0.0 | Environment config | BSD |
| **psutil** | 5.9.7 | System monitoring | BSD |
| **requests** | 2.31.0 | HTTP client | Apache 2.0 |

## 11. Test & Kabul Kriterleri

| Test Türü | Kapsam | Araçlar | Kabul Kriteri |
|-----------|--------|---------|---------------|
| **Unit Tests** | DAO, Services | pytest | Coverage >80% |
| **Integration** | API endpoints | pytest + httpx | All endpoints 2xx |
| **UI Tests** | PyQt5 screens | pytest-qt | No crashes, memory <500MB |
| **Load Test** | Concurrent users | locust | 50 users, <2s response |
| **UAT Senaryoları** | End-to-end | Manual | 100 sipariş/0 hata |

### Manuel Test Senaryoları

1. **Çoklu Operatör**: 3 kullanıcı aynı anda farklı siparişler
2. **Yoğun Barkod**: 100 barkod/dakika okutma
3. **Ağ Kesintisi**: Offline mode + sync recovery
4. **Yazıcı Hatası**: Kuyruk yönetimi + retry
5. **GPS Kesintisi**: Manuel konum girişi
6. **Büyük Sipariş**: 500+ satırlı sipariş performansı

### Başarı Metrikleri

- Sipariş tamamlama: <10 dakika (50 satır)
- Hata oranı: <%0.5
- Eşzamanlı kullanıcı: 20+
- Uptime: %99.5
- DB response: <500ms (p95)

## 12. Performans & NFR

| Metrik | Hedef | Mevcut | Optimizasyon |
|--------|-------|--------|--------------|
| **Sipariş/Gün** | 500 | 350 | Batch processing |
| **Satır/Saat** | 1000 | 850 | Index tuning |
| **Barkod Response** | <100ms | 85ms | Memory cache |
| **PDF Generation** | <3s | 2.5s | Async workers |
| **API Latency (p95)** | <500ms | 420ms | Connection pool |
| **DB Pool Size** | 2-10 | 2-10 | Dynamic scaling |
| **Retry Strategy** | 3x, 2s backoff | Implemented | Circuit breaker |
| **Queue Size** | 1000 items | Unlimited | Redis consideration |
| **Print Queue** | 50 jobs | Windows default | Custom spooler |

### Database İndeksler

```sql
-- Performance kritik indeksler
CREATE INDEX IX_PICKQUEUE_ORDER_STATUS ON WMS_PICKQUEUE(order_no, status)
CREATE INDEX IX_AUDIT_TIMESTAMP ON WMS_SCAN_AUDIT(scan_timestamp DESC)
CREATE INDEX IX_SHIPMENT_DATE ON shipment_header(shipment_date, closed)
CREATE INDEX IX_BARCODE_LOOKUP ON barcode_xref(barcode_value) INCLUDE (stock_code)
```

## 13. Değişiklik Özeti (DELTA)

### Çoklu Kullanıcı Desteği (v2.0)

| Özellik | Eski | Yeni | Etki |
|---------|------|------|------|
| **Login** | Windows auth | RBAC + bcrypt | Rol bazlı yetki |
| **Scanner Lock** | - | sp_getapplock | Race condition önleme |
| **Audit Trail** | - | WMS_SCAN_AUDIT | Kim, ne zaman, ne yaptı |
| **Connection Pool** | Single | Thread-safe pool | 10x performans |
| **Order Completion** | Sync | Background worker | UI donma önleme |
| **Over-scan Control** | - | Tolerance setting | Hatalı okutma önleme |
| **Concurrent Shipment** | Manual lock | Atomic MERGE | Data integrity |

### API Eklemeleri

- `/api/users/activity` - Kullanıcı aktivite logu
- `/api/locks/status` - Aktif kilit durumu
- `/api/system/health` - Sistem sağlık kontrolü
- `/api/bulk/orders` - Toplu sipariş işlemleri

### Tablo Değişiklikleri

- `WMS_PICKQUEUE`: +version, +last_scan_user, +last_scan_time
- `WMS_KULLANICILAR`: +failed_attempts, +locked_until, +last_activity
- `shipment_header`: +created_by, +modified_by, +sync_status

## 14. Riskler & Açık Konular

| Risk | Olasılık | Etki | Azaltma |
|------|----------|------|---------|
| **Yazıcı arızası** | Orta | Yüksek | Yedek yazıcı, PDF fallback |
| **Wi-Fi kesintisi** | Yüksek | Orta | Offline queue + sync |
| **Deadlock** | Düşük | Yüksek | Lock timeout + retry |
| **Yanlış stok eşleme** | Düşük | Kritik | barcode_xref validation |
| **Barkod çakışması** | Çok düşük | Orta | Unique constraint |
| **GPS yanılma** | Orta | Düşük | Manuel düzeltme |
| **Token çalınması** | Düşük | Yüksek | Refresh token + IP check |
| **DB connection pool tükenmesi** | Düşük | Yüksek | Circuit breaker |
| **Büyük PDF bellek hatası** | Düşük | Orta | Streaming + pagination |

### Teknik Borç

1. **TODO**: Redis cache implementation için altyapı var, impl yok
2. **FIXME**: GPS aggregation memory leak (>1M kayıt)
3. **OPTIMIZE**: Picklist PDF generation batch processing
4. **SECURITY**: API rate limiting implementation bekliyor
5. **UPGRADE**: PyQt5 → PyQt6 migration planı

## 15. Kapsam Dışı

- E-fatura entegrasyonu (kod var, aktif değil)
- RFID tag desteği (tablo yapısı hazır)
- Blockchain kayıt (araştırma aşaması)
- AI-bazlı demand forecasting (TODO comment)
- Multi-warehouse transfer (partial implementation)
- Mobile native app (sadece web API)
- Real-time video tracking (GPS only)

## 16. Zaman & Efor Tahmini

| Başlık | Adam-Saat | Öncelik | Bağımlılık |
|--------|-----------|---------|------------|
| **RBAC Implementasyonu** | 24-36h | Kritik | Tamamlandı ✓ |
| **Etiket Hattı Sertleştirme** | 10-16h | Yüksek | Yazıcı driver |
| **Redis Cache** | 20-30h | Orta | Infrastructure |
| **API Rate Limiting** | 8-12h | Yüksek | Security audit |
| **GPS Optimization** | 16-24h | Düşük | Memory profiling |
| **PyQt6 Migration** | 40-60h | Düşük | Major version |
| **E-Fatura** | 30-45h | Orta | GIB onayı |
| **RFID Integration** | 50-80h | Düşük | Hardware |
| **Load Balancing** | 20-30h | Orta | Multi-instance |
| **Monitoring Dashboard** | 15-20h | Yüksek | Grafana setup |

### Backlog Önerisi (Değer/Risk)

1. **API Rate Limiting** - Güvenlik kritik
2. **Monitoring Dashboard** - Operasyon görünürlüğü
3. **Redis Cache** - Performans kazanımı
4. **E-Fatura** - Yasal uyum
5. **Load Balancing** - Ölçeklenebilirlik
6. **GPS Optimization** - Kaynak tasarrufu
7. **PyQt6 Migration** - Uzun vadeli destek
8. **RFID Integration** - Gelecek teknoloji

---

*Döküman Sonu - LOGLine WMS Technical Analysis v2.0*
*Oluşturma: 2025-09-24*
*Toplam Kod Satırı: ~25,000*
*Aktif Kullanıcı: 50+*
*Günlük İşlem: 5,000+*