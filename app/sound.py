"""
app.sound  –  Uygulama genelinde ses yönetimi
• loader_page / scanner_page gibi yerlerde üretilen QSoundEffect objelerini
  register() ile bildiriyoruz.
• set_global_volume() hem ses seviyesini hem de “enabled” bayrağını uygular.
"""
from __future__ import annotations
from typing import List
from PyQt5.QtMultimedia import QSoundEffect

# Bellekte tutulan tüm ses efektleri
_SFX: List[QSoundEffect] = []

def register(sfx: QSoundEffect) -> None:
    """Her oluşturulan QSoundEffect, merkezi kontrolde kullanılsın diye kaydedilir."""
    _SFX.append(sfx)

def set_global_volume(vol: float = 0.9, *, enabled: bool = True) -> None:
    """
    • vol : 0.0-1.0 arası seviye (ayarlar menüsündeki % değeri /100)
    • enabled = False ise ses tamamen kapatılır.
    """
    level = vol if enabled else 0.0
    for s in _SFX:
        s.setVolume(level)
