"""
Common utility functions for the WMS system
===========================================
This module contains frequently used utility functions that are used across
multiple components of the WMS system. These utilities help reduce code 
duplication and provide consistent behavior.
"""

from typing import Optional, Any
from datetime import date, datetime
from PyQt5.QtWidgets import QMessageBox, QWidget
from PyQt5.QtCore import QDate
from app.dao.logo import get_conn
from app.dao.transactions import transaction_scope
import logging

logger = logging.getLogger(__name__)


def format_qt_date(qt_date: QDate) -> str:
    """
    Formats a QDate object to ISO date string.
    
    Args:
        qt_date: QDate object to format
        
    Returns:
        str: Date in YYYY-MM-DD format
        
    Example:
        >>> qdate = QDate(2025, 8, 30)
        >>> format_qt_date(qdate)
        '2025-08-30'
    """
    if not qt_date or not qt_date.isValid():
        return date.today().isoformat()
    
    return qt_date.toString("yyyy-MM-dd")


def show_error(parent: Optional[QWidget], title: str, message: str) -> None:
    """
    Shows a standardized error dialog with consistent styling.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog window title
        message: Error message to display
        
    Example:
        >>> show_error(self, "Database Error", "Connection failed")
    """
    QMessageBox.critical(parent, f"❌ {title}", message)


def show_warning(parent: Optional[QWidget], title: str, message: str) -> None:
    """
    Shows a standardized warning dialog with consistent styling.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog window title
        message: Warning message to display
        
    Example:
        >>> show_warning(self, "Validation Warning", "Invalid barcode format")
    """
    QMessageBox.warning(parent, f"⚠️ {title}", message)


def show_info(parent: Optional[QWidget], title: str, message: str) -> None:
    """
    Shows a standardized information dialog with consistent styling.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog window title
        message: Information message to display
        
    Example:
        >>> show_info(self, "Success", "Order completed successfully")
    """
    QMessageBox.information(parent, f"ℹ️ {title}", message)


def get_connection_with_lock(autocommit: bool = False):
    """
    Gets a database connection with proper locking mechanism.
    This is a wrapper around the standard get_conn function that ensures
    consistent connection handling across the application.
    
    Args:
        autocommit: Whether to enable autocommit mode
        
    Returns:
        Database connection context manager
        
    Example:
        >>> with get_connection_with_lock(autocommit=True) as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM table")
    """
    return get_conn(autocommit=autocommit)


def get_transaction_connection():
    """
    Gets a database connection within a transaction scope.
    This ensures atomic operations and automatic rollback on failure.
    
    Returns:
        Transaction scope context manager
        
    Example:
        >>> with get_transaction_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("INSERT INTO table VALUES (?)", value)
        ...     cursor.execute("UPDATE table SET field = ?", new_value)
        ...     # Auto-commit on success, rollback on exception
    """
    return transaction_scope()


def validate_package_count(pkg_count: int, operation: str = "operation") -> None:
    """
    Validates package count to prevent negative or zero values.
    
    Args:
        pkg_count: Package count to validate
        operation: Description of the operation for error messages
        
    Raises:
        ValueError: If package count is invalid
        
    Example:
        >>> validate_package_count(5, "shipment creation")  # OK
        >>> validate_package_count(0, "loading")  # Raises ValueError
    """
    if pkg_count <= 0:
        raise ValueError(f"HATA: Geçersiz paket sayısı ({pkg_count}) {operation} için. Pozitif değer olmalı.")
    
    if pkg_count > 9999:
        raise ValueError(f"HATA: Paket sayısı çok büyük ({pkg_count}) {operation} için. Maksimum 9999 desteklenir.")


def validate_package_number(pkg_no: int, operation: str = "operation") -> None:
    """
    Validates package number to prevent negative or zero values.
    
    Args:
        pkg_no: Package number to validate
        operation: Description of the operation for error messages
        
    Raises:
        ValueError: If package number is invalid
        
    Example:
        >>> validate_package_number(3, "loading")  # OK
        >>> validate_package_number(-1, "scanning")  # Raises ValueError
    """
    if pkg_no <= 0:
        raise ValueError(f"HATA: Geçersiz paket numarası ({pkg_no}) {operation} için. Pozitif değer olmalı.")
    
    if pkg_no > 9999:
        raise ValueError(f"HATA: Paket numarası çok büyük ({pkg_no}) {operation} için. Maksimum 9999 desteklenir.")


def log_operation(operation: str, details: str = "", success: bool = True) -> None:
    """
    Logs operations with consistent formatting for debugging and monitoring.
    
    Args:
        operation: Name of the operation
        details: Additional details about the operation
        success: Whether the operation was successful
        
    Example:
        >>> log_operation("barcode_scan", "ABC123 -> Package loaded", True)
        >>> log_operation("database_update", "Connection failed", False)
    """
    level = logging.INFO if success else logging.ERROR
    status = "SUCCESS" if success else "FAILED"
    message = f"{operation.upper()} {status}"
    
    if details:
        message += f": {details}"
    
    logger.log(level, message)


def format_currency(amount: float, currency: str = "TL") -> str:
    """
    Formats monetary amounts consistently.
    
    Args:
        amount: Amount to format
        currency: Currency symbol
        
    Returns:
        str: Formatted currency string
        
    Example:
        >>> format_currency(1234.56)
        '1.234,56 TL'
    """
    # Turkish number formatting (comma for decimals, dot for thousands)
    formatted = f"{amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{formatted} {currency}"


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """
    Safely converts a value to integer with fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        int: Converted integer or default value
        
    Example:
        >>> safe_int_conversion("123")
        123
        >>> safe_int_conversion("invalid", 0)
        0
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Safely converts a value to float with fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        float: Converted float or default value
        
    Example:
        >>> safe_float_conversion("123.45")
        123.45
        >>> safe_float_conversion("invalid", 0.0)
        0.0
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncates text to specified length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        str: Truncated text
        
    Example:
        >>> truncate_text("Very long text", 10)
        'Very lo...'
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def is_valid_barcode(barcode: str) -> bool:
    """
    Validates barcode format according to WMS standards.
    
    Args:
        barcode: Barcode string to validate
        
    Returns:
        bool: True if valid, False otherwise
        
    Example:
        >>> is_valid_barcode("ABC123")
        True
        >>> is_valid_barcode("AB@#$")
        False
    """
    if not barcode or len(barcode) < 2:
        return False
    
    # Alfanumerik + tire/alt çizgi/slash/nokta/artı/boşluk izin ver
    allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/.+ ")
    return all(c.upper() in allowed_chars for c in barcode)


# Error handling decorator
def handle_database_errors(operation_name: str = "database operation"):
    """
    Decorator to handle common database errors consistently.
    
    Args:
        operation_name: Name of the operation for logging
        
    Example:
        >>> @handle_database_errors("user creation")
        ... def create_user(name):
        ...     # database operations
        ...     pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"{operation_name} failed: {str(e)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
        return wrapper
    return decorator