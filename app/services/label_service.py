"""
label_service.py – V6 (CAN Otomotiv, 100 × 100 mm + Footer)
====================================================
• Tek PDF → çok sayfa (koli adedi)
• Sayfa boyutu **100 mm × 100 mm**
• DejaVu Sans Unicode font gömülü → Türkçe karakter sorunu yok
• Barkod, fatura no, tarih, transfer vb.
• Dinamik footer desteği: tüm etiketlerin en altına ortalanmış metin eklenebilir

Kullanım
--------
```bash
python -m app.services.label_service --order-no SO2025-000202
python -m app.services.label_service --order-no SO2025-000202 --force
```
`--force`: Fatura yoksa sipariş no barkodlanır

Ek argüman
----------
`--footer "METİN"` : Etiket altına ortalanmış footer metni

Env vars
--------
FONT_PATH = "app/fonts/DejaVuSans.ttf"
LABEL_OUT_DIR (default: ./labels)
"""
from __future__ import annotations

__all__ = ['make_labels']

import os
import sys
import re
import logging
import argparse
import datetime as dt
from typing import Dict, Optional
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pyodbc

try:
    from app.dao import logo as dao
    from app import settings as st
except (ModuleNotFoundError, ImportError):
    try:
        import dao.logo as dao
        st = None  # settings yoksa env var kullan
    except (ModuleNotFoundError, ImportError):
        # PyInstaller frozen executable için
        import sys
        if hasattr(sys, '_MEIPASS'):
            # Frozen modda çalışıyoruz
            from dao import logo as dao
            st = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# ---------------------------------------------------------------------------
# Determine base directory based on execution mode
if getattr(sys, 'frozen', False):
    # Running as PyInstaller executable
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Running in development
    BASE_DIR = Path(__file__).resolve().parent.parent

COMPANY_TEXT = "CAN OTOMOTIV"
PAGE_SIZE    = (100*mm, 100*mm)

# Use centralized WMS path management
try:
    from app.utils.wms_paths import get_label_path, get_wms_folders
    wms_folders = get_wms_folders()
    LABEL_DIR = wms_folders['labels']
    OUT_DIR = LABEL_DIR
except ImportError:
    # Fallback if wms_paths not available
    LABEL_DIR = Path.home() / "Documents" / "WMS" / "labels"
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR = LABEL_DIR

# Try multiple font paths
font_paths = [
    str(BASE_DIR / "app" / "fonts" / "DejaVuSans.ttf"),
    str(BASE_DIR / "fonts" / "DejaVuSans.ttf"),
    os.getenv("FONT_PATH", ""),
    str(Path(__file__).resolve().parent.parent / "fonts" / "DejaVuSans.ttf"),
    str(Path(__file__).resolve().parent.parent / "app" / "fonts" / "DejaVuSans.ttf"),
]

FONT_NAME = "Helvetica"  # Default fallback
for font_path in font_paths:
    if font_path and Path(font_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))
            FONT_NAME = "DejaVu"
            logging.info(f"Font loaded from: {font_path}")
            break
        except Exception as e:
            logging.warning(f"Could not load font from {font_path}: {e}")
            continue

if FONT_NAME == "Helvetica":
    logging.warning("DejaVuSans.ttf not found; using Helvetica (Turkish characters may not display correctly)")

# ---------------------------------------------------------------------------
def get_current_user_first_name() -> str:
    """Get the first name of the current user from settings."""
    try:
        from app.settings_manager import get_manager
        manager = get_manager()
        username = manager.get("login.last_username", "")
        
        # Get user's full name from database
        with dao.get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("SELECT name FROM users WHERE username = ?", username)
            row = cursor.fetchone()
            if row and row[0]:
                # Extract first name (MUSTAFA KUYAR -> MUSTAFA)
                full_name = str(row[0]).strip()
                first_name = full_name.split()[0] if full_name else username
                return first_name.upper()
        return username.upper()
    except Exception as e:
        logging.debug(f"Could not get user first name: {e}")
        return ""

# ---------------------------------------------------------------------------
def parse_int(text: str, default:int=1) -> int:
    m = re.search(r"(\d+)", text or "")
    return int(m.group(1)) if m else default

# ---------------------------------------------------------------------------
def fetch_invoice_no(order_no: str) -> Optional[str]:
    """Fatura no al (CAN*/ARV* öncelikli)"""
    sqls = [
        f"""
        SELECT TOP 1 I.FICHENO
        FROM {dao._t('INVOICE')} I
        JOIN {dao._t('STLINE')} S ON S.INVOICEREF = I.LOGICALREF
        WHERE S.ORDFICHEREF IN (
              SELECT LOGICALREF FROM {dao._t('ORFICHE')} WHERE FICHENO = ?)
          AND I.CANCELLED = 0
          AND (I.FICHENO LIKE 'CAN%' OR I.FICHENO LIKE 'ARV%')
        """,
        f"""
        SELECT TOP 1 FICHENO
        FROM {dao._t('INVOICE')}
        WHERE SPECODE = ? AND CANCELLED=0
        """,
    ]
    with dao.get_conn() as cn:
        for sql in sqls:
            try:
                row = cn.execute(sql, order_no).fetchone()
                if row:
                    return row[0]
            except pyodbc.ProgrammingError:
                continue
    return None

# ---------------------------------------------------------------------------
def draw_page(c: canvas.Canvas, p: Dict[str, str]):
    """Tek koli etiketi (100×100 mm) çizer"""
    x = 6*mm
    y = 93*mm

    # Başlık & bölge
    c.setFont(FONT_NAME, 14)
    c.drawString(x, y, COMPANY_TEXT)
    c.setFont(FONT_NAME, 10)
    c.drawRightString(PAGE_SIZE[0]-x, y, "GEREDE")

    y -= 6*mm
    c.setFont(FONT_NAME, 8)
    c.drawRightString(PAGE_SIZE[0]-x, y, p["region"])

    # Cari kodu & adı
    y -= 10*mm
    c.setFont(FONT_NAME, 8)
    c.drawString(x, y, p["cari_kodu"])
    y -= 5*mm
    c.setFont(FONT_NAME, 10)
    c.drawString(x, y, p["cari_adi"])

    # Adres
    c.setFont(FONT_NAME, 8)
    for line in p["adres_lines"]:
        y -= 4*mm
        c.drawString(x, y, line)

    # Sipariş No & Koli
    y -= 6*mm
    c.setFont(FONT_NAME, 10)
    c.drawString(x, y, f"Sipariş No: {p['order_no']}")
    c.drawRightString(PAGE_SIZE[0]-x, y, f"Koli: {p['pkg_no']}/{p['pkg_tot']}")

    # Barkod
    y -= 20*mm
    bc = code128.Code128(p["barkod"], barHeight=12*mm, barWidth=0.825)
    bc_x = (PAGE_SIZE[0] - bc.width) / 2
    bc.drawOn(c, bc_x, y)

    # Barkod altı fatura no
    y -= 7*mm
    c.setFont(FONT_NAME, 8)
    c.drawCentredString(PAGE_SIZE[0]/2, y, p["barkod"])

    # Sipariş tarihi & transfer
    y -= 6*mm
    c.setFont(FONT_NAME, 7)
    c.drawString(x, y, f"Sipariş Tarihi: {p['sip_tarih']}")
    if p.get("transfer"):
        c.drawRightString(PAGE_SIZE[0]-x, y, f"Transfer: {p['transfer']}")

    # İlk sayfa için fatura hatırlatma metni
    if p.get("inv_line"):
        y -= 8*mm
        c.setFont(FONT_NAME, 9)
        c.drawCentredString(PAGE_SIZE[0]/2, y, p["inv_line"])

    # Footer (ör: "EKSİK GÖNDERİLEN SEVKİYAT")
    if p.get("footer"):
        c.setFont(FONT_NAME, 8)
        c.drawCentredString(PAGE_SIZE[0]/2, 5*mm, p["footer"])
    
    # User name in bottom right
    if p.get("user_name"):
        c.setFont(FONT_NAME, 7)
        c.drawRightString(PAGE_SIZE[0]-6*mm, 3*mm, p["user_name"])
    
    # Print date/time in bottom left
    if p.get("print_datetime"):
        c.setFont(FONT_NAME, 6)
        c.drawString(6*mm, 3*mm, p["print_datetime"])

    c.showPage()


# ---------------------------------------------------------------------------
def make_labels(order_no: str, *, force: bool = False, footer: str = ""):
    """
    • Her paket için barkod  →  FaturaNo-K1 , FaturaNo-K2 …
    • force=True  → fatura yoksa da sipariş no kullanılır.
    """
    hdr = dao.fetch_order_header(order_no)
    if not hdr:
        logging.error("Sipariş bulunamadı: %s", order_no)
        sys.exit(1)

    invoice_no = fetch_invoice_no(order_no)
    if not invoice_no and not force:
        logging.warning("Fatura yok – basılmadı")
        sys.exit(1)

    barkod_root = invoice_no or order_no           # ← temel kısım
    pkg_tot     = parse_int(hdr.get("genexp4", "1"))

    # Ensure safe filename (remove any path separators)
    safe_order_no = order_no.replace('/', '_').replace('\\', '_')
    pdf_filename = f"LABEL_{dt.datetime.now():%Y%m%d_%H%M%S}_{safe_order_no}.pdf"
    pdf_path = OUT_DIR / pdf_filename
    
    # Ensure directory exists
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Convert to string with forward slashes
    pdf_path_str = str(pdf_path).replace('\\', '/')
    c = canvas.Canvas(pdf_path_str, pagesize=PAGE_SIZE)

    # — adres satırlarını kır —
    adres_raw   = (hdr.get("adres", "").upper()).split()
    adres_lines = [" ".join(adres_raw[i:i + 6]) for i in range(0, len(adres_raw), 6)][:2]
    
    # Get current user's first name
    user_name = get_current_user_first_name()
    
    # Get current datetime for print timestamp
    print_datetime = dt.datetime.now().strftime("%d.%m.%Y %H:%M")

    for i in range(1, pkg_tot + 1):
        barkod = f"{barkod_root}-K{i}"             # ← 🔸 YENİ: paket no ekle

        payload = {
            "order_no":   order_no,
            "pkg_no":     i,
            "pkg_tot":    pkg_tot,
            "barkod":     barkod,                  # ← güncel barkod
            "cari_kodu":  hdr.get("cari_kodu", ""),
            "cari_adi":   hdr.get("cari_adi", "")[:30],
            "adres_lines": adres_lines,
            "region":     f"{hdr.get('genexp2','')} - {hdr.get('genexp3','')}".strip(" -"),
            "sip_tarih":  dt.datetime.now().strftime("%d-%m-%Y"),
            "transfer":   hdr.get("genexp1", "").strip(";"),
            "inv_line":   "FATURA BU PAKETİN İÇİNDEDİR" if i == 1 else "",
            "footer":     footer,
            "user_name":  user_name,
            "print_datetime": print_datetime,
        }
        draw_page(c, payload)

    c.save()
    logging.info("PDF etiketi oluşturuldu: %s", pdf_path)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="CAN Otomotiv etiket PDF")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--order-no", "--order", help="Sipariş no (FICHENO)")
    grp.add_argument("--id", type=int, help="Sipariş LOGICALREF")
    ap.add_argument("--force", action="store_true", help="Fatura yoksa da bastır")
    ap.add_argument("--footer", default="", help="Etiket altına ortalanacak metin")
    args = ap.parse_args()

    hdr = dao.fetch_order_header(args.order_no)
    if not hdr:
        logging.error("Sipariş no bulunamadı!")
        sys.exit(1)

    ord_no = hdr.get("order_no")

    if not ord_no:
        logging.error("Geçersiz order_no, işlem atlandı!")
        sys.exit(1)

    make_labels(ord_no, force=args.force, footer=args.footer)

# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    main()
