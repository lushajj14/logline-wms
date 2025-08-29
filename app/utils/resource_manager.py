"""
Resource Manager for Memory Management
=======================================
Centralized resource management to prevent memory leaks.
"""
import weakref
import threading
from typing import Dict, Any, Optional
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ResourceManager:
    """Singleton resource manager for application-wide resources."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._sound_cache: Dict[str, QSoundEffect] = {}
        self._cache_lock = threading.Lock()
        self._references = weakref.WeakValueDictionary()
        
        # Sound directory
        self._sound_dir = Path(__file__).resolve().parents[2] / "sounds"
        
        logger.info("ResourceManager initialized")
    
    def get_sound(self, name: str, volume: float = 0.9) -> Optional[QSoundEffect]:
        """
        Get cached sound effect.
        
        Args:
            name: Sound file name (e.g., 'ding.wav')
            volume: Volume level (0.0 to 1.0)
            
        Returns:
            QSoundEffect instance or None if not found
        """
        with self._cache_lock:
            if name not in self._sound_cache:
                sound_path = self._sound_dir / name
                
                if not sound_path.exists():
                    logger.warning(f"Sound file not found: {sound_path}")
                    return None
                
                try:
                    sound = QSoundEffect()
                    sound.setSource(QUrl.fromLocalFile(str(sound_path)))
                    sound.setVolume(volume)
                    self._sound_cache[name] = sound
                    logger.debug(f"Loaded sound: {name}")
                except Exception as e:
                    logger.error(f"Failed to load sound {name}: {e}")
                    return None
            
            return self._sound_cache[name]
    
    def set_sound_volume(self, volume: float):
        """
        Set volume for all cached sounds.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        with self._cache_lock:
            for sound in self._sound_cache.values():
                if sound:
                    sound.setVolume(volume)
    
    def clear_sounds(self):
        """Clear all cached sounds to free memory."""
        with self._cache_lock:
            for sound in self._sound_cache.values():
                if sound:
                    try:
                        sound.stop()
                        sound.deleteLater()
                    except:
                        pass
            
            self._sound_cache.clear()
            logger.info("Sound cache cleared")
    
    def register_widget(self, widget_id: str, widget: Any):
        """
        Register a widget for lifecycle management.
        
        Args:
            widget_id: Unique widget identifier
            widget: Widget instance
        """
        self._references[widget_id] = widget
    
    def unregister_widget(self, widget_id: str):
        """
        Unregister a widget.
        
        Args:
            widget_id: Widget identifier
        """
        if widget_id in self._references:
            del self._references[widget_id]
    
    def cleanup(self):
        """Cleanup all resources."""
        self.clear_sounds()
        self._references.clear()
        logger.info("ResourceManager cleanup completed")
    
    def get_memory_usage(self) -> Dict[str, int]:
        """
        Get current memory usage statistics.
        
        Returns:
            Dictionary with memory usage info
        """
        return {
            'sound_cache_size': len(self._sound_cache),
            'registered_widgets': len(self._references),
            'sound_cache_names': list(self._sound_cache.keys())
        }


# Global instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get the global ResourceManager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def cleanup_resources():
    """Cleanup all resources (call on application exit)."""
    global _resource_manager
    if _resource_manager:
        _resource_manager.cleanup()
        _resource_manager = None