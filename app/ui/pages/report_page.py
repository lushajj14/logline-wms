from __future__ import annotations
from pathlib import Path
from datetime import date
import sys, pandas as pd

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView
)

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.backorder import list_fulfilled   # DAO

class ReportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    # --------------------------- UI ----------------------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>Günlük Back-Order Raporu</b>"))

        top = QHBoxLayout()
        self.dt = QDateEdit(QDate.currentDate()); top.addWidget(QLabel("Tarih:")); top.addWidget(self.dt)
        btn_view = QPushButton("Görüntüle"); btn_view.clicked.connect(self.refresh)
        btn_xls  = QPushButton("Excel İndir"); btn_xls.clicked.connect(self.export_excel)
        top.addStretch(); top.addWidget(btn_view); top.addWidget(btn_xls)
        lay.addLayout(top)

        self.tbl = QTableWidget(0,6)
        self.tbl.setHorizontalHeaderLabels(["Sipariş","Ürün","Eksik","Ambar","Tamamlandı","Fulfilled_at"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tbl)

    # --------------------------- Veri --------------------------
    def refresh(self):
        sel_date = self.dt.date().toPyDate()
        recs = list_fulfilled(sel_date.isoformat())
        self._df = pd.DataFrame(recs)
        self.tbl.setRowCount(0)
        for r in recs:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            for col, key in enumerate(["order_no","item_code","qty_missing","warehouse_id","fulfilled","fulfilled_at"]):
                it = QTableWidgetItem(str(r[key]))
                it.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(row, col, it)

    def export_excel(self):
        if not hasattr(self, "_df") or self._df.empty:
            QMessageBox.information(self,"Rapor","Önce raporu görüntüleyin")
            return
        path, _ = QFileDialog.getSaveFileName(self,"Excel Kaydet","","Excel Files (*.xlsx)")
        if path:
            self._df.to_excel(path, index=False)
            QMessageBox.information(self,"Rapor",f"Excel kaydedildi ➜ {path}")
