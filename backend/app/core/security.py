"""Small dependency-free authentication for optional local multi-user mode."""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$%s$%s" % (
        _encode(salt),
        _encode(digest),
    )


def verify_password(password: str, stored_value: str | None) -> bool:
    if not stored_value:
        return False
    try:
        algorithm, work_factor, salt_value, digest_value = stored_value.split("$", 3)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode(salt_value),
            n=int(work_factor),
            r=8,
            p=1,
        )
        return hmac.compare_digest(digest, _decode(digest_value))
    except (TypeError, ValueError):
        return False


def create_access_token(user: User) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=max(1, settings.auth_token_ttl_hours))
    payload = {"sub": user.id, "exp": int(expires_at.timestamp())}
    payload_value = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        payload_value.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_value}.{_encode(signature)}", expires_at.replace(tzinfo=None)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    if not settings.auth_enabled:
        return _get_local_user(db)

    token = _token_from_request(request)
    user_id = _verify_access_token(token) if token else None
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentikasi diperlukan. Silakan masuk kembali.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _get_local_user(db: Session) -> User:
    user = db.query(User).filter(User.username == "local").first()
    if user is None:
        user = User(id="local-user", username="local", display_name="Local User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip()
    return request.query_params.get("access_token")


def _verify_access_token(token: str) -> str | None:
    try:
        payload_value, signature_value = token.split(".", 1)
        expected_signature = hmac.new(
            settings.auth_secret_key.encode("utf-8"),
            payload_value.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, _decode(signature_value)):
            return None
        payload = json.loads(_decode(payload_value).decode("utf-8"))
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            return None
        return str(payload["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
