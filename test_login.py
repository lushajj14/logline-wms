#!/usr/bin/env python3
"""Basit Login Testi"""

import os
import sys

# Path ayarları
project_root = os.path.dirname(__file__)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_login():
    """Login sistemi test et."""
    print("LOGIN TEST")
    print("="*50)
    
    try:
        from app.dao.users_new import UserDAO
        dao = UserDAO()
        
        print("\n1. Tablo kontrol:")
        if dao.check_tables_exist():
            print("[OK] Tablolar mevcut")
        else:
            print("[ERROR] Tablolar bulunamadı")
            print("  Lütfen CREATE_USER_TABLES.sql dosyasını çalıştırın")
            return
        
        print("\n2. Admin kullanıcı testi:")
        result = dao.authenticate("admin", "Admin123!")
        if result:
            print(f"[OK] Admin giriş başarılı: {result['username']} ({result['role']})")
        else:
            print("[ERROR] Admin giriş başarısız")
        
        print("\n3. Yanlış şifre testi:")
        result = dao.authenticate("admin", "WrongPassword")
        if not result:
            print("[OK] Yanlış şifre doğru şekilde reddedildi")
        else:
            print("[ERROR] Yanlış şifre kabul edildi!")
        
        print("\n4. Kullanıcı listesi:")
        users = dao.get_all_users()
        print(f"   Toplam kullanıcı: {len(users)}")
        for user in users:
            status = "Aktif" if user['is_active'] else "Pasif"
            print(f"   - {user['username']} | {user['role']} | {status}")
        
        print("\n5. AuthManager testi:")
        from app.models.user import get_auth_manager
        auth = get_auth_manager()
        
        result = auth.login("admin", "Admin123!")
        if result:
            user, token = result
            print(f"[OK] AuthManager login başarılı: {user.username}")
            print(f"   Token: {token[:30]}...")
            
            # Permission test
            print(f"   Orders view: {auth.has_permission('orders', 'view')}")
            print(f"   Users create: {auth.has_permission('users', 'create')}")
        else:
            print("[ERROR] AuthManager login başarısız")
    
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_login()