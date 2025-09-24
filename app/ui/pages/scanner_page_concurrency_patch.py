"""
Scanner Page Concurrency Improvements
=====================================
This file contains replacement methods for scanner_page.py that implement
proper concurrency control using atomic operations and application-level locks.

These methods should replace the existing ones in scanner_page.py for full
concurrency protection when multiple users are scanning simultaneously.
"""
from __future__ import annotations

import logging
import getpass
from typing import Dict
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

# Import atomic operations
from app.dao.atomic_scanner import atomic_scan_increment, get_fresh_queue_state, AtomicScanResult
from app.dao.atomic_completion import atomic_complete_order, check_order_completion_status, OrderCompletionResult
from app.dao.logo import log_activity
from app.utils.sound_manager import get_sound_manager
from app import toast

logger = logging.getLogger(__name__)
sound_manager = get_sound_manager()

def enhanced_on_scan(self) -> None:
    """
    Enhanced scanning method with full concurrency protection.
    Replace the existing on_scan method in scanner_page.py with this implementation.
    """
    raw = self.entry.text().strip()
    self.entry.clear()
    
    # Focus'u geri ver (kritik!)
    QTimer.singleShot(0, self.entry.setFocus)
    
    # ──────────────────────────────────────────────
    # TEMEL KONTROLLER (Değişmez)
    # ──────────────────────────────────────────────
    
    # 1. Boş veya çok kısa barkod
    if not raw or len(raw) < 2:
        if len(raw) < 2:
            sound_manager.play_error()
            QMessageBox.warning(self, "Barkod", "Barkod çok kısa!")
        return
    
    # 2. Sipariş seçili mi?
    if not self.current_order:
        sound_manager.play_error()
        QMessageBox.warning(self, "Sipariş", "Önce sipariş seçin!")
        return
    
    # 3. Geçersiz karakterler kontrolü
    allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/.+ ")
    invalid_chars = [c for c in raw if c.upper() not in allowed_chars]
    if invalid_chars:
        sound_manager.play_error()
        QMessageBox.warning(self, "Barkod", f"Barkod geçersiz karakterler içeriyor: {', '.join(set(invalid_chars))}\nBarkod: {raw}")
        return
    
    # 4. Depo prefix kontrolü
    detected_wh = self._infer_wh_from_prefix(raw)
    if detected_wh and int(detected_wh) not in self._warehouse_set:
        sound_manager.play_error()
        QMessageBox.warning(self, "Depo Hatası", 
                          f"Bu barkod farklı depo için (Depo: {detected_wh})!\nBu siparişin depoları: {', '.join(self._warehouse_set)}")
        return

    # ──────────────────────────────────────────────
    # GELİŞTİRİLMİŞ ATOMIK SCAN İŞLEMİ
    # ──────────────────────────────────────────────
    
    try:
        # Barcode eşleştirme (local işlem)
        matched_line, qty_inc = self._find_matching_line(raw)
        
        if not matched_line:
            sound_manager.play_error()
            QMessageBox.warning(self, "Barkod / Kod", f"'{raw}' bu siparişte eşleşmedi!\n\nBu barkod:\n• Stok kodu değil\n• Depo prefix'i yanlış\n• barcode_xref'te yok")
            try:
                log_activity(getpass.getuser(), "INVALID_SCAN",
                             details=raw, order_no=self.current_order["order_no"])
            except:
                pass
            return
        
        code = matched_line["item_code"]
        ordered = float(matched_line["qty_ordered"])
        qty_inc = float(qty_inc) if qty_inc else 1.0
        over_tol = float(getattr(self, '_over_tol', 0) or 0)
        
        # ✅ ATOMIK SCAN OPERASYONU - Race condition korumalı
        scan_result: AtomicScanResult = atomic_scan_increment(
            order_id=self.current_order["order_id"],
            item_code=code,
            qty_increment=qty_inc,
            qty_ordered=ordered,
            over_scan_tolerance=over_tol
        )
        
        if not scan_result.success:
            sound_manager.play_error()
            
            if scan_result.was_over_limit:
                QMessageBox.warning(
                    self, "Fazla Adet",
                    f"{code} için sipariş adedi {ordered}; {scan_result.message}"
                )
                try:
                    log_activity(getpass.getuser(), "OVER_SCAN",
                                 details=f"{code} / Giriş:{raw}",
                                 order_no=self.current_order["order_no"],
                                 item_code=code,
                                 qty_ordered=ordered,
                                 qty_scanned=scan_result.current_db_qty + qty_inc,
                                 warehouse_id=matched_line["warehouse_id"])
                except:
                    pass
            else:
                QMessageBox.critical(self, "Tarama Hatası", scan_result.message)
            
            return
        
        # ✅ UI VE LOCAL STATE GÜNCELLEMESİ
        # Database'den fresh değerleri al ve local state'i senkronize et
        fresh_quantities = get_fresh_queue_state(self.current_order["order_id"])
        
        # Sadece değişen ürün için hızlı güncelleme
        if code in fresh_quantities:
            self.sent[code] = fresh_quantities[code]
            self._update_single_row(code, fresh_quantities[code])
        
        # Progress ve UI güncelleme
        self.update_progress()
        
        # Başarı mesajı
        self.lbl_last_scan.setText(f"🎯 BAŞARILI: {code} (+{qty_inc} adet) → Toplam: {scan_result.new_qty_sent}")
        
        # Başarı sesi
        QTimer.singleShot(0, sound_manager.play_ok)
        
    except Exception as e:
        logger.error(f"Enhanced scan failed: {e}")
        sound_manager.play_error()
        QMessageBox.critical(self, "Sistem Hatası", f"Tarama işlemi başarısız: {str(e)}")


def enhanced_finish_order(self):
    """
    Enhanced order completion method with full concurrency protection.
    Replace the existing finish_order method in scanner_page.py with this implementation.
    """
    if not self.current_order:
        return
    
    order_id = self.current_order["order_id"]
    order_no = self.current_order["order_no"]
    
    # ──────────────────────────────────────────────
    # ÖN KONTROLLER
    # ──────────────────────────────────────────────
    
    # 1. Başka kullanıcı completion yapıyor mu kontrol et
    completion_status = check_order_completion_status(order_id)
    if completion_status:
        QMessageBox.warning(
            self, "Sipariş Kilidi",
            f"Bu sipariş şu anda başka bir kullanıcı tarafından tamamlanıyor.\n"
            f"Lütfen birkaç saniye bekleyip tekrar deneyin."
        )
        return
    
    # 2. Fresh database state ile eksik kontrolü
    fresh_quantities = get_fresh_queue_state(order_id)
    has_missing = any(
        fresh_quantities.get(ln["item_code"], 0) < ln["qty_ordered"] 
        for ln in self.lines
    )
    
    if has_missing:
        if QMessageBox.question(
            self, "Eksikler",
            "Eksikler var, yine de tamamla?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.No:
            return
    
    # ──────────────────────────────────────────────
    # PAKET SAYISI BELİRLEME
    # ──────────────────────────────────────────────
    
    # Paket geçmişini kontrol et
    previous_packages = self._get_previous_package_count(order_no)
    
    if previous_packages > 0:
        if has_missing:
            default_pkg = max(1, previous_packages - 1)
            message = f"Bu sipariş daha önce {previous_packages} koli olarak kapatılmıştı.\n" \
                     f"Eksikler tamamlandı. Şimdi kaç koli çıkacak?"
        else:
            default_pkg = previous_packages
            message = f"Bu sipariş daha önce {previous_packages} koli olarak kapatılmıştı.\n" \
                     f"Kaç koli çıkacak?"
    else:
        if has_missing:
            total_requested = sum(ln["qty_ordered"] for ln in self.lines)
            total_sent = sum(fresh_quantities.get(ln["item_code"], 0) for ln in self.lines)
            completion_ratio = total_sent / total_requested if total_requested > 0 else 1
            
            estimated_packages = max(1, int(5 * completion_ratio))  # 5 koli baseline
            default_pkg = estimated_packages
            message = f"Eksikli sipariş için tahmini koli sayısı: {estimated_packages}\nKaç koli çıkacak?"
        else:
            default_pkg = 3
            message = "Kaç koli çıkacak?"
    
    from PyQt5.QtWidgets import QInputDialog
    pkg_tot, ok = QInputDialog.getInt(
        self, "Koli Sayısı",
        message,
        default_pkg, 1, 50
    )
    
    if not ok:
        return
    
    # ──────────────────────────────────────────────
    # ATOMIK COMPLETION İŞLEMİ
    # ──────────────────────────────────────────────
    
    try:
        completion_result: OrderCompletionResult = atomic_complete_order(
            order_id=order_id,
            package_count=pkg_tot,
            lines_data=self.lines,
            sent_quantities=fresh_quantities,
            username=getpass.getuser()
        )
        
        if not completion_result.success:
            if completion_result.was_already_completed:
                QMessageBox.information(
                    self, "Sipariş Tamamlandı",
                    f"Bu sipariş başka bir kullanıcı tarafından tamamlandı: {completion_result.order_no}"
                )
                # UI'yi yenile
                self.refresh_orders()
                return
            else:
                QMessageBox.critical(
                    self, "Tamamlama Hatası",
                    completion_result.message
                )
                return
        
        # ✅ BAŞARILI TAMAMLAMA
        toast("STATUS 4 verildi", completion_result.order_no)
        
        # UI temizlik ve yenileme
        self.current_order = None
        self.lines = []
        self.sent = {}
        self.tbl.setRowCount(0)
        self.update_progress()
        
        # Sipariş listesini yenile
        self.refresh_orders()
        
        # Başarı mesajı
        QMessageBox.information(
            self, "Başarılı",
            f"Sipariş {completion_result.order_no} başarıyla tamamlandı!\n"
            f"Oluşturulan paket sayısı: {completion_result.packages_created}"
        )
        
    except Exception as e:
        logger.error(f"Enhanced order completion failed: {e}")
        QMessageBox.critical(self, "Sistem Hatası", f"Sipariş tamamlama hatası: {str(e)}")


def enhanced_load_order(self, order_dict: Dict):
    """
    Enhanced order loading with fresh database synchronization.
    Replace the existing load_order method with this implementation.
    """
    try:
        self.current_order = order_dict.copy()
        order_id = order_dict["order_id"]
        
        # Fetch order lines
        from app.dao.logo import fetch_order_lines
        self.lines = fetch_order_lines(order_id)
        
        if not self.lines:
            QMessageBox.warning(self, "Hata", "Sipariş satırları yüklenemedi!")
            return
        
        # ✅ FRESH DATABASE STATE İLE SENKRONIZASYON
        fresh_quantities = get_fresh_queue_state(order_id)
        self.sent = fresh_quantities.copy()
        
        # Cache temizle ve depo setini hazırla
        if hasattr(self, '_barcode_cache'):
            self._barcode_cache.clear()
        
        self._warehouse_set = {ln["warehouse_id"] for ln in self.lines}
        
        # UI tablosunu doldur
        self._populate_table()
        
        # Progress güncelle
        self.update_progress()
        
        # Order başlangıç zamanını işaretle
        from datetime import datetime
        self.order_start_time = datetime.now()
        
        # Vardiya istatistiklerini güncelle
        if hasattr(self, 'update_shift_stats'):
            self.update_shift_stats()
        
        # Son işlem bilgisini güncelle
        if hasattr(self, 'lbl_last_scan'):
            self.lbl_last_scan.setText(f"📋 Sipariş yüklendi: {self.current_order['order_no']} ({len(self.lines)} ürün)")
        
        logger.info(f"Order {order_dict['order_no']} loaded with fresh synchronization")
        
    except Exception as e:
        logger.error(f"Enhanced order loading failed: {e}")
        QMessageBox.critical(self, "Yükleme Hatası", f"Sipariş yüklenemedi: {str(e)}")


# ──────────────────────────────────────────────
# INSTALLATION INSTRUCTIONS
# ──────────────────────────────────────────────

INSTALLATION_GUIDE = """
KURULUM TALİMATLARI
===================

Bu concurrency iyileştirmelerini uygulamak için:

1. scanner_page.py dosyasında mevcut metodları değiştirin:
   
   a) on_scan metodunu enhanced_on_scan ile değiştirin (satır 1398 civarı)
   b) finish_order metodunu enhanced_finish_order ile değiştirin (satır 1593 civarı)
   c) load_order metodunu enhanced_load_order ile değiştirin (satır 1300 civarı)

2. Import'ları ekleyin (dosya başına):
   from app.dao.atomic_scanner import atomic_scan_increment, get_fresh_queue_state
   from app.dao.atomic_completion import atomic_complete_order, check_order_completion_status

3. Test edin:
   - Çoklu kullanıcı senaryosunda aynı sipariş üzerinde çalışın
   - Aynı ürünü eş zamanlı taratin
   - Sipariş tamamlamayı eş zamanlı deneyin

AVANTAJLAR:
- Race condition koruması
- Gerçek zamanlı senkronizasyon  
- Atomik operasyonlar
- Kullanıcı dostu hata mesajları
- Performans optimizasyonu

GERIYE UYUMLULUK:
- Mevcut database yapısı değişmez
- Eski fonksiyonlar çalışmaya devam eder
- Kademeli geçiş mümkün
"""

if __name__ == "__main__":
    print(INSTALLATION_GUIDE)