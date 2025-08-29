"""
Pytest Configuration and Fixtures
==================================
Shared test fixtures and configuration.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["LOGO_SQL_SERVER"] = "test_server"
os.environ["LOGO_SQL_DB"] = "test_db"
os.environ["LOGO_SQL_USER"] = "test_user"
os.environ["LOGO_SQL_PASSWORD"] = "test_password"
os.environ["API_SECRET"] = "test-secret-key-for-testing-only"
os.environ["DB_USE_POOL"] = "false"


@pytest.fixture
def mock_db_connection():
    """Mock database connection for testing."""
    with patch("pyodbc.connect") as mock_connect:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn


@pytest.fixture
def test_env_config():
    """Test environment configuration."""
    from app.config.env_config import EnvironmentConfig
    config = EnvironmentConfig(".env.test")
    return config


@pytest.fixture
def mock_sound_manager():
    """Mock sound manager for testing."""
    from unittest.mock import MagicMock
    sound_manager = MagicMock()
    sound_manager.play_ok = MagicMock()
    sound_manager.play_error = MagicMock()
    sound_manager.play_warning = MagicMock()
    return sound_manager


@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return [
        {
            "LOGICALREF": 1,
            "FICHENO": "ORD001",
            "DATE_": "2024-01-15",
            "DOCODE": "DOC001",
            "SOURCEINDEX": 1,
            "CLIENTREF": 101,
            "NAME": "Test Customer 1",
            "GROSSTOTAL": 1000.00,
            "NETTOTAL": 900.00
        },
        {
            "LOGICALREF": 2,
            "FICHENO": "ORD002",
            "DATE_": "2024-01-16",
            "DOCODE": "DOC002",
            "SOURCEINDEX": 2,
            "CLIENTREF": 102,
            "NAME": "Test Customer 2",
            "GROSSTOTAL": 2000.00,
            "NETTOTAL": 1800.00
        }
    ]


@pytest.fixture
def sample_pagination_data():
    """Sample pagination response data."""
    return {
        "data": [],
        "pagination": {
            "total_count": 100,
            "page_size": 10,
            "current_page": 1,
            "total_pages": 10,
            "has_next": True,
            "has_previous": False,
            "start_index": 1,
            "end_index": 10
        }
    }