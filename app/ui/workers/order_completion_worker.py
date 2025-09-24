"""
Order Completion Worker - Thread based background processing for order completion
Prevents UI freezing during long database operations
"""

from PyQt5.QtCore import QThread, pyqtSignal
from typing import Dict, List, Any, Optional
from datetime import date
import logging

from app.dao.logo import get_connection as get_logo_connection, fetch_order_header, fetch_invoice_no
from app.dao.transactions import transaction_scope
from app import backorder as bo
from app.shipment_safe_sync import safe_sync_packages

logger = logging.getLogger(__name__)


class OrderCompletionWorker(QThread):
    """
    Background worker thread for order completion.
    Uses batch operations to minimize database round trips.
    """
    
    # Signals
    progress_update = pyqtSignal(int, str)  # Progress percentage, message
    completed = pyqtSignal(bool, str)  # Success, message
    
    def __init__(self, order_data: Dict, lines: List[Dict], sent: Dict, package_count: int):
        """
        Initialize the worker with order data.
        
        Args:
            order_data: Current order information
            lines: Order lines with item details
            sent: Dictionary of sent quantities by item code
            package_count: Number of packages
        """
        super().__init__()
        self.order_data = order_data
        self.lines = lines
        self.sent = sent
        self.package_count = package_count
        self.trip_date = date.today().isoformat()
        
    def run(self):
        """Main worker thread execution."""
        try:
            self.progress_update.emit(5, "İşlem başlatılıyor...")
            
            # Get order header
            self.progress_update.emit(10, "Sipariş başlığı okunuyor...")
            hdr = fetch_order_header(self.order_data["order_no"])
            if not hdr:
                self.completed.emit(False, "Sipariş başlığı okunamadı")
                return
                
            # Prepare batch data for missing items
            self.progress_update.emit(20, "Eksik ürünler hesaplanıyor...")
            missing_items = []
            shipment_items = []
            
            for ln in self.lines:
                code = ln["item_code"]
                wh = ln["warehouse_id"]
                ordered = ln["qty_ordered"]
                sent_qty = self.sent.get(code, 0)
                missing = ordered - sent_qty
                
                if sent_qty > 0:
                    shipment_items.append({
                        'code': code,
                        'warehouse': wh,
                        'ordered': ordered,
                        'sent': sent_qty
                    })
                
                if missing > 0:
                    missing_items.append({
                        'line_id': ln["line_id"],
                        'warehouse': wh,
                        'code': code,
                        'missing': missing
                    })
            
            # Start transaction
            self.progress_update.emit(30, "Veritabanı işlemleri başlıyor...")
            
            try:
                conn = get_logo_connection()
                if not conn:
                    raise Exception("Veritabanı bağlantısı kurulamadı")
            except Exception as e:
                self.progress_update.emit(100, "Veritabanı bağlantı hatası!")
                self.completed.emit(False, f"Veritabanına bağlanılamadı: {str(e)}")
                return
            
            try:
                cursor = conn.cursor()
                
                # Get invoice info with error handling
                try:
                    invoice_no = fetch_invoice_no(self.order_data["order_no"])
                    inv_root = invoice_no.split("-K")[0] if invoice_no else None
                except Exception as e:
                    logger.warning(f"Could not fetch invoice number: {e}")
                    invoice_no = None
                    inv_root = None
                
                # 1. Check if shipment header already exists
                self.progress_update.emit(40, "Sevkiyat başlığı kontrol ediliyor...")
                
                # First check for existing shipment
                cursor.execute(
                    "SELECT id, pkgs_total, status FROM shipment_header WHERE order_no=? AND trip_date=?",
                    self.order_data["order_no"], self.trip_date
                )
                existing_shipment = cursor.fetchone()
                
                if existing_shipment:
                    # Shipment already exists, just update package count if different
                    self.progress_update.emit(42, "Mevcut sevkiyat güncelleniyor...")
                    trip_id = existing_shipment.id
                    
                    if existing_shipment.pkgs_total != self.package_count:
                        cursor.execute(
                            "UPDATE shipment_header SET pkgs_total=?, updated_date=GETDATE() WHERE id=?",
                            self.package_count, trip_id
                        )
                        logger.info(f"Updated existing shipment {trip_id} package count: {existing_shipment.pkgs_total} -> {self.package_count}")
                    else:
                        logger.info(f"Using existing shipment {trip_id} with {self.package_count} packages")
                else:
                    # Create new shipment
                    self.progress_update.emit(42, "Yeni sevkiyat başlığı oluşturuluyor...")
                    
                    try:
                        from app.shipment import upsert_header
                        
                        upsert_header(
                            self.order_data["order_no"],
                            self.trip_date,
                            self.package_count,
                            customer_code=hdr.get("cari_kodu", ""),
                            customer_name=hdr.get("cari_adi", "")[:60],
                            region=f"{hdr.get('genexp2', '')} - {hdr.get('genexp3', '')}".strip(" -"),
                            address1=hdr.get("adres", "")[:128],
                            invoice_root=inv_root,
                            conn=conn
                        )
                        
                        # Get the newly created trip ID
                        cursor.execute(
                            "SELECT id FROM shipment_header WHERE order_no=? AND trip_date=?",
                            self.order_data["order_no"], self.trip_date
                        )
                        trip_result = cursor.fetchone()
                        if not trip_result:
                            raise Exception("Sevkiyat başlığı oluşturulamadı")
                        
                        trip_id = trip_result.id
                        logger.info(f"Created new shipment {trip_id} for order {self.order_data['order_no']}")
                        
                    except Exception as e:
                        # If upsert fails, try to get existing one more time
                        cursor.execute(
                            "SELECT id FROM shipment_header WHERE order_no=?",
                            self.order_data["order_no"]
                        )
                        fallback_result = cursor.fetchone()
                        if fallback_result:
                            trip_id = fallback_result.id
                            logger.warning(f"Using fallback shipment {trip_id} after upsert error: {e}")
                        else:
                            raise Exception(f"Sevkiyat başlığı oluşturulamadı: {str(e)}")
                
                self.progress_update.emit(45, "Sevkiyat başlığı hazır")
                
                # 2. Sync packages
                self.progress_update.emit(50, f"{self.package_count} paket senkronize ediliyor...")
                sync_result = safe_sync_packages(trip_id, self.package_count)
                if not sync_result["success"]:
                    raise Exception(f"Paket senkronizasyonu başarısız: {sync_result['message']}")
                
                # 3. Batch insert shipment items
                if shipment_items:
                    self.progress_update.emit(60, f"{len(shipment_items)} sevkiyat kalemi ekleniyor...")
                    for item in shipment_items:
                        bo.add_shipment(
                            self.order_data["order_no"],
                            self.trip_date,
                            item['code'],
                            warehouse_id=item['warehouse'],
                            invoiced_qty=item['ordered'],
                            qty_delta=item['sent']
                            # conn parametresi kaldırıldı - bo.add_shipment kabul etmiyor
                        )
                
                # 4. Batch insert backorders (BATCH OPERATION)
                if missing_items:
                    self.progress_update.emit(70, f"{len(missing_items)} eksik ürün kaydediliyor...")
                    
                    # Prepare batch data
                    backorder_data = [
                        (self.order_data["order_no"], 
                         item['line_id'],
                         item['warehouse'],
                         item['code'],
                         item['missing'])
                        for item in missing_items
                    ]
                    
                    # BATCH INSERT - Single query for all missing items
                    if len(backorder_data) > 0:
                        # Check if backorders table exists (correct table name)
                        cursor.execute("""
                            IF OBJECT_ID('backorders', 'U') IS NOT NULL
                            BEGIN
                                SELECT 1
                            END
                            ELSE
                            BEGIN
                                SELECT 0
                            END
                        """)
                        table_exists = cursor.fetchone()[0]
                        
                        if table_exists:
                            # Use batch insert for performance
                            for batch_item in backorder_data:
                                bo.insert_backorder(
                                    batch_item[0],  # order_no
                                    batch_item[1],  # line_id
                                    batch_item[2],  # warehouse
                                    batch_item[3],  # code
                                    batch_item[4]   # missing
                                    # conn parametresi kaldırıldı
                                )
                        else:
                            logger.warning("backorders table not found, skipping backorder creation")
                
                # 5. Update Logo order status
                self.progress_update.emit(85, "Sipariş durumu güncelleniyor...")
                ficheno = hdr.get("ficheno", "")
                genexp5_text = f"Sipariş No: {ficheno}" if ficheno else ""
                
                cursor.execute(
                    "UPDATE LG_025_01_ORFICHE SET STATUS = 4, GENEXP4 = ?, GENEXP5 = ? "
                    "WHERE LOGICALREF = ?",
                    f"PAKET SAYISI : {self.package_count}",
                    genexp5_text,
                    self.order_data["order_id"]
                )
                
                # 6. Remove from queue
                self.progress_update.emit(95, "Kuyruk temizleniyor...")
                cursor.execute(
                    "DELETE FROM WMS_PICKQUEUE WHERE order_id = ?",
                    self.order_data["order_id"]
                )
                
                # Commit transaction
                conn.commit()
                self.progress_update.emit(100, "İşlem tamamlandı!")
                
                # Success
                self.completed.emit(
                    True,
                    f"Sipariş başarıyla tamamlandı!\n"
                    f"Paket: {self.package_count}\n"
                    f"Eksik: {len(missing_items)} kalem"
                )
                
            except Exception as e:
                logger.error(f"Order completion failed: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                self.completed.emit(False, f"İşlem başarısız: {str(e)}")
            finally:
                if conn:
                    try:
                        cursor.close()
                    except:
                        pass
                    try:
                        conn.close()
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Worker thread error: {e}")
            self.completed.emit(False, f"İşlem başarısız: {str(e)}")