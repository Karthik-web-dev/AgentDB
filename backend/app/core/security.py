from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt

from app.core.config import settings


def get_password_hash(password: str) -> str:
    """Generate a bcrypt password hash. Never store or log the plaintext password."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token with expiration.

    Args:
        subject: The user identifier to embed as the JWT 'sub' claim (e.g. user id as string).
        expires_delta: Optional custom expiration window; defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Signed JWT string encoded with HS256 and settings.SECRET_KEY.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Decode and validate a JWT access token.

    Returns the 'sub' (user id) if the token is valid, unexpired, and correctly signed.
    Returns None if the token is missing, malformed, expired, or has an invalid signature.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        subject: Optional[str] = payload.get("sub")
        if subject is None:
            return None
        return subject
    except JWTError:
        return None