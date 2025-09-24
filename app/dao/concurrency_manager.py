"""
WMS Concurrency Manager - Application-Level Locks
=================================================
Provides distributed locking mechanisms for WMS operations using SQL Server's sp_getapplock.
This ensures atomic operations across multiple scanner instances and prevents race conditions.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Optional
from app.dao.logo import get_conn

logger = logging.getLogger(__name__)

class WMSConcurrencyManager:
    """Manages application-level locks for WMS operations."""
    
    LOCK_TIMEOUT_MS = 5000  # 5 seconds
    
    @staticmethod
    @contextmanager
    def scanner_lock(order_id: int, item_code: str):
        """
        Acquire application-level lock for scanning a specific item in an order.
        Prevents race conditions when multiple users scan the same item simultaneously.
        
        Args:
            order_id: Order ID being processed
            item_code: Item code being scanned
            
        Raises:
            RuntimeError: If lock cannot be acquired within timeout
        """
        lock_name = f"WMS_SCAN_{order_id}_{item_code}"
        
        with get_conn(autocommit=False) as conn:
            try:
                # Acquire exclusive lock
                cursor = conn.cursor()
                cursor.execute(
                    "EXEC sp_getapplock @Resource = ?, @LockMode = 'Exclusive', @LockTimeout = ?",
                    lock_name, WMSConcurrencyManager.LOCK_TIMEOUT_MS
                )
                
                result = cursor.fetchone()[0]
                
                if result < 0:
                    error_messages = {
                        -1: "Request timed out",
                        -2: "Request canceled", 
                        -3: "Deadlock victim",
                        -999: "Parameter validation or other error"
                    }
                    raise RuntimeError(f"Failed to acquire scanner lock: {error_messages.get(result, f'Error code: {result}')}")
                
                logger.debug(f"Acquired scanner lock for {order_id}_{item_code}")
                
                yield conn
                
            finally:
                try:
                    # Release lock
                    cursor.execute("EXEC sp_releaseapplock @Resource = ?", lock_name)
                    conn.commit()
                    logger.debug(f"Released scanner lock for {order_id}_{item_code}")
                except Exception as e:
                    logger.warning(f"Failed to release scanner lock {lock_name}: {e}")

    @staticmethod
    @contextmanager 
    def order_completion_lock(order_id: int):
        """
        Acquire application-level lock for order completion operations.
        Ensures only one user can complete an order at a time.
        
        Args:
            order_id: Order ID being completed
            
        Raises:
            RuntimeError: If lock cannot be acquired within timeout
        """
        lock_name = f"WMS_COMPLETE_{order_id}"
        
        with get_conn(autocommit=False) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "EXEC sp_getapplock @Resource = ?, @LockMode = 'Exclusive', @LockTimeout = ?",
                    lock_name, WMSConcurrencyManager.LOCK_TIMEOUT_MS
                )
                
                result = cursor.fetchone()[0]
                
                if result < 0:
                    error_messages = {
                        -1: "Request timed out - another user is completing this order",
                        -2: "Request canceled", 
                        -3: "Deadlock victim",
                        -999: "Parameter validation or other error"
                    }
                    raise RuntimeError(f"Failed to acquire completion lock: {error_messages.get(result, f'Error code: {result}')}")
                
                logger.debug(f"Acquired completion lock for order {order_id}")
                
                yield conn
                
            finally:
                try:
                    cursor.execute("EXEC sp_releaseapplock @Resource = ?", lock_name)
                    conn.commit()
                    logger.debug(f"Released completion lock for order {order_id}")
                except Exception as e:
                    logger.warning(f"Failed to release completion lock {lock_name}: {e}")

    @staticmethod
    def check_lock_status(resource_name: str) -> Optional[dict]:
        """
        Check the status of an application lock.
        
        Args:
            resource_name: Name of the lock resource
            
        Returns:
            dict: Lock status information or None if not found
        """
        try:
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT request_mode, request_status, request_session_id FROM sys.dm_tran_locks "
                    "WHERE resource_description = ? AND resource_type = 'APPLICATION'",
                    resource_name
                )
                
                row = cursor.fetchone()
                if row:
                    return {
                        'mode': row[0],
                        'status': row[1], 
                        'session_id': row[2]
                    }
                return None
                
        except Exception as e:
            logger.warning(f"Failed to check lock status for {resource_name}: {e}")
            return None


# Convenience functions for common operations
def with_scanner_lock(order_id: int, item_code: str):
    """Decorator for scanner operations requiring locks."""
    return WMSConcurrencyManager.scanner_lock(order_id, item_code)

def with_completion_lock(order_id: int):
    """Decorator for order completion operations requiring locks."""
    return WMSConcurrencyManager.order_completion_lock(order_id)