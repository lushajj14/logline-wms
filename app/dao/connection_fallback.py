#!/usr/bin/env python3
"""
Connection Fallback Manager
============================
Automatically tries multiple database servers if primary fails.
"""

import pyodbc
import logging
import os
from typing import Optional, Tuple, List
from app.settings_manager import get_manager

logger = logging.getLogger(__name__)


class ConnectionFallback:
    """Manages automatic fallback between database servers."""
    
    # Server priority list (will try in order)
    FALLBACK_SERVERS = [
        # Primary from settings/env
        None,  # Will be filled with current settings
        
        # Known alternatives
        ("192.168.5.100,1433", "VPN/Local Network"),
        ("78.135.108.160,1433", "Public Internet"),
        ("localhost,1433", "Local Test"),
    ]
    
    @classmethod
    def get_working_connection(cls) -> Tuple[Optional[str], Optional[str]]:
        """
        Try to establish a database connection using fallback servers.
        
        Returns:
            Tuple of (connection_string, server_description) if successful
            (None, None) if all attempts fail
        """
        manager = get_manager()
        
        # Get current settings
        current_server = manager.get("db.server", os.getenv("LOGO_SQL_SERVER", "192.168.5.100,1433"))
        database = manager.get("db.database", os.getenv("LOGO_SQL_DB", "logo"))
        user = manager.get("db.user", os.getenv("LOGO_SQL_USER", "barkod1"))
        password = manager.get("db.password", os.getenv("LOGO_SQL_PASSWORD", "Barkod14*"))
        
        # Build server list with current as first priority
        servers_to_try = [(current_server, "Current Settings")]
        
        # Add other servers if different from current
        for server, desc in cls.FALLBACK_SERVERS[1:]:
            if server != current_server:
                servers_to_try.append((server, desc))
        
        # Get best available driver
        drivers = [d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d]
        drivers.sort(key=lambda s: int("".join(filter(str.isdigit, s))) or 0)
        driver = os.getenv("LOGO_SQL_DRIVER") or (drivers[-1] if drivers else "SQL Server")
        
        # Try each server
        for server, description in servers_to_try:
            if not server:
                continue
                
            logger.info(f"Trying connection to {description}: {server}")
            
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
                f"UID={user};PWD={password};TrustServerCertificate=yes;"
            )
            
            try:
                # Quick connection test (3 second timeout)
                conn = pyodbc.connect(conn_str, timeout=3)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                conn.close()
                
                logger.info(f"Successfully connected to {description}: {server}")
                
                # Update settings with working server if different
                if server != current_server:
                    manager.set("db.server", server)
                    manager.set("db.last_working_server", server)
                    manager.set("db.last_working_description", description)
                    manager.save()
                    logger.info(f"Updated settings to use {description}")
                
                return conn_str, description
                
            except Exception as e:
                logger.warning(f"Failed to connect to {description}: {str(e)[:100]}")
                continue
        
        logger.error("All database connection attempts failed!")
        return None, None
    
    @classmethod
    def initialize_with_fallback(cls) -> bool:
        """
        Initialize connection pool with automatic fallback.
        
        Returns:
            True if successful, False otherwise
        """
        from app.dao.connection_pool import initialize_global_pool
        
        conn_str, description = cls.get_working_connection()
        
        if conn_str:
            # Show notification to user
            try:
                from PyQt5.QtWidgets import QApplication, QMessageBox
                app = QApplication.instance()
                if app and description != "Current Settings":
                    # Non-blocking notification
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Information)
                    msg.setWindowTitle("Bağlantı Değişti")
                    msg.setText(f"Otomatik olarak {description} sunucusuna bağlanıldı.")
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.setModal(False)
                    msg.show()
            except:
                pass  # GUI not ready yet
            
            return initialize_global_pool(conn_str)
        
        return False