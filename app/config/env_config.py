"""
Environment Configuration Manager
==================================
Secure environment variable management with validation.
Production-ready configuration system.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


class EnvironmentConfig:
    """Centralized environment configuration with validation."""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize environment configuration.
        
        Args:
            env_file: Path to .env file (optional)
        """
        # Determine the base directory
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            base_dir = Path(sys.executable).parent
        else:
            # Running in development
            base_dir = Path(__file__).resolve().parent.parent.parent
        
        # Set env file path
        if env_file:
            self.env_file = env_file
        else:
            self.env_file = str(base_dir / ".env")
        
        self.is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        self.required_vars = {}
        self.optional_vars = {}
        
        # Try to load .env file from multiple locations
        env_locations = [
            self.env_file,
            str(base_dir / ".env"),
            ".env",
            str(Path.cwd() / ".env")
        ]
        
        env_loaded = False
        for env_path in env_locations:
            if Path(env_path).exists():
                load_dotenv(env_path)
                logger.info(f"Loaded environment from {env_path}")
                env_loaded = True
                break
        
        # Eğer .env bulunamazsa, remote config'i dene
        if not env_loaded:
            logger.warning("No .env file found, trying remote config...")
            try:
                from app.config.remote_config import RemoteConfigClient
                client = RemoteConfigClient()
                config = client.fetch_config(use_cache=True)
                
                if config:
                    logger.info("Successfully loaded config from remote server")
                    # Remote config zaten environment'a yüklendi
                else:
                    logger.warning("Remote config failed, using defaults")
            except Exception as e:
                logger.error(f"Remote config error: {e}")
                logger.warning("No .env file found in any expected location")
    
    def require(self, key: str, description: str = "") -> str:
        """
        Get required environment variable.
        
        Args:
            key: Environment variable name
            description: Description for error message
            
        Returns:
            Environment variable value
            
        Raises:
            ConfigurationError: If variable is not set
        """
        value = os.getenv(key)
        
        if value is None or value.strip() == "":
            error_msg = f"Required environment variable '{key}' is not set"
            if description:
                error_msg += f" ({description})"
            
            # In production, this is critical
            if self.is_production:
                logger.critical(error_msg)
                sys.exit(1)
            else:
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
        
        self.required_vars[key] = value
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get optional environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value if not set
            
        Returns:
            Environment variable value or default
        """
        value = os.getenv(key, default)
        self.optional_vars[key] = value
        return value
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get environment variable as integer."""
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            logger.warning(f"Invalid integer value for {key}, using default: {default}")
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get environment variable as boolean."""
        value = self.get(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def validate_all(self) -> bool:
        """
        Validate all required environment variables.
        
        Returns:
            True if all valid, False otherwise
        """
        missing = []
        
        # Check database configuration
        db_vars = [
            ("LOGO_SQL_SERVER", "Database server address"),
            ("LOGO_SQL_DB", "Database name"),
            ("LOGO_SQL_USER", "Database username"),
            ("LOGO_SQL_PASSWORD", "Database password")
        ]
        
        for var, desc in db_vars:
            try:
                self.require(var, desc)
            except ConfigurationError:
                missing.append(f"{var} - {desc}")
        
        # Check API configuration
        if self.is_production:
            try:
                self.require("API_SECRET", "API JWT secret key")
            except ConfigurationError:
                missing.append("API_SECRET - API JWT secret key")
        
        if missing:
            logger.error("Missing required environment variables:")
            for var in missing:
                logger.error(f"  - {var}")
            
            if self.is_production:
                logger.critical("Cannot start in production without required configuration")
                sys.exit(1)
            return False
        
        return True
    
    def get_database_config(self) -> Dict[str, str]:
        """
        Get database configuration with validation.
        
        Returns:
            Dictionary with database configuration
        """
        config = {
            "server": self.require("LOGO_SQL_SERVER", "Database server"),
            "database": self.require("LOGO_SQL_DB", "Database name"),
            "username": self.require("LOGO_SQL_USER", "Database user"),
            "password": self.require("LOGO_SQL_PASSWORD", "Database password"),
            "driver": self.get("LOGO_SQL_DRIVER"),
            "company_nr": self.get("LOGO_COMPANY_NR", "025"),
            "period_nr": self.get("LOGO_PERIOD_NR", "01"),
            "timeout": self.get_int("DB_CONN_TIMEOUT", 10)
        }
        
        # Auto-detect driver if not specified
        if not config["driver"]:
            import pyodbc
            drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
            config["driver"] = drivers[-1] if drivers else "SQL Server"
        
        return config
    
    def get_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration."""
        return {
            "enabled": self.get_bool("DB_USE_POOL", True),
            "min_connections": self.get_int("DB_POOL_MIN_CONNECTIONS", 2),
            "max_connections": self.get_int("DB_POOL_MAX_CONNECTIONS", 10),
            "pool_timeout": self.get_int("DB_POOL_TIMEOUT", 30)
        }
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        secret = self.get("API_SECRET")
        
        if not secret and self.is_production:
            logger.critical("API_SECRET must be set in production")
            sys.exit(1)
        
        # Generate secret for development if not set
        if not secret:
            import secrets
            secret = secrets.token_urlsafe(32)
            logger.warning(f"Generated temporary API secret: {secret}")
            logger.warning("Set API_SECRET environment variable for production")
        
        return {
            "secret_key": secret,
            "algorithm": self.get("API_ALGORITHM", "HS256"),
            "token_expire_minutes": self.get_int("API_TOKEN_EXPIRE_MINUTES", 120)
        }
    
    def print_config_status(self):
        """Print configuration status for debugging."""
        print("\n" + "="*60)
        print("ENVIRONMENT CONFIGURATION STATUS")
        print("="*60)
        print(f"Environment: {('PRODUCTION' if self.is_production else 'DEVELOPMENT')}")
        print(f"Config file: {self.env_file}")
        print(f"Required vars set: {len(self.required_vars)}")
        print(f"Optional vars set: {len(self.optional_vars)}")
        
        if not self.is_production:
            print("\nRequired variables:")
            for key in self.required_vars:
                # Mask sensitive values
                if "PASSWORD" in key or "SECRET" in key:
                    print(f"  {key}: ***")
                else:
                    print(f"  {key}: {self.required_vars[key]}")
        
        print("="*60 + "\n")


# Global configuration instance
_config: Optional[EnvironmentConfig] = None


def get_config() -> EnvironmentConfig:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = EnvironmentConfig()
    return _config


def init_config(env_file: Optional[str] = None) -> EnvironmentConfig:
    """
    Initialize global configuration.
    
    Args:
        env_file: Path to .env file
        
    Returns:
        EnvironmentConfig instance
    """
    global _config
    _config = EnvironmentConfig(env_file)
    _config.validate_all()
    return _config