-- =====================================================
-- WMS KULLANICI YÖNETİMİ TABLOLARI
-- SQL Server Management Studio'da çalıştır
-- =====================================================

USE [logo]  -- Veya hangi database kullanıyorsan
GO

-- 1. Ana kullanıcı tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='WMS_KULLANICILAR' AND xtype='U')
BEGIN
    CREATE TABLE [WMS_KULLANICILAR] (
        [LOGICALREF] [int] IDENTITY(1,1) NOT NULL,
        [KULLANICI_ADI] [nvarchar](50) NOT NULL,
        [EMAIL] [nvarchar](100) NOT NULL,
        [SIFRE_HASH] [nvarchar](255) NOT NULL,
        [AD_SOYAD] [nvarchar](100) NULL,
        [ROL] [nvarchar](20) NOT NULL DEFAULT 'operator',
        [AKTIF] [bit] NOT NULL DEFAULT 1,
        [OLUSTURMA_TARIHI] [datetime] NOT NULL DEFAULT GETDATE(),
        [GUNCELLEME_TARIHI] [datetime] NOT NULL DEFAULT GETDATE(),
        [SON_GIRIS] [datetime] NULL,
        [BASARISIZ_GIRIS] [int] NOT NULL DEFAULT 0,
        [KILITLI_TARIH] [datetime] NULL,
        
        CONSTRAINT [PK_WMS_KULLANICILAR] PRIMARY KEY ([LOGICALREF]),
        CONSTRAINT [UK_WMS_KULLANICILAR_ADI] UNIQUE ([KULLANICI_ADI]),
        CONSTRAINT [UK_WMS_KULLANICILAR_EMAIL] UNIQUE ([EMAIL]),
        CONSTRAINT [CHK_WMS_KULLANICILAR_ROL] CHECK ([ROL] IN ('admin', 'supervisor', 'operator', 'viewer'))
    )
    
    -- Index'ler
    CREATE INDEX [IX_WMS_KULLANICILAR_KULLANICI_ADI] ON [WMS_KULLANICILAR]([KULLANICI_ADI])
    CREATE INDEX [IX_WMS_KULLANICILAR_EMAIL] ON [WMS_KULLANICILAR]([EMAIL])
    CREATE INDEX [IX_WMS_KULLANICILAR_ROL] ON [WMS_KULLANICILAR]([ROL])
    
    PRINT 'WMS_KULLANICILAR tablosu oluşturuldu'
END
GO

-- 2. Kullanıcı oturumları tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='WMS_KULLANICI_OTURUMLARI' AND xtype='U')
BEGIN
    CREATE TABLE [WMS_KULLANICI_OTURUMLARI] (
        [LOGICALREF] [int] IDENTITY(1,1) NOT NULL,
        [KULLANICI_REF] [int] NOT NULL,
        [TOKEN] [nvarchar](500) NOT NULL,
        [IP_ADRESI] [nvarchar](45) NULL,
        [TARAYICI] [nvarchar](255) NULL,
        [OLUSTURMA_TARIHI] [datetime] NOT NULL DEFAULT GETDATE(),
        [SON_KULLANIM] [datetime] NOT NULL,
        [AKTIF] [bit] NOT NULL DEFAULT 1,
        
        CONSTRAINT [PK_WMS_KULLANICI_OTURUMLARI] PRIMARY KEY ([LOGICALREF]),
        CONSTRAINT [FK_WMS_OTURUMLARI_KULLANICI] FOREIGN KEY ([KULLANICI_REF]) 
            REFERENCES [WMS_KULLANICILAR]([LOGICALREF]) ON DELETE CASCADE
    )
    
    CREATE INDEX [IX_WMS_OTURUMLARI_TOKEN] ON [WMS_KULLANICI_OTURUMLARI]([TOKEN])
    CREATE INDEX [IX_WMS_OTURUMLARI_KULLANICI_REF] ON [WMS_KULLANICI_OTURUMLARI]([KULLANICI_REF])
    
    PRINT 'WMS_KULLANICI_OTURUMLARI tablosu oluşturuldu'
END
GO

-- 3. Kullanıcı aktiviteleri tablosu
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='WMS_KULLANICI_AKTIVITELERI' AND xtype='U')
BEGIN
    CREATE TABLE [WMS_KULLANICI_AKTIVITELERI] (
        [LOGICALREF] [int] IDENTITY(1,1) NOT NULL,
        [KULLANICI_REF] [int] NOT NULL,
        [AKTIVITE] [nvarchar](100) NOT NULL,
        [MODUL] [nvarchar](50) NULL,
        [DETAY] [nvarchar](max) NULL,
        [IP_ADRESI] [nvarchar](45) NULL,
        [TARIH] [datetime] NOT NULL DEFAULT GETDATE(),
        
        CONSTRAINT [PK_WMS_KULLANICI_AKTIVITELERI] PRIMARY KEY ([LOGICALREF]),
        CONSTRAINT [FK_WMS_AKTIVITELER_KULLANICI] FOREIGN KEY ([KULLANICI_REF]) 
            REFERENCES [WMS_KULLANICILAR]([LOGICALREF]) ON DELETE CASCADE
    )
    
    CREATE INDEX [IX_WMS_AKTIVITELER_KULLANICI_REF] ON [WMS_KULLANICI_AKTIVITELERI]([KULLANICI_REF])
    CREATE INDEX [IX_WMS_AKTIVITELER_TARIH] ON [WMS_KULLANICI_AKTIVITELERI]([TARIH])
    
    PRINT 'WMS_KULLANICI_AKTIVITELERI tablosu oluşturuldu'
END
GO

-- 4. Default admin kullanıcısı oluştur
IF NOT EXISTS (SELECT * FROM WMS_KULLANICILAR WHERE KULLANICI_ADI = 'admin')
BEGIN
    -- Şifre: Admin123! (bcrypt hash)
    INSERT INTO [WMS_KULLANICILAR] (
        [KULLANICI_ADI], 
        [EMAIL], 
        [SIFRE_HASH], 
        [AD_SOYAD], 
        [ROL]
    )
    VALUES (
        'admin',
        'admin@wms.local',
        '$2b$12$LQG1P0Q5yH3N6rZGcMqJOe7Zp5kY1x8Qn9vX4mK2jF8tR6wS3dL5u',
        'System Administrator',
        'admin'
    )
    
    PRINT 'Admin kullanıcısı oluşturuldu (Kullanıcı: admin, Şifre: Admin123!)'
END
GO

-- 5. Test kullanıcıları oluştur
IF NOT EXISTS (SELECT * FROM WMS_KULLANICILAR WHERE KULLANICI_ADI = 'operator')
BEGIN
    INSERT INTO [WMS_KULLANICILAR] (
        [KULLANICI_ADI], 
        [EMAIL], 
        [SIFRE_HASH], 
        [AD_SOYAD], 
        [ROL]
    )
    VALUES 
    ('operator', 'operator@wms.local', '$2b$12$LQG1P0Q5yH3N6rZGcMqJOe7Zp5kY1x8Qn9vX4mK2jF8tR6wS3dL5u', 'Operatör Kullanıcı', 'operator'),
    ('viewer', 'viewer@wms.local', '$2b$12$LQG1P0Q5yH3N6rZGcMqJOe7Zp5kY1x8Qn9vX4mK2jF8tR6wS3dL5u', 'İzleyici Kullanıcı', 'viewer')
    
    PRINT 'Test kullanıcıları oluşturuldu'
END
GO

-- 6. Kontrol sorguları
PRINT ''
PRINT '=== TABLO KONTROL ==='
SELECT 'WMS_KULLANICILAR' as TABLO, COUNT(*) as KAYIT_SAYISI FROM WMS_KULLANICILAR
UNION ALL
SELECT 'WMS_KULLANICI_OTURUMLARI', COUNT(*) FROM WMS_KULLANICI_OTURUMLARI
UNION ALL
SELECT 'WMS_KULLANICI_AKTIVITELERI', COUNT(*) FROM WMS_KULLANICI_AKTIVITELERI

PRINT ''
PRINT '=== KULLANICI LİSTESİ ==='
SELECT 
    LOGICALREF,
    KULLANICI_ADI,
    EMAIL,
    AD_SOYAD,
    ROL,
    AKTIF,
    OLUSTURMA_TARIHI
FROM WMS_KULLANICILAR
ORDER BY KULLANICI_ADI

PRINT ''
PRINT '✅ WMS kullanıcı tabloları başarıyla oluşturuldu!'
PRINT 'Test bilgileri:'
PRINT '  Admin: admin / Admin123!'
PRINT '  Operator: operator / Admin123!'
PRINT '  Viewer: viewer / Admin123!'
GO