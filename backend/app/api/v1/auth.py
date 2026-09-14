"""
Authentication endpoints — login, register, profile.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, decode_token

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
        
    result = await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT tokens."""
    clean_username = form_data.username.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == clean_username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def register():
    """Register a new user account."""
    return {"message": "Registration endpoint — implemented in Phase 17"}


@router.get("/me")
async def get_user_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "faculty_id": str(current_user.faculty_id) if current_user.faculty_id else None,
        "is_active": current_user.is_active
    }

from pydantic import BaseModel
class SettingsUpdate(BaseModel):
    notifications_enabled: bool

@router.get("/settings")
async def get_settings(current_user: User = Depends(get_current_user)):
    return {
        "notifications_enabled": True,
        "theme": "dark",
        "api_keys_configured": ["openalex", "crossref"]
    }

@router.put("/settings")
async def update_settings(settings: SettingsUpdate, current_user: User = Depends(get_current_user)):
    return {"message": "Settings updated"}
