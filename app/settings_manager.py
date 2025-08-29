#!/usr/bin/env python3
"""
Enhanced Settings Manager with JSON Persistence
================================================
Manages application settings with JSON file persistence,
environment variable support, and secure credential handling.
"""

import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Determine base directory
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    SETTINGS_FILE = BASE_DIR / "settings.json"
else:
    BASE_DIR = Path(__file__).resolve().parents[2]
    SETTINGS_FILE = BASE_DIR / "settings.json"

# Alternative user settings location
USER_SETTINGS_FILE = Path.home() / ".wms_settings" / "settings.json"

# Default settings structure
DEFAULTS: Dict[str, Any] = {
    "version": "2.0.0",
    "ui": {
        "theme": "system",
        "font_pt": 10,
        "toast_secs": 3,
        "lang": "TR",
        "sounds": {
            "enabled": True,
            "volume": 0.9
        },
        "auto_focus": True,
        "auto_refresh": 30
    },
    "scanner": {
        "prefixes": {"D1-": "0", "D3-": "1"},
        "over_scan_tol": 0,
        "auto_print": False,
        "beep_on_scan": True
    },
    "loader": {
        "auto_refresh": 30,
        "block_incomplete": True,
        "show_completed": False,
        "auto_close_on_complete": False
    },
    "db": {
        # DB settings now come from environment variables
        # These are just display defaults
        "retry": 3,
        "heartbeat": 10,
        "pool_enabled": True,
        "pool_min": 2,
        "pool_max": 10,
        "cache_enabled": True,
        "cache_ttl": 300
    },
    "paths": {
        "label_dir": str(Path.home() / "Documents" / "WMS" / "labels"),
        "export_dir": str(Path.home() / "Desktop"),
        "log_dir": str(Path.home() / "WMS" / "logs"),
        "backup_dir": str(Path.home() / "WMS" / "backups"),
        "font_dir": str(BASE_DIR / "fonts")
    },
    "print": {
        "label_printer": "",
        "doc_printer": "",
        "label_tpl": "default.tpl",
        "auto_open": True,
        "copies": 1,
        "paper_size": "A4"
    },
    "advanced": {
        "debug_mode": False,
        "log_level": "INFO",
        "backup_on_startup": True,
        "check_updates": True,
        "telemetry_enabled": False
    },
    "last_updated": None
}


class SettingsManager:
    """Enhanced settings manager with JSON persistence."""
    
    def __init__(self, settings_file: Optional[Path] = None):
        """
        Initialize settings manager.
        
        Args:
            settings_file: Custom settings file path
        """
        self.settings_file = settings_file or SETTINGS_FILE
        self._settings: Dict[str, Any] = {}
        self._observers = []
        self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load settings from JSON file with fallback to defaults."""
        # Start with defaults
        self._settings = self._deep_copy(DEFAULTS)
        
        # Try to load from file
        settings_files = [self.settings_file, USER_SETTINGS_FILE]
        
        for file_path in settings_files:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        user_settings = json.load(f)
                        self._deep_update(self._settings, user_settings)
                        logger.info(f"Settings loaded from {file_path}")
                        break
                except Exception as e:
                    logger.error(f"Failed to load settings from {file_path}: {e}")
        
        # Override with environment variables for sensitive data
        self._apply_env_overrides()
        
        # Ensure required directories exist
        self._ensure_directories()
        
        return self._settings
    
    def save(self) -> bool:
        """Save current settings to JSON file."""
        try:
            # Update timestamp
            self._settings["last_updated"] = datetime.now().isoformat()
            
            # Create backup if exists
            if self.settings_file.exists():
                backup_path = self.settings_file.with_suffix('.backup.json')
                backup_path.write_text(self.settings_file.read_text())
            
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save settings (exclude sensitive data)
            save_data = self._prepare_for_save(self._settings)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Settings saved to {self.settings_file}")
            
            # Notify observers
            self._notify_observers()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get setting value by dot-notation path.
        
        Args:
            path: Dot-separated path (e.g., "ui.theme")
            default: Default value if path not found
            
        Returns:
            Setting value or default
        """
        current = self._settings
        
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
    
    def set(self, path: str, value: Any, auto_save: bool = True) -> None:
        """
        Set setting value by dot-notation path.
        
        Args:
            path: Dot-separated path (e.g., "ui.theme")
            value: Value to set
            auto_save: Automatically save to disk
        """
        parts = path.split(".")
        current = self._settings
        
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        
        current[parts[-1]] = value
        
        if auto_save:
            self.save()
    
    def reset_to_defaults(self, section: Optional[str] = None) -> None:
        """
        Reset settings to defaults.
        
        Args:
            section: Specific section to reset (e.g., "ui") or None for all
        """
        if section:
            if section in DEFAULTS:
                self._settings[section] = self._deep_copy(DEFAULTS[section])
        else:
            self._settings = self._deep_copy(DEFAULTS)
        
        self.save()
    
    def export_settings(self, file_path: Path) -> bool:
        """Export settings to a file."""
        try:
            save_data = self._prepare_for_save(self._settings)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to export settings: {e}")
            return False
    
    def import_settings(self, file_path: Path) -> bool:
        """Import settings from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            
            # Validate version compatibility
            if imported.get("version", "1.0.0") < "2.0.0":
                logger.warning("Importing old version settings, some values may be reset")
            
            self._deep_update(self._settings, imported)
            self.save()
            return True
            
        except Exception as e:
            logger.error(f"Failed to import settings: {e}")
            return False
    
    def add_observer(self, callback):
        """Add observer for settings changes."""
        self._observers.append(callback)
    
    def _notify_observers(self):
        """Notify all observers of settings change."""
        for callback in self._observers:
            try:
                callback(self._settings)
            except Exception as e:
                logger.error(f"Observer notification failed: {e}")
    
    def _deep_copy(self, obj: Any) -> Any:
        """Deep copy a nested dictionary."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    def _deep_update(self, dst: Dict, src: Dict) -> None:
        """Deep update nested dictionaries."""
        for key, value in src.items():
            if key in dst and isinstance(dst[key], dict) and isinstance(value, dict):
                self._deep_update(dst[key], value)
            else:
                dst[key] = value
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides for sensitive settings."""
        # Database settings from environment
        if os.getenv("LOGO_SQL_SERVER"):
            self._settings.setdefault("db_display", {})
            self._settings["db_display"]["server"] = os.getenv("LOGO_SQL_SERVER")
            self._settings["db_display"]["database"] = os.getenv("LOGO_SQL_DB", "")
            self._settings["db_display"]["user"] = os.getenv("LOGO_SQL_USER", "")
        
        # Pool settings from environment
        if os.getenv("DB_USE_POOL"):
            self._settings["db"]["pool_enabled"] = os.getenv("DB_USE_POOL", "true").lower() in ("true", "1", "yes")
            self._settings["db"]["pool_min"] = int(os.getenv("DB_POOL_MIN_CONNECTIONS", "2"))
            self._settings["db"]["pool_max"] = int(os.getenv("DB_POOL_MAX_CONNECTIONS", "10"))
        
        # Cache settings
        if os.getenv("CACHE_TTL_SECONDS"):
            self._settings["db"]["cache_ttl"] = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    
    def _prepare_for_save(self, data: Dict) -> Dict:
        """Prepare settings for saving (remove sensitive data)."""
        save_data = self._deep_copy(data)
        
        # Don't save database credentials
        save_data.pop("db_display", None)
        
        # Don't save temporary or runtime data
        for key in ["_temp", "_runtime", "_cache"]:
            save_data.pop(key, None)
        
        return save_data
    
    def _ensure_directories(self):
        """Ensure all configured directories exist."""
        for path_key in ["label_dir", "export_dir", "log_dir", "backup_dir", "font_dir"]:
            path = self.get(f"paths.{path_key}")
            if path:
                Path(path).mkdir(parents=True, exist_ok=True)


# Global instance
_manager: Optional[SettingsManager] = None


def get_manager() -> SettingsManager:
    """Get global settings manager instance."""
    global _manager
    if _manager is None:
        _manager = SettingsManager()
    return _manager


# Backward compatibility functions
def reload() -> Dict[str, Any]:
    """Reload settings from disk."""
    return get_manager().load()


def load() -> Dict[str, Any]:
    """Alias for reload."""
    return reload()


def get(path: str, default: Any = None) -> Any:
    """Get setting value."""
    return get_manager().get(path, default)


def set(path: str, value: Any) -> None:
    """Set setting value."""
    get_manager().set(path, value)


def save() -> None:
    """Save settings to disk."""
    get_manager().save()


# Initialize on import
reload()