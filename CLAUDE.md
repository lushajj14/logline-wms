# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Turkish warehouse management system with Logo ERP integration. Desktop PyQt5 app + FastAPI mobile backend.

## Commands

### Development
```bash
# Desktop application
python main.py

# Mobile API server (port 8000)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Configuration server (port 8001)
python -m uvicorn config_server:app --host 0.0.0.0 --port 8001

# Start all servers
start_servers.bat

# Start config server only
start_servers_only_config.bat
```

### Build & Deployment
```bash
# Full build with dependency check (recommended for production)
build.bat

# Quick build without dependency check (for testing)
quick_build.bat

# Output: dist/WMS_System.exe
```

**Build Prerequisites:**
- Python 3.8+ installed
- All dependencies from requirements.txt installed
- PyInstaller 6.3.0+
- ODBC Driver 17 for SQL Server (for testing connection)

### Testing
```bash
# Test remote configuration
python test_remote_config.py

# Test build configuration
python test_build_config.py

# Test backorders module and database
python test_backorders.py

# Test region functionality
python test_region.py
```

## Architecture

### Three-Tier Architecture
1. **Desktop Client** (`main.py`) - PyQt5 UI for warehouse operations
2. **Mobile API** (`api/main.py`) - FastAPI backend for mobile delivery apps
3. **Config Server** (`config_server.py`) - Centralized configuration provider

### Configuration Flow
The system uses a remote configuration architecture to eliminate local config files:
1. Desktop client starts → Contacts config server (port 8001)
2. Config server provides database credentials and settings
3. Client caches config locally for offline fallback
4. Connection attempts: VPN IP (192.168.5.100) → Public IP → Cached config

### Database Architecture
- **Logo ERP Integration**: Direct access to `LG_025_01_*` tables (025=company code, 01=period)
- **WMS Extensions**: Custom tables (`WMS_PICKQUEUE`, `WMS_KULLANICILAR`, `shipment_*`)
- **Connection Management**: `app/dao/logo.py` implements connection pooling with automatic retry and fallback
- **Concurrency Control**: Database-level locks via `database/concurrency_enhancements.sql`

### Key Service Interactions
- **Order Processing Flow**: Logo ERP → `fetch_draft_orders()` → Picklist generation (status=2) → Scanner UI → `queue_inc()` updates → Order completion (status=4) → Shipment creation
- **Authentication**:
  - Desktop: Login via `app/ui/pages/login_page.py` with `WMS_KULLANICILAR` table
  - Mobile API: JWT with `sp_auth_login` stored procedure (api/main.py:59-77)
- **Background Workers**: `app/ui/workers/order_completion_worker.py` handles async order completion to prevent UI freeze
- **PDF Generation**: `app/services/enhanced_picklist.py` creates picklists with Turkish character support using ReportLab + DejaVuSans font
- **Barcode Resolution**: `app/services/barcode_service.py` provides centralized barcode lookup with cross-reference support

## Critical Implementation Details

### Order Status Codes
- `1` = Draft (imported from Logo)
- `2` = Picked (picklist generated)
- `4` = Shipped (completed)

### Warehouse Prefix Routing
Scanner page uses prefixes to route items (configured in `scanner_page.py:85-90`):
- `D1-` = Warehouse 0 (Merkez/Main)
- `D3-` = Warehouse 1 (EGT)
- `D4-` = Warehouse 2 (OTOİS)
- `D5-` = Warehouse 3 (ATAK)

Prefixes can be customized via `scanner.prefixes` in config.json

### Turkish/Logo ERP Specifics
- **Table naming**: `LG_025_01_ORFICHE` where 025=company code, 01=fiscal period
- **Centralized table management**: `app/dao/logo_tables.py` - All Logo tables defined here
- **Date format**: DD.MM.YYYY (Turkish standard)
- **Character encoding**: UTF-8 with special PDF handling in `enhanced_picklist.py`
- **Font requirements**: DejaVuSans.ttf in `app/fonts/` and `fonts/` for Turkish character support in PDFs

### Logo Table Configuration (Yıllık Dönem Değişikliği)
Company/period codes are configured via Settings UI or environment variables:
```python
# Usage in code - NEVER hardcode table names!
from app.dao.logo_tables import LogoTables as T

cursor.execute(f"SELECT * FROM {T.ORFICHE} WHERE STATUS = 1")
cursor.execute(f"SELECT * FROM {T.ITEMS} WHERE ACTIVE = 0")

# Available tables:
# Period-dependent: T.ORFICHE, T.ORFLINE, T.STFICHE, T.STLINE, T.INVOICE, T.CLFICHE
# Period-independent: T.ITEMS, T.CLCARD, T.UNITSETF, T.UNITSETL
```

**Yeni yıl geçişi için:**
1. Settings > Veritabanı > "Firma No" ve "Dönem No" alanlarını güncelle
2. Kaydet - LogoTables otomatik olarak yeni config'i yükler
3. Uygulama yeniden başlatmaya gerek yok

### Concurrency & Race Conditions
The system handles concurrent barcode scanning via:
1. **Application-level locks**: `sp_getapplock` in `app/dao/concurrency_manager.py` with 5-second timeout
2. **Database-level row locks**: `WITH (ROWLOCK, UPDLOCK)` for atomic quantity updates
3. **Atomic operations**: `app/dao/atomic_scanner.py` ensures thread-safe barcode scanning
4. **Shared queue**: `WMS_PICKQUEUE` table synchronized across all scanner instances
   - `queue_inc(order_id, item_code, qty)` atomically increments `qty_sent`
   - Lock resource naming: `WMS_SCAN_{order_id}_{item_code}`

### Output File Locations
All generated files go to `Documents/WMS/`:
- `picklists/` - PDF picklists with barcodes
- `labels/` - Shipping labels (PDF or ZPL)
- `logs/` - Application logs
- `cache/` - Temporary files

### Mobile API Authentication
```python
# JWT auth flow for mobile apps:
POST /login → sp_auth_login stored procedure → JWT token (120 min expiry)
# All subsequent requests require: Authorization: Bearer {token}
# Token refresh: POST /refresh_token with old token
```

### Key Mobile API Endpoints
- `POST /login` - Authenticate user, returns JWT token
- `POST /scan/qr` - Scan QR code to get trip details
- `POST /load_pkgs` - Bulk package delivery (updates `shipment_loaded` and closes trip when complete)
- `GET /trips` - Get active trips with pending packages
- `GET /trips_delivered` - Get completed/partial deliveries
- `POST /trip/start`, `/trip/end` - GPS tracking with route calculation
- `POST /gps/track` - Track location during trip
- `POST /learn_location` - ML-based coordinate learning for addresses
- `GET /api/customers-with-pending-orders` - Customer-based bulk delivery
- `POST /api/customer-bulk-delivery` - Submit bulk delivery for customer

## Build & Deployment

### PyInstaller Configuration
The `wms.spec` file configures single-file EXE build:
- Includes all hidden imports for dynamic module loading
- Bundles fonts, sounds, and data files
- Excludes config files (.env, config.ini) - fetched from server instead
- No console window for production use

### Deployment Process
1. **Server setup** (192.168.5.100):
   ```bash
   start_servers_only_config.bat  # Port 8001
   # Open firewall: netsh advfirewall firewall add rule name="WMS Config" dir=in action=allow protocol=TCP localport=8001
   ```

2. **Client deployment**:
   - Run `build.bat` to create `dist/WMS_System.exe`
   - Copy single EXE to target machines
   - No additional files or configuration needed

## Debugging & Troubleshooting

### Connection Debugging
```python
# Test connection fallback chain
from app.dao.logo import get_conn, _initialize_pool_if_needed
_initialize_pool_if_needed()  # Initialize pool first

# Test remote config
python test_remote_config.py

# Enable debug logging
os.environ["APP_DEBUG"] = "true"
```

### Connection Fallback Chain (app/dao/connection_fallback.py)
The system tries connections in this order:
1. **VPN/Local**: `192.168.5.100,1433` (primary)
2. **Public IP**: `78.135.108.160,1433` (fallback)
3. **Cached config**: Last successful configuration from `Documents/WMS/cache/`

### Common Issues & Solutions
- **Config server unreachable**:
  - Check firewall: `netsh advfirewall firewall add rule name="WMS Config" dir=in action=allow protocol=TCP localport=8001`
  - Verify service: `http://192.168.5.100:8001/` should return status
  - Test: `python test_remote_config.py`
- **Database connection failed**:
  - Check ODBC drivers: `ODBC Driver 17 for SQL Server` required
  - Verify credentials in `config_server.py:33-36`
  - Connection timeout: 10 seconds (configurable via `DB_CONN_TIMEOUT`)
- **PDF generation errors**:
  - Verify `app/fonts/DejaVuSans.ttf` and `fonts/DejaVuSans.ttf` exist
  - Check reportlab installation: `pip show reportlab`
- **Scanner freeze**:
  - Check lock timeouts in `app/dao/concurrency_manager.py` (default: 5000ms)
  - Look for deadlocks in SQL Server Management Studio
  - Review `Documents/WMS/logs/crash.log`
- **Sound not playing**:
  - Ensure `sounds/*.wav` files exist (success.wav, error.wav, beep.wav)
  - Check `app/utils/sound_manager.py` for memory leaks
  - Verify UI settings: `UI_SOUNDS_ENABLED=true`

### Performance Configuration
- **Database**: Connection pool min=2, max=10 (env: `DB_POOL_MIN_CONNECTIONS`, `DB_POOL_MAX_CONNECTIONS`)
- **Pagination**: 50 items default (`PAGINATION_DEFAULT_SIZE` in app/dao/pagination.py)
- **Cache**: 300s TTL for repeated queries
- **Sounds**: Preloaded via `app/utils/sound_manager.py` to prevent UI delays
- **Timeouts**:
  - Connection: 10s (`DB_CONN_TIMEOUT`)
  - Query retry: 3 attempts with 2s wait (`MAX_RETRY`, `RETRY_WAIT` in app/dao/logo.py)

## Security Considerations
- **Database credentials**: Stored in `config_server.py:33-36` - update for production
- **JWT Configuration**:
  - Secret: `API_SECRET` env var (default: "SuperGizliAnahtar123" - **CHANGE IN PRODUCTION**)
  - Algorithm: HS256
  - Token expiry: 120 minutes
  - Refresh endpoint: `POST /refresh_token`
- **Password hashing**: bcrypt for `WMS_KULLANICILAR` table
- **Mobile auth**: `sp_auth_login` stored procedure validates credentials
- **RBAC system**: Roles (admin, operator, viewer) in user management
- **Config validation**: `startup_validator.py` checks for risky database settings on startup

## Important Notes
- **No .env or config.ini needed**: All config fetched from remote server (port 8001)
- **ODBC Driver**: SQL Server ODBC Driver 17 required on all machines
- **Turkish characters**: Requires UTF-8 encoding and DejaVuSans.ttf font
- **Multi-user support**: Concurrency managed via database-level and application-level locks
- **Offline mode**: Cached config in `Documents/WMS/cache/` used when config server unreachable