"""
Atomic scanner operations for concurrent access control.
Prevents race conditions when multiple users scan simultaneously.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
from app.dao.logo import get_connection

logger = logging.getLogger(__name__)

@dataclass
class ScanResult:
    """Result of an atomic scan operation"""
    success: bool
    message: str
    new_qty_sent: float = 0
    item_code: str = ""
    order_id: int = 0

def atomic_scan_increment(
    order_id: int,
    item_code: str,
    qty_increment: float = 1.0,
    qty_ordered: Optional[float] = None,
    over_scan_tolerance: float = 0
) -> ScanResult:
    """
    Atomically increment scan quantity with race condition protection.
    
    Args:
        order_id: Order ID
        item_code: Item barcode
        qty_increment: Quantity to add (default 1)
        qty_ordered: Expected ordered quantity (for validation)
        over_scan_tolerance: Allowed over-scan amount
        
    Returns:
        ScanResult with success status and new quantity
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # First get the ordered quantity if not provided
        if qty_ordered is None:
            cursor.execute(
                "SELECT qty_ordered FROM WMS_PICKQUEUE WHERE order_id = ? AND item_code = ?",
                order_id, item_code
            )
            row = cursor.fetchone()
            if row:
                qty_ordered = row.qty_ordered
            else:
                cursor.close()
                conn.close()
                return ScanResult(
                    success=False,
                    message=f"Ürün bulunamadı: {item_code}",
                    item_code=item_code,
                    order_id=order_id
                )
        
        # Use the simple stored procedure for atomic update
        # The simple version only takes 3 parameters: order_id, item_code, qty_increment
        cursor.execute("EXEC sp_atomic_scan_increment ?, ?, ?", order_id, item_code, qty_increment)
        
        # Handle transaction results properly
        conn.commit()  # Commit the stored procedure transaction
        
        # Try to get result, if fails assume success (procedure ran)
        try:
            cursor.nextset()  # Move to result set if exists
            result = cursor.fetchone()
        except:
            # No result set, but procedure executed - check manually
            result = None
        
        # Get the updated quantity
        cursor.execute(
            "SELECT qty_sent FROM WMS_PICKQUEUE WHERE order_id = ? AND item_code = ?",
            order_id, item_code
        )
        qty_row = cursor.fetchone()
        new_qty = qty_row.qty_sent if qty_row else 0
        
        cursor.close()
        conn.close()
        
        # Check if the update was successful
        # If result is None, check if qty was actually updated
        if (result and hasattr(result, 'UpdatedRows') and result.UpdatedRows > 0) or (result is None and new_qty > 0):
            # Check for over-scan
            if qty_ordered and new_qty > (qty_ordered + over_scan_tolerance):
                return ScanResult(
                    success=False,
                    message=f"Fazla adet! İzin verilen: {qty_ordered + over_scan_tolerance}, Şu an: {new_qty}",
                    item_code=item_code,
                    order_id=order_id,
                    new_qty_sent=new_qty,
                    was_over_limit=True
                )
            
            return ScanResult(
                success=True,
                message=f"Başarıyla tarandı: {item_code}",
                new_qty_sent=new_qty,
                item_code=item_code,
                order_id=order_id
            )
        else:
            return ScanResult(
                success=False,
                message="Ürün güncellenemedi - satır bulunamadı",
                item_code=item_code,
                order_id=order_id
            )
                
    except Exception as e:
        logger.error(f"Atomic scan error: {e}")
        return ScanResult(
            success=False,
            message=f"Veritabanı hatası: {str(e)}",
            item_code=item_code,
            order_id=order_id
        )

def get_current_quantities(order_id: int, item_code: str) -> Dict[str, Any]:
    """
    Get current quantities for an item (thread-safe read).
    
    Args:
        order_id: Order ID
        item_code: Item barcode
        
    Returns:
        Dict with qty_sent, qty_ordered, or None if not found
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT qty_sent, qty_ordered 
            FROM WMS_PICKQUEUE WITH (NOLOCK)
            WHERE order_id = ? AND item_code = ?
            """,
            order_id, item_code
        )
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return {
                'qty_sent': row.qty_sent,
                'qty_ordered': row.qty_ordered,
                'remaining': row.qty_ordered - row.qty_sent
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting quantities: {e}")
        return None