"""
WMS System - Build Configuration Helper
======================================
This module contains configuration helpers for PyInstaller builds.
It helps resolve common issues with path resolution and resource loading
when running as a frozen executable.
"""

import os
import sys
from pathlib import Path


def get_resource_path(relative_path):
    """
    Get absolute path to resource, works for both development and PyInstaller.
    
    Args:
        relative_path (str): Path relative to the application root
        
    Returns:
        str: Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Development mode - use the directory containing this file
        base_path = Path(__file__).resolve().parent
    
    return os.path.join(base_path, relative_path)


def get_app_data_path(relative_path):
    """
    Get path for application data that should persist between runs.
    Always uses Documents/WMS folder, never the exe directory.
    
    Args:
        relative_path (str): Path relative to the application data root
        
    Returns:
        str: Absolute path for persistent data
    """
    # Always use WMS directory in Documents
    wms_dir = Path.home() / "Documents" / "WMS"
    wms_dir.mkdir(parents=True, exist_ok=True)
    
    full_path = wms_dir / relative_path
    
    # Create directory if it doesn't exist
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    return str(full_path)


def is_frozen():
    """
    Check if running as PyInstaller executable.
    
    Returns:
        bool: True if running as frozen executable, False otherwise
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_executable_dir():
    """
    Get the directory containing the executable.
    
    Returns:
        str: Directory path
    """
    if is_frozen():
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parent


# Configuration for common paths used by the WMS system
WMS_PATHS = {
    'sounds': 'sounds',
    'fonts': 'fonts', 
    'app_sounds': 'app/sounds',
    'app_fonts': 'app/fonts',
    'picklists': 'app/picklists',
    'labels': 'app/labels',
    'reports': 'app/reports',
    'logs': 'app/logs',
    'output': 'output',
    'temp': 'temp',
}


def get_wms_path(path_key):
    """
    Get a standard WMS system path.
    
    Args:
        path_key (str): Key from WMS_PATHS dictionary
        
    Returns:
        str: Absolute path
    """
    if path_key not in WMS_PATHS:
        raise ValueError(f"Unknown path key: {path_key}")
    
    relative_path = WMS_PATHS[path_key]
    
    # For resource paths (sounds, fonts), use get_resource_path
    if path_key in ['sounds', 'fonts', 'app_sounds', 'app_fonts']:
        return get_resource_path(relative_path)
    
    # For data paths (outputs, logs), use get_app_data_path
    return get_app_data_path(relative_path)


def ensure_directories():
    """
    Ensure all required directories exist.
    Call this early in your application startup.
    """
    data_paths = ['picklists', 'labels', 'reports', 'logs', 'output', 'temp']
    
    for path_key in data_paths:
        path = get_wms_path(path_key)
        Path(path).mkdir(parents=True, exist_ok=True)
        print(f"Ensured directory: {path}")


if __name__ == "__main__":
    # Test the configuration
    print("WMS Build Configuration Test")
    print("=" * 40)
    print(f"Is frozen: {is_frozen()}")
    print(f"Executable dir: {get_executable_dir()}")
    print()
    
    print("Resource paths:")
    for key in ['sounds', 'fonts', 'app_sounds', 'app_fonts']:
        try:
            path = get_wms_path(key)
            exists = Path(path).exists()
            print(f"  {key}: {path} {'(exists)' if exists else '(missing)'}")
        except Exception as e:
            print(f"  {key}: ERROR - {e}")
    
    print()
    print("Data paths:")
    for key in ['picklists', 'labels', 'reports', 'logs', 'output', 'temp']:
        try:
            path = get_wms_path(key)
            exists = Path(path).exists()
            print(f"  {key}: {path} {'(exists)' if exists else '(missing)'}")
        except Exception as e:
            print(f"  {key}: ERROR - {e}")
    
    print()
    print("Creating directories...")
    ensure_directories()
    print("Done!")