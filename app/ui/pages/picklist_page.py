"""PickList Page – Otomatik taslak sipariş takibi
================================================
• STATUS 1 (taslak)         # PDF + STATUS 2 işlemleri
        processed_orders = []
        for r in sorted(rows, reverse=True):          # büyükten küçüğe → sıra bozulmaz
            # 🔸 Tablodaki satırdan sipariş no'yu al
            if r < self.tbl.rowCount():
                order_no_from_table = self.tbl.item(r, 0).text()
                
                # self.orders listesinde bu sipariş no'yu bul
                order_obj = None
                order_index = None
                for i, o in enumerate(self.orders):
                    if o["order_no"] == order_no_from_table:
                        order_obj = o
                        order_index = i
                        break
                
                if not order_obj:
                    continue
            else:
                # Fallback: eski yöntem
                order_obj = self.orders[r]
                order_index = r
                
            try:
                lines = fetch_order_lines(order_obj["order_id"])
                create_picklist_pdf(order_obj, lines)
                update_order_status(order_obj["order_id"], 2)
                queue_insert(order_obj["order_id"])
                processed_orders.append((r, order_index, order_obj))
            except Exception as exc:
                QMessageBox.critical(self, "Hata", str(exc))
                continue

        # Temizleme işlemleri (büyük index'ten küçüğe)
        for table_row, list_index, order_obj in sorted(processed_orders, reverse=True):
            self.tbl.removeRow(table_row)
            if list_index < len(self.orders):
                self._order_ids.discard(self.orders[list_index]["order_id"])
                self.orders.pop(list_index)n’de bir yeniler
• Başlangıç / Bitiş tarih filtresi
• Yeni gelen sipariş tabloya eklenir ➜ Scanner kuyruğuna iletilir
• Seçili satır(lar)dan PDF pick‑list üret + sipariş STATUS 2’ye çek
• CSV raporu (tüm tablo) tek tıkla dışa aktar
"""
from __future__ import annotations

import csv, sys
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Set

from PyQt5.QtCore    import Qt, QTimer, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox,
    QSpinBox, QFileDialog, QDateEdit
)

from app.dao.logo  import (
    fetch_draft_orders,            # STATUS 1 – taslak
    update_order_status,
    fetch_order_lines,
    queue_insert,
)
from app.services.picklist import create_picklist_pdf

# ---------------------------------------------------------------------------
class PicklistPage(QWidget):
    """Depo taslak siparişlerini otomatik izler ve pick‑list üretir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._order_ids: Set[int] = set()   # tabloya eklenenler
        self.orders: List[Dict] = []        # satır dizisi
        self._build_ui()
        self._start_timer()

    # ---------------- UI ----------------
    def _build_ui(self):
        lay = QVBoxLayout(self)

        title = QLabel("<b>Pick‑List Oluştur</b>"); title.setStyleSheet("font-size:16px")
        lay.addWidget(title)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Başlangıç:"))
        self.dt_from = QDateEdit(QDate.currentDate()); self.dt_from.setCalendarPopup(True)
        ctrl.addWidget(self.dt_from)
        ctrl.addWidget(QLabel("Bitiş:"))
        self.dt_to   = QDateEdit(QDate.currentDate()); self.dt_to.setCalendarPopup(True)
        ctrl.addWidget(self.dt_to)

        ctrl.addStretch()
        btn_csv  = QPushButton("CSV");  btn_csv.clicked.connect(self.export_csv)
        btn_pdf  = QPushButton("PDF");  btn_pdf.clicked.connect(self.make_pdf)
        ctrl.addWidget(btn_csv); ctrl.addWidget(btn_pdf)
        lay.addLayout(ctrl)

        self.tbl = QTableWidget(0,3)
        self.tbl.setHorizontalHeaderLabels(["Sipariş","Müşteri","Tarih"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.tbl)

    # ---------------- Timer ----------------
    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(15_000)   # 15 saniye
        self.refresh()             # ilk çağrı hemen

    # ---------------- Data ----------------
    def refresh(self):
        d1 = self.dt_from.date().toPyDate()
        d2 = self.dt_to.date().toPyDate() + timedelta(days=1)   # gün sonu
        try:
            rows = fetch_draft_orders(limit=500)   # Logo’da DATE_ filtresi yoksa getir, sonra filtrele
        except Exception as e:
            QMessageBox.critical(self,"DB Hatası", str(e)); return

        # Tarih filtresi
        rows = [r for r in rows if d1 <= r["order_date"].date() < d2]

        new_rows = [r for r in rows if r["order_id"] not in self._order_ids]
        if not new_rows:
            return

        self.tbl.setSortingEnabled(False)
        for o in new_rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r,0,QTableWidgetItem(o["order_no"]))
            self.tbl.setItem(r,1,QTableWidgetItem(o["customer_code"]))
            self.tbl.setItem(r,2,QTableWidgetItem(o["order_date"].strftime("%d.%m.%Y")))
            self.orders.append(o)
            self._order_ids.add(o["order_id"])

            # Scanner kuyruğuna ilet
            if parent := self.parent():
                if hasattr(parent, "scanner_page") and hasattr(parent.scanner_page, "enqueue"):
                    parent.scanner_page.enqueue(o)
        self.tbl.setSortingEnabled(True)

    # ---------------- PDF ----------------
    def make_pdf(self):
        """Seçili satırlar (ya da seçim yoksa tümü) için pick‑list PDF üretir
        • Logo STATUS 2′ye çeker
        • Tablo ve dahili listelerden işlenen siparişleri siler → tekrar basılmaz
        """
        if not self.orders:
            return

        sel_rows = {i.row() for i in self.tbl.selectedIndexes()}
        rows = sel_rows or set(range(len(self.orders)))

        if not rows:
            return

        # PDF + STATUS 2 işlemleri
        for r in sorted(rows, reverse=True):          # büyükten küçüğe → sıra bozulmaz
            o = self.orders[r]
            try:
                lines = fetch_order_lines(o["order_id"])
                create_picklist_pdf(o, lines)
                update_order_status(o["order_id"], 2)
                queue_insert(o["order_id"])  
            except Exception as exc:
                QMessageBox.critical(self, "Hata", str(exc))
                continue

            # ✅ tabloda ve listelerde temizle – böylece tekrar status 2 yapılmaz
            self.tbl.removeRow(r)
            self._order_ids.discard(o["order_id"])
            self.orders.pop(r)

        QMessageBox.information(self, "Pick‑List", "PDF oluşturuldu, STATUS 2 yapıldı.")

    # ---------------- CSV ----------------
    def export_csv(self):
        """Görünen tarih aralığındaki TASLAK siparişleri CSV’e döker.
        Bellekte sipariş olmasa bile veritabanından taze çeker –
        program yeniden başlatılsa dahi ‘bugün gelenler’ indirilebilir."""
        d1 = self.dt_from.date().toPyDate()
        d2 = self.dt_to.date().toPyDate() + timedelta(days=1)
        try:
            rows = fetch_draft_orders(limit=1000)   # geniş limit, sonra filtrele
        except Exception as exc:
            QMessageBox.critical(self, "DB Hatası", str(exc)); return

        rows = [r for r in rows if d1 <= r["order_date"].date() < d2]
        if not rows:
            QMessageBox.information(self, "CSV", "Seçili aralıkta sipariş yok.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "CSV Kaydet",
            f"picklist_{d1:%Y%m%d}_{d2:%Y%m%d}.csv",
            "CSV Files (*.csv)")
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["order_no", "customer_code", "order_date"])
            for o in rows:
                w.writerow([o["order_no"], o["customer_code"], o["order_date"].strftime("%Y-%m-%d")])

        QMessageBox.information(self, "CSV", "Dosya kaydedildi.")
