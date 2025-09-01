# WMS System - AI Assistant Documentation

## Quick Start
Turkish warehouse management system with Logo ERP integration. Desktop PyQt5 app + FastAPI mobile backend.

### Run Development
```bash
# Desktop app
python main.py

# Mobile API (port 8000)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Config Server (port 8001)
python -m uvicorn config_server:app --host 0.0.0.0 --port 8001
```

### Build EXE
```bash
build.bat  # Creates dist/WMS_System.exe (single file, no config needed)
```

## Architecture

### Core Components
- **main.py** - Desktop entry, PyQt5 UI initialization
- **api/main.py** - Mobile API with JWT auth, delivery endpoints
- **config_server.py** - Remote config (eliminates .env files)
- **app/dao/logo.py** - Database layer, connection pooling
- **app/ui/pages/scanner_page.py** - Barcode scanning operations

### Database
- **SQL Server** with Logo ERP tables (`LG_025_01_*`)
- **WMS Tables**: `WMS_PICKQUEUE`, `WMS_KULLANICILAR`, `shipment_*`
- **Connection**: Pool with fallback, `pyodbc` driver

### Configuration System
- **Remote Config**: Server provides DB credentials (port 8001)
- **No .env needed**: Config fetched on startup
- **Fallback**: VPN IP → Public IP → Cache
- **WMS Folders**: `Documents/WMS/` for all outputs

## Key Features

### Scanner System
- Real-time barcode scanning with sound feedback
- Multi-warehouse support (prefix-based routing)
- Race condition protection via DB locks
- Status tracking: Draft(1) → Picked(2) → Shipped(4)

### Picklist & Labels
- **Picklist**: ReportLab PDFs with barcodes, Turkish support
- **Labels**: ZPL (Zebra) or PDF format, QR codes
- **Batch processing**: Multiple orders simultaneously

### Mobile Integration
- **Auth**: JWT tokens, `sp_auth_login` stored procedure
- **Endpoints**: `/trips`, `/load_pkgs`, `/gps/track`
- **Features**: GPS tracking, photo upload, bulk delivery

## Important Files

```
app/
├── dao/logo.py           # Database access, connection pool
├── services/
│   ├── enhanced_picklist.py  # PDF generation
│   └── label_service.py      # Label printing
├── ui/pages/
│   ├── scanner_page.py   # Main warehouse ops
│   └── loader_page.py    # Shipment management
└── config/
    ├── env_config.py     # Environment management
    └── remote_config.py  # Remote config client
```

## Common Tasks

### Add New User
```python
# In User Management page or directly in SQL:
INSERT INTO WMS_KULLANICILAR (KULLANICI_ADI, SIFRE_HASH, ROL)
VALUES ('user', bcrypt_hash('password'), 'operator')
```

### Process Order Flow
1. Orders imported from Logo (STATUS=1)
2. Generate picklist → STATUS=2
3. Scan items → Update WMS_PICKQUEUE
4. Complete → Create shipment (STATUS=4)
5. Backorders tracked separately

### Debug Connection Issues
```python
# Check in app/dao/logo.py
ConnectionManager.test_connection()  # Tests all fallback servers
get_connection_stats()  # Pool statistics
```

## Turkish/Logo Specifics

- **Table Naming**: `LG_025_01_ORFICHE` (025=company, 01=period)
- **Character Encoding**: UTF-8 throughout, special handling in PDFs
- **Date Format**: DD.MM.YYYY (Turkish standard)
- **Status Codes**: 1=Draft, 2=Picked, 4=Shipped
- **Warehouse Prefixes**: SM=Main, SA=A, SO=Online

## Build & Deployment

### PyInstaller Build
```python
# wms.spec key settings:
- Single file mode
- No console window
- Hidden imports for all services
- Excludes .env and config.ini
```

### Server Deployment
```bash
# On server (192.168.5.100):
start_servers_only_config.bat  # Starts config server on 8001

# Firewall:
netsh advfirewall firewall add rule name="WMS Config" dir=in action=allow protocol=TCP localport=8001
```

### Client Deployment
- Copy `dist/WMS_System.exe` to any PC
- Run - automatically fetches config from server
- No additional files needed

## Troubleshooting

### Common Issues
1. **"Config server unreachable"** - Check firewall port 8001
2. **"Database connection failed"** - Verify SQL Server credentials in config_server.py
3. **"Missing ODBC driver"** - Install SQL Server ODBC Driver 17
4. **"PDF generation error"** - Check fonts in app/fonts/

### Debug Mode
```python
# In startup_validator.py:
os.environ["APP_DEBUG"] = "true"  # Enables detailed logging
```

## Recent Updates
- **Remote Config System**: Centralized configuration without .env files
- **Enhanced Picklist**: Fixed lambda closures, added region data
- **WMS Paths**: Centralized to Documents/WMS
- **Mobile API**: Complete implementation with all endpoints
- **Build System**: Single EXE with all dependencies

## Security Notes
- Database credentials in config_server.py (update for production)
- JWT secret in API_SECRET environment variable
- User passwords hashed with bcrypt
- Mobile auth uses separate stored procedure
- Role-based access control (admin, operator, viewer)

## Recent Updates
- Fixed user creation foreign key constraint errors
- Implemented unified transaction management in users_new.py
- Added role-based access control to user management
- Fixed User object attribute access errors
- Build system updated with remote config support

## Performance Tips
- Connection pool: min=2, max=10 connections
- Pagination: 50 items default (PAGINATION_DEFAULT_SIZE)
- Cache TTL: 300 seconds for repeated queries
- Sound files preloaded to avoid delays

---
*Last updated: 2025-09-01 - Full system operational with RBAC and user management fixes*