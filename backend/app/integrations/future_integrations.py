"""Documented future integration interfaces for Web Search and Browser Automation.

Neither capability is enabled as a live external tool in this milestone; they define
explicit security policies and typed contracts for future MCP adapters.
"""

from dataclasses import dataclass, field
import ipaddress
from typing import Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class WebSearchResult:
    """Cited web search result returned by a future WebSearchProvider."""

    title: str
    url: str
    snippet: str
    published_at: str | None = None


class WebSearchProvider(Protocol):
    """Contract for a future Web Search MCP adapter."""

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        """Search the web and return cited results with source URLs."""
        ...


@dataclass(frozen=True)
class BrowserSecurityPolicy:
    """Strict isolation and URL allowlist policy for future Playwright automation."""

    allowed_domains: tuple[str, ...] = ()
    block_private_networks: bool = True
    require_approval_for_mutations: bool = True
    reuse_personal_profile: bool = False  # Must always remain False.
    max_steps_per_session: int = 15
    blocked_schemes: tuple[str, ...] = ("file", "javascript", "data", "ftp")
    sensitive_actions: tuple[str, ...] = field(
        default=("submit_form", "purchase", "send_message", "upload_file", "download_file")
    )


def validate_navigation_url(url: str, policy: BrowserSecurityPolicy) -> str:
    """Validate URLs before browser navigation, blocking unsafe/internal targets."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or scheme in policy.blocked_schemes:
        raise ValueError(f"Unsupported or blocked URL scheme: '{scheme}'.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL must include a valid hostname.")

    if policy.block_private_networks:
        if hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"} or hostname.endswith(".local"):
            raise ValueError("Navigation to localhost or internal network hosts is blocked.")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("Navigation to private or reserved IP addresses is blocked.")
        except ValueError as exc:
            # Hostname is a DNS name (not a literal IP); only re-raise our block errors.
            if "blocked" in str(exc):
                raise

    if policy.allowed_domains:
        if not any(
            hostname == allowed.lower() or hostname.endswith(f".{allowed.lower()}")
            for allowed in policy.allowed_domains
        ):
            raise ValueError(f"Domain '{hostname}' is not in the approved browser allowlist.")

    return url.strip()


class BrowserAutomationService(Protocol):
    """Contract for a future isolated Playwright MCP server."""

    async def open_page(self, url: str, *, user_id: int) -> dict[str, str]:
        """Open an allowlisted URL inside a fresh ephemeral browser context."""
        ...

    async def cancel_session(self, session_id: str, *, user_id: int) -> None:
        """Kill/cancel an active browser session immediately."""
        ...
