"""
backorder_picklist.py – Mini Pick‑List (Eksik Ürün Tamamlamaları)
================================================================
Eksik ürünler tamamlandığında çalışan ad-hoc PDF pick‑list.

Kullanım
--------
# Belirli tarih (YYYY-MM-DD) için (default: bugün)
python -m app.services.backorder_picklist --date 2025-05-30

Çıktı
-----
`picklists/BACKORDER_PICKLIST_YYYYMMDD.pdf` dosyası

İçerik
------
| Saat      | Sipariş No   | Ürün Kodu          | Koli  | Amb  |
|-----------|--------------|--------------------|-----:|----:|
| 13:19:29  | SM2025-000181| D1-ZEG984-00       |    1  |    0 |
…
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path
from typing import List, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# Proje dizinine ekle
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.dao import logo as dao

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# PDF Ayarları
OUT_DIR = BASE_DIR / "picklists"
OUT_DIR.mkdir(exist_ok=True)
FONT_PATH = BASE_DIR / "fonts" / "DejaVuSans.ttf"
if FONT_PATH.exists():
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_PATH)))
    FONT = "DejaVu"
else:
    FONT = "Helvetica"

def fetch_fulfilled(date: dt.date) -> List[Dict]:
    # Parameter binding for date may fail on ODBC driver; inline literal.
    date_str = date.strftime("%Y-%m-%d")
    sql = f"""
    SELECT order_no, item_code, qty_missing AS qty, warehouse_id, fulfilled_at
      FROM backorders
     WHERE fulfilled = 1
       AND CAST(fulfilled_at AS DATE) = '{date_str}'
    """
    with dao.get_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    sql = f"""
    SELECT order_no, item_code, qty_missing AS qty, warehouse_id, fulfilled_at
      FROM backorders
     WHERE fulfilled = 1
       AND CAST(fulfilled_at AS DATE) = ?
    """
    with dao.get_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql, date)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def create_picklist(date: dt.date):
    records = fetch_fulfilled(date)
    if not records:
        logger.info("%s için tamamlanan eksik ürün yok", date)
        return

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUT_DIR / f"BACKORDER_PICKLIST_{date.strftime('%Y%m%d')}_{ts}.pdf"
    doc = SimpleDocTemplate(str(out_file), pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm)

    # Başlık
    elements = []
    title = f"Eksik Ürün Tamamlamaları - {date.strftime('%d-%m-%Y')}"
    elements.append(Paragraph(title, ParagraphStyle("title", fontName=FONT, fontSize=14, leading=16)))
    elements.append(Spacer(1, 6*mm))

    # Tablo verisi
    data = [["Saat", "Sipariş No", "Ürün Kodu", "Adet", "Amb"]]
    for r in records:
        time_str = r['fulfilled_at'].strftime("%H:%M:%S")
        data.append([time_str, r['order_no'], r['item_code'], str(r['qty']), str(r['warehouse_id'])])

    tbl = Table(data, colWidths=[30*mm, 50*mm, 60*mm, 20*mm, 20*mm])
    tbl.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 9),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (3,1), (4,-1), "CENTER"),
    ]))
    elements.append(tbl)

    # PDF oluştur
    doc.build(elements)
    logger.info("Pick-list oluşturuldu → %s", out_file.relative_to(BASE_DIR))


def main():
    ap = argparse.ArgumentParser(description="Backorder Pick-list PDF oluşturucu")
    ap.add_argument("--date", help="Tarih (YYYY-MM-DD)", default=dt.date.today().isoformat())
    args = ap.parse_args()

    try:
        date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Geçersiz tarih: %s", args.date)
        return

    create_picklist(date)


if __name__ == "__main__":
    main()
