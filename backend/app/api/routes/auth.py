"""LifeDesk user session endpoints (separate from Google OAuth)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.database import get_db
from app.database.models import User
from app.database.repositories import UserRepository
from app.schemas.auth import (
    AuthSessionResponse,
    UserListResponse,
    UserLoginRequest,
    UserOut,
    UserRegisterRequest,
)
from app.security.auth import create_session_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TimezoneUpdateRequest(BaseModel):
    timezone: str = Field(..., min_length=1, max_length=64)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated LifeDesk user profile."""
    return UserOut.model_validate(current_user)


@router.get("/users", response_model=UserListResponse)
def list_users(db: Session = Depends(get_db)) -> UserListResponse:
    """List local LifeDesk user profiles (no credentials exposed)."""
    users = UserRepository(db).list_all()
    return UserListResponse(users=[UserOut.model_validate(u) for u in users])


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthSessionResponse:
    """Register a new LifeDesk user and return a signed session token."""
    repo = UserRepository(db)
    if repo.get_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    user = repo.create(name=payload.name, email=payload.email, user_timezone=payload.timezone)
    token = create_session_token(user.id, settings.app_secret_key)
    return AuthSessionResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthSessionResponse)
def login_user(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthSessionResponse:
    """Authenticate as a LifeDesk user and issue a signed session token."""
    repo = UserRepository(db)
    user = None
    if payload.user_id is not None:
        user = repo.get_by_id(payload.user_id)
    elif payload.email is not None:
        user = repo.get_by_email(payload.email)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide user_id or email to sign in.",
        )

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    token = create_session_token(user.id, settings.app_secret_key)
    return AuthSessionResponse(access_token=token, user=UserOut.model_validate(user))


@router.patch("/timezone", response_model=UserOut)
def update_timezone(
    payload: TimezoneUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Update the authenticated user's configured timezone."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(payload.timezone.strip())
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown IANA timezone '{payload.timezone}'. Example: 'Asia/Kolkata' or 'UTC'.",
        ) from exc

    updated = UserRepository(db).update_timezone(current_user.id, payload.timezone)
    assert updated is not None
    return UserOut.model_validate(updated)
