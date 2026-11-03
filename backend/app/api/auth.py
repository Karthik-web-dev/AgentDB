from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.core.security import get_password_hash, verify_password, create_access_token
from app.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from app.api.dependencies import get_current_user

router = APIRouter(prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> UserResponse:
    """Register a new user account.

    - Email is normalized to lowercase.
    - Password is hashed with bcrypt before storage.
    - Duplicate emails are rejected with HTTP 409.
    - Default role 'user' is assigned; callers cannot elevate their own role.
    """
    # Check for duplicate email before attempting insert
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    new_user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name,
        role="user",  # Safe default: callers may not assign privileged roles during registration
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Authenticate a user and return a JWT bearer token.

    Deliberately returns identical error messages for unknown email and wrong
    password to avoid leaking account existence information.
    """
    invalid_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise invalid_credentials_exception

    if not verify_password(payload.password, user.password_hash):
        raise invalid_credentials_exception

    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return safe profile information for the currently authenticated user.

    Requires a valid Bearer token. Never returns password_hash or internal credentials.
    """
    return UserResponse.model_validate(current_user)
