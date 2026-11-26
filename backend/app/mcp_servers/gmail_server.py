"""Official MCP Server (mcp 2.x MCPServer) exposing Gmail tools over STDIO."""

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.mcp_servers.gmail_service import GmailService, GmailServiceError, build_gmail_client

mcp = MCPServer("lifedesk-gmail")


def _get_service() -> GmailService:
    token = os.environ.get("LIFEDESK_GOOGLE_ACCESS_TOKEN", "").strip()
    if not token:
        raise GmailServiceError(
            "Missing per-user Google access token in isolated MCP environment.",
            status_code=401,
        )
    return GmailService(build_gmail_client(token))


@mcp.tool()
def gmail_search_emails(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the user's Gmail messages using Gmail search syntax (e.g., 'from:rahul', 'is:unread')."""
    try:
        return _get_service().search_emails(query=query, max_results=max_results)
    except GmailServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def gmail_get_email(message_id: str) -> dict[str, Any]:
    """Retrieve the full details and body of a specific Gmail message by message_id."""
    try:
        return _get_service().get_email(message_id=message_id)
    except GmailServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def gmail_list_recent_emails(max_results: int = 5) -> dict[str, Any]:
    """List the most recent emails in the user's Gmail inbox."""
    try:
        return _get_service().list_recent_emails(max_results=max_results)
    except GmailServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def gmail_get_thread(thread_id: str) -> dict[str, Any]:
    """Retrieve all messages in a Gmail conversation thread by thread_id."""
    try:
        return _get_service().get_thread(thread_id=thread_id)
    except GmailServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def gmail_create_draft(
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
) -> dict[str, Any]:
    """Create a Gmail draft without sending it. Pass thread_id when drafting a reply."""
    try:
        return _get_service().create_draft(
            to=to,
            subject=subject,
            body=body,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
        )
    except GmailServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


@mcp.tool()
def gmail_send_email(
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
) -> dict[str, Any]:
    """Send an email via Gmail (must only be invoked after explicit user approval)."""
    try:
        return _get_service().send_email(
            to=to,
            subject=subject,
            body=body,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
        )
    except GmailServiceError as exc:
        return {"status": "error", "error": str(exc), "code": exc.status_code}


if __name__ == "__main__":
    mcp.run(transport="stdio")
