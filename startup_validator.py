#!/usr/bin/env python3
"""
Startup Database Configuration Validator
=========================================
Validates database settings before application starts.
Provides recovery options if settings are invalid.
"""

import sys
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def validate_startup_config():
    """Validate database configuration at startup."""
    
    # Check if running with reset flag
    if "--reset-db" in sys.argv:
        reset_to_defaults()
        return True
    
    # Load settings
    settings_file = Path.home() / "Desktop" / "settings.json"
    
    if not settings_file.exists():
        # No settings file, will use .env defaults
        return True
    
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except Exception as e:
        print(f"⚠️  Ayarlar dosyası okunamadı: {e}")
        return prompt_for_reset()
    
    # Check database settings
    db_settings = settings.get('db', {})
    server = db_settings.get('server', '')
    
    # Known good configurations
    SAFE_CONFIGS = [
        "192.168.5.100,1433",   # Ana sunucu (VPN/Local)
        "78.135.108.160,1433",  # Yedek sunucu (Public Internet)
        "localhost,1433",       # Local test
        "127.0.0.1,1433",       # Local test
    ]
    
    if server and server not in SAFE_CONFIGS:
        print(f"\n⚠️  UYARI: Riskli veritabanı ayarı tespit edildi!")
        print(f"   Mevcut: {server}")
        print(f"   Önerilen: 192.168.5.100,1433")
        print(f"\nSeçenekler:")
        print(f"1. Varsayılan ayarlara dön (192.168.5.100,1433)")
        print(f"2. Riski kabul et ve devam et")
        print(f"3. Programı kapat")
        
        choice = input("\nSeçiminiz (1/2/3): ").strip()
        
        if choice == "1":
            return reset_db_config(settings_file)
        elif choice == "2":
            print("⚠️  Risk kabul edildi. Devam ediliyor...")
            return True
        else:
            print("Program kapatılıyor...")
            sys.exit(0)
    
    return True


def reset_db_config(settings_file: Path) -> bool:
    """Reset database configuration to safe defaults."""
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # Reset to safe defaults
        settings['db']['server'] = "192.168.5.100,1433"
        settings['db']['database'] = "logo"
        settings['db']['user'] = "barkod1"
        settings['db']['password'] = "Barkod14*"
        
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        print("✅ Veritabanı ayarları varsayılana döndürüldü.")
        return True
        
    except Exception as e:
        print(f"❌ Ayarlar sıfırlanamadı: {e}")
        return False


def reset_to_defaults():
    """Reset all settings to defaults."""
    settings_file = Path.home() / "Desktop" / "settings.json"
    
    if settings_file.exists():
        backup_file = settings_file.with_suffix('.json.backup')
        settings_file.rename(backup_file)
        print(f"✅ Mevcut ayarlar yedeklendi: {backup_file}")
    
    print("✅ Varsayılan ayarlar yüklendi.")
    return True


def prompt_for_reset() -> bool:
    """Prompt user for reset options."""
    print("\nAyarlar dosyası bozuk veya okunamıyor.")
    print("1. Varsayılan ayarlarla başlat")
    print("2. Programı kapat")
    
    choice = input("\nSeçiminiz (1/2): ").strip()
    
    if choice == "1":
        return reset_to_defaults()
    else:
        sys.exit(0)


if __name__ == "__main__":
    # This can be imported and called from main.py
    if not validate_startup_config():
        sys.exit(1)
    
    print("✅ Veritabanı ayarları kontrol edildi.")