from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDateEdit, QSpinBox, QLineEdit,
    QComboBox, QMessageBox, QHeaderView, QFileDialog
)
from PyQt5.QtCore import Qt, QDate, QSize
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

# --- Backend imports for Pick‑List ---------------------------------
from app.dao.logo import (
    fetch_draft_orders,
    fetch_order_lines,
    update_order_status,
)
from app.services.picklist import create_picklist_pdf

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LOGLine Yönetim Paneli")
        self.setMinimumSize(1200, 800)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        palette = self.sidebar.palette()
        palette.setColor(QPalette.Base, QColor('#2C3E50'))
        palette.setColor(QPalette.Text, QColor('#ECF0F1'))
        self.sidebar.setPalette(palette)
        modules = ['Pick-List','Scanner','Back-Orders','Rapor','Etiket','Ayarlar']
        icons = ['document-print','system-search','view-list','x-office-spreadsheet','emblem-ok','preferences-system']
        for name, icon in zip(modules, icons):
            itm = QListWidgetItem(QIcon.fromTheme(icon), name)
            itm.setSizeHint(QSize(180,40))
            self.sidebar.addItem(itm)
        self.sidebar.currentRowChanged.connect(self._display_page)
        main_layout.addWidget(self.sidebar)

        # Stacked Pages
        self.pages = QStackedWidget()
        main_layout.addWidget(self.pages,1)
        self.pages.addWidget(self._page_picklist())
        self.pages.addWidget(self._page_scanner())
        self.pages.addWidget(self._page_backorders())
        self.pages.addWidget(self._page_report())
        self.pages.addWidget(self._page_label())
        self.pages.addWidget(self._page_settings())
        self.sidebar.setCurrentRow(0)

    def _display_page(self,index):
        self.pages.setCurrentIndex(index)

    def _make_header(self,text):
        lbl = QLabel(text)
        lbl.setFont(QFont('Arial',16,QFont.Bold))
        lbl.setStyleSheet('color:#34495E; padding:8px 0')
        return lbl

    # ---------- Pick-List ----------
    def _page_picklist(self):
        w=QWidget(); layout=QVBoxLayout(w)
        layout.addWidget(self._make_header('Pick-List Oluştur'))
        ctrl=QHBoxLayout()
        ctrl.addWidget(QLabel('Limit:'))
        self.pick_limit=QSpinBox();self.pick_limit.setRange(1,500);self.pick_limit.setValue(50)
        ctrl.addWidget(self.pick_limit)
        btn_load=QPushButton('Siparişleri Yükle'); btn_load.clicked.connect(self.load_picklist)
        btn_pdf=QPushButton('PDF Oluştur'); btn_pdf.clicked.connect(self.generate_picklist)
        ctrl.addStretch(); ctrl.addWidget(btn_load); ctrl.addWidget(btn_pdf)
        layout.addLayout(ctrl)
        self.tbl_pick=QTableWidget(0,3)
        self.tbl_pick.setHorizontalHeaderLabels(['Sipariş No','Müşteri','Tarih'])
        self.tbl_pick.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_pick)
        return w

    # ---------- Scanner ----------
    def _page_scanner(self):
        w=QWidget(); layout=QVBoxLayout(w)
        layout.addWidget(self._make_header('Scanner Barkod Doğrulama'))
        ctrl=QHBoxLayout()
        ctrl.addWidget(QLabel('Sipariş:'))
        self.combo_scan_orders=QComboBox()
        ctrl.addWidget(self.combo_scan_orders)
        ctrl.addWidget(QLabel('Ambar:'))
        self.combo_warehouse=QComboBox()
        ctrl.addWidget(self.combo_warehouse)
        btn_load=QPushButton('Yükle'); btn_load.clicked.connect(self.load_scanner_orders)
        ctrl.addWidget(btn_load)
        layout.addLayout(ctrl)
        self.tbl_scan=QTableWidget(0,5)
        self.tbl_scan.setHorizontalHeaderLabels(['Stok Kodu','Ürün Adı','İst','Okunan','Ambar'])
        self.tbl_scan.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_scan)
        scan_ctrl=QHBoxLayout()
        self.entry_scan=QLineEdit();self.entry_scan.setPlaceholderText('Barkod okutun...')
        scan_ctrl.addWidget(self.entry_scan)
        btn_scan=QPushButton('Oku'); btn_scan.clicked.connect(self.on_scan)
        scan_ctrl.addWidget(btn_scan)
        layout.addLayout(scan_ctrl)
        btn_complete=QPushButton('Siparişi Tamamla'); btn_complete.clicked.connect(self.finish_order)
        layout.addWidget(btn_complete)
        return w

    # ---------- Back-Orders ----------
    def _page_backorders(self):
        w=QWidget(); layout=QVBoxLayout(w)
        layout.addWidget(self._make_header('Back-Order Bekleyen'))
        ctrl=QHBoxLayout()
        btn_refresh=QPushButton('Bekleyenleri Yenile'); btn_refresh.clicked.connect(self.load_backorders)
        btn_mark=QPushButton('Seçiliyi Tamamla'); btn_mark.clicked.connect(self.complete_selected)
        ctrl.addWidget(btn_refresh); ctrl.addWidget(btn_mark); ctrl.addStretch()
        layout.addLayout(ctrl)
        self.tbl_back=QTableWidget(0,6)
        self.tbl_back.setHorizontalHeaderLabels(['ID','Sipariş No','Ürün','Eksik','Ambar','Tarih'])
        self.tbl_back.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_back)
        return w

    # ---------- Rapor ----------
    def _page_report(self):
        w=QWidget(); layout=QVBoxLayout(w)
        layout.addWidget(self._make_header('Günlük Rapor'))
        ctrl=QHBoxLayout()
        self.date_report=QDateEdit(QDate.currentDate())
        ctrl.addWidget(QLabel('Tarih:')); ctrl.addWidget(self.date_report)
        btn_view=QPushButton('Raporu Görüntüle'); btn_view.clicked.connect(self.generate_report)
        ctrl.addWidget(btn_view); ctrl.addStretch()
        btn_save=QPushButton('Excel İndir'); btn_save.clicked.connect(self.download_report)
        ctrl.addWidget(btn_save)
        layout.addLayout(ctrl)
        self.tbl_report=QTableWidget(0,5)
        self.tbl_report.setHorizontalHeaderLabels(['Sipariş','Ürün','Eksik','Ambar','Tamamlanma'])
        self.tbl_report.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_report)
        return w

    # ---------- Label ----------
    def _page_label(self):
        w=QWidget(); layout=QVBoxLayout(w)
        layout.addWidget(self._make_header('Back-Order Etiket Bas'))
        ctrl=QHBoxLayout()
        self.date_label=QDateEdit(QDate.currentDate()); ctrl.addWidget(QLabel('Tarih:')); ctrl.addWidget(self.date_label)
        self.spin_label=QSpinBox(); self.spin_label.setRange(1,10); ctrl.addWidget(QLabel('Paket Adedi:')); ctrl.addWidget(self.spin_label)
        btn_label=QPushButton('Etiket Bas'); btn_label.clicked.connect(self.generate_label)
        ctrl.addStretch(); ctrl.addWidget(btn_label)
        layout.addLayout(ctrl)
        return w

    # ---------- Settings ----------
    def _page_settings(self):
        w=QWidget(); layout=QVBoxLayout(w)
        layout.addWidget(self._make_header('Ayarlar'))
        layout.addWidget(QLabel('DB Server:')); self.db_server=QLineEdit(); layout.addWidget(self.db_server)
        layout.addWidget(QLabel('DB Kullanıcı:')); self.db_user=QLineEdit(); layout.addWidget(self.db_user)
        layout.addWidget(QLabel('DB Şifre:')); self.db_pass=QLineEdit(); self.db_pass.setEchoMode(QLineEdit.Password); layout.addWidget(self.db_pass)
        layout.addWidget(QLabel('Printer Adı:')); self.printer_name=QLineEdit(); layout.addWidget(self.printer_name)
        btn_save=QPushButton('Ayarları Kaydet'); btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        return w

        # ---------- Placeholder Methods ----------
        # ---------- Pick‑List Logic ----------
    def load_picklist(self):
        """Siparişleri Logo'dan çeker ve tabloya doldurur."""
        limit = self.pick_limit.value()
        try:
            orders = fetch_draft_orders(limit=limit)
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"DB bağlantı hatası:{exc}")

            return

        self.orders_cache = orders  # tablo satır -> sipariş eşlemesi
        self.tbl_pick.setRowCount(0)
        for row, o in enumerate(orders):
            self.tbl_pick.insertRow(row)
            self.tbl_pick.setItem(row, 0, QTableWidgetItem(o["order_no"]))
            self.tbl_pick.setItem(row, 1, QTableWidgetItem(o["customer_code"]))
            self.tbl_pick.setItem(row, 2, QTableWidgetItem(str(o["order_date"])[:10]))
        QMessageBox.information(self, "Pick‑List", f"{len(orders)} sipariş yüklendi.")

    def generate_picklist(self):
        """Seçili (veya tüm) siparişler için PDF pick‑list oluşturur."""
        if not hasattr(self, "orders_cache") or not self.orders_cache:
            QMessageBox.warning(self, "Pick‑List", "Önce siparişleri yükleyin.")
            return

        # Seçili satır indeksleri; seçim yoksa hepsi
        selected = [idx.row() for idx in self.tbl_pick.selectedIndexes()]
        if not selected:
            selected = list(range(len(self.orders_cache)))

        ok_count = 0
        for row in selected:
            order = self.orders_cache[row]
            lines = fetch_order_lines(order["order_id"])
            try:
                create_picklist_pdf(order, lines)
                update_order_status(order["order_id"], 2)  # STATUS = picking
                ok_count += 1
            except Exception as exc:
                QMessageBox.warning(self, "Pick‑List", f"{order['order_no']} hata:{exc}")


        QMessageBox.information(self, "Pick‑List", f"{ok_count} pick‑list PDF oluşturuldu ve STATUS=2 yapıldı.")

    # ---------- Rapor / İndir ----------
    def download_report(self):
        """Excel dosyasını kayıt eder."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            'Excel Kaydet',
            '',
            'Excel Files (*.xlsx)'
        )
        if not path:
            return
        # TODO: gerçek raporu path'e yaz
        QMessageBox.information(self, 'Rapor', f'Rapor kaydedildi:{path}')


    def save_settings(self):
        # TODO: ayarları kalıcı dosyaya yaz
        QMessageBox.information(self, 'Ayarlar', 'Ayarlar kaydedildi.')

    def generate_label(self):
        # TODO: backorder_label_service.make_backorder_labels
        QMessageBox.information(self, 'Etiket', 'Etiket basıldı.')

        # TODO: picklist servisini çağır
        QMessageBox.information(self, 'Pick-List', 'PDF oluşturuldu.')

    def load_scanner_orders(self):
        # TODO: fetch_picking_orders, fetch_order_lines, populate combobox ve table
        QMessageBox.information(self, 'Scanner', 'Sipariş yüklendi.')

    def on_scan(self):
        # TODO: barkod okutma ve table güncelleme
        pass

    def finish_order(self):
        # TODO: backorder.insert, update_order_header, update_order_status
        QMessageBox.information(self, 'Scanner', 'Sipariş tamamlandı.')

    def load_backorders(self):
        # TODO: list_pending, tabloya yükle
        QMessageBox.information(self, 'Back-Order', 'Bekleyenler yüklendi.')

    def complete_selected(self):
        # TODO: seçili backorder kaydını mark_fulfilled
        QMessageBox.information(self, 'Back-Order', 'Seçili tamamlandı.')

    def generate_report(self):
        # TODO: list_fulfilled(date), tabloyu doldur
        QMessageBox.information(self, 'Rapor', 'Rapor görüntülendi.')

        # ---------- Rapor / İndir ----------
    def download_report(self):
        """Excel dosyasını kayıt eder."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            'Excel Kaydet',
            '',
            'Excel Files (*.xlsx)'
        )
        if not path:
            return
        # TODO: gerçek raporu path'e yaz
        QMessageBox.information(self, 'Rapor', f'Rapor kaydedildi:{path}')


    # ---------- Ayarları Kaydet ----------
    def save_settings(self):
        """DB & yazıcı ayarlarını kalıcı olarak saklar (TODO)."""
        # TODO: settings.json veya .env dosyasına yaz
        QMessageBox.information(self, 'Ayarlar', 'Ayarlar kaydedildi.')

    # ---------- Back‑order Etiket ----------
    def generate_label(self):
        """Seçilen tarihte back‑order etiketi basar (TODO)."""
        QMessageBox.information(self, 'Etiket', 'Etiket basıldı.')
