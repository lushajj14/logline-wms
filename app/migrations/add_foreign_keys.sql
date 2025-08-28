-- Migration: Add Foreign Keys for Data Integrity
-- WARNING: Run this after ensuring no orphaned records exist

-- 1. Check for orphaned records before adding constraints
PRINT 'Checking for orphaned records...'

-- Check backorders
IF EXISTS (
    SELECT 1 FROM dbo.backorders b
    WHERE NOT EXISTS (
        SELECT 1 FROM ORFICHE o WHERE o.FICHENO = b.order_no
    )
)
BEGIN
    PRINT 'WARNING: Found orphaned records in backorders table'
    -- Optional: DELETE FROM dbo.backorders WHERE order_no NOT IN (SELECT FICHENO FROM ORFICHE)
END

-- Check shipment_header
IF EXISTS (
    SELECT 1 FROM dbo.shipment_header s
    WHERE NOT EXISTS (
        SELECT 1 FROM ORFICHE o WHERE o.FICHENO = s.order_no
    )
)
BEGIN
    PRINT 'WARNING: Found orphaned records in shipment_header table'
END

-- 2. Add indexes for better performance (if not exists)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_backorders_order_no')
    CREATE INDEX IX_backorders_order_no ON dbo.backorders(order_no);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_backorders_item_code')
    CREATE INDEX IX_backorders_item_code ON dbo.backorders(item_code);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_shipment_header_order_no')
    CREATE INDEX IX_shipment_header_order_no ON dbo.shipment_header(order_no);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_shipment_loaded_trip_id')
    CREATE INDEX IX_shipment_loaded_trip_id ON dbo.shipment_loaded(trip_id);

-- 3. Add Foreign Key Constraints (with CASCADE options for safety)

-- shipment_loaded -> shipment_header
IF NOT EXISTS (
    SELECT * FROM sys.foreign_keys 
    WHERE name = 'FK_shipment_loaded_shipment_header'
)
BEGIN
    ALTER TABLE dbo.shipment_loaded
    ADD CONSTRAINT FK_shipment_loaded_shipment_header
    FOREIGN KEY (trip_id) REFERENCES dbo.shipment_header(id)
    ON DELETE CASCADE  -- When header deleted, remove all loaded records
    ON UPDATE CASCADE;
    PRINT 'Added FK: shipment_loaded -> shipment_header'
END

-- Note: Cannot add FK to ORFICHE without knowing Logo table structure
-- These would need custom triggers or application-level enforcement

-- 4. Add Check Constraints for data validation
IF NOT EXISTS (
    SELECT * FROM sys.check_constraints 
    WHERE name = 'CK_backorders_qty_positive'
)
BEGIN
    ALTER TABLE dbo.backorders
    ADD CONSTRAINT CK_backorders_qty_positive
    CHECK (qty_missing > 0);
    PRINT 'Added check constraint: qty_missing must be positive'
END

IF NOT EXISTS (
    SELECT * FROM sys.check_constraints 
    WHERE name = 'CK_shipment_header_pkgs_positive'
)
BEGIN
    ALTER TABLE dbo.shipment_header
    ADD CONSTRAINT CK_shipment_header_pkgs_positive
    CHECK (pkgs_total > 0 AND pkgs_loaded >= 0);
    PRINT 'Added check constraint: package counts must be valid'
END

IF NOT EXISTS (
    SELECT * FROM sys.check_constraints 
    WHERE name = 'CK_shipment_loaded_pkg_valid'
)
BEGIN
    ALTER TABLE dbo.shipment_loaded
    ADD CONSTRAINT CK_shipment_loaded_pkg_valid
    CHECK (pkg_no > 0);
    PRINT 'Added check constraint: pkg_no must be positive'
END

-- 5. Add unique constraints to prevent duplicates
IF NOT EXISTS (
    SELECT * FROM sys.indexes 
    WHERE name = 'UQ_shipment_loaded_trip_pkg'
)
BEGIN
    CREATE UNIQUE INDEX UQ_shipment_loaded_trip_pkg
    ON dbo.shipment_loaded(trip_id, pkg_no);
    PRINT 'Added unique constraint: trip_id + pkg_no'
END

PRINT 'Foreign key migration completed'