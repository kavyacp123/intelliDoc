"""
Pydantic schemas for user-related API requests and responses.
"""

from pydantic import BaseModel, EmailStr


class UserRegisterRequest(BaseModel):
    """POST /register body."""

    email: str
    password: str


class UserLoginRequest(BaseModel):
    """POST /login body."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response after successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user representation (never includes password)."""

    user_id: str
    email: str
