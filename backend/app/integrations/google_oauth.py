"""Google OAuth 2.0 Authorization Code + PKCE flow and encrypted credential manager."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import secrets
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import utc_now
from app.database.repositories import IntegrationRepository, OAuthStateRepository
from app.schemas.integration import IntegrationCardOut
from app.security.crypto import TokenCipher

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Least-privilege Google scopes
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
CALENDAR_READ_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
IDENTITY_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]


class GoogleOAuthConfigError(Exception):
    """Raised when Google OAuth client ID/secret or encryption key is missing."""


class GoogleOAuthFlowError(Exception):
    """Raised when OAuth state validation or token exchange fails."""


class IntegrationNotConnectedError(Exception):
    """Raised when a user invokes an integration they have not connected."""

    def __init__(self, provider: str, message: str | None = None) -> None:
        self.provider = provider
        super().__init__(
            message
            or f"{provider.title()} is not connected. Connect your Google account on the Integrations page."
        )


class IntegrationAuthError(Exception):
    """Raised when stored OAuth tokens are revoked, expired, or lack required scopes."""


def resolve_requested_scopes(
    service: Literal["gmail", "calendar", "both"],
    access_level: Literal["read", "write"] = "write",
) -> list[str]:
    """Return least-privilege Google scopes for the requested service and access level."""
    scopes: list[str] = list(IDENTITY_SCOPES)
    if service in ("gmail", "both"):
        scopes.append(GMAIL_READ_SCOPE)
        if access_level == "write":
            scopes.extend([GMAIL_COMPOSE_SCOPE, GMAIL_SEND_SCOPE])
    if service in ("calendar", "both"):
        scopes.append(CALENDAR_READ_SCOPE)
        if access_level == "write":
            scopes.append(CALENDAR_EVENTS_SCOPE)
    return list(dict.fromkeys(scopes))


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class GoogleOAuthService:
    """Manages Google OAuth authorization, token exchange, encryption, and refresh."""

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._http_client = http_client

    def is_oauth_configured(self) -> bool:
        return bool(self.settings.google_client_id and self.settings.google_client_secret)

    def is_encryption_configured(self) -> bool:
        if not self.settings.token_encryption_key:
            return False
        try:
            TokenCipher(self.settings.token_encryption_key)
            return True
        except Exception:
            return False

    def _require_oauth_and_cipher(self) -> TokenCipher:
        if not self.is_oauth_configured():
            raise GoogleOAuthConfigError(
                "Google OAuth credentials are not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in backend/.env."
            )
        return TokenCipher(self.settings.token_encryption_key)

    def build_authorization_url(
        self,
        db: Session,
        *,
        user_id: int,
        service: Literal["gmail", "calendar", "both"] = "both",
        access_level: Literal["read", "write"] = "write",
        force_consent: bool = True,
    ) -> tuple[str, str, list[str]]:
        """Create a CSRF-protected, PKCE-enabled Google OAuth authorization URL."""
        self._require_oauth_and_cipher()

        requested_scopes = resolve_requested_scopes(service, access_level=access_level)
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = _pkce_challenge(code_verifier)

        OAuthStateRepository(db).create(
            state=state,
            user_id=user_id,
            service=service,
            requested_scopes=requested_scopes,
            code_verifier=code_verifier,
            expires_at=utc_now() + timedelta(minutes=10),
        )

        params = {
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(requested_scopes),
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if force_consent:
            params["prompt"] = "consent"

        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}", state, requested_scopes

    def _post_token_endpoint(self, data: dict[str, str]) -> dict[str, Any]:
        owns_client = self._http_client is None
        client = self._http_client or httpx.Client(timeout=20.0)
        try:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
            payload = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                err_code = payload.get("error", "token_exchange_failed")
                err_desc = payload.get("error_description", f"HTTP {resp.status_code}")
                raise GoogleOAuthFlowError(f"{err_code}: {err_desc}")
            return payload
        except GoogleOAuthFlowError:
            raise
        except Exception as exc:
            raise GoogleOAuthFlowError(f"Failed to contact Google token endpoint: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _fetch_account_email(self, access_token: str) -> str | None:
        owns_client = self._http_client is None
        client = self._http_client or httpx.Client(timeout=15.0)
        try:
            resp = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json().get("email")
        except Exception:
            logger.warning("google_userinfo_fetch_failed")
        finally:
            if owns_client:
                client.close()
        return None

    def handle_callback(
        self,
        db: Session,
        *,
        code: str,
        state: str,
    ) -> tuple[int, str, str | None]:
        """Validate one-time state, exchange authorization code, and store encrypted tokens."""
        cipher = self._require_oauth_and_cipher()

        oauth_state = OAuthStateRepository(db).consume(state)
        if oauth_state is None:
            raise GoogleOAuthFlowError("Invalid or expired OAuth state parameter.")

        token_payload = self._post_token_endpoint(
            {
                "client_id": self.settings.google_client_id or "",
                "client_secret": self.settings.google_client_secret or "",
                "code": code,
                "code_verifier": oauth_state.code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": self.settings.google_redirect_uri,
            }
        )

        access_token = token_payload.get("access_token")
        if not access_token:
            raise GoogleOAuthFlowError("Google did not return an access token.")

        refresh_token = token_payload.get("refresh_token")
        expires_in = int(token_payload.get("expires_in", 3600))
        expiry = utc_now() + timedelta(seconds=expires_in)

        granted_str = token_payload.get("scope", "")
        granted_scopes = (
            granted_str.split()
            if granted_str
            else json.loads(oauth_state.requested_scopes)
        )
        account_email = self._fetch_account_email(access_token)

        encrypted_access = cipher.encrypt(access_token)
        encrypted_refresh = cipher.encrypt(refresh_token) if refresh_token else None

        providers_to_update: list[str] = []
        if oauth_state.service in ("gmail", "both") or any("gmail" in s for s in granted_scopes):
            providers_to_update.append("gmail")
        if oauth_state.service in ("calendar", "both") or any("calendar" in s for s in granted_scopes):
            providers_to_update.append("calendar")
        if not providers_to_update:
            providers_to_update = [oauth_state.service]

        repo = IntegrationRepository(db, user_id=oauth_state.user_id)
        for provider in providers_to_update:
            provider_scopes = [
                s
                for s in granted_scopes
                if provider in s or s in IDENTITY_SCOPES
            ]
            repo.upsert_connection(
                provider=provider,
                account_email=account_email,
                status="connected",
                granted_scopes=provider_scopes,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                token_expiry=expiry,
                encryption_version=TokenCipher.VERSION,
            )

        logger.info(
            "google_oauth_connected user_id=%s service=%s",
            oauth_state.user_id,
            oauth_state.service,
        )
        return oauth_state.user_id, oauth_state.service, account_email

    def get_valid_access_token(
        self,
        db: Session,
        *,
        user_id: int,
        provider: Literal["gmail", "calendar"],
        required_scopes: list[str] | None = None,
    ) -> str:
        """Return a valid decrypted access token for user_id + provider, refreshing if expired."""
        repo = IntegrationRepository(db, user_id=user_id)
        integration = repo.get_by_provider(provider)
        if integration is None or integration.status == "disconnected" or integration.credential is None:
            raise IntegrationNotConnectedError(provider)

        if integration.status == "needs_reconnect":
            raise IntegrationAuthError(
                f"{provider.title()} authorization expired or was revoked. Please reconnect."
            )

        if required_scopes:
            granted = set(json.loads(integration.granted_scopes or "[]"))
            missing = [scope for scope in required_scopes if scope not in granted]
            if missing:
                raise IntegrationAuthError(
                    f"{provider.title()} is missing required permission(s): {', '.join(missing)}. "
                    "Please reconnect and approve the requested permissions."
                )

        cipher = TokenCipher(self.settings.token_encryption_key)
        cred = integration.credential
        now = utc_now()
        expiry = cred.token_expiry
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if cred.encrypted_access_token and expiry is not None and expiry > (now + timedelta(seconds=60)):
            return cipher.decrypt(cred.encrypted_access_token)

        # Access token missing or expired -> refresh using encrypted refresh token.
        if not cred.encrypted_refresh_token:
            repo.update_status(provider, "needs_reconnect")
            raise IntegrationAuthError(
                f"{provider.title()} access token expired and no refresh token is stored. Please reconnect."
            )

        if not self.is_oauth_configured():
            raise GoogleOAuthConfigError(
                "Google OAuth credentials are required to refresh access tokens."
            )

        refresh_token = cipher.decrypt(cred.encrypted_refresh_token)
        try:
            token_payload = self._post_token_endpoint(
                {
                    "client_id": self.settings.google_client_id or "",
                    "client_secret": self.settings.google_client_secret or "",
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
            )
        except GoogleOAuthFlowError as exc:
            repo.update_status(provider, "needs_reconnect")
            logger.warning("google_token_refresh_failed user_id=%s provider=%s", user_id, provider)
            raise IntegrationAuthError(
                f"{provider.title()} access was revoked or expired ({exc}). Please reconnect."
            ) from exc

        new_access_token = token_payload.get("access_token")
        if not new_access_token:
            repo.update_status(provider, "needs_reconnect")
            raise IntegrationAuthError(
                f"{provider.title()} token refresh did not return an access token. Please reconnect."
            )

        expires_in = int(token_payload.get("expires_in", 3600))
        new_expiry = utc_now() + timedelta(seconds=expires_in)
        repo.update_access_token(
            integration,
            encrypted_access_token=cipher.encrypt(new_access_token),
            token_expiry=new_expiry,
            encryption_version=TokenCipher.VERSION,
        )
        return new_access_token

    def disconnect(
        self,
        db: Session,
        *,
        user_id: int,
        provider: Literal["gmail", "calendar", "both"] = "both",
    ) -> list[str]:
        """Delete stored encrypted credentials and mark integration(s) disconnected."""
        repo = IntegrationRepository(db, user_id=user_id)
        targets = ["gmail", "calendar"] if provider == "both" else [provider]
        disconnected: list[str] = []
        for target in targets:
            if repo.disconnect(target):
                disconnected.append(target)
        return disconnected

    def build_integration_cards(
        self,
        db: Session,
        *,
        user_id: int,
    ) -> list[IntegrationCardOut]:
        """Build safe UI cards for active Google integrations and planned Coming Soon items."""
        repo = IntegrationRepository(db, user_id=user_id)
        by_provider = {item.provider: item for item in repo.list_all()}
        oauth_ok = self.is_oauth_configured()

        def google_card(
            provider: str,
            display_name: str,
            description: str,
            permissions: list[str],
        ) -> IntegrationCardOut:
            row = by_provider.get(provider)
            scopes = json.loads(row.granted_scopes) if row and row.granted_scopes else []
            return IntegrationCardOut(
                provider=provider,
                display_name=display_name,
                description=description,
                category="active",
                status=row.status if row else "disconnected",
                account_email=row.account_email if row else None,
                granted_scopes=scopes,
                available_permissions=permissions,
                last_connected_at=row.last_connected_at if row else None,
                oauth_configured=oauth_ok,
                demo_mode_active=self.settings.demo_mode,
            )

        cards = [
            google_card(
                "gmail",
                "Gmail",
                "Search emails, read threads, create drafts, and send approval-gated replies.",
                [
                    "Read & search emails (gmail.readonly)",
                    "Create drafts (gmail.compose)",
                    "Send approved emails (gmail.send)",
                ],
            ),
            google_card(
                "calendar",
                "Google Calendar",
                "Check schedule availability, detect conflicts, and create approval-gated events.",
                [
                    "Read calendars & events (calendar.readonly)",
                    "Create, update & delete approved events (calendar.events)",
                ],
            ),
            IntegrationCardOut(
                provider="google_drive",
                display_name="Google Drive",
                description="Search and summarize documents and attachments from Drive.",
                category="coming_soon",
                status="coming_soon",
                available_permissions=["Read Drive files (planned)"],
            ),
            IntegrationCardOut(
                provider="web_search",
                display_name="Web Search",
                description="Search the live web and summarize results with source citations.",
                category="coming_soon",
                status="coming_soon",
                available_permissions=["Read-only cited web search (planned)"],
            ),
            IntegrationCardOut(
                provider="browser_automation",
                display_name="Browser Automation",
                description="Isolated Playwright browser workflows for allowlisted websites.",
                category="coming_soon",
                status="coming_soon",
                available_permissions=["Allowlisted navigation & approval-gated actions (planned)"],
            ),
            IntegrationCardOut(
                provider="notion",
                display_name="Notion",
                description="Sync meeting notes, project wikis, and action items with Notion.",
                category="coming_soon",
                status="coming_soon",
                available_permissions=["Read & update Notion pages (planned)"],
            ),
            IntegrationCardOut(
                provider="slack",
                display_name="Slack",
                description="Summarize team channels and draft approval-gated replies.",
                category="coming_soon",
                status="coming_soon",
                available_permissions=["Read channels & post approved messages (planned)"],
            ),
        ]
        return cards
