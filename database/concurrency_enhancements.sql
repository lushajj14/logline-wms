-- =====================================================
-- WMS Concurrency Enhancements for SQL Server
-- =====================================================
-- These enhancements improve concurrency control and performance
-- for the WMS system when multiple users are scanning simultaneously.

-- -----------------------------------------------------
-- 1. ADD OPTIMISTIC LOCKING TO WMS_PICKQUEUE
-- -----------------------------------------------------
-- Add version column for optimistic concurrency control
IF NOT EXISTS (SELECT * FROM sys.columns WHERE OBJECT_ID = OBJECT_ID('WMS_PICKQUEUE') AND name = 'version_stamp')
BEGIN
    ALTER TABLE WMS_PICKQUEUE ADD version_stamp BIGINT NOT NULL DEFAULT 0
    PRINT 'Added version_stamp column to WMS_PICKQUEUE for optimistic locking'
END

-- Add trigger to automatically increment version on updates
IF NOT EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_WMS_PICKQUEUE_VERSION')
BEGIN
    EXEC('
    CREATE TRIGGER TR_WMS_PICKQUEUE_VERSION
    ON WMS_PICKQUEUE
    AFTER UPDATE
    AS
    BEGIN
        SET NOCOUNT ON
        
        UPDATE WMS_PICKQUEUE 
        SET version_stamp = version_stamp + 1
        FROM WMS_PICKQUEUE p
        INNER JOIN inserted i ON p.order_id = i.order_id AND p.item_code = i.item_code
    END
    ')
    PRINT 'Created version stamp trigger for WMS_PICKQUEUE'
END

-- -----------------------------------------------------
-- 2. ADD AUDIT TRAIL FOR CONCURRENT OPERATIONS
-- -----------------------------------------------------
-- Create audit table for tracking concurrent operations
IF NOT EXISTS (SELECT * FROM sys.objects WHERE name = 'WMS_SCAN_AUDIT' AND type = 'U')
BEGIN
    CREATE TABLE WMS_SCAN_AUDIT (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        operation_time DATETIME2(3) NOT NULL DEFAULT SYSDATETIME(),
        session_id INT NOT NULL DEFAULT @@SPID,
        user_name NVARCHAR(128) NOT NULL DEFAULT SYSTEM_USER,
        operation_type VARCHAR(20) NOT NULL, -- SCAN, COMPLETE, LOCK_ACQUIRE, LOCK_RELEASE
        order_id INT NOT NULL,
        item_code VARCHAR(30) NULL,
        quantity_before FLOAT NULL,
        quantity_after FLOAT NULL,
        status VARCHAR(20) NOT NULL, -- SUCCESS, FAILED, LOCKED
        error_message NVARCHAR(500) NULL,
        lock_wait_time_ms INT NULL,
        
        INDEX IX_WMS_SCAN_AUDIT_TIME (operation_time),
        INDEX IX_WMS_SCAN_AUDIT_ORDER (order_id, operation_time),
        INDEX IX_WMS_SCAN_AUDIT_SESSION (session_id, operation_time)
    )
    PRINT 'Created WMS_SCAN_AUDIT table for concurrency tracking'
END

-- -----------------------------------------------------
-- 3. ENHANCED ATOMIC SCAN PROCEDURE
-- -----------------------------------------------------
-- Create stored procedure for atomic scan operations with full concurrency protection
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_wms_atomic_scan')
    DROP PROCEDURE sp_wms_atomic_scan
GO

CREATE PROCEDURE sp_wms_atomic_scan
    @order_id INT,
    @item_code VARCHAR(30),
    @qty_increment FLOAT,
    @qty_ordered FLOAT,
    @over_scan_tolerance FLOAT = 0.0,
    @user_name VARCHAR(128) = NULL,
    @new_qty_sent FLOAT OUTPUT,
    @success BIT OUTPUT,
    @message NVARCHAR(500) OUTPUT
AS
BEGIN
    SET NOCOUNT ON
    SET @success = 0
    SET @message = 'Unknown error'
    SET @user_name = ISNULL(@user_name, SYSTEM_USER)
    
    DECLARE @lock_name VARCHAR(255) = 'WMS_SCAN_' + CAST(@order_id AS VARCHAR) + '_' + @item_code
    DECLARE @lock_result INT
    DECLARE @start_time DATETIME2 = SYSDATETIME()
    DECLARE @current_qty FLOAT
    DECLARE @calculated_qty FLOAT
    DECLARE @max_allowed FLOAT
    
    BEGIN TRY
        -- Acquire application lock with timeout
        EXEC @lock_result = sp_getapplock 
            @Resource = @lock_name,
            @LockMode = 'Exclusive',
            @LockTimeout = 5000 -- 5 seconds
        
        IF @lock_result < 0
        BEGIN
            SET @message = CASE @lock_result
                WHEN -1 THEN 'Lock timeout - another user is scanning this item'
                WHEN -2 THEN 'Request canceled'
                WHEN -3 THEN 'Deadlock victim'
                ELSE 'Lock acquisition failed'
            END
            
            -- Log failed lock attempt
            INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, status, error_message, user_name)
            VALUES ('LOCK_ACQUIRE', @order_id, @item_code, 'FAILED', @message, @user_name)
            
            RETURN
        END
        
        -- Log successful lock acquisition
        INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, status, user_name, lock_wait_time_ms)
        VALUES ('LOCK_ACQUIRE', @order_id, @item_code, 'SUCCESS', @user_name, DATEDIFF(ms, @start_time, SYSDATETIME()))
        
        -- Get current quantity with row lock
        SELECT @current_qty = qty_sent 
        FROM WMS_PICKQUEUE WITH (UPDLOCK, ROWLOCK)
        WHERE order_id = @order_id AND item_code = @item_code
        
        IF @@ROWCOUNT = 0
        BEGIN
            SET @message = 'Item not found in queue'
            INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, status, error_message, user_name)
            VALUES ('SCAN', @order_id, @item_code, 'FAILED', @message, @user_name)
            RETURN
        END
        
        -- Calculate new quantity and validate
        SET @calculated_qty = @current_qty + @qty_increment
        SET @max_allowed = @qty_ordered + @over_scan_tolerance
        
        IF @calculated_qty > @max_allowed
        BEGIN
            SET @message = 'Over-scan detected: ' + CAST(@calculated_qty AS VARCHAR(10)) + ' > ' + CAST(@max_allowed AS VARCHAR(10))
            INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, quantity_before, quantity_after, status, error_message, user_name)
            VALUES ('SCAN', @order_id, @item_code, @current_qty, @calculated_qty, 'OVER_SCAN', @message, @user_name)
            RETURN
        END
        
        -- Perform atomic update
        UPDATE WMS_PICKQUEUE
        SET qty_sent = @calculated_qty
        WHERE order_id = @order_id AND item_code = @item_code
        
        IF @@ROWCOUNT = 1
        BEGIN
            SET @new_qty_sent = @calculated_qty
            SET @success = 1
            SET @message = 'Scan successful'
            
            -- Log successful scan
            INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, quantity_before, quantity_after, status, user_name)
            VALUES ('SCAN', @order_id, @item_code, @current_qty, @calculated_qty, 'SUCCESS', @user_name)
        END
        ELSE
        BEGIN
            SET @message = 'Failed to update quantity'
            INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, status, error_message, user_name)
            VALUES ('SCAN', @order_id, @item_code, 'FAILED', @message, @user_name)
        END
        
    END TRY
    BEGIN CATCH
        SET @message = ERROR_MESSAGE()
        INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, status, error_message, user_name)
        VALUES ('SCAN', @order_id, @item_code, 'ERROR', @message, @user_name)
    END CATCH
    
    -- Always release the lock
    EXEC sp_releaseapplock @Resource = @lock_name
    
    -- Log lock release
    INSERT INTO WMS_SCAN_AUDIT (operation_type, order_id, item_code, status, user_name)
    VALUES ('LOCK_RELEASE', @order_id, @item_code, 'SUCCESS', @user_name)
END
GO

PRINT 'Created sp_wms_atomic_scan procedure for atomic scanning operations'

-- -----------------------------------------------------
-- 4. ORDER COMPLETION LOCK PROCEDURE
-- -----------------------------------------------------
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_wms_check_order_completion_lock')
    DROP PROCEDURE sp_wms_check_order_completion_lock
GO

CREATE PROCEDURE sp_wms_check_order_completion_lock
    @order_id INT,
    @is_locked BIT OUTPUT,
    @lock_holder VARCHAR(128) OUTPUT
AS
BEGIN
    SET NOCOUNT ON
    SET @is_locked = 0
    SET @lock_holder = NULL
    
    DECLARE @lock_name VARCHAR(255) = 'WMS_COMPLETE_' + CAST(@order_id AS VARCHAR)
    
    SELECT @is_locked = 1, @lock_holder = request_session_id
    FROM sys.dm_tran_locks
    WHERE resource_description = @lock_name 
      AND resource_type = 'APPLICATION'
      AND request_mode = 'X'
      AND request_status = 'GRANT'
END
GO

PRINT 'Created sp_wms_check_order_completion_lock procedure'

-- -----------------------------------------------------
-- 5. CONCURRENCY MONITORING VIEWS
-- -----------------------------------------------------
-- Create view for monitoring concurrent operations
IF EXISTS (SELECT * FROM sys.views WHERE name = 'v_wms_concurrency_monitor')
    DROP VIEW v_wms_concurrency_monitor
GO

CREATE VIEW v_wms_concurrency_monitor
AS
SELECT 
    sa.operation_time,
    sa.session_id,
    sa.user_name,
    sa.operation_type,
    sa.order_id,
    oh.FICHENO as order_no,
    sa.item_code,
    sa.quantity_before,
    sa.quantity_after,
    sa.status,
    sa.error_message,
    sa.lock_wait_time_ms,
    CASE 
        WHEN sa.lock_wait_time_ms > 1000 THEN 'HIGH_CONTENTION'
        WHEN sa.lock_wait_time_ms > 500 THEN 'MEDIUM_CONTENTION'
        WHEN sa.lock_wait_time_ms > 0 THEN 'LOW_CONTENTION'
        ELSE 'NO_CONTENTION'
    END as contention_level
FROM WMS_SCAN_AUDIT sa
LEFT JOIN LG_025_01_ORFICHE oh ON sa.order_id = oh.LOGICALREF
WHERE sa.operation_time > DATEADD(hour, -24, SYSDATETIME()) -- Last 24 hours
GO

PRINT 'Created v_wms_concurrency_monitor view'

-- Create view for active locks
IF EXISTS (SELECT * FROM sys.views WHERE name = 'v_wms_active_locks')
    DROP VIEW v_wms_active_locks
GO

CREATE VIEW v_wms_active_locks
AS
SELECT 
    l.request_session_id,
    l.resource_description,
    l.request_mode,
    l.request_status,
    l.request_time,
    DATEDIFF(second, l.request_time, SYSDATETIME()) as lock_duration_seconds,
    s.login_name,
    s.program_name,
    s.host_name,
    CASE 
        WHEN l.resource_description LIKE 'WMS_SCAN_%' THEN 'SCAN_LOCK'
        WHEN l.resource_description LIKE 'WMS_COMPLETE_%' THEN 'COMPLETION_LOCK'
        ELSE 'OTHER_LOCK'
    END as lock_type,
    CASE 
        WHEN l.resource_description LIKE 'WMS_SCAN_%' 
        THEN SUBSTRING(l.resource_description, CHARINDEX('_', l.resource_description, 10) + 1, 50)
        WHEN l.resource_description LIKE 'WMS_COMPLETE_%'
        THEN SUBSTRING(l.resource_description, 14, 50)
        ELSE l.resource_description
    END as resource_identifier
FROM sys.dm_tran_locks l
INNER JOIN sys.dm_exec_sessions s ON l.request_session_id = s.session_id
WHERE l.resource_type = 'APPLICATION'
  AND l.resource_description LIKE 'WMS_%'
GO

PRINT 'Created v_wms_active_locks view'

-- -----------------------------------------------------
-- 6. PERFORMANCE INDEXES
-- -----------------------------------------------------
-- Add indexes for better performance under concurrent load
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('WMS_PICKQUEUE') AND name = 'IX_WMS_PICKQUEUE_ORDER_ITEM')
BEGIN
    CREATE NONCLUSTERED INDEX IX_WMS_PICKQUEUE_ORDER_ITEM 
    ON WMS_PICKQUEUE (order_id, item_code) 
    INCLUDE (qty_ordered, qty_sent, version_stamp)
    PRINT 'Created performance index IX_WMS_PICKQUEUE_ORDER_ITEM'
END

-- Add index on LG_025_01_ORFICHE for status queries
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('LG_025_01_ORFICHE') AND name = 'IX_ORFICHE_STATUS_LOGICALREF')
BEGIN
    CREATE NONCLUSTERED INDEX IX_ORFICHE_STATUS_LOGICALREF
    ON LG_025_01_ORFICHE (STATUS, LOGICALREF)
    INCLUDE (FICHENO, DATE_)
    PRINT 'Created performance index IX_ORFICHE_STATUS_LOGICALREF'
END

-- -----------------------------------------------------
-- 7. CLEANUP PROCEDURES
-- -----------------------------------------------------
-- Create procedure to clean old audit records
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_wms_cleanup_audit')
    DROP PROCEDURE sp_wms_cleanup_audit
GO

CREATE PROCEDURE sp_wms_cleanup_audit
    @retention_days INT = 30
AS
BEGIN
    SET NOCOUNT ON
    
    DECLARE @cutoff_date DATETIME2 = DATEADD(day, -@retention_days, SYSDATETIME())
    DECLARE @deleted_count INT
    
    DELETE FROM WMS_SCAN_AUDIT 
    WHERE operation_time < @cutoff_date
    
    SET @deleted_count = @@ROWCOUNT
    
    PRINT 'Cleaned up ' + CAST(@deleted_count AS VARCHAR(10)) + ' audit records older than ' + CAST(@retention_days AS VARCHAR(3)) + ' days'
END
GO

PRINT 'Created sp_wms_cleanup_audit procedure'

-- -----------------------------------------------------
-- 8. MONITORING QUERIES
-- -----------------------------------------------------
PRINT ''
PRINT '=====================================================
MONITORING QUERIES FOR CONCURRENCY ANALYSIS
====================================================='

PRINT '
-- Check current lock contention:
SELECT * FROM v_wms_active_locks ORDER BY lock_duration_seconds DESC

-- Check recent concurrency issues:
SELECT * FROM v_wms_concurrency_monitor 
WHERE status IN (''FAILED'', ''OVER_SCAN'', ''ERROR'')
ORDER BY operation_time DESC

-- Check scan performance by user:
SELECT 
    user_name,
    COUNT(*) as total_scans,
    AVG(lock_wait_time_ms) as avg_wait_time_ms,
    MAX(lock_wait_time_ms) as max_wait_time_ms,
    COUNT(CASE WHEN status = ''SUCCESS'' THEN 1 END) as successful_scans,
    COUNT(CASE WHEN status = ''FAILED'' THEN 1 END) as failed_scans
FROM v_wms_concurrency_monitor
WHERE operation_type = ''SCAN''
  AND operation_time > DATEADD(hour, -1, SYSDATETIME())
GROUP BY user_name
ORDER BY total_scans DESC

-- Check order completion conflicts:
SELECT 
    order_id,
    COUNT(DISTINCT session_id) as concurrent_users,
    COUNT(*) as total_operations,
    MIN(operation_time) as first_operation,
    MAX(operation_time) as last_operation
FROM WMS_SCAN_AUDIT
WHERE operation_type = ''COMPLETE''
  AND operation_time > DATEADD(hour, -1, SYSDATETIME())
GROUP BY order_id
HAVING COUNT(DISTINCT session_id) > 1
ORDER BY concurrent_users DESC
'

PRINT ''
PRINT 'WMS Concurrency enhancements completed successfully!'
PRINT 'Remember to:'
PRINT '1. Schedule sp_wms_cleanup_audit to run weekly'
PRINT '2. Monitor v_wms_concurrency_monitor for performance issues'
PRINT '3. Use sp_wms_atomic_scan in your application code for better concurrency'
PRINT '4. Test with multiple concurrent users before deploying to production'