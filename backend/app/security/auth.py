"""Lightweight LifeDesk user authentication, signed session tokens, and rate limiting."""

import base64
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import threading
import time

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.database import get_db
from app.database.models import User

TOKEN_TTL_HOURS = 24 * 7


def create_session_token(user_id: int, secret_key: str) -> str:
    """Create an HMAC-SHA256 signed session token bound to user_id."""
    exp = int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())
    payload = json.dumps({"uid": user_id, "exp": exp}, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    sig = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def verify_session_token(token: str, secret_key: str) -> int:
    """Verify an HMAC-signed session token and return the authenticated user_id."""
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed session token.")
    payload_b64, sig_b64 = parts
    expected_sig = hmac.new(
        secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")
    if not hmac.compare_digest(sig_b64, expected_b64):
        raise ValueError("Invalid session token signature.")

    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    exp = int(data.get("exp", 0))
    if exp < int(time.time()):
        raise ValueError("Session token expired.")
    uid = int(data["uid"])
    return uid


def get_current_user(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the authenticated LifeDesk user independently of Google OAuth."""
    raw_token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()
    elif x_session_token:
        raw_token = x_session_token.strip()

    if raw_token:
        try:
            user_id = verify_session_token(raw_token, settings.app_secret_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired LifeDesk session token: {exc}",
            ) from exc

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user account no longer exists.",
            )
        return user

    if settings.allow_demo_user_fallback:
        demo_user = db.query(User).filter(User.id == 1).first()
        if demo_user is None:
            demo_user = User(
                id=1,
                name="LifeDesk User",
                email="demo@lifedesk.local",
                timezone=settings.default_timezone,
            )
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)
        return demo_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Sign in to LifeDesk first.",
    )


class InMemoryRateLimiter:
    """Simple sliding-window per-user rate limiter for sensitive endpoints."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests for this sensitive operation. Please slow down.",
                )
            bucket.append(now)


sensitive_rate_limiter = InMemoryRateLimiter(max_requests=30, window_seconds=60)
