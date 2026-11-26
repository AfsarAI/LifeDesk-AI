"""Google OAuth 2.0 and integration management endpoints."""

from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.database import get_db
from app.database.models import User
from app.integrations.google_oauth import (
    GoogleOAuthConfigError,
    GoogleOAuthFlowError,
    GoogleOAuthService,
)
from app.schemas.integration import (
    GoogleConnectResponse,
    GoogleDisconnectResponse,
    GoogleStatusResponse,
    IntegrationListResponse,
)
from app.security.auth import get_current_user, sensitive_rate_limiter
from app.security.crypto import TokenEncryptionError

router = APIRouter(prefix="/integrations", tags=["Integrations"])


def get_oauth_service(settings: Settings = Depends(get_settings)) -> GoogleOAuthService:
    return GoogleOAuthService(settings)


@router.get("", response_model=IntegrationListResponse)
def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth: GoogleOAuthService = Depends(get_oauth_service),
) -> IntegrationListResponse:
    """List active and planned integrations scoped to the authenticated user."""
    cards = oauth.build_integration_cards(db, user_id=current_user.id)
    return IntegrationListResponse(
        integrations=cards,
        oauth_configured=oauth.is_oauth_configured(),
        encryption_configured=oauth.is_encryption_configured(),
    )


@router.get("/google/connect", response_model=GoogleConnectResponse)
def connect_google(
    service: Literal["gmail", "calendar", "both"] = Query(default="both"),
    access_level: Literal["read", "write"] = Query(default="write"),
    redirect: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth: GoogleOAuthService = Depends(get_oauth_service),
) -> GoogleConnectResponse | RedirectResponse:
    """Generate a CSRF/PKCE-protected Google OAuth consent URL for the authenticated user."""
    sensitive_rate_limiter.check(f"oauth_connect:{current_user.id}")
    try:
        auth_url, state, scopes = oauth.build_authorization_url(
            db,
            user_id=current_user.id,
            service=service,
            access_level=access_level,
            force_consent=True,
        )
    except (GoogleOAuthConfigError, TokenEncryptionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if redirect:
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    return GoogleConnectResponse(
        authorization_url=auth_url,
        state=state,
        service=service,
        requested_scopes=scopes,
    )


@router.get("/google/callback")
def google_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    oauth: GoogleOAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """Validate OAuth state, exchange authorization code, and redirect back to frontend."""
    base_redirect = f"{settings.frontend_url}/"

    if error:
        qs = urlencode({"page": "integrations", "oauth": "error", "reason": error})
        return RedirectResponse(url=f"{base_redirect}?{qs}", status_code=status.HTTP_302_FOUND)

    if not code or not state:
        qs = urlencode(
            {
                "page": "integrations",
                "oauth": "error",
                "reason": "Missing authorization code or state parameter.",
            }
        )
        return RedirectResponse(url=f"{base_redirect}?{qs}", status_code=status.HTTP_302_FOUND)

    try:
        _uid, service, _email = oauth.handle_callback(db, code=code, state=state)
    except (GoogleOAuthFlowError, GoogleOAuthConfigError, TokenEncryptionError) as exc:
        qs = urlencode({"page": "integrations", "oauth": "error", "reason": str(exc)})
        return RedirectResponse(url=f"{base_redirect}?{qs}", status_code=status.HTTP_302_FOUND)

    qs = urlencode({"page": "integrations", "oauth": "connected", "service": service})
    return RedirectResponse(url=f"{base_redirect}?{qs}", status_code=status.HTTP_302_FOUND)


@router.get("/google/status", response_model=GoogleStatusResponse)
def google_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth: GoogleOAuthService = Depends(get_oauth_service),
) -> GoogleStatusResponse:
    """Return safe Gmail & Google Calendar connection status without exposing tokens."""
    cards = {
        c.provider: c for c in oauth.build_integration_cards(db, user_id=current_user.id)
    }
    return GoogleStatusResponse(
        oauth_configured=oauth.is_oauth_configured(),
        encryption_configured=oauth.is_encryption_configured(),
        gmail=cards["gmail"],
        calendar=cards["calendar"],
    )


@router.post("/google/disconnect", response_model=GoogleDisconnectResponse)
def disconnect_google(
    provider: Literal["gmail", "calendar", "both"] = Query(default="both"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth: GoogleOAuthService = Depends(get_oauth_service),
) -> GoogleDisconnectResponse:
    """Delete stored encrypted Google credentials for the authenticated user."""
    sensitive_rate_limiter.check(f"oauth_disconnect:{current_user.id}")
    disconnected = oauth.disconnect(db, user_id=current_user.id, provider=provider)
    return GoogleDisconnectResponse(
        disconnected=disconnected,
        message=(
            f"Disconnected {', '.join(disconnected)}."
            if disconnected
            else "No active Google connection found to disconnect."
        ),
    )


@router.post("/google/reconnect", response_model=GoogleConnectResponse)
def reconnect_google(
    service: Literal["gmail", "calendar", "both"] = Query(default="both"),
    access_level: Literal["read", "write"] = Query(default="write"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth: GoogleOAuthService = Depends(get_oauth_service),
) -> GoogleConnectResponse:
    """Generate a fresh OAuth consent URL to refresh permissions or recover from revocation."""
    sensitive_rate_limiter.check(f"oauth_reconnect:{current_user.id}")
    try:
        auth_url, state, scopes = oauth.build_authorization_url(
            db,
            user_id=current_user.id,
            service=service,
            access_level=access_level,
            force_consent=True,
        )
    except (GoogleOAuthConfigError, TokenEncryptionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return GoogleConnectResponse(
        authorization_url=auth_url,
        state=state,
        service=service,
        requested_scopes=scopes,
    )
