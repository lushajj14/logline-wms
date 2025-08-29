#!/usr/bin/env python3
"""Admin şifresini düzelt"""

import os
import sys

# Path ayarları
project_root = os.path.dirname(__file__)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def fix_admin_password():
    """Admin şifresini düzelt"""
    print("ADMIN ŞİFRE DÜZELTİMİ")
    print("="*40)
    
    try:
        from app.dao.users_new import UserDAO
        import bcrypt
        
        dao = UserDAO()
        
        # Yeni hash oluştur
        password = "Admin123!"
        salt = bcrypt.gensalt()
        new_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        print(f"Yeni hash: {new_hash}")
        
        # Admin kullanıcısını güncelle
        from app.dao.logo import execute_query
        
        rows = execute_query(
            """
            UPDATE WMS_KULLANICILAR 
            SET SIFRE_HASH = ? 
            WHERE KULLANICI_ADI = 'admin'
            """,
            [new_hash]
        )
        
        if rows > 0:
            print(f"[OK] Admin şifresi güncellendi ({rows} kayıt)")
            
            # Test et
            result = dao.authenticate("admin", password)
            if result:
                print(f"[OK] Admin giriş test başarılı: {result['username']}")
            else:
                print("[ERROR] Admin giriş test başarısız")
        else:
            print("[ERROR] Admin kullanıcısı bulunamadı")
    
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_admin_password()