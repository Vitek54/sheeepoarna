#!/usr/bin/env python3
"""
Discord Self-Tool — минималистичная чёрно-белая утилита для управления аккаунтом.

Категории:
  [А] Удаление сообщений (4 режима + реакции)
  [Б] Парсинг и поиск
  [В] Управление аккаунтом
  [Г] Серверные утилиты
  [Д] Друзья и связи
  [Е] Утилиты
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Тема ─────────────────────────────────────────────────────────────────────

THEME = Theme(
    {
        "title": "bold white",
        "accent": "bright_white",
        "dim": "dim white",
        "err": "bold red",
        "ok": "bold green",
        "warn": "yellow",
        "info": "bright_white",
    }
)

console = Console(theme=THEME)

API_BASE = "https://discord.com/api/v10"
SNOWFLAKE_EPOCH = 1420070400000

HYPESQUAD_HOUSES = {
    "1": ("Bravery", 1),
    "2": ("Brilliance", 2),
    "3": ("Balance", 3),
}

LOCALE_MAP = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "ru": "Русский",
    "uk": "Українська",
    "de": "Deutsch",
    "fr": "Français",
    "es-ES": "Español",
    "pt-BR": "Português (BR)",
    "ja": "日本語",
    "ko": "한국어",
    "zh-CN": "中文 (简体)",
    "zh-TW": "中文 (繁體)",
    "tr": "Türkçe",
    "pl": "Polski",
    "it": "Italiano",
    "nl": "Nederlands",
    "ar": "العربية",
}


# ── Утилиты ──────────────────────────────────────────────────────────────────


def snowflake_time(snowflake_id: int) -> datetime:
    ts = ((snowflake_id >> 22) + SNOWFLAKE_EPOCH) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def format_permissions(perms: int) -> list[str]:
    perm_names = {
        0: "CREATE_INSTANT_INVITE", 1: "KICK_MEMBERS", 2: "BAN_MEMBERS",
        3: "ADMINISTRATOR", 4: "MANAGE_CHANNELS", 5: "MANAGE_GUILD",
        6: "ADD_REACTIONS", 7: "VIEW_AUDIT_LOG", 8: "PRIORITY_SPEAKER",
        9: "STREAM", 10: "VIEW_CHANNEL", 11: "SEND_MESSAGES",
        13: "SEND_TTS_MESSAGES", 14: "MANAGE_MESSAGES",
        15: "EMBED_LINKS", 16: "ATTACH_FILES", 17: "READ_MESSAGE_HISTORY",
        18: "MENTION_EVERYONE", 19: "USE_EXTERNAL_EMOJIS",
        20: "VIEW_GUILD_INSIGHTS", 21: "CONNECT", 22: "SPEAK",
        23: "MUTE_MEMBERS", 24: "DEAFEN_MEMBERS", 25: "MOVE_MEMBERS",
        26: "USE_VAD", 27: "CHANGE_NICKNAME", 28: "MANAGE_NICKNAMES",
        29: "MANAGE_ROLES", 30: "MANAGE_WEBHOOKS",
        31: "MANAGE_GUILD_EXPRESSIONS", 37: "MANAGE_THREADS",
        38: "CREATE_PUBLIC_THREADS", 39: "CREATE_PRIVATE_THREADS",
        40: "USE_EXTERNAL_STICKERS", 41: "SEND_MESSAGES_IN_THREADS",
    }
    result = []
    for bit, name in perm_names.items():
        if perms & (1 << bit):
            result.append(name)
    return result


# ── Rate-Limit-Aware HTTP клиент ─────────────────────────────────────────────


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
                wait = min(2 ** attempt, 30)
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
                wait = min(2 ** attempt, 30)
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

    # ── Удобные методы ───────────────────────────────────────────────────

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


# ── Основная логика ──────────────────────────────────────────────────────────


class SelfTool:
    def __init__(self, client: DiscordClient) -> None:
        self.client = client
        self.user: dict[str, Any] = {}
        self.settings: dict[str, Any] = {}

    async def init(self) -> bool:
        resp = await self.client.get("/users/@me")
        if resp is None or resp.status_code != 200:
            console.print("[err]Невалидный токен![/]")
            return False
        self.user = resp.json()
        settings_resp = await self.client.get("/users/@me/settings")
        if settings_resp and settings_resp.status_code == 200:
            self.settings = settings_resp.json()
        return True

    @property
    def user_id(self) -> str:
        return self.user["id"]

    @property
    def username(self) -> str:
        name = self.user.get("username", "?")
        disc = self.user.get("discriminator", "0")
        if disc and disc != "0":
            return f"{name}#{disc}"
        display = self.user.get("global_name")
        return f"{display} (@{name})" if display else f"@{name}"

    # ══════════════════════════════════════════════════════════════════════
    #  ПОЛУЧЕНИЕ ДАННЫХ
    # ══════════════════════════════════════════════════════════════════════

    async def get_dm_channels(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/users/@me/channels")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    async def get_guilds(self) -> list[dict[str, Any]]:
        guilds: list[dict[str, Any]] = []
        after = "0"
        while True:
            resp = await self.client.get(
                "/users/@me/guilds", params={"limit": 200, "after": after}
            )
            if not resp or resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            guilds.extend(batch)
            after = batch[-1]["id"]
            if len(batch) < 200:
                break
        return guilds

    async def get_guild_channels(self, guild_id: str) -> list[dict[str, Any]]:
        resp = await self.client.get(f"/guilds/{guild_id}/channels")
        if resp and resp.status_code == 200:
            return [
                ch for ch in resp.json()
                if ch.get("type") in (0, 2, 5, 10, 11, 12, 15)
            ]
        return []

    async def get_guild_roles(self, guild_id: str) -> list[dict[str, Any]]:
        resp = await self.client.get(f"/guilds/{guild_id}/roles")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  ПОИСК СООБЩЕНИЙ
    # ══════════════════════════════════════════════════════════════════════

    async def search_messages(
        self,
        *,
        guild_id: str | None = None,
        channel_id: str | None = None,
        author_id: str | None = None,
        content: str | None = None,
        has: str | None = None,
        min_id: str | None = None,
        max_id: str | None = None,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        if guild_id:
            path = f"/guilds/{guild_id}/messages/search"
        elif channel_id:
            path = f"/channels/{channel_id}/messages/search"
        else:
            return 0, []

        params: dict[str, Any] = {"offset": offset}
        if author_id:
            params["author_id"] = author_id
        if content:
            params["content"] = content
        if has:
            params["has"] = has
        if min_id:
            params["min_id"] = min_id
        if max_id:
            params["max_id"] = max_id

        resp = await self.client.get(path, params=params)
        if not resp or resp.status_code != 200:
            return 0, []
        data = resp.json()
        total = data.get("total_results", 0)
        messages = [m[0] for m in data.get("messages", []) if m]
        return total, messages

    # ══════════════════════════════════════════════════════════════════════
    #  УДАЛЕНИЕ СООБЩЕНИЙ
    # ══════════════════════════════════════════════════════════════════════

    async def delete_messages_in_channel(
        self,
        channel_id: str,
        channel_name: str = "",
        progress: Progress | None = None,
        task_id: Any = None,
    ) -> int:
        deleted = 0
        last_id: str | None = None

        while True:
            params: dict[str, Any] = {"limit": 100}
            if last_id:
                params["before"] = last_id

            resp = await self.client.get(
                f"/channels/{channel_id}/messages", params=params
            )
            if not resp or resp.status_code != 200:
                break

            messages = resp.json()
            if not messages:
                break

            my_msgs = [m for m in messages if m["author"]["id"] == self.user_id]
            last_id = messages[-1]["id"]

            for msg in my_msgs:
                del_resp = await self.client.delete(
                    f"/channels/{channel_id}/messages/{msg['id']}"
                )
                if del_resp and del_resp.status_code == 204:
                    deleted += 1
                    if progress and task_id is not None:
                        progress.update(task_id, advance=1)
                elif del_resp and del_resp.status_code == 404:
                    pass
                await asyncio.sleep(0.35)

            if len(messages) < 100:
                break

        return deleted

    async def delete_messages_in_channel_via_search(
        self,
        channel_id: str,
        channel_name: str = "",
    ) -> int:
        deleted = 0
        seen: set[str] = set()
        label = channel_name or channel_id

        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[accent]{task.description}[/]"),
            BarColumn(bar_width=30, style="white", complete_style="bright_white"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"  {label}", total=None)

            while True:
                total, messages = await self.search_messages(
                    channel_id=channel_id, author_id=self.user_id
                )

                if total == 0 or not messages:
                    break

                new_msgs = [m for m in messages if m["id"] not in seen]
                if not new_msgs:
                    break

                if progress.tasks[task].total is None:
                    progress.update(task, total=total)

                for msg in new_msgs:
                    seen.add(msg["id"])
                    resp = await self.client.delete(
                        f"/channels/{channel_id}/messages/{msg['id']}"
                    )
                    if resp and resp.status_code == 204:
                        deleted += 1
                        progress.update(task, advance=1)
                    elif resp and resp.status_code == 404:
                        progress.update(task, advance=1)
                    await asyncio.sleep(0.35)

                await asyncio.sleep(0.5)

        return deleted

    async def delete_in_guild_via_search(
        self, guild_id: str, guild_name: str = ""
    ) -> int:
        deleted = 0
        seen: set[str] = set()
        label = guild_name or guild_id

        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[accent]{task.description}[/]"),
            BarColumn(bar_width=30, style="white", complete_style="bright_white"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"  {label}", total=None)

            while True:
                total, messages = await self.search_messages(
                    guild_id=guild_id, author_id=self.user_id
                )
                if total == 0 or not messages:
                    break

                new_msgs = [m for m in messages if m["id"] not in seen]
                if not new_msgs:
                    break

                if progress.tasks[task].total is None:
                    progress.update(task, total=total)

                for msg in new_msgs:
                    seen.add(msg["id"])
                    ch_id = msg.get("channel_id")
                    resp = await self.client.delete(
                        f"/channels/{ch_id}/messages/{msg['id']}"
                    )
                    if resp and resp.status_code == 204:
                        deleted += 1
                        progress.update(task, advance=1)
                    elif resp and resp.status_code == 404:
                        progress.update(task, advance=1)
                    await asyncio.sleep(0.35)

                await asyncio.sleep(0.5)

        return deleted

    async def purge_everywhere(self) -> int:
        total_deleted = 0

        console.print("\n[accent]── Удаление во всех ЛС ──[/]")
        dms = await self.get_dm_channels()
        for dm in dms:
            recipients = dm.get("recipients", [])
            name = ", ".join(r.get("username", "?") for r in recipients) or dm["id"]
            count = await self.delete_messages_in_channel_via_search(
                dm["id"], f"ЛС: {name}"
            )
            total_deleted += count

        console.print("\n[accent]── Удаление на всех серверах ──[/]")
        guilds = await self.get_guilds()
        for guild in guilds:
            count = await self.delete_in_guild_via_search(
                guild["id"], guild["name"]
            )
            total_deleted += count

        return total_deleted

    async def purge_specific_channel(self, channel_id: str) -> int:
        return await self.delete_messages_in_channel_via_search(
            channel_id, f"Канал {channel_id}"
        )

    async def purge_all_servers(self) -> int:
        total = 0
        guilds = await self.get_guilds()
        for guild in guilds:
            count = await self.delete_in_guild_via_search(
                guild["id"], guild["name"]
            )
            total += count
        return total

    async def purge_specific_server(self, guild_id: str) -> int:
        return await self.delete_in_guild_via_search(guild_id)

    # ══════════════════════════════════════════════════════════════════════
    #  ПАРСИНГ УЧАСТНИКОВ ПО РОЛИ
    # ══════════════════════════════════════════════════════════════════════

    async def parse_role_members(
        self, guild_id: str, role_id: str
    ) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []

        resp = await self.client.get(
            f"/guilds/{guild_id}/roles/{role_id}/member-ids"
        )
        if resp and resp.status_code == 200:
            member_ids = resp.json()
            console.print(
                f"  [ok]Получено {len(member_ids)} ID через role-members API[/]"
            )
            for mid in member_ids:
                members.append({"id": mid})
            return members

        console.print(
            "  [dim]role-members API недоступен, использую member-search...[/]"
        )
        after = "0"
        while True:
            resp = await self.client.get(
                f"/guilds/{guild_id}/members",
                params={"limit": 1000, "after": after},
            )
            if not resp or resp.status_code != 200:
                break

            batch = resp.json()
            if not batch:
                break

            for m in batch:
                if role_id in m.get("roles", []):
                    members.append(
                        {
                            "id": m["user"]["id"],
                            "username": m["user"].get("username", "?"),
                            "global_name": m["user"].get("global_name"),
                        }
                    )

            after = batch[-1]["user"]["id"]
            if len(batch) < 1000:
                break

        if not members:
            console.print("  [dim]Пробую members-search endpoint...[/]")
            resp = await self.client.post(
                f"/guilds/{guild_id}/members-search",
                json_data={
                    "or_query": {},
                    "and_query": {"role_ids": {"or_query": [role_id]}},
                    "limit": 1000,
                },
            )
            if resp and resp.status_code == 200:
                data = resp.json()
                for item in data.get("members", []):
                    member = item.get("member", {})
                    user = member.get("user", {})
                    members.append(
                        {
                            "id": user.get("id", "?"),
                            "username": user.get("username", "?"),
                            "global_name": user.get("global_name"),
                        }
                    )

        return members

    # ══════════════════════════════════════════════════════════════════════
    #  ПОИСК СООБЩЕНИЙ НА СЕРВЕРЕ
    # ══════════════════════════════════════════════════════════════════════

    async def search_in_guild(
        self, guild_id: str, query: str, max_results: int = 50
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        offset = 0
        while len(results) < max_results:
            _, messages = await self.search_messages(
                guild_id=guild_id, content=query, offset=offset
            )
            if not messages:
                break
            results.extend(messages)
            offset += 25
            await asyncio.sleep(0.5)
        return results[:max_results]

    # ══════════════════════════════════════════════════════════════════════
    #  ЭКСПОРТ КАНАЛА
    # ══════════════════════════════════════════════════════════════════════

    async def export_channel(self, channel_id: str, output_path: str) -> int:
        all_messages: list[dict[str, Any]] = []
        last_id: str | None = None

        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[accent]{task.description}[/]"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Экспорт", total=None)

            while True:
                params: dict[str, Any] = {"limit": 100}
                if last_id:
                    params["before"] = last_id

                resp = await self.client.get(
                    f"/channels/{channel_id}/messages", params=params
                )
                if not resp or resp.status_code != 200:
                    break

                messages = resp.json()
                if not messages:
                    break

                for m in messages:
                    all_messages.append(
                        {
                            "id": m["id"],
                            "author": m["author"].get("username", "?"),
                            "author_id": m["author"]["id"],
                            "content": m.get("content", ""),
                            "timestamp": m.get("timestamp", ""),
                            "attachments": [
                                a.get("url", "") for a in m.get("attachments", [])
                            ],
                            "embeds": len(m.get("embeds", [])),
                            "reactions": [
                                {
                                    "emoji": r.get("emoji", {}).get("name", "?"),
                                    "count": r.get("count", 0),
                                }
                                for r in m.get("reactions", [])
                            ],
                        }
                    )
                    progress.update(task, advance=1)

                last_id = messages[-1]["id"]
                if len(messages) < 100:
                    break

        all_messages.reverse()
        Path(output_path).write_text(
            json.dumps(all_messages, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return len(all_messages)

    # ══════════════════════════════════════════════════════════════════════
    #  ИНФОРМАЦИЯ О СЕРВЕРЕ
    # ══════════════════════════════════════════════════════════════════════

    async def guild_info(self, guild_id: str) -> dict[str, Any] | None:
        resp = await self.client.get(f"/guilds/{guild_id}?with_counts=true")
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    # ══════════════════════════════════════════════════════════════════════
    #  КАСТОМНЫЙ СТАТУС
    # ══════════════════════════════════════════════════════════════════════

    async def set_custom_status(
        self, text: str, emoji_name: str = ""
    ) -> bool:
        payload: dict[str, Any] = {"custom_status": {"text": text}}
        if emoji_name:
            payload["custom_status"]["emoji_name"] = emoji_name
        resp = await self.client.patch(
            "/users/@me/settings", json_data=payload
        )
        return resp is not None and resp.status_code == 200

    # ══════════════════════════════════════════════════════════════════════
    #  ПОЛНАЯ ИНФОРМАЦИЯ ОБ АККАУНТЕ
    # ══════════════════════════════════════════════════════════════════════

    async def full_account_info(self) -> dict[str, Any]:
        resp = await self.client.get("/users/@me")
        user = resp.json() if resp and resp.status_code == 200 else {}
        prof_resp = await self.client.get(f"/users/{self.user_id}/profile")
        profile = prof_resp.json() if prof_resp and prof_resp.status_code == 200 else {}
        settings_resp = await self.client.get("/users/@me/settings")
        settings = (
            settings_resp.json()
            if settings_resp and settings_resp.status_code == 200
            else {}
        )
        billing_resp = await self.client.get(
            "/users/@me/billing/payment-sources"
        )
        has_billing = (
            bool(billing_resp.json())
            if billing_resp and billing_resp.status_code == 200
            else False
        )
        return {
            "user": user,
            "profile": profile,
            "settings": settings,
            "has_billing": has_billing,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  RELATIONSHIPS (ДРУЗЬЯ, БЛОК, ЗАПРОСЫ)
    # ══════════════════════════════════════════════════════════════════════

    async def get_relationships(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/users/@me/relationships")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  USER LOOKUP
    # ══════════════════════════════════════════════════════════════════════

    async def user_lookup(self, user_id: str) -> dict[str, Any] | None:
        resp = await self.client.get(f"/users/{user_id}/profile")
        if resp and resp.status_code == 200:
            return resp.json()
        resp2 = await self.client.get(f"/users/{user_id}")
        if resp2 and resp2.status_code == 200:
            return {"user": resp2.json()}
        return None

    # ══════════════════════════════════════════════════════════════════════
    #  ОБЩИЕ СЕРВЕРЫ / ДРУЗЬЯ
    # ══════════════════════════════════════════════════════════════════════

    async def mutual_guilds(self, user_id: str) -> list[dict[str, Any]]:
        resp = await self.client.get(
            f"/users/{user_id}/profile",
            params={"with_mutual_guilds": "true"},
        )
        if resp and resp.status_code == 200:
            return resp.json().get("mutual_guilds", [])
        return []

    async def mutual_friends(self, user_id: str) -> list[dict[str, Any]]:
        resp = await self.client.get(
            f"/users/{user_id}/profile",
            params={"with_mutual_friends": "true"},
        )
        if resp and resp.status_code == 200:
            return resp.json().get("mutual_friends", [])
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  INVITE INFO
    # ══════════════════════════════════════════════════════════════════════

    async def invite_info(self, code: str) -> dict[str, Any] | None:
        code = code.replace("https://discord.gg/", "").replace(
            "https://discord.com/invite/", ""
        )
        resp = await self.client.get(
            f"/invites/{code}",
            params={"with_counts": "true", "with_expiration": "true"},
        )
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    # ══════════════════════════════════════════════════════════════════════
    #  HYPESQUAD
    # ══════════════════════════════════════════════════════════════════════

    async def change_hypesquad(self, house_id: int) -> bool:
        resp = await self.client.post(
            "/hypesquad/online", json_data={"house_id": house_id}
        )
        return resp is not None and resp.status_code == 204

    async def leave_hypesquad(self) -> bool:
        resp = await self.client.delete("/hypesquad/online")
        return resp is not None and resp.status_code == 204

    # ══════════════════════════════════════════════════════════════════════
    #  BIO
    # ══════════════════════════════════════════════════════════════════════

    async def change_bio(self, bio: str) -> bool:
        resp = await self.client.patch(
            "/users/@me", json_data={"bio": bio}
        )
        return resp is not None and resp.status_code == 200

    # ══════════════════════════════════════════════════════════════════════
    #  DISPLAY NAME
    # ══════════════════════════════════════════════════════════════════════

    async def change_display_name(self, name: str) -> bool:
        resp = await self.client.patch(
            "/users/@me", json_data={"global_name": name}
        )
        return resp is not None and resp.status_code == 200

    # ══════════════════════════════════════════════════════════════════════
    #  AVATAR
    # ══════════════════════════════════════════════════════════════════════

    async def change_avatar(self, image_path: str) -> bool:
        path = Path(image_path)
        if not path.exists():
            console.print("[err]Файл не найден.[/]")
            return False
        data = path.read_bytes()
        ext = path.suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(ext, "image/png")
        b64 = base64.b64encode(data).decode()
        data_uri = f"data:{mime};base64,{b64}"
        resp = await self.client.patch(
            "/users/@me", json_data={"avatar": data_uri}
        )
        return resp is not None and resp.status_code == 200

    async def remove_avatar(self) -> bool:
        resp = await self.client.patch(
            "/users/@me", json_data={"avatar": None}
        )
        return resp is not None and resp.status_code == 200

    # ══════════════════════════════════════════════════════════════════════
    #  LOCALE / THEME / STATUS
    # ══════════════════════════════════════════════════════════════════════

    async def change_locale(self, locale: str) -> bool:
        resp = await self.client.patch(
            "/users/@me/settings", json_data={"locale": locale}
        )
        return resp is not None and resp.status_code == 200

    async def change_theme(self, theme: str) -> bool:
        resp = await self.client.patch(
            "/users/@me/settings", json_data={"theme": theme}
        )
        return resp is not None and resp.status_code == 200

    async def change_status(self, status: str) -> bool:
        resp = await self.client.patch(
            "/users/@me/settings", json_data={"status": status}
        )
        return resp is not None and resp.status_code == 200

    # ══════════════════════════════════════════════════════════════════════
    #  GUILDS — LEAVE / MASS LEAVE
    # ══════════════════════════════════════════════════════════════════════

    async def leave_guild(self, guild_id: str) -> bool:
        resp = await self.client.delete(f"/users/@me/guilds/{guild_id}")
        return resp is not None and resp.status_code == 204

    async def mass_leave_guilds(
        self, guild_ids: list[str]
    ) -> tuple[int, int]:
        left = 0
        failed = 0
        for gid in guild_ids:
            if await self.leave_guild(gid):
                left += 1
            else:
                failed += 1
            await asyncio.sleep(0.5)
        return left, failed

    # ══════════════════════════════════════════════════════════════════════
    #  DM — CLOSE
    # ══════════════════════════════════════════════════════════════════════

    async def close_dm(self, channel_id: str) -> bool:
        resp = await self.client.delete(f"/channels/{channel_id}")
        return resp is not None and resp.status_code == 200

    async def close_all_dms(self) -> int:
        dms = await self.get_dm_channels()
        closed = 0
        for dm in dms:
            if await self.close_dm(dm["id"]):
                closed += 1
            await asyncio.sleep(0.3)
        return closed

    # ══════════════════════════════════════════════════════════════════════
    #  BLOCK / UNBLOCK / FRIEND
    # ══════════════════════════════════════════════════════════════════════

    async def block_user(self, user_id: str) -> bool:
        resp = await self.client.put(
            f"/users/@me/relationships/{user_id}",
            json_data={"type": 2},
        )
        return resp is not None and resp.status_code == 204

    async def unblock_user(self, user_id: str) -> bool:
        resp = await self.client.delete(
            f"/users/@me/relationships/{user_id}"
        )
        return resp is not None and resp.status_code == 204

    async def remove_friend(self, user_id: str) -> bool:
        resp = await self.client.delete(
            f"/users/@me/relationships/{user_id}"
        )
        return resp is not None and resp.status_code == 204

    async def send_friend_request(self, username: str) -> bool:
        resp = await self.client.post(
            "/users/@me/relationships",
            json_data={"username": username},
        )
        return resp is not None and resp.status_code == 204

    async def mass_unfriend(self) -> tuple[int, int]:
        rels = await self.get_relationships()
        friends = [r for r in rels if r.get("type") == 1]
        removed = 0
        failed = 0
        for fr in friends:
            if await self.remove_friend(fr["id"]):
                removed += 1
            else:
                failed += 1
            await asyncio.sleep(0.5)
        return removed, failed

    # ══════════════════════════════════════════════════════════════════════
    #  PENDING REQUESTS
    # ══════════════════════════════════════════════════════════════════════

    async def get_pending_requests(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rels = await self.get_relationships()
        incoming = [r for r in rels if r.get("type") == 3]
        outgoing = [r for r in rels if r.get("type") == 4]
        return incoming, outgoing

    async def accept_friend_request(self, user_id: str) -> bool:
        resp = await self.client.put(
            f"/users/@me/relationships/{user_id}",
            json_data={"type": 1},
        )
        return resp is not None and resp.status_code == 204

    # ══════════════════════════════════════════════════════════════════════
    #  EMOJIS — DOWNLOAD
    # ══════════════════════════════════════════════════════════════════════

    async def download_emojis(
        self, guild_id: str, output_dir: str
    ) -> int:
        resp = await self.client.get(f"/guilds/{guild_id}/emojis")
        if not resp or resp.status_code != 200:
            return 0

        emojis = resp.json()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        downloaded = 0

        for emoji in emojis:
            ext = "gif" if emoji.get("animated") else "png"
            url = f"https://cdn.discordapp.com/emojis/{emoji['id']}.{ext}"
            fname = f"{emoji.get('name', emoji['id'])}.{ext}"

            async with httpx.AsyncClient() as dl:
                try:
                    r = await dl.get(url)
                    if r.status_code == 200:
                        (out / fname).write_bytes(r.content)
                        downloaded += 1
                except httpx.HTTPError:
                    pass
            await asyncio.sleep(0.1)

        return downloaded

    # ══════════════════════════════════════════════════════════════════════
    #  CONNECTIONS
    # ══════════════════════════════════════════════════════════════════════

    async def get_connections(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/users/@me/connections")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  SESSIONS
    # ══════════════════════════════════════════════════════════════════════

    async def get_sessions(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/auth/sessions")
        if resp and resp.status_code == 200:
            return resp.json().get("user_sessions", [])
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  WEBHOOKS
    # ══════════════════════════════════════════════════════════════════════

    async def get_channel_webhooks(
        self, channel_id: str
    ) -> list[dict[str, Any]]:
        resp = await self.client.get(f"/channels/{channel_id}/webhooks")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  NICKNAME
    # ══════════════════════════════════════════════════════════════════════

    async def change_nickname(
        self, guild_id: str, nickname: str
    ) -> bool:
        resp = await self.client.patch(
            f"/guilds/{guild_id}/members/@me",
            json_data={"nick": nickname},
        )
        return resp is not None and resp.status_code in (200, 204)

    # ══════════════════════════════════════════════════════════════════════
    #  BOOSTS
    # ══════════════════════════════════════════════════════════════════════

    async def get_boosts(self) -> list[dict[str, Any]]:
        resp = await self.client.get(
            "/users/@me/guilds/premium/subscription-slots"
        )
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  SUBSCRIPTIONS
    # ══════════════════════════════════════════════════════════════════════

    async def get_subscriptions(self) -> list[dict[str, Any]]:
        resp = await self.client.get(
            "/users/@me/billing/subscriptions"
        )
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ══════════════════════════════════════════════════════════════════════
    #  SEND MESSAGE
    # ══════════════════════════════════════════════════════════════════════

    async def send_message(
        self, channel_id: str, content: str
    ) -> bool:
        resp = await self.client.post(
            f"/channels/{channel_id}/messages",
            json_data={"content": content},
        )
        return resp is not None and resp.status_code == 200

    # ══════════════════════════════════════════════════════════════════════
    #  REACTIONS — REMOVE MINE
    # ══════════════════════════════════════════════════════════════════════

    async def remove_my_reactions_in_channel(
        self, channel_id: str
    ) -> int:
        removed = 0
        last_id: str | None = None

        while True:
            params: dict[str, Any] = {"limit": 100}
            if last_id:
                params["before"] = last_id
            resp = await self.client.get(
                f"/channels/{channel_id}/messages", params=params
            )
            if not resp or resp.status_code != 200:
                break
            messages = resp.json()
            if not messages:
                break
            last_id = messages[-1]["id"]

            for msg in messages:
                for reaction in msg.get("reactions", []):
                    if not reaction.get("me"):
                        continue
                    emoji = reaction.get("emoji", {})
                    emoji_str = (
                        f"{emoji['name']}:{emoji['id']}"
                        if emoji.get("id")
                        else emoji.get("name", "?")
                    )
                    del_resp = await self.client.delete(
                        f"/channels/{channel_id}/messages/{msg['id']}"
                        f"/reactions/{emoji_str}/@me"
                    )
                    if del_resp and del_resp.status_code == 204:
                        removed += 1
                    await asyncio.sleep(0.3)

            if len(messages) < 100:
                break

        return removed


# ══════════════════════════════════════════════════════════════════════════════
#  TUI
# ══════════════════════════════════════════════════════════════════════════════

LOGO = r"""
 ╔══════════════════════════════════════════════════╗
 ║                                                  ║
 ║      ██████╗ ████████╗ ██████╗  ██████╗ ██╗      ║
 ║      ██╔══██╗╚══██╔══╝██╔═══██╗██╔═══██╗██║      ║
 ║      ██║  ██║   ██║   ██║   ██║██║   ██║██║      ║
 ║      ██║  ██║   ██║   ██║   ██║██║   ██║██║      ║
 ║      ██████╔╝   ██║   ╚██████╔╝╚██████╔╝███████╗ ║
 ║      ╚═════╝    ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝ ║
 ║                                                  ║
 ║           D I S C O R D   S E L F - T O O L      ║
 ║                                                  ║
 ╚══════════════════════════════════════════════════╝
"""

MENU_SECTIONS = [
    (
        "УДАЛЕНИЕ",
        [
            ("1", "Удалить сообщения везде"),
            ("2", "Удалить в конкретном канале / ЛС"),
            ("3", "Удалить на всех серверах"),
            ("4", "Удалить на конкретном сервере"),
            ("5", "Удалить свои реакции в канале"),
        ],
    ),
    (
        "ПАРСИНГ И ПОИСК",
        [
            ("6", "Парсинг участников по роли"),
            ("7", "Поиск сообщений на сервере"),
            ("8", "Lookup пользователя по ID"),
            ("9", "Общие серверы с пользователем"),
            ("10", "Общие друзья с пользователем"),
            ("11", "Информация об инвайте"),
        ],
    ),
    (
        "АККАУНТ",
        [
            ("12", "Полная информация об аккаунте"),
            ("13", "Сменить био / About Me"),
            ("14", "Сменить отображаемое имя"),
            ("15", "Сменить аватар / Удалить аватар"),
            ("16", "Сменить HypeSquad House"),
            ("17", "Сменить статус (online/idle/dnd/invisible)"),
            ("18", "Установить кастомный статус"),
            ("19", "Сменить язык Discord"),
            ("20", "Сменить тему (dark/light)"),
            ("21", "Привязанные аккаунты (connections)"),
            ("22", "Активные сессии (устройства)"),
            ("23", "Nitro / Подписки"),
            ("24", "Серверные бусты"),
        ],
    ),
    (
        "СЕРВЕРЫ",
        [
            ("25", "Информация о сервере"),
            ("26", "Список всех серверов"),
            ("27", "Список ролей на сервере"),
            ("28", "Скачать все эмодзи с сервера"),
            ("29", "Экспорт канала в JSON"),
            ("30", "Сменить ник на сервере"),
            ("31", "Mass Leave серверов"),
        ],
    ),
    (
        "ДРУЗЬЯ",
        [
            ("32", "Список друзей"),
            ("33", "Входящие / исходящие запросы в друзья"),
            ("34", "Принять все входящие запросы"),
            ("35", "Заблокировать пользователя"),
            ("36", "Разблокировать пользователя"),
            ("37", "Отправить запрос в друзья"),
            ("38", "Mass Unfriend (удалить всех друзей)"),
        ],
    ),
    (
        "УТИЛИТЫ",
        [
            ("39", "Закрыть все ЛС"),
            ("40", "Отправить сообщение в канал"),
            ("41", "Вебхуки канала"),
        ],
    ),
    (
        "",
        [("0", "Выход")],
    ),
]


def draw_header(username: str) -> None:
    clear()
    console.print(Text(LOGO, style="bright_white"))
    console.print(
        Panel(
            f"[accent]Аккаунт:[/] {username}",
            border_style="bright_white",
            padding=(0, 2),
        )
    )


def draw_menu() -> None:
    for section_name, items in MENU_SECTIONS:
        if section_name:
            console.print(f"\n  [title]── {section_name} ──[/]")
        table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
        table.add_column(style="bright_white", width=5)
        table.add_column(style="white")
        for key, label in items:
            table.add_row(f"[{key}]", label)
        console.print(table)


async def select_guild(tool: SelfTool) -> tuple[str, str] | None:
    console.print("\n[accent]Загрузка серверов...[/]")
    guilds = await tool.get_guilds()
    if not guilds:
        console.print("[err]Серверы не найдены.[/]")
        return None

    table = Table(
        title="Серверы",
        show_lines=False,
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")

    for i, g in enumerate(guilds, 1):
        table.add_row(str(i), g["name"], g["id"])

    console.print(table)
    choice = IntPrompt.ask("[accent]Выбери номер сервера[/]", default=0)
    if choice < 1 or choice > len(guilds):
        console.print("[err]Неверный выбор.[/]")
        return None

    g = guilds[choice - 1]
    return g["id"], g["name"]


def pause() -> None:
    Prompt.ask("\n[dim]Enter для продолжения...[/]", default="")


# ══════════════════════════════════════════════════════════════════════════════
#  ОБРАБОТЧИКИ МЕНЮ
# ══════════════════════════════════════════════════════════════════════════════


async def handle_purge_everywhere(tool: SelfTool) -> None:
    console.print("\n[warn]Это удалит ВСЕ твои сообщения (ЛС + серверы).[/]")
    if not Confirm.ask("Продолжить?", default=False):
        return
    count = await tool.purge_everywhere()
    console.print(f"\n[ok]Удалено {count} сообщений.[/]")


async def handle_purge_channel(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала / ЛС[/]").strip()
    if not channel_id:
        return
    if not Confirm.ask(f"Удалить все сообщения в {channel_id}?", default=False):
        return
    count = await tool.purge_specific_channel(channel_id)
    console.print(f"\n[ok]Удалено {count} сообщений.[/]")


async def handle_purge_all_servers(tool: SelfTool) -> None:
    console.print("\n[warn]Удаление на всех серверах (без ЛС).[/]")
    if not Confirm.ask("Продолжить?", default=False):
        return
    count = await tool.purge_all_servers()
    console.print(f"\n[ok]Удалено {count} сообщений.[/]")


async def handle_purge_server(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    if not Confirm.ask(
        f"Удалить все сообщения на [{guild_name}]?", default=False
    ):
        return
    count = await tool.purge_specific_server(guild_id)
    console.print(f"\n[ok]Удалено {count} сообщений на {guild_name}.[/]")


async def handle_remove_reactions(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return
    console.print("[accent]Удаление реакций...[/]")
    count = await tool.remove_my_reactions_in_channel(channel_id)
    console.print(f"[ok]Удалено {count} реакций.[/]")


async def handle_parse_role(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    role_id = Prompt.ask("[accent]ID роли[/]").strip()
    if not role_id:
        return

    console.print(f"\n[accent]Парсинг участников с ролью {role_id}...[/]")
    members = await tool.parse_role_members(guild_id, role_id)

    if not members:
        console.print("[err]Участники не найдены.[/]")
        return

    table = Table(
        title=f"Участники с ролью ({len(members)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=6)
    table.add_column("ID", style="white")
    table.add_column("Username", style="dim")

    for i, m in enumerate(members, 1):
        table.add_row(
            str(i),
            m.get("id", "?"),
            m.get("username", m.get("global_name", "-")),
        )
    console.print(table)

    if Confirm.ask("[accent]Сохранить в файл?[/]", default=False):
        filename = f"role_{role_id}_members.txt"
        lines = [m.get("id", "?") for m in members]
        Path(filename).write_text("\n".join(lines), encoding="utf-8")
        console.print(f"[ok]Сохранено в {filename}[/]")


async def handle_search_messages(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    query = Prompt.ask("[accent]Поисковый запрос[/]").strip()
    if not query:
        return
    max_res = IntPrompt.ask("[accent]Макс. результатов[/]", default=25)

    console.print(f"\n[accent]Поиск [{query}] на {guild_name}...[/]")
    msgs = await tool.search_in_guild(guild_id, query, max_res)

    if not msgs:
        console.print("[dim]Ничего не найдено.[/]")
        return

    table = Table(
        title=f"Результаты ({len(msgs)})",
        border_style="bright_white",
        header_style="bold white",
        show_lines=True,
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Автор", style="white", width=16)
    table.add_column("Содержимое", style="dim", max_width=50)
    table.add_column("Дата", style="dim", width=20)

    for i, m in enumerate(msgs, 1):
        content = (m.get("content") or "")[:80]
        author = m.get("author", {}).get("username", "?")
        ts = m.get("timestamp", "")[:19]
        table.add_row(str(i), author, content, ts)

    console.print(table)


async def handle_user_lookup(tool: SelfTool) -> None:
    uid = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not uid:
        return
    console.print("[accent]Поиск...[/]")
    data = await tool.user_lookup(uid)
    if not data:
        console.print("[err]Пользователь не найден.[/]")
        return

    user = data.get("user", data.get("user_profile", {}))
    if "user" in user:
        user = user["user"]

    table = Table(
        title="Пользователь",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white")
    table.add_column("Значение", style="white")

    table.add_row("ID", user.get("id", "?"))
    table.add_row("Username", user.get("username", "?"))
    table.add_row("Display Name", user.get("global_name", "-"))
    table.add_row(
        "Аватар",
        f"https://cdn.discordapp.com/avatars/{user.get('id')}/{user.get('avatar')}.png"
        if user.get("avatar")
        else "-",
    )
    table.add_row(
        "Баннер",
        f"https://cdn.discordapp.com/banners/{user.get('id')}/{user.get('banner')}.png"
        if user.get("banner")
        else "-",
    )
    table.add_row("Бот", str(user.get("bot", False)))
    created = snowflake_time(int(user.get("id", "0")))
    table.add_row("Создан", created.strftime("%Y-%m-%d %H:%M UTC"))

    bio = data.get("user_profile", {}).get("bio", "")
    if bio:
        table.add_row("Bio", bio[:200])

    badges = data.get("badges", [])
    if badges:
        badge_names = [b.get("id", "?") for b in badges]
        table.add_row("Бейджи", ", ".join(badge_names))

    premium = data.get("premium_since")
    table.add_row("Nitro с", premium or "-")

    console.print(table)


async def handle_mutual_guilds(tool: SelfTool) -> None:
    uid = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not uid:
        return
    mutuals = await tool.mutual_guilds(uid)
    if not mutuals:
        console.print("[dim]Общих серверов не найдено.[/]")
        return
    table = Table(
        title=f"Общие серверы ({len(mutuals)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("ID", style="white")
    table.add_column("Nick", style="dim")

    for i, g in enumerate(mutuals, 1):
        table.add_row(str(i), g.get("id", "?"), g.get("nick") or "-")
    console.print(table)


async def handle_mutual_friends(tool: SelfTool) -> None:
    uid = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not uid:
        return
    mutuals = await tool.mutual_friends(uid)
    if not mutuals:
        console.print("[dim]Общих друзей не найдено.[/]")
        return
    table = Table(
        title=f"Общие друзья ({len(mutuals)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("ID", style="white")
    table.add_column("Username", style="dim")

    for i, fr in enumerate(mutuals, 1):
        u = fr.get("user", fr)
        table.add_row(str(i), u.get("id", "?"), u.get("username", "?"))
    console.print(table)


async def handle_invite_info(tool: SelfTool) -> None:
    code = Prompt.ask("[accent]Инвайт (код или ссылка)[/]").strip()
    if not code:
        return
    info = await tool.invite_info(code)
    if not info:
        console.print("[err]Инвайт не найден или истёк.[/]")
        return

    table = Table(
        title="Инвайт", border_style="bright_white", header_style="bold white"
    )
    table.add_column("Поле", style="bright_white")
    table.add_column("Значение", style="white")

    guild = info.get("guild", {})
    table.add_row("Код", info.get("code", "?"))
    table.add_row("Сервер", guild.get("name", "?"))
    table.add_row("ID сервера", guild.get("id", "?"))
    table.add_row("Участников", str(info.get("approximate_member_count", "?")))
    table.add_row("Онлайн", str(info.get("approximate_presence_count", "?")))
    table.add_row("Канал", info.get("channel", {}).get("name", "?"))

    inviter = info.get("inviter", {})
    if inviter:
        table.add_row(
            "Пригласил", f"{inviter.get('username', '?')} ({inviter.get('id', '?')})"
        )

    table.add_row("Истекает", info.get("expires_at") or "Никогда")
    table.add_row(
        "Верификация", str(guild.get("verification_level", "?"))
    )
    table.add_row("NSFW", str(guild.get("nsfw", False)))

    console.print(table)


async def handle_full_account_info(tool: SelfTool) -> None:
    console.print("[accent]Загрузка данных аккаунта...[/]")
    info = await tool.full_account_info()
    user = info["user"]
    profile = info["profile"]
    settings = info["settings"]

    table = Table(
        title="Аккаунт",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white", width=25)
    table.add_column("Значение", style="white")

    table.add_row("ID", user.get("id", "?"))
    table.add_row("Username", user.get("username", "?"))
    table.add_row("Display Name", user.get("global_name", "-"))
    table.add_row("Email", user.get("email", "скрыт"))
    table.add_row("Телефон", user.get("phone") or "-")
    table.add_row("Verified Email", str(user.get("verified", "?")))
    table.add_row("MFA Enabled", str(user.get("mfa_enabled", False)))
    table.add_row("Locale", settings.get("locale", user.get("locale", "?")))
    table.add_row(
        "Nitro Type",
        {0: "Нет", 1: "Classic", 2: "Nitro", 3: "Basic"}.get(
            user.get("premium_type", 0), "?"
        ),
    )
    table.add_row("NSFW Allowed", str(user.get("nsfw_allowed", "?")))

    bio = profile.get("user_profile", {}).get("bio", "")
    table.add_row("Bio", (bio[:100] + "...") if len(bio) > 100 else (bio or "-"))

    created = snowflake_time(int(user.get("id", "0")))
    table.add_row("Аккаунт создан", created.strftime("%Y-%m-%d %H:%M UTC"))

    flags = user.get("flags", 0)
    public_flags = user.get("public_flags", 0)
    table.add_row("Flags", str(flags))
    table.add_row("Public Flags", str(public_flags))

    table.add_row("Has Billing", str(info["has_billing"]))
    table.add_row("Theme", settings.get("theme", "?"))
    table.add_row("Status", settings.get("status", "?"))
    table.add_row(
        "Developer Mode", str(settings.get("developer_mode", "?"))
    )

    avatar = user.get("avatar")
    if avatar:
        ext = "gif" if avatar.startswith("a_") else "png"
        table.add_row(
            "Avatar URL",
            f"https://cdn.discordapp.com/avatars/{user['id']}/{avatar}.{ext}",
        )

    banner = user.get("banner")
    if banner:
        ext = "gif" if banner.startswith("a_") else "png"
        table.add_row(
            "Banner URL",
            f"https://cdn.discordapp.com/banners/{user['id']}/{banner}.{ext}",
        )

    console.print(table)


async def handle_change_bio(tool: SelfTool) -> None:
    bio = Prompt.ask("[accent]Новый bio (пусто = очистить)[/]", default="")
    ok = await tool.change_bio(bio)
    console.print("[ok]Bio обновлён.[/]" if ok else "[err]Ошибка.[/]")


async def handle_change_display_name(tool: SelfTool) -> None:
    name = Prompt.ask("[accent]Новое отображаемое имя[/]").strip()
    if not name:
        return
    ok = await tool.change_display_name(name)
    console.print("[ok]Имя обновлено.[/]" if ok else "[err]Ошибка.[/]")


async def handle_change_avatar(tool: SelfTool) -> None:
    console.print("  [dim]1[/] Сменить аватар (файл)")
    console.print("  [dim]2[/] Удалить аватар")
    choice = Prompt.ask("[accent]Выбор[/]", default="1").strip()
    if choice == "1":
        path = Prompt.ask("[accent]Путь к файлу (png/jpg/gif)[/]").strip()
        if not path:
            return
        ok = await tool.change_avatar(path)
        console.print("[ok]Аватар обновлён.[/]" if ok else "[err]Ошибка.[/]")
    elif choice == "2":
        ok = await tool.remove_avatar()
        console.print("[ok]Аватар удалён.[/]" if ok else "[err]Ошибка.[/]")


async def handle_hypesquad(tool: SelfTool) -> None:
    console.print("  [dim]1[/] Bravery")
    console.print("  [dim]2[/] Brilliance")
    console.print("  [dim]3[/] Balance")
    console.print("  [dim]0[/] Покинуть HypeSquad")
    choice = Prompt.ask("[accent]Выбор[/]").strip()
    if choice == "0":
        ok = await tool.leave_hypesquad()
        console.print(
            "[ok]HypeSquad покинут.[/]" if ok else "[err]Ошибка.[/]"
        )
    elif choice in HYPESQUAD_HOUSES:
        name, hid = HYPESQUAD_HOUSES[choice]
        ok = await tool.change_hypesquad(hid)
        console.print(
            f"[ok]HypeSquad: {name}[/]" if ok else "[err]Ошибка.[/]"
        )


async def handle_change_status(tool: SelfTool) -> None:
    console.print("  [dim]1[/] online")
    console.print("  [dim]2[/] idle")
    console.print("  [dim]3[/] dnd")
    console.print("  [dim]4[/] invisible")
    choices = {"1": "online", "2": "idle", "3": "dnd", "4": "invisible"}
    c = Prompt.ask("[accent]Выбор[/]").strip()
    status = choices.get(c)
    if not status:
        return
    ok = await tool.change_status(status)
    console.print(f"[ok]Статус: {status}[/]" if ok else "[err]Ошибка.[/]")


async def handle_custom_status(tool: SelfTool) -> None:
    text = Prompt.ask("[accent]Текст статуса[/]").strip()
    emoji = Prompt.ask("[accent]Эмодзи (имя, пусто = без)[/]", default="")
    ok = await tool.set_custom_status(text, emoji)
    console.print(
        f'[ok]Статус: "{text}"[/]' if ok else "[err]Ошибка.[/]"
    )


async def handle_change_locale(tool: SelfTool) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bright_white", width=8)
    table.add_column(style="white")
    for code, name in LOCALE_MAP.items():
        table.add_row(code, name)
    console.print(table)
    locale = Prompt.ask("[accent]Код языка[/]").strip()
    if locale not in LOCALE_MAP:
        console.print("[err]Неизвестный код.[/]")
        return
    ok = await tool.change_locale(locale)
    console.print(
        f"[ok]Язык: {LOCALE_MAP[locale]}[/]" if ok else "[err]Ошибка.[/]"
    )


async def handle_change_theme(tool: SelfTool) -> None:
    console.print("  [dim]1[/] dark")
    console.print("  [dim]2[/] light")
    c = Prompt.ask("[accent]Выбор[/]").strip()
    theme = {"1": "dark", "2": "light"}.get(c)
    if not theme:
        return
    ok = await tool.change_theme(theme)
    console.print(f"[ok]Тема: {theme}[/]" if ok else "[err]Ошибка.[/]")


async def handle_connections(tool: SelfTool) -> None:
    conns = await tool.get_connections()
    if not conns:
        console.print("[dim]Нет привязанных аккаунтов.[/]")
        return
    table = Table(
        title="Привязанные аккаунты",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Сервис", style="bright_white")
    table.add_column("Имя", style="white")
    table.add_column("Видимость", style="dim")
    table.add_column("Verified", style="dim")

    for c in conns:
        table.add_row(
            c.get("type", "?"),
            c.get("name", "?"),
            "Публичный" if c.get("visibility") else "Скрытый",
            str(c.get("verified", False)),
        )
    console.print(table)


async def handle_sessions(tool: SelfTool) -> None:
    sessions = await tool.get_sessions()
    if not sessions:
        console.print("[dim]Нет данных о сессиях.[/]")
        return
    table = Table(
        title="Активные сессии",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("ID Hash", style="bright_white", width=12)
    table.add_column("OS", style="white")
    table.add_column("Платформа", style="white")
    table.add_column("Клиент", style="dim")

    for s in sessions:
        ci = s.get("client_info", {})
        table.add_row(
            s.get("id_hash", "?")[:10],
            ci.get("os", "?"),
            ci.get("platform", "?"),
            ci.get("client", "?"),
        )
    console.print(table)


async def handle_subscriptions(tool: SelfTool) -> None:
    subs = await tool.get_subscriptions()
    if not subs:
        console.print("[dim]Нет активных подписок.[/]")
        return
    table = Table(
        title="Подписки",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("ID", style="bright_white")
    table.add_column("Тип", style="white")
    table.add_column("Статус", style="dim")
    table.add_column("Создан", style="dim")

    for s in subs:
        table.add_row(
            s.get("id", "?")[:12],
            str(s.get("type", "?")),
            s.get("status", "?"),
            str(s.get("created_at", "?"))[:19],
        )
    console.print(table)


async def handle_boosts(tool: SelfTool) -> None:
    boosts = await tool.get_boosts()
    if not boosts:
        console.print("[dim]Нет бустов.[/]")
        return
    table = Table(
        title="Серверные бусты",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Слот ID", style="bright_white")
    table.add_column("Guild ID", style="white")
    table.add_column("Cooldown до", style="dim")

    for b in boosts:
        table.add_row(
            str(b.get("id", "?"))[:12],
            str(b.get("premium_guild_subscription", {}).get("guild_id", "-")),
            str(b.get("cooldown_ends_at") or "-")[:19],
        )
    console.print(table)


async def handle_guild_info(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, _ = result
    info = await tool.guild_info(guild_id)
    if not info:
        console.print("[err]Не удалось получить информацию.[/]")
        return

    table = Table(
        title=info.get("name", "?"),
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white")
    table.add_column("Значение", style="white")

    table.add_row("ID", info.get("id", "?"))
    table.add_row("Владелец", info.get("owner_id", "?"))
    table.add_row(
        "Участников", str(info.get("approximate_member_count", "?"))
    )
    table.add_row(
        "Онлайн", str(info.get("approximate_presence_count", "?"))
    )
    table.add_row("Уровень буста", str(info.get("premium_tier", 0)))
    table.add_row("Бустов", str(info.get("premium_subscription_count", 0)))
    table.add_row("Верификация", str(info.get("verification_level", 0)))
    created = snowflake_time(int(info["id"]))
    table.add_row("Создан", created.strftime("%Y-%m-%d %H:%M UTC"))
    table.add_row("Ролей", str(len(info.get("roles", []))))
    table.add_row("Эмодзи", str(len(info.get("emojis", []))))
    table.add_row("Стикеров", str(len(info.get("stickers", []))))
    table.add_row("NSFW Level", str(info.get("nsfw_level", 0)))
    table.add_row(
        "Vanity URL",
        info.get("vanity_url_code") or "-",
    )
    table.add_row("Description", (info.get("description") or "-")[:100])
    table.add_row(
        "Features",
        ", ".join(info.get("features", [])[:10]) or "-",
    )

    console.print(table)


async def handle_guild_list(tool: SelfTool) -> None:
    guilds = await tool.get_guilds()
    if not guilds:
        console.print("[dim]Серверов нет.[/]")
        return

    table = Table(
        title=f"Все серверы ({len(guilds)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white", max_width=30)
    table.add_column("ID", style="dim")
    table.add_column("Владелец?", style="dim", width=10)
    table.add_column("Permissions", style="dim", width=12)

    for i, g in enumerate(guilds, 1):
        is_owner = "Да" if g.get("owner") else "Нет"
        perms = g.get("permissions", "0")
        table.add_row(str(i), g["name"], g["id"], is_owner, str(perms))

    console.print(table)


async def handle_guild_roles(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    roles = await tool.get_guild_roles(guild_id)
    if not roles:
        console.print("[dim]Ролей нет.[/]")
        return

    roles.sort(key=lambda r: r.get("position", 0), reverse=True)

    table = Table(
        title=f"Роли на {guild_name} ({len(roles)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Позиция", style="bright_white", width=8)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")
    table.add_column("Цвет", style="dim", width=8)
    table.add_column("Участников", style="dim", width=10)

    for r in roles:
        color_hex = f"#{r.get('color', 0):06x}" if r.get("color") else "-"
        table.add_row(
            str(r.get("position", 0)),
            r.get("name", "?"),
            r.get("id", "?"),
            color_hex,
            str(r.get("member_count", "?")),
        )

    console.print(table)


async def handle_download_emojis(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    output = Prompt.ask(
        "[accent]Папка для эмодзи[/]",
        default=f"emojis_{guild_id}",
    )
    console.print(f"[accent]Скачивание эмодзи с {guild_name}...[/]")
    count = await tool.download_emojis(guild_id, output)
    console.print(f"[ok]Скачано {count} эмодзи в {output}/[/]")


async def handle_export_channel(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return
    output = Prompt.ask(
        "[accent]Имя файла[/]",
        default=f"export_{channel_id}.json",
    )
    console.print(f"[accent]Экспорт канала {channel_id}...[/]")
    count = await tool.export_channel(channel_id, output)
    console.print(f"[ok]Экспортировано {count} сообщений в {output}[/]")


async def handle_change_nickname(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    nick = Prompt.ask("[accent]Новый ник (пусто = сброс)[/]", default="")
    ok = await tool.change_nickname(guild_id, nick)
    console.print(
        f"[ok]Ник на {guild_name} обновлён.[/]" if ok else "[err]Ошибка.[/]"
    )


async def handle_mass_leave(tool: SelfTool) -> None:
    guilds = await tool.get_guilds()
    if not guilds:
        console.print("[dim]Серверов нет.[/]")
        return

    table = Table(
        show_lines=False, border_style="bright_white", header_style="bold white"
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")

    for i, g in enumerate(guilds, 1):
        table.add_row(str(i), g["name"], g["id"])
    console.print(table)

    selection = Prompt.ask(
        "[accent]Номера серверов через запятую (или 'all')[/]"
    ).strip()

    if selection.lower() == "all":
        ids = [g["id"] for g in guilds]
    else:
        try:
            indices = [int(x.strip()) for x in selection.split(",")]
            ids = [
                guilds[i - 1]["id"] for i in indices if 1 <= i <= len(guilds)
            ]
        except (ValueError, IndexError):
            console.print("[err]Неверный ввод.[/]")
            return

    if not Confirm.ask(f"Покинуть {len(ids)} серверов?", default=False):
        return

    left, failed = await tool.mass_leave_guilds(ids)
    console.print(f"[ok]Покинуто: {left}, ошибок: {failed}[/]")


async def handle_friend_list(tool: SelfTool) -> None:
    rels = await tool.get_relationships()
    friends = [r for r in rels if r.get("type") == 1]
    blocked = [r for r in rels if r.get("type") == 2]

    if not friends and not blocked:
        console.print("[dim]Список пуст.[/]")
        return

    if friends:
        table = Table(
            title=f"Друзья ({len(friends)})",
            border_style="bright_white",
            header_style="bold white",
        )
        table.add_column("#", style="bright_white", width=4)
        table.add_column("Username", style="white")
        table.add_column("Display Name", style="dim")
        table.add_column("ID", style="dim")

        for i, fr in enumerate(friends, 1):
            u = fr.get("user", {})
            table.add_row(
                str(i),
                u.get("username", "?"),
                u.get("global_name", "-"),
                u.get("id", "?"),
            )
        console.print(table)

    if blocked:
        console.print(f"\n[dim]Заблокировано: {len(blocked)}[/]")


async def handle_pending_requests(tool: SelfTool) -> None:
    incoming, outgoing = await tool.get_pending_requests()

    if incoming:
        table = Table(
            title=f"Входящие ({len(incoming)})",
            border_style="bright_white",
            header_style="bold white",
        )
        table.add_column("#", style="bright_white", width=4)
        table.add_column("Username", style="white")
        table.add_column("ID", style="dim")

        for i, r in enumerate(incoming, 1):
            u = r.get("user", {})
            table.add_row(str(i), u.get("username", "?"), u.get("id", "?"))
        console.print(table)
    else:
        console.print("[dim]Нет входящих запросов.[/]")

    if outgoing:
        table2 = Table(
            title=f"Исходящие ({len(outgoing)})",
            border_style="bright_white",
            header_style="bold white",
        )
        table2.add_column("#", style="bright_white", width=4)
        table2.add_column("Username", style="white")
        table2.add_column("ID", style="dim")

        for i, r in enumerate(outgoing, 1):
            u = r.get("user", {})
            table2.add_row(str(i), u.get("username", "?"), u.get("id", "?"))
        console.print(table2)
    else:
        console.print("[dim]Нет исходящих запросов.[/]")


async def handle_accept_all_requests(tool: SelfTool) -> None:
    incoming, _ = await tool.get_pending_requests()
    if not incoming:
        console.print("[dim]Нет входящих запросов.[/]")
        return

    if not Confirm.ask(
        f"Принять все {len(incoming)} запросов?", default=False
    ):
        return

    accepted = 0
    for r in incoming:
        if await tool.accept_friend_request(r["id"]):
            accepted += 1
        await asyncio.sleep(0.5)
    console.print(f"[ok]Принято: {accepted}[/]")


async def handle_block_user(tool: SelfTool) -> None:
    uid = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not uid:
        return
    ok = await tool.block_user(uid)
    console.print("[ok]Заблокирован.[/]" if ok else "[err]Ошибка.[/]")


async def handle_unblock_user(tool: SelfTool) -> None:
    uid = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not uid:
        return
    ok = await tool.unblock_user(uid)
    console.print("[ok]Разблокирован.[/]" if ok else "[err]Ошибка.[/]")


async def handle_send_friend_request(tool: SelfTool) -> None:
    username = Prompt.ask("[accent]Username[/]").strip()
    if not username:
        return
    ok = await tool.send_friend_request(username)
    console.print("[ok]Запрос отправлен.[/]" if ok else "[err]Ошибка.[/]")


async def handle_mass_unfriend(tool: SelfTool) -> None:
    console.print("[warn]Это удалит ВСЕХ друзей![/]")
    if not Confirm.ask("Продолжить?", default=False):
        return
    removed, failed = await tool.mass_unfriend()
    console.print(f"[ok]Удалено: {removed}, ошибок: {failed}[/]")


async def handle_close_all_dms(tool: SelfTool) -> None:
    console.print("[warn]Закроет все открытые ЛС.[/]")
    if not Confirm.ask("Продолжить?", default=False):
        return
    count = await tool.close_all_dms()
    console.print(f"[ok]Закрыто {count} ЛС.[/]")


async def handle_send_message(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return
    content = Prompt.ask("[accent]Текст сообщения[/]").strip()
    if not content:
        return
    ok = await tool.send_message(channel_id, content)
    console.print("[ok]Отправлено.[/]" if ok else "[err]Ошибка.[/]")


async def handle_channel_webhooks(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return
    webhooks = await tool.get_channel_webhooks(channel_id)
    if not webhooks:
        console.print("[dim]Вебхуков нет (или нет прав).[/]")
        return
    table = Table(
        title="Вебхуки",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Имя", style="white")
    table.add_column("ID", style="dim")
    table.add_column("Создатель", style="dim")
    table.add_column("URL", style="dim", max_width=40)

    for w in webhooks:
        creator = w.get("user", {}).get("username", "?")
        url = (
            f"https://discord.com/api/webhooks/{w['id']}/{w.get('token', '?')}"
            if w.get("token")
            else "-"
        )
        table.add_row(w.get("name", "?"), w.get("id", "?"), creator, url)
    console.print(table)


# ══════════════════════════════════════════════════════════════════════════════
#  ДИСПЕТЧЕР
# ══════════════════════════════════════════════════════════════════════════════

HANDLERS: dict[str, Any] = {
    "1": handle_purge_everywhere,
    "2": handle_purge_channel,
    "3": handle_purge_all_servers,
    "4": handle_purge_server,
    "5": handle_remove_reactions,
    "6": handle_parse_role,
    "7": handle_search_messages,
    "8": handle_user_lookup,
    "9": handle_mutual_guilds,
    "10": handle_mutual_friends,
    "11": handle_invite_info,
    "12": handle_full_account_info,
    "13": handle_change_bio,
    "14": handle_change_display_name,
    "15": handle_change_avatar,
    "16": handle_hypesquad,
    "17": handle_change_status,
    "18": handle_custom_status,
    "19": handle_change_locale,
    "20": handle_change_theme,
    "21": handle_connections,
    "22": handle_sessions,
    "23": handle_subscriptions,
    "24": handle_boosts,
    "25": handle_guild_info,
    "26": handle_guild_list,
    "27": handle_guild_roles,
    "28": handle_download_emojis,
    "29": handle_export_channel,
    "30": handle_change_nickname,
    "31": handle_mass_leave,
    "32": handle_friend_list,
    "33": handle_pending_requests,
    "34": handle_accept_all_requests,
    "35": handle_block_user,
    "36": handle_unblock_user,
    "37": handle_send_friend_request,
    "38": handle_mass_unfriend,
    "39": handle_close_all_dms,
    "40": handle_send_message,
    "41": handle_channel_webhooks,
}


async def menu_loop(tool: SelfTool) -> None:
    while True:
        draw_header(tool.username)
        draw_menu()

        choice = Prompt.ask("\n[accent]Выбери действие[/]").strip()

        if choice == "0":
            console.print("\n[dim]Пока![/]")
            break

        handler = HANDLERS.get(choice)
        if handler:
            try:
                await handler(tool)
            except KeyboardInterrupt:
                console.print("\n[warn]Прервано.[/]")
            except Exception as e:
                console.print(f"[err]Ошибка: {e}[/]")
            pause()
        else:
            console.print("[err]Неверный выбор.[/]")
            pause()


# ══════════════════════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════════════════════


async def main() -> None:
    clear()
    console.print(Text(LOGO, style="bright_white"))

    token = Prompt.ask("[accent]Вставь свой Discord токен[/]", password=True)
    if not token.strip():
        console.print("[err]Токен не может быть пустым![/]")
        sys.exit(1)

    console.print("\n[dim]Проверяю токен...[/]")
    client = DiscordClient(token.strip())
    tool = SelfTool(client)

    if not await tool.init():
        await client.close()
        sys.exit(1)

    console.print(f"[ok]Авторизован как {tool.username}[/]")
    await asyncio.sleep(1)

    try:
        await menu_loop(tool)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
