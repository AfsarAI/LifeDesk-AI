"""Automated tests for Google OAuth 2.0 state validation, encryption, refresh, and disconnect."""

from datetime import timedelta
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import User, utc_now
from app.database.repositories import IntegrationRepository, UserRepository
from app.integrations.google_oauth import (
    GMAIL_READ_SCOPE,
    GoogleOAuthFlowError,
    GoogleOAuthService,
    IntegrationAuthError,
)
from app.security.crypto import TokenCipher, TokenEncryptionError


def _make_settings(fernet_key: str | None = None) -> Settings:
    return Settings(
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:8000/api/integrations/google/callback",
        token_encryption_key=fernet_key or Fernet.generate_key().decode("utf-8"),
        app_secret_key="test-app-secret-key-at-least-32-chars",
    )


def _mock_http_transport(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_token_cipher_roundtrip_and_invalid_key() -> None:
    key1 = Fernet.generate_key().decode("utf-8")
    key2 = Fernet.generate_key().decode("utf-8")
    cipher1 = TokenCipher(key1)
    cipher2 = TokenCipher(key2)

    raw_refresh = "1//0gFakeRefreshTokenSecret"
    encrypted = cipher1.encrypt(raw_refresh)
    assert raw_refresh not in encrypted
    assert cipher1.decrypt(encrypted) == raw_refresh

    with pytest.raises(TokenEncryptionError):
        cipher2.decrypt(encrypted)

    with pytest.raises(TokenEncryptionError):
        TokenCipher(None)


def test_oauth_state_validation_callback_and_refresh_token_preservation(
    db_session: Session,
) -> None:
    settings = _make_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/token" in str(request.url):
            body = parse_qs(request.content.decode("utf-8"))
            if body.get("code") == ["code_first"]:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "ya29.access_one",
                        "refresh_token": "1//refresh_keep_me",
                        "expires_in": 3600,
                        "scope": f"openid https://www.googleapis.com/auth/userinfo.email {GMAIL_READ_SCOPE}",
                    },
                )
            # Incremental re-consent where Google omits refresh_token.
            return httpx.Response(
                200,
                json={
                    "access_token": "ya29.access_two",
                    "expires_in": 3600,
                    "scope": GMAIL_READ_SCOPE,
                },
            )
        if "userinfo" in str(request.url):
            return httpx.Response(200, json={"email": "alice@gmail.com"})
        return httpx.Response(404)

    service = GoogleOAuthService(settings, http_client=_mock_http_transport(handler))
    auth_url, state, _scopes = service.build_authorization_url(
        db_session, user_id=1, service="gmail", access_level="read"
    )
    parsed = parse_qs(urlparse(auth_url).query)
    assert parsed["state"] == [state]
    assert parsed["code_challenge_method"] == ["S256"]

    uid, connected_service, email = service.handle_callback(
        db_session, code="code_first", state=state
    )
    assert uid == 1
    assert connected_service == "gmail"
    assert email == "alice@gmail.com"

    # Replaying the exact same one-time state must fail.
    with pytest.raises(GoogleOAuthFlowError):
        service.handle_callback(db_session, code="code_first", state=state)

    # Invalid state must fail.
    with pytest.raises(GoogleOAuthFlowError):
        service.handle_callback(db_session, code="code_first", state="forged_state")

    # Second consent omitting refresh_token must NOT overwrite stored encrypted refresh token.
    _, state2, _ = service.build_authorization_url(db_session, user_id=1, service="gmail")
    service.handle_callback(db_session, code="code_second", state=state2)

    integration = IntegrationRepository(db_session, user_id=1).get_by_provider("gmail")
    assert integration is not None and integration.credential is not None
    cipher = TokenCipher(settings.token_encryption_key)
    assert cipher.decrypt(integration.credential.encrypted_refresh_token or "") == "1//refresh_keep_me"
    assert cipher.decrypt(integration.credential.encrypted_access_token or "") == "ya29.access_two"


def test_token_refresh_revoked_handling_and_disconnect(db_session: Session) -> None:
    settings = _make_settings()
    cipher = TokenCipher(settings.token_encryption_key)
    repo = IntegrationRepository(db_session, user_id=1)

    # Seed expired access token with valid encrypted refresh token.
    repo.upsert_connection(
        provider="calendar",
        account_email="alice@gmail.com",
        status="connected",
        granted_scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        encrypted_access_token=cipher.encrypt("ya29.expired"),
        encrypted_refresh_token=cipher.encrypt("1//valid_refresh"),
        token_expiry=utc_now() - timedelta(minutes=5),
        encryption_version=TokenCipher.VERSION,
    )

    def refresh_ok(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "ya29.fresh_token", "expires_in": 3600})

    svc_ok = GoogleOAuthService(settings, http_client=_mock_http_transport(refresh_ok))
    token = svc_ok.get_valid_access_token(db_session, user_id=1, provider="calendar")
    assert token == "ya29.fresh_token"

    # Now simulate expired access token + revoked refresh token (invalid_grant).
    integ = repo.get_by_provider("calendar")
    assert integ is not None
    repo.update_access_token(
        integ,
        encrypted_access_token=cipher.encrypt("ya29.expired_again"),
        token_expiry=utc_now() - timedelta(minutes=5),
        encryption_version=TokenCipher.VERSION,
    )

    def refresh_revoked(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token revoked"})

    svc_revoked = GoogleOAuthService(settings, http_client=_mock_http_transport(refresh_revoked))
    with pytest.raises(IntegrationAuthError):
        svc_revoked.get_valid_access_token(db_session, user_id=1, provider="calendar")

    assert repo.get_by_provider("calendar").status == "needs_reconnect"  # type: ignore[union-attr]

    # Disconnect deletes credential completely.
    disconnected = svc_revoked.disconnect(db_session, user_id=1, provider="calendar")
    assert disconnected == ["calendar"]
    after = repo.get_by_provider("calendar")
    assert after is not None
    assert after.status == "disconnected"
    assert after.credential is None
