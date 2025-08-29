"""
Web Backend - FastAPI Extension
Mevcut 8000 portundaki mobil API'yi genişletir
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# Environment variables yükle
load_dotenv()

# Mevcut proje yolunu ekle
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import routers
from routers import dashboard, auth

# Web API instance
web_app = FastAPI(title="LOGLine Web Interface", version="1.0.0")

# CORS middleware - development için
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
web_app.include_router(dashboard.router)
web_app.include_router(auth.router)

# Static files (React build) - production için
try:
    web_app.mount("/static", StaticFiles(directory="web/frontend/build/static"), name="static")
except RuntimeError:
    print("Static files bulunamadı - development modunda çalışıyor")

@web_app.get("/")
async def serve_index():
    """Ana sayfa - React uygulaması"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LOGLine Web Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
        <div id="root">Loading...</div>
        <script>
            // Geliştirme aşamasında basit placeholder
            document.getElementById('root').innerHTML = `
                <div style="padding: 20px; font-family: Arial;">
                    <h1>🚀 LOGLine Web Dashboard</h1>
                    <p>Web geçişi devam ediyor...</p>
                    <p>Mevcut PyQt uygulaması çalışmaya devam ediyor.</p>
                </div>
            `;
        </script>
    </body>
    </html>
    """)

# API Routes
@web_app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Dashboard istatistikleri"""
    try:
        # Mevcut DAO'yu kullan
        orders_count = fetch_one("SELECT COUNT(*) as cnt FROM LG_025_01_ORFICHE WHERE STATUS = 1")
        items_count = fetch_one("SELECT COUNT(*) as cnt FROM LG_025_ITEMS WHERE ACTIVE = 0")
        
        return {
            "orders": orders_count["cnt"] if orders_count else 0,
            "items": items_count["cnt"] if items_count else 0,
            "users": 5,  # TODO: Gerçek kullanıcı sayısı
            "activities": 10,  # TODO: Günlük aktivite sayısı
            "alerts": 2,  # TODO: Sistem uyarı sayısı
            "warehouse": 8  # TODO: Ambar işlem sayısı
        }
    except Exception as e:
        return {
            "orders": 0, "items": 0, "users": 0, 
            "activities": 0, "alerts": 0, "warehouse": 0,
            "error": str(e)
        }

@web_app.get("/api/system/status")
async def get_system_status():
    """Sistem durumu"""
    try:
        # DB bağlantı testi
        db_test = fetch_one("SELECT 1 as test")
        db_status = "Bağlı" if db_test else "Bağlantı Hatası"
        
        return {
            "database": {"status": db_status, "connected": bool(db_test)},
            "pool": {"active": 5, "max": 10, "usage": 50},
            "logo_db": {"status": "Bağlı", "last_sync": "2024-01-15 10:30"}
        }
    except Exception as e:
        return {
            "database": {"status": f"Hata: {str(e)}", "connected": False},
            "pool": {"active": 0, "max": 10, "usage": 0},
            "logo_db": {"status": "Bağlantı Hatası", "last_sync": "Bilinmiyor"}
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8002)