"""
User Data Access Object - Yeni Tablo Yapısı
============================================
Türkçe tablo adları ile kullanıcı veritabanı işlemleri.
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging
import bcrypt
from app.dao.logo import fetch_one, fetch_all, execute_query, get_conn

logger = logging.getLogger(__name__)


class UserDAO:
    """Kullanıcı veritabanı işlemleri."""
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Kullanıcı adı ve şifre ile giriş doğrulama.
        
        Args:
            username: Kullanıcı adı
            password: Düz metin şifre
            
        Returns:
            Başarılıysa kullanıcı bilgileri, değilse None
        """
        try:
            # Kullanıcıyı bul ve şifreyi kontrol et
            user = fetch_one(
                """
                SELECT 
                    LOGICALREF,
                    KULLANICI_ADI,
                    EMAIL,
                    SIFRE_HASH,
                    AD_SOYAD,
                    ROL,
                    AKTIF,
                    KILITLI_TARIH,
                    BASARISIZ_GIRIS
                FROM WMS_KULLANICILAR 
                WHERE KULLANICI_ADI = ? OR EMAIL = ?
                """,
                [username, username]
            )
            
            if not user:
                logger.warning(f"User not found: {username}")
                return None
            
            # Hesap kilitli mi kontrol et
            if user['kilitli_tarih'] and user['kilitli_tarih'] > datetime.now():
                logger.warning(f"Account locked: {username}")
                return None
            
            # Hesap aktif mi kontrol et
            if not user['aktif']:
                logger.warning(f"Account inactive: {username}")
                return None
            
            # Şifreyi doğrula
            if not self._verify_password(password, user['sifre_hash']):
                # Başarısız deneme sayısını artır
                self._update_failed_attempts(user['logicalref'])
                return None
            
            # Başarılı giriş: son giriş tarihini güncelle, başarısız denemeleri sıfırla
            execute_query(
                """
                UPDATE WMS_KULLANICILAR 
                SET SON_GIRIS = GETDATE(), 
                    BASARISIZ_GIRIS = 0, 
                    KILITLI_TARIH = NULL,
                    GUNCELLEME_TARIHI = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [user['logicalref']]
            )
            
            # Kullanıcı bilgilerini döndür (şifre hash'i olmadan)
            return {
                'id': user['logicalref'],
                'username': user['kullanici_adi'],
                'email': user['email'],
                'full_name': user['ad_soyad'],
                'role': user['rol'],
                'is_active': user['aktif']
            }
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """ID'ye göre kullanıcı getir."""
        try:
            user = fetch_one(
                """
                SELECT 
                    LOGICALREF,
                    KULLANICI_ADI,
                    EMAIL,
                    AD_SOYAD,
                    ROL,
                    AKTIF,
                    OLUSTURMA_TARIHI,
                    GUNCELLEME_TARIHI,
                    SON_GIRIS
                FROM WMS_KULLANICILAR
                WHERE LOGICALREF = ?
                """,
                [user_id]
            )
            
            if user:
                return {
                    'id': user['logicalref'],
                    'username': user['kullanici_adi'],
                    'email': user['email'],
                    'full_name': user['ad_soyad'],
                    'role': user['rol'],
                    'is_active': user['aktif'],
                    'created_at': user['olusturma_tarihi'],
                    'updated_at': user['guncelleme_tarihi'],
                    'last_login': user['son_giris']
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Kullanıcı adına göre kullanıcı getir."""
        try:
            user = fetch_one(
                """
                SELECT 
                    LOGICALREF,
                    KULLANICI_ADI,
                    EMAIL,
                    AD_SOYAD,
                    ROL,
                    AKTIF,
                    OLUSTURMA_TARIHI,
                    GUNCELLEME_TARIHI,
                    SON_GIRIS
                FROM WMS_KULLANICILAR
                WHERE KULLANICI_ADI = ?
                """,
                [username]
            )
            
            if user:
                return {
                    'id': user['logicalref'],
                    'username': user['kullanici_adi'],
                    'email': user['email'],
                    'full_name': user['ad_soyad'],
                    'role': user['rol'],
                    'is_active': user['aktif'],
                    'created_at': user['olusturma_tarihi'],
                    'updated_at': user['guncelleme_tarihi'],
                    'last_login': user['son_giris']
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            return None
    
    def get_all_users(self) -> List[Dict]:
        """Tüm kullanıcıları getir."""
        try:
            users = fetch_all(
                """
                SELECT 
                    LOGICALREF,
                    KULLANICI_ADI,
                    EMAIL,
                    AD_SOYAD,
                    ROL,
                    AKTIF,
                    OLUSTURMA_TARIHI,
                    GUNCELLEME_TARIHI,
                    SON_GIRIS
                FROM WMS_KULLANICILAR
                ORDER BY KULLANICI_ADI
                """
            )
            
            result = []
            for user in users:
                result.append({
                    'id': user['logicalref'],
                    'username': user['kullanici_adi'],
                    'email': user['email'],
                    'full_name': user['ad_soyad'],
                    'role': user['rol'],
                    'is_active': user['aktif'],
                    'created_at': user['olusturma_tarihi'],
                    'updated_at': user['guncelleme_tarihi'],
                    'last_login': user['son_giris']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def create_user(self, user_data: Dict) -> Optional[int]:
        """
        Yeni kullanıcı oluştur.
        
        Args:
            user_data: Kullanıcı verileri dict
            
        Returns:
            Başarılıysa yeni kullanıcı ID'si
        """
        try:
            # Tek transaction'da hem kullanıcı oluştur hem aktivite logla
            with get_conn() as conn:
                cursor = conn.cursor()
                
                # Kullanıcıyı ekle
                cursor.execute(
                    """
                    INSERT INTO WMS_KULLANICILAR (
                        KULLANICI_ADI, 
                        EMAIL, 
                        SIFRE_HASH, 
                        AD_SOYAD, 
                        ROL,
                        AKTIF,
                        OLUSTURMA_TARIHI,
                        GUNCELLEME_TARIHI
                    )
                    OUTPUT INSERTED.LOGICALREF
                    VALUES (?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                    """,
                    [
                        user_data['username'],
                        user_data.get('email', ''),
                        user_data.get('password_hash', ''),  # UI'dan hash'lenmiş geliyor
                        user_data.get('full_name', ''),
                        user_data.get('role', 'operator'),
                        user_data.get('is_active', True)
                    ]
                )
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                user_id = result[0]  # OUTPUT INSERTED.LOGICALREF
                logger.info(f"User created: {user_data['username']} (ID: {user_id})")
                
                # Aynı transaction'da aktiviteyi logla
                try:
                    cursor.execute(
                        """
                        INSERT INTO WMS_KULLANICI_AKTIVITELERI 
                        (KULLANICI_REF, AKTIVITE, MODUL, DETAY, IP_ADRESI)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        [user_id, 'user_created', 'users', f"User {user_data['username']} created", None]
                    )
                except Exception as log_error:
                    logger.warning(f"Could not log activity for user creation: {log_error}")
                    # Aktivite loglanamasa bile kullanıcı oluşturulacak
                
                # Transaction'ı commit et
                conn.commit()
                return user_id
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def update_user(self, user_id: int, user_data: Dict) -> bool:
        """
        Kullanıcı bilgilerini güncelle.
        
        Args:
            user_id: Kullanıcı ID
            user_data: Güncellenecek veriler
            
        Returns:
            Başarılıysa True
        """
        try:
            allowed_fields = {
                'username': 'KULLANICI_ADI',
                'email': 'EMAIL',
                'full_name': 'AD_SOYAD',
                'role': 'ROL',
                'is_active': 'AKTIF'
            }
            
            updates = []
            values = []
            
            for field, value in user_data.items():
                if field in allowed_fields:
                    updates.append(f"{allowed_fields[field]} = ?")
                    values.append(value)
            
            if not updates:
                return False
            
            updates.append("GUNCELLEME_TARIHI = GETDATE()")
            values.append(user_id)
            
            query = f"""
                UPDATE WMS_KULLANICILAR 
                SET {', '.join(updates)}
                WHERE LOGICALREF = ?
            """
            
            rows = execute_query(query, values)
            
            if rows > 0:
                self.log_activity(user_id, 'user_updated', 'users', f"User updated: {list(user_data.keys())}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """Kullanıcı şifresini değiştir."""
        try:
            password_hash = self._hash_password(new_password)
            
            rows = execute_query(
                """
                UPDATE WMS_KULLANICILAR 
                SET SIFRE_HASH = ?, 
                    GUNCELLEME_TARIHI = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [password_hash, user_id]
            )
            
            if rows > 0:
                self.log_activity(user_id, 'password_changed', 'users', 'Password changed')
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return False
    
    def log_activity(self, user_id: int, action: str, module: str = None, 
                    details: str = None, ip_address: str = None) -> bool:
        """Kullanıcı aktivitesini logla."""
        try:
            execute_query(
                """
                INSERT INTO WMS_KULLANICI_AKTIVITELERI 
                (KULLANICI_REF, AKTIVITE, MODUL, DETAY, IP_ADRESI)
                VALUES (?, ?, ?, ?, ?)
                """,
                [user_id, action, module, details, ip_address]
            )
            return True
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
            return False
    
    def get_user_activities(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Kullanıcı aktivitelerini getir."""
        try:
            activities = fetch_all(
                """
                SELECT TOP (?) 
                    AKTIVITE,
                    MODUL,
                    DETAY,
                    IP_ADRESI,
                    TARIH
                FROM WMS_KULLANICI_AKTIVITELERI
                WHERE KULLANICI_REF = ?
                ORDER BY TARIH DESC
                """,
                [limit, user_id]
            )
            
            result = []
            for activity in activities:
                result.append({
                    'action': activity['aktivite'],
                    'module': activity['modul'],
                    'details': activity['detay'],
                    'ip_address': activity['ip_adresi'],
                    'created_at': activity['tarih']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user activities: {e}")
            return []
    
    def check_tables_exist(self) -> bool:
        """Kullanıcı tablolarının var olup olmadığını kontrol et."""
        try:
            result = fetch_one(
                """
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'WMS_KULLANICILAR'
                """
            )
            return result and result['count'] > 0
        except:
            return False
    
    def _hash_password(self, password: str) -> str:
        """Şifreyi bcrypt ile hash'le."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Şifreyi hash ile karşılaştır."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    
    def _update_failed_attempts(self, user_id: int):
        """Başarısız giriş denemelerini güncelle."""
        try:
            execute_query(
                """
                UPDATE WMS_KULLANICILAR 
                SET BASARISIZ_GIRIS = BASARISIZ_GIRIS + 1,
                    KILITLI_TARIH = CASE 
                        WHEN BASARISIZ_GIRIS >= 4 
                        THEN DATEADD(MINUTE, 30, GETDATE())
                        ELSE KILITLI_TARIH
                    END,
                    GUNCELLEME_TARIHI = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [user_id]
            )
        except Exception as e:
            logger.error(f"Error updating failed attempts: {e}")
    
    def get_login_stats(self) -> Dict:
        """Giriş istatistiklerini getir."""
        try:
            stats = fetch_one(
                """
                SELECT 
                    COUNT(*) as total_users,
                    SUM(CASE WHEN AKTIF = 1 THEN 1 ELSE 0 END) as active_users,
                    SUM(CASE WHEN SON_GIRIS > DATEADD(DAY, -7, GETDATE()) THEN 1 ELSE 0 END) as weekly_active,
                    SUM(CASE WHEN KILITLI_TARIH > GETDATE() THEN 1 ELSE 0 END) as locked_users
                FROM WMS_KULLANICILAR
                """
            )
            
            return {
                'total_users': stats['total_users'] or 0,
                'active_users': stats['active_users'] or 0,
                'weekly_active_users': stats['weekly_active'] or 0,
                'locked_users': stats['locked_users'] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting login stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'weekly_active_users': 0,
                'locked_users': 0
            }
    
    def update_password(self, user_id: int, password_hash: str) -> bool:
        """
        Kullanıcı şifresini güncelle.
        
        Args:
            user_id: Kullanıcı ID
            password_hash: Hash'lenmiş şifre
            
        Returns:
            Başarılı ise True
        """
        try:
            execute_query(
                """
                UPDATE WMS_KULLANICILAR 
                SET SIFRE_HASH = ?,
                    GUNCELLEME_TARIHI = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [password_hash, user_id]
            )
            
            logger.info(f"Password updated for user ID: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """
        Kullanıcıyı sil.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            Başarılı ise True
        """
        try:
            # Soft delete - sadece aktif durumunu kapat
            execute_query(
                """
                UPDATE WMS_KULLANICILAR 
                SET AKTIF = 0,
                    SILINME_TARIHI = GETDATE(),
                    GUNCELLEME_TARIHI = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [user_id]
            )
            
            logger.info(f"User deleted (soft): ID {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False