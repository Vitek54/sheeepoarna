"""HTTP client utilities for Cat Tool."""

import asyncio
from typing import Optional

import aiohttp
import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TIMEOUT = 15


def get(url: str, headers: Optional[dict] = None, timeout: int = TIMEOUT, allow_redirects: bool = True) -> Optional[requests.Response]:
    """Make a GET request with default headers."""
    merged = {**DEFAULT_HEADERS}
    if headers:
        merged.update(headers)
    try:
        resp = requests.get(url, headers=merged, timeout=timeout, allow_redirects=allow_redirects)
        return resp
    except (requests.RequestException, Exception):
        return None


def head(url: str, headers: Optional[dict] = None, timeout: int = TIMEOUT) -> Optional[requests.Response]:
    """Make a HEAD request."""
    merged = {**DEFAULT_HEADERS}
    if headers:
        merged.update(headers)
    try:
        resp = requests.head(url, headers=merged, timeout=timeout, allow_redirects=True)
        return resp
    except (requests.RequestException, Exception):
        return None


async def async_get(session: aiohttp.ClientSession, url: str, timeout: int = TIMEOUT) -> Optional[dict]:
    """Make an async GET request returning status and text."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True, ssl=False) as resp:
            text = await resp.text()
            return {"status": resp.status, "text": text, "url": str(resp.url), "headers": dict(resp.headers)}
    except Exception:
        return None


async def async_check_url(session: aiohttp.ClientSession, url: str, name: str, timeout: int = TIMEOUT) -> dict:
    """Check if a URL exists (returns 200) asynchronously."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True, ssl=False) as resp:
            return {
                "name": name,
                "url": url,
                "status": resp.status,
                "exists": resp.status == 200,
            }
    except Exception:
        return {
            "name": name,
            "url": url,
            "status": 0,
            "exists": False,
        }


def create_async_session() -> aiohttp.ClientSession:
    """Create an aiohttp session with default headers."""
    return aiohttp.ClientSession(headers=DEFAULT_HEADERS)


def run_async(coro):
    """Run an async coroutine from sync code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
