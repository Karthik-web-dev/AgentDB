from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db, set_app_user
from app.core.security import decode_access_token
from app.models.user import User

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: extract, validate JWT, resolve and return the authenticated User.

    Raises HTTP 401 for any of:
    - Missing Authorization header
    - Malformed token
    - Invalid/expired signature
    - User not found in database
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    user_id_str = decode_access_token(credentials.credentials)
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception

    # Publish the caller to MySQL. The owned views (migration 009) read this identity, so row
    # isolation holds even if a query omits its WHERE clause. It is re-applied at every new
    # transaction, so it survives commits and connection changes.
    set_app_user(db, user.id)

    return user
