"""
Environment Validation Script
==============================
Validates all required environment variables at application startup.
"""

import sys
import logging
from typing import List, Tuple
from app.config.env_config import get_config, ConfigurationError

logger = logging.getLogger(__name__)


def validate_environment() -> Tuple[bool, List[str]]:
    """
    Validate all required environment variables.
    
    Returns:
        Tuple of (success: bool, errors: List[str])
    """
    errors = []
    config = get_config()
    
    # Validate database configuration
    try:
        db_config = config.get_database_config()
        logger.info(f"Database config validated: {db_config['server']}/{db_config['database']}")
    except ConfigurationError as e:
        errors.append(f"Database config error: {e}")
    
    # Validate API configuration
    try:
        api_config = config.get_api_config()
        if config.is_production and len(api_config["secret_key"]) < 32:
            errors.append("API secret key must be at least 32 characters in production")
        logger.info("API config validated")
    except Exception as e:
        errors.append(f"API config error: {e}")
    
    # Validate pool configuration
    try:
        pool_config = config.get_pool_config()
        if pool_config["max_connections"] < pool_config["min_connections"]:
            errors.append("Pool max_connections must be >= min_connections")
        logger.info(f"Pool config validated: min={pool_config['min_connections']}, max={pool_config['max_connections']}")
    except Exception as e:
        errors.append(f"Pool config error: {e}")
    
    # Additional checks
    if config.is_production:
        # Production-specific checks
        if config.get_bool("APP_DEBUG", False):
            errors.append("APP_DEBUG must be False in production")
        
        if config.get("APP_LOG_LEVEL", "INFO") == "DEBUG":
            errors.append("APP_LOG_LEVEL should not be DEBUG in production")
    
    return len(errors) == 0, errors


def run_validation(exit_on_error: bool = True) -> bool:
    """
    Run environment validation with optional exit on error.
    
    Args:
        exit_on_error: Exit application if validation fails
        
    Returns:
        True if validation passed, False otherwise
    """
    config = get_config()
    
    print("\n" + "="*60)
    print("ENVIRONMENT VALIDATION")
    print("="*60)
    print(f"Environment: {'PRODUCTION' if config.is_production else 'DEVELOPMENT'}")
    print(f"Config file: {config.env_file}")
    print("-"*60)
    
    success, errors = validate_environment()
    
    if success:
        print("[OK] All environment variables validated successfully")
        print("="*60 + "\n")
        return True
    else:
        print("[ERROR] Validation errors found:")
        for error in errors:
            print(f"  - {error}")
        print("="*60 + "\n")
        
        if exit_on_error and config.is_production:
            logger.critical("Environment validation failed in production")
            sys.exit(1)
        
        return False


if __name__ == "__main__":
    # Run validation when script is executed directly
    run_validation(exit_on_error=False)