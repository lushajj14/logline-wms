-- User Management Tables for WMS Application
-- Version: 1.0.0
-- Date: 2024-01-29

-- 1. Users table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='wms_users' AND xtype='U')
BEGIN
    CREATE TABLE wms_users (
        LOGICALREF INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) UNIQUE NOT NULL,
        email NVARCHAR(100) UNIQUE NOT NULL,
        password_hash NVARCHAR(255) NOT NULL,
        full_name NVARCHAR(100),
        role NVARCHAR(20) NOT NULL DEFAULT 'operator',
        is_active BIT DEFAULT 1,
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE(),
        last_login DATETIME NULL,
        failed_attempts INT DEFAULT 0,
        locked_until DATETIME NULL,
        CONSTRAINT CHK_Role CHECK (role IN ('admin', 'supervisor', 'operator', 'viewer'))
    );
    
    -- Create indexes
    CREATE INDEX IX_wms_users_username ON wms_users(username);
    CREATE INDEX IX_wms_users_email ON wms_users(email);
    CREATE INDEX IX_wms_users_role ON wms_users(role);
END

-- 2. User sessions table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='wms_user_sessions' AND xtype='U')
BEGIN
    CREATE TABLE wms_user_sessions (
        LOGICALREF INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        token NVARCHAR(500) NOT NULL,
        ip_address NVARCHAR(45),
        user_agent NVARCHAR(255),
        created_at DATETIME DEFAULT GETDATE(),
        expires_at DATETIME NOT NULL,
        is_active BIT DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES wms_users(LOGICALREF) ON DELETE CASCADE
    );
    
    CREATE INDEX IX_wms_user_sessions_token ON wms_user_sessions(token);
    CREATE INDEX IX_wms_user_sessions_user_id ON wms_user_sessions(user_id);
END

-- 3. User activity log
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='wms_user_activities' AND xtype='U')
BEGIN
    CREATE TABLE wms_user_activities (
        LOGICALREF INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        action NVARCHAR(100) NOT NULL,
        module NVARCHAR(50),
        details NVARCHAR(MAX),
        ip_address NVARCHAR(45),
        created_at DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (user_id) REFERENCES wms_users(LOGICALREF) ON DELETE CASCADE
    );
    
    CREATE INDEX IX_wms_user_activities_user_id ON wms_user_activities(user_id);
    CREATE INDEX IX_wms_user_activities_created_at ON wms_user_activities(created_at);
END

-- 4. User permissions (for granular access control)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='wms_user_permissions' AND xtype='U')
BEGIN
    CREATE TABLE wms_user_permissions (
        LOGICALREF INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL,
        module NVARCHAR(50) NOT NULL,
        can_view BIT DEFAULT 1,
        can_create BIT DEFAULT 0,
        can_update BIT DEFAULT 0,
        can_delete BIT DEFAULT 0,
        created_at DATETIME DEFAULT GETDATE(),
        FOREIGN KEY (user_id) REFERENCES wms_users(LOGICALREF) ON DELETE CASCADE,
        UNIQUE(user_id, module)
    );
END

-- Insert default admin user (password: Admin123!)
-- Password should be changed on first login
IF NOT EXISTS (SELECT * FROM wms_users WHERE username = 'admin')
BEGIN
    INSERT INTO wms_users (username, email, password_hash, full_name, role)
    VALUES (
        'admin',
        'admin@wms.local',
        '$2b$12$LQG1P0Q5yH3N6rZGcMqJOe7Zp5kY1x8Qn9vX4mK2jF8tR6wS3dL5u', -- bcrypt hash of 'Admin123!'
        'System Administrator',
        'admin'
    );
END

-- Create stored procedures for user management
GO

-- Login procedure
CREATE OR ALTER PROCEDURE sp_user_login
    @username NVARCHAR(50),
    @password_hash NVARCHAR(255)
AS
BEGIN
    DECLARE @user_id INT;
    DECLARE @is_active BIT;
    DECLARE @locked_until DATETIME;
    
    SELECT @user_id = LOGICALREF, @is_active = is_active, @locked_until = locked_until
    FROM wms_users
    WHERE username = @username AND password_hash = @password_hash;
    
    IF @user_id IS NOT NULL
    BEGIN
        IF @is_active = 0
        BEGIN
            SELECT 'ERROR' as status, 'User account is disabled' as message;
            RETURN;
        END
        
        IF @locked_until IS NOT NULL AND @locked_until > GETDATE()
        BEGIN
            SELECT 'ERROR' as status, 'Account is locked' as message;
            RETURN;
        END
        
        -- Update last login
        UPDATE wms_users 
        SET last_login = GETDATE(), failed_attempts = 0, locked_until = NULL
        WHERE LOGICALREF = @user_id;
        
        -- Return user data
        SELECT 'SUCCESS' as status, 
               LOGICALREF as id, username, email, full_name, role
        FROM wms_users
        WHERE LOGICALREF = @user_id;
    END
    ELSE
    BEGIN
        -- Update failed attempts
        UPDATE wms_users 
        SET failed_attempts = failed_attempts + 1,
            locked_until = CASE 
                WHEN failed_attempts >= 4 THEN DATEADD(MINUTE, 30, GETDATE())
                ELSE NULL
            END
        WHERE username = @username;
        
        SELECT 'ERROR' as status, 'Invalid credentials' as message;
    END
END
GO

-- Log user activity
CREATE OR ALTER PROCEDURE sp_log_user_activity
    @user_id INT,
    @action NVARCHAR(100),
    @module NVARCHAR(50) = NULL,
    @details NVARCHAR(MAX) = NULL,
    @ip_address NVARCHAR(45) = NULL
AS
BEGIN
    INSERT INTO wms_user_activities (user_id, action, module, details, ip_address)
    VALUES (@user_id, @action, @module, @details, @ip_address);
END
GO

PRINT 'User management tables and procedures created successfully';