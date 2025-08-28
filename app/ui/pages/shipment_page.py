"""Shipment Page – Sevkiyat Listesi
------------------------------------------------
Sipariş başlıkları, sağ‑tıkla detay ve **önceden oluşturulmuş etiket PDF’ini açma**

"""
from __future__ import annotations
import app.settings as st
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from app.dao.logo import ensure_qr_token     
import os
import sys
from pathlib import Path
from datetime import date
from typing import Dict, List 
from app.utils.fonts import register_pdf_font   
from PyQt5.QtCore    import Qt, QDate, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QMenu
)

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# DAO & helpers --------------------------------------------------------------
from app.shipment import list_headers_range  # noqa: E402
from app.dao.logo           import fetch_order_lines_by_no, fetch_invoice_no  # noqa: E402
try:
    from app.services.label_service import make_labels as print_labels  # PDF oluşturucu
except (ImportError, AttributeError):
    print_labels = None  # opsiyonel – yoksa sadece uyarı verir

# Settings'ten label directory al - label_service ile aynı yolu kullan
LABEL_DIR = Path(st.get("paths.label_dir", "labels"))

# ────────────────────────────────────────────────────────────────
COLS = [
    ("id",            "id"),           # gizli – dahili
    ("order_no",      "Sipariş"),
    ("customer_code", "Cari Kod"),
    ("customer_name", "Cari Adı"),
    ("region",        "Bölge"),
    ("address1",      "Adres"),
    ("pkgs_total",    "Koli"),
    ("pkgs_loaded",   "Yüklendi"),
    ("status_txt",    "Durum"),
    ("created_at",    "Oluşturma"),
]

class ShipmentPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(15_000)  
    # ---------------- UI ----------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>Sevkiyat Listesi</b>"))

        top = QHBoxLayout()
        self.dt_from = QDateEdit(QDate.currentDate());  top.addWidget(QLabel("Başlangıç:")); top.addWidget(self.dt_from)
        self.dt_to   = QDateEdit(QDate.currentDate());  top.addWidget(QLabel("Bitiş:"));    top.addWidget(self.dt_to)
        self.search  = QLineEdit(); self.search.setPlaceholderText("Sipariş / Cari ara…"); top.addWidget(self.search,1)
        btn_list = QPushButton("Listele"); btn_list.clicked.connect(self.refresh)
        btn_pdf = QPushButton("PDF (Ctrl+P)")
        btn_pdf.clicked.connect(self.export_pdf)
        btn_pdf.setShortcut("Ctrl+P")
        top.addWidget(btn_pdf)

        top.addStretch(); top.addWidget(btn_list)
        lay.addLayout(top)

        self.tbl = QTableWidget(0, len(COLS))
        self.tbl.setHorizontalHeaderLabels([c[1] for c in COLS])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSortingEnabled(True)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.tbl)

        # id sütununu gizle
        self.tbl.setColumnHidden(0, True)


    def _visible_rows(self) -> List[Dict]:
        """Tabloda sırayla görünen tüm satır kayıtlarını döndürür."""
        return [
            self._rows[self.tbl.item(r, 0).row()]   # id sütunu gizli ama index aynı
            for r in range(self.tbl.rowCount())
    ]


    # ---------------- Liste ----------------
    def refresh(self):
        d1 = self.dt_from.date().toPyDate().isoformat()
        d2 = self.dt_to.date().toPyDate().isoformat()
        rows = list_headers_range(d1, d2)

        q = self.search.text().strip().upper()
        if q:
            rows = [r for r in rows
                    if q in r["order_no"].upper()
                    or q in (r["customer_code"] or "").upper()]

        for r in rows:
            r["status_txt"] = "✔" if r["closed"] else "⏳"
        self._rows = rows

        # ——— YENİ KOD ———
        self.tbl.setSortingEnabled(False)   # sıralamayı geçici kapat
        self.tbl.setRowCount(0)             # önceki satırları sil
        for rec in rows:
            self._add_row(rec)              # tüm yeni satırları ekle
        self.tbl.setSortingEnabled(True)    # sıralamayı geri aç

    def _add_row(self, rec: Dict):
        row = self.tbl.rowCount(); self.tbl.insertRow(row)
        for col,(key,_) in enumerate(COLS):
            itm = QTableWidgetItem(str(rec.get(key,""))); itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl.setItem(row,col,itm)

    # ---------------- Sağ‑tık Menü ----------------
    def _ctx_menu(self, pos):
        idx = self.tbl.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        trip_id  = int(self.tbl.item(row,0).text())   # gizli id
        order_no = self.tbl.item(row,1).text()

        menu = QMenu(self)
        act_detail = menu.addAction("Detay…")
        act_print  = menu.addAction("Etiket Yazdır…")
        act_detail.triggered.connect(lambda _=False, tid=trip_id, ono=order_no: self._show_detail(tid, ono))
        act_print.triggered.connect(lambda _=False, ono=order_no: self._open_or_create_label(ono))
        menu.exec_(self.tbl.viewport().mapToGlobal(pos))

    # ---------------- Detay ----------------
    def _show_detail(self, trip_id:int, order_no:str):
        rec = next((r for r in self._rows if r["id"]==trip_id), None)
        if not rec:
            return
        try:
            lines = fetch_order_lines_by_no(order_no)
            lines_html = [f"{ln['item_code']} – {ln['qty_ordered']}" for ln in lines]
        except Exception as exc:
            lines_html = [f"<i>Satırlar okunamadı: {exc}</i>"]

        html = [
            f"<b>Sipariş</b>: {order_no}",
            f"Cari: {rec.get('customer_code')} – {rec.get('customer_name')}",
            f"Bölge: {rec.get('region','')}",
            f"Adres: {rec.get('address1','')}",
            f"Koli: {rec.get('pkgs_loaded')}/{rec.get('pkgs_total')}",
            f"Durum: {'Tamam' if rec.get('closed') else 'Bekliyor'}",
            "<hr><b>Ürünler</b>:",
            *lines_html,
        ]
        QMessageBox.information(self, f"Sipariş Detay – {order_no}", "<br>".join(html))

  # ------------------------------------------------------------------
    #   Etiket PDF aç / oluştur  +  invoice_root yaz
    # ------------------------------------------------------------------
    def _open_or_create_label(self, order_no: str):
        """
        • Siparişe ait fatura varsa etiket PDF’ini bulur ya da oluşturur
        • Başlık tablosuna invoice_root yazar (boşsa)
        • Ayarlar->Yazdırma’da seçilen “Etiket yazıcısı” varsa doğrudan o yazıcıya gönderir,
        yoksa eski davranış: dosyayı aç.
        """
        # 1) Fatura kontrolü ------------------------------------------------------
        invoice_no = fetch_invoice_no(order_no)
        if not invoice_no:
            QMessageBox.warning(self, "Fatura Yok",
                                "Siparişe ait fatura kesilmedi; etiket basılamaz.")
            return

        inv_root = invoice_no.split("-K")[0]        # ➜ CAN2025…, ARV2025…

        # 2) PDF’i bul veya oluştur ----------------------------------------------
        pattern  = f"LABEL_*_{order_no}.pdf"
        pdf_path = next(iter(sorted(LABEL_DIR.glob(pattern),
                                    key=lambda p: p.stat().st_mtime,
                                    reverse=True)), None)

        if pdf_path is None:                        # yoksa üret
            if print_labels is None:
                QMessageBox.warning(self, "Servis Yok",
                                    "label_service.make_labels bulunamadı; PDF üretilemedi.")
                return
            try:
                print_labels(order_no, force=False)
                pdf_path = next(iter(sorted(LABEL_DIR.glob(pattern),
                                            key=lambda p: p.stat().st_mtime,
                                            reverse=True)), None)
            except Exception as exc:
                QMessageBox.critical(self, "Baskı Hatası", str(exc))
                return

        # 3) invoice_root güncelle (NULL ise) -------------------------------------
        try:
            # Sadece invoice_root'u güncelle, diğer bilgileri koru
            from app.dao.logo import get_conn
            with get_conn(autocommit=True) as cn:
                cn.execute(
                    "UPDATE shipment_header SET invoice_root = ? WHERE order_no = ? AND invoice_root IS NULL",
                    inv_root, order_no
                )
        except Exception as exc:
            print(f"[shipment_page] invoice_root yazılamadı: {exc}")

        # 4) Yazdır / Aç ----------------------------------------------------------
        if pdf_path and pdf_path.exists():
            try:
                os.startfile(pdf_path)                 # PDF'i ekranda aç
            except Exception as exc:
                QMessageBox.warning(self, "Dosya Hatası",
                                   f"PDF dosyası açılamadı: {pdf_path}\n\nHata: {exc}")
        else:
            QMessageBox.warning(self, "Dosya Yok",
                                "Etiket PDF bulunamadı veya oluşturulamadı.")

    def export_pdf(self):
        """Seçili ya da görünür tüm satırları Masaüstü’ne PDF yazar."""
        if not getattr(self, "_rows", None):
            QMessageBox.warning(self, "PDF", "Önce listeyi getir!")
            return

        vis = self._visible_rows()
        sel = {ix.row() for ix in self.tbl.selectionModel().selectedRows()}
        rows = [vis[r] for r in sel] if sel else vis
        if not rows:
            QMessageBox.information(self, "PDF", "Basılacak satır yok.")
            return

        # ------ Masaüstü + dosya adı  ---------------------------------
        desktop = Path.home() / "Desktop"
        fname   = f"SevkListesi_{date.today():%Y%m%d_%H%M%S}.pdf"
        out_pdf = desktop / fname

        # ------ Font ---------------------------------------------------
        FONT = register_pdf_font()


        # ------ PDF kurulum -------------------------------------------
        W, H = landscape(A4)
        pdf  = canvas.Canvas(str(out_pdf), pagesize=(W, H))
        pdf.setFont(FONT, 8)

        cols = [
            ("QR",22*mm),("Sipariş",28*mm),("Cari Kod",24*mm),("Müşteri",38*mm),
            ("Bölge",28*mm),("Adres",50*mm),("Paket",12*mm),
            ("Yüklendi",28*mm),("Kaşe",36*mm)
        ]
        margin, header_h, row_h = 15*mm, 12*mm, 24*mm
        y_top = H - margin

        # -------- yardımcılar -----------------------------------------
        def split(txt, maxw):
            out, cur = [], ""
            for w in str(txt).split():
                t = (cur+" "+w).strip()
                if stringWidth(t, FONT, 7) <= maxw:
                    cur = t
                else:
                    if cur: out.append(cur)  # noqa: E701
                    cur = w
            out.append(cur); return out

        def hdr(y):
            x = margin
            for t,w in cols:
                pdf.rect(x, y-header_h, w, header_h)
                pdf.drawCentredString(x+w/2, y-header_h+3, t)
                x += w

        # -------- çizim döngüsü ---------------------------------------
        hdr(y_top); y = y_top-header_h
        for rec in rows:
            buf = io.BytesIO()
            qrcode.make(ensure_qr_token(rec["order_no"])).save(buf, "PNG"); buf.seek(0)
            qr_img = ImageReader(buf)

            data = [
                rec["order_no"], rec["customer_code"], rec["customer_name"],
                rec["region"], rec["address1"],
                f"{rec['pkgs_loaded']}/{rec['pkgs_total']}",
                rec["created_at"][11:16] if rec.get("created_at") else "", ""
            ]

            dyn = row_h
            lines = []
            for (_h,w),txt in zip(cols[1:], data):
                ls = split(txt, w-4*mm); lines.append(ls)
                dyn = max(dyn, 6+9*len(ls))

            if y - dyn < margin:
                pdf.showPage(); pdf.setFont(FONT, 8)
                hdr(H-margin); y = H-margin-header_h

            x = margin
            for _h,w in cols:
                pdf.rect(x, y-dyn, w, dyn); x += w

            qr_sz = 18*mm
            pdf.drawImage(
                qr_img,
                margin + (cols[0][1]-qr_sz)/2,
                y-dyn + (dyn-qr_sz)/2,
                qr_sz, qr_sz, preserveAspectRatio=True
            )

            x = margin + cols[0][1]; pdf.setFont(FONT,7)
            for (_h,w),ls in zip(cols[1:], lines):
                for i,l in enumerate(ls):  # noqa: E741
                    pdf.drawString(x+2, y-9-i*9, l)
                x += w

            y -= dyn

        pdf.save()
        # --- PDF’i aç / yazdır -------------------------------------------------


        prn_name = st.get("print.list_printer", "")
        try:
            if prn_name:
                os.startfile(out_pdf, "print")
            else:
                os.startfile(out_pdf)
        except Exception as exc:
            QMessageBox.information(self, "PDF",
                f"Yükleme listesi PDF hazırlandı: {out_pdf}\n{exc}")

