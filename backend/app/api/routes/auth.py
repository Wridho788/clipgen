"""Optional local account endpoints, enabled with AUTH_ENABLED=true."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
    AuthUserResponse,
)

router = APIRouter()


@router.get("/config")
async def auth_config():
    return {
        "enabled": settings.auth_enabled,
        "registration_enabled": settings.auth_enabled,
    }


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register(data: AuthRegisterRequest, db: Session = Depends(get_db)):
    _require_auth_enabled()
    username = data.username.lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username sudah digunakan")

    user = User(
        username=username,
        display_name=data.display_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _session_response(user)


@router.post("/login", response_model=AuthSessionResponse)
async def login(data: AuthLoginRequest, db: Session = Depends(get_db)):
    _require_auth_enabled()
    user = db.query(User).filter(User.username == data.username.lower()).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau password tidak sesuai")
    return _session_response(user)


@router.get("/me", response_model=AuthUserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


def _require_auth_enabled() -> None:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=409,
            detail="Autentikasi lokal belum aktif. Set AUTH_ENABLED=true terlebih dahulu.",
        )


def _session_response(user: User) -> AuthSessionResponse:
    token, expires_at = create_access_token(user)
    return AuthSessionResponse(
        access_token=token,
        expires_at=expires_at,
        user=_user_response(user),
    )


def _user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(id=user.id, username=user.username, display_name=user.display_name)
