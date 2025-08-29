"""
Database Connection Pool Implementation
=======================================
Thread-safe connection pool for pyodbc connections.
Provides connection pooling to improve database performance.

Usage:
    from app.dao.connection_pool import get_pooled_connection
    
    with get_pooled_connection() as conn:
        cursor = conn.execute("SELECT * FROM table")
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from queue import Queue, Empty, Full
from typing import Optional
import pyodbc
import os

logger = logging.getLogger(__name__)

class ConnectionPool:
    """Thread-safe database connection pool."""
    
    def __init__(
        self, 
        connection_string: str, 
        min_connections: int = 2,
        max_connections: int = 10,
        connection_timeout: int = 10,
        pool_timeout: int = 30
    ):
        """
        Initialize connection pool.
        
        Args:
            connection_string: ODBC connection string
            min_connections: Minimum connections to maintain
            max_connections: Maximum connections allowed
            connection_timeout: Timeout for individual connections (seconds)
            pool_timeout: Timeout to wait for available connection (seconds)
        """
        self.connection_string = connection_string
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.pool_timeout = pool_timeout
        
        # Thread-safe queue for available connections
        self._pool = Queue(maxsize=max_connections)
        self._active_connections = 0
        self._lock = threading.RLock()
        self._initialized = False
        
        # Statistics
        self._stats = {
            'total_created': 0,
            'total_borrowed': 0,
            'total_returned': 0,
            'current_active': 0,
            'current_idle': 0
        }
    
    def _create_connection(self) -> Optional[pyodbc.Connection]:
        """Create a new database connection."""
        try:
            conn = pyodbc.connect(
                self.connection_string, 
                timeout=self.connection_timeout,
                autocommit=False
            )
            
            # Set connection properties for better performance
            conn.setencoding('utf-8')
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            
            with self._lock:
                self._stats['total_created'] += 1
                
            logger.debug("New database connection created")
            return conn
            
        except pyodbc.Error as e:
            logger.error(f"Failed to create database connection: {e}")
            return None
    
    def _initialize_pool(self) -> bool:
        """Initialize the connection pool with minimum connections."""
        if self._initialized:
            return True
            
        logger.info(f"Initializing connection pool (min: {self.min_connections}, max: {self.max_connections})")
        
        success_count = 0
        for i in range(self.min_connections):
            conn = self._create_connection()
            if conn:
                try:
                    self._pool.put_nowait(conn)
                    success_count += 1
                    with self._lock:
                        self._active_connections += 1
                except Full:
                    conn.close()
                    break
            else:
                logger.warning(f"Failed to create initial connection {i+1}/{self.min_connections}")
        
        if success_count > 0:
            self._initialized = True
            logger.info(f"Connection pool initialized with {success_count} connections")
            return True
        else:
            logger.error("Failed to initialize connection pool - no connections created")
            return False
    
    def _is_connection_valid(self, conn: pyodbc.Connection) -> bool:
        """Check if a connection is still valid."""
        try:
            # Simple validation query
            cursor = conn.execute("SELECT 1")
            cursor.fetchone()
            return True
        except (pyodbc.Error, Exception):
            return False
    
    @contextmanager
    def get_connection(self, *, autocommit: bool = False):
        """
        Get a connection from the pool with context manager.
        
        Args:
            autocommit: Whether to enable autocommit mode
            
        Yields:
            pyodbc.Connection: Database connection
            
        Raises:
            RuntimeError: If unable to get connection from pool
        """
        if not self._initialized and not self._initialize_pool():
            raise RuntimeError("Connection pool initialization failed")
        
        conn = None
        start_time = time.time()
        
        try:
            # Try to get connection from pool
            try:
                conn = self._pool.get(timeout=self.pool_timeout)
                with self._lock:
                    self._stats['total_borrowed'] += 1
                    self._stats['current_active'] += 1
                    self._stats['current_idle'] = self._pool.qsize()
                    
            except Empty:
                # Pool is empty, try to create new connection if under limit
                with self._lock:
                    if self._active_connections < self.max_connections:
                        conn = self._create_connection()
                        if conn:
                            self._active_connections += 1
                            self._stats['total_borrowed'] += 1
                            self._stats['current_active'] += 1
                        else:
                            raise RuntimeError("Failed to create new connection")
                    else:
                        raise RuntimeError(f"Connection pool exhausted (max: {self.max_connections})")
            
            # Validate connection
            if conn and not self._is_connection_valid(conn):
                logger.warning("Invalid connection detected, creating new one")
                try:
                    conn.close()
                except:
                    pass
                conn = self._create_connection()
                if not conn:
                    raise RuntimeError("Failed to create replacement connection")
            
            # Set autocommit if requested
            if conn:
                conn.autocommit = autocommit
                
            logger.debug(f"Connection borrowed from pool (took {time.time() - start_time:.3f}s)")
            yield conn
            
        except Exception as e:
            logger.error(f"Error in get_connection: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._active_connections -= 1
            raise
            
        finally:
            # Return connection to pool
            if conn:
                try:
                    # Reset connection state
                    if conn.autocommit != False:
                        conn.autocommit = False
                    
                    # Rollback any uncommitted transactions
                    try:
                        conn.rollback()
                    except:
                        pass
                    
                    # Return to pool if still valid
                    if self._is_connection_valid(conn):
                        try:
                            self._pool.put_nowait(conn)
                            with self._lock:
                                self._stats['total_returned'] += 1
                                self._stats['current_active'] -= 1
                                self._stats['current_idle'] = self._pool.qsize()
                            logger.debug("Connection returned to pool")
                        except Full:
                            # Pool is full, close connection
                            conn.close()
                            with self._lock:
                                self._active_connections -= 1
                                self._stats['current_active'] -= 1
                    else:
                        # Connection is invalid, close and decrease count
                        try:
                            conn.close()
                        except:
                            pass
                        with self._lock:
                            self._active_connections -= 1
                            self._stats['current_active'] -= 1
                        logger.warning("Invalid connection discarded")
                        
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    try:
                        conn.close()
                    except:
                        pass
                    with self._lock:
                        self._active_connections -= 1
                        self._stats['current_active'] -= 1
    
    def get_stats(self) -> dict:
        """Get connection pool statistics."""
        with self._lock:
            return {
                **self._stats.copy(),
                'pool_size': self._pool.qsize(),
                'active_connections': self._active_connections,
                'max_connections': self.max_connections,
                'min_connections': self.min_connections,
                'initialized': self._initialized
            }
    
    def close_all(self):
        """Close all connections in the pool."""
        logger.info("Closing all connections in pool")
        
        # Close all connections in queue
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except (Empty, Exception) as e:
                logger.error(f"Error closing pooled connection: {e}")
        
        with self._lock:
            self._active_connections = 0
            self._initialized = False
            self._stats = {
                'total_created': 0,
                'total_borrowed': 0,
                'total_returned': 0,
                'current_active': 0,
                'current_idle': 0
            }
        
        logger.info("Connection pool closed")


# Global connection pool instance
_global_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def initialize_global_pool(
    connection_string: str = None,
    min_connections: int = None,
    max_connections: int = None,
    **kwargs
) -> bool:
    """
    Initialize the global connection pool.
    
    Args:
        connection_string: Database connection string (optional, will build from settings)
        min_connections: Minimum connections (default from env or 2)
        max_connections: Maximum connections (default from env or 10)
        **kwargs: Additional arguments for ConnectionPool
    
    Returns:
        bool: True if initialization successful
    """
    global _global_pool
    
    # Build connection string if not provided
    if connection_string is None:
        from app.settings_manager import get_manager
        manager = get_manager()
        
        # Get from settings first, then env, then defaults
        SERVER = manager.get("db.server", os.getenv("LOGO_SQL_SERVER", "192.168.5.100,1433"))
        DATABASE = manager.get("db.database", os.getenv("LOGO_SQL_DB", "logo"))
        USER = manager.get("db.user", os.getenv("LOGO_SQL_USER", "barkod1"))
        PASSWORD = manager.get("db.password", os.getenv("LOGO_SQL_PASSWORD", "Barkod14*"))
        
        # Get best available driver
        drivers = [d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d]
        drivers.sort(key=lambda s: int("".join(filter(str.isdigit, s))) or 0)
        DRIVER = os.getenv("LOGO_SQL_DRIVER") or (drivers[-1] if drivers else "SQL Server")
        
        connection_string = (
            f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
            f"UID={USER};PWD={PASSWORD};TrustServerCertificate=yes;"
        )
        
        logger.info(f"Using database connection: Server={SERVER}, Database={DATABASE}, User={USER}")
    
    # Get configuration from environment variables
    if min_connections is None:
        min_connections = int(os.getenv('DB_POOL_MIN_CONNECTIONS', '2'))
    if max_connections is None:
        max_connections = int(os.getenv('DB_POOL_MAX_CONNECTIONS', '10'))
    
    with _pool_lock:
        if _global_pool:
            logger.info("Global connection pool already initialized")
            return True
        
        try:
            _global_pool = ConnectionPool(
                connection_string=connection_string,
                min_connections=min_connections,
                max_connections=max_connections,
                **kwargs
            )
            logger.info("Global connection pool initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize global connection pool: {e}")
            return False


@contextmanager
def get_pooled_connection(*, autocommit: bool = False):
    """
    Get a connection from the global pool.
    Falls back to direct connection if pool is not available.
    
    Args:
        autocommit: Whether to enable autocommit mode
        
    Yields:
        pyodbc.Connection: Database connection
    """
    global _global_pool
    
    # Check if pool is available
    if _global_pool and _global_pool._initialized:
        try:
            with _global_pool.get_connection(autocommit=autocommit) as conn:
                yield conn
            return
        except Exception as e:
            logger.warning(f"Pool connection failed, falling back to direct connection: {e}")
    
    # Fallback to direct connection (without importing logo.py to avoid circular import)
    logger.debug("Using direct database connection (pool not available)")
    
    # Direct connection without circular import
    conn = None
    try:
        # Get connection string from settings first, then environment, then defaults
        import pyodbc
        from app.settings_manager import get_manager
        
        manager = get_manager()
        
        # Try settings.json first, then env, then defaults
        SERVER = manager.get("db.server", os.getenv("LOGO_SQL_SERVER", "192.168.5.100,1433"))
        DATABASE = manager.get("db.database", os.getenv("LOGO_SQL_DB", "logo"))
        USER = manager.get("db.user", os.getenv("LOGO_SQL_USER", "barkod1"))
        PASSWORD = manager.get("db.password", os.getenv("LOGO_SQL_PASSWORD", "Barkod14*"))
        CONN_TIMEOUT = int(os.getenv("DB_CONN_TIMEOUT", "10"))
        
        # Get best available driver
        drivers = [d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d]
        drivers.sort(key=lambda s: int("".join(filter(str.isdigit, s))) or 0)
        DRIVER = os.getenv("LOGO_SQL_DRIVER") or (drivers[-1] if drivers else "SQL Server")
        
        CONN_STR = (
            f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
            f"UID={USER};PWD={PASSWORD};TrustServerCertificate=yes;"
        )
        
        conn = pyodbc.connect(CONN_STR, timeout=CONN_TIMEOUT, autocommit=autocommit)
        yield conn
        
    except Exception as e:
        logger.error(f"Direct connection failed: {e}")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_pool_stats() -> Optional[dict]:
    """Get statistics from the global connection pool."""
    global _global_pool
    
    if _global_pool:
        return _global_pool.get_stats()
    return None


def close_global_pool():
    """Close the global connection pool."""
    global _global_pool
    
    with _pool_lock:
        if _global_pool:
            _global_pool.close_all()
            _global_pool = None
            logger.info("Global connection pool closed")


def reconnect_global_pool() -> bool:
    """
    Reconnect the global connection pool with new settings.
    This allows live updating of database connections.
    """
    global _global_pool
    
    logger.info("Reconnecting global connection pool with new settings...")
    
    # Close existing pool
    close_global_pool()
    
    # Re-initialize with new settings
    from app.settings_manager import get_manager
    manager = get_manager()
    
    # Get new settings
    SERVER = manager.get("db.server", os.getenv("LOGO_SQL_SERVER", "192.168.5.100,1433"))
    DATABASE = manager.get("db.database", os.getenv("LOGO_SQL_DB", "logo"))
    USER = manager.get("db.user", os.getenv("LOGO_SQL_USER", "barkod1"))
    PASSWORD = manager.get("db.password", os.getenv("LOGO_SQL_PASSWORD", "Barkod14*"))
    
    # Get best available driver
    drivers = [d for d in pyodbc.drivers() if d.startswith("ODBC Driver") and "SQL Server" in d]
    drivers.sort(key=lambda s: int("".join(filter(str.isdigit, s))) or 0)
    DRIVER = os.getenv("LOGO_SQL_DRIVER") or (drivers[-1] if drivers else "SQL Server")
    
    connection_string = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        f"UID={USER};PWD={PASSWORD};TrustServerCertificate=yes;"
    )
    
    # Initialize new pool
    success = initialize_global_pool(connection_string)
    
    if success:
        logger.info(f"Successfully reconnected to: Server={SERVER}, Database={DATABASE}")
    else:
        logger.error("Failed to reconnect connection pool")
    
    return success