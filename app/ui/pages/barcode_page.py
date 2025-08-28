from __future__ import annotations
"""
Barkod Yönetim Aracı – barcode_xref CRUD UI
================================================
• Depo-bazlı ek barkod eşlemelerini canlı okur / düzenler.
• Temel işlevler:
    – Listeleme  (depo + arama filtresi)
    – Satır ekle / sil / kaydet
    – CSV içe aktarma
"""
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QHeaderView, QFileDialog,
    QMessageBox, QTableView
)
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence

from app.ui.models.xref_model import XrefModel

# ───────────────────────────────────────────────────────────────────────────
# DAO bağlantıları  (yoksa UI yine açılır ama veri yazmaz)
# ───────────────────────────────────────────────────────────────────────────
try:
    from app.dao.logo import fetch_all as _dao_fetch_all, exec_sql as _dao_exec_sql
except ImportError:
    _dao_fetch_all = _dao_exec_sql = None


# ---------- DAO yardımcıları ------------------------------------------------
def fetch_barcodes(wh: str | None = None, text: str = "") -> List[Dict[str, Any]]:
    if _dao_fetch_all is None:
        return []

    sql     = "SELECT barcode, warehouse_id, item_code, multiplier, updated_at FROM dbo.barcode_xref"
    where   = []
    params: list[Any] = []

    if wh is not None:
        where.append("warehouse_id = ?")
        params.append(wh)
    if text:
        where.append("(barcode LIKE ? OR item_code LIKE ?)")
        params.extend([f"%{text}%", f"%{text}%"])

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY updated_at DESC, barcode"
    return _dao_fetch_all(sql, *params)


def upsert_barcode(barcode: str, wh: str, item_code: str, mul: float | Decimal = 1.0):
    if _dao_exec_sql is None:
        return
    _dao_exec_sql(
        """
        MERGE dbo.barcode_xref AS tgt
        USING (SELECT ? AS bc, ? AS wh) src
              ON (tgt.barcode = src.bc AND tgt.warehouse_id = src.wh)
        WHEN MATCHED THEN
            UPDATE SET item_code = ?, multiplier = ?, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (barcode, warehouse_id, item_code, multiplier, updated_at)
            VALUES (src.bc, src.wh, ?, ?, GETDATE());
        """,
        barcode, wh, item_code, mul, item_code, mul
    )


def delete_barcodes(keys: list[tuple[str, str]]):
    if _dao_exec_sql is None or not keys:
        return
    for bc, wh in keys:
        _dao_exec_sql("DELETE FROM dbo.barcode_xref WHERE barcode=? AND warehouse_id=?", bc, wh)


# ───────────────────────────────────────────────────────────────────────────
# UI bileşeni
# ───────────────────────────────────────────────────────────────────────────
class BarcodePage(QWidget):
    """Sol menüde yer alan canlı barkod yönetim sayfası."""
    data_changed = pyqtSignal()

    COLS = [
        ("barcode",      "Barkod"),
        ("warehouse_id", "Depo"),
        ("item_code",    "Stok Kodu"),
        ("multiplier",   "Çarpan"),
        ("updated_at",   "Güncelleme"),
    ]

    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        lay = QVBoxLayout(self)

        # Üst filtre satırı ---------------------------------------------------
        flt = QHBoxLayout()
        self.cmb_wh = QComboBox(); self.cmb_wh.addItems(["Tümü", "0", "1", "2", "3"])
        self.search = QLineEdit();  self.search.setPlaceholderText("Barkod / Stok ara…")

        self.btn_import = QPushButton("İçe Aktar…")
        self.btn_add    = QPushButton("Ekle")
        self.btn_del    = QPushButton("Sil")
        self.btn_save   = QPushButton("Kaydet")    # ← yeni

        flt.addWidget(QLabel("Depo:")); flt.addWidget(self.cmb_wh)
        flt.addWidget(self.search, 1);  flt.addStretch()
        flt.addWidget(self.btn_import); flt.addWidget(self.btn_add)
        flt.addWidget(self.btn_del);    flt.addWidget(self.btn_save)
        lay.addLayout(flt)


        # Tablo  --------------------------------------------------------------
        from app.ui.models.xref_model import XrefModel
        self.tbl = QTableView()
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tbl)
        QShortcut(QKeySequence("Delete"), self.tbl, activated=self._delete_selected)

        # ► sinyaller
        self.cmb_wh.currentIndexChanged.connect(self.refresh)
        self._deb = QTimer(self, singleShot=True, interval=300)   # 0.3 sn
        self.search.textChanged.connect(self._deb.start)
        self._deb.timeout.connect(self.refresh)
        self.btn_add.clicked.connect(self._add_row)
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_import.clicked.connect(self._import_csv)
        self.btn_save.clicked.connect(self._save_changes)         # ← yeni

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self._delete_selected()
        else:
            super().keyPressEvent(e)
    # ------------------------------------------------------------- Data ---
    def refresh(self):
        wh = None if self.cmb_wh.currentIndex() == 0 else self.cmb_wh.currentText()
        text = self.search.text().strip()
        self.tbl.setModel(XrefModel(wh_filter=wh, text=text))

    # -------------------------------------------------------- Row ops -----
    def _add_row(self):
        """QTableView + model kullanırken yeni satır eklemek için model üzerinden işlem yapar."""
        # Basit çözüm: Yeni barkod ekleme dialog'u açalım
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QLabel, QPushButton, QComboBox
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Barkod Ekle")
        dlg.resize(300, 200)
        lay = QVBoxLayout(dlg)
        
        lay.addWidget(QLabel("Barkod:"))
        edt_barcode = QLineEdit()
        lay.addWidget(edt_barcode)
        
        lay.addWidget(QLabel("Depo:"))
        cmb_wh = QComboBox()
        cmb_wh.addItems(["0", "1", "2", "3", "4"])  # veya mevcut depo listesi
        lay.addWidget(cmb_wh)
        
        lay.addWidget(QLabel("Stok Kodu:"))
        edt_item = QLineEdit()
        lay.addWidget(edt_item)
        
        lay.addWidget(QLabel("Çarpan:"))
        edt_mul = QLineEdit("1.0")
        lay.addWidget(edt_mul)
        
        btn_ok = QPushButton("Ekle")
        btn_ok.clicked.connect(dlg.accept)
        lay.addWidget(btn_ok)
        
        if dlg.exec_() == QDialog.Accepted:
            try:
                barcode = edt_barcode.text().strip()
                warehouse = cmb_wh.currentText()
                item_code = edt_item.text().strip()
                multiplier = float(edt_mul.text() or "1.0")
                
                if barcode and warehouse and item_code:
                    upsert_barcode(barcode, warehouse, item_code, multiplier)
                    self.refresh()  # Modeli yenile
                else:
                    QMessageBox.warning(self, "Hata", "Tüm alanları doldurun!")
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    # barcode_page.py  –  sınıf içindeki _delete_selected'i TAMAMIYLA değiştirin
    # -------------------------------------------------------- Row delete -----
    def _delete_selected(self):
        """Seçili satır(lar)ı hem UI’den hem veritabanından sil."""
        sel_rows = sorted(
            {ix.row() for ix in self.tbl.selectionModel().selectedRows()},
            reverse=True
        )
        if not sel_rows:
            return

        if QMessageBox.question(
            self, "Sil",
            f"{len(sel_rows)} satır silinsin mi?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.No:
            return

        model = self.tbl.model()          # QAbstractTableModel
        keys: list[tuple[str, str]] = []  # (barcode, warehouse_id)

        for r in sel_rows:
            bc = model.index(r, 0).data() or ""
            wh = model.index(r, 1).data() or ""
            if bc and wh:
                keys.append((bc, wh))

        # Veritabanından sil
        delete_barcodes(keys)

        # Modele yeniden bağlanarak UI’yi tazele
        self.refresh()
        self.data_changed.emit()



    # ---------------------------------------------------- CSV / Excel import ------
    def _import_csv(self):                         
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Dosya Seç…",
            str(Path.home()),
            "Veri Dosyaları (*.csv *.xlsx *.xls)"
        )
        if not path:
            return

        # ► Ayrı servis → temiz kod
        from app.services.import_barcodes import load_file
        ok, sec, err = load_file(path)

        QMessageBox.information(
            self, "İçe Aktar",
            f"✔ {ok:,} satır ({sec:0.1f} sn)\n❌ Hata: {err}"
        )
        self.refresh()
        self.data_changed.emit()

# barcode_page.py  – _save_changes()
    def _save_changes(self):
        ok_cnt = err_cnt = 0

        for r in range(self.tbl.rowCount()):
            # güvenli okuma -----------------------------------------------------
            def cell(row: int, col: int) -> str:
                itm = self.tbl.item(row, col)
                return itm.text().strip() if itm else ""

            bc  = cell(r, 0)
            wh  = cell(r, 1)
            itm = cell(r, 2)
            mul = cell(r, 3) or "1"

            # zorunlu alanlar dolu değilse es geç
            if not (bc and wh and itm):
                err_cnt += 1
                continue

            try:
                upsert_barcode(bc, wh, itm, float(mul))
                ok_cnt += 1
            except Exception as exc:
                err_cnt += 1
                print(f"[barcode-save] {bc}/{wh}: {exc}")

        QMessageBox.information(
            self, "Barkodlar",
            f"✔ {ok_cnt} satır kaydedildi\n❌ {err_cnt} satır atlandı."
        )
        self.refresh()
        self.data_changed.emit()
