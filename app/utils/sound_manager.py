"""
Sound Manager for Application
==============================
Centralized sound management to avoid duplication.
"""
from PyQt5.QtMultimedia import QSoundEffect
from app.utils.resource_manager import get_resource_manager
import app.settings as st


class SoundManager:
    """Centralized sound management."""
    
    # Sound names
    SOUND_OK = "ding.wav"
    SOUND_ERROR = "error.wav"
    SOUND_DUPLICATE = "bip.wav"
    SOUND_WARNING = "warning.wav"
    
    def __init__(self):
        self.resource_manager = get_resource_manager()
        self._enabled = True
        self._volume = 0.9
        self.apply_settings()
    
    def apply_settings(self):
        """Apply sound settings from configuration."""
        self._enabled = st.get("ui.sounds.enabled", True)
        self._volume = st.get("ui.sounds.volume", 0.9)
        
        # Update volume for all cached sounds
        if not self._enabled:
            self.resource_manager.set_sound_volume(0.0)
        else:
            self.resource_manager.set_sound_volume(self._volume)
    
    def play_ok(self):
        """Play success sound."""
        self._play(self.SOUND_OK)
    
    def play_error(self):
        """Play error sound."""
        self._play(self.SOUND_ERROR)
    
    def play_duplicate(self):
        """Play duplicate/warning sound."""
        self._play(self.SOUND_DUPLICATE)
    
    def play_warning(self):
        """Play warning sound."""
        self._play(self.SOUND_WARNING)
    
    def _play(self, sound_name: str):
        """
        Play a sound by name.
        
        Args:
            sound_name: Name of the sound file
        """
        if not self._enabled:
            return
        
        sound = self.resource_manager.get_sound(sound_name, self._volume)
        if sound:
            sound.play()
    
    def set_enabled(self, enabled: bool):
        """Enable or disable sounds."""
        self._enabled = enabled
        if not enabled:
            self.resource_manager.set_sound_volume(0.0)
        else:
            self.resource_manager.set_sound_volume(self._volume)
    
    def set_volume(self, volume: float):
        """Set sound volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))
        if self._enabled:
            self.resource_manager.set_sound_volume(self._volume)


# Global instance
_sound_manager = None


def get_sound_manager() -> SoundManager:
    """Get the global SoundManager instance."""
    global _sound_manager
    if _sound_manager is None:
        _sound_manager = SoundManager()
    return _sound_manager