"""
Remote Config Test Script
=========================
Config server bağlantısını test eder.
"""

import sys
import os

# Path'leri ayarla
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.remote_config import RemoteConfigClient
import json

def test_remote_config():
    """Remote config'i test et."""
    
    print("="*60)
    print("REMOTE CONFIG TEST")
    print("="*60)
    
    # Client oluştur
    client = RemoteConfigClient()
    
    print(f"\n[SERVER] URL: {client.server_url}")
    print(f"[MACHINE] ID: {client.machine_id}")
    print(f"[HOST] Name: {client.hostname}")
    print(f"[VERSION] App: {client.app_version}")
    
    print("\n" + "-"*60)
    print("Config çekiliyor...")
    print("-"*60)
    
    # Config çek
    config = client.fetch_config(use_cache=True)
    
    if config:
        print("\n[OK] Config basariyla alindi!\n")
        print("Alınan config değerleri:")
        print("-"*60)
        
        # Hassas bilgileri maskele
        for key, value in sorted(config.items())[:10]:  # İlk 10 değeri göster
            if "PASSWORD" in key or "SECRET" in key:
                print(f"  {key}: ***MASKED***")
            else:
                print(f"  {key}: {value}")
        
        if len(config) > 10:
            print(f"  ... ve {len(config)-10} değer daha")
        
        # Environment kontrolü
        print("\n" + "-"*60)
        print("Environment variable kontrolü:")
        print("-"*60)
        
        test_keys = ["LOGO_SQL_SERVER", "LOGO_SQL_DB", "LOGO_COMPANY_NR"]
        for key in test_keys:
            env_value = os.getenv(key)
            if env_value:
                print(f"  [OK] {key} = {env_value}")
            else:
                print(f"  [HATA] {key} ayarlanmamis!")
        
        # Update kontrolü
        print("\n" + "-"*60)
        print("Güncelleme kontrolü...")
        print("-"*60)
        
        update_info = client.check_update()
        if update_info:
            if update_info.get("update_available"):
                print(f"  [UYARI] Yeni versiyon mevcut: {update_info.get('latest_version')}")
                print(f"     İndirme: {update_info.get('download_url')}")
            else:
                print(f"  [OK] Guncel versiyon: {update_info.get('current_version')}")
        
    else:
        print("\n[HATA] Config alinamadi!")
        print("\nOlası sebepler:")
        print("  1. Config server çalışmıyor")
        print("  2. Network bağlantısı yok")
        print("  3. Firewall port 8001'i engelliyor")
        print("  4. Makine yetkilendirilmemiş")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    try:
        test_remote_config()
    except KeyboardInterrupt:
        print("\n\n[UYARI] Test iptal edildi.")
    except Exception as e:
        print(f"\n[HATA] Test hatasi: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nDevam etmek için Enter'a basın...")