from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel,              \
                            QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtGui     import QColor
from datetime import datetime
from app.dao.logo    import fetch_all

_SQL = """
SELECT order_no,
       pkgs_total - pkgs_loaded AS kalan,
       pkgs_total, pkgs_loaded,
       loaded_at_expected
FROM   shipment_header
WHERE  closed = 0
ORDER  BY loaded_at_expected, order_no
"""

# ════════════════════════════════════════════════════════════════
class TaskBoardPage(QWidget):
    def __init__(self):
        super().__init__()

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>Görev / İş Listesi</b>"))

        self.tbl = QTableWidget(0, 5); lay.addWidget(self.tbl)
        self.tbl.setHorizontalHeaderLabels(
            ["Sipariş", "Kalan", "Toplam", "Yüklendi", "Hedef Çıkış"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 30 sn’de bir otomatik yenile
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

        self.refresh()

    # ────────────────────────────────────────────────────────────
    def refresh(self):
        rows = fetch_all(_SQL)
        self.tbl.setRowCount(0)

        for r in rows:
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)

            # Hücre değerleri
            cells = [
                r["order_no"],
                r["kalan"],
                r["pkgs_total"],
                r["pkgs_loaded"],
                (r["loaded_at_expected"].strftime("%H:%M")
                 if r["loaded_at_expected"] else "-")
            ]
            for c, v in enumerate(cells):
                itm = QTableWidgetItem(str(v))
                itm.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(row, c, itm)

            # Satır renklendirme
            if r["kalan"] == 0:                         # tamamlandı
                base = QColor("#27ae60")                # yeşil
            elif (r["loaded_at_expected"]
                  and r["loaded_at_expected"] < datetime.now()):
                base = QColor("#e74c3c")                # gecikti - kırmızı
            else:
                base = QColor("#f1c40f")                # devam ediyor - sarı
            base.setAlpha(40)                           # hafif saydam

            for c in range(5):
                self.tbl.item(row, c).setBackground(base)
