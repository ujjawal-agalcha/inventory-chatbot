import os
import hashlib
import secrets
from datetime import datetime, timedelta

# pyrefly: ignore [missing-import]
import jwt
# pyrefly: ignore [missing-import]
from fastapi import Request, Depends, HTTPException, status, WebSocket
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from models import get_db, User


# ============================================================
# PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# ============================================================

def hash_password(password: str) -> str:
    """Generate a secure salted hash for the given password."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"{salt}:{pwd_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored salted hash."""
    if not hashed_password or ":" not in hashed_password:
        return False
    try:
        salt, stored_hash = hashed_password.split(":", 1)
        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return secrets.compare_digest(calculated_hash, stored_hash)
    except Exception:
        return False


# ============================================================
# JWT TOKEN MANAGEMENT
# ============================================================

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_user_from_token(token: str, db: Session) -> User | None:
    """Extract user from a JWT token."""
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


# ============================================================
# FASTAPI DEPENDENCY: GET CURRENT USER
# ============================================================

def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Extract user from Bearer header, cookie, or session."""
    token = None

    # 1. Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    # 2. Check Cookie
    if not token:
        token = request.cookies.get("access_token")

    # 3. Check query param
    if not token:
        token = request.query_params.get("token")

    # 4. Check session fallback
    if not token:
        session_user = request.session.get("user")
        if session_user and isinstance(session_user, dict):
            user_id = session_user.get("id")
            if user_id:
                return db.query(User).filter(User.id == user_id).first()
            username = session_user.get("username")
            if username:
                return db.query(User).filter(User.username == username).first()

    if not token:
        return None

    return get_user_from_token(token, db)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency requiring an authenticated user."""
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ============================================================
# WEBSOCKET AUTHENTICATION
# ============================================================

def authenticate_websocket(
    websocket: WebSocket,
    db: Session,
) -> User | None:
    """Authenticate WebSocket connection using query param or cookie."""
    token = websocket.query_params.get("token")

    if not token:
        token = websocket.cookies.get("access_token")

    if not token:
        # Check session cookie if present
        session_cookie = websocket.cookies.get("inventory_session")
        if session_cookie:
            # Let token authentication be the primary method
            pass

    if not token:
        return None

    return get_user_from_token(token, db)
