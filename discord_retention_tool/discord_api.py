"""Discord API client for compliant bot-token retention operations.

This module intentionally supports bot tokens only. Discord forbids automating
normal user accounts outside the OAuth2/bot API, so user-token/self-bot flows
are rejected before any request is made.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Iterable

API_BASE = "https://discord.com/api/v10"
USER_TOKEN_HINTS = ("mfa.",)


class DiscordAPIError(RuntimeError):
    """Raised when a Discord API request cannot be completed safely."""


@dataclass(slots=True)
class RetryItem:
    method: str
    path: str
    body: dict[str, Any] | None
    reason: str
    attempts: int = 0


@dataclass(slots=True)
class RateLimitConfig:
    max_retries: int = 8
    base_delay: float = 1.0
    max_delay: float = 120.0
    jitter: float = 0.25


@dataclass(slots=True)
class DiscordClient:
    token: str
    config: RateLimitConfig = field(default_factory=RateLimitConfig)
    user_agent: str = "discord-retention-tool/0.1 (+compliant-bot-token-retention)"
    second_pass: Deque[RetryItem] = field(default_factory=deque)

    def __post_init__(self) -> None:
        token = self.token.strip()
        if token.lower().startswith("bot "):
            token = token[4:].strip()
        if not token or any(token.startswith(prefix) for prefix in USER_TOKEN_HINTS):
            raise ValueError("Only Discord bot tokens are supported; user tokens/self-bots are refused.")
        self.token = token

    @property
    def authorization(self) -> str:
        return f"Bot {self.token}"

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Perform a request, respecting 429 retry hints and queuing other failures."""

        for attempt in range(self.config.max_retries + 1):
            try:
                return self._request_once(method, path, body)
            except urllib.error.HTTPError as exc:
                payload = self._read_error_payload(exc)
                if exc.code == 429:
                    delay = self._rate_limit_delay(exc, payload, attempt)
                    time.sleep(delay)
                    continue
                self.second_pass.append(RetryItem(method, path, body, f"HTTP {exc.code}: {payload}", attempt))
                return None
            except urllib.error.URLError as exc:
                self.second_pass.append(RetryItem(method, path, body, f"Network error: {exc.reason}", attempt))
                return None
        self.second_pass.append(RetryItem(method, path, body, "rate-limit retries exhausted", self.config.max_retries))
        return None

    def _request_once(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        url = f"{API_BASE}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, method=method.upper())
        request.add_header("Authorization", self.authorization)
        request.add_header("User-Agent", self.user_agent)
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS API endpoint
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))

    def _read_error_payload(self, exc: urllib.error.HTTPError) -> dict[str, Any] | str:
        raw = exc.read()
        if not raw:
            return ""
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw.decode("utf-8", errors="replace")

    def _rate_limit_delay(self, exc: urllib.error.HTTPError, payload: dict[str, Any] | str, attempt: int) -> float:
        retry_after = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
        if retry_after is None and isinstance(payload, dict):
            retry_after = payload.get("retry_after")
        try:
            server_delay = float(retry_after) if retry_after is not None else 0.0
        except (TypeError, ValueError):
            server_delay = 0.0
        exponential = min(self.config.base_delay * (2**attempt), self.config.max_delay)
        jitter = random.uniform(0, self.config.jitter) if self.config.jitter else 0.0
        return min(max(server_delay, exponential) + jitter, self.config.max_delay)

    def second_pass_retry(self) -> list[RetryItem]:
        """Retry non-rate-limit failures once; return items still failing."""

        original = list(self.second_pass)
        self.second_pass.clear()
        unresolved: list[RetryItem] = []
        for item in original:
            item.attempts += 1
            result = self.request(item.method, item.path, item.body)
            if result is None and self.second_pass:
                unresolved.extend(self.second_pass)
                self.second_pass.clear()
        return unresolved

    def get_current_bot_user(self) -> dict[str, Any]:
        result = self.request("GET", "/users/@me")
        if not isinstance(result, dict) or "id" not in result:
            raise DiscordAPIError("Unable to authenticate bot token with /users/@me.")
        return result

    def iter_channel_messages(self, channel_id: str, *, limit: int = 100) -> Iterable[dict[str, Any]]:
        """Yield all visible channel messages by walking backward with `before`."""

        before: str | None = None
        while True:
            query = {"limit": str(min(max(limit, 1), 100))}
            if before:
                query["before"] = before
            path = f"/channels/{channel_id}/messages?{urllib.parse.urlencode(query)}"
            batch = self.request("GET", path)
            if not batch:
                break
            if not isinstance(batch, list):
                raise DiscordAPIError(f"Unexpected messages response for channel {channel_id}: {batch!r}")
            for message in batch:
                yield message
            before = str(batch[-1]["id"])

    def delete_message(self, channel_id: str, message_id: str) -> bool:
        queued_before = len(self.second_pass)
        self.request("DELETE", f"/channels/{channel_id}/messages/{message_id}")
        return len(self.second_pass) == queued_before

    def get_guild_channels(self, guild_id: str) -> list[dict[str, Any]]:
        channels = self.request("GET", f"/guilds/{guild_id}/channels")
        if not isinstance(channels, list):
            return []
        return channels

    def text_channel_ids_for_guild(self, guild_id: str) -> list[str]:
        # Discord channel types: 0 guild text, 5 announcement, 10-12 threads, 15 forum.
        supported = {0, 5, 10, 11, 12, 15}
        return [str(channel["id"]) for channel in self.get_guild_channels(guild_id) if channel.get("type") in supported]
