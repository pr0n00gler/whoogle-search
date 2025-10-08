"""MCP server exposing a single web search tool."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import Any, Dict

import httpx
from mcp.server.fastmcp import FastMCP


DEFAULT_BASE_URL = "http://whoogle-search:5000"
SEARCH_PATH = "/search"

mcp = FastMCP("whoogle-web-search")


async def _perform_search(query: str, *, timeout: float = 10.0) -> Dict[str, Any]:
    """Perform the HTTP request to the Whoogle search endpoint."""
    base_url = os.getenv("WHOOGLE_BASE_URL", DEFAULT_BASE_URL)

    params = {
        "q": query,
        "format": "json",
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.get(SEARCH_PATH, params=params)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def web_search(query: str) -> str:
    """Run a web search against the Whoogle instance."""
    if not query or not query.strip():
        raise ValueError("The search query must not be empty.")

    payload = await _perform_search(query.strip())
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> None:
    """Run the MCP server entry point."""
    maybe_coro = mcp.run()
    if inspect.iscoroutine(maybe_coro):
        asyncio.run(maybe_coro)


if __name__ == "__main__":
    main()
