import re
from datetime import datetime
from pydantic import BaseModel, field_validator

# Deliberately simple: rejects obviously malformed addresses without adding
# an extra dependency. Deliverability is not checked.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 255 or not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address.")
    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    """Payload accepted for POST /api/auth/register."""
    email: str
    password: str
    full_name: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _validate_email(v)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name must not be empty.")
        return v


class UserLogin(BaseModel):
    """Payload accepted for POST /api/auth/login."""
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        # Login uses the same normalization but does not reject here; a
        # malformed address simply fails authentication with a generic 401.
        return v.strip().lower()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Safe public representation of a user. Never includes password_hash."""
    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT access token response."""
    access_token: str
    token_type: str = "bearer"
