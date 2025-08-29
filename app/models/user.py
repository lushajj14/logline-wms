"""
User Model and Authentication
==============================
User management and authentication system for WMS.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import hashlib
import secrets
import bcrypt
from jose import jwt, JWTError
import logging

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User model."""
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    @property
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == 'admin'
    
    @property
    def is_supervisor(self) -> bool:
        """Check if user is supervisor or higher."""
        return self.role in ('admin', 'supervisor')
    
    @property
    def can_edit(self) -> bool:
        """Check if user can edit data."""
        return self.role in ('admin', 'supervisor', 'operator')
    
    @property
    def can_view_only(self) -> bool:
        """Check if user is view-only."""
        return self.role == 'viewer'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """Create from dictionary."""
        return cls(
            id=data.get('id', 0),
            username=data['username'],
            email=data['email'],
            full_name=data.get('full_name', ''),
            role=data.get('role', 'operator'),
            is_active=data.get('is_active', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            last_login=datetime.fromisoformat(data['last_login']) if data.get('last_login') else None
        )


class AuthManager:
    """Authentication manager."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize auth manager.
        
        Args:
            secret_key: JWT secret key
            algorithm: JWT algorithm
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self._current_user: Optional[User] = None
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            password: Plain text password
            hashed: Hashed password
            
        Returns:
            True if password matches
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def create_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT token for user.
        
        Args:
            user: User object
            expires_delta: Token expiration time
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=2)
        
        payload = {
            'sub': user.username,
            'user_id': user.id,
            'role': user.role,
            'exp': expire,
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def login(self, username: str, password: str) -> Optional[tuple[User, str]]:
        """
        Authenticate user and return token.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            Tuple of (User, token) if successful, None otherwise
        """
        from app.dao.users_new import UserDAO
        
        dao = UserDAO()
        user_data = dao.authenticate(username, password)
        
        if user_data:
            user = User.from_dict(user_data)
            token = self.create_token(user)
            self._current_user = user
            
            # Log activity
            dao.log_activity(user.id, "login", "auth", f"Logged in from desktop app")
            
            return user, token
        
        return None
    
    def get_current_user(self) -> Optional[User]:
        """Get currently logged in user."""
        return self._current_user
    
    def logout(self):
        """Logout current user."""
        if self._current_user:
            from app.dao.users_new import UserDAO
            dao = UserDAO()
            dao.log_activity(self._current_user.id, "logout", "auth", "Logged out")
            self._current_user = None
    
    @property
    def current_user(self) -> Optional[User]:
        """Get current logged in user."""
        return self._current_user
    
    @current_user.setter
    def current_user(self, user: Optional[User]):
        """Set current user."""
        self._current_user = user
    
    def has_permission(self, module: str, action: str = 'view') -> bool:
        """
        Check if current user has permission.
        
        Args:
            module: Module name
            action: Action type (view, create, update, delete)
            
        Returns:
            True if user has permission
        """
        if not self._current_user:
            return False
        
        # Admins have all permissions
        if self._current_user.is_admin:
            return True
        
        # Check role-based permissions
        role_permissions = {
            'supervisor': {
                'view': True,
                'create': True,
                'update': True,
                'delete': False
            },
            'operator': {
                'view': True,
                'create': True,
                'update': True,
                'delete': False
            },
            'viewer': {
                'view': True,
                'create': False,
                'update': False,
                'delete': False
            }
        }
        
        role = self._current_user.role
        if role in role_permissions:
            return role_permissions[role].get(action, False)
        
        return False


# Global auth manager instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    global _auth_manager
    
    if _auth_manager is None:
        from app.config.env_config import get_config
        config = get_config()
        api_config = config.get_api_config()
        
        _auth_manager = AuthManager(
            secret_key=api_config['secret_key'],
            algorithm=api_config['algorithm']
        )
    
    return _auth_manager