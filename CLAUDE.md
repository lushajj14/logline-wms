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
# Build single-file EXE (includes all dependencies, no config files needed)
build.bat

# Output: dist/WMS_System.exe
```

### Testing
```bash
# Test remote configuration
python test_remote_config.py

# Test build configuration
python test_build_config.py

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
- **Order Processing Flow**: Logo ERP → `app/services/order_service.py` → Scanner UI → Shipment creation
- **Authentication**: Desktop uses Windows auth, Mobile API uses JWT with `sp_auth_login` stored procedure
- **Background Workers**: `app/ui/workers/order_completion_worker.py` handles async order completion
- **PDF Generation**: `app/services/enhanced_picklist.py` creates picklists with Turkish character support

## Critical Implementation Details

### Order Status Codes
- `1` = Draft (imported from Logo)
- `2` = Picked (picklist generated)
- `4` = Shipped (completed)

### Warehouse Prefix Routing
Scanner page uses prefixes to route items:
- `SM` = Main warehouse
- `SA` = Warehouse A
- `SO` = Online orders

### Turkish/Logo ERP Specifics
- **Table naming**: `LG_025_01_ORFICHE` where 025=company code, 01=fiscal period
- **Date format**: DD.MM.YYYY (Turkish standard)
- **Character encoding**: UTF-8 with special PDF handling in `enhanced_picklist.py`
- **Region data**: Turkey provinces/districts in `app/data/region_data.py`

### Concurrency & Race Conditions
The system handles concurrent barcode scanning via:
1. Database-level row locks (`WITH (ROWLOCK, UPDLOCK)`)
2. Atomic operations in `app/dao/atomic_scanner.py`
3. Concurrency manager in `app/dao/concurrency_manager.py`

### Output File Locations
All generated files go to `Documents/WMS/`:
- `picklists/` - PDF picklists with barcodes
- `labels/` - Shipping labels (PDF or ZPL)
- `logs/` - Application logs
- `cache/` - Temporary files

### Mobile API Authentication
```python
# JWT auth flow for mobile apps:
POST /auth/login → sp_auth_login stored procedure → JWT token
# All subsequent requests require: Authorization: Bearer {token}
```

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
from app.dao.logo import ConnectionManager
ConnectionManager.test_connection()
get_connection_stats()  # Pool statistics

# Enable debug logging
os.environ["APP_DEBUG"] = "true"  # In startup_validator.py
```

### Common Issues & Solutions
- **Config server unreachable**: Check firewall port 8001, verify network connectivity
- **Database connection failed**: Check credentials in `config_server.py`, ensure SQL Server ODBC Driver 17 installed
- **PDF generation errors**: Verify fonts exist in `app/fonts/`, check Turkish character encoding
- **Scanner freeze**: Check `app/dao/concurrency_manager.py` for lock timeouts

### Performance Configuration
- Database connection pool: min=2, max=10 (configured in `app/dao/logo.py`)
- Default pagination: 50 items (`PAGINATION_DEFAULT_SIZE`)
- Cache TTL: 300 seconds for repeated queries
- Sound files preloaded in `app/ui/pages/scanner_page.py` to avoid delays

## Security Considerations
- Database credentials stored in `config_server.py` - update for production
- JWT secret in `API_SECRET` environment variable for mobile API
- User passwords hashed with bcrypt in `WMS_KULLANICILAR` table
- Mobile authentication via `sp_auth_login` stored procedure
- RBAC system with roles: admin, operator, viewer