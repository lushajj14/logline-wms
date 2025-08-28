from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app import settings
from pathlib import Path

def register_pdf_font(name: str = "DejaVuSans", filename: str = "DejaVuSans.ttf") -> str:
    """TTF fontu ReportLab'a kaydeder ve adını döner"""
    font_path = Path(settings.get("paths.font_dir", "fonts")) / filename
    try:
        if not pdfmetrics.getFont(name):
            pdfmetrics.registerFont(TTFont(name, str(font_path)))
    except Exception:
        return "Helvetica"
    return name
