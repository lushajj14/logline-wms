-- ================================================================
-- WMS Stored Procedure Kontrol Sorguları
-- ================================================================

-- 1. TÜM PROSEDÜRLER (basit liste)
SELECT name, create_date, modify_date
FROM sys.procedures
ORDER BY name;

-- 2. ATOMIC SCAN PROSEDÜRÜNÜ BUL
SELECT 
    name AS 'Prosedür Adı',
    create_date AS 'Oluşturulma Tarihi',
    modify_date AS 'Son Değişiklik'
FROM sys.procedures
WHERE name LIKE '%atomic%' 
   OR name LIKE '%scan%'
   OR name = 'sp_atomic_scan_increment';

-- 3. PROSEDÜR DETAYLI BİLGİ
SELECT 
    p.name AS 'Prosedür Adı',
    p.create_date AS 'Oluşturulma',
    p.modify_date AS 'Güncelleme',
    m.definition AS 'Prosedür Kodu'
FROM sys.procedures p
JOIN sys.sql_modules m ON p.object_id = m.object_id
WHERE p.name = 'sp_atomic_scan_increment';

-- 4. PROSEDÜR KODU (sadece kod)
EXEC sp_helptext 'sp_atomic_scan_increment';

-- 5. EĞER PROSEDÜR YOKSA OLUŞTUR
IF NOT EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_atomic_scan_increment')
BEGIN
    PRINT 'Prosedür bulunamadı! Oluşturuluyor...'
    
    EXEC('
    CREATE PROCEDURE sp_atomic_scan_increment
        @order_id INT,
        @item_code VARCHAR(30),
        @qty_inc FLOAT
    AS
    BEGIN
        SET TRANSACTION ISOLATION LEVEL SERIALIZABLE
        BEGIN TRANSACTION
        
        -- Doğru kolon isimleriyle güncelle
        UPDATE WMS_PICKQUEUE WITH (UPDLOCK, ROWLOCK)
        SET qty_sent = qty_sent + @qty_inc
        WHERE order_id = @order_id 
          AND item_code = @item_code
          AND qty_sent + @qty_inc <= qty_ordered
        
        -- Etkilenen satır sayısını dön
        SELECT @@ROWCOUNT AS UpdatedRows
        
        COMMIT
    END
    ')
    
    PRINT 'Prosedür başarıyla oluşturuldu!'
END
ELSE
BEGIN
    PRINT 'Prosedür zaten mevcut.'
END

-- 6. WMS_PICKQUEUE TABLOSU KONTROLÜ
IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'WMS_PICKQUEUE')
BEGIN
    PRINT 'WMS_PICKQUEUE tablosu mevcut.'
    
    -- Kolon listesi
    SELECT 
        COLUMN_NAME AS 'Kolon Adı',
        DATA_TYPE AS 'Veri Tipi',
        IS_NULLABLE AS 'Null Olabilir'
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'WMS_PICKQUEUE'
    ORDER BY ORDINAL_POSITION;
END
ELSE
BEGIN
    PRINT 'UYARI: WMS_PICKQUEUE tablosu bulunamadı!'
END