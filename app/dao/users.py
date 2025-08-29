"""
User Data Access Object
========================
Database operations for user management.
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging
import bcrypt
from app.dao.logo import fetch_one, fetch_all, execute_query, get_conn

logger = logging.getLogger(__name__)


class UserDAO:
    """User database operations."""
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User data if authenticated, None otherwise
        """
        try:
            # First get user to check password
            user = fetch_one(
                """
                SELECT LOGICALREF as id, username, email, password_hash, full_name, role, 
                       is_active, locked_until, failed_attempts
                FROM wms_users 
                WHERE username = ? OR email = ?
                """,
                [username, username]
            )
            
            if not user:
                return None
            
            # Check if account is locked
            if user['locked_until'] and user['locked_until'] > datetime.now():
                logger.warning(f"Login attempt for locked account: {username}")
                return None
            
            # Check if account is active
            if not user['is_active']:
                logger.warning(f"Login attempt for inactive account: {username}")
                return None
            
            # Verify password
            if not self._verify_password(password, user['password_hash']):
                # Update failed attempts
                self._update_failed_attempts(user['id'])
                return None
            
            # Reset failed attempts and update last login
            execute_query(
                """
                UPDATE wms_users 
                SET last_login = GETDATE(), 
                    failed_attempts = 0, 
                    locked_until = NULL
                WHERE LOGICALREF = ?
                """,
                [user['id']]
            )
            
            # Return user data (without password hash)
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name'],
                'role': user['role'],
                'is_active': user['is_active']
            }
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        return fetch_one(
            """
            SELECT LOGICALREF as id, username, email, full_name, role, is_active,
                   created_at, updated_at, last_login
            FROM wms_users
            WHERE LOGICALREF = ?
            """,
            [user_id]
        )
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        return fetch_one(
            """
            SELECT LOGICALREF as id, username, email, full_name, role, is_active,
                   created_at, updated_at, last_login
            FROM wms_users
            WHERE username = ?
            """,
            [username]
        )
    
    def get_all_users(self) -> List[Dict]:
        """Get all users."""
        return fetch_all(
            """
            SELECT LOGICALREF as id, username, email, full_name, role, is_active,
                   created_at, updated_at, last_login
            FROM wms_users
            ORDER BY username
            """
        )
    
    def create_user(self, username: str, email: str, password: str, 
                   full_name: str, role: str = 'operator') -> Optional[int]:
        """
        Create new user.
        
        Args:
            username: Username
            email: Email address
            password: Plain text password
            full_name: Full name
            role: User role
            
        Returns:
            New user ID if successful
        """
        try:
            # Hash password
            password_hash = self._hash_password(password)
            
            # Insert user
            result = fetch_one(
                """
                INSERT INTO wms_users (username, email, password_hash, full_name, role)
                OUTPUT INSERTED.LOGICALREF as id
                VALUES (?, ?, ?, ?, ?)
                """,
                [username, email, password_hash, full_name, role]
            )
            
            if result:
                logger.info(f"User created: {username}")
                return result['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """
        Update user information.
        
        Args:
            user_id: User ID
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        try:
            allowed_fields = ['email', 'full_name', 'role', 'is_active']
            updates = []
            values = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)
            
            if not updates:
                return False
            
            updates.append("updated_at = GETDATE()")
            values.append(user_id)
            
            query = f"""
                UPDATE wms_users 
                SET {', '.join(updates)}
                WHERE LOGICALREF = ?
            """
            
            rows = execute_query(query, values)
            return rows > 0
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """Change user password."""
        try:
            password_hash = self._hash_password(new_password)
            
            rows = execute_query(
                """
                UPDATE wms_users 
                SET password_hash = ?, updated_at = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [password_hash, user_id]
            )
            
            return rows > 0
            
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete by deactivating)."""
        try:
            rows = execute_query(
                """
                UPDATE wms_users 
                SET is_active = 0, updated_at = GETDATE()
                WHERE LOGICALREF = ?
                """,
                [user_id]
            )
            
            return rows > 0
            
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
    
    def log_activity(self, user_id: int, action: str, module: str = None, 
                    details: str = None, ip_address: str = None) -> bool:
        """Log user activity."""
        try:
            execute_query(
                """
                INSERT INTO wms_user_activities (user_id, action, module, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
                """,
                [user_id, action, module, details, ip_address]
            )
            return True
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
            return False
    
    def get_user_activities(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get user activities."""
        return fetch_all(
            """
            SELECT TOP (?) action, module, details, ip_address, created_at
            FROM wms_user_activities
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            [limit, user_id]
        )
    
    def get_recent_activities(self, limit: int = 100) -> List[Dict]:
        """Get recent activities from all users."""
        return fetch_all(
            """
            SELECT TOP (?) 
                a.action, a.module, a.details, a.created_at,
                u.username, u.full_name
            FROM wms_user_activities a
            JOIN wms_users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            """,
            [limit]
        )
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    
    def _update_failed_attempts(self, user_id: int):
        """Update failed login attempts."""
        try:
            execute_query(
                """
                UPDATE wms_users 
                SET failed_attempts = failed_attempts + 1,
                    locked_until = CASE 
                        WHEN failed_attempts >= 4 
                        THEN DATEADD(MINUTE, 30, GETDATE())
                        ELSE locked_until
                    END
                WHERE LOGICALREF = ?
                """,
                [user_id]
            )
        except Exception as e:
            logger.error(f"Error updating failed attempts: {e}")
    
    def check_table_exists(self) -> bool:
        """Check if users table exists."""
        try:
            result = fetch_one(
                """
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'wms_users'
                """
            )
            return result and result['count'] > 0
        except:
            return False
    
    def init_tables(self) -> bool:
        """Initialize user tables if they don't exist."""
        try:
            # Read and execute migration script
            from pathlib import Path
            migration_file = Path(__file__).parent.parent.parent / "migrations" / "001_create_users_table.sql"
            
            if migration_file.exists():
                with open(migration_file, 'r') as f:
                    sql_script = f.read()
                
                # Execute the script
                with get_conn() as conn:
                    cursor = conn.cursor()
                    
                    # Split by GO statements
                    statements = sql_script.split('\nGO\n')
                    
                    for statement in statements:
                        if statement.strip():
                            try:
                                cursor.execute(statement)
                                conn.commit()
                            except Exception as e:
                                logger.warning(f"Statement execution warning: {e}")
                
                logger.info("User tables initialized successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error initializing tables: {e}")
            return False