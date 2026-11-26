"""Official MCP Server (mcp 2.x MCPServer) exposing Google Calendar tools over STDIO."""

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.mcp_servers.calendar_service import (
    CalendarService,
    CalendarServiceError,
    build_calendar_client,
)

mcp = MCPServer("lifedesk-calendar")


def _get_service() -> CalendarService:
    token = os.environ.get("LIFEDESK_GOOGLE_ACCESS_TOKEN", "").strip()
    tz = os.environ.get("LIFEDESK_USER_TIMEZONE", "UTC").strip() or "UTC"
    if not token:
        raise CalendarServiceError(
            "Missing per-user Google access token in isolated MCP environment.",
            status_code=401,
        )
    return CalendarService(build_calendar_client(token), user_timezone=tz)


@mcp.tool()
def calendar_list_calendars() -> dict[str, Any]:
    """List the user's Google Calendars."""
    try:
        return _get_service().list_calendars()
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_list_events(start_datetime: str, end_datetime: str) -> dict[str, Any]:
    """List Google Calendar events between start_datetime and end_datetime (ISO-8601)."""
    try:
        return _get_service().list_events(start_datetime=start_datetime, end_datetime=end_datetime)
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_get_event(event_id: str) -> dict[str, Any]:
    """Retrieve full details for a single Google Calendar event by event_id."""
    try:
        return _get_service().get_event(event_id=event_id)
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_check_availability(start_datetime: str, end_datetime: str) -> dict[str, Any]:
    """Check free and busy slots across a time window (ISO-8601)."""
    try:
        return _get_service().check_availability(
            start_datetime=start_datetime, end_datetime=end_datetime
        )
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_find_conflicts(start_datetime: str, end_datetime: str) -> dict[str, Any]:
    """Find any overlapping events in the given time window (ISO-8601)."""
    try:
        return _get_service().find_conflicts(
            start_datetime=start_datetime, end_datetime=end_datetime
        )
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_create_event(
    title: str,
    start_datetime: str,
    end_datetime: str,
    description: str | None = None,
    attendees: list[str] | None = None,
) -> dict[str, Any]:
    """Create a Google Calendar event (must only be invoked after explicit user approval)."""
    try:
        return _get_service().create_event(
            title=title,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=description,
            attendees=attendees,
        )
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_update_event(
    event_id: str,
    title: str | None = None,
    description: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    attendees: list[str] | None = None,
) -> dict[str, Any]:
    """Update an existing Google Calendar event (must only be invoked after explicit user approval)."""
    try:
        return _get_service().update_event(
            event_id=event_id,
            title=title,
            description=description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            attendees=attendees,
        )
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def calendar_delete_event(event_id: str) -> dict[str, Any]:
    """Delete an existing Google Calendar event (must only be invoked after explicit user approval)."""
    try:
        return _get_service().delete_event(event_id=event_id)
    except CalendarServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


if __name__ == "__main__":
    mcp.run(transport="stdio")
