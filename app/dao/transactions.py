"""
Database Transaction Manager
Ensures atomic operations across multiple tables
"""
from contextlib import contextmanager
import pyodbc
import logging
from typing import Callable, Any
from app.dao.logo import CONN_STR, MAX_RETRY
import time

logger = logging.getLogger(__name__)

@contextmanager
def transaction_scope():
    """
    Context manager for database transactions.
    Ensures all operations within the scope are atomic.
    
    Usage:
        with transaction_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            cursor.execute(...)
            # Auto-commit on success, rollback on exception
    """
    conn = None
    last_exc = None
    
    # Retry logic for transient failures
    for attempt in range(1, MAX_RETRY + 1):
        try:
            conn = pyodbc.connect(CONN_STR, timeout=10, autocommit=False)
            break
        except pyodbc.Error as exc:
            last_exc = exc
            if attempt < MAX_RETRY:
                time.sleep(0.5 * attempt)  # Exponential backoff
                continue
            raise last_exc
    
    if not conn:
        raise RuntimeError("Could not establish database connection")
    
    try:
        yield conn
        conn.commit()  # Commit only if no exception
        logger.debug("Transaction committed successfully")
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                logger.warning(f"Transaction rolled back due to: {e}")
            except:
                pass  # Rollback might fail if connection is broken
        raise
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def execute_in_transaction(operations: list[Callable[[pyodbc.Connection], Any]]) -> list[Any]:
    """
    Execute multiple operations in a single transaction.
    
    Args:
        operations: List of functions that take a connection and perform operations
        
    Returns:
        List of results from each operation
        
    Example:
        def op1(conn):
            conn.execute("INSERT ...")
            return "op1 done"
            
        def op2(conn):
            conn.execute("UPDATE ...")
            return "op2 done"
            
        results = execute_in_transaction([op1, op2])
    """
    results = []
    
    with transaction_scope() as conn:
        for operation in operations:
            try:
                result = operation(conn)
                results.append(result)
            except Exception as e:
                logger.error(f"Operation failed in transaction: {e}")
                raise  # Will trigger rollback
    
    return results