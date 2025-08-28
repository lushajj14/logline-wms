"""
SettingsPage – Uygulama ayarları paneli
---------------------------------------
• app.settings üzerinden JSON okur / yazar.
• Kaydet → settings.save() + settings_saved sinyali.
• Vazgeç → JSON’daki son duruma geri döner.
"""
from __future__ import annotations
from pathlib import Path
# ruff: noqa: E702
from PyQt5.QtCore    import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QGridLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QFileDialog, QMessageBox, QHBoxLayout,
    QTableWidget, QHeaderView, QTableWidgetItem, QLineEdit
)

import app.settings as st

BASE_DIR = Path(__file__).resolve().parents[3]

# ===================================================================
class SettingsPage(QWidget):
    """Üç sekmeli ayar sayfası – görünüm / veritabanı / dosya yolları."""
    settings_saved = pyqtSignal()          # ⇢ MainWindow’a tetik gönderir

    # ----------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.load()                        # JSON → widget’lar

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------
    def _build_ui(self) -> None:
        main  = QVBoxLayout(self)
        self.tabs = QTabWidget();  main.addWidget(self.tabs)

        # ─── SEKME: Görünüm ───────────────────────────────────────
        tab_ui = QWidget(); self.tabs.addTab(tab_ui, "Görünüm")
        g = QGridLayout(tab_ui); r = 0

        self.cmb_theme  = QComboBox(); self.cmb_theme.addItems(["light","dark","system"])
        g.addWidget(QLabel("Tema"), r,0); g.addWidget(self.cmb_theme, r,1); r+=1

        self.spin_font  = QSpinBox();  self.spin_font.setRange(7,24)
        g.addWidget(QLabel("Yazı boyutu (pt)"), r,0); g.addWidget(self.spin_font, r,1); r+=1

        self.chk_sound  = QCheckBox("Sesli uyarılar")
        g.addWidget(self.chk_sound, r,0, 1,2); r+=1  # noqa: E702

        self.spin_volume = QSpinBox(); self.spin_volume.setRange(0,100)
        g.addWidget(QLabel("Ses seviyesi %"), r,0); g.addWidget(self.spin_volume, r,1); r+=1

        self.spin_toast = QSpinBox(); self.spin_toast.setRange(1,10)
        g.addWidget(QLabel("Toast süresi (sn)"), r,0); g.addWidget(self.spin_toast, r,1); r+=1

        self.chk_focus  = QCheckBox("Barkod alanına otomatik odak")
        g.addWidget(self.chk_focus, r,0, 1,2); r+=1
        g.setColumnStretch(2,1)

        # ─── SEKME: Veritabanı ────────────────────────────────────
        tab_db = QWidget(); self.tabs.addTab(tab_db, "Veritabanı")
        g2 = QGridLayout(tab_db); r = 0  # noqa: E702

        self.lin_db_server = QLineEdit();  g2.addWidget(QLabel("Sunucu"),  r,0); g2.addWidget(self.lin_db_server, r,1); r+=1
        self.lin_db_name   = QLineEdit();  g2.addWidget(QLabel("DB adı"),  r,0); g2.addWidget(self.lin_db_name,   r,1); r+=1
        self.lin_db_user   = QLineEdit();  g2.addWidget(QLabel("Kullanıcı"), r,0); g2.addWidget(self.lin_db_user,   r,1); r+=1

        self.spin_retry = QSpinBox(); self.spin_retry.setRange(0,10)
        g2.addWidget(QLabel("Yeniden bağlanma denemesi"), r,0); g2.addWidget(self.spin_retry, r,1); r+=1

        self.spin_hb   = QSpinBox(); self.spin_hb.setRange(1,120)
        g2.addWidget(QLabel("Heartbeat (sn)"), r,0); g2.addWidget(self.spin_hb, r,1); r+=1

        # ─── SEKME: Loader ────────────────────────────────────────
        tab_loader = QWidget(); self.tabs.addTab(tab_loader, "Loader")
        gL = QGridLayout(tab_loader); r = 0

        self.spin_loader_refresh = QSpinBox(); self.spin_loader_refresh.setRange(5,300)
        gL.addWidget(QLabel("Oto-yenile (sn)"), r,0); gL.addWidget(self.spin_loader_refresh, r,1); r+=1

        self.chk_loader_block = QCheckBox("Eksik koli kapatmayı engelle")
        gL.addWidget(self.chk_loader_block, r,0, 1,2); r+=1

        # ─── SEKME: Barkod ────────────────────────────────────────
        tab_bc = QWidget(); self.tabs.addTab(tab_bc, "Barkod")
        g3 = QGridLayout(tab_bc); r = 0

        self.tbl_pref = QTableWidget(0,2)
        self.tbl_pref.setHorizontalHeaderLabels(["Ön-ek","Depo"])
        self.tbl_pref.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        g3.addWidget(self.tbl_pref, r,0,1,3); r+=1

        btn_add = QPushButton("Ekle"); btn_add.clicked.connect(self._add_prefix_row)
        btn_del = QPushButton("Sil");  btn_del.clicked.connect(self._del_prefix_row)
        g3.addWidget(btn_add, r,1); g3.addWidget(btn_del, r,2); r+=1

        self.spin_tol = QSpinBox(); self.spin_tol.setRange(0,10)
        g3.addWidget(QLabel("Fazla okutma toleransı"), r,0); g3.addWidget(self.spin_tol, r,1); r+=1

        # --- SEKME: Yazdırma ------------------------------------------------
        tab_prn = QWidget(); self.tabs.addTab(tab_prn, "Yazdırma")
        gP = QGridLayout(tab_prn); r = 0

        from PyQt5.QtPrintSupport import QPrinterInfo
        printers = [p.printerName() for p in QPrinterInfo.availablePrinters()]

        self.cmb_label_prn = QComboBox(); self.cmb_label_prn.addItems(printers)
        self.cmb_doc_prn   = QComboBox(); self.cmb_doc_prn.addItems([""]+printers)

        gP.addWidget(QLabel("Etiket yazıcısı"), r,0); gP.addWidget(self.cmb_label_prn, r,1); r+=1
        gP.addWidget(QLabel("PDF yazıcısı"),   r,0); gP.addWidget(self.cmb_doc_prn,   r,1); r+=1
        self.line_tpl = QLineEdit();  gP.addWidget(QLabel("Label şablonu"), r,0)
        gP.addWidget(self.line_tpl, r,1); r+=1
        self.chk_auto_open = QCheckBox("Dosyayı kaydedince otomatik aç"); gP.addWidget(self.chk_auto_open, r,0,1,2)


        # ─── SEKME: Dosya Yolları ─────────────────────────────────
        tab_path = QWidget(); self.tabs.addTab(tab_path, "Dosya Yolları")
        g5 = QGridLayout(tab_path); r = 0

        self.lbl_label_dir  = QLabel(); self._make_dir_row(g5, r, "Etiket klasörü", self.lbl_label_dir); r+=1
        self.lbl_export_dir = QLabel(); self._make_dir_row(g5, r, "Dışa aktarım",   self.lbl_export_dir); r+=1
        self.lbl_log_dir    = QLabel(); self._make_dir_row(g5, r, "Log klasörü",    self.lbl_log_dir);    r+=1

        # Alt butonlar
        btn_row = QHBoxLayout(); main.addLayout(btn_row); btn_row.addStretch()
        self.btn_cancel = QPushButton("Vazgeç"); self.btn_cancel.clicked.connect(self.load)
        self.btn_save   = QPushButton("Kaydet"); self.btn_save.clicked.connect(self.save)
        btn_row.addWidget(self.btn_cancel); btn_row.addWidget(self.btn_save)

    def _add_prefix_row(self) -> None:
        """Tablonun sonuna boş bir ön-ek/depo satırı ekler."""
        self.tbl_pref.insertRow(self.tbl_pref.rowCount())
        # İsterseniz varsayılan depo id’sini ‘01’ verebilirsiniz:
        # self.tbl_pref.setItem(self.tbl_pref.rowCount()-1, 1,
        #                       QTableWidgetItem("01"))

    # SettingsPage sınıfı içinde (ör. _add_prefix_row’ın hemen altına)
    def _del_prefix_row(self):
        """
        Tablo­da seçili satır(lar)ı tamamen kaldırır.
        Yüksek index’ten başlayarak silmek önemlidir.
        """
        rows = {ix.row() for ix in self.tbl_pref.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self.tbl_pref.removeRow(row)


    # ----------------------------------------------------------------
    # Yardımcı – dizin seç butonu
    # ----------------------------------------------------------------
    def _make_dir_row(self, lay: QGridLayout, row: int,
                      label: str, lbl_path: QLabel) -> None:
        btn = QPushButton("Değiştir…")
        btn.clicked.connect(lambda _=False, label=lbl_path: self._choose_dir(label))
        lay.addWidget(QLabel(label), row, 0)
        lay.addWidget(lbl_path,      row, 1)
        lay.addWidget(btn,           row, 2)

    def _choose_dir(self, lbl: QLabel) -> None:
        path = QFileDialog.getExistingDirectory(self, "Klasör Seç", lbl.text() or str(Path.home()))
        if path:
            lbl.setText(path)

    # ----------------------------------------------------------------
    # SETTINGS  →  WIDGET
    def load(self) -> None:
        st.reload()

        # Görünüm
        self.cmb_theme.setCurrentText(st.get("ui.theme"))
        self.spin_font.setValue(st.get("ui.font_pt"))
        self.chk_sound.setChecked(st.get("ui.sounds.enabled"))
        self.spin_volume.setValue(int(st.get("ui.sounds.volume")*100))
        self.spin_toast.setValue(st.get("ui.toast_secs"))
        self.chk_focus.setChecked(st.get("ui.auto_focus"))

        # Loader
        self.spin_loader_refresh.setValue(st.get("loader.auto_refresh"))
        self.chk_loader_block.setChecked(st.get("loader.block_incomplete"))

        # Barkod
        self.tbl_pref.setRowCount(0)
        for pfx, wh in st.get("scanner.prefixes", {}).items():
            self._prefix_to_row(pfx, wh)
        self.spin_tol.setValue(st.get("scanner.over_scan_tol"))

        # Yazdırma
        self.cmb_label_prn.setCurrentText(st.get("print.label_printer", ""))
        self.cmb_doc_prn.setCurrentText  (st.get("print.doc_printer",   ""))
        self.line_tpl.setText(st.get("print.label_tpl"))
        self.chk_auto_open.setChecked(st.get("print.auto_open", True))

        # DB
        self.lin_db_server.setText(st.get("db.server"))
        self.lin_db_name.setText(st.get("db.database"))
        self.lin_db_user.setText(st.get("db.user"))
        self.spin_retry.setValue(st.get("db.retry"))
        self.spin_hb.setValue(st.get("db.heartbeat"))

        # Yollar
        self.lbl_label_dir.setText(st.get("paths.label_dir"))
        self.lbl_export_dir.setText(st.get("paths.export_dir"))
        self.lbl_log_dir.setText(st.get("paths.log_dir"))

# ----------------------------------------------------------------
    # WIDGET → SETTINGS  (+ json diske yaz & sinyal)
    # ----------------------------------------------------------------
    def save(self) -> None:
        # Görünüm
        st.set("ui.theme",          self.cmb_theme.currentText())
        st.set("ui.font_pt",        self.spin_font.value())
        st.set("ui.sounds.enabled", self.chk_sound.isChecked())
        st.set("ui.sounds.volume",  self.spin_volume.value()/100)
        st.set("ui.toast_secs",     self.spin_toast.value())
        st.set("ui.auto_focus",     self.chk_focus.isChecked())

        # Loader
        st.set("loader.auto_refresh",    self.spin_loader_refresh.value())
        st.set("loader.block_incomplete", self.chk_loader_block.isChecked())

        # -------- Barkod ----------   ▼▼ sadece bu bloğu yenile ▼▼
        prefixes: dict[str, str] = {}
        for row in range(self.tbl_pref.rowCount()):
            itm_p = self.tbl_pref.item(row, 0)
            itm_w = self.tbl_pref.item(row, 1)
            if not itm_p or not itm_w:
                continue                      # hücre yoksa atla
            p = itm_p.text().strip()
            w = itm_w.text().strip()
            if p and w:                       # her iki alan DOLU ise kaydet
                prefixes[p] = w
        st.set("scanner.prefixes", prefixes)
        st.set("scanner.over_scan_tol", self.spin_tol.value())

        # Yazdırma
        st.set("print.label_printer", self.cmb_label_prn.currentText())
        st.set("print.doc_printer",   self.cmb_doc_prn.currentText())
        st.set("print.label_tpl",     self.line_tpl.text())
        st.set("print.auto_open",     self.chk_auto_open.isChecked())

        # DB
        st.set("db.server",    self.lin_db_server.text())
        st.set("db.database",  self.lin_db_name.text())
        st.set("db.user",      self.lin_db_user.text())
        st.set("db.retry",     self.spin_retry.value())
        st.set("db.heartbeat", self.spin_hb.value())

        # Yollar
        st.set("paths.label_dir",  self.lbl_label_dir.text())
        st.set("paths.export_dir", self.lbl_export_dir.text())
        st.set("paths.log_dir",    self.lbl_log_dir.text())

        self.settings_saved.emit()
        QMessageBox.information(self, "Ayarlar", "Kaydedildi ✓")
            # ----------------------------------------------------------------
    # Kısayol: Esc = Vazgeç
    # ----------------------------------------------------------------
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.load()
        else:
            super().keyPressEvent(e)


    def _prefix_to_row(self, prefix: str, warehouse: str) -> None:
        """
        scanner.prefixes sözlüğündeki her bir ögeyi
        (örn. 'D1-' : '01') tabloya tek satır olarak yazar.
        """
        row = self.tbl_pref.rowCount()
        self.tbl_pref.insertRow(row)

        itm_p = QTableWidgetItem(prefix)
        itm_w = QTableWidgetItem(warehouse)

        # Düzenlenebilir bırakmak istiyorsanız flags() ayarlamasına gerek yok;
        # salt-okunur olsun derseniz:
        # itm_p.setFlags(itm_p.flags() | Qt.ItemIsEditable)
        # itm_w.setFlags(itm_w.flags() | Qt.ItemIsEditable)

        self.tbl_pref.setItem(row, 0, itm_p)
        self.tbl_pref.setItem(row, 1, itm_w)