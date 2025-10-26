"""MCP server exposing a single web search tool."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import Any, Dict
import requests
from datetime import datetime
import json
from requests import get
from bs4 import BeautifulSoup
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
import unicodedata
import re

import httpx
from mcp.server.fastmcp import FastMCP

from tavily import TavilyClient


DEFAULT_BASE_URL = "http://whoogle-search:5000"
SEARCH_PATH = "/search"
PAGE_CONTENT_WORDS_LIMIT = 5000
MAX_LINKS_IN_RESPONSE = 5

HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.100 Safari/537.36"
        }

def truncate_to_n_words(text, token_limit):
    tokens = text.split()
    truncated_tokens = tokens[:token_limit]
    return " ".join(truncated_tokens)

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
async def get_website(url: str) -> str:
        """
        Web scrape the website provided and get the content of it.
        :params url: The URL of the website.
        :return: The content of the website in markdown format.
        """
        
        tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = tavily_client.extract(url, format="markdown")

        if len(response["failed_results"]) > 0:
            return response["failed_results"][0]["error"]

        return truncate_to_n_words(response["results"][0]["raw_content"], PAGE_CONTENT_WORDS_LIMIT)


@mcp.tool()
async def web_search(query: str) -> str:
    """
        Search the web and get the content of the relevant pages. Search for unknown knowledge, news, info, public contact info, weather, etc.
        :params query: Web Query used in search engine.
        :return: The content of the pages in json format.
        """
    if not query or not query.strip():
        raise ValueError("The search query must not be empty.")

    payload = await _perform_search(query.strip())
    payload["results"] = filter(lambda r: "reddit.com" not in r["href"], payload["results"])
    n = min(len(payload["results"]), MAX_LINKS_IN_RESPONSE)
    for i in range(0, n):
        content = await get_website(payload["results"][i]["href"])
        payload["results"][i]["text"] = content
        del payload["results"][i]["content"]
    payload["results"] = payload["results"][0:n]

    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> None:
    """Run the MCP server entry point."""
    maybe_coro = mcp.run()
    if inspect.iscoroutine(maybe_coro):
        asyncio.run(maybe_coro)


if __name__ == "__main__":
    main()
