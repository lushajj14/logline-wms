"""BackordersPage – Eksik satırların listesi ve kapatma
====================================================
Tablo:
    * ID, Sipariş No, Stok Kodu, Eksik Adet, Ambar, Kayıt Tarihi
İşlevler:
    * Yenile ↻  – list_pending()
    * Seçiliyi Tamamla ✓ – mark_fulfilled(id)  ➜ UI & DB güncellenir
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QSplitter, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl
from pathlib import Path
from typing import Dict, List
import sys

from app.backorder import list_pending, mark_fulfilled
from app.dao.logo import fetch_one, resolve_barcode_prefix
from app.settings import get as cfg

# Scanner'dan ses dosyaları için
BASE_DIR = Path(__file__).resolve().parents[3]
SOUND_DIR = BASE_DIR / "sounds"

def _load_wav(name: str) -> QSoundEffect:
    s = QSoundEffect()
    s.setSource(QUrl.fromLocalFile(str(SOUND_DIR / name)))
    s.setVolume(0.9)
    return s

# Ses efektleri
snd_ok = _load_wav("ding.wav")
snd_err = _load_wav("error.wav")

def barcode_xref_lookup(barcode: str, warehouse_id: str | None = None):
    """Scanner'dan kopyalanan barkod lookup fonksiyonu"""
    try:
        if warehouse_id is not None:
            row = fetch_one(
                "SELECT TOP 1 item_code, multiplier "
                "FROM barcode_xref WHERE barcode=? AND warehouse_id=?",
                barcode, warehouse_id
            )
        else:
            row = fetch_one(
                "SELECT TOP 1 item_code, multiplier "
                "FROM barcode_xref WHERE barcode=?", barcode
            )
        if row:
            return row["item_code"], row.get("multiplier", 1)
    except Exception as exc:
        print(f"[barcode_xref_lookup] DB error: {exc}")
    return None, None


class BackordersPage(QWidget):
    """Bekleyen back‑order satırlarını sipariş bazlı hierarşik yapıda gösterir."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        
        # Depo prefix map'ini settings'den al
        self.WH_PREFIX_MAP = cfg("scanner.prefixes", {
            "D1-": "0",  # Merkez
            "D3-": "1",  # EGT  
            "D4-": "2",  # OTOİS
            "D5-": "3",  # ATAK
        })
            
        self.records_cache: list[dict] = []
        self.grouped_orders: Dict = {}
        self.selected_order: str | None = None
        self.selected_items: List[dict] = []
        self._warehouse_set: set = set()
        
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)  # Kenar boşluklarını daha da azalt
        lay.setSpacing(2)  # Widget'lar arası boşluğu minimize et
        
        # --- Kompakt başlık + toolbar aynı satırda ----------------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        title = QLabel("Back‑Order Sipariş Bazlı Görünüm")
        title.setStyleSheet("font-size:13px;font-weight:bold;padding:1px")
        header_layout.addWidget(title)
        
        header_layout.addStretch()  # Boşluk bırak
        
        # Toolbar butonları başlıkla aynı satırda
        self.btn_refresh = QPushButton("↻ Yenile")
        self.btn_refresh.setFixedHeight(22)  # Daha kompakt
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_done = QPushButton("✓ Seçiliyi Tamamla")
        self.btn_done.setFixedHeight(22)
        self.btn_done.clicked.connect(self.complete_selected)
        header_layout.addWidget(self.btn_refresh)
        header_layout.addWidget(self.btn_done)
        
        lay.addLayout(header_layout)

        # --- splitter: sol = sipariş ağacı, sağ = ürün detayları -------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Tam genişlik-yükseklik
        
        # Sol panel - Sipariş ağacı
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(2, 2, 2, 2)  # Minimal kenar boşlukları
        left_layout.setSpacing(1)  # Minimal spacing
        
        orders_label = QLabel("📋 Siparişler")
        orders_label.setStyleSheet("font-weight:bold;font-size:11px;padding:1px")
        left_layout.addWidget(orders_label)
        
        # Filtreleme alanı
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(3)
        filter_label = QLabel("🔍 Filtre:")
        filter_label.setFixedWidth(45)
        filter_label.setStyleSheet("font-size:10px")
        self.filter_entry = QLineEdit()
        self.filter_entry.setFixedHeight(20)
        self.filter_entry.setPlaceholderText("Sipariş No ile filtrele...")
        self.filter_entry.textChanged.connect(self.filter_orders)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_entry)
        left_layout.addLayout(filter_layout)
        
        # Siparişler tablosu (QTreeWidget yerine QTableWidget)
        self.tbl_orders = QTableWidget()
        self.tbl_orders.setColumnCount(4)
        self.tbl_orders.setHorizontalHeaderLabels(["Sipariş No", "Müşteri", "Depo", "Toplam"])
        self.tbl_orders.itemClicked.connect(self.on_order_selected)
        
        # Çift sıralama için değişkenler
        self.sort_history = []  # [(column, order), ...]
        
        # Header tıklama event'ini yakala
        header = self.tbl_orders.horizontalHeader()
        header.sectionClicked.connect(self.on_header_clicked)
        
        # Varsayılan sıralama KAPALI (manuel kontrol edeceğiz)
        self.tbl_orders.setSortingEnabled(False)
        self.tbl_orders.setAlternatingRowColors(True)
        self.tbl_orders.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_orders.verticalHeader().hide()  # Satır numaralarını gizle
        
        # Kolon genişliklerini ayarla
        header = self.tbl_orders.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Sipariş No
        header.setSectionResizeMode(1, QHeaderView.Stretch)      # Müşteri - esnek
        header.setSectionResizeMode(2, QHeaderView.Fixed)        # Depo - sabit
        header.setSectionResizeMode(3, QHeaderView.Fixed)        # Toplam - sabit
        
        self.tbl_orders.setColumnWidth(0, 120)  # Sipariş No
        self.tbl_orders.setColumnWidth(2, 50)   # Depo  
        self.tbl_orders.setColumnWidth(3, 50)   # Toplam
        
        # Tablonun yükseklik politikasını ayarla
        self.tbl_orders.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_layout.addWidget(self.tbl_orders)
        
        # Sağ panel - Seçili sipariş detayları
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(2, 2, 2, 2)  # Minimal kenar boşlukları
        right_layout.setSpacing(1)  # Minimal spacing
        
        self.lbl_selected = QLabel("Sipariş seçin...")
        self.lbl_selected.setStyleSheet("font-weight:bold; color:#666; font-size:11px; padding:1px")
        right_layout.addWidget(self.lbl_selected)
        
        # Ürün tablosu
        self.tbl_items = QTableWidget(0, 5)
        self.tbl_items.setHorizontalHeaderLabels([
            "Stok Kodu", "Ürün Adı", "Eksik", "Depo", "ID"
        ])
        # Manuel kolon genişlikleri
        header = self.tbl_items.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Stok Kodu
        header.setSectionResizeMode(1, QHeaderView.Stretch)      # Ürün Adı - esnek
        header.setSectionResizeMode(2, QHeaderView.Fixed)        # Eksik - sabit
        header.setSectionResizeMode(3, QHeaderView.Fixed)        # Depo - sabit
        header.setSectionResizeMode(4, QHeaderView.Fixed)        # ID - sabit
        
        self.tbl_items.setColumnWidth(0, 120)  # Stok Kodu
        self.tbl_items.setColumnWidth(2, 60)   # Eksik
        self.tbl_items.setColumnWidth(3, 50)   # Depo
        self.tbl_items.setColumnWidth(4, 50)   # ID
        
        self.tbl_items.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_items.setAlternatingRowColors(True)
        # Satır yüksekliğini azalt
        self.tbl_items.verticalHeader().setDefaultSectionSize(20)
        self.tbl_items.verticalHeader().hide()  # Satır numaralarını gizle
        # Tablonun yükseklik politikasını ayarla - mümkün olduğunca genişlesin
        self.tbl_items.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        right_layout.addWidget(self.tbl_items)
        
        # Barkod girişi - en altta kompakt
        barcode_layout = QHBoxLayout()
        barcode_layout.setSpacing(3)
        barcode_label = QLabel("🔍 Barkod:")
        barcode_label.setFixedWidth(55)
        barcode_label.setStyleSheet("font-size:10px")
        barcode_layout.addWidget(barcode_label)
        self.entry_barcode = QLineEdit()
        self.entry_barcode.setFixedHeight(22)  # Kompakt
        self.entry_barcode.setPlaceholderText("Barkod okutun → Enter")
        self.entry_barcode.returnPressed.connect(self.on_barcode_scan)
        barcode_layout.addWidget(self.entry_barcode)
        right_layout.addLayout(barcode_layout)
        
        # Splitter'a panelleri ekle
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])  # Sol:400px (daha geniş), Sağ:600px - siparişler bölümü daha geniş
        splitter.setStretchFactor(0, 1)  # Sol panel de esnek olsun
        splitter.setStretchFactor(1, 2)  # Sağ panel 2x daha esnek
        
        lay.addWidget(splitter)  # Splitter ana layout'un tamamını kaplasın

    # ------------------------------------------------------------------
    def group_orders(self, records: List[dict]) -> Dict:
        """Düz backorder listesini sipariş bazında grupla"""
        grouped = {}
        for rec in records:
            order_no = rec["order_no"]
            if order_no not in grouped:
                # Depo bilgisini direkt olarak göster - gereksiz prefix ekleme
                warehouse_id = str(rec.get("warehouse_id", ""))
                
                grouped[order_no] = {
                    "customer": rec.get("customer_name", "Bilinmiyor"),
                    "warehouse_display": warehouse_id,  # Sadece warehouse_id'yi göster
                    "items": [],
                    "total_qty": 0
                }
            grouped[order_no]["items"].append(rec)
            grouped[order_no]["total_qty"] += rec["qty_missing"]
        return grouped

    def populate_orders(self):
        """Siparişler tablosunu doldur"""
        self.tbl_orders.setRowCount(0)
        self.all_orders_data = []  # Filtreleme için tüm veriyi sakla
        
        for order_no, order_data in self.grouped_orders.items():
            # Müşteri adını kısalt
            customer_name = order_data["customer"][:25]
            if len(order_data["customer"]) > 25:
                customer_name += "..."
            
            # Veriyi kaydet (filtreleme için)
            order_row_data = {
                "order_no": str(order_no),
                "customer": str(customer_name),
                "warehouse_display": str(order_data["warehouse_display"]),
                "total_qty": int(order_data["total_qty"])
            }
            self.all_orders_data.append(order_row_data)
        
        # Filtreleme uygula
        self.filter_orders()

    def filter_orders(self):
        """Sipariş listesini filtrele"""
        filter_text = self.filter_entry.text().lower()
        
        # Filtrelenmiş veriyi tabloya yükle
        filtered_data = []
        if not filter_text:
            filtered_data = self.all_orders_data
        else:
            filtered_data = [
                order for order in self.all_orders_data 
                if filter_text in order["order_no"].lower()
            ]
        
        # Tabloyu temizle ve yeniden doldur
        self.tbl_orders.setRowCount(len(filtered_data))
        self.tbl_orders.setSortingEnabled(False)  # Sıralama deaktif ederek veri ekle
        
        for i, order_data in enumerate(filtered_data):
            # Hücreler
            cells = [
                order_data["order_no"],
                order_data["customer"], 
                order_data["warehouse_display"],
                str(order_data["total_qty"])
            ]
            
            for j, cell_value in enumerate(cells):
                item = QTableWidgetItem(str(cell_value))
                # Sipariş no'yu UserRole'de sakla
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, order_data["order_no"])
                self.tbl_orders.setItem(i, j, item)
        
        self.tbl_orders.setSortingEnabled(True)  # Sıralama tekrar aktif et

    def on_header_clicked(self, logical_index: int):
        """Header'a tıklandığında çift sıralama uygula"""
        # Mevcut sıralama geçmişini kontrol et
        existing_index = -1
        for i, (col, order) in enumerate(self.sort_history):
            if col == logical_index:
                existing_index = i
                break
        
        if existing_index >= 0:
            # Bu kolona daha önce tıklanmış - sıralama yönünü değiştir
            current_order = self.sort_history[existing_index][1]
            new_order = Qt.SortOrder.DescendingOrder if current_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.sort_history[existing_index] = (logical_index, new_order)
        else:
            # Yeni kolon - en sona ekle
            self.sort_history.append((logical_index, Qt.SortOrder.AscendingOrder))
        
        # Maksimum 3 kolon sıralama (çok karmaşık olmasın)
        if len(self.sort_history) > 3:
            self.sort_history.pop(0)
        
        # Çift sıralama uygula
        self.apply_multi_sort()
        
        # Sıralama bilgisini göster
        self.show_sort_info()

    def apply_multi_sort(self):
        """Çift/üçlü sıralama uygula - doğru hiyerarşik sıralama"""
        if not self.sort_history:
            return
            
        # Mevcut filtrelenmiş veriyi al
        current_data = []
        for i in range(self.tbl_orders.rowCount()):
            row_data = {}
            for j in range(self.tbl_orders.columnCount()):
                item = self.tbl_orders.item(i, j)
                if item:
                    if j == 0:  # Sipariş No
                        row_data['order_no'] = item.text()
                        row_data['user_data'] = item.data(Qt.ItemDataRole.UserRole)
                    elif j == 1:  # Müşteri
                        row_data['customer'] = item.text()
                    elif j == 2:  # Depo
                        row_data['warehouse'] = item.text()
                    elif j == 3:  # Toplam
                        row_data['total'] = int(item.text())
            current_data.append(row_data)
        
        # Çok seviyeli sıralama key'i oluştur
        def multi_sort_key(row):
            """Her sıralama seviyesi için ayrı key döner"""
            keys = []
            
            # Sıralama geçmişini doğru sırayla işle (ilk tıklanan en önemli)
            for col, order in self.sort_history:
                if col == 0:  # Sipariş No
                    value = row['order_no']
                elif col == 1:  # Müşteri  
                    value = row['customer']
                elif col == 2:  # Depo
                    value = row['warehouse']
                elif col == 3:  # Toplam
                    value = row['total']
                else:
                    value = ""
                
                # Azalan sıralama için negatif (sadece sayısal)
                if order == Qt.SortOrder.DescendingOrder:
                    if isinstance(value, int):
                        keys.append(-value)
                    else:
                        # String'ler için reverse key
                        keys.append('~' + value)  # ASCII'de ~ en büyük karakter
                else:
                    keys.append(value)
            
            return tuple(keys)
        
        # Sıralama uygula
        sorted_data = sorted(current_data, key=multi_sort_key)
        
        # Tabloyu güncelle
        self.tbl_orders.setSortingEnabled(False)
        for i, row_data in enumerate(sorted_data):
            # Sipariş No
            item0 = QTableWidgetItem(row_data['order_no'])
            item0.setData(Qt.ItemDataRole.UserRole, row_data['user_data'])
            self.tbl_orders.setItem(i, 0, item0)
            
            # Müşteri
            item1 = QTableWidgetItem(row_data['customer'])
            self.tbl_orders.setItem(i, 1, item1)
            
            # Depo  
            item2 = QTableWidgetItem(row_data['warehouse'])
            self.tbl_orders.setItem(i, 2, item2)
            
            # Toplam
            item3 = QTableWidgetItem(str(row_data['total']))
            self.tbl_orders.setItem(i, 3, item3)
        
        self.tbl_orders.setSortingEnabled(False)  # Manuel kontrol için kapalı tut

    def show_sort_info(self):
        """Aktif sıralama bilgisini göster"""
        if not self.sort_history:
            return
            
        col_names = ["Sipariş No", "Müşteri", "Depo", "Toplam"]
        sort_info = []
        
        for i, (col, order) in enumerate(self.sort_history):
            direction = "↑" if order == Qt.SortOrder.AscendingOrder else "↓"
            priority = f"{i+1}." if len(self.sort_history) > 1 else ""
            sort_info.append(f"{priority}{col_names[col]}{direction}")
        
        # Filtreleme alanının placeholder'ını güncelle
        sort_text = " → ".join(sort_info)
        current_filter = self.filter_entry.text()
        if not current_filter:
            self.filter_entry.setPlaceholderText(f"Filtre... | Sıralama: {sort_text}")

    def on_order_selected(self, item: QTableWidgetItem):
        """Sipariş seçildiğinde detayları göster"""
        if not item:
            return
            
        # Sipariş no'yu UserRole'den al (sadece 0. kolonda saklanıyor)
        order_no = None
        if item.column() == 0:
            order_no = item.data(Qt.ItemDataRole.UserRole)
        else:
            # Diğer kolonlarda ise aynı satırın 0. kolonundaki veriyi al
            order_item = self.tbl_orders.item(item.row(), 0)
            if order_item:
                order_no = order_item.data(Qt.ItemDataRole.UserRole)
        
        if not order_no:
            return
            
        self.selected_order = order_no
        self.selected_items = self.grouped_orders[order_no]["items"]
        
        # Warehouse set'ini güncelle
        self._warehouse_set = {item["warehouse_id"] for item in self.selected_items}
        
        # Label'ı güncelle
        customer = self.grouped_orders[order_no]["customer"]
        self.lbl_selected.setText(f"📦 {order_no} - {customer}")
        
        # Tablo'yu doldur
        self.populate_items_table()
        
        # Barkod girişine odak ver
        QTimer.singleShot(0, self.entry_barcode.setFocus)

    def populate_items_table(self):
        """Seçili siparişin ürünlerini tabloda göster"""
        self.tbl_items.setRowCount(0)
        
        for i, item in enumerate(self.selected_items):
            self.tbl_items.insertRow(i)
            
            # Hücreler
            cells = [
                item["item_code"],
                item.get("item_name", ""),
                str(item["qty_missing"]),
                item["warehouse_id"],
                str(item["id"])
            ]
            
            for j, cell_value in enumerate(cells):
                cell = QTableWidgetItem(str(cell_value))
                self.tbl_items.setItem(i, j, cell)

    # ------------------------------------------------------------------
    def refresh(self):
        """DB'den bekleyenleri çek ve hierarşik yapıyı güncelle."""
        try:
            recs = list_pending()
        except Exception as exc:
            QMessageBox.critical(self, "DB Hatası", str(exc))
            return

        self.records_cache = recs
        self.grouped_orders = self.group_orders(recs)
        self.populate_orders()  # populate_tree yerine populate_orders
        
        # Seçimi temizle
        self.selected_order = None
        self.selected_items = []
        self.lbl_selected.setText("Sipariş seçin...")
        self.tbl_items.setRowCount(0)

    # ------------------------------------------------------------------
    def _infer_wh_from_prefix(self, barcode: str) -> str | None:
        """Scanner'dan kopyalanan depo prefix fonksiyonu"""
        for pfx, wh in self.WH_PREFIX_MAP.items():
            if barcode.upper().startswith(pfx):
                return wh
        return None

    def _find_matching_item(self, raw: str) -> dict | None:
        """Scanner mantığını kullanarak ürün bul"""
        if not self.selected_items:
            return None
            
        # 1) Direkt stok kodu eşleşmesi
        matched_item = next(
            (item for item in self.selected_items 
             if item["item_code"].lower() == raw.lower()),
            None
        )
        
        # 2) Depo prefix çözümü  
        if not matched_item:
            for item in self.selected_items:
                code = resolve_barcode_prefix(raw, item["warehouse_id"])
                if code and code == item["item_code"]:
                    matched_item = item
                    break
        
        # 3) barcode_xref tablosu
        if not matched_item:
            for wh_try in self._warehouse_set:
                itm_code, mult = barcode_xref_lookup(raw, wh_try)
                if itm_code:
                    matched_item = next(
                        (item for item in self.selected_items
                         if item["item_code"] == itm_code
                         and item["warehouse_id"] == wh_try),
                        None
                    )
                    if matched_item:
                        break
        
        # 4) Karmaşık barkod formatı (44-1800/A-T10009-24-K10-1)
        if not matched_item and "/" in raw and "-K" in raw:
            stock_part = raw.split("/")[0].strip()
            for wh_try in self._warehouse_set:
                itm_code, mult = barcode_xref_lookup(stock_part, wh_try)
                if itm_code:
                    matched_item = next(
                        (item for item in self.selected_items
                         if item["item_code"] == itm_code
                         and item["warehouse_id"] == wh_try),
                        None
                    )
                    if matched_item:
                        break
        
        return matched_item

    def on_barcode_scan(self):
        """Barkod okutulduğunda çalışır"""
        raw = self.entry_barcode.text().strip()
        self.entry_barcode.clear()
        
        # Focus'u geri ver
        QTimer.singleShot(0, self.entry_barcode.setFocus)
        
        # Kontroller
        if not raw:
            return
        if len(raw) < 2:
            snd_err.play()
            QMessageBox.warning(self, "Barkod", "Barkod çok kısa!")
            return
        if not self.selected_order:
            snd_err.play()
            QMessageBox.warning(self, "Sipariş", "Önce sipariş seçin!")
            return
        
        # Geçersiz karakterler kontrolü - Logo stok kodları için genişletildi
        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/.+ ")
        if not all(c.upper() in allowed_chars for c in raw):
            invalid_chars = [c for c in raw if c.upper() not in allowed_chars]
            snd_err.play()
            QMessageBox.warning(self, "Barkod", f"Geçersiz karakterler: {invalid_chars}")
            return
        
        # Ürün ara
        matched_item = self._find_matching_item(raw)
        if not matched_item:
            snd_err.play()
            QMessageBox.warning(self, "Barkod", f"'{raw}' bu siparişte bulunamadı!")
            return
        
        # Başarılı eşleşme
        snd_ok.play()
        self.process_scanned_item(matched_item)

    def process_scanned_item(self, item: dict):
        """Okutulan ürünü işle - 1 adet düş, 0 olursa tamamla"""
        item_id = item["id"]
        current_qty = item["qty_missing"]
        
        if current_qty <= 1:
            # Son adet - direkt tamamla
            try:
                mark_fulfilled(item_id)
                # Sessizce tamamla - uyarı verme
                self._smart_refresh_after_item_completion(item_id)
            except Exception as exc:
                QMessageBox.critical(self, "Hata", f"Tamamlama hatası: {exc}")
        else:
            # Adeti 1 azalt (SQL UPDATE)
            try:
                from app.dao.logo import exec_sql
                exec_sql(
                    "UPDATE backorders SET qty_missing = qty_missing - 1 WHERE id = ?",
                    item_id
                )
                # Sessizce güncelle - uyarı verme
                self._smart_refresh_after_item_update(item_id, current_qty - 1)
            except Exception as exc:
                QMessageBox.critical(self, "Hata", f"Güncelleme hatası: {exc}")

    def _smart_refresh_after_item_completion(self, completed_item_id: int):
        """Bir item tamamlandıktan sonra akıllı yenileme"""
        # Tamamlanan item'ı selected_items'dan çıkar
        self.selected_items = [item for item in self.selected_items if item["id"] != completed_item_id]
        
        # Eğer bu siparişte hiç item kalmadıysa sipariş listesini yenile
        if not self.selected_items:
            QMessageBox.information(self, "Sipariş Tamamlandı", 
                                  f"'{self.selected_order}' siparişindeki tüm backorder'lar tamamlandı!")
            self.refresh()  # Tam yenileme - sipariş listesi güncellenir
        else:
            # Sadece item tablosunu güncelle, sipariş seçili kalsın
            self.populate_items_table()
            # Sipariş ağacındaki toplam sayıyı da güncelle
            self._update_order_total_in_tree()

    def _smart_refresh_after_item_update(self, updated_item_id: int, new_qty: int):
        """Bir item'ın adeti azaltıldıktan sonra akıllı yenileme"""
        # Selected_items'da quantity'yi güncelle
        for item in self.selected_items:
            if item["id"] == updated_item_id:
                item["qty_missing"] = new_qty
                break
        
        # Sadece item tablosunu güncelle, sipariş seçili kalsın
        self.populate_items_table()
        # Sipariş ağacındaki toplam sayıyı da güncelle
        self._update_order_total_in_tree()

    def _update_order_total_in_tree(self):
        """Mevcut seçili siparişin toplam adetini tabloda güncelle"""
        if not self.selected_order:
            return
            
        # Yeni toplam hesapla
        new_total = sum(item["qty_missing"] for item in self.selected_items)
        
        # Tabloda bu siparişi bul ve güncelle
        for i in range(self.tbl_orders.rowCount()):
            order_item = self.tbl_orders.item(i, 0)  # Sipariş No kolonu
            if order_item:
                order_no = order_item.data(Qt.ItemDataRole.UserRole)
                if order_no == self.selected_order:
                    # Toplam kolonu güncelle
                    total_item = self.tbl_orders.item(i, 3)
                    if total_item:
                        total_item.setText(str(new_total))
                    break

    # ------------------------------------------------------------------
    def complete_selected(self):
        """Seçili siparişteki tüm ürünleri tamamla"""
        if not self.selected_order:
            QMessageBox.information(self, "Bilgi", "Önce sipariş seçin.")
            return

        rows = {idx.row() for idx in self.tbl_items.selectedIndexes()}
        if not rows:
            QMessageBox.information(self, "Bilgi", "Önce ürün seçin.")
            return

        ok = 0
        fail = 0
        completed_item_ids = []
        
        for row in rows:
            item = self.selected_items[row]
            try:
                mark_fulfilled(item["id"])
                completed_item_ids.append(item["id"])
                ok += 1
            except Exception as exc:
                fail += 1
                QMessageBox.warning(self, "Hata", f"{item['item_code']} : {exc}")
        
        # Tamamlanan item'ları listeden çıkar
        if completed_item_ids:
            self.selected_items = [item for item in self.selected_items 
                                 if item["id"] not in completed_item_ids]
        
        # Eğer bu siparişte hiç item kalmadıysa sipariş listesini yenile
        if not self.selected_items:
            QMessageBox.information(self, "Tamamlandı", 
                                  f"{ok} ürün tamamlandı. Sipariş tamamen bitti!")
            self.refresh()  # Tam yenileme - sipariş listesi güncellenir
        else:
            # Sadece item tablosunu güncelle
            self.populate_items_table()
            self._update_order_total_in_tree()
            QMessageBox.information(self, "Tamamlandı", 
                                  f"{ok} ürün tamamlandı. {(''+str(fail)+' hata.') if fail else ''}")
