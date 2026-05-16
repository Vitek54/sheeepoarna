"""Rate-limit-aware HTTP клиент для Discord API."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from discord_tool.core.config import API_BASE, console


@dataclass
class RateBucket:
    remaining: int = 5
    reset_at: float = 0.0
    limit: int = 5


@dataclass
class DiscordClient:
    token: str
    _client: httpx.AsyncClient = field(init=False)
    _buckets: dict[str, RateBucket] = field(default_factory=dict)
    _global_reset: float = field(default=0.0)
    _global_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _bucket_key(self, method: str, path: str) -> str:
        parts = path.strip("/").split("/")
        key_parts = [method]
        i = 0
        while i < len(parts):
            key_parts.append(parts[i])
            if parts[i] in ("channels", "guilds", "webhooks") and i + 1 < len(parts):
                key_parts.append(parts[i + 1])
                i += 1
            i += 1
        return ":".join(key_parts)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_data: Any = None,
        params: dict[str, Any] | None = None,
        max_retries: int = 10,
    ) -> httpx.Response | None:
        bkey = self._bucket_key(method, path)
        bucket = self._buckets.setdefault(bkey, RateBucket())

        for attempt in range(max_retries):
            async with self._global_lock:
                now = time.monotonic()
                if self._global_reset > now:
                    wait = self._global_reset - now
                    console.print(
                        f"  [dim]Глобальный rate-limit, жду {wait:.1f}с...[/]"
                    )
                    await asyncio.sleep(wait)

            now = time.monotonic()
            if bucket.remaining <= 0 and bucket.reset_at > now:
                wait = bucket.reset_at - now + 0.25
                console.print(
                    f"  [dim]Rate-limit bucket, жду {wait:.1f}с...[/]"
                )
                await asyncio.sleep(wait)

            try:
                resp = await self._client.request(
                    method, path, json=json_data, params=params
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout):
                wait = min(2**attempt, 30)
                console.print(f"  [warn]Сетевая ошибка, повтор через {wait}с[/]")
                await asyncio.sleep(wait)
                continue

            h = resp.headers
            if "X-RateLimit-Remaining" in h:
                bucket.remaining = int(h["X-RateLimit-Remaining"])
                bucket.limit = int(h.get("X-RateLimit-Limit", bucket.limit))
                reset_after = float(h.get("X-RateLimit-Reset-After", "0"))
                bucket.reset_at = time.monotonic() + reset_after

            if resp.status_code == 429:
                body = resp.json()
                retry_after = body.get("retry_after", 5.0)
                is_global = body.get("global", False)
                scope = h.get("X-RateLimit-Scope", "user")

                if is_global:
                    async with self._global_lock:
                        self._global_reset = time.monotonic() + retry_after
                    console.print(
                        f"  [warn]Глобальный 429, жду {retry_after:.1f}с "
                        f"(scope={scope})[/]"
                    )
                else:
                    console.print(
                        f"  [warn]429, жду {retry_after:.1f}с "
                        f"(scope={scope})[/]"
                    )

                bucket.remaining = 0
                bucket.reset_at = time.monotonic() + retry_after
                await asyncio.sleep(retry_after + 0.5)
                continue

            if resp.status_code in (500, 502, 503, 504):
                wait = min(2**attempt, 30)
                console.print(
                    f"  [warn]Сервер {resp.status_code}, повтор через {wait}с[/]"
                )
                await asyncio.sleep(wait)
                continue

            return resp

        console.print(
            f"  [err]Не удалось выполнить {method} {path} "
            f"после {max_retries} попыток[/]"
        )
        return None

    async def get(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("GET", path, **kw)

    async def delete(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("DELETE", path, **kw)

    async def post(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("POST", path, **kw)

    async def patch(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("PATCH", path, **kw)

    async def put(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("PUT", path, **kw)
