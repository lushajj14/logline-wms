"""
FastAPI + JWT oturum
Çalıştır:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from datetime import datetime, timedelta
from typing import Annotated
import os
import pyodbc

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware  # BU SATIRI EKLE
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from pydantic import BaseModel

# ───────────────────────────── Ayarlar
SECRET_KEY = os.getenv("API_SECRET", "SuperGizliAnahtar123")
ALGO       = "HS256"
TOKEN_MIN  = 120

SERVER   = os.getenv("LOGO_SQL_SERVER", "WIN-H4RP7JCPI93")
DATABASE = os.getenv("LOGO_SQL_DB",     "logo")
USER     = os.getenv("LOGO_SQL_USER",   "sa")
PASSWORD = os.getenv("LOGO_SQL_PASSWORD", "gHm4952!")

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};DATABASE={DATABASE};UID={USER};PWD={PASSWORD};"
    "Encrypt=no;TrustServerCertificate=yes;"
)

def get_conn_cur() -> tuple[pyodbc.Connection, pyodbc.Cursor]:
    try:
        conn = pyodbc.connect(CONN_STR, timeout=3)
        return conn, conn.cursor()
    except pyodbc.Error as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"DB bağlantı hatası: {e}",
        )

# ───────────────────────────── Uygulama


app = FastAPI(title="Loader API")

  # CORS middleware ekle
app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

# ───────────────────────────── Auth yardımcıları
def check_user(u: str, p: str) -> bool:
    with pyodbc.connect(CONN_STR) as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.sp_auth_login ?, ?", u, p)
        return cur.fetchone() is not None

# ───────────────────────────── Giriş modeli
class LoginData(BaseModel):
    username: str
    password: str

# ───────────────────────────── /login
@app.post("/login")
async def login(data: LoginData):
    if not check_user(data.username, data.password):
        return JSONResponse(status_code=401, content={"msg": "Hatalı giriş"})
    exp   = datetime.utcnow() + timedelta(minutes=TOKEN_MIN)
    token = jwt.encode({"sub": data.username, "exp": exp}, SECRET_KEY, algorithm=ALGO)
    return {"access_token": token, "token_type": "bearer", "user": {"username": data.username}}

# ───────────────────────────── Token doğrulama
def _decode_jwt(t: str):
    try:
        return jwt.decode(t, SECRET_KEY, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(401, "Token süresi doldu veya geçersiz")

def get_token(
    auth: Annotated[str | None, Header(alias="Authorization", convert_underscores=False)]
):
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "Token yok")
    return _decode_jwt(auth.removeprefix("Bearer ").strip())

TokenData = Annotated[dict, Depends(get_token)]

# ───────────────────────────── Basit ping
@app.get("/dbping")
def dbping(_: TokenData):
    conn, cur = get_conn_cur()
    cur.execute("SELECT 1")
    conn.close()
    return {"ok": True}

# ───────────────────────────── QR okuma
from fastapi import Body, Depends

@app.post("/scan/qr")
def scan_qr(
    _: dict = Depends(get_token),
    data: dict = Body(...)
):
    qr_token = data.get("qr_token", "").strip()
    conn, cur = get_conn_cur()
    cur.execute(
        "SELECT id, invoice_root, customer_code, pkgs_total FROM shipment_header WHERE LTRIM(RTRIM(qr_token)) = ?",
        qr_token,
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "QR bulunamadı")
    return {
        "trip_id":       row.id,
        "invoice_root":  row.invoice_root,
        "customer_code": row.customer_code,
        "pkgs_total":    row.pkgs_total,
    }




# ✅ DÜZELTİLMİŞ REFRESH TOKEN ENDPOINT'İ

@app.post("/refresh_token")
async def refresh_token(data: dict):
    old_token = data.get("token")
    
    if not old_token:
        raise HTTPException(401, "Token gerekli")
    
    try:
        # Eski token'ı decode et ve validate et
        payload = jwt.decode(old_token, SECRET_KEY, algorithms=[ALGO])
        username = payload.get("sub")
        
        if not username:
            raise HTTPException(401, "Geçersiz token")
        
        # Yeni token oluştur
        exp = datetime.utcnow() + timedelta(minutes=TOKEN_MIN)
        new_token = jwt.encode(
            {"sub": username, "exp": exp}, 
            SECRET_KEY, 
            algorithm=ALGO
        )
        
        return {
            "access_token": new_token, 
            "token_type": "bearer",
            "expires_in": TOKEN_MIN * 60
        }
        
    except JWTError as e:
        raise HTTPException(401, f"Token yenilenemedi: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Sunucu hatası: {str(e)}")


# ALTERNATIF - Daha basit approach (eğer token validation istemiyorsan)
@app.post("/refresh_token_simple")
async def refresh_token_simple(data: dict):
    old_token = data.get("token")
    
    try:
        # Sadece yeni token oluştur (old token'ı validate etme)
        # Bu durumda username'i data'dan al
        username = data.get("username", "default_user")
        
        exp = datetime.utcnow() + timedelta(minutes=TOKEN_MIN)
        new_token = jwt.encode(
            {"sub": username, "exp": exp}, 
            SECRET_KEY, 
            algorithm=ALGO
        )
        
        return {"access_token": new_token, "token_type": "bearer"}
        
    except Exception as e:
        raise HTTPException(500, f"Token oluşturulamadı: {str(e)}")

    

# ───────────────────────────── Tek barkod (opsiyonel eski)
@app.post("/scan/pkg")
def scan_pkg(trip_id: int, pkg_no: int, _: TokenData):
    conn, cur = get_conn_cur()
    cur.execute(
        "SELECT delivered FROM shipment_loaded WHERE trip_id = ? AND pkg_no = ?",
        trip_id, pkg_no,
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Paket bulunamadı")
    if row.delivered:
        return {"status": "duplicate"}

    cur.execute(
        """
        UPDATE shipment_loaded
           SET delivered = 1, delivered_at = GETDATE(), delivered_by = SYSTEM_USER
         WHERE trip_id = ? AND pkg_no = ?
        """,
        trip_id, pkg_no,
    )
    conn.commit()
    return {"status": "ok"}

# ───────────────────────────── TOPLU teslim /load_pkgs
# ✅ DÜZELTİLMİŞ BACKEND load_pkgs ENDPOİNT'İ

@app.post("/load_pkgs")
def load_pkgs(data: dict, _: TokenData):
    """
    Body: {"trip_id": 78, "pkgs": [1,2,3]}
    """
    trip_id = int(data["trip_id"])
    pkgs    = data.get("pkgs") or []
    if not pkgs:
        raise HTTPException(400, "Paket listesi boş")
    
    conn, cur = get_conn_cur()
    
    # 1. ✅ Paketleri delivered=1 yap
    placeholders = ",".join("?" * len(pkgs))
    cur.execute(
        f"""
        UPDATE shipment_loaded
           SET delivered    = 1,
               delivered_at = GETDATE(),
               delivered_by = SYSTEM_USER
         WHERE trip_id = ?
           AND pkg_no IN ({placeholders})
           AND delivered = 0  -- ✅ Sadece henüz teslim edilmemişleri güncelle
        """,
        (trip_id, *pkgs),
    )
    
    updated_packages = cur.rowcount  # ✅ Gerçekten güncellenen paket sayısı
    
    # 2. ✅ shipment_header'daki pkgs_loaded sayısını güncelle
    cur.execute("""
        UPDATE shipment_header 
        SET pkgs_loaded = (
            SELECT COUNT(*) FROM shipment_loaded 
            WHERE trip_id = ? AND delivered = 1
        )
        WHERE id = ?
    """, trip_id, trip_id)
    
    # 3. ✅ Tüm paketler teslim edildiyse trip'i kapat
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM shipment_loaded WHERE trip_id = ? AND delivered = 0) as remaining_count,
            (SELECT COUNT(*) FROM shipment_loaded WHERE trip_id = ?) as total_count
    """, trip_id, trip_id)
    
    result = cur.fetchone()
    remaining_count = result[0]
    total_count = result[1]
    
    if remaining_count == 0 and total_count > 0:
        # ✅ Tüm paketler teslim edildi - trip'i kapat
        cur.execute("""
            UPDATE shipment_header 
            SET closed = 1, 
                delivered_at = GETDATE(),
                loaded_at = COALESCE(loaded_at, GETDATE())
            WHERE id = ?
        """, trip_id)
        print(f"🔥 Trip {trip_id} tamamen teslim edildi ve kapatıldı")
    else:
        print(f"📦 Trip {trip_id} kısmi teslimat: {total_count - remaining_count}/{total_count}")
    
    conn.commit()
    conn.close()
    
    # 4. ✅ Doğru bilgiyle response döndür
    return {
        "updated": updated_packages,
        "total_delivered": total_count - remaining_count,
        "remaining": remaining_count,
        "status": "completed" if remaining_count == 0 else "partial"
    }



# ✅ DÜZELTİLMİŞ /trips ENDPOİNT'İ

@app.get("/trips")
def trips(start: str, end: str, _: TokenData):
    conn, cur = get_conn_cur()
    cur.execute(
        """
        SELECT h.id,
               h.order_no,
               h.invoice_root,
               h.customer_code,
               h.customer_name,
               h.address1 AS customer_addr,
               h.region,
               -- Öğrenilen koordinatları JOIN ile getir
               ac.latitude,
               ac.longitude,
               -- ✅ DÜZELTİLMİŞ PAKET SAYMA MANTĞI
               (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id) AS pkgs_total,
               (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 1) AS pkgs_loaded,
               -- ✅ KALAN PAKET SAYISI (Frontend için)
               (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 0) AS pkgs_remaining
          FROM shipment_header h
          LEFT JOIN address_coordinates ac 
            ON h.address1 LIKE '%' + ac.customer_addr + '%'
           AND ac.confidence_score = (
               SELECT MAX(confidence_score) 
               FROM address_coordinates ac2 
               WHERE h.address1 LIKE '%' + ac2.customer_addr + '%'
           )
         WHERE h.created_at BETWEEN ? AND ?
           AND h.closed = 0  -- ✅ Sadece açık trip'ler
           AND h.invoice_root IS NOT NULL
           AND h.qr_token IS NOT NULL
           AND EXISTS (SELECT 1 FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 0)  -- ✅ Bekleyen paket var mı
         ORDER BY h.created_at;
        """,
        start, end,
    )
    return [
        {
            "id": r.id,
            "order_no": r.order_no,
            "invoice_root": r.invoice_root,
            "customer_code": r.customer_code,
            "customer_name": r.customer_name,
            "customer_addr": r.customer_addr,
            "region": r.region,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "pkgs_total": r.pkgs_total,
            "pkgs_loaded": r.pkgs_loaded,
            "pkgs_remaining": r.pkgs_remaining,  # ✅ Yeni field
            "status": f"{r.pkgs_loaded}/{r.pkgs_total}",
            "delivered": r.pkgs_loaded,  # ✅ Backend'den gelen gerçek veri
        }
        for r in cur
    ]

@app.get("/trips_delivered")
def trips_delivered(start: str, end: str, _: TokenData):
    conn, cur = get_conn_cur()
    cur.execute(
        """
        SELECT h.id,
               h.order_no,
               h.invoice_root,
               h.customer_code,
               h.customer_name,
               h.address1     AS customer_addr,
               h.region,
               (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id) AS pkgs_total,
               (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 1) AS pkgs_loaded,
               (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 0) AS pkgs_remaining,
               h.loaded_at,
               -- ✅ Gerçek teslimat tarihi (en son teslimat edilen paket)
               (SELECT MAX(l.delivered_at) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 1) AS delivered_at,
               h.delivery_note,
               -- ✅ Teslimat durumu hesapla
               CASE 
                   WHEN h.closed = 1 THEN 'Tamamlandı'
                   WHEN (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 1) > 0 
                        THEN 'Kısmi Teslimat'
                   ELSE 'Bekliyor'
               END AS delivery_status
          FROM shipment_header h
         WHERE (
               h.closed = 1  -- ✅ Tamamen teslim edilenler
               OR 
               EXISTS (SELECT 1 FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 1)  -- ✅ Kısmi teslimatlar
           )
           -- ✅ Teslimat tarihine göre filtreleme - basit yaklaşım
           AND EXISTS (
               SELECT 1 FROM shipment_loaded l 
               WHERE l.trip_id = h.id 
               AND l.delivered = 1 
               AND l.delivered_at BETWEEN ? AND ?
           )
         ORDER BY (SELECT MAX(l.delivered_at) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 1) DESC;
        """,
        start, end,  # ✅ Sadece 2 parametre
    )
    return [
        {
            "id": r.id,
            "order_no": r.order_no,
            "invoice_root": r.invoice_root,
            "customer_code": r.customer_code,
            "customer_name": r.customer_name,
            "customer_addr": r.customer_addr,
            "region": r.region,
            "pkgs_total": r.pkgs_total,
            "pkgs_loaded": r.pkgs_loaded,
            "pkgs_remaining": r.pkgs_remaining,
            "loaded_at": r.loaded_at,
            "delivered_at": getattr(r, "delivered_at", None),
            "note": getattr(r, "delivery_note", None),
            "delivery_status": r.delivery_status,
            "status": f"{r.pkgs_loaded}/{r.pkgs_total}",
            "is_partial": r.pkgs_remaining > 0,
        }
        for r in cur
    ]


@app.post("/set_delivery_note")
def set_delivery_note(data: dict, _: TokenData):
    trip_id = int(data["trip_id"])
    note = data.get("note", "")
    conn, cur = get_conn_cur()
    cur.execute(
        "UPDATE shipment_header SET delivery_note = ? WHERE id = ?",
        note, trip_id
    )
    conn.commit()
    return {"ok": True}


@app.get("/stats")
def stats(from_date: str, to_date: str, _: TokenData):
    conn, cur = get_conn_cur()

    # 1) Günlük teslim miktarı
    cur.execute(
        """
        SELECT CAST(loaded_at AS date) d, SUM(pkgs_total) q
          FROM shipment_header
         WHERE loaded_at BETWEEN ? AND ?
           AND closed = 1
         GROUP BY CAST(loaded_at AS date)
         ORDER BY d
        """,
        from_date, to_date,
    )
    daily = [{"date": r.d.isoformat(), "qty": r.q} for r in cur]

    # 2) En çok koli giden 5 müşteri
    cur.execute(
        """
        SELECT TOP 5 customer_name, SUM(pkgs_total) q
          FROM shipment_header
         WHERE loaded_at BETWEEN ? AND ?
           AND closed = 1
         GROUP BY customer_name
         ORDER BY q DESC
        """,
        from_date, to_date,
    )
    top = [{"name": r.customer_name, "qty": r.q} for r in cur]

    # 3) Başarı oranı
    cur.execute(
        """
        SELECT SUM(delivered_cnt)*1.0 / NULLIF(SUM(pkgs_total),0)
          FROM (
            SELECT
              (SELECT COUNT(*) FROM shipment_loaded l
                WHERE l.trip_id = h.id AND delivered = 1) delivered_cnt,
              pkgs_total
              FROM shipment_header h
              WHERE loaded_at BETWEEN ? AND ?
                AND closed = 1
          ) x
        """,
        from_date, to_date,
    )
    success = cur.fetchone()[0] or 0

    # 4) Ortalama teslim süresi (dk)
    cur.execute(
        """
        SELECT AVG(DATEDIFF(minute, loaded_at, delivered_at))
          FROM shipment_header
         WHERE loaded_at BETWEEN ? AND ?
           AND closed = 1
           AND delivered_at IS NOT NULL
        """,
        from_date, to_date,
    )
    avg_min = cur.fetchone()[0] or 0

    # 5) Bugün kalan bekleyen koli
    cur.execute(
        """
        SELECT COUNT(*)
          FROM shipment_loaded l
          JOIN shipment_header h ON h.id = l.trip_id
         WHERE h.closed = 0
           AND CAST(h.created_at AS date) = CAST(GETDATE() AS date)
           AND l.delivered = 0
        """)
    pending_today = cur.fetchone()[0]

    # *** YENİ: Eksik istatistikleri ekle ***
    
    # 6) Toplam trip sayısı (tarih aralığında)
    cur.execute(
        "SELECT COUNT(*) FROM shipment_header WHERE created_at BETWEEN ? AND ?",
        from_date, to_date,
    )
    total_trips = cur.fetchone()[0]

    # 7) Teslim edilen trip sayısı
    cur.execute(
        "SELECT COUNT(*) FROM shipment_header WHERE loaded_at BETWEEN ? AND ? AND closed = 1",
        from_date, to_date,
    )
    delivered_trips = cur.fetchone()[0]

    # 8) Bekleyen trip sayısı
    pending_trips = total_trips - delivered_trips

    # 9) Toplam paket sayısı
    cur.execute(
        "SELECT SUM(pkgs_total) FROM shipment_header WHERE created_at BETWEEN ? AND ?",
        from_date, to_date,
    )
    total_packages = cur.fetchone()[0] or 0

    # 10) Teslim edilen paket sayısı
    cur.execute(
        "SELECT SUM(pkgs_total) FROM shipment_header WHERE loaded_at BETWEEN ? AND ? AND closed = 1",
        from_date, to_date,
    )
    delivered_packages = cur.fetchone()[0] or 0

    # 11) Bekleyen paket sayısı
    pending_packages = total_packages - delivered_packages

    return {
        # *** Frontend'in beklediği anahtarlarla döndür ***
        "total_trips": total_trips,
        "delivered_trips": delivered_trips,
        "pending_trips": pending_trips,
        "total_packages": total_packages,
        "delivered_packages": delivered_packages,
        "pending_packages": pending_packages,
        "delivery_rate": round(success * 100, 1),  # %91.0 formatında
        "avg_delivery_time": round(avg_min / 60, 1),  # Saate çevir
        "daily_deliveries": daily,  # ✅ Düzeltildi
        "top_customers": top,       # ✅ Düzeltildi
        "successRate": round(success, 2),
        "avgDurationMin": int(avg_min),
        "pendingToday": pending_today,
    }

@app.get("/performance_stats")
def performance_stats(from_date: str, to_date: str, _: TokenData):
    conn, cur = get_conn_cur()
    
    # Gerçek mesafe verilerini trip_routes'dan al
    cur.execute("""
        SELECT 
            SUM(total_distance) as total_distance,
            SUM(total_duration_minutes) as total_duration,
            SUM(fuel_consumed) as total_fuel,
            AVG(total_distance) as avg_distance_per_trip
        FROM trip_routes tr
        JOIN shipment_header sh ON tr.trip_id = sh.id
        WHERE sh.loaded_at BETWEEN ? AND ? AND sh.closed = 1
    """, from_date, to_date)
    
    route_stats = cur.fetchone()
    total_distance = route_stats.total_distance or 0
    total_duration = route_stats.total_duration or 0
    total_fuel = route_stats.total_fuel or 0
    
    # Günlük ortalama teslimat
    cur.execute("""
        SELECT AVG(daily_count) FROM (
            SELECT COUNT(*) as daily_count
            FROM shipment_header 
            WHERE loaded_at BETWEEN ? AND ? AND closed = 1
            GROUP BY CAST(loaded_at AS date)
        ) daily_stats
    """, from_date, to_date)
    avg_delivery_per_day = cur.fetchone()[0] or 0
    
    # En iyi/kötü gün
    cur.execute("""
        SELECT MAX(daily_count) as best, MIN(daily_count) as worst FROM (
            SELECT COUNT(*) as daily_count
            FROM shipment_header 
            WHERE loaded_at BETWEEN ? AND ? AND closed = 1
            GROUP BY CAST(loaded_at AS date)
        ) daily_stats
    """, from_date, to_date)
    row = cur.fetchone()
    best_day = row.best or 0
    worst_day = row.worst or 0
    
    # Zamanında teslimat oranı
    cur.execute("""
        SELECT COUNT(*) as ontime FROM shipment_header 
        WHERE loaded_at BETWEEN ? AND ? AND closed = 1
        AND DATEDIFF(hour, created_at, delivered_at) <= 24
    """, from_date, to_date)
    ontime_count = cur.fetchone()[0] or 0
    
    cur.execute("""
        SELECT COUNT(*) as total FROM shipment_header 
        WHERE loaded_at BETWEEN ? AND ? AND closed = 1
    """, from_date, to_date)
    total_deliveries = cur.fetchone()[0] or 1
    
    # Yakıt verimliliği hesapla
    fuel_efficiency = (total_distance / total_fuel) if total_fuel > 0 else 0
    
    conn.close()
    
    return {
        "totalDistance": round(total_distance, 1),
        "totalDeliveryTime": int(total_duration),
        "fuelEfficiency": round(fuel_efficiency, 1),
        "avgDeliveryPerDay": round(avg_delivery_per_day, 1),
        "bestDayDeliveries": best_day,
        "worstDayDeliveries": worst_day,
        "onTimeDeliveryRate": round(ontime_count / total_deliveries, 2),
        "customerSatisfaction": 4.2,
    }

@app.get("/recent_deliveries")
def recent_deliveries(_: TokenData, limit: int = 10):
    conn, cur = get_conn_cur()
    
    cur.execute(f"""
        SELECT TOP {int(limit)}
               h.customer_name,
               h.delivered_at,
               h.pkgs_total,
               DATEDIFF(minute, h.loaded_at, h.delivered_at) as duration_minutes
        FROM shipment_header h
        WHERE h.closed = 1 AND h.delivered_at IS NOT NULL
        ORDER BY h.delivered_at DESC
    """)
    
    # ✅ Return statement ekle
    return [
        {
            "customerName": r.customer_name,
            "deliveryTime": r.delivered_at.isoformat() if r.delivered_at else None,
            "packageCount": r.pkgs_total,
            "duration": r.duration_minutes,
            "status": "delivered"
        }
        for r in cur
    ]




@app.post("/track_location")
def track_location(data: dict, _: TokenData):
    # Konum kaydetme mantığı
    pass

@app.get("/daily_distance")
def daily_distance(date: str, _: TokenData):
    """Belirtilen gün için mesafe bilgisi"""
    conn, cur = get_conn_cur()
    
    cur.execute("""
        SELECT 
            SUM(total_distance) as total_distance,
            COUNT(*) as trip_count
        FROM trip_routes tr
        JOIN shipment_header sh ON tr.trip_id = sh.id
        WHERE CAST(sh.loaded_at AS date) = ?
    """, date)
    
    row = cur.fetchone()
    conn.close()
    
    return {
        "total_distance": round(row.total_distance or 0, 1),
        "trip_count": row.trip_count or 0
    }

@app.get("/weekly_distance")
def weekly_distance(from_date: str, to_date: str, _: TokenData):
    """Haftalık mesafe dağılımı"""
    conn, cur = get_conn_cur()
    
    cur.execute("""
        SELECT 
            CAST(sh.loaded_at AS date) as date,
            SUM(tr.total_distance) as distance,
            COUNT(*) as trips
        FROM trip_routes tr
        JOIN shipment_header sh ON tr.trip_id = sh.id
        WHERE sh.loaded_at BETWEEN ? AND ? AND sh.closed = 1
        GROUP BY CAST(sh.loaded_at AS date)
        ORDER BY date
    """, from_date, to_date)
    
    result = [
        {
            "date": row.date.isoformat(),
            "distance": round(row.distance or 0, 1),
            "trips": row.trips
        }
        for row in cur
    ]
    
    conn.close()
    return result

@app.get("/pending/{trip_id}")
def pending_list(trip_id: int, _: TokenData):
    conn, cur = get_conn_cur()
    cur.execute(
        """
        SELECT pkg_no, 1 AS qty, delivered
          FROM shipment_loaded
         WHERE trip_id = ?
        """,
        trip_id,
    )
    return [
        {
            "packageCode": r.pkg_no,
            "pieces": r.qty,
            "delivered": int(r.delivered)  # Burada int'e çeviriyoruz
        }
        for r in cur
    ]

# Diğer tek-koli /load_pkg endpoint'i (isteğe bağlı hâlâ duruyor)
@app.post("/load_pkg")
def load_pkg(trip_id: int, pkg_no: int, _: TokenData):
    return {"msg": "use /load_pkgs instead"}

# Change password stub
@app.post("/change_pwd")
def change_pwd(data: dict, _: TokenData):
    return {"msg": "ok"}



# ═══════════════════════════════════════════════════════════════════
# GPS ve Route Tracking Sistemı
# ═══════════════════════════════════════════════════════════════════

@app.post("/settings/depot")
def set_depot_location(data: dict, token: TokenData):
    """Depo konumunu ayarla"""
    username = token["sub"]
    lat = float(data["latitude"])
    lng = float(data["longitude"])
    fuel_efficiency = float(data.get("fuel_efficiency", 10.0))
    
    conn, cur = get_conn_cur()
    
    # Mevcut ayar var mı kontrol et
    cur.execute("SELECT id FROM user_settings WHERE username = ?", username)
    if cur.fetchone():
        cur.execute("""
            UPDATE user_settings 
            SET depot_latitude = ?, depot_longitude = ?, 
                vehicle_fuel_efficiency = ?, updated_at = GETDATE()
            WHERE username = ?
        """, lat, lng, fuel_efficiency, username)
    else:
        cur.execute("""
            INSERT INTO user_settings (username, depot_latitude, depot_longitude, vehicle_fuel_efficiency)
            VALUES (?, ?, ?, ?)
        """, username, lat, lng, fuel_efficiency)
    
    conn.commit()
    conn.close()
    return {"success": True, "message": "Depo konumu kaydedildi"}

@app.get("/settings/depot")
def get_depot_location(token: TokenData):
    """Depo konumunu getir"""
    username = token["sub"]
    conn, cur = get_conn_cur()
    
    cur.execute("""
        SELECT depot_latitude, depot_longitude, vehicle_fuel_efficiency 
        FROM user_settings WHERE username = ?
    """, username)
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            "latitude": float(row.depot_latitude) if row.depot_latitude else None,
            "longitude": float(row.depot_longitude) if row.depot_longitude else None,
            "fuel_efficiency": float(row.vehicle_fuel_efficiency) if row.vehicle_fuel_efficiency else 10.0
        }
    else:
        return {"latitude": None, "longitude": None, "fuel_efficiency": 10.0}

@app.post("/trip/start")
def start_trip(data: dict, token: TokenData):
    """Trip başlat ve GPS tracking'i başlat"""
    trip_id = int(data["trip_id"])
    lat = float(data["latitude"])
    lng = float(data["longitude"])
    
    conn, cur = get_conn_cur()
    
    # Trip route kaydı oluştur
    cur.execute("""
        INSERT INTO trip_routes (trip_id, start_latitude, start_longitude, start_time)
        VALUES (?, ?, ?, GETDATE())
    """, trip_id, lat, lng)
    
    # İlk GPS kaydını ekle
    cur.execute("""
        INSERT INTO gps_tracking (trip_id, latitude, longitude, recorded_at)
        VALUES (?, ?, ?, GETDATE())
    """, trip_id, lat, lng)
    
    # Shipment header'da başlangıç zamanını güncelle
    cur.execute("""
        UPDATE shipment_header 
        SET loaded_at = GETDATE() 
        WHERE id = ? AND loaded_at IS NULL
    """, trip_id)
    
    conn.commit()
    conn.close()
    return {"success": True, "message": "Trip başlatıldı"}

@app.post("/trip/end")
def end_trip(data: dict, token: TokenData):
    """Trip bitir ve mesafe/yakıt hesapla"""
    trip_id = int(data["trip_id"])
    lat = float(data["latitude"])
    lng = float(data["longitude"])
    
    conn, cur = get_conn_cur()
    
    # Son GPS kaydını ekle
    cur.execute("""
        INSERT INTO gps_tracking (trip_id, latitude, longitude, recorded_at)
        VALUES (?, ?, ?, GETDATE())
    """, trip_id, lat, lng)
    
    # Toplam mesafeyi hesapla (GPS noktaları arası)
    cur.execute("""
        WITH gps_pairs AS (
            SELECT 
                latitude, longitude,
                LAG(latitude) OVER (ORDER BY recorded_at) as prev_lat,
                LAG(longitude) OVER (ORDER BY recorded_at) as prev_lng
            FROM gps_tracking 
            WHERE trip_id = ?
            ORDER BY recorded_at
        )
        SELECT SUM(
            6371 * ACOS(
                COS(RADIANS(latitude)) * COS(RADIANS(prev_lat)) 
                * COS(RADIANS(prev_lng) - RADIANS(longitude)) 
                + SIN(RADIANS(latitude)) * SIN(RADIANS(prev_lat))
            )
        ) as total_distance
        FROM gps_pairs 
        WHERE prev_lat IS NOT NULL
    """, trip_id)
    
    distance_result = cur.fetchone()
    total_distance = distance_result[0] if distance_result and distance_result[0] else 0
    
    # Kullanıcının yakıt verimliliğini al
    username = token["sub"]
    cur.execute("SELECT vehicle_fuel_efficiency FROM user_settings WHERE username = ?", username)
    fuel_eff_row = cur.fetchone()
    fuel_efficiency = fuel_eff_row[0] if fuel_eff_row else 10.0
    
    fuel_consumed = total_distance / fuel_efficiency if fuel_efficiency > 0 else 0
    
    # Trip route'u güncelle
    cur.execute("""
        UPDATE trip_routes 
        SET end_latitude = ?, end_longitude = ?, end_time = GETDATE(),
            total_distance = ?, 
            total_duration_minutes = DATEDIFF(MINUTE, start_time, GETDATE()),
            fuel_consumed = ?
        WHERE trip_id = ?
    """, lat, lng, total_distance, fuel_consumed, trip_id)
    
    # Shipment header'da bitiş zamanını güncelle
    cur.execute("""
        UPDATE shipment_header 
        SET delivered_at = GETDATE(), closed = 1
        WHERE id = ?
    """, trip_id)
    
    conn.commit()
    conn.close()
    
    return {
        "success": True, 
        "total_distance": round(total_distance, 2),
        "fuel_consumed": round(fuel_consumed, 2),
        "message": "Trip tamamlandı"
    }

@app.post("/gps/track")
def track_gps(data: dict, token: TokenData):
    """Aktif trip sırasında GPS konumu kaydet"""
    trip_id = int(data["trip_id"])
    lat = float(data["latitude"])
    lng = float(data["longitude"])
    speed = data.get("speed", 0)
    accuracy = data.get("accuracy", 0)
    
    conn, cur = get_conn_cur()
    
    cur.execute("""
        INSERT INTO gps_tracking (trip_id, latitude, longitude, speed, accuracy, recorded_at)
        VALUES (?, ?, ?, ?, ?, GETDATE())
    """, trip_id, lat, lng, speed, accuracy)
    
    conn.commit()
    conn.close()
    return {"success": True}



from fastapi import UploadFile, File, HTTPException, Depends
import shutil
import os

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "UPLOADS")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post('/api/delivered/{id}/upload_photo')
async def upload_delivery_photo(
    id: int,
    file: UploadFile = File(...),
    _: dict = Depends(get_token)  # JWT doğrulama için
):
    conn, cur = get_conn_cur()
    # Fatura numarasını çek
    cur.execute("SELECT invoice_root FROM shipment_header WHERE id = ?", id)
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Fatura numarası bulunamadı")
    invoice_no = row.invoice_root
    # Fotoğraf adını fatura numarası ile oluştur
    ext = os.path.splitext(file.filename)[1]
    filename = f'{invoice_no}{ext}'
    file_path = os.path.join(UPLOAD_DIR, filename)
    # Dosyayı kaydet
    with open(file_path, 'wb') as buffer:
        shutil.copyfileobj(file.file, buffer)
    # SQL'e dosya yolunu kaydet
    cur.execute("UPDATE shipment_header SET delivery_photo_path = ? WHERE id = ?", file_path, id)
    conn.commit()
    conn.close()
    return {"success": True, "file_path": file_path}



# Koordinat öğrenme endpoint'i
@app.post("/learn_location")
def learn_location(data: dict, _: TokenData):
    """
    Şoför teslimat yaptığında koordinat öğren
    Body: {
        "trip_id": 78,
        "latitude": 40.8040,
        "longitude": 32.2106
    }
    """
    trip_id = data["trip_id"]
    lat = float(data["latitude"])
    lng = float(data["longitude"])
    
    conn, cur = get_conn_cur()
    
    # Trip bilgilerini al
    cur.execute("""
        SELECT customer_addr, region 
        FROM shipment_header 
        WHERE id = ?
    """, trip_id)
    
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Trip bulunamadı")
    
    address = row.customer_addr
    region = row.region
    
    # Öğrenilen koordinatı kaydet
    cur.execute("""
        INSERT INTO address_coordinates 
        (customer_addr, region, latitude, longitude, learned_by)
        VALUES (?, ?, ?, ?, SYSTEM_USER)
    """, address, region, lat, lng)
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Konum öğrenildi"}

# Öğrenilen koordinatları getir
@app.get("/learned_coordinates")
def get_learned_coordinates(address: str = None, _: TokenData = None):
    """
    Adres için öğrenilen koordinatları getir
    """
    conn, cur = get_conn_cur()
    
    if address:
        cur.execute("""
            SELECT latitude, longitude, confidence_score
            FROM address_coordinates 
            WHERE customer_addr LIKE ?
            ORDER BY confidence_score DESC, learned_at DESC
        """, f"%{address}%")
    else:
        cur.execute("""
            SELECT customer_addr, region, latitude, longitude, confidence_score
            FROM address_coordinates 
            ORDER BY learned_at DESC
        """)
    
    return [
        {
            "address": getattr(r, "customer_addr", address),
            "region": getattr(r, "region", ""),
            "latitude": r.latitude,
            "longitude": r.longitude,
            "confidence": r.confidence_score
        }
        for r in cur
    ]


# ══════════════════════════════════════════════════════════════════════════════
# YENİ MÜŞTERİ BAZLI HIZLI TESLİMAT ENDPOİNT'LERİ
# ══════════════════════════════════════════════════════════════════════════════

# Backend Güncelleme Önerisi
# /api/customers-with-pending-orders endpoint'ini /trips ile tutarlı hale getirin

@app.get("/api/customers-with-pending-orders")
def get_customers_with_pending_orders(start: str = None, end: str = None, _: TokenData = None):
    """
    Bekleyen siparişli müşterileri /trips endpoint'i ile aynı mantıkla döndür
    """
    conn, cur = get_conn_cur()
    
    # Eğer tarih belirtilmemişse son 30 günü al
    if not start or not end:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        start = start_date.strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
    
    # AYNI SORGU: /trips endpoint'i ile birebir aynı mantık
    cur.execute(
        """
        SELECT h.customer_code,
               h.customer_name,
               COUNT(DISTINCT h.id) as pending_order_count,
               SUM(CASE WHEN EXISTS (SELECT 1 FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 0)
                        THEN (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id)
                        ELSE 0 END) AS pkgs_total
          FROM shipment_header h
         WHERE h.created_at BETWEEN ? AND ?
           AND h.closed = 0
           AND h.invoice_root IS NOT NULL
           AND h.qr_token IS NOT NULL
           AND EXISTS (SELECT 1 FROM shipment_loaded l WHERE l.trip_id = h.id AND l.delivered = 0)
         GROUP BY h.customer_code, h.customer_name
         ORDER BY h.customer_name;
        """,
        start, end,
    )
    
    return [
        {
            "customer_code": r.customer_code,
            "customer_name": r.customer_name,
            "pending_order_count": r.pending_order_count,
            "pkgs_total": r.pkgs_total,
            "total_packages": r.pkgs_total,
            "package_count": r.pkgs_total
        }
        for r in cur
    ]


@app.get("/api/customers/{customer_code}/pending-orders")
def get_customer_pending_orders(customer_code: str, _: TokenData):
    conn, cur = get_conn_cur()
    
    # ✅ DÜZELTME: delivered=0 ve closed=0 filtrelerini ekle
    cur.execute("""
        SELECT 
            h.id as order_id,
            h.order_no as order_number,
            h.invoice_root,
            h.address1 as delivery_address,
            h.created_at,
            h.region,
            pending_counts.pending_packages as pkgs_total,     -- ✅ Gerçek bekleyen paket sayısı
            pending_counts.pending_packages as package_count,  -- ✅ Alternative field
            h.pkgs_total as original_total                      -- ✅ Orijinal toplam (referans için)
        FROM shipment_header h
        INNER JOIN (
            SELECT 
                l.trip_id,
                COUNT(*) as pending_packages
            FROM shipment_loaded l
            WHERE l.delivered = 0  -- ✅ Sadece teslim edilmemiş paketler
            GROUP BY l.trip_id
        ) pending_counts ON h.id = pending_counts.trip_id
        WHERE h.customer_code = ?
            AND h.closed = 0  -- ✅ Sadece kapatılmamış siparişler
        ORDER BY h.created_at DESC
    """, customer_code)
    
    orders = []
    header_rows = cur.fetchall()
    
    for row in header_rows:
        # ✅ Sadece teslim edilmemiş barkodları getir
        cur.execute("""
            SELECT CAST(pkg_no AS VARCHAR) as barcode
            FROM shipment_loaded 
            WHERE trip_id = ? AND delivered = 0  -- ✅ Önemli: delivered = 0 filtresi
        """, row.order_id)
        
        barcodes = [barcode_row.barcode for barcode_row in cur.fetchall()]
        
        # ✅ Eğer hiç bekleyen paketi yoksa bu siparişi dahil etme
        if barcodes:
            orders.append({
                "order_id": str(row.order_id),
                "order_number": row.order_number or row.invoice_root,
                "pkgs_total": len(barcodes),      # ✅ Gerçek bekleyen paket sayısı
                "package_count": len(barcodes),   # ✅ Alternative field  
                "delivery_address": row.delivery_address,
                "region": row.region,
                "barcodes": barcodes,
                "created_date": row.created_at.strftime("%Y-%m-%d") if row.created_at else None
            })
    
    conn.close()
    return orders


@app.post("/api/customer-bulk-delivery")
def submit_customer_bulk_delivery(data: dict, _: TokenData):
    customer_code = data["customer_code"]
    order_ids = data["order_ids"]
    scanned_barcodes = data["scanned_barcodes"] 
    partial_delivery = data.get("partial_delivery", False)
    
    conn, cur = get_conn_cur()
    delivered_count = 0
    
    try:
        for order_id in order_ids:
            for barcode in scanned_barcodes:
                cur.execute("""
                    UPDATE shipment_loaded 
                    SET delivered = 1, 
                        delivered_at = GETDATE(),
                        delivered_by = SYSTEM_USER
                    WHERE trip_id = ? 
                        AND CAST(pkg_no AS VARCHAR) = ?
                        AND delivered = 0
                """, order_id, barcode)
                
                if cur.rowcount > 0:
                    delivered_count += 1
        
        if not partial_delivery:
            for order_id in order_ids:
                cur.execute("""
                    SELECT COUNT(*) FROM shipment_loaded 
                    WHERE trip_id = ? AND delivered = 0
                """, order_id)
                
                remaining = cur.fetchone()[0]
                if remaining == 0:
                    cur.execute("""
                        UPDATE shipment_header 
                        SET closed = 1, 
                            delivered_at = GETDATE(),
                            loaded_at = COALESCE(loaded_at, GETDATE())
                        WHERE id = ?
                    """, order_id)
        
        conn.commit()
        
        message = "Kısmi teslimat başarıyla tamamlandı" if partial_delivery else "Teslimat başarıyla tamamlandı"
        
        return {
            "success": True,
            "message": message,
            "delivered_count": delivered_count,
            "total_count": len(scanned_barcodes),
            "customer_code": customer_code
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Teslimat kaydedilemedi: {str(e)}")
    
    finally:
        conn.close()