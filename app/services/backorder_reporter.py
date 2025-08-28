"""
backorder_reporter.py – Eksik & Tamamlanan Ürün Raporu
====================================================

Bu script, `backorders` tablosundaki bekleyen ve belirli tarihte tamamlanan
kayıtları çeker ve **Excel** formatında çıktı üretir.

Kullanım
--------
# Bugünün raporu
python -m app.services.backorder_reporter
# Belirli tarih (YYYY-MM-DD)
python -m app.services.backorder_reporter --date 2025-05-30

Çıktı
-----
reports/BACKORDER_REPORT_YYYYMMDD.xlsx
"""
import os, sys, logging, argparse
from datetime import datetime, date
from pathlib import Path
import pandas as pd

# Proje kökü PYTHONPATH'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.dao import logo as dao
import app.backorder as bo

# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
def fetch_pending() -> pd.DataFrame:
    """fulfilled=0 olan bekleyen eksik ürünleri getirir"""
    sql = """
    SELECT order_no, item_code, qty_missing, warehouse_id, created_at
      FROM backorders
     WHERE fulfilled = 0
    """
    with dao.get_conn() as cn:
        return pd.read_sql(sql, cn)

# ---------------------------------------------------------------------------
def fetch_completed(on_date: date) -> pd.DataFrame:
    """Belirli tarihte fulfilled=1 olan kayıtları getirir"""
    sql = """
    SELECT order_no, item_code, qty_missing, warehouse_id, fulfilled_at
      FROM backorders
     WHERE fulfilled = 1
       AND CAST(fulfilled_at AS DATE) = ?
    """
    with dao.get_conn() as cn:
        return pd.read_sql(sql, cn, params=[on_date.strftime("%Y-%m-%d")])

# ---------------------------------------------------------------------------
def generate_report(report_date: date):
    """Excel raporu oluşturur: Bekleyen & Tamamlanan sayfaları"""
    df_pending   = fetch_pending()
    df_completed = fetch_completed(report_date)

    out_dir = Path(os.getenv("REPORT_OUTPUT_DIR", BASE_DIR / "reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"BACKORDER_REPORT_{report_date.strftime('%Y%m%d')}.xlsx"

    with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
        df_pending.to_excel(writer, sheet_name='Bekleyen', index=False)
        startrow = len(df_pending) + 3
        df_completed.to_excel(writer, sheet_name='Tamamlanan', index=False, startrow=startrow)

    logger.info("Rapor oluşturuldu → %s", report_path)

# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Backorder rapor oluşturucu")
    ap.add_argument(
        "--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(), help="Rapor tarihi (YYYY-MM-DD)"
    )
    args = ap.parse_args()
    generate_report(args.date)

if __name__ == "__main__":
    main()
