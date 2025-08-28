"""
Data‑Access Object (DAO) katmanı
================================
Logo GO Wings MSSQL veritabanına *yalnızca* `pyodbc` ile erişir.

* Tablo şablonu: `LG_<COMPANY_NR>_<PERIOD_NR>_<NAME>`
* `COMPANY_NR` (üç hane) ve `PERIOD_NR` (iki hane) ortam değişkeni ile
  değiştirilebilir.
* ODBC sürücüsü otomatik tespit edilir – `LOGO_SQL_DRIVER` ile zorla
  belirtebilirsin.

Ek olarak **WMS_PICKQUEUE** tablosu, çoklu istasyon senaryosunda
`ScannerPage` ile paylaşılan kalıcı kuyruğu tutar:

```sql
CREATE TABLE dbo.WMS_PICKQUEUE (
    order_id    INT NOT NULL,
    item_code   VARCHAR(30) NOT NULL,
    qty_ordered FLOAT NOT NULL,
    qty_sent    FLOAT NOT NULL DEFAULT 0,
    CONSTRAINT PK_WMS_PICKQUEUE PRIMARY KEY (order_id, item_code)
);
```
"""
from __future__ import annotations
import os
import time
import logging
from contextlib import contextmanager
from typing import Any, Dict, List
import uuid
import pyodbc

MAX_RETRY = 3
RETRY_WAIT = 2  # saniye
# Standardized connection timeout (seconds)
CONN_TIMEOUT = int(os.getenv("DB_CONN_TIMEOUT", "10"))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bağlantı Ayarları –  env > fallback
# ---------------------------------------------------------------------------
# Database credentials - MUST be set via environment variables for security
SERVER     = os.getenv("LOGO_SQL_SERVER")
DATABASE   = os.getenv("LOGO_SQL_DB")
USER       = os.getenv("LOGO_SQL_USER")
PASSWORD   = os.getenv("LOGO_SQL_PASSWORD")

# Validate required environment variables
if not all([SERVER, DATABASE, USER, PASSWORD]):
    # For backwards compatibility, use defaults but warn
    import warnings
    warnings.warn(
        "SECURITY WARNING: Using default database credentials. "
        "Please set environment variables: LOGO_SQL_SERVER, LOGO_SQL_DB, LOGO_SQL_USER, LOGO_SQL_PASSWORD",
        RuntimeWarning
    )
    SERVER     = SERVER or "192.168.5.100,1433"
    DATABASE   = DATABASE or "logo"
    USER       = USER or "barkod1"
    PASSWORD   = PASSWORD or "Barkod14*"  # This should NEVER be in production!
COMPANY_NR = os.getenv("LOGO_COMPANY_NR", "025")    # firma
PERIOD_NR  = os.getenv("LOGO_PERIOD_NR", "01")       # dönem (01‑12)

# --- Sürücü seçimi ----------------------------------------------------------
_available = [d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d]
_available.sort(key=lambda s: int("".join(filter(str.isdigit, s))) or 0)  # 17,18… artan
DRIVER = os.getenv("LOGO_SQL_DRIVER") or (_available[-1] if _available else "SQL Server")

logger.debug("Seçilen ODBC sürücüsü: %s", DRIVER)

CONN_STR = (
    f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
    f"UID={USER};PWD={PASSWORD};TrustServerCertificate=yes;"
)

QUEUE_TABLE = "WMS_PICKQUEUE"  # kalıcı kuyruk tablosu

# ---------------------------------------------------------------------------
@contextmanager
def get_conn(*, autocommit: bool = False):
    """
    MSSQL bağlantısı üretir; geçici hatalarda max 3 kez yeniden dener.
    Başarı → pyodbc.Connection  |  Başarısız → son hatayı yükseltir.
    """
    last_exc = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            conn = pyodbc.connect(CONN_STR, timeout=CONN_TIMEOUT, autocommit=autocommit)
            break                      # ➜ başarılı çıkış
        except pyodbc.Error as exc:
            last_exc = exc
            logger.warning(
                "DB bağlantı hatası (deneme %d/%d): %s",
                attempt, MAX_RETRY, exc)
            time.sleep(RETRY_WAIT)
    else:                              # for-else 👉 3 deneme de başarısız
        raise last_exc                 # ↑ main window yakalayacak

    try:
        yield conn
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Yardımcı – tablo adı üretici
# ---------------------------------------------------------------------------

def _t(name: str, *, period_dependent: bool = True) -> str:
    """Logo tablo adını firma & dönem parametreleriyle döndürür."""
    return f"LG_{COMPANY_NR}_{PERIOD_NR}_{name}" if period_dependent else f"LG_{COMPANY_NR}_{name}"

# ---------------------------------------------------------------------------
# Küçük util fonksiyonlar (Logo dışı genel) ----------------------------------
# ---------------------------------------------------------------------------

def exec_sql(sql: str, *params):
    """Basit `INSERT/UPDATE/DELETE` yardımcısı (autocommit=ON)."""
    with get_conn(autocommit=True) as cn:
        cn.execute(sql, *params)


def fetch_all(sql: str, *params) -> List[Dict[str, Any]]:
    with get_conn() as cn:
        cur = cn.execute(sql, *params)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def fetch_one(sql: str, *params) -> Dict[str, Any] | None:
    """Tek bir satır döndürür, yoksa None."""
    with get_conn() as cn:
        cur = cn.execute(sql, *params)
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0].lower() for c in cur.description]
        return dict(zip(cols, row))
# ---------------------------------------------------------------------------
# DAO Fonksiyonları
# ---------------------------------------------------------------------------

def fetch_draft_orders(*, limit: int = 100) -> List[Dict[str, Any]]:
    """`STATUS = 1` (öneri) siparişleri getirir."""
    sql = f"""
    SELECT TOP (?)
        F.LOGICALREF AS order_id,
        F.FICHENO    AS order_no,
        F.DATE_      AS order_date,
        F.STATUS,
        F.CYPHCODE   AS cyphcode,
        C.CODE       AS customer_code,
        C.DEFINITION_ AS customer_name
    FROM {_t('ORFICHE')} F
    JOIN {_t('CLCARD', period_dependent=False)} C ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 1      -- öneri
      AND F.CANCELLED = 0
    ORDER BY F.DATE_, F.FICHENO;"""
    with get_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql, limit)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    

def fetch_picking_orders(limit: int = 100) -> List[Dict[str, Any]]:
    """
    STATUS = 2 (picking) durumundaki sipariş başlıklarını döndürür.
    """
    sql = f"""
    SELECT TOP (?) 
        F.LOGICALREF  AS order_id,
        F.FICHENO     AS order_no,
        F.DATE_       AS order_date,
        C.CODE        AS customer_code,
        C.DEFINITION_ AS customer_name
    FROM { _t('ORFICHE') } F
    JOIN { _t('CLCARD', period_dependent=False) } C
          ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 2           -- picking
      AND F.CANCELLED = 0
    ORDER BY F.DATE_, F.FICHENO;
    """
    with get_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql, limit)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_order_lines(order_id: int) -> List[Dict[str, Any]]:
    """Belirtilen satış siparişinin satırlarını getirir (ORFLINE)."""
    sql = f"""
    SELECT
        L.LOGICALREF AS line_id,
        L.STOCKREF   AS item_ref,
        I.CODE       AS item_code,
        I.NAME       AS item_name,
        I.SPECODE    AS shelf_loc,
        L.AMOUNT     AS qty_ordered,
        L.PRICE      AS price,
        L.SOURCEINDEX AS warehouse_id,
        L.STATUS     AS line_status
    FROM {_t('ORFLINE')} L
    JOIN {_t('ITEMS', period_dependent=False)} I ON I.LOGICALREF = L.STOCKREF
    WHERE L.ORDFICHEREF = ?
      AND L.CANCELLED   = 0
    ORDER BY L.LINENO_;"""
    with get_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql, order_id)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---- Order lines by FICHENO (order_no) -------------------------------
def fetch_order_lines_by_no(order_no: str) -> List[Dict[str, Any]]:
    sql = f"""
        SELECT L.LOGICALREF   AS line_id,
               I.CODE         AS item_code,
               I.NAME         AS item_name,
               L.AMOUNT       AS qty_ordered,
               L.SOURCEINDEX  AS warehouse_id
        FROM { _t('ORFLINE') } L                -- ✅ STLINE → ORFLINE
        JOIN { _t('ITEMS', period_dependent=False) } I
             ON I.LOGICALREF = L.STOCKREF
        WHERE L.ORDFICHEREF = (
              SELECT LOGICALREF FROM { _t('ORFICHE') }
              WHERE FICHENO = ? )
          AND L.CANCELLED = 0                   -- iptal edilmemiş satırlar
        ORDER BY L.LOGICALREF;                  -- sürümler arası güvenli
    """
    with get_conn() as cn:
        cur  = cn.execute(sql, order_no)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]



def update_order_status(order_id: int, new_status: int) -> None:
    """Sipariş fişinin `STATUS` alanını günceller."""
    sql = f"""
    UPDATE {_t('ORFICHE')}
        SET STATUS = ?
     WHERE LOGICALREF = ?;
    """
    with get_conn(autocommit=True) as cn:
        cn.execute(sql, new_status, order_id)


def mark_line_backorder(line_id: int, missing_qty: float, eta_date: str) -> None:
    """Eksik miktarı (`missing_qty`) ve tahmini varış tarihini (`eta_date`) satıra yazar."""
    sql = f"""
    UPDATE {_t('STLINE')}
        SET GENEXP1 = ?, GENEXP2 = ?
     WHERE LOGICALREF = ?;
    """
    with get_conn(autocommit=True) as cn:
        cn.execute(sql, str(missing_qty), eta_date, line_id)

# ---------------------------------------------------------------------------
# Sipariş başlığı okuma / yazma ve fatura kontrolü
# ---------------------------------------------------------------------------

def update_order_header(
    order_id: int,
    *,
    genexp1: str | None = None,
    genexp4: str | None = None,
    genexp5: str | None = None,   # ★ eklendi
) -> None:
    sets, params = [], []
    if genexp1 is not None:
        sets.append("GENEXP1 = ?")
        params.append(genexp1)
    if genexp4 is not None:
        sets.append("GENEXP4 = ?")
        params.append(genexp4)
    if genexp5 is not None:                        # ★
        sets.append("GENEXP5 = ?")                 # ★
        params.append(genexp5)                     # ★
    if not sets:
        return
    sql = f"UPDATE {_t('ORFICHE')} SET {', '.join(sets)} WHERE LOGICALREF = ?"
    params.append(order_id)
    with get_conn(autocommit=True) as cn:
        cn.execute(sql, params)



# ---------------------------------------------------------------------------
# Siparişten fatura numarası bulma (3 şema senaryosu)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Siparişten fatura numarası bulma –  sürüme dayanıklı
# ---------------------------------------------------------------------------
def fetch_invoice_no(order_no: str) -> str | None:
    """
    Sipariş no (FICHENO) → kesilmiş fatura no’yu döndür.
    Tablo şemasına göre 3 farklı kolon denenir; kolon yoksa 42S22 hatası
    sessizce yutulur ve sıradaki sorguya geçilir.
    """
    sql_variants = [
        # 1) Yeni sürümlerde ORDFICHENO
        f"""
        SELECT TOP 1 FICHENO
        FROM {_t('INVOICE')}
        WHERE ORDFICHENO = ? AND CANCELLED = 0
        """,
        # 2) Bazı sürümlerde SOURCEFICHENO
        f"""
        SELECT TOP 1 FICHENO
        FROM {_t('INVOICE')}
        WHERE SOURCEFICHENO = ? AND CANCELLED = 0
        """,
        # 3) Eski sürümlerde STFICHE ilişkisi (INVOICEREF)
        f"""
        SELECT TOP 1 I.FICHENO
        FROM {_t('INVOICE')} I
        JOIN {_t('STFICHE')} S ON S.LOGICALREF = I.INVOICEREF
        WHERE S.FICHENO = ? AND I.CANCELLED = 0
        """,
        ## 4) STLINE.INVOICEREF (main.py’deki yol)
        f"""
        SELECT TOP 1 I.FICHENO
        FROM {_t('INVOICE')} I
        JOIN {_t('STLINE')} S ON S.INVOICEREF = I.LOGICALREF
        WHERE S.ORDFICHEREF IN (
              SELECT LOGICALREF FROM {_t('ORFICHE')} WHERE FICHENO = ?)
          AND I.CANCELLED = 0
        """,

    ]
    with get_conn() as cn:
        for sql in sql_variants:
            try:
                row = cn.execute(sql, order_no).fetchone()
                if row:
                    return row[0]
            except pyodbc.ProgrammingError as e:
                # Kolon yoksa (42S22) → bu sorguyu atla
                if "42S22" in str(e):
                    continue
                raise
    return None

def log_activity(
    username: str,
    action: str,
    details: str = "",
    *,
    order_no: str | None = None,
    item_code: str | None = None,
    qty_ordered: float | None = None,
    qty_scanned: float | None = None,
    warehouse_id: int | None = None,
):
    sql = """
        INSERT INTO USER_ACTIVITY
        (username, action, details, order_no, item_code,
         qty_ordered, qty_scanned, warehouse_id)
        VALUES (?,?,?,?,?,?,?,?)
    """
    exec_sql(sql, username, action[:50], details[:255],
             order_no, item_code, qty_ordered, qty_scanned, warehouse_id)


def fetch_activities(limit: int = 500) -> List[Dict[str, Any]]:
    sql = """
        SELECT TOP (?)
               username,
               event_time,
               action,
               details,
               order_no,
               item_code,
               qty_ordered,
               qty_scanned,
               warehouse_id
        FROM   USER_ACTIVITY
        ORDER BY event_time DESC
    """
    return fetch_all(sql, limit)

def db_ping() -> bool:
    try:
        with get_conn() as cn:
            cn.execute("SELECT 1")
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Sipariş başlığı ayrıntıları
# ---------------------------------------------------------------------------

def fetch_order_header(order_no: str) -> dict | None:
    """
    FICHENO (sipariş no) ile başlık alanlarını döndürür.
    GENEXP2  → Bölge 1
    GENEXP3  → Bölge 2
    GENEXP4  → 'PAKET SAYISI : N'
    """
    sql = f"""
    SELECT TOP 1
           F.LOGICALREF,
           F.FICHENO,
           F.GENEXP1,
           F.GENEXP2,
           F.GENEXP3,
           F.GENEXP4,
           C.CODE        AS cari_kodu,
           C.DEFINITION_ AS cari_adi,
           C.ADDR1       AS adres
    FROM {_t('ORFICHE')} F
    JOIN {_t('CLCARD', period_dependent=False)} C
         ON C.LOGICALREF = F.CLIENTREF
    WHERE F.FICHENO = ?;
    """
    with get_conn() as cn:
        cur = cn.execute(sql, order_no)
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0].lower() for c in cur.description]   # ✅ doğru cursor
        return dict(zip(cols, row))



# WMS_PICKQUEUE  –  Kalıcı barkod kuyruğu fonksiyonları
# ---------------------------------------------------------------------------

def queue_insert(order_id: int):
    """Sipariş satırlarını WMS_PICKQUEUE'ye ekler (varsa ignor)."""
    sql = f"""
    INSERT INTO {QUEUE_TABLE} (order_id, item_code, qty_ordered, qty_sent)
    SELECT L.ORDFICHEREF, I.CODE, L.AMOUNT, 0
    FROM   {_t('ORFLINE')} L
    JOIN   {_t('ITEMS', period_dependent=False)} I ON I.LOGICALREF = L.STOCKREF
    WHERE  L.ORDFICHEREF = ?
      AND  L.CANCELLED   = 0
      AND NOT EXISTS (SELECT 1 FROM {QUEUE_TABLE} q
                       WHERE  q.order_id  = L.ORDFICHEREF
                         AND  q.item_code = I.CODE);
    """
    exec_sql(sql, order_id)


def queue_fetch(order_id: int) -> List[Dict[str, Any]]:
    """Kuyruktaki satırları (ordered & sent) döndürür."""
    sql = f"SELECT item_code, qty_ordered, qty_sent, 0 AS warehouse_id FROM {QUEUE_TABLE} WHERE order_id = ?"
    return fetch_all(sql, order_id)


def queue_inc(order_id: int, item_code: str, inc: float = 1):
    """Barkod okutuldukça `qty_sent += inc`."""
    sql = f"""UPDATE {QUEUE_TABLE} SET qty_sent = qty_sent + ? WHERE order_id = ? AND item_code = ?"""
    exec_sql(sql, inc, order_id, item_code)


def queue_delete(order_id: int):
    """Sipariş tamamlandığında kuyruğu temizle."""
    exec_sql(f"DELETE FROM {QUEUE_TABLE} WHERE order_id = ?", order_id)


_PREFIX_BY_WH = {0: "D1-", 1: "D3-", 2: "D4-", 3: "D5-"}   # depo → stok kodu ön eki

def resolve_barcode_prefix(barcode: str, warehouse_id: int) -> str | None:
    prefix = _PREFIX_BY_WH.get(warehouse_id)
    if not prefix:
        return None

    sql = f'''
        SELECT TOP 1 I.CODE
        FROM   {_t("UNITBARCODE", period_dependent=False)} UB   -- ★ düzeltildi
        JOIN   {_t("ITMUNITA",    period_dependent=False)} IU   -- ★ düzeltildi
               ON IU.LOGICALREF = UB.ITMUNITAREF
        JOIN   {_t("ITEMS",       period_dependent=False)} I
               ON I.LOGICALREF = IU.ITEMREF
        WHERE  UB.BARCODE = ?
          AND  IU.LINENR  = 1
          AND  I.CODE LIKE ?
    '''
    row = fetch_one(sql, barcode, prefix + '%')
    return row['code'] if row else None




def ensure_qr_token(order_no: str) -> str:
    """Sevkiyat başlığına qr_token yoksa üretip kaydeder, token'ı döndürür."""
    row = fetch_one("SELECT qr_token FROM shipment_header WHERE order_no=?", order_no)
    if row and row["qr_token"]:
        return row["qr_token"]
    token = str(uuid.uuid4())
    exec_sql("UPDATE shipment_header SET qr_token=?, printed=0 WHERE order_no=?",
             token, order_no)
    return token


# --------------------------------------------------------------
# Barkod ↔ stok kartı eşleme   (barcode_xref)
# --------------------------------------------------------------
def lookup_barcode(warehouse_id: str, barcode: str) -> dict | None:
    """
    Verilen barkodu ve depo kodunu `barcode_xref` tablosunda arar.
    Bulursa:
        { "item_code": "D1-AYD 60000A",
          "multiplier": 1.0 }
    aksi hâlde None.
    """
    sql = """
        SELECT item_code, multiplier
        FROM   dbo.barcode_xref
        WHERE  barcode      = ?
          AND  warehouse_id = ?
    """
    return fetch_one(sql, barcode, warehouse_id)


# ---------------------------------------------------------------------------
# Smoke‑test (yalnızca yeni fonksiyonlar)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    try:
        oid_test = 123456  # test sip.
        queue_insert(oid_test)
        rows = queue_fetch(oid_test)
        logging.info("%d satır kuyruğa kopyalandı", len(rows))
        if rows:
            queue_inc(oid_test, rows[0]['item_code'])
            logging.info("%s qty_sent +1", rows[0]['item_code'])
        queue_delete(oid_test)
        logging.info("Kuyruk temizlendi")
    except pyodbc.Error as exc:
        logging.error("DB hata: %s", exc)


# ---------------------------------------------------------------------------
# DEPRECATED: Use get_conn() instead
# ---------------------------------------------------------------------------
def get_connection(autocommit: bool = True):
    """
    DEPRECATED: Bu fonksiyon get_conn() lehine kullanımdan kaldırılmıştır.
    Geriye uyumluluk için korunmuştur.
    
    Parametreler
    ------------
    autocommit : bool
        • True  → her sorgu otomatik commit (INSERT/UPDATE/DELETE'lerde güvenli)
        • False → manuel transaction kontrolü (load_file gibi toplu insert'te)
    
    Dönüş
    -----
    pyodbc.Connection
    """
    return pyodbc.connect(CONN_STR, autocommit=autocommit)