"""Official MCP ClientSession + STDIO transport manager for isolated per-user tools."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

BACKEND_ROOT = str(Path(__file__).resolve().parents[2])

MCP_SERVER_MODULES: dict[str, str] = {
    "gmail": "app.mcp_servers.gmail_server",
    "calendar": "app.mcp_servers.calendar_server",
}


class MCPClientError(Exception):
    """Raised when an MCP server cannot be reached or returns an invalid result."""


def _run_coro_sync(coro: Any) -> Any:
    """Execute an async MCP coroutine cleanly whether or not an event loop is running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _parse_mcp_call_result(call_result: Any) -> dict[str, Any]:
    """Normalize mcp.types.CallToolResult into a plain Python dictionary."""
    structured = getattr(call_result, "structured_content", None)
    if structured is None:
        structured = getattr(call_result, "structuredContent", None)
    if isinstance(structured, dict):
        if "result" in structured and isinstance(structured["result"], dict) and len(structured) == 1:
            return structured["result"]
        return structured

    is_error = bool(getattr(call_result, "is_error", getattr(call_result, "isError", False)))
    content_blocks = getattr(call_result, "content", None) or []
    texts: list[str] = []
    for block in content_blocks:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())

    combined = "\n".join(texts).strip()
    if not combined:
        if is_error:
            return {"status": "error", "error": "MCP tool returned an unspecified error."}
        return {"status": "ok"}

    try:
        parsed = json.loads(combined)
        if isinstance(parsed, dict):
            return parsed
        return {"status": "ok", "data": parsed}
    except json.JSONDecodeError:
        if is_error:
            return {"status": "error", "error": combined}
        return {"status": "ok", "text": combined}


class MCPClientManager:
    """Discovers and invokes external tools via isolated per-user MCP STDIO sessions."""

    def __init__(self, server_modules: dict[str, str] | None = None) -> None:
        self._server_modules = server_modules or dict(MCP_SERVER_MODULES)

    def _build_server_params(
        self,
        provider: str,
        *,
        access_token: str | None = None,
        user_timezone: str = "UTC",
    ) -> StdioServerParameters:
        module = self._server_modules.get(provider)
        if not module:
            raise MCPClientError(f"No MCP server adapter is registered for provider '{provider}'.")

        # Pass only minimal environment needed by Python + isolated user access token.
        # Never forward unrelated server secrets to external MCP child processes.
        isolated_env: dict[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": BACKEND_ROOT,
            "PYTHONUNBUFFERED": "1",
            "LIFEDESK_USER_TIMEZONE": user_timezone,
        }
        if access_token:
            isolated_env["LIFEDESK_GOOGLE_ACCESS_TOKEN"] = access_token

        return StdioServerParameters(
            command=sys.executable,
            args=["-m", module],
            env=isolated_env,
            cwd=BACKEND_ROOT,
        )

    async def _discover_tools_async(self, provider: str) -> list[dict[str, Any]]:
        params = self._build_server_params(provider)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": getattr(t, "input_schema", None)
                        or getattr(t, "inputSchema", None)
                        or {"type": "object", "properties": {}},
                    }
                    for t in result.tools
                ]

    def discover_tools(self, provider: str) -> list[dict[str, Any]]:
        """Discover tool schemas exposed by an MCP server via official list_tools()."""
        try:
            return _run_coro_sync(self._discover_tools_async(provider))
        except Exception as exc:
            logger.warning("mcp_discover_failed provider=%s error=%s", provider, exc)
            raise MCPClientError(f"Failed to discover MCP tools for '{provider}': {exc}") from exc

    async def _call_tool_async(
        self,
        provider: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        access_token: str,
        user_timezone: str,
    ) -> dict[str, Any]:
        params = self._build_server_params(
            provider,
            access_token=access_token,
            user_timezone=user_timezone,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return _parse_mcp_call_result(result)

    def call_tool(
        self,
        *,
        provider: str,
        tool_name: str,
        arguments: dict[str, Any],
        access_token: str,
        user_timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Invoke an MCP tool inside an isolated per-user STDIO session."""
        try:
            return _run_coro_sync(
                self._call_tool_async(
                    provider,
                    tool_name,
                    arguments,
                    access_token=access_token,
                    user_timezone=user_timezone,
                )
            )
        except MCPClientError:
            raise
        except Exception as exc:
            logger.warning("mcp_call_failed provider=%s tool=%s", provider, tool_name)
            raise MCPClientError(f"MCP tool '{tool_name}' failed: {exc}") from exc
