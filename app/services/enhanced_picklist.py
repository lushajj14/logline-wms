"""
Enhanced Picklist Service
=========================
Geliştirilmiş picklist servisi:
- Günlük sipariş özeti
- Kullanıcı ve zaman bilgisi
- İstatistikler
- Otomatik bildirimler
"""

from __future__ import annotations
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    KeepTogether,
)

# Package paths
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.dao.logo import (
    fetch_draft_orders,
    fetch_order_lines,
    update_order_status,
    fetch_all,
    _t,
)
from app.dao.logo_tables import LogoTables
from app.settings_manager import get_manager
from app.utils.wms_paths import get_wms_folders, get_picklist_path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# Font registration - Determine base directory based on execution mode
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

# Use centralized WMS path management
wms_folders = get_wms_folders()
OUT_DIR = wms_folders['picklists']

# Styles
styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle(
    name="Title",
    fontName=DEFAULT_FONT,
    fontSize=14,
    leading=16,
    alignment=1,  # Center
    spaceAfter=12,
)

HEADER_STYLE = ParagraphStyle(
    name="Header",
    fontName=DEFAULT_FONT,
    fontSize=10,
    leading=12,
    textColor=colors.HexColor("#333333"),
)

PARA_STYLE = ParagraphStyle(
    name="tbl",
    fontName=DEFAULT_FONT,
    fontSize=8,
    leading=9,
    wordWrap="CJK",
)

FOOTER_STYLE = ParagraphStyle(
    name="Footer",
    fontName=DEFAULT_FONT,
    fontSize=7,
    leading=8,
    textColor=colors.HexColor("#666666"),
    alignment=1,
)


def get_current_user() -> str:
    """Get current user from settings."""
    try:
        manager = get_manager()
        username = manager.get("login.last_username", "sistem")
        
        # Try to get full name from database
        from app.dao.logo import fetch_one
        user = fetch_one("SELECT name FROM users WHERE username = ?", username)
        if user and user.get("name"):
            return user["name"]
        return username.upper()
    except:
        return "SİSTEM"


def get_daily_statistics() -> Dict[str, any]:
    """Get daily order statistics."""
    try:
        today = datetime.now().date()
        
        # Bugünkü siparişler
        today_orders = fetch_all(f"""
            SELECT COUNT(*) as count, 
                   SUM(CASE WHEN STATUS = 1 THEN 1 ELSE 0 END) as draft,
                   SUM(CASE WHEN STATUS = 2 THEN 1 ELSE 0 END) as picking,
                   SUM(CASE WHEN STATUS = 4 THEN 1 ELSE 0 END) as completed
            FROM {_t('ORFICHE')}
            WHERE CAST(DATE_ AS DATE) = ?
            AND FICHENO LIKE 'S%{LogoTables.ORDER_YEAR}%'
        """, today)
        
        if today_orders:
            stats = today_orders[0]
            return {
                "total": stats.get("count", 0),
                "draft": stats.get("draft", 0),
                "picking": stats.get("picking", 0),
                "completed": stats.get("completed", 0),
                "date": today.strftime("%d.%m.%Y"),
            }
    except Exception as e:
        logger.error(f"İstatistik alınamadı: {e}")
    
    return {
        "total": 0,
        "draft": 0,
        "picking": 0,
        "completed": 0,
        "date": datetime.now().strftime("%d.%m.%Y"),
    }


def create_enhanced_picklist_pdf(order: dict, lines: List[dict]) -> Path:
    """Create enhanced picklist PDF with user info and statistics."""
    
    ts = datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    
    # Clean filename - remove problematic characters
    order_no = str(order['order_no']).replace('/', '_').replace('\\', '_')
    filename = f"PICKLIST_{ts_str}_ORD{order_no}.pdf"
    
    # Use centralized path management
    pdf_path = get_picklist_path(filename)
    
    # Ensure directory exists
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    
    doc = SimpleDocTemplate(
        str(pdf_path).replace('\\', '/'), 
        pagesize=A4,
        topMargin=20*mm, 
        bottomMargin=25*mm,
        title=f"Picklist - {order_no}",
        author=get_current_user(),
    )
    
    elements = []
    
    # Title
    title = Paragraph(f"<b>TOPLAMA LİSTESİ</b>", TITLE_STYLE)
    elements.append(title)
    
    # Order info header
    # Construct region string like in label_service.py
    region = f"{order.get('genexp2', '')} - {order.get('genexp3', '')}".strip(" -")
    
    order_info = f"""
    <b>Sipariş No:</b> {order['order_no']}<br/>
    <b>Müşteri:</b> {order['customer_code']} - {order['customer_name']}<br/>"""
    
    # Add region if available
    if region:
        order_info += f"""
    <b>Bölge:</b> {region}<br/>"""
    
    order_info += f"""
    <b>Tarih:</b> {order.get('order_date', ts).strftime('%d.%m.%Y') if hasattr(order.get('order_date', ts), 'strftime') else order.get('order_date', '')}<br/>
    <b>Hazırlayan:</b> {get_current_user()}<br/>
    <b>Hazırlanma:</b> {ts.strftime('%d.%m.%Y %H:%M')}
    """
    elements.append(Paragraph(order_info, HEADER_STYLE))
    elements.append(Spacer(1, 10*mm))
    
    # Product table
    data = [["Sıra", "Stok Kodu", "Ürün Adı", "Adet", "Lokasyon", "Toplanan"]]
    
    for idx, line in enumerate(lines, 1):
        data.append([
            str(idx),
            Paragraph(line.get("item_code", ""), PARA_STYLE),
            Paragraph(line.get("item_name", ""), PARA_STYLE),
            Paragraph(str(line.get("qty_ordered", 0)), PARA_STYLE),
            "",  # Lokasyon - ileride eklenebilir
            "☐",  # Checkbox for picking
        ])
    
    tbl = Table(data, colWidths=[15*mm, 35*mm, 75*mm, 20*mm, 25*mm, 15*mm])
    tbl.setStyle(TableStyle([
        # Header style
        ("FONT", (0, 0), (-1, 0), DEFAULT_FONT, 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A90E2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        
        # Body style
        ("FONT", (0, 1), (-1, -1), DEFAULT_FONT, 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),  # Sıra no
        ("ALIGN", (3, 1), (3, -1), "CENTER"),  # Adet
        ("ALIGN", (5, 1), (5, -1), "CENTER"),  # Checkbox
        
        # Zebra striping
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ]))
    
    elements.append(KeepTogether(tbl))
    
    # Summary section
    elements.append(Spacer(1, 10*mm))
    
    # Benzersiz ürün sayısını hesapla
    unique_products = len(set(line.get("item_code") for line in lines if line.get("item_code")))
    
    summary_data = [
        ["Toplam Kalem:", str(unique_products)],  # Artık benzersiz ürün sayısı
        ["Toplam Adet:", str(sum(line.get("qty_ordered", 0) for line in lines))],
    ]
    
    summary_table = Table(summary_data, colWidths=[40*mm, 30*mm])
    summary_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F4FD")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#4A90E2")),
    ]))
    
    elements.append(summary_table)
    
    # Notes section
    elements.append(Spacer(1, 10*mm))
    notes_title = Paragraph("<b>Notlar:</b>", HEADER_STYLE)
    elements.append(notes_title)
    
    # Empty lines for notes
    for _ in range(3):
        elements.append(Paragraph("_" * 80, PARA_STYLE))
        elements.append(Spacer(1, 5*mm))
    
    # Footer with daily statistics
    stats = get_daily_statistics()
    footer_text = f"""
    <i>Günlük Özet ({stats['date']}): 
    Toplam {stats['total']} sipariş | 
    {stats['draft']} Taslak | 
    {stats['picking']} Toplanıyor | 
    {stats['completed']} Tamamlandı</i>
    """
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(footer_text, FOOTER_STYLE))
    
    # Build PDF
    doc.build(elements)
    
    return pdf_path


def create_daily_summary_pdf() -> Path:
    """Create daily summary PDF with all orders."""
    
    ts = datetime.now()
    ts_str = ts.strftime("%Y%m%d")
    
    # Use centralized path management
    filename = f"DAILY_SUMMARY_{ts_str}.pdf"
    pdf_path = get_picklist_path(filename)
    
    # Ensure directory exists
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    
    doc = SimpleDocTemplate(
        str(pdf_path).replace('\\', '/'),
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        title=f"Günlük Sipariş Özeti - {ts_str}",
        author=get_current_user(),
    )
    
    elements = []
    
    # Title
    title = Paragraph(f"<b>GÜNLÜK SİPARİŞ ÖZETİ</b><br/>{ts.strftime('%d.%m.%Y')}", TITLE_STYLE)
    elements.append(title)
    elements.append(Spacer(1, 10*mm))
    
    # Get all orders for today
    try:
        today_orders = fetch_all(f"""
            SELECT O.FICHENO as order_no,
                   O.DATE_ as order_date,
                   O.STATUS as status,
                   O.DOCODE as customer_code,
                   O.NETTOTAL as total_amount,
                   O.GENEXP1 as notes,
                   O.GENEXP2 as genexp2,
                   O.GENEXP3 as genexp3
            FROM {_t('ORFICHE')} O
            WHERE CAST(O.DATE_ AS DATE) = CAST(GETDATE() AS DATE)
            AND O.FICHENO LIKE 'S%{LogoTables.ORDER_YEAR}%'
            ORDER BY O.STATUS, O.FICHENO
        """)
    except:
        # Fallback - sadece siparişleri al
        today_orders = fetch_all(f"""
            SELECT FICHENO as order_no,
                   DATE_ as order_date,
                   STATUS as status,
                   DOCODE as customer_code,
                   NETTOTAL as total_amount,
                   GENEXP1 as notes,
                   GENEXP2 as genexp2,
                   GENEXP3 as genexp3
            FROM {_t('ORFICHE')}
            WHERE FICHENO LIKE 'S%{LogoTables.ORDER_YEAR}%'
            ORDER BY STATUS, FICHENO
        """)
    
    if not today_orders:
        elements.append(Paragraph("Bugün için sipariş bulunmamaktadır.", HEADER_STYLE))
    else:
        # Group by status
        status_groups = defaultdict(list)
        for order in today_orders:
            status = order.get("status", 0)
            status_groups[status].append(order)
        
        # Status names
        status_names = {
            1: "📝 TASLAK SİPARİŞLER",
            2: "📦 TOPLANIYOR",
            3: "✅ HAZIRLANDI",
            4: "🚚 TAMAMLANDI",
        }
        
        for status_code, status_name in status_names.items():
            if status_code not in status_groups:
                continue
            
            elements.append(Paragraph(f"<b>{status_name}</b>", HEADER_STYLE))
            elements.append(Spacer(1, 5*mm))
            
            # Create table for this status
            data = [["Sipariş No", "Müşteri", "Tutar", "Not"]]
            
            for order in status_groups[status_code]:
                data.append([
                    order.get("order_no", ""),
                    order.get("customer_code", "")[:30] if order.get("customer_code") else "",
                    f"{order.get('total_amount', 0):,.2f} TL" if order.get('total_amount') else "0.00 TL",
                    order.get("notes", "")[:20] if order.get("notes") else "",
                ])
            
            tbl = Table(data, colWidths=[35*mm, 70*mm, 35*mm, 40*mm])
            tbl.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
            ]))
            
            elements.append(tbl)
            elements.append(Spacer(1, 10*mm))
    
    # Statistics
    stats = get_daily_statistics()
    stats_para = Paragraph(f"""
    <b>GÜNLÜK İSTATİSTİKLER</b><br/>
    Toplam Sipariş: {stats['total']}<br/>
    Taslak: {stats['draft']}<br/>
    Toplanıyor: {stats['picking']}<br/>
    Tamamlandı: {stats['completed']}<br/>
    <br/>
    <i>Rapor Hazırlayan: {get_current_user()}<br/>
    Tarih/Saat: {ts.strftime('%d.%m.%Y %H:%M')}</i>
    """, HEADER_STYLE)
    
    elements.append(PageBreak())
    elements.append(stats_para)
    
    # Build PDF
    doc.build(elements)
    
    return pdf_path


def process_order_enhanced(order: dict):
    """Process order with enhanced features."""
    lines = fetch_order_lines(order["order_id"])
    pdf_path = create_enhanced_picklist_pdf(order, lines)
    logger.info("Enhanced PDF oluşturuldu: %s", pdf_path.name)
    
    # Update status to picking
    update_order_status(order["order_id"], 2)
    logger.info("Sipariş %s STATUS=2 yapıldı", order["order_no"])
    
    # Add to queue if needed
    try:
        from app.dao.logo import queue_insert
        queue_insert(order["order_id"])
        logger.info("Sipariş kuyruğa eklendi: %s", order["order_no"])
    except:
        pass


def main():
    parser = argparse.ArgumentParser(description="Enhanced Picklist Service")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--daily", action="store_true", help="Create daily summary")
    parser.add_argument("--interval", type=int, default=30, help="Watcher interval (seconds)")
    args = parser.parse_args()
    
    if args.daily:
        # Create daily summary
        pdf_path = create_daily_summary_pdf()
        logger.info("Günlük özet oluşturuldu: %s", pdf_path.name)
        
    elif args.once:
        # Process pending orders once
        orders = fetch_draft_orders(limit=50)
        logger.info("%d taslak sipariş bulundu", len(orders))
        
        for order in orders:
            try:
                process_order_enhanced(order)
            except Exception as e:
                logger.error("Sipariş işlenemedi %s: %s", order.get("order_no"), e)
                
    else:
        # Watcher mode
        logger.info("Enhanced Picklist watcher başlatıldı (%d sn aralıkla)", args.interval)
        
        while True:
            try:
                orders = fetch_draft_orders(limit=50)
                
                if orders:
                    logger.info("%d yeni taslak sipariş bulundu", len(orders))
                    
                    for order in orders:
                        try:
                            process_order_enhanced(order)
                        except Exception as e:
                            logger.error("Sipariş işlenemedi %s: %s", order.get("order_no"), e)
                            
            except Exception as e:
                logger.error("Watcher hatası: %s", e)
                
            time.sleep(args.interval)


if __name__ == "__main__":
    main()