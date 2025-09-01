"""
WMS Desktop Configuration Server
=================================
Merkezi config yönetimi için basit API server.
Token gerektirmez, makine ID doğrulaması yapar.

Çalıştırma:
    uvicorn config_server:app --host 0.0.0.0 --port 8001
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import hashlib
import json
import os

app = FastAPI(title="WMS Config Server")

# CORS - Desktop uygulamalardan erişim için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= CONFIGURATION =============
# Bunları environment'tan al veya config dosyasından oku
CONFIG = {
    "LOGO_SQL_SERVER": os.getenv("LOGO_SQL_SERVER", "192.168.5.100,1433"),
    "LOGO_SQL_DB": os.getenv("LOGO_SQL_DB", "logo"),
    "LOGO_SQL_USER": os.getenv("LOGO_SQL_USER", "barkod1"),
    "LOGO_SQL_PASSWORD": os.getenv("LOGO_SQL_PASSWORD", "Barkod14*"),
    "LOGO_COMPANY_NR": os.getenv("LOGO_COMPANY_NR", "025"),
    "LOGO_PERIOD_NR": os.getenv("LOGO_PERIOD_NR", "01"),
    
    # Connection Pool
    "DB_USE_POOL": "true",
    "DB_POOL_MIN_CONNECTIONS": "2",
    "DB_POOL_MAX_CONNECTIONS": "10",
    "DB_POOL_TIMEOUT": "30",
    "DB_CONN_TIMEOUT": "10",
    
    # API Settings
    "API_SECRET": "production-secret-key-change-this",
    "API_ALGORITHM": "HS256",
    "API_TOKEN_EXPIRE_MINUTES": "120",
    
    # App Settings
    "APP_DEBUG": "false",
    "APP_LOG_LEVEL": "INFO",
    
    # UI Settings
    "UI_AUTO_REFRESH": "30",
    "UI_SOUNDS_ENABLED": "true",
    "UI_SOUNDS_VOLUME": "0.9"
}

# Onaylı makine listesi (opsiyonel güvenlik)
AUTHORIZED_MACHINES = {
    # "machine_id": "machine_name"
    # Boş bırakırsan tüm makineler erişebilir
}

# Version bilgisi
CURRENT_VERSION = "2.0.0"
LATEST_VERSION = "2.0.0"

# ============= MODELS =============
class ConfigRequest(BaseModel):
    machine_id: str
    hostname: str = None
    username: str = None
    app_version: str = None

class ConfigResponse(BaseModel):
    config: dict
    version_info: dict
    server_time: str

# ============= ENDPOINTS =============

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "WMS Config Server",
        "version": "1.0.0",
        "time": datetime.now().isoformat()
    }

@app.post("/desktop/config")
async def get_desktop_config(request: ConfigRequest):
    """
    Desktop uygulamalar için config endpoint'i.
    Token gerektirmez, makine ID ile doğrulama yapar.
    """
    
    # Makine ID kontrolü (opsiyonel)
    if AUTHORIZED_MACHINES:
        if request.machine_id not in AUTHORIZED_MACHINES:
            raise HTTPException(status_code=403, detail="Unauthorized machine")
    
    # Log kaydı (kim, ne zaman config çekti)
    print(f"Config requested by: {request.machine_id} / {request.hostname} / {request.username} at {datetime.now()}")
    
    # Makineye özel config düzenlemeleri yapabilirsin
    machine_config = CONFIG.copy()
    
    # Örnek: Test makineleri farklı DB kullanabilir
    if request.hostname and "TEST" in request.hostname.upper():
        machine_config["LOGO_SQL_DB"] = "logo_test"
        machine_config["APP_DEBUG"] = "true"
    
    # Version kontrolü
    version_info = {
        "current_version": CURRENT_VERSION,
        "client_version": request.app_version,
        "update_available": False,
        "update_url": None
    }
    
    if request.app_version and request.app_version < CURRENT_VERSION:
        version_info["update_available"] = True
        version_info["update_url"] = f"http://{os.getenv('SERVER_IP', '192.168.5.100')}:8001/download/wms_setup.exe"
    
    return ConfigResponse(
        config=machine_config,
        version_info=version_info,
        server_time=datetime.now().isoformat()
    )

@app.get("/desktop/config/{machine_id}")
async def get_desktop_config_simple(machine_id: str):
    """
    Basit GET endpoint - eski sistemler için.
    """
    request = ConfigRequest(machine_id=machine_id)
    return await get_desktop_config(request)

@app.post("/desktop/register")
async def register_machine(request: ConfigRequest):
    """
    Yeni makine kaydı (opsiyonel).
    İlk kurulumda makineyi sisteme tanıtır.
    """
    # Makineyi kaydet (DB veya dosyaya)
    registration = {
        "machine_id": request.machine_id,
        "hostname": request.hostname,
        "username": request.username,
        "registered_at": datetime.now().isoformat(),
        "app_version": request.app_version
    }
    
    # Burada DB'ye kaydedebilirsin
    print(f"New machine registered: {registration}")
    
    return {
        "status": "registered",
        "machine_id": request.machine_id,
        "message": "Machine successfully registered"
    }

@app.get("/desktop/version")
async def check_version(current: str = None):
    """
    Version kontrolü için endpoint.
    """
    update_available = False
    if current and current < LATEST_VERSION:
        update_available = True
    
    return {
        "latest_version": LATEST_VERSION,
        "current_version": current,
        "update_available": update_available,
        "download_url": f"http://{os.getenv('SERVER_IP', '192.168.5.100')}:8001/download/wms_setup.exe" if update_available else None,
        "changelog": "Bug fixes and performance improvements"
    }

@app.post("/desktop/heartbeat")
async def heartbeat(machine_id: str):
    """
    Desktop uygulamaların canlı olduğunu bildirmesi için.
    Monitoring ve lisans kontrolü için kullanılabilir.
    """
    # Makine aktivitesini kaydet
    heartbeat_data = {
        "machine_id": machine_id,
        "timestamp": datetime.now().isoformat(),
        "status": "active"
    }
    
    # Burada DB'ye kaydedebilirsin
    print(f"Heartbeat from: {machine_id}")
    
    return {"status": "ok", "next_heartbeat_seconds": 300}

# ============= ADMIN ENDPOINTS =============

@app.get("/admin/machines")
async def list_machines():
    """
    Kayıtlı makineleri listele (admin panel için).
    """
    # DB'den çek veya cache'ten al
    return {
        "total": len(AUTHORIZED_MACHINES),
        "machines": AUTHORIZED_MACHINES
    }

@app.post("/admin/update-config")
async def update_config(key: str, value: str):
    """
    Config değerini güncelle (admin panel için).
    """
    if key in CONFIG:
        CONFIG[key] = value
        return {"status": "updated", "key": key, "value": value}
    else:
        raise HTTPException(status_code=404, detail="Config key not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)