"""
Authentication API routes.

Endpoints:
  POST /register — Create a new user account
  POST /login    — Authenticate and receive a JWT token
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.database import get_connection
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.user_schema import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(request: UserRegisterRequest):
    """
    Create a new user account.

    - Validates email uniqueness
    - Hashes the password with bcrypt
    - Returns the created user (without password)
    """
    conn = get_connection()

    # Check if email already exists
    existing = conn.execute(
        "SELECT user_id FROM users WHERE email = ?",
        [request.email],
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user_id = str(uuid.uuid4())
    hashed = hash_password(request.password)

    conn.execute(
        "INSERT INTO users (user_id, email, password) VALUES (?, ?, ?)",
        [user_id, request.email, hashed],
    )

    return UserResponse(user_id=user_id, email=request.email)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate a user and return a JWT access token.

    The token encodes the user_id in the 'sub' claim and must be
    sent as a Bearer token in subsequent requests.
    """
    conn = get_connection()

    row = conn.execute(
        "SELECT user_id, password FROM users WHERE email = ?",
        [form_data.username],
    ).fetchone()

    if row is None or not verify_password(form_data.password, row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_id = row[0]
    token = create_access_token(data={"sub": user_id})

    return TokenResponse(access_token=token)
