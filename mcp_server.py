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


DEFAULT_BASE_URL = "http://whoogle-search:5000"
SEARCH_PATH = "/search"
PAGE_CONTENT_WORDS_LIMIT = 1000
MAX_LINKS_IN_RESPONSE = 3

HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.100 Safari/537.36"
        }

class HelpFunctions:
    def __init__(self):
        pass

    def get_base_url(self, url):
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return base_url

    def generate_excerpt(self, content, max_length=200):
        return content[:max_length] + "..." if len(content) > max_length else content

    def format_text(self, original_text):
        soup = BeautifulSoup(original_text, "html.parser")
        formatted_text = soup.get_text(separator=" ", strip=True)
        formatted_text = unicodedata.normalize("NFKC", formatted_text)
        formatted_text = re.sub(r"\s+", " ", formatted_text)
        formatted_text = formatted_text.strip()
        formatted_text = self.remove_emojis(formatted_text)
        return formatted_text

    def remove_emojis(self, text):
        return "".join(c for c in text if not unicodedata.category(c).startswith("So"))

    def process_search_result(self, result):
        title_site = self.remove_emojis(result["title"])
        url_site = result["url"]
        snippet = result.get("content", "")

        try:
            response_site = requests.get(url_site, timeout=20)
            response_site.raise_for_status()
            html_content = response_site.text

            soup = BeautifulSoup(html_content, "html.parser")
            content_site = self.format_text(soup.get_text(separator=" ", strip=True))

            truncated_content = self.truncate_to_n_words(
                content_site, PAGE_CONTENT_WORDS_LIMIT
            )

            return {
                "title": title_site,
                "url": url_site,
                "content": truncated_content,
                "snippet": self.remove_emojis(snippet),
            }

        except requests.exceptions.RequestException as e:
            return None

    def truncate_to_n_words(self, text, token_limit):
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
        :return: The content of the website in json format.
        """
        functions = HelpFunctions()

        results_json = []

        try:
            response_site = requests.get(url, headers=HEADERS, timeout=120)
            response_site.raise_for_status()
            html_content = response_site.text

            soup = BeautifulSoup(html_content, "html.parser")

            page_title = soup.title.string if soup.title else "No title found"
            page_title = unicodedata.normalize("NFKC", page_title.strip())
            page_title = functions.remove_emojis(page_title)
            title_site = page_title
            url_site = url
            content_site = functions.format_text(
                soup.get_text(separator=" ", strip=True)
            )

            truncated_content = functions.truncate_to_n_words(
                content_site, PAGE_CONTENT_WORDS_LIMIT
            )

            result_site = {
                "title": title_site,
                "url": url_site,
                "content": truncated_content,
                "excerpt": functions.generate_excerpt(content_site),
            }

            results_json.append(result_site)

        except requests.exceptions.RequestException as e:
            results_json.append(
                {
                    "url": url,
                    "content": f"Failed to retrieve the page. Error: {str(e)}",
                }
            )

        return json.dumps(results_json, ensure_ascii=False)


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
    n = min(len(payload["results"]), MAX_LINKS_IN_RESPONSE)
    for i in range(0, n):
        content = json.loads(await get_website(payload["results"][i]["href"]))[0]["content"]
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
