"""
UI Donma Sorunu Çözümleri - scanner_page.py için
"""

# ÇÖZÜM 1: Progress Dialog ile Kullanıcı Bildirimi (EN HIZLI)
def fix_with_progress_dialog(self):
    """
    finish_order metoduna eklenecek - satır 1670 civarı
    """
    from PyQt5.QtWidgets import QProgressDialog
    from PyQt5.QtCore import QCoreApplication
    
    # Progress dialog oluştur
    progress = QProgressDialog("Sipariş tamamlanıyor...", None, 0, 100, self)
    progress.setWindowTitle("İşlem Devam Ediyor")
    progress.setWindowModality(Qt.WindowModal)
    progress.setCancelButton(None)  # İptal edilemez
    progress.show()
    
    try:
        conn = get_logo_connection()
        cursor = conn.cursor()
        
        # Her önemli adımda progress güncelle
        progress.setValue(10)
        progress.setLabelText("Eksik ürünler kontrol ediliyor...")
        QCoreApplication.processEvents()  # UI'yi güncelle
        
        # Eksik ürünleri kontrol et
        missing_items = self.get_missing_items()
        
        progress.setValue(30)
        progress.setLabelText(f"{len(missing_items)} eksik ürün işleniyor...")
        QCoreApplication.processEvents()
        
        # Backorder oluştur
        if missing_items:
            for idx, item in enumerate(missing_items):
                # Her 5 üründe bir progress güncelle
                if idx % 5 == 0:
                    progress.setValue(30 + (idx * 40 // len(missing_items)))
                    progress.setLabelText(f"Eksik ürün {idx+1}/{len(missing_items)}: {item['code']}")
                    QCoreApplication.processEvents()
                
                # Backorder insert işlemi
                cursor.execute("INSERT INTO WMS_BACKORDERS ...")
        
        progress.setValue(70)
        progress.setLabelText("Sipariş durumu güncelleniyor...")
        QCoreApplication.processEvents()
        
        # Status güncelle
        cursor.execute("UPDATE LG_025_01_ORFICHE SET STATUS = 4 WHERE LOGICALREF = ?", order_id)
        
        progress.setValue(90)
        progress.setLabelText("Sevkiyat oluşturuluyor...")
        QCoreApplication.processEvents()
        
        # Shipment oluştur
        create_shipment(...)
        
        conn.commit()
        progress.setValue(100)
        progress.close()
        
    except Exception as e:
        progress.close()
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


# ÇÖZÜM 2: Thread ile Arka Plan İşlemi (ÖNERILEN)
from PyQt5.QtCore import QThread, pyqtSignal

class OrderCompletionThread(QThread):
    progress_update = pyqtSignal(int, str)
    completed = pyqtSignal(bool, str)
    
    def __init__(self, order_data, missing_items):
        super().__init__()
        self.order_data = order_data
        self.missing_items = missing_items
    
    def run(self):
        try:
            conn = get_logo_connection()
            cursor = conn.cursor()
            
            # Eksik ürünleri işle
            self.progress_update.emit(20, "Eksik ürünler işleniyor...")
            
            if self.missing_items:
                for idx, item in enumerate(self.missing_items):
                    if idx % 5 == 0:
                        progress = 20 + (idx * 50 // len(self.missing_items))
                        self.progress_update.emit(progress, f"Eksik: {item['code']}")
                    
                    cursor.execute("""
                        INSERT INTO WMS_BACKORDERS 
                        (order_id, item_code, qty_missing, created_date)
                        VALUES (?, ?, ?, GETDATE())
                    """, self.order_data['id'], item['code'], item['missing'])
            
            self.progress_update.emit(70, "Sipariş durumu güncelleniyor...")
            
            # Status güncelle
            cursor.execute("""
                UPDATE LG_025_01_ORFICHE 
                SET STATUS = 4, 
                    CLOSED_DATE = GETDATE(),
                    CLOSED_BY = ?
                WHERE LOGICALREF = ?
            """, self.order_data['user'], self.order_data['id'])
            
            self.progress_update.emit(90, "Sevkiyat oluşturuluyor...")
            
            # Shipment oluştur
            cursor.execute("""
                INSERT INTO shipment_headers 
                (order_id, package_count, status, created_date)
                VALUES (?, ?, 1, GETDATE())
            """, self.order_data['id'], self.order_data['packages'])
            
            conn.commit()
            self.completed.emit(True, "Sipariş başarıyla tamamlandı!")
            
        except Exception as e:
            conn.rollback()
            self.completed.emit(False, str(e))
        finally:
            cursor.close()
            conn.close()

# scanner_page.py'de kullanım:
def finish_order_threaded(self):
    """finish_order yerine bu kullanılacak"""
    # Thread oluştur
    self.completion_thread = OrderCompletionThread(
        order_data={'id': self.current_order['order_id'], ...},
        missing_items=self.get_missing_items()
    )
    
    # Progress dialog
    self.progress_dialog = QProgressDialog("Başlıyor...", None, 0, 100, self)
    self.progress_dialog.setWindowModality(Qt.WindowModal)
    self.progress_dialog.setCancelButton(None)
    
    # Sinyalleri bağla
    self.completion_thread.progress_update.connect(self.update_progress)
    self.completion_thread.completed.connect(self.on_completion_finished)
    
    # Thread'i başlat
    self.completion_thread.start()
    self.progress_dialog.show()

def update_progress(self, value, text):
    self.progress_dialog.setValue(value)
    self.progress_dialog.setLabelText(text)

def on_completion_finished(self, success, message):
    self.progress_dialog.close()
    if success:
        QMessageBox.information(self, "Başarılı", message)
        self.reset_order()
    else:
        QMessageBox.critical(self, "Hata", f"İşlem başarısız: {message}")


# ÇÖZÜM 3: Batch İşlem Optimizasyonu (EN PERFORMANSLI)
def optimized_batch_completion(self):
    """
    Tek sorguda çoklu insert - satır 1700 civarı değişecek
    """
    conn = get_logo_connection()
    cursor = conn.cursor()
    
    try:
        # TÜM eksikleri tek sorguda ekle (döngü yerine)
        if missing_items:
            # Batch insert için veri hazırla
            backorder_data = [
                (self.current_order['order_id'], item['code'], item['missing'], 
                 item.get('warehouse_id', 'SM'))
                for item in missing_items
            ]
            
            # Tek seferde çoklu insert
            cursor.executemany("""
                INSERT INTO WMS_BACKORDERS 
                (order_id, item_code, qty_missing, warehouse_id, created_date)
                VALUES (?, ?, ?, ?, GETDATE())
            """, backorder_data)
            
            # Tek UPDATE ile tüm satırları güncelle
            cursor.execute("""
                UPDATE WMS_PICKQUEUE 
                SET backorder_qty = qty_ordered - qty_sent,
                    status = 'PARTIAL'
                WHERE order_id = ? AND qty_sent < qty_ordered
            """, self.current_order['order_id'])
        
        # Gerisi aynı...
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()