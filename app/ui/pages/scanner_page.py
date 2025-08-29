"""Scanner Page – Barkod Doğrulama
============================================================
• STATUS = 2 siparişleri listeler (senkron kuyruk: **WMS_PICKQUEUE**)
• Combodan sipariş seçildiğinde otomatik yüklenir; gizli “Yükle” butonu yedekte
• Barkod okutuldukça `qty_sent` DB’de artar → tüm istasyonlar aynı değeri görür
• “Tamamla” → sevkiyat + back‑order + STATUS 4 + kuyruğu temizler
"""
from __future__ import annotations
import logging
import sys
import threading
import getpass
from pathlib import Path
from datetime import date
from typing import Dict, List
from app.settings import get as cfg
import app.settings as st
from app.dao.logo import (
    resolve_barcode_prefix,
    log_activity,
    queue_inc,
)

from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl, QTimer, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QMessageBox,
    QInputDialog, QProgressBar, QMenu, QAction
)
from PyQt5.QtGui import QColor

# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[3]
SOUND_DIR = BASE_DIR / "sounds"

# Sound manager kullan - memory leak önlenir
from app.utils.sound_manager import get_sound_manager
sound_manager = get_sound_manager()

# ---------------------------------------------------------------------------
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# ---- DAO & servisler -------------------------------------------------------
from app.dao.logo import (  # noqa: E402
    fetch_picking_orders,
    fetch_order_lines,
    update_order_status,
    update_order_header,
    fetch_order_header,
    fetch_invoice_no,
    queue_fetch,
    queue_delete,
    exec_sql,
    fetch_one,
)
from app.dao.transactions import transaction_scope  # noqa: E402
import app.backorder as bo  # noqa: E402
from app.shipment import upsert_header  # noqa: E402
from app import toast  # noqa: E402

# Barcode lookup moved to centralized service
from app.services.barcode_service import barcode_xref_lookup, find_item_by_barcode



try:
    from app.services.label_service import make_labels as print_labels
except Exception:
    print_labels = None

logger = logging.getLogger(__name__)




# ---------------------------------------------------------------------------
class ScannerPage(QWidget):

    # -----------------------------------------------------------
    WH_PREFIX_MAP = {        # depo kodu  →  warehouse_id
        "D1-": "0",          # Merkez
        "D3-": "1",          # EGT
        "D4-": "2",          # OTOİS
        "D5-": "3",          # ATAK
    }
    # -----------------------------------------------------------

    """STATUS = 2 siparişler için barkod doğrulama ekranı."""

    def __init__(self):
            super().__init__()

            # Ayarlardaki depo ön-ek sözlüğü (.json → "scanner.prefixes") varsa
            # sabiti onunla ezerek dinamikleştir.
            custom_map = cfg("scanner.prefixes", None)
            if custom_map:
                self.WH_PREFIX_MAP = custom_map

            self.current_order: Dict | None = None
            self.lines: List[Dict] = []
            self.sent:  Dict[str, float] = {}
            self._order_map: Dict[str, Dict] = {}
            
            # Thread-safe cache implementation
            from app.utils.thread_safe_cache import get_barcode_cache
            self._barcode_cache = get_barcode_cache()  # Thread-safe barcode cache
            self._warehouse_set: set = set()  # mevcut siparişin depoları
            self._scan_lock = threading.Lock()  # Thread-safe scan işlemi için lock
            
            self._build_ui()
            self.refresh_orders()
    def showEvent(self, event):
        """Sekmeye / ekrana dönüldüğünde:
           • sipariş listesini yenile
           • barkod kutusuna odak ver
        """
        super().showEvent(event)

        self.refresh_orders()             # eski alt showEvent’ten
        QTimer.singleShot(0, self.entry.setFocus)   # odak

    def apply_settings(self):
        """UI ayarlarını anında uygula."""
        # Sound manager ayarlarını uygula
        sound_manager.apply_settings()

        # Over-scan toleransı
        self._over_tol = st.get("scanner.over_scan_tol", 0)

    def _infer_wh_from_prefix(self, barcode: str) -> str | None:
        """
        Barkod veya stok kodu 'D4-AYD ...' biçimindeyse
        ön-ekten depo numarasını (warehouse_id) döndürür.
        """
        for pfx, wh in self.WH_PREFIX_MAP.items():
            if barcode.upper().startswith(pfx):
                return wh
        return None
    
    # ---------------- UI ----------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lbl = QLabel("<b>Scanner Barkod Doğrulama</b>")
        lbl.setStyleSheet("font-size:16px; color:#34495E")
        lay.addWidget(lbl)

        # --- Sipariş seçimi satırı ---
        # === ÜST PANEL: Sipariş seçimi + Progress ===
        top = QHBoxLayout()
        top.addWidget(QLabel("Sipariş:"))
        self.cmb_orders = QComboBox()
        self.cmb_orders.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 2px solid #E3F2FD;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: #1565C0;
                min-width: 250px;
            }
            QComboBox:hover {
                border-color: #1976D2;
                background-color: #F0F7FF;
            }
            QComboBox:focus {
                border-color: #0D47A1;
                background-color: #E3F2FD;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #E3F2FD;
                background-color: #42A5F5;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #1976D2;
                background-color: white;
                selection-background-color: #E3F2FD;
                selection-color: #0D47A1;
                font-size: 13px;
            }
        """)
        self.cmb_orders.currentIndexChanged.connect(self.load_order)  # otomatik yükle
        top.addWidget(self.cmb_orders)

        self.btn_load = QPushButton("📥 Yükle")
        self.btn_load.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #42A5F5, stop:1 #1976D2);
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                margin: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #64B5F6, stop:1 #1976D2);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1976D2, stop:1 #1565C0);
            }
        """)
        self.btn_load.clicked.connect(self.load_order)
        self.btn_load.hide()  # talebe göre gizli kalsın
        top.addWidget(self.btn_load)
        top.addStretch()
        
        # === VARDIYA BİLGİLERİ PANELİ ===
        self.lbl_shift_stats = QLabel("Bugün: 0 sipariş | Bu saat: 0")
        self.lbl_shift_stats.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e3f2fd, stop:1 #f3e5f5);
                border: 1px solid #90caf9;
                border-radius: 6px;
                padding: 6px 12px;
                color: #1976d2;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        top.addWidget(self.lbl_shift_stats)
        
        lay.addLayout(top)
        
        # === PROGRESS BAR ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("İlerleme: %p% (%v / %m ürün)")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #45a049);
                border-radius: 5px;
            }
        """)
        lay.addWidget(self.progress_bar)

        # --- Tablo ---
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Stok", "Ürün Adı", "İst", "Gönderilen", "Ambar", "Raf"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # === YENİ ÖZELLİKLER ===
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)  # Sağ tık menüsü
        self.tbl.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tbl.itemDoubleClicked.connect(self.on_double_click_item)  # Çift tık
        
        # CTRL+C kopyalama desteği
        from PyQt5.QtGui import QKeySequence
        from PyQt5.QtWidgets import QShortcut
        copy_shortcut = QShortcut(QKeySequence.Copy, self.tbl)
        copy_shortcut.activated.connect(self.copy_selected_cell)
        
        # === MODERN TABLO TASARIMI ===
        self.tbl.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 2px solid #E8EDF3;
                border-radius: 8px;
                gridline-color: #F1F5F9;
                font-size: 13px;
                selection-background-color: #E3F2FD;
                alternate-background-color: #FAFBFC;
            }
            
            QTableWidget::item {
                padding: 8px;
            }
            
            QTableWidget::item:selected {
                background-color: #1976D2;
                color: white;
            }
            
            QTableWidget::item:hover {
                background-color: #F0F7FF;
            }
            
            QHeaderView::section {
                background-color: #4A90E2;
                color: white;
                padding: 10px;
                border: none;
                border-right: 1px solid #2E6DA4;
                font-weight: bold;
                font-size: 12px;
            }
            
            QHeaderView::section:hover {
                background-color: #5BA0F2;
            }
            
            QScrollBar:vertical {
                background: #F5F7FA;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #CBD5E0;
                min-height: 20px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #A0AEC0;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background: #F5F7FA;
                height: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #CBD5E0;
                min-width: 20px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #A0AEC0;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        
        # Tablo ayarları
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setSortingEnabled(False)  # Karışıklığı önlemek için
        self.tbl.setShowGrid(True)
        
        lay.addWidget(self.tbl)

        # --- Barkod girişi ---
        scan = QVBoxLayout()
        
        # Başlık
        scan_label = QLabel("🔍 BARKOD GİRİŞİ")
        scan_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2e7d32;
                padding: 5px;
            }
        """)
        scan.addWidget(scan_label)
        
        # Büyük barkod kutusu
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("🔍 Barkod okutun veya yazın → Enter")
        self.entry.setStyleSheet("""
            QLineEdit {
                font-size: 18px;
                font-weight: bold;
                padding: 16px 20px;
                border: 3px solid #4CAF50;
                border-radius: 12px;
                background: #FFFFFF;
                color: #2E7D32;
                selection-background-color: #81C784;
            }
            QLineEdit:focus {
                border: 3px solid #2E7D32;
                background: #F1F8E9;
            }
            QLineEdit:hover {
                border-color: #66BB6A;
                background: #F9FBE7;
            }
        """)
        self.entry.returnPressed.connect(self.on_scan)
        scan.addWidget(self.entry)
        lay.addLayout(scan)
        
        # === SON İŞLEM BİLGİSİ ===
        self.lbl_last_scan = QLabel("🟢 Hazır - Barkod bekleniyor...")
        self.lbl_last_scan.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e8f5e8, stop:1 #f1f8e9);
                border: 2px solid #81c784;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                font-weight: bold;
                color: #2e7d32;
                margin: 5px;
            }
        """)
        lay.addWidget(self.lbl_last_scan)
        
        # === ZAMAN TAKİBİ PANELİ ===
        time_widget = QWidget()
        time_widget.setStyleSheet("""
            QWidget {
                background: #fff3e0;
                border: 1px solid #ffb74d;
                border-radius: 6px;
                margin: 2px;
            }
        """)
        
        time_layout = QHBoxLayout(time_widget)
        
        # Geçen süre
        self.lbl_time_info = QLabel("⏱️ Geçen: --:--")
        self.lbl_time_info.setStyleSheet("""
            QLabel {
                color: #e65100;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
                background: transparent;
                border: none;
            }
        """)
        time_layout.addWidget(self.lbl_time_info)
        
        # Ayırıcı
        separator = QLabel("|")
        separator.setStyleSheet("color: #ffb74d; font-weight: bold;")
        time_layout.addWidget(separator)
        
        # Tahmini bitiş
        self.lbl_estimated = QLabel("🎯 Bitiş: --:--")
        self.lbl_estimated.setStyleSheet("""
            QLabel {
                color: #e65100;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
                background: transparent;
                border: none;
            }
        """)
        time_layout.addWidget(self.lbl_estimated)
        time_layout.addStretch()
        
        lay.addWidget(time_widget)

        # --- Tamamla butonu ---
        self.btn_done = QPushButton("✅ Siparişi Tamamla")
        self.btn_done.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66BB6A, stop:1 #4CAF50);
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 18px 35px;
                border: none;
                border-radius: 12px;
                margin: 10px;
                min-width: 200px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5CB85C, stop:1 #449D44);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAE4C, stop:1 #388E3C);
            }
            QPushButton:disabled {
                background: #CCCCCC;
                color: #666666;
            }
        """)
        self.btn_done.clicked.connect(self.finish_order)
        lay.addWidget(self.btn_done, alignment=Qt.AlignmentFlag.AlignRight)

    # ---- Pick‑List’ten gelen siparişi comboya ekle ----
    def enqueue(self, order: Dict):
        key = f"{order['order_no']} – {order['customer_code']}"
        if key not in self._order_map:
            self._order_map[key] = order
            self.cmb_orders.addItem(key)

    # ---- Yardımcı: tabloyu doldur ---- 
    def _populate_table(self):
        """Satır renklendirme:
           • Tamamı gönderildi → yeşil
           • Hiç gönderilmedi   → kırmızı
           • Kısmen gönderildi → sarı
        """

        self.tbl.setRowCount(0)
        for ln in self.lines:
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)

            code     = ln["item_code"]
            ordered  = ln["qty_ordered"]
            sent     = self.sent.get(code, 0)

            cells = [
                code,
                ln["item_name"],
                ordered,
                sent,
                ln["warehouse_id"],
                ln["shelf_loc"] or "",
            ]
            for c, val in enumerate(cells):
                itm = QTableWidgetItem(str(val))
                itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter if c != 1 else Qt.AlignmentFlag.AlignLeft)
                self.tbl.setItem(row, c, itm)

            # ---- Modern Renklendirme & İkonlar ------------------------------------
            completion_percent = (sent / ordered * 100) if ordered > 0 else 0
            
            # Durum belirteci ekle (ilk sütuna)
            code_item = self.tbl.item(row, 0)
            
            if sent >= ordered and ordered > 0:          # tam + fazla
                color = QColor("#E8F5E8")                # açık yeşil
                border_color = "#4CAF50"
                icon = "✅"
                status = "completed"
            elif sent == 0:
                color = QColor("#FFEBEE")                # açık kırmızı  
                border_color = "#F44336"
                icon = "❌"
                status = "pending"
            else:                                        # eksik (kısmi)
                color = QColor("#FFF3E0")                # açık turuncu
                border_color = "#FF9800"
                icon = "🔄"
                status = "progress"
            
            # Tüm satırı renklendir ve border ekle
            for c in range(6):
                item = self.tbl.item(row, c)
                item.setBackground(color)
                
                # İlk sütuna durum ikonu ekle
                if c == 0:
                    item.setText(f"{icon} {code}")
                    item.setToolTip(f"Durum: {status}\nTamamlanma: %{completion_percent:.1f}")
                
                # Özel stil özellikleri
                current_style = item.data(Qt.UserRole) or ""
                item.setData(Qt.UserRole, f"{current_style}border-left: 4px solid {border_color}; completion: {status};")
            
            # İlerleme yüzdesini "Gönderilen" sütununda göster
            sent_item = self.tbl.item(row, 3)
            if completion_percent > 0:
                sent_item.setText(f"{sent} (%{completion_percent:.0f})")
                sent_item.setToolTip(f"Tamamlanan: {sent}/{ordered} adet\nYüzde: %{completion_percent:.1f}")
            else:
                sent_item.setText(str(sent))
                sent_item.setToolTip(f"Tamamlanan: {sent}/{ordered} adet")
    # ------------------------------------------------------------------


    # ---- STATUS 2 başlıklarını getir ----
    def refresh_orders(self):
        try:
            orders = fetch_picking_orders(limit=200)
        except Exception as exc:
            QMessageBox.critical(self, "DB Hatası", str(exc))
            return
        self._order_map = {f"{o['order_no']} – {o['customer_code']}": o for o in orders}
        self.cmb_orders.clear()
        self.cmb_orders.addItems(self._order_map.keys())

    # Pick‑List sinyali için alias
    def load_orders(self):
        self.refresh_orders()

    # ---- Seçilen siparişi yükle ----
    def load_order(self):
        key = self.cmb_orders.currentText()
        if not key:
            return
        self.current_order = self._order_map.get(key)
        if not self.current_order:
            return
        try:
            self.lines = fetch_order_lines(self.current_order["order_id"])
            sent_map = {r["item_code"]: r["qty_sent"] for r in queue_fetch(self.current_order["order_id"]) }
            
            # Thread-safe cache temizle ve depo setini hazırla
            self._barcode_cache.clear()
            self._warehouse_set = {ln["warehouse_id"] for ln in self.lines}
            
        except Exception as exc:
            QMessageBox.critical(self, "Satır Hatası", str(exc))
            return
        self.sent = {ln["item_code"]: sent_map.get(ln["item_code"], 0) for ln in self.lines}
        self._populate_table()
        self.entry.setFocus()
        
        # === YENİ ÖZELLİKLER ===
        # Zaman takibini başlat
        from datetime import datetime
        self.order_start_time = datetime.now()
        
        # Progress bar güncelle
        self.update_progress()
        
        # Vardiya istatistiklerini güncelle
        self.update_shift_stats()
        
        # Son işlem bilgisini güncelle
        self.lbl_last_scan.setText(f"📋 Sipariş yüklendi: {self.current_order['order_no']} ({len(self.lines)} ürün)")

     
    # ---- Barkod / Kod okutuldu ----
    def on_scan(self) -> None:
        raw = self.entry.text().strip()
        self.entry.clear()
        
        # DEBUG: Barkod kontrolü için log
        print(f"[DEBUG] Okutulan barkod: '{raw}' (uzunluk: {len(raw)})")
        
        # Focus'u geri ver (kritik!)
        QTimer.singleShot(0, self.entry.setFocus)
        
        # ──────────────────────────────────────────────
        # YANLŞ BARKOD KONTROLLERİ
        # ──────────────────────────────────────────────
        
        # 1. Boş veya çok kısa barkod
        if not raw:
            return
        if len(raw) < 2:
            sound_manager.play_error()
            QMessageBox.warning(self, "Barkod", "Barkod çok kısa!")
            return
            
        # 2. Sipariş seçili mi?
        if not self.current_order:
            sound_manager.play_error()
            QMessageBox.warning(self, "Sipariş", "Önce sipariş seçin!")
            return
            
        # 3. Geçersiz karakterler kontrolü - boşluk da izin ver
        # Alfanumerik + tire/alt çizgi/slash/nokta/artı/boşluk izin ver
        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/.+ ")
        invalid_chars = [c for c in raw if c.upper() not in allowed_chars]
        if invalid_chars:
            sound_manager.play_error()
            QMessageBox.warning(self, "Barkod", f"Barkod geçersiz karakterler içeriyor: {', '.join(set(invalid_chars))}\nBarkod: {raw}")
            return
            
        # 4. Depo prefix kontrolü - yanlış depo barkodu
        detected_wh = self._infer_wh_from_prefix(raw)
        if detected_wh and detected_wh not in self._warehouse_set:
            sound_manager.play_error()
            QMessageBox.warning(self, "Depo Hatası", 
                              f"Bu barkod farklı depo için (Depo: {detected_wh})!\nBu siparişin depoları: {', '.join(self._warehouse_set)}")
            return

        # Thread-safe scan işlemi
        if not self._scan_lock.acquire(blocking=False):
            return  # Başka bir scan işlemi devam ediyor
        
        try:
            # Thread-safe cache kontrolü
            cache_key = f"{raw}_{self.current_order['order_id']}"
            cached_result = self._barcode_cache.get(cache_key)
            
            if cached_result:
                matched_line, qty_inc = cached_result
            else:
                matched_line, qty_inc = self._find_matching_line(raw)
                if matched_line:
                    # Thread-safe cache update
                    self._barcode_cache.set(cache_key, (matched_line, qty_inc))

            if not matched_line:
                sound_manager.play_error()
                QMessageBox.warning(self, "Barkod / Kod", f"'{raw}' bu siparişte eşleşmedi!\n\nBu barkod:\n• Stok kodu değil\n• Depo prefix'i yanlış\n• barcode_xref'te yok")
                log_activity(getpass.getuser(), "INVALID_SCAN",
                             details=raw, order_no=self.current_order["order_no"])
                return

            # Fazla okutma kontrolü
            code      = matched_line["item_code"]
            ordered   = float(matched_line["qty_ordered"])
            sent_now  = float(self.sent.get(code, 0))

            # qty_inc zaten float olarak geliyor, Decimal kontrolüne gerek yok
            qty_inc = float(qty_inc) if qty_inc else 1.0
            over_tol = float(self._over_tol or 0)

            if sent_now + qty_inc > ordered + over_tol:
                sound_manager.play_error()
                QMessageBox.warning(
                    self, "Fazla Adet",
                    f"{code} için sipariş adedi {ordered}; {sent_now + qty_inc} okutulamaz."
                )
                log_activity(getpass.getuser(), "OVER_SCAN",
                             details=f"{code} / Giriş:{raw}",
                             order_no=self.current_order["order_no"],
                             item_code=code,
                             qty_ordered=ordered,
                             qty_scanned=sent_now + qty_inc,
                             warehouse_id=matched_line["warehouse_id"])
                return

            # Database ve local state güncelleme - atomic olmalı
            try:
                # Önce database güncelle
                queue_inc(self.current_order["order_id"], code, qty_inc)
                
                # Database başarılıysa local state güncelle
                self.sent[code] = sent_now + qty_inc
                
                # UI güncelle
                self._update_single_row(code, sent_now + qty_inc)
                
                # === YENİ ÖZELLİKLER ===
                # Progress bar güncelle
                self.update_progress()
                
                # Son işlem bilgisini göster
                self.lbl_last_scan.setText(f"🎯 BAŞARILI: {code} (+{qty_inc} adet) → Toplam: {sent_now + qty_inc}")
                
                # Başarı sesi - en son
                QTimer.singleShot(0, sound_manager.play_ok)
            except Exception as e:
                # Hata durumunda cache'i temizle
                self._barcode_cache.delete(cache_key)
                sound_manager.play_error()
                QMessageBox.critical(self, "Database Hatası", f"Kayıt güncellenemedi: {e}")
                return
            
        finally:
            self._scan_lock.release()

    def _find_matching_line(self, raw: str) -> tuple:
        """Barkod eşleştirme optimized version"""
        try:
            # Use centralized barcode service
            matched_line, qty_inc = find_item_by_barcode(raw, self.lines, self._warehouse_set)
            return matched_line, qty_inc
        except Exception as e:
            # Database error - show actual error to user
            logger.error(f"Barcode lookup error: {e}")
            sound_manager.play_error()
            QMessageBox.critical(self, "Database Hatası", 
                                f"Barkod kontrolü sırasında hata oluştu:\n{str(e)}\n\nLütfen IT desteğe başvurun.")
            return None, 1

    def _update_single_row(self, item_code: str, new_sent: float):
        """Tek satırı güncelle - tüm tabloyu yeniden çizmek yerine"""
        
        for row in range(self.tbl.rowCount()):
            code_item = self.tbl.item(row, 0)
            if code_item:
                # İkon içeren text'ten sadece kodu al (ikonu kaldır)
                item_text = code_item.text()
                # "✅ D4-AFT" -> "D4-AFT" 
                actual_code = item_text.split(" ", 1)[-1] if " " in item_text else item_text
                
                if actual_code == item_code:
                    # Gönderilen kolonunu güncelle ve modern renklendirme uygula
                    ordered = float(self.tbl.item(row, 2).text())
                    completion_percent = (new_sent / ordered * 100) if ordered > 0 else 0
                    
                    # Modern renklendirme sistemi
                    if new_sent >= ordered and ordered > 0:
                        color = QColor("#E8F5E8")  # açık yeşil
                        icon = "✅"
                        status = "completed"
                    elif new_sent == 0:
                        color = QColor("#FFEBEE")  # açık kırmızı
                        icon = "❌"
                        status = "pending"
                    else:
                        color = QColor("#FFF3E0")  # açık turuncu
                        icon = "🔄"
                        status = "progress"
                    
                    # İlk kolonun textini güncelle (ikon + kod)
                    code_item.setText(f"{icon} {item_code}")
                    code_item.setToolTip(f"Durum: {status}\nTamamlanma: %{completion_percent:.1f}")
                    
                    # Gönderilen kolonunu güncelle
                    sent_item = self.tbl.item(row, 3)
                    if sent_item:
                        if completion_percent > 0:
                            sent_item.setText(f"{new_sent} (%{completion_percent:.0f})")
                            sent_item.setToolTip(f"Tamamlanan: {new_sent}/{ordered} adet\nYüzde: %{completion_percent:.1f}")
                        else:
                            sent_item.setText(str(new_sent))
                            sent_item.setToolTip(f"Tamamlanan: {new_sent}/{ordered} adet")
                    
                    # Tüm satırı renklendir
                    for c in range(6):
                        self.tbl.item(row, c).setBackground(color)
                    break


      
        # ---------- Siparişi tamamla ----------
    def finish_order(self):
        if not self.current_order:
            return

        # --- 1. Eksik kontrolü ------------------------------------------------
        if any(self.sent[ln["item_code"]] < ln["qty_ordered"] for ln in self.lines):
            if QMessageBox.question(
                self, "Eksikler",
                "Eksikler var, yine de tamamla?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.No:
                return

        # --- 2. Koli adedi ----------------------------------------------------
        pkg_tot, ok = QInputDialog.getInt(
            self, "Koli Adedi", "Kaç koli çıkacak?", 1, 1
        )
        if not ok:
            return

        order_id  = self.current_order["order_id"]
        order_no  = self.current_order["order_no"]
        trip_date = date.today().isoformat()          # ★ tek noktadan üret

        # --- 3. Logo başlığı ---------------------------------------------------
        hdr = fetch_order_header(order_no)
        if not hdr:
            QMessageBox.warning(self, "Logo", "Sipariş başlığı okunamadı")
            return

        # Use transaction for all database operations
        try:
            with transaction_scope() as conn:
                cursor = conn.cursor()
                
                # ------------------------------------------------------------ 3-A
                invoice_no = fetch_invoice_no(order_no)
                inv_root   = invoice_no.split("-K")[0] if invoice_no else None

                # Create or update shipment header
                upsert_header(
                    order_no, trip_date, pkg_tot,
                    customer_code=hdr.get("cari_kodu") or "",
                    customer_name=hdr.get("cari_adi", "")[:60],
                    region=f"{hdr.get('genexp2','')} - {hdr.get('genexp3','')}".strip(" -"),
                    address1=hdr.get("adres", "")[:128],
                    invoice_root=inv_root,
                    conn=conn  # Pass transaction connection
                )

                # Get header info with transaction connection
                cursor.execute(
                    "SELECT id, pkgs_total FROM shipment_header "
                    "WHERE order_no=? AND trip_date=?", 
                    order_no, trip_date
                )
                cur = cursor.fetchone()
                if cur:
                    existing_total = cur.pkgs_total
                    trip_id = cur.id
                    
                    # Update count if different
                    if existing_total != pkg_tot:
                        cursor.execute(
                            "UPDATE shipment_header SET pkgs_total=? "
                            "WHERE id=?",
                            pkg_tot, trip_id
                        )
                        
                        # If reducing, delete excess package records
                        if pkg_tot < existing_total:
                            cursor.execute(
                                "DELETE FROM shipment_loaded "
                                "WHERE trip_id = ? AND pkg_no > ?",
                                trip_id, pkg_tot
                            )
                else:
                    raise Exception("Failed to create/update shipment header")

                # ------------------------------------------------------------ 3-B
                # Create package records
                for k in range(1, pkg_tot + 1):
                    cursor.execute(
                        """
                        MERGE dbo.shipment_loaded AS tgt
                        USING (SELECT ? AS trip_id, ? AS pkg_no) src
                        ON tgt.trip_id = src.trip_id AND tgt.pkg_no = src.pkg_no
                        WHEN NOT MATCHED THEN
                            INSERT (trip_id, pkg_no, loaded)
                            VALUES (src.trip_id, src.pkg_no, 0);
                        """,
                        trip_id, k
                    )

                # ------------------------------------------------------------ 3-C
                # Process backorders and shipment lines
                for ln in self.lines:
                    code      = ln["item_code"]
                    wh        = ln["warehouse_id"]
                    ordered   = ln["qty_ordered"]
                    sent_qty  = self.sent.get(code, 0)
                    missing   = ordered - sent_qty

                    if sent_qty:
                        bo.add_shipment(
                            order_no, trip_date, code,
                            warehouse_id=wh,
                            invoiced_qty=ordered,
                            qty_delta=sent_qty,
                            conn=conn  # Pass transaction connection
                        )
                    if missing > 0:
                        bo.insert_backorder(
                            order_no, ln["line_id"], wh, code, missing,
                            conn=conn  # Pass transaction connection
                        )

                # ------------------------------------------------------------ 3-D
                # Update Logo order status
                ficheno = hdr.get("ficheno", "")
                genexp5_text = f"Sipariş No: {ficheno}" if ficheno else ""
                
                cursor.execute(
                    "UPDATE LG_025_ORFICHE SET STATUS = 4, GENEXP4 = ?, GENEXP5 = ? "
                    "WHERE LOGICALREF = ?",
                    f"PAKET SAYISI : {pkg_tot}", genexp5_text, order_id
                )
                
                # Remove from queue
                cursor.execute("DELETE FROM WMS_PICKQUEUE WHERE ORDER_ID = ?", order_id)
                
                # Transaction will auto-commit on success
                toast("STATUS 4 verildi", order_no)

            # --- 4. UI temizlik / yenileme --------------------------------
            self.lines.clear()
            self.sent.clear()
            self.current_order = None
            self._barcode_cache.clear()  # Thread-safe cache temizle
            self._warehouse_set.clear()
            self.tbl.setRowCount(0)
            self.refresh_orders()

            QMessageBox.information(
                self, "Tamam",
                f"{order_no} işlemi bitti."
            )

        except Exception as exc:
            logger.exception("finish_order")
            QMessageBox.critical(self, "Tamamlama Hatası", str(exc))
    
    # =========================================================================
    # YENİ ÖZELLİKLER - MANTALİTEYİ BOZMADAN EKLENMİŞTİR
    # =========================================================================
    
    def show_table_context_menu(self, position):
        """Tablo sağ tık menüsü."""
        item = self.tbl.itemAt(position)
        if not item or not self.lines:
            return
        
        row = item.row()
        if row >= len(self.lines):
            return
            
        line = self.lines[row]
        code = line["item_code"]
        
        menu = QMenu(self)
        
        # Manuel miktar girişi
        act_manual = QAction("📝 Manuel Miktar Gir", self)
        act_manual.triggered.connect(lambda: self.manual_quantity_input(row))
        menu.addAction(act_manual)
        
        # Stok bilgisi
        act_stock = QAction("📋 Stok Bilgisi", self)
        act_stock.triggered.connect(lambda: self.show_stock_info(code))
        menu.addAction(act_stock)
        
        # Raf konumu (zaten tabloda var ama detaylı bilgi)
        act_location = QAction("📍 Raf Detayları", self)
        act_location.triggered.connect(lambda: self.show_location_details(line))
        menu.addAction(act_location)
        
        menu.addSeparator()
        
        # Problem bildir
        act_problem = QAction("⚠️ Problem Bildir", self)
        act_problem.triggered.connect(lambda: self.report_problem(code))
        menu.addAction(act_problem)
        
        menu.exec_(self.tbl.mapToGlobal(position))
    
    def copy_selected_cell(self):
        """CTRL+C ile seçili hücreyi panoya kopyala."""
        current_item = self.tbl.currentItem()
        if current_item:
            from PyQt5.QtWidgets import QApplication
            text = current_item.text()
            
            # İkon varsa sadece kodu al
            if current_item.column() == 0 and " " in text:  # Stok kolonu
                text = text.split(" ", 1)[-1]  # İkonu kaldır
            
            QApplication.clipboard().setText(text)
            
            # Kullanıcıya feedback ver
            self.lbl_last_scan.setText(f"📋 Panoya kopyalandı: {text}")
            QTimer.singleShot(2000, lambda: self.lbl_last_scan.setText("🟢 Hazır - Barkod bekleniyor..."))
    
    def on_double_click_item(self, item):
        """Çift tıkla manuel miktar girişi."""
        if not item or not self.lines:
            return
        row = item.row()
        if row < len(self.lines):
            self.manual_quantity_input(row)
    
    def manual_quantity_input(self, row):
        """Manuel miktar girişi dialog."""
        if row >= len(self.lines):
            return
            
        line = self.lines[row]
        code = line["item_code"]
        current_sent = self.sent.get(code, 0)
        ordered = line["qty_ordered"]
        
        from PyQt5.QtWidgets import QInputDialog
        
        # Input dialog
        qty, ok = QInputDialog.getDouble(
            self, 
            "Manuel Miktar Girişi",
            f"Ürün: {code}\nSipariş: {ordered}\nMevcut: {current_sent}\n\nYeni miktar:",
            current_sent,
            0.0, 
            ordered + 10.0,  # Max biraz fazla ver
            2  # 2 decimal places
        )
        
        if ok and qty >= 0:
            # Thread-safe güncelleme
            with self._scan_lock:
                self.sent[code] = qty
                try:
                    # DB'yi güncelle
                    queue_inc(self.current_order["order_id"], code, qty - current_sent)
                    # UI'yi güncelle
                    self._populate_table()
                    self.update_progress()
                    # Log
                    log_activity(getpass.getuser(), "MANUAL_QTY", 
                               details=f"{code}: {current_sent} → {qty}",
                               order_no=self.current_order["order_no"],
                               item_code=code,
                               qty_scanned=qty - current_sent)
                    # Bilgi güncelle
                    self.lbl_last_scan.setText(f"✏️ MANUEL GİRİŞ: {code} ({qty} adet)")
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Miktar güncellenemedi: {e}")
    
    def show_stock_info(self, code):
        """Stok bilgisi popup."""
        try:
            from app.dao.logo import fetch_one, _t
            
            # Stok bilgilerini çek
            stock_query = f"""
                SELECT 
                    CODE, NAME, 
                    ONHAND, RESERVED, AVAILABLE,
                    UNIT1, UNIT2, UNIT3
                FROM {_t('ITEMS')} 
                WHERE CODE = ?
            """
            stock = fetch_one(stock_query, code)
            
            if stock:
                info_text = f"""
                📦 STOK BİLGİLERİ
                
                Kod: {stock['code']}
                Ad: {stock['name']}
                
                Eldeki: {stock['onhand']:.2f}
                Rezerve: {stock['reserved']:.2f} 
                Müsait: {stock['available']:.2f}
                
                Birimler: {stock['unit1']} / {stock['unit2']} / {stock['unit3']}
                """
            else:
                info_text = f"❌ {code} için stok bilgisi bulunamadı."
            
            QMessageBox.information(self, "Stok Bilgisi", info_text)
            
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Stok bilgisi alınamadı: {e}")
    
    def show_location_details(self, line):
        """Detaylı raf bilgisi."""
        info_text = f"""
        📍 RAF KONUM DETAYLARI
        
        Ürün: {line['item_code']}
        Depo: {line['warehouse_id']}
        Raf: {line.get('shelf_code', 'Belirtilmemiş')}
        
        Sipariş Miktarı: {line['qty_ordered']:.2f}
        Taranan: {self.sent.get(line['item_code'], 0):.2f}
        Kalan: {line['qty_ordered'] - self.sent.get(line['item_code'], 0):.2f}
        """
        
        QMessageBox.information(self, "Raf Detayları", info_text)
    
    def report_problem(self, code):
        """Problem raporlama."""
        from PyQt5.QtWidgets import QInputDialog
        
        problem, ok = QInputDialog.getText(
            self, 
            "Problem Bildir",
            f"Ürün: {code}\n\nSorunu açıklayın:",
            text="Ürün bulunamıyor / Hasar var / Diğer"
        )
        
        if ok and problem.strip():
            try:
                # Log olarak kaydet
                log_activity(
                    getpass.getuser(), 
                    "PROBLEM_REPORT",
                    details=f"{code}: {problem}",
                    order_no=self.current_order.get("order_no", ""),
                    item_code=code
                )
                QMessageBox.information(self, "Başarılı", "Problem raporu kaydedildi.")
                
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Problem kaydedilemedi: {e}")
    
    def update_progress(self):
        """Progress bar ve bilgileri güncelle."""
        if not self.lines:
            self.progress_bar.setVisible(False)
            return
            
        self.progress_bar.setVisible(True)
        total_items = len(self.lines)
        completed_items = sum(1 for line in self.lines 
                            if self.sent.get(line["item_code"], 0) >= line["qty_ordered"])
        
        self.progress_bar.setMaximum(total_items)
        self.progress_bar.setValue(completed_items)
        
        # Zaman hesaplama (basit)
        if hasattr(self, 'order_start_time') and self.order_start_time:
            from datetime import datetime, timedelta
            elapsed = datetime.now() - self.order_start_time
            
            if completed_items > 0:
                avg_time_per_item = elapsed.total_seconds() / completed_items
                remaining_items = total_items - completed_items
                estimated_remaining = timedelta(seconds=avg_time_per_item * remaining_items)
                
                elapsed_str = f"{elapsed.seconds // 60:02d}:{elapsed.seconds % 60:02d}"
                estimated_end = datetime.now() + estimated_remaining
                
                self.lbl_time_info.setText(f"Geçen süre: {elapsed_str}")
                self.lbl_estimated.setText(f"Tahmini bitiş: {estimated_end.strftime('%H:%M')}")
            else:
                self.lbl_time_info.setText(f"Geçen süre: {elapsed.seconds // 60:02d}:{elapsed.seconds % 60:02d}")
                self.lbl_estimated.setText("Tahmini bitiş: Hesaplanıyor...")
    
    def update_shift_stats(self):
        """Vardiya istatistiklerini güncelle."""
        try:
            from datetime import datetime, date
            from app.dao.logo import fetch_one, _t
            
            today = date.today()
            current_hour = datetime.now().hour
            
            # Bugün tamamlanan sipariş sayısı
            daily_query = f"""
                SELECT COUNT(*) as daily_count
                FROM {_t('ORFICHE')}
                WHERE STATUS = 4 
                  AND CAST(DATE_ AS DATE) = ?
            """
            daily_result = fetch_one(daily_query, today)
            daily_count = daily_result['daily_count'] if daily_result else 0
            
            # Son 1 saatte tamamlanan (daha mantıklı)
            hourly_query = f"""
                SELECT COUNT(*) as hourly_count
                FROM {_t('ORFICHE')}
                WHERE STATUS = 4 
                  AND DATE_ >= DATEADD(HOUR, -1, GETDATE())
            """
            hourly_result = fetch_one(hourly_query)
            hourly_count = hourly_result['hourly_count'] if hourly_result else 0
            
            self.lbl_shift_stats.setText(f"📅 Bugün: {daily_count} sipariş | ⏰ Son 1 saat: {hourly_count}")
            
        except Exception as e:
            self.lbl_shift_stats.setText("Vardiya bilgisi alınamadı")
    
    def keyPressEvent(self, event):
        """Klavye kısayolları."""
        from PyQt5.QtCore import Qt
        
        if event.key() == Qt.Key_F5:
            # F5: Yenile
            self.refresh_orders()
            self.update_shift_stats()
        elif event.key() == Qt.Key_F1:
            # F1: Yardım
            self.show_help_dialog()
        elif event.key() == Qt.Key_Escape:
            # ESC: Barkod kutusunu temizle ve focus ver
            self.entry.clear()
            self.entry.setFocus()
        elif event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_Plus:
                # Ctrl++ : Font büyüt
                current_font = self.font()
                current_font.setPointSize(current_font.pointSize() + 1)
                self.setFont(current_font)
            elif event.key() == Qt.Key_Minus:
                # Ctrl+- : Font küçült
                current_font = self.font()
                if current_font.pointSize() > 8:
                    current_font.setPointSize(current_font.pointSize() - 1)
                    self.setFont(current_font)
        else:
            super().keyPressEvent(event)
    
    def show_help_dialog(self):
        """Yardım penceresi."""
        help_text = """
        🔧 SCANNER YARDIM
        
        📋 Klavye Kısayolları:
        • F5: Sipariş listesini yenile
        • F1: Bu yardım penceresi
        • ESC: Barkod kutusunu temizle
        • Ctrl++: Yazı boyutunu büyüt
        • Ctrl+-: Yazı boyutunu küçült
        
        🖱️ Mouse İşlemleri:
        • Çift tık: Manuel miktar girişi
        • Sağ tık: İşlem menüsü
        
        📦 Barkod Formatları:
        • Direkt stok kodu: ABC123
        • Depo prefixi ile: D1-ABC123
        • Test barkodu: TEST-12345
        
        ℹ️ İpuçları:
        • Progress bar siparişin ilerlemesini gösterir
        • Yeşil satırlar tamamlanmış ürünleri işaret eder
        • Son taranan ürün altta gösterilir
        """
        
        QMessageBox.information(self, "Scanner Yardımı", help_text)
