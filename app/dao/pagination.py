"""
Pagination Support for Database Queries
========================================
Provides pagination functionality for large datasets.
"""
from typing import Dict, List, Any, Optional, Tuple
import math
from app.dao.logo import fetch_all, fetch_one, _t


class Paginator:
    """Database query pagination helper."""
    
    def __init__(self, page_size: int = 50):
        """
        Initialize paginator.
        
        Args:
            page_size: Number of items per page (default: 50)
        """
        self.page_size = max(1, min(page_size, 500))  # Limit between 1-500
    
    def get_page_sql(self, base_sql: str, page: int = 1, order_by: str = None) -> Tuple[str, int, int]:
        """
        Convert base SQL to paginated SQL using OFFSET/FETCH.
        
        Args:
            base_sql: Base SELECT query (without ORDER BY)
            page: Page number (1-based)
            order_by: ORDER BY clause (required for OFFSET/FETCH)
            
        Returns:
            Tuple of (paginated_sql, offset, limit)
        """
        if not order_by:
            raise ValueError("ORDER BY is required for pagination in SQL Server")
        
        page = max(1, page)  # Ensure page is at least 1
        offset = (page - 1) * self.page_size
        
        # SQL Server syntax
        paginated_sql = f"""
        {base_sql}
        {order_by}
        OFFSET {offset} ROWS
        FETCH NEXT {self.page_size} ROWS ONLY
        """
        
        return paginated_sql, offset, self.page_size
    
    def get_page_info(self, total_count: int, current_page: int = 1) -> Dict[str, Any]:
        """
        Calculate pagination metadata.
        
        Args:
            total_count: Total number of items
            current_page: Current page number
            
        Returns:
            Dictionary with pagination info
        """
        total_pages = math.ceil(total_count / self.page_size) if total_count > 0 else 1
        current_page = max(1, min(current_page, total_pages))
        
        return {
            'total_count': total_count,
            'page_size': self.page_size,
            'current_page': current_page,
            'total_pages': total_pages,
            'has_next': current_page < total_pages,
            'has_previous': current_page > 1,
            'start_index': (current_page - 1) * self.page_size + 1,
            'end_index': min(current_page * self.page_size, total_count)
        }


def fetch_paginated(
    base_sql: str,
    count_sql: str,
    order_by: str,
    params: tuple = (),
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """
    Execute paginated query with metadata.
    
    Args:
        base_sql: Base SELECT query
        count_sql: Query to get total count
        order_by: ORDER BY clause
        params: Query parameters
        page: Page number (1-based)
        page_size: Items per page
        
    Returns:
        Dictionary with 'data' and 'pagination' keys
    """
    paginator = Paginator(page_size)
    
    # Get total count
    count_result = fetch_one(count_sql, *params)
    total_count = count_result[0] if count_result else 0
    
    # Get paginated data
    paginated_sql, _, _ = paginator.get_page_sql(base_sql, page, order_by)
    data = fetch_all(paginated_sql, *params)
    
    # Get pagination info
    pagination = paginator.get_page_info(total_count, page)
    
    return {
        'data': data,
        'pagination': pagination
    }


# ---- Paginated DAO Functions ----

def fetch_draft_orders_paginated(
    page: int = 1,
    page_size: int = 50,
    search: str = None
) -> Dict[str, Any]:
    """
    Fetch draft orders with pagination.
    
    Args:
        page: Page number (1-based)
        page_size: Items per page
        search: Optional search term for order_no or customer
        
    Returns:
        Dictionary with paginated results
    """
    # Base query
    base_sql = f"""
    SELECT
        F.LOGICALREF AS order_id,
        F.FICHENO    AS order_no,
        F.DATE_      AS order_date,
        C.CODE       AS customer_code,
        C.TITLE      AS customer_name,
        F.NETTOTAL   AS net_total,
        F.GROSSTOTAL AS gross_total,
        F.GENEXP1    AS notes
    FROM {_t('ORFICHE')} F
    LEFT JOIN {_t('CLCARD')} C ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 1 AND F.CANCELLED = 0
    """
    
    # Add search filter if provided
    params = []
    if search:
        base_sql += " AND (F.FICHENO LIKE ? OR C.TITLE LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term])
    
    # Count query
    count_sql = f"""
    SELECT COUNT(*)
    FROM {_t('ORFICHE')} F
    LEFT JOIN {_t('CLCARD')} C ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 1 AND F.CANCELLED = 0
    """
    
    if search:
        count_sql += " AND (F.FICHENO LIKE ? OR C.TITLE LIKE ?)"
    
    # Order by
    order_by = "ORDER BY F.DATE_ DESC, F.FICHENO DESC"
    
    return fetch_paginated(
        base_sql=base_sql,
        count_sql=count_sql,
        order_by=order_by,
        params=tuple(params),
        page=page,
        page_size=page_size
    )


def fetch_picking_orders_paginated(
    page: int = 1,
    page_size: int = 50,
    search: str = None
) -> Dict[str, Any]:
    """
    Fetch picking orders (STATUS=2) with pagination.
    
    Args:
        page: Page number (1-based)
        page_size: Items per page
        search: Optional search term
        
    Returns:
        Dictionary with paginated results
    """
    # Base query
    base_sql = f"""
    SELECT 
        F.LOGICALREF  AS order_id,
        F.FICHENO     AS order_no,
        F.DATE_       AS order_date,
        C.CODE        AS customer_code,
        C.TITLE       AS customer_name,
        F.NETTOTAL    AS net_total,
        F.SOURCEINDEX AS warehouse_id,
        F.GENEXP1     AS notes
    FROM {_t('ORFICHE')} F
    LEFT JOIN {_t('CLCARD')} C ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 2 AND F.CANCELLED = 0
    """
    
    # Add search filter
    params = []
    if search:
        base_sql += " AND (F.FICHENO LIKE ? OR C.TITLE LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term])
    
    # Count query
    count_sql = f"""
    SELECT COUNT(*)
    FROM {_t('ORFICHE')} F
    LEFT JOIN {_t('CLCARD')} C ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 2 AND F.CANCELLED = 0
    """
    
    if search:
        count_sql += " AND (F.FICHENO LIKE ? OR C.TITLE LIKE ?)"
    
    # Order by
    order_by = "ORDER BY F.DATE_ DESC, F.FICHENO DESC"
    
    return fetch_paginated(
        base_sql=base_sql,
        count_sql=count_sql,
        order_by=order_by,
        params=tuple(params),
        page=page,
        page_size=page_size
    )


def fetch_loaded_orders_paginated(
    page: int = 1,
    page_size: int = 50,
    trip_date: str = None
) -> Dict[str, Any]:
    """
    Fetch loaded shipment orders with pagination.
    
    Args:
        page: Page number (1-based)
        page_size: Items per page
        trip_date: Optional filter by trip date (YYYY-MM-DD)
        
    Returns:
        Dictionary with paginated results
    """
    # Base query
    base_sql = """
    SELECT 
        h.id AS trip_id,
        h.order_no,
        h.trip_date,
        h.customer_code,
        h.customer_name,
        h.address1,
        h.region,
        h.pkgs_total,
        h.pkgs_loaded,
        h.closed,
        h.created_at
    FROM shipment_header h
    WHERE h.closed = 0
    """
    
    # Add date filter
    params = []
    if trip_date:
        base_sql += " AND h.trip_date = ?"
        params.append(trip_date)
    
    # Count query
    count_sql = """
    SELECT COUNT(*)
    FROM shipment_header h
    WHERE h.closed = 0
    """
    
    if trip_date:
        count_sql += " AND h.trip_date = ?"
    
    # Order by
    order_by = "ORDER BY h.created_at DESC, h.order_no DESC"
    
    return fetch_paginated(
        base_sql=base_sql,
        count_sql=count_sql,
        order_by=order_by,
        params=tuple(params),
        page=page,
        page_size=page_size
    )


# ---- Helper Functions ----

def get_page_range(current_page: int, total_pages: int, window: int = 5) -> List[int]:
    """
    Get page numbers to display in pagination controls.
    
    Args:
        current_page: Current page number
        total_pages: Total number of pages
        window: Number of pages to show around current (default: 5)
        
    Returns:
        List of page numbers to display
    """
    if total_pages <= window:
        return list(range(1, total_pages + 1))
    
    start = max(1, current_page - window // 2)
    end = min(total_pages, start + window - 1)
    
    # Adjust if we're near the end
    if end - start < window - 1:
        start = max(1, end - window + 1)
    
    return list(range(start, end + 1))