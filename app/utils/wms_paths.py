"""
WMS Path Management
===================
Centralized path management for WMS system.
Creates and manages all WMS folders in Documents directory.
"""

import os
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and frozen exe."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Development mode
        base_path = Path(__file__).resolve().parent.parent.parent
    
    return os.path.join(base_path, relative_path)

def get_wms_base_dir() -> Path:
    """Get or create the base WMS directory in Documents folder."""
    # Get Documents folder path (works on any Windows machine)
    documents = Path.home() / "Documents"
    
    # Create WMS base directory
    wms_dir = documents / "WMS"
    wms_dir.mkdir(parents=True, exist_ok=True)
    
    return wms_dir

def get_wms_folders() -> dict:
    """Get all WMS folder paths and create them if they don't exist."""
    base_dir = get_wms_base_dir()
    
    folders = {
        'base': base_dir,
        'labels': base_dir / 'labels',
        'picklists': base_dir / 'picklists',
        'reports': base_dir / 'reports',
        'logs': base_dir / 'logs',
        'temp': base_dir / 'temp',
        'backorders': base_dir / 'backorders',
        'output': base_dir / 'output',
        'exports': base_dir / 'exports',
        'imports': base_dir / 'imports',
        'backups': base_dir / 'backups',
    }
    
    # Create all folders
    for name, path in folders.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured folder exists: {path}")
        except Exception as e:
            logger.error(f"Could not create folder {name}: {e}")
    
    return folders

def get_label_path(filename: str) -> Path:
    """Get full path for a label file."""
    folders = get_wms_folders()
    return folders['labels'] / filename

def get_picklist_path(filename: str) -> Path:
    """Get full path for a picklist file."""
    folders = get_wms_folders()
    return folders['picklists'] / filename

def get_report_path(filename: str) -> Path:
    """Get full path for a report file."""
    folders = get_wms_folders()
    return folders['reports'] / filename

def get_temp_path(filename: str) -> Path:
    """Get full path for a temporary file."""
    folders = get_wms_folders()
    return folders['temp'] / filename

def ensure_wms_structure():
    """Ensure all WMS folders exist on startup."""
    folders = get_wms_folders()
    logger.info(f"WMS folder structure initialized at: {folders['base']}")
    return folders

# Initialize on import
if __name__ != "__main__":
    try:
        ensure_wms_structure()
    except Exception as e:
        logger.warning(f"Could not initialize WMS folders on import: {e}")