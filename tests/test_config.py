"""
Tests for Configuration Management
===================================
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from app.config.env_config import EnvironmentConfig, ConfigurationError


class TestEnvironmentConfig:
    """Test environment configuration management."""
    
    def test_init_loads_env_file(self, tmp_path):
        """Test that .env file is loaded on initialization."""
        env_file = tmp_path / ".env.test"
        env_file.write_text("TEST_VAR=test_value\n")
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            config = EnvironmentConfig(str(env_file))
            assert config.env_file == str(env_file)
            assert not config.is_production
    
    def test_production_detection(self):
        """Test production environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            config = EnvironmentConfig()
            assert config.is_production
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            config = EnvironmentConfig()
            assert not config.is_production
    
    def test_require_with_valid_var(self):
        """Test require() with valid environment variable."""
        with patch.dict(os.environ, {"TEST_REQUIRED": "test_value"}, clear=True):
            config = EnvironmentConfig()
            value = config.require("TEST_REQUIRED")
            assert value == "test_value"
            assert "TEST_REQUIRED" in config.required_vars
    
    def test_require_with_missing_var(self):
        """Test require() with missing environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            config = EnvironmentConfig()
            with pytest.raises(ConfigurationError) as exc_info:
                config.require("MISSING_VAR", "This is required")
            assert "MISSING_VAR" in str(exc_info.value)
            assert "This is required" in str(exc_info.value)
    
    def test_get_with_default(self):
        """Test get() with default value."""
        with patch.dict(os.environ, {"EXISTING": "value"}, clear=True):
            config = EnvironmentConfig()
            
            # Existing variable
            assert config.get("EXISTING") == "value"
            
            # Non-existing variable with default
            assert config.get("NON_EXISTING", "default") == "default"
    
    def test_get_int(self):
        """Test get_int() type conversion."""
        with patch.dict(os.environ, {"INT_VAR": "42", "BAD_INT": "not_a_number"}, clear=True):
            config = EnvironmentConfig()
            
            assert config.get_int("INT_VAR") == 42
            assert config.get_int("BAD_INT", 10) == 10
            assert config.get_int("MISSING", 5) == 5
    
    def test_get_bool(self):
        """Test get_bool() type conversion."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("random", False)
        ]
        
        config = EnvironmentConfig()
        for value, expected in test_cases:
            with patch.dict(os.environ, {"BOOL_VAR": value}, clear=True):
                assert config.get_bool("BOOL_VAR") == expected
    
    def test_database_config(self):
        """Test database configuration retrieval."""
        env_vars = {
            "LOGO_SQL_SERVER": "test_server",
            "LOGO_SQL_DB": "test_db",
            "LOGO_SQL_USER": "test_user",
            "LOGO_SQL_PASSWORD": "test_pass",
            "LOGO_SQL_DRIVER": "Test Driver",
            "LOGO_COMPANY_NR": "001",
            "LOGO_PERIOD_NR": "02",
            "DB_CONN_TIMEOUT": "15"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = EnvironmentConfig()
            db_config = config.get_database_config()
            
            assert db_config["server"] == "test_server"
            assert db_config["database"] == "test_db"
            assert db_config["username"] == "test_user"
            assert db_config["password"] == "test_pass"
            assert db_config["driver"] == "Test Driver"
            assert db_config["company_nr"] == "001"
            assert db_config["period_nr"] == "02"
            assert db_config["timeout"] == 15
    
    def test_pool_config(self):
        """Test connection pool configuration."""
        env_vars = {
            "DB_USE_POOL": "true",
            "DB_POOL_MIN_CONNECTIONS": "5",
            "DB_POOL_MAX_CONNECTIONS": "20",
            "DB_POOL_TIMEOUT": "45"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = EnvironmentConfig()
            pool_config = config.get_pool_config()
            
            assert pool_config["enabled"] is True
            assert pool_config["min_connections"] == 5
            assert pool_config["max_connections"] == 20
            assert pool_config["pool_timeout"] == 45
    
    def test_api_config_development(self):
        """Test API configuration in development mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            with patch("secrets.token_urlsafe", return_value="generated_secret"):
                config = EnvironmentConfig()
                api_config = config.get_api_config()
                
                assert api_config["secret_key"] == "generated_secret"
                assert api_config["algorithm"] == "HS256"
                assert api_config["token_expire_minutes"] == 120
    
    def test_api_config_production_without_secret(self):
        """Test API configuration in production without secret."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            with patch("sys.exit") as mock_exit:
                config = EnvironmentConfig()
                config.get_api_config()
                mock_exit.assert_called_once()
    
    def test_validate_all_success(self):
        """Test validate_all() with all required variables."""
        env_vars = {
            "ENVIRONMENT": "development",
            "LOGO_SQL_SERVER": "server",
            "LOGO_SQL_DB": "db",
            "LOGO_SQL_USER": "user",
            "LOGO_SQL_PASSWORD": "pass"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = EnvironmentConfig()
            assert config.validate_all() is True
    
    def test_validate_all_missing_vars(self):
        """Test validate_all() with missing variables."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            config = EnvironmentConfig()
            assert config.validate_all() is False