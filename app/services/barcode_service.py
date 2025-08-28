"""
Centralized Barcode Service
Handles all barcode lookup and validation operations
"""
import logging
from typing import Tuple, Optional
from app.dao.logo import fetch_one, resolve_barcode_prefix

logger = logging.getLogger(__name__)


def barcode_xref_lookup(barcode: str, warehouse_id: str | None = None) -> Tuple[Optional[str], Optional[float]]:
    """
    Looks up a barcode in the barcode_xref table.
    
    Args:
        barcode: The barcode to lookup
        warehouse_id: Optional warehouse filter
        
    Returns:
        Tuple of (item_code, multiplier) or (None, None) if not found
        
    Note: This function properly handles database errors and logs them,
          instead of silently returning (None, None)
    """
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
                "FROM barcode_xref WHERE barcode=?", 
                barcode
            )
        
        if row:
            multiplier = row.get("multiplier", 1)
            return row["item_code"], float(multiplier) if multiplier else 1.0
            
        return None, None
        
    except Exception as exc:
        # Log the actual error instead of silent failure
        logger.error(f"Database error in barcode_xref_lookup for '{barcode}': {exc}")
        # Re-raise to let caller handle appropriately
        raise


def find_item_by_barcode(barcode: str, lines: list, warehouse_set: set | None = None) -> Tuple[dict | None, float]:
    """
    Find matching line item for a barcode using multiple strategies.
    
    Args:
        barcode: The barcode to find
        lines: List of order lines to search
        warehouse_set: Set of valid warehouse IDs (optional)
        
    Returns:
        Tuple of (matched_line, quantity_multiplier) or (None, 1.0) if not found
    """
    # 1) Direct stock code match
    matched_line = next(
        (ln for ln in lines if ln["item_code"].lower() == barcode.lower()),
        None
    )
    if matched_line:
        return matched_line, 1.0
    
    # 2) Warehouse prefix resolution
    for ln in lines:
        code = resolve_barcode_prefix(barcode, ln["warehouse_id"])
        if code and code == ln["item_code"]:
            return ln, 1.0
    
    # 3) Barcode xref lookup with warehouse filtering
    if warehouse_set:
        for wh_id in warehouse_set:
            try:
                item_code, multiplier = barcode_xref_lookup(barcode, wh_id)
                if item_code:
                    matched_line = next(
                        (ln for ln in lines
                         if ln["item_code"] == item_code
                         and ln["warehouse_id"] == wh_id),
                        None
                    )
                    if matched_line:
                        return matched_line, multiplier or 1.0
            except Exception as e:
                logger.warning(f"Error looking up barcode in warehouse {wh_id}: {e}")
                continue
    else:
        # No warehouse filter - try general lookup
        try:
            item_code, multiplier = barcode_xref_lookup(barcode)
            if item_code:
                matched_line = next(
                    (ln for ln in lines if ln["item_code"] == item_code),
                    None
                )
                if matched_line:
                    return matched_line, multiplier or 1.0
        except Exception as e:
            logger.warning(f"Error in general barcode lookup: {e}")
    
    return None, 1.0


def parse_complex_barcode(barcode: str, lines: list) -> Tuple[dict | None, float]:
    """
    Parse complex barcode formats like "44-1800/A-T10009-24-K10-1"
    
    Args:
        barcode: Complex barcode string
        lines: List of order lines
        
    Returns:
        Tuple of (matched_line, quantity) or (None, 1.0)
    """
    # Example implementation for specific format
    # This should be customized based on actual barcode format requirements
    
    if "-K" in barcode:
        # Format: PREFIX-CODE-Kxx-QTY
        parts = barcode.split("-K")
        if len(parts) == 2:
            code_part = parts[0]
            qty_part = parts[1]
            
            # Extract quantity if present
            try:
                if "-" in qty_part:
                    qty_str = qty_part.split("-")[-1]
                    qty = float(qty_str)
                else:
                    qty = 1.0
            except (ValueError, IndexError):
                qty = 1.0
            
            # Try to match the code part
            for ln in lines:
                if code_part in ln["item_code"]:
                    return ln, qty
    
    return None, 1.0