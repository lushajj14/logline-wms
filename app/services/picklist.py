"""
service_picklist.py
===================
STATUS=1 (öneri) siparişleri algılar, PDF pick‑list oluşturur ve siparişi
"picking" (STATUS = 2) durumuna çeker.

Kullanım
--------
# Tek sefer
python -m app.services.picklist --once
# Watcher (varsayılan 30 s)
python -m app.services.picklist --interval 45

PDF Özellikleri
---------------
* **Unicode DejaVu Sans** font – Türkçe karakter sorunu yok.
* Kolon genişlikleri: 55 mm | 105 mm | 20 mm
* Ürün adı hücresi otomatik satır kırar (Paragraph).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

# Import centralized WMS path management
from app.utils.wms_paths import get_wms_folders, get_picklist_path

# ---------------------------------------------------------------------------
# Paket yolu – script doğrudan çalıştırılırsa dao'yu bulsun
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

try:
    from app.dao.logo import (
        fetch_draft_orders,
        fetch_order_lines,
        update_order_status,
    )
except ModuleNotFoundError:
    from dao.logo import (
        fetch_draft_orders,
        fetch_order_lines,
        update_order_status,
    )

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# ---------------------------------------------------------------------------
# Font kaydı - Determine base directory based on execution mode
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    # Running as PyInstaller executable
    FONT_BASE_DIR = Path(sys._MEIPASS)
else:
    # Running in development
    FONT_BASE_DIR = Path(__file__).resolve().parent.parent

# Try multiple font paths
font_paths = [
    str(FONT_BASE_DIR / "app" / "fonts" / "DejaVuSans.ttf"),
    str(FONT_BASE_DIR / "fonts" / "DejaVuSans.ttf"),
    os.getenv("PICKLIST_FONT_PATH", ""),
    str(Path(__file__).resolve().parent.parent / "fonts" / "DejaVuSans.ttf"),
    str(Path(__file__).resolve().parent.parent / "app" / "fonts" / "DejaVuSans.ttf"),
]

DEFAULT_FONT = "Helvetica"  # Default fallback
for font_path in font_paths:
    if font_path and Path(font_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
            DEFAULT_FONT = "DejaVuSans"
            logger.info("Font loaded from: %s", font_path)
            break
        except Exception as e:
            logger.warning("Could not load font from %s: %s", font_path, e)
            continue

if DEFAULT_FONT == "Helvetica":
    logger.warning("DejaVuSans.ttf not found; using Helvetica (Turkish characters may not display correctly)")

PARA_STYLE = ParagraphStyle(
    name="tbl",
    fontName=DEFAULT_FONT,
    fontSize=8,
    leading=9,
    wordWrap="CJK",
)

# Use centralized WMS path management
wms_folders = get_wms_folders()
OUT_DIR = wms_folders['picklists']

# ---------------------------------------------------------------------------
# PDF üretici
# ---------------------------------------------------------------------------

def create_picklist_pdf(order: dict, lines: List[dict]) -> Path:
    """Siparişe ait pick‑list PDF’sini oluşturur ve yolunu döndürür."""
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Clean filename - remove problematic characters
    order_no = str(order['order_no']).replace('/', '_').replace('\\', '_')
    filename = f"PICKLIST_{ts}_ORD{order_no}.pdf"
    
    # Use centralized path management
    pdf_path = get_picklist_path(filename)
    
    # Ensure directory exists
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # ReportLab Path objesini kabul etmez – stringe dönüştürüyoruz
    doc = SimpleDocTemplate(str(pdf_path).replace('\\', '/'), pagesize=A4,
                            topMargin=25*mm, bottomMargin=20*mm)

    elements = []
    
    # First line: Order and Customer
    head = (
        f"<b>Sipariş No:</b> {order['order_no']}  "
        f"<b>Müşteri:</b> {order['customer_code']} – {order['customer_name']}"
    )
    elements.append(Paragraph(head, ParagraphStyle("head", fontName=DEFAULT_FONT, fontSize=12, leading=14)))
    
    # Second line: Region info if available
    region = f"{order.get('genexp2', '')} - {order.get('genexp3', '')}".strip(" -")
    if region:
        region_text = f"<b>Bölge:</b> {region}"
        elements.append(Paragraph(region_text, ParagraphStyle("region", fontName=DEFAULT_FONT, fontSize=10, leading=12)))
    
    elements.append(Spacer(1, 6 * mm))

    data = [["Stok Kodu", "Ürün Adı", "Adet"]]
    for l in lines:
        data.append([
            Paragraph(l["item_code"], PARA_STYLE),
            Paragraph(l["item_name"], PARA_STYLE),
            Paragraph(str(l["qty_ordered"]), PARA_STYLE),
        ])

    tbl = Table(data, colWidths=[55 * mm, 105 * mm, 20 * mm])
    tbl.setStyle(
        TableStyle([
            ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ])
    )

    elements.append(tbl)
    
    # Özet bilgileri ekle
    elements.append(Spacer(1, 6 * mm))
    
    # Benzersiz ürün sayısını hesapla
    unique_products = len(set(line["item_code"] for line in lines if line.get("item_code")))
    total_qty = sum(line.get("qty_ordered", 0) for line in lines)
    
    summary_text = f"<b>Toplam:</b> {unique_products} kalem, {total_qty} adet"
    elements.append(Paragraph(summary_text, ParagraphStyle("summary", fontName=DEFAULT_FONT, fontSize=10)))
    
    doc.build(elements)
    return pdf_path

# ---------------------------------------------------------------------------
# Sipariş işleyici
# ---------------------------------------------------------------------------

def process_order(order: dict):
    lines = fetch_order_lines(order["order_id"])
    pdf_path = create_picklist_pdf(order, lines)
    logger.info("PDF oluşturuldu: %s", pdf_path.relative_to(BASE_DIR))
    update_order_status(order["order_id"], 2)  # picking
    logger.info("Sipariş %s STATUS=2 yapıldı", order["order_no"])

# ---------------------------------------------------------------------------
# Watcher döngüsü
# ---------------------------------------------------------------------------

def watcher_loop(interval: int):
    logger.info("Pick‑list watcher %d sn aralıkla çalışıyor…", interval)
    while True:
        try:
            orders = fetch_draft_orders(limit=50)
            for o in orders:
                process_order(o)
        except Exception as exc:
            logger.error("Watcher döngüsü hatası: %s", exc)
        time.sleep(interval)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pick‑list PDF oluşturucu")
    parser.add_argument("--once", action="store_true", help="Tek sefer çalış ve çık")
    parser.add_argument("--interval", type=int, default=30, help="Watcher döngü süresi (sn)")
    args = parser.parse_args()

    if args.once:
        for o in fetch_draft_orders(limit=10):
            process_order(o)
    else:
        watcher_loop(args.interval)

if __name__ == "__main__":
    main()
