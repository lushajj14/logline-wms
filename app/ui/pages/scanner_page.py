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
    QInputDialog
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
        top = QHBoxLayout()
        top.addWidget(QLabel("Sipariş:"))
        self.cmb_orders = QComboBox()
        self.cmb_orders.currentIndexChanged.connect(self.load_order)  # otomatik yükle
        top.addWidget(self.cmb_orders)

        self.btn_load = QPushButton("Yükle")
        self.btn_load.clicked.connect(self.load_order)
        self.btn_load.hide()  # talebe göre gizli kalsın
        top.addWidget(self.btn_load)
        top.addStretch()
        lay.addLayout(top)

        # --- Tablo ---
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Stok", "Ürün Adı", "İst", "Gönderilen", "Ambar", "Raf"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tbl)

        # --- Barkod girişi ---
        scan = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Barkod okutun → Enter")
        self.entry.returnPressed.connect(self.on_scan)
        scan.addWidget(self.entry)
        lay.addLayout(scan)

        # --- Tamamla butonu ---
        self.btn_done = QPushButton("Siparişi Tamamla")
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

            # ---- Renklendirme ------------------------------------
            if sent >= ordered and ordered > 0:          # tam + fazla
                color = QColor("#A5D6A7")                # yeşil
            elif sent == 0:
                color = QColor("#FFCDD2")                # kırmızı
            else:                                        # eksik (kısmi)
                color = QColor("#FFF59D")                # sarı

            for c in range(6):
                self.tbl.item(row, c).setBackground(color)
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

     
    # ---- Barkod / Kod okutuldu ----
    def on_scan(self) -> None:
        raw = self.entry.text().strip()
        self.entry.clear()
        
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
            
        # 3. Geçersiz karakterler (sadece alfanumerik + tire/alt çizgi/slash)
        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/")
        if not all(c.upper() in allowed_chars for c in raw):
            sound_manager.play_error()
            QMessageBox.warning(self, "Barkod", "Barkod geçersiz karakterler içeriyor!")
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
            if code_item and code_item.text() == item_code:
                # Gönderilen kolonunu güncelle
                sent_item = self.tbl.item(row, 3)
                if sent_item:
                    sent_item.setText(str(new_sent))
                
                # Renk güncelle
                ordered = float(self.tbl.item(row, 2).text())
                if new_sent >= ordered and ordered > 0:
                    color = QColor("#A5D6A7")  # yeşil
                elif new_sent == 0:
                    color = QColor("#FFCDD2")  # kırmızı
                else:
                    color = QColor("#FFF59D")  # sarı
                
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
