from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QLineEdit
from app.dao.logo import fetch_activities

class ActivityViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kullanıcı Aktiviteleri")
        self.resize(900, 450)
        lay = QVBoxLayout(self)

        # --- filtre satırı ---
        top = QHBoxLayout()
        self.txt_filter = QLineEdit(); self.txt_filter.setPlaceholderText("Ara...")
        self.txt_filter.textChanged.connect(self.apply_filter)
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Tümü", "OVER_SCAN", "INVALID_BARCODE"])
        self.cmb_type.currentIndexChanged.connect(self.apply_filter)
        top.addWidget(self.txt_filter); top.addWidget(self.cmb_type)
        lay.addLayout(top)

        # --- tablo ---
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels(
            ["Kullanıcı","Zaman","Aksiyon","Detay",
             "Sipariş","Stok","İst","Okut."]
        )
        self.tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl)

        self.logs = fetch_activities(limit=1000)   # önbellek
        self.load_rows(self.logs)
    def load_rows(self, rows):
        def _val(v):
            return "0" if v in (None, "") else str(v)

        # ► Aksiyon kodunu Türkçeye çevir
        TR = {"OVER_SCAN": "Fazla Okutma",
              "INVALID_SCAN": "Geçersiz Barkod"}

        self.tbl.setRowCount(0)
        keys = ["username","event_time","action","details",
                "order_no","item_code","qty_ordered","qty_scanned"]

        for log in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            for c, key in enumerate(keys):
                val = log.get(key, "")
                if key == "action":                 # ★ çeviri burada
                    val = TR.get(val, val)
                self.tbl.setItem(r, c, QTableWidgetItem(_val(val)))


    def apply_filter(self):
        text = self.txt_filter.text().lower()
        typ  = self.cmb_type.currentText()
        rows = [
            l for l in self.logs
            if (typ=="Tümü" or l["action"]==typ)
            and (text in (l["details"] or "").lower()
                 or text in (l["order_no"] or "").lower()
                 or text in (l["item_code"] or "").lower())
        ]
        self.load_rows(rows)
