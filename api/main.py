"""
FastAPI + JWT oturum
Çalıştır:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
import os
import pyodbc
from contextlib import contextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from pydantic import BaseModel

# ───────────────────────────── Ayarlar
# API Security - Generate secure secret key
import secrets
import sys

SECRET_KEY: str = os.getenv("API_SECRET", "")
if not SECRET_KEY:
    # Generate a secure random secret key
    SECRET_KEY = secrets.token_urlsafe(32)
    
    # Log warning and provide the generated key for user to save
    import warnings
    warnings.warn(
        f"\n{'='*60}\n"
        f"SECURITY WARNING: No API_SECRET environment variable found!\n"
        f"A temporary secret key has been generated for this session.\n"
        f"Please save this key and set it as API_SECRET environment variable:\n\n"
        f"API_SECRET={SECRET_KEY}\n"
        f"\nOn Windows: set API_SECRET={SECRET_KEY}\n"
        f"On Linux/Mac: export API_SECRET={SECRET_KEY}\n"
        f"{'='*60}\n",
        RuntimeWarning
    )
    
    # In production, you might want to refuse to start without a proper secret
    if os.getenv("ENVIRONMENT") == "production":
        sys.exit("ERROR: API_SECRET must be set in production environment!")

# Ensure SECRET_KEY is never None for type safety
assert SECRET_KEY, "SECRET_KEY must not be empty"
ALGO       = "HS256"
TOKEN_MIN  = 120

SERVER   = os.getenv("LOGO_SQL_SERVER", "192.168.5.100,1433")
DATABASE = os.getenv("LOGO_SQL_DB",     "logo")
USER     = os.getenv("LOGO_SQL_USER",   "sa")
PASSWORD = os.getenv("LOGO_SQL_PASSWORD", "gHm4952!")

# Standardized connection timeout (seconds)
CONN_TIMEOUT = int(os.getenv("DB_CONN_TIMEOUT", "10"))

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};DATABASE={DATABASE};UID={USER};PWD={PASSWORD};"
    "Encrypt=no;TrustServerCertificate=yes;"
)

@contextmanager
def get_conn():
    """
    Context manager for database connections.
    Uses connection pool if available, falls back to direct connection.
    """
    conn = None
    use_pool = False
    
    try:
        # Try to use connection pool from DAO layer
        # Check if pool is available and enabled
        if os.getenv("DB_USE_POOL", "true").lower() in ("true", "1", "yes", "on"):
            try:
                from app.dao.connection_pool import get_pooled_connection
                # Use the pooled connection directly
                with get_pooled_connection(autocommit=False) as pool_conn:
                    use_pool = True
                    yield pool_conn
                return
            except (ImportError, Exception) as e:
                # Pool not available or failed, fall back to direct connection
                pass
        
        # Fallback to direct connection
        conn = pyodbc.connect(CONN_STR, timeout=CONN_TIMEOUT)
        yield conn
        
    except pyodbc.Error as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"DB bağlantı hatası: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Beklenmeyen hata: {e}",
        )
    finally:
        # Only close if using direct connection (pool handles its own connections)
        if conn and not use_pool:
            try:
                conn.close()
            except:
                pass

def get_conn_cur() -> tuple[pyodbc.Connection, pyodbc.Cursor]:
    """
    Legacy function - use get_conn() context manager instead.
    This function is deprecated and should be avoided.
    """
    try:
        conn = pyodbc.connect(CONN_STR, timeout=CONN_TIMEOUT)
        return conn, conn.cursor()
    except pyodbc.Error as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"DB bağlantı hatası: {e}",
        )

# ───────────────────────────── Uygulama
app = FastAPI(title="Loader API")

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
    exp   = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MIN)
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
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
    return {"ok": True}

# ───────────────────────────── QR okuma
@app.post("/scan/qr")
def scan_qr(qr_token: str, _: TokenData):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,
                   invoice_root,
                   customer_code,
                   pkgs_total
              FROM shipment_header
             WHERE qr_token = ?
            """,
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

# ───────────────────────────── Tek barkod (opsiyonel eski)
@app.post("/scan/pkg")
def scan_pkg(trip_id: int, pkg_no: int, _: TokenData):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT loaded FROM shipment_loaded WHERE trip_id = ? AND pkg_no = ?",
            trip_id, pkg_no,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Paket bulunamadı")
        if row.loaded:
            return {"status": "duplicate"}

        cur.execute(
            """
            UPDATE shipment_loaded
               SET loaded = 1, loaded_at = GETDATE(), loaded_by = SYSTEM_USER
             WHERE trip_id = ? AND pkg_no = ?
            """,
            trip_id, pkg_no,
        )
        conn.commit()
        return {"status": "ok"}

# ───────────────────────────── TOPLU teslim /load_pkgs
@app.post("/load_pkgs")
def load_pkgs(data: dict, _: TokenData):
    """
    Body: {"trip_id": 78, "pkgs": [1,2,3]}
    """
    trip_id = int(data["trip_id"])
    pkgs    = data.get("pkgs") or []
    if not pkgs:
        raise HTTPException(400, "Paket listesi boş")
    
    with get_conn() as conn:
        cur = conn.cursor()
        placeholders = ",".join("?" * len(pkgs))
        cur.execute(
            f"""
            UPDATE shipment_loaded
               SET loaded    = 1,
                   loaded_at = GETDATE(),
                   loaded_by = SYSTEM_USER
             WHERE trip_id = ?
               AND pkg_no IN ({placeholders})
            """,
            (trip_id, *pkgs),
        )
        conn.commit()
        return {"updated": cur.rowcount}

# --- /trips -------------------------------------------------
@app.get("/trips")
def trips(start: str, end: str, _: TokenData):
    with get_conn() as conn:
        cur = conn.cursor()
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
                   (SELECT COUNT(*) FROM shipment_loaded l WHERE l.trip_id = h.id AND l.loaded = 1) AS pkgs_loaded
              FROM shipment_header h
             WHERE h.created_at BETWEEN ? AND ?
               AND h.closed = 0
               AND h.invoice_root IS NOT NULL
               AND h.qr_token     IS NOT NULL
               AND EXISTS (SELECT 1 FROM shipment_loaded l WHERE l.trip_id = h.id AND l.loaded = 0)
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
                "pkgs_total": r.pkgs_total,
                "pkgs_loaded": r.pkgs_loaded,
                "status": f"{r.pkgs_loaded}/{r.pkgs_total}",
            }
            for r in cur
        ]

# --- /trips_delivered ---------------------------------------
@app.get("/trips_delivered")
def trips_delivered(start: str, end: str, _: TokenData):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT h.id,
                   h.order_no,
                   h.invoice_root,
                   h.customer_code,
                   h.customer_name,
                   h.address1     AS customer_addr,
                   h.region,
                   h.pkgs_total,
                   h.pkgs_loaded,
                   h.loaded_at
              FROM shipment_header h
             WHERE h.created_at BETWEEN ? AND ?
               AND h.closed = 1
             ORDER BY h.loaded_at DESC;
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
                "pkgs_total": r.pkgs_total,
                "pkgs_loaded": r.pkgs_loaded,
                "loaded_at":   r.loaded_at,
            }
            for r in cur
        ]



# --- /stats -------------------------------------------------
@app.get("/stats")
def stats(from_date: str, to_date: str, _: TokenData):
    """
    Tarih aralığı → YYYY-MM-DD
    Dönen JSON:
      {
        dailyDelivered:[{date:'2025-06-24', qty:120}, …],
        topCustomers  :[{name:'KOÇHAN', qty:340}, …],
        successRate   :0.96,
        avgDurationMin:18,
        pendingToday  :42
      }
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
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
            SELECT SUM(loaded_cnt)*1.0 / NULLIF(SUM(pkgs_total),0)
              FROM (
                SELECT
                  (SELECT COUNT(*) FROM shipment_loaded l
                    WHERE l.trip_id = h.id AND loaded = 1) loaded_cnt,
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
            SELECT AVG(DATEDIFF(min, created_at, loaded_at))
              FROM shipment_header
             WHERE loaded_at BETWEEN ? AND ?
               AND closed = 1
               AND loaded_at IS NOT NULL
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
               AND l.loaded = 0
            """)
        pending_today = cur.fetchone()[0]

        return {
            "dailyDelivered": daily,
            "topCustomers"  : top,
            "successRate"   : round(success, 2),
            "avgDurationMin": int(avg_min),
            "pendingToday"  : pending_today,
        }


# --- /pending/{trip_id} ------------------------------------
@app.get("/pending/{trip_id}")
def pending_list(trip_id: int, _: TokenData):
    with get_conn() as conn:
        cur = conn.cursor()
    cur.execute(
        """
        SELECT pkg_no, 1 AS qty, loaded

          FROM shipment_loaded
         WHERE trip_id = ?
        """,
        trip_id,
    )
    return [
        {"packageCode": r.pkg_no, "pieces": r.qty, "delivered": r.loaded}
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


# --- Connection Pool Monitoring ---
@app.get("/system/pool_status")
def pool_status():
    """
    Connection pool durumunu döndürür.
    Admin kullanıcılar için sistem bilgisi.
    """
    try:
        from app.dao.logo import get_pool_info
        return get_pool_info()
    except ImportError:
        return {
            "pool_enabled": False,
            "error": "Pool module not available"
        }
    except Exception as e:
        return {
            "pool_enabled": False,
            "error": str(e)
        }


@app.post("/system/pool_reinit")
def pool_reinitialize(_: TokenData):
    """
    Connection pool'u yeniden başlatır.
    Admin yetkisi gerekir.
    """
    try:
        from app.dao.logo import reinitialize_pool
        success = reinitialize_pool()
        return {
            "success": success,
            "message": "Pool reinitialized" if success else "Pool reinitialization failed"
        }
    except ImportError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Pool module not available"
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Pool reinitialization error: {e}"
        )
