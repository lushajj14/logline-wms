"""
backorder.py – Eksik satır & sevkiyat kayıtları
==============================================

 • İki yardımcı tablo oluşturur:
      dbo.backorders       –  eksik (missing) satırlar
      dbo.shipment_lines   –  gönderilen (shipped) satırlar
 • insert_backorder      → eksik satır ekle / güncelle
 • add_shipment          → sevk satırı ekle / güncelle
 • create_tables() ilk import’ta otomatik çalışır
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
import logging, os

from app.dao.logo import get_conn   # aynı ODBC bağlantısını kullanıyoruz

_log = logging.getLogger(__name__)
# SQL injection güvenliği için şema adını sabit tut
SCHEMA = "dbo"  # Environment variable yerine sabit değer kullan

# -------------------------------------------------------------------- #
#  TABLOLARI OLUŞTUR – yalnızca ilk import’ta                                 #
# -------------------------------------------------------------------- #
def create_tables() -> None:
    # Şema adı artık güvenli bir sabit
    ddl = f"""
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='backorders')
    CREATE TABLE {SCHEMA}.backorders(
        id           INT IDENTITY PRIMARY KEY,
        order_no     NVARCHAR(32),
        line_id      INT,
        warehouse_id INT,
        item_code    NVARCHAR(64),
        qty_missing  FLOAT,
        eta_date     DATE NULL,
        fulfilled    BIT         DEFAULT 0,
        created_at   DATETIME    DEFAULT GETDATE(),
        fulfilled_at DATETIME    NULL,
        last_update  DATETIME    DEFAULT GETDATE()
    );

    IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='shipment_lines')
    CREATE TABLE {SCHEMA}.shipment_lines(
        id            INT IDENTITY PRIMARY KEY,
        invoice_no    NVARCHAR(32),     -- bizde sipariş no
        item_code     NVARCHAR(64),
        warehouse_id  INT,
        invoiced_qty  FLOAT,
        qty_shipped   FLOAT     DEFAULT 0,
        last_update   DATETIME  DEFAULT GETDATE()
    );

    /* eksik kolonları sonradan ekle -- idempotent */
    IF NOT EXISTS (SELECT * FROM sys.columns
                   WHERE Name='trip_date'
                     AND Object_ID = Object_ID('{SCHEMA}.shipment_lines'))
        ALTER TABLE {SCHEMA}.shipment_lines
            ADD trip_date DATE NULL;

    IF NOT EXISTS (SELECT * FROM sys.columns
                   WHERE Name='order_no'
                     AND Object_ID = Object_ID('{SCHEMA}.shipment_lines'))
        ALTER TABLE {SCHEMA}.shipment_lines
            ADD order_no NVARCHAR(32) NULL;

    IF NOT EXISTS (SELECT * FROM sys.columns
                   WHERE Name='qty_sent'
                     AND Object_ID = Object_ID('{SCHEMA}.shipment_lines'))
        ALTER TABLE {SCHEMA}.shipment_lines
            ADD qty_sent FLOAT DEFAULT 0;

    IF NOT EXISTS (SELECT * FROM sys.columns
                   WHERE Name='loaded'
                     AND Object_ID = Object_ID('{SCHEMA}.shipment_lines'))
        ALTER TABLE {SCHEMA}.shipment_lines
            ADD loaded BIT DEFAULT 0;
    """
    with get_conn(autocommit=True) as cn:
        cn.execute(ddl)
    _log.info("backorders / shipment_lines tabloları hazır.")

# Lazy initialization - only create tables when needed
_tables_created = False

def ensure_tables():
    """Ensure tables exist before any operation"""
    global _tables_created
    if not _tables_created:
        try:
            create_tables()
            _tables_created = True
        except Exception as e:
            _log.warning(f"Could not create tables on startup: {e}")
            # Will retry on first actual operation

# -------------------------------------------------------------------- #
#  BACK-ORDER KAYITLARI                                                #
# -------------------------------------------------------------------- #
def insert_backorder(order_no:str, line_id:int, warehouse_id:int,
                     item_code:str, qty_missing:float, eta_date:Optional[str]=None):
    """
    Aynı sipariş + stok için kayıt varsa qty_missing değerini günceller (idempotent).
    NOT: Artık qty_missing değerini toplamıyor, doğrudan set ediyor.
    """
    # Parametreli sorgu - şema adı güvenli sabit
    sql_sel = f"""SELECT id, qty_missing FROM {SCHEMA}.backorders
                  WHERE fulfilled=0 AND order_no=? AND item_code=?"""
    # Parametreli insert - SQL injection güvenli
    sql_ins = f"""INSERT INTO {SCHEMA}.backorders
                  (order_no,line_id,warehouse_id,item_code,qty_missing,eta_date)
                  VALUES (?,?,?,?,?,?)"""
    # Parametreli update - SQL injection güvenli
    sql_upd = f"""UPDATE {SCHEMA}.backorders
                  SET qty_missing = ?, last_update = GETDATE()
                  WHERE id=?"""
    with get_conn(autocommit=True) as cn:
        row = cn.execute(sql_sel, order_no, item_code).fetchone()
        if row:
            # Doğrudan yeni değeri set et, toplama yapma
            cn.execute(sql_upd, qty_missing, row.id)
        else:
            cn.execute(sql_ins,
                       order_no,line_id,warehouse_id,item_code,qty_missing,eta_date)

def add_shipment(order_no: str,          # sipariş / fatura kökü
                 trip_date: str,         # YYYY-MM-DD  → gün anahtarı
                 item_code: str,
                 warehouse_id: int,
                 invoiced_qty: float,    # Logo’daki fatura adedi
                 qty_delta: float):      # bu sevk-tamamlama ile gönderilen

    """
    • Aynı (trip_date + order_no + item_code) satırı varsa
      qty_sent (eski adı qty_shipped) alanını artırır.
    • Yoksa yeni satır açar.
    """

    sql = f"""
    MERGE {SCHEMA}.shipment_lines AS tgt
    USING (SELECT
              ? AS trip_date,
              ? AS order_no,
              ? AS item_code) src
      ON  tgt.trip_date  = src.trip_date
      AND tgt.order_no   = src.order_no
      AND tgt.item_code  = src.item_code
    WHEN MATCHED THEN
        UPDATE
           SET qty_sent    = qty_sent + ?,
               last_update = GETDATE()
    WHEN NOT MATCHED THEN
        INSERT (trip_date, order_no, item_code,
                warehouse_id, invoiced_qty, qty_sent, loaded,
                last_update)
        VALUES (?,?,?,?,?,?,0,GETDATE());
    """

    with get_conn(autocommit=True) as cn:
        cn.execute(sql,
                   trip_date, order_no, item_code,      # src
                   qty_delta,                           # UPDATE
                   trip_date, order_no, item_code,      # INSERT
                   warehouse_id, invoiced_qty, qty_delta)


# -------------------------------------------------------------------- #
#  YARDIMCI LİSTELER                                                   #
# -------------------------------------------------------------------- #
def list_pending() -> List[Dict[str,Any]]:
    """Bekleyen backorder'ları müşteri ve ürün bilgileriyle birlikte getirir"""
    # Logo ERP tablo isimleri için _t fonksiyonunu import et
    from app.dao.logo import _t
    
    sql = f"""
    SELECT 
        b.*,
        C.DEFINITION_ as customer_name,
        C.CODE as customer_code,
        I.NAME as item_name
    FROM {SCHEMA}.backorders b
    LEFT JOIN {_t('ORFICHE')} O ON b.order_no = O.FICHENO
    LEFT JOIN {_t('CLCARD', period_dependent=False)} C ON O.CLIENTREF = C.LOGICALREF
    LEFT JOIN {_t('ITEMS', period_dependent=False)} I ON b.item_code = I.CODE
    WHERE b.fulfilled = 0
    ORDER BY b.order_no, b.item_code
    """
    with get_conn() as cn:
        cur = cn.execute(sql)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols,row)) for row in cur.fetchall()]

def mark_fulfilled(back_id:int):
    sql = f"""UPDATE {SCHEMA}.backorders
              SET fulfilled=1, fulfilled_at=GETDATE() WHERE id=?"""
    with get_conn(autocommit=True) as cn:
        cn.execute(sql, back_id)


# --------------------------------------------------------------------
#  Tamamlanmış eksikler – listele
# --------------------------------------------------------------------
def list_fulfilled(on_date: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = f"SELECT * FROM {SCHEMA}.backorders WHERE fulfilled = 1"
    if on_date:
        # güvenlik / performans için parametreli ver
        sql += " AND CAST(fulfilled_at AS DATE) = ?"
        params = (on_date,)
    else:
        params = ()
    with get_conn() as cn:
        cur = cn.execute(sql, *params)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

