"""
Authentication API Router
Mevcut kullanıcı sistemi ile entegre authentication
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

# Proje root'unu sys.path'e ekle
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.models.user import get_auth_manager, User
    from app.dao.logo import fetch_one
except ImportError as e:
    print(f"Auth import hatası: {e}")
    # Fallback - development için
    def get_auth_manager(): return None
    def fetch_one(query): return None

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Web login endpoint
    Mevcut PyQt authentication sistemini kullanır
    """
    try:
        auth_manager = get_auth_manager()
        
        if not auth_manager:
            # Development fallback
            if credentials.username == "admin" and credentials.password == "admin":
                return LoginResponse(
                    access_token="dev_token_123",
                    user={
                        "username": "admin",
                        "full_name": "System Admin", 
                        "role": "admin",
                        "active": True
                    }
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Geçersiz kullanıcı adı veya şifre"
                )
        
        # Gerçek authentication
        user = auth_manager.authenticate(credentials.username, credentials.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz kullanıcı adı veya şifre"
            )
        
        # Token oluştur (mevcut sistemden)
        token = auth_manager.create_token(user.username)
        
        return LoginResponse(
            access_token=token,
            user={
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "active": user.active,
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Giriş sırasında bir hata oluştu"
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """
    JWT token'dan kullanıcı bilgilerini çıkarır
    Mevcut token validation sistemini kullanır
    """
    if not credentials:
        return None
    
    try:
        auth_manager = get_auth_manager()
        
        if not auth_manager:
            # Development fallback
            if credentials.credentials == "dev_token_123":
                return {
                    "username": "admin",
                    "full_name": "System Admin",
                    "role": "admin"
                }
            return None
        
        # Gerçek token validation
        user_data = auth_manager.validate_token(credentials.credentials)
        return user_data
        
    except Exception as e:
        print(f"Token validation error: {e}")
        return None

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Authentication gerektiren endpoint'ler için decorator
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials

@router.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """
    Mevcut kullanıcı bilgilerini döndürür
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token geçersiz veya süresi dolmuş"
        )
    
    return user

@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(require_auth)):
    """
    Kullanıcı çıkışı
    """
    try:
        auth_manager = get_auth_manager()
        
        if auth_manager:
            # Token'ı invalidate et
            auth_manager.invalidate_token(credentials.credentials)
        
        return {"message": "Başarıyla çıkış yapıldı"}
        
    except Exception as e:
        print(f"Logout error: {e}")
        return {"message": "Çıkış yapıldı"}  # Her durumda success döndür

@router.post("/refresh")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(require_auth)):
    """
    Token yenileme
    """
    try:
        auth_manager = get_auth_manager()
        
        if not auth_manager:
            # Development fallback
            return LoginResponse(
                access_token="dev_token_refreshed_123",
                user={"username": "admin", "role": "admin"}
            )
        
        # Yeni token oluştur
        user_data = auth_manager.validate_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token geçersiz"
            )
        
        new_token = auth_manager.create_token(user_data["username"])
        
        return LoginResponse(
            access_token=new_token,
            user=user_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Refresh token error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token yenilenemedi"
        )