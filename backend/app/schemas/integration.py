"""Pydantic schemas for external integrations (never exposing tokens)."""

from datetime import datetime

from pydantic import BaseModel, Field


class IntegrationCardOut(BaseModel):
    """Safe integration status card returned to the frontend."""

    provider: str
    display_name: str
    description: str
    category: str  # active | coming_soon
    status: str  # connected | disconnected | needs_reconnect | coming_soon
    account_email: str | None = None
    granted_scopes: list[str] = Field(default_factory=list)
    available_permissions: list[str] = Field(default_factory=list)
    last_connected_at: datetime | None = None
    oauth_configured: bool = False
    demo_mode_active: bool = False


class IntegrationListResponse(BaseModel):
    """Response for GET /api/integrations."""

    integrations: list[IntegrationCardOut]
    oauth_configured: bool
    encryption_configured: bool


class GoogleConnectResponse(BaseModel):
    """Response for GET /api/integrations/google/connect and POST /reconnect."""

    authorization_url: str
    state: str
    service: str
    requested_scopes: list[str]


class GoogleStatusResponse(BaseModel):
    """Response for GET /api/integrations/google/status."""

    oauth_configured: bool
    encryption_configured: bool
    gmail: IntegrationCardOut
    calendar: IntegrationCardOut


class GoogleDisconnectResponse(BaseModel):
    """Response for POST /api/integrations/google/disconnect."""

    disconnected: list[str]
    message: str
