# WMS KULLANICI TABLOLARI KURULUM REHBERİ

## 1. Adım: SQL Server Management Studio'yu Aç

1. SQL Server Management Studio (SSMS) açın
2. SQL Server'a bağlanın (LOGO veritabanınızın olduğu sunucu)

## 2. Adım: Veritabanı Seçimi

```sql
USE [logo]  -- Veya hangi veritabanı kullanıyorsanız
GO
```

## 3. Adım: CREATE_USER_TABLES.sql Dosyasını Çalıştır

1. File → Open → File menüsünden `CREATE_USER_TABLES.sql` dosyasını açın
2. Veya dosyanın içeriğini kopyalayıp Query penceresine yapıştırın
3. Execute (F5) tuşuna basın

## 4. Adım: Kontrol Sorguları

Tablolar doğru oluşturulduğunu kontrol etmek için:

```sql
-- Tablo kontrol
SELECT name FROM sysobjects WHERE xtype='U' AND name LIKE 'WMS_%'

-- Kullanıcı sayısı kontrol
SELECT COUNT(*) as kullanici_sayisi FROM WMS_KULLANICILAR

-- Test kullanıcıları listesi
SELECT KULLANICI_ADI, EMAIL, ROL, AKTIF FROM WMS_KULLANICILAR
```

## 5. Adım: Python Kodunu Güncelle

Tablolar oluşturulduktan sonra Python kodunda `users_new.py` dosyasını kullanmaya başlayın:

```python
# Eski: from app.dao.users import UserDAO
# Yeni:
from app.dao.users_new import UserDAO
```

## Test Kullanıcıları

Otomatik oluşturulan kullanıcılar:
- **admin** / Admin123! (admin rolü)
- **operator** / Admin123! (operator rolü)  
- **viewer** / Admin123! (viewer rolü)

## Sorun Giderme

Eğer tablolar zaten varsa:
```sql
-- Tabloları silmek için (DİKKAT: Veri kaybı!)
DROP TABLE WMS_KULLANICI_AKTIVITELERI
DROP TABLE WMS_KULLANICI_OTURUMLARI  
DROP TABLE WMS_KULLANICILAR
```

Sonra tekrar CREATE_USER_TABLES.sql çalıştırın.