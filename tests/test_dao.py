"""
Tests for Data Access Object (DAO) Layer
=========================================
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from contextlib import contextmanager
import pyodbc


class TestConnectionPool:
    """Test connection pool functionality."""
    
    @patch("pyodbc.connect")
    def test_pool_initialization(self, mock_connect):
        """Test connection pool initialization."""
        from app.dao.connection_pool import ConnectionPool
        
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        pool = ConnectionPool(
            connection_string="test_connection",
            min_connections=2,
            max_connections=5
        )
        
        # Should create min_connections on init
        assert mock_connect.call_count == 2
        assert pool.stats["total_created"] == 2
    
    @patch("pyodbc.connect")
    def test_get_connection_from_pool(self, mock_connect):
        """Test getting connection from pool."""
        from app.dao.connection_pool import ConnectionPool
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        pool = ConnectionPool("test", min_connections=1, max_connections=3)
        
        with pool.get_connection() as conn:
            assert conn is not None
            assert pool.stats["total_borrowed"] == 1
        
        # Connection should be returned to pool
        assert pool.stats["total_returned"] == 1
    
    @patch("pyodbc.connect")
    def test_pool_max_connections(self, mock_connect):
        """Test pool respects max connections limit."""
        from app.dao.connection_pool import ConnectionPool
        import threading
        import time
        
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        
        pool = ConnectionPool("test", min_connections=1, max_connections=2)
        connections_held = []
        
        def get_and_hold():
            with pool.get_connection() as conn:
                connections_held.append(conn)
                time.sleep(0.1)
        
        threads = [threading.Thread(target=get_and_hold) for _ in range(3)]
        for t in threads:
            t.start()
        
        time.sleep(0.05)  # Let threads acquire connections
        
        # Only max_connections should be created
        assert pool.stats["total_created"] <= 2
        
        for t in threads:
            t.join()


class TestLogoDAO:
    """Test logo.py DAO functions."""
    
    @patch("app.dao.logo.get_conn")
    def test_fetch_one(self, mock_get_conn):
        """Test fetch_one function."""
        from app.dao.logo import fetch_one
        
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"id": 1, "name": "test"}
        mock_cursor.description = [("id",), ("name",)]
        
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        
        mock_get_conn.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=None)
        
        result = fetch_one("SELECT * FROM test WHERE id = ?", [1])
        
        assert result == {"id": 1, "name": "test"}
        mock_conn.execute.assert_called_once_with("SELECT * FROM test WHERE id = ?", [1])
    
    @patch("app.dao.logo.get_conn")
    def test_fetch_all(self, mock_get_conn):
        """Test fetch_all function."""
        from app.dao.logo import fetch_all
        
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, "test1"),
            (2, "test2")
        ]
        mock_cursor.description = [("id",), ("name",)]
        
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        
        mock_get_conn.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=None)
        
        result = fetch_all("SELECT * FROM test")
        
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["name"] == "test1"
        assert result[1]["id"] == 2
        assert result[1]["name"] == "test2"
    
    @patch("app.dao.logo.get_conn")
    def test_execute_query(self, mock_get_conn):
        """Test execute_query function."""
        from app.dao.logo import execute_query
        
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        
        mock_get_conn.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=None)
        
        rows_affected = execute_query("UPDATE test SET name = ? WHERE id = ?", ["updated", 1])
        
        assert rows_affected == 1
        mock_conn.execute.assert_called_once_with("UPDATE test SET name = ? WHERE id = ?", ["updated", 1])
        mock_conn.commit.assert_called_once()


class TestPagination:
    """Test pagination functionality."""
    
    @patch("app.dao.logo.fetch_one")
    @patch("app.dao.logo.fetch_all")
    def test_paginated_query(self, mock_fetch_all, mock_fetch_one):
        """Test paginated query execution."""
        from app.dao.pagination import PaginationHelper
        
        # Mock total count
        mock_fetch_one.return_value = {"total": 100}
        
        # Mock data fetch
        mock_fetch_all.return_value = [{"id": i} for i in range(1, 11)]
        
        helper = PaginationHelper()
        result = helper.paginate(
            base_query="SELECT * FROM orders",
            count_query="SELECT COUNT(*) as total FROM orders",
            page=1,
            page_size=10
        )
        
        assert result["pagination"]["total_count"] == 100
        assert result["pagination"]["current_page"] == 1
        assert result["pagination"]["page_size"] == 10
        assert result["pagination"]["total_pages"] == 10
        assert result["pagination"]["has_next"] is True
        assert result["pagination"]["has_previous"] is False
        assert len(result["data"]) == 10
    
    def test_pagination_metadata(self):
        """Test pagination metadata calculation."""
        from app.dao.pagination import PaginationHelper
        
        helper = PaginationHelper()
        metadata = helper._calculate_metadata(
            total_count=100,
            page=3,
            page_size=10
        )
        
        assert metadata["total_count"] == 100
        assert metadata["current_page"] == 3
        assert metadata["page_size"] == 10
        assert metadata["total_pages"] == 10
        assert metadata["has_next"] is True
        assert metadata["has_previous"] is True
        assert metadata["start_index"] == 21
        assert metadata["end_index"] == 30
    
    def test_pagination_edge_cases(self):
        """Test pagination edge cases."""
        from app.dao.pagination import PaginationHelper
        
        helper = PaginationHelper()
        
        # Last page
        metadata = helper._calculate_metadata(
            total_count=95,
            page=10,
            page_size=10
        )
        assert metadata["has_next"] is False
        assert metadata["has_previous"] is True
        assert metadata["end_index"] == 95
        
        # Single page
        metadata = helper._calculate_metadata(
            total_count=5,
            page=1,
            page_size=10
        )
        assert metadata["has_next"] is False
        assert metadata["has_previous"] is False
        assert metadata["total_pages"] == 1
        
        # Empty result
        metadata = helper._calculate_metadata(
            total_count=0,
            page=1,
            page_size=10
        )
        assert metadata["total_pages"] == 0
        assert metadata["has_next"] is False


class TestCacheLayer:
    """Test caching functionality."""
    
    def test_thread_safe_cache_basic(self):
        """Test basic cache operations."""
        from app.utils.thread_safe_cache import ThreadSafeCache
        
        cache = ThreadSafeCache(max_size=3)
        
        # Test set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Test missing key
        assert cache.get("missing") is None
        assert cache.get("missing", "default") == "default"
    
    def test_cache_max_size(self):
        """Test cache respects max size."""
        from app.utils.thread_safe_cache import ThreadSafeCache
        
        cache = ThreadSafeCache(max_size=2)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
    
    def test_cache_ttl(self):
        """Test cache TTL expiration."""
        from app.utils.thread_safe_cache import ThreadSafeCache
        import time
        
        cache = ThreadSafeCache(ttl_seconds=0.1)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        time.sleep(0.15)
        assert cache.get("key1") is None
    
    def test_cache_clear(self):
        """Test cache clearing."""
        from app.utils.thread_safe_cache import ThreadSafeCache
        
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size() == 0