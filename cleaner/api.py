"""Thin Discord API client with full rate-limit handling.

Handles:
- Per-bucket rate limits via ``X-RateLimit-*`` response headers.
- Global rate limits via ``X-RateLimit-Global`` and 429 responses.
- Search indexing 202 responses (Discord asynchronously indexes guilds).
- Cloudflare / transient 5xx with exponential backoff.

The client does NOT inject any ``Bot`` / ``Bearer`` prefix into the
Authorization header — Discord user tokens are passed verbatim.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)


API_BASE = "https://discord.com/api/v9"

# Realistic browser-like headers reduce the chance Discord flags traffic
# as obviously non-client. They are NOT a guarantee.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) discord/1.0.9034 Chrome/124.0.6367.243 "
        "Electron/30.0.1 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Discord-Locale": "en-US",
    "X-Debug-Options": "bugReporterEnabled",
}


class DiscordError(Exception):
    """Generic Discord API failure."""

    def __init__(self, status: int, body: Any):
        super().__init__(f"discord api {status}: {body}")
        self.status = status
        self.body = body


class Unauthorized(DiscordError):
    """Raised when the token is rejected (401)."""


class Forbidden(DiscordError):
    """Raised on 403 (missing access, locked channel, etc.)."""


class NotFound(DiscordError):
    """Raised on 404."""


@dataclass
class _Bucket:
    remaining: int = 1
    reset_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


class DiscordClient:
    """Synchronous Discord HTTP client with rate-limit awareness."""

    def __init__(
        self,
        token: str,
        *,
        min_delay: float = 0.35,
        jitter: float = 0.25,
        max_retries: int = 8,
    ):
        if not token or not isinstance(token, str):
            raise ValueError("token must be a non-empty string")
        self.token = token.strip()
        self.min_delay = min_delay
        self.jitter = jitter
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.headers["Authorization"] = self.token

        self._buckets: dict[str, _Bucket] = {}
        self._route_to_bucket: dict[str, str] = {}
        self._global_lock = threading.Lock()
        self._global_reset_at = 0.0
        self._last_request_at = 0.0

    # ------------------------------------------------------------------
    # Low-level request loop

    def _route_key(self, method: str, path: str) -> str:
        # Replace major params with placeholders so similar routes share a bucket.
        # Major params per Discord docs: channel_id, guild_id, webhook_id.
        parts = path.strip("/").split("/")
        norm: list[str] = []
        keep_next = False
        for p in parts:
            if keep_next:
                norm.append(p)
                keep_next = False
                continue
            if p in {"channels", "guilds", "webhooks"}:
                norm.append(p)
                keep_next = True
                continue
            # Snowflake-like (purely digits, >=15 chars): mask.
            if p.isdigit() and len(p) >= 15:
                norm.append(":id")
            else:
                norm.append(p)
        return f"{method.upper()} /{'/'.join(norm)}"

    def _wait_for_slot(self, route: str) -> None:
        # Global rate limit
        now = time.monotonic()
        if self._global_reset_at > now:
            sleep_for = self._global_reset_at - now
            log.info("global rate limit: sleeping %.2fs", sleep_for)
            time.sleep(sleep_for)

        # Per-bucket
        bucket_id = self._route_to_bucket.get(route)
        if bucket_id:
            bucket = self._buckets.get(bucket_id)
            if bucket:
                with bucket.lock:
                    now = time.monotonic()
                    if bucket.remaining <= 0 and bucket.reset_at > now:
                        sleep_for = bucket.reset_at - now
                        log.debug(
                            "bucket %s exhausted, sleeping %.2fs",
                            bucket_id,
                            sleep_for,
                        )
                        time.sleep(sleep_for)

        # Polite floor between requests.
        elapsed = time.monotonic() - self._last_request_at
        floor = self.min_delay + random.uniform(0.0, self.jitter)
        if elapsed < floor:
            time.sleep(floor - elapsed)

    def _update_buckets(self, route: str, resp: requests.Response) -> None:
        bucket_id = resp.headers.get("X-RateLimit-Bucket")
        if not bucket_id:
            return
        self._route_to_bucket[route] = bucket_id
        bucket = self._buckets.setdefault(bucket_id, _Bucket())
        try:
            remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
        except ValueError:
            remaining = 1
        try:
            reset_after = float(resp.headers.get("X-RateLimit-Reset-After", "0"))
        except ValueError:
            reset_after = 0.0
        with bucket.lock:
            bucket.remaining = remaining
            bucket.reset_at = time.monotonic() + reset_after

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
    ) -> Any:
        route = self._route_key(method, path)
        url = f"{API_BASE}{path}"

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._wait_for_slot(route)
            try:
                resp = self.session.request(
                    method, url, params=params, json=json, timeout=30
                )
            except requests.RequestException as e:
                last_exc = e
                wait = min(2 ** attempt, 30) + random.uniform(0, 1)
                log.warning("network error: %s — retrying in %.1fs", e, wait)
                time.sleep(wait)
                continue
            finally:
                self._last_request_at = time.monotonic()

            self._update_buckets(route, resp)

            # 429 — rate limited
            if resp.status_code == 429:
                payload = _safe_json(resp)
                retry_after = float(payload.get("retry_after", 1.0)) if isinstance(payload, dict) else 1.0
                is_global = bool(payload.get("global")) if isinstance(payload, dict) else False
                scope = resp.headers.get("X-RateLimit-Scope", "user")
                log.warning(
                    "429 rate limit (scope=%s global=%s) — sleeping %.2fs",
                    scope,
                    is_global,
                    retry_after,
                )
                if is_global:
                    self._global_reset_at = time.monotonic() + retry_after
                time.sleep(retry_after + 0.25)
                continue

            # 202 — guild search indexing in progress
            if resp.status_code == 202:
                payload = _safe_json(resp)
                retry_after = (
                    float(payload.get("retry_after", 5)) / 1000.0
                    if isinstance(payload, dict) and "retry_after" in payload
                    else 5.0
                )
                # retry_after on 202 is sometimes in ms, sometimes seconds.
                # Discord historically returned ms — clamp into [1, 60].
                retry_after = max(1.0, min(retry_after, 60.0))
                log.info("guild indexing — sleeping %.1fs", retry_after)
                time.sleep(retry_after)
                continue

            # 5xx — transient
            if 500 <= resp.status_code < 600:
                wait = min(2 ** attempt, 30) + random.uniform(0, 1)
                log.warning(
                    "server %s — retrying in %.1fs", resp.status_code, wait
                )
                time.sleep(wait)
                continue

            # Final status handling
            if resp.status_code == 401:
                raise Unauthorized(401, _safe_json(resp))
            if resp.status_code == 403:
                raise Forbidden(403, _safe_json(resp))
            if resp.status_code == 404:
                raise NotFound(404, _safe_json(resp))
            if 400 <= resp.status_code < 500:
                raise DiscordError(resp.status_code, _safe_json(resp))

            if resp.status_code == 204:
                return None
            return _safe_json(resp)

        if last_exc is not None:
            raise last_exc
        raise DiscordError(0, "exceeded max retries")

    # ------------------------------------------------------------------
    # High-level helpers

    def me(self) -> dict:
        return self.request("GET", "/users/@me")

    def my_guilds(self) -> list[dict]:
        return self.request("GET", "/users/@me/guilds")

    def my_private_channels(self) -> list[dict]:
        return self.request("GET", "/users/@me/channels")

    def guild_channels(self, guild_id: str) -> list[dict]:
        return self.request("GET", f"/guilds/{guild_id}/channels")

    def search_guild(
        self, guild_id: str, author_id: str, *, offset: int = 0
    ) -> dict:
        params = {"author_id": author_id, "offset": offset, "include_nsfw": "true"}
        return self.request(
            "GET", f"/guilds/{guild_id}/messages/search", params=params
        )

    def search_channel(
        self, channel_id: str, author_id: str, *, offset: int = 0
    ) -> dict:
        params = {"author_id": author_id, "offset": offset, "include_nsfw": "true"}
        return self.request(
            "GET", f"/channels/{channel_id}/messages/search", params=params
        )

    def channel_messages(
        self,
        channel_id: str,
        *,
        before: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before
        return self.request(
            "GET", f"/channels/{channel_id}/messages", params=params
        )

    def delete_message(self, channel_id: str, message_id: str) -> None:
        self.request(
            "DELETE", f"/channels/{channel_id}/messages/{message_id}"
        )

    def edit_channel(self, channel_id: str, **fields: Any) -> dict:
        """PATCH /channels/{id} — used to unarchive threads."""
        return self.request(
            "PATCH", f"/channels/{channel_id}", json=fields
        )

    def get_channel(self, channel_id: str) -> dict:
        return self.request("GET", f"/channels/{channel_id}")

    def guild_members(
        self,
        guild_id: str,
        *,
        after: str = "0",
        limit: int = 1000,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": min(limit, 1000), "after": after}
        return self.request(
            "GET", f"/guilds/{guild_id}/members", params=params
        )

    def role_member_ids(self, guild_id: str, role_id: str) -> list[str]:
        return self.request(
            "GET", f"/guilds/{guild_id}/roles/{role_id}/member-ids"
        )


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text
