"""
Atomic Order Completion Manager
==============================
Provides atomic order completion operations to prevent race conditions
when multiple users attempt to complete the same order simultaneously.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
from datetime import date
from app.dao.logo import fetch_one, fetch_all, _t, QUEUE_TABLE
from app.dao.concurrency_manager import with_completion_lock
from app.dao.transactions import transaction_scope
import app.backorder as bo
from app.shipment import upsert_header

logger = logging.getLogger(__name__)

class OrderCompletionResult:
    """Result of order completion operation."""
    
    def __init__(self, success: bool, message: str = "", order_no: str = "", 
                 packages_created: int = 0, was_already_completed: bool = False):
        self.success = success
        self.message = message
        self.order_no = order_no
        self.packages_created = packages_created
        self.was_already_completed = was_already_completed

def atomic_complete_order(
    order_id: int,
    package_count: int,
    lines_data: List[Dict],
    sent_quantities: Dict[str, float],
    username: str = "SYSTEM"
) -> OrderCompletionResult:
    """
    Atomically complete an order with full concurrency protection.
    
    This function ensures that:
    1. Only one user can complete an order at a time
    2. Order status is verified before completion
    3. All operations happen in a single transaction
    4. Rollback occurs if any step fails
    
    Args:
        order_id: Order ID to complete
        package_count: Number of packages for shipment
        lines_data: Order line data for processing
        sent_quantities: Map of item_code -> qty_sent
        username: User performing the operation
        
    Returns:
        OrderCompletionResult: Result with success status and details
    """
    
    try:
        with with_completion_lock(order_id) as conn:
            cursor = conn.cursor()
            
            # Step 1: Verify order is still available for completion
            cursor.execute(f"""
                SELECT LOGICALREF, FICHENO, STATUS
                FROM {_t('ORFICHE')} WITH (UPDLOCK, ROWLOCK)
                WHERE LOGICALREF = ?
            """, order_id)
            
            order_row = cursor.fetchone()
            if not order_row:
                return OrderCompletionResult(
                    success=False,
                    message="Order not found"
                )
            
            order_no = order_row[1]
            current_status = order_row[2]
            
            # Check if already completed
            if current_status == 4:
                return OrderCompletionResult(
                    success=False,
                    message=f"Order {order_no} already completed by another user",
                    order_no=order_no,
                    was_already_completed=True
                )
            
            # Verify it's available for completion (STATUS = 2)
            if current_status != 2:
                return OrderCompletionResult(
                    success=False,
                    message=f"Order {order_no} is not ready for completion (STATUS = {current_status})"
                )
            
            # Step 2: Get order header details for shipment
            cursor.execute(f"""
                SELECT 
                    oh.FICHENO as order_no,
                    cl.CODE as cari_kodu,
                    cl.DEFINITION_ as cari_adi,
                    oh.GENEXP2,
                    oh.GENEXP3,
                    cl.ADDR1 as adres
                FROM {_t('ORFICHE')} oh
                LEFT JOIN {_t('CLCARD', period_dependent=False)} cl ON oh.CLIENTREF = cl.LOGICALREF  
                WHERE oh.LOGICALREF = ?
            """, order_id)
            
            header_row = cursor.fetchone()
            if not header_row:
                return OrderCompletionResult(
                    success=False,
                    message="Could not fetch order header details"
                )
            
            hdr = {
                'order_no': header_row[0],
                'cari_kodu': header_row[1] or '',
                'cari_adi': header_row[2] or '',
                'genexp2': header_row[3] or '',
                'genexp3': header_row[4] or '',
                'adres': header_row[5] or ''
            }
            
            # Step 3: Get invoice root
            inv_root = ""
            try:
                cursor.execute(f"""
                    SELECT TOP 1 FICHENO 
                    FROM {_t('INVOICE')} 
                    WHERE SOURCEINDEX = ? AND TRCODE IN (7,8)
                """, order_id)
                inv_row = cursor.fetchone()
                if inv_row:
                    inv_root = inv_row[0].replace('-K1', '').replace('-K2', '').replace('-K3', '')
            except Exception:
                logger.warning(f"Could not fetch invoice root for order {order_id}")
            
            # Step 4: Create/update shipment header
            trip_date = date.today().strftime('%Y-%m-%d')
            
            upsert_header(
                order_no, trip_date, package_count,
                customer_code=hdr.get("cari_kodu", ""),
                customer_name=hdr.get("cari_adi", "")[:60],
                region=f"{hdr.get('genexp2','')} - {hdr.get('genexp3','')}".strip(" -"),
                address1=hdr.get("adres", "")[:128],
                invoice_root=inv_root,
                conn=conn  # Use same transaction connection
            )
            
            # Step 5: Get shipment header ID for synchronization
            cursor.execute(
                "SELECT id, pkgs_total FROM shipment_header WHERE order_no=? AND trip_date=?", 
                order_no, trip_date
            )
            shipment_row = cursor.fetchone()
            if not shipment_row:
                raise Exception("Failed to create/update shipment header")
            
            trip_id = shipment_row[0]
            
            # Step 6: Synchronize packages
            from app.shipment_safe_sync import safe_sync_packages
            sync_result = safe_sync_packages(trip_id, package_count, conn=conn)
            
            if not sync_result["success"]:
                raise Exception(f"Package sync failed: {sync_result['message']}")
            
            # Step 7: Process backorders and shipment lines
            for line_data in lines_data:
                code = line_data["item_code"]
                wh = line_data["warehouse_id"]
                ordered = line_data["qty_ordered"]
                sent_qty = sent_quantities.get(code, 0)
                missing = ordered - sent_qty
                
                if sent_qty > 0:
                    bo.add_shipment(
                        order_no, trip_date, code,
                        warehouse_id=wh,
                        invoiced_qty=ordered,
                        qty_delta=sent_qty,
                        conn=conn
                    )
                
                if missing > 0:
                    bo.insert_backorder(
                        order_no, line_data["line_id"], wh, code, missing,
                        conn=conn
                    )
            
            # Step 8: Update order status to completed (STATUS = 4)
            genexp5_text = f"TAMAMLANDI: {username} / {date.today().strftime('%d.%m.%Y')}"
            
            cursor.execute(f"""
                UPDATE {_t('ORFICHE')} 
                SET STATUS = 4, GENEXP4 = ?, GENEXP5 = ?
                WHERE LOGICALREF = ?
            """, f"PAKET SAYISI : {package_count}", genexp5_text, order_id)
            
            # Step 9: Clear from queue
            cursor.execute(f"DELETE FROM {QUEUE_TABLE} WHERE order_id = ?", order_id)
            
            # Transaction will auto-commit when context manager exits
            logger.info(f"Order {order_no} completed atomically by {username}")
            
            return OrderCompletionResult(
                success=True,
                message=f"Order {order_no} completed successfully",
                order_no=order_no,
                packages_created=package_count
            )
            
    except Exception as e:
        logger.error(f"Atomic order completion failed for {order_id}: {e}")
        return OrderCompletionResult(
            success=False,
            message=f"Completion failed: {str(e)}"
        )

def check_order_completion_status(order_id: int) -> Optional[Dict]:
    """
    Check if an order is currently being completed by another user.
    
    Args:
        order_id: Order ID to check
        
    Returns:
        dict: Status information or None if not locked
    """
    from app.dao.concurrency_manager import WMSConcurrencyManager
    
    lock_name = f"WMS_COMPLETE_{order_id}"
    return WMSConcurrencyManager.check_lock_status(lock_name)