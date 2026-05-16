#!/usr/bin/env python3
"""
Discord Self-Tool — минималистичная чёрно-белая утилита для управления аккаунтом.

Функции:
  • Удаление сообщений (везде / канал / все серверы / конкретный сервер)
  • Парсинг участников по роли
  • Поиск сообщений по ключевому слову
  • Информация об аккаунте
  • Клон канала (экспорт сообщений в JSON)
"""

from __future__ import annotations

import asyncio
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
from rich.prompt import IntPrompt, Prompt
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

# ── Утилиты ──────────────────────────────────────────────────────────────────


def snowflake_time(snowflake_id: int) -> datetime:
    ts = ((snowflake_id >> 22) + SNOWFLAKE_EPOCH) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


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
                        f"  [dim]⏳ Глобальный rate-limit, жду {wait:.1f}с...[/]"
                    )
                    await asyncio.sleep(wait)

            now = time.monotonic()
            if bucket.remaining <= 0 and bucket.reset_at > now:
                wait = bucket.reset_at - now + 0.25
                console.print(
                    f"  [dim]⏳ Rate-limit bucket, жду {wait:.1f}с...[/]"
                )
                await asyncio.sleep(wait)

            try:
                resp = await self._client.request(
                    method, path, json=json_data, params=params
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout):
                wait = min(2 ** attempt, 30)
                console.print(f"  [warn]⚠ Сетевая ошибка, повтор через {wait}с[/]")
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
                        f"  [warn]⚠ Глобальный 429, жду {retry_after:.1f}с "
                        f"(scope={scope})[/]"
                    )
                else:
                    console.print(
                        f"  [warn]⚠ 429, жду {retry_after:.1f}с "
                        f"(scope={scope})[/]"
                    )

                bucket.remaining = 0
                bucket.reset_at = time.monotonic() + retry_after
                await asyncio.sleep(retry_after + 0.5)
                continue

            if resp.status_code in (500, 502, 503, 504):
                wait = min(2 ** attempt, 30)
                console.print(
                    f"  [warn]⚠ Сервер {resp.status_code}, повтор через {wait}с[/]"
                )
                await asyncio.sleep(wait)
                continue

            return resp

        console.print(f"  [err]✗ Не удалось выполнить {method} {path} "
                      f"после {max_retries} попыток[/]")
        return None

    # ── Удобные методы ───────────────────────────────────────────────────

    async def get(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("GET", path, **kw)

    async def delete(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("DELETE", path, **kw)

    async def post(self, path: str, **kw: Any) -> httpx.Response | None:
        return await self.request("POST", path, **kw)


# ── Основная логика ──────────────────────────────────────────────────────────


class SelfTool:
    def __init__(self, client: DiscordClient) -> None:
        self.client = client
        self.user: dict[str, Any] = {}

    async def init(self) -> bool:
        resp = await self.client.get("/users/@me")
        if resp is None or resp.status_code != 200:
            console.print("[err]✗ Невалидный токен![/]")
            return False
        self.user = resp.json()
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

    # ── Получение каналов ────────────────────────────────────────────────

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

    # ── Поиск сообщений через search API ─────────────────────────────────

    async def search_messages(
        self,
        *,
        guild_id: str | None = None,
        channel_id: str | None = None,
        author_id: str | None = None,
        content: str | None = None,
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

        resp = await self.client.get(path, params=params)
        if not resp or resp.status_code != 200:
            return 0, []
        data = resp.json()
        total = data.get("total_results", 0)
        messages = [m[0] for m in data.get("messages", []) if m]
        return total, messages

    # ── Удаление сообщений ───────────────────────────────────────────────

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
                    pass  # уже удалено
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
        label = channel_name or channel_id

        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[accent]{task.description}[/]"),
            BarColumn(bar_width=30, style="white", complete_style="bright_white"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"🗑  {label}", total=None)

            while True:
                total, messages = await self.search_messages(
                    channel_id=channel_id, author_id=self.user_id
                )

                if total == 0 or not messages:
                    break

                if progress.tasks[task].total is None:
                    progress.update(task, total=total)

                for msg in messages:
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
        label = guild_name or guild_id

        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[accent]{task.description}[/]"),
            BarColumn(bar_width=30, style="white", complete_style="bright_white"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"🗑  {label}", total=None)

            while True:
                total, messages = await self.search_messages(
                    guild_id=guild_id, author_id=self.user_id
                )
                if total == 0 or not messages:
                    break

                if progress.tasks[task].total is None:
                    progress.update(task, total=total)

                for msg in messages:
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

    # ── Главные функции удаления ──────────────────────────────────────────

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

    # ── Парсинг участников по роли ───────────────────────────────────────

    async def parse_role_members(
        self, guild_id: str, role_id: str
    ) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []

        # Метод 1: /guilds/{id}/roles/{id}/member-ids (user-only endpoint)
        resp = await self.client.get(
            f"/guilds/{guild_id}/roles/{role_id}/member-ids"
        )
        if resp and resp.status_code == 200:
            member_ids = resp.json()
            console.print(
                f"  [ok]✓[/] Получено {len(member_ids)} ID через role-members API"
            )
            for mid in member_ids:
                members.append({"id": mid})
            return members

        # Метод 2: /guilds/{id}/members/search с фильтрацией
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
                # Если и это не работает — пробуем search
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
            # Метод 3: members-search (Elasticsearch endpoint)
            console.print(
                "  [dim]Пробую members-search endpoint...[/]"
            )
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

    # ── Поиск сообщений ──────────────────────────────────────────────────

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

    # ── Экспорт канала ───────────────────────────────────────────────────

    async def export_channel(
        self, channel_id: str, output_path: str
    ) -> int:
        all_messages: list[dict[str, Any]] = []
        last_id: str | None = None

        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[accent]{task.description}[/]"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("📥 Экспорт", total=None)

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

    # ── Информация о сервере ─────────────────────────────────────────────

    async def guild_info(self, guild_id: str) -> dict[str, Any] | None:
        resp = await self.client.get(f"/guilds/{guild_id}?with_counts=true")
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    # ── Статус / Server list ─────────────────────────────────────────────

    async def set_custom_status(self, text: str, emoji_name: str = "") -> bool:
        payload: dict[str, Any] = {
            "custom_status": {"text": text}
        }
        if emoji_name:
            payload["custom_status"]["emoji_name"] = emoji_name
        resp = await self.client.request(
            "PATCH", "/users/@me/settings", json_data=payload
        )
        return resp is not None and resp.status_code == 200


# ── TUI Меню ─────────────────────────────────────────────────────────────────


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

MENU_ITEMS = [
    ("1", "Удалить сообщения везде"),
    ("2", "Удалить в конкретном канале / ЛС"),
    ("3", "Удалить на всех серверах"),
    ("4", "Удалить на конкретном сервере"),
    ("5", "Парсинг участников по роли"),
    ("6", "Поиск сообщений на сервере"),
    ("7", "Экспорт канала в JSON"),
    ("8", "Информация о сервере"),
    ("9", "Установить кастомный статус"),
    ("0", "Выход"),
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
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 3),
        expand=False,
    )
    table.add_column(style="bright_white", width=4)
    table.add_column(style="white")

    for key, label in MENU_ITEMS:
        table.add_row(f"[{key}]", label)

    console.print(
        Panel(table, title="[title]МЕНЮ[/]", border_style="bright_white", padding=1)
    )


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
    choice = IntPrompt.ask(
        "[accent]Выбери номер сервера[/]", default=0
    )
    if choice < 1 or choice > len(guilds):
        console.print("[err]Неверный выбор.[/]")
        return None

    g = guilds[choice - 1]
    return g["id"], g["name"]


async def menu_loop(tool: SelfTool) -> None:
    while True:
        draw_header(tool.username)
        draw_menu()

        choice = Prompt.ask("[accent]Выбери действие[/]").strip()

        # ── 1: Удалить везде ─────────────────────────────────────────────
        if choice == "1":
            console.print(
                "\n[warn]⚠ Это удалит ВСЕ твои сообщения (ЛС + серверы).[/]"
            )
            confirm = Prompt.ask("Продолжить? (y/n)", default="n")
            if confirm.lower() != "y":
                continue
            count = await tool.purge_everywhere()
            console.print(f"\n[ok]✓ Удалено {count} сообщений.[/]")

        # ── 2: Удалить в канале ──────────────────────────────────────────
        elif choice == "2":
            channel_id = Prompt.ask("[accent]Введи ID канала / ЛС[/]").strip()
            if not channel_id:
                continue
            console.print(
                f"\n[warn]⚠ Удаление всех твоих сообщений в канале {channel_id}[/]"
            )
            confirm = Prompt.ask("Продолжить? (y/n)", default="n")
            if confirm.lower() != "y":
                continue
            count = await tool.purge_specific_channel(channel_id)
            console.print(f"\n[ok]✓ Удалено {count} сообщений.[/]")

        # ── 3: Удалить на всех серверах ──────────────────────────────────
        elif choice == "3":
            console.print(
                "\n[warn]⚠ Удаление всех сообщений на всех серверах (без ЛС).[/]"
            )
            confirm = Prompt.ask("Продолжить? (y/n)", default="n")
            if confirm.lower() != "y":
                continue
            count = await tool.purge_all_servers()
            console.print(f"\n[ok]✓ Удалено {count} сообщений.[/]")

        # ── 4: Удалить на конкретном сервере ─────────────────────────────
        elif choice == "4":
            result = await select_guild(tool)
            if not result:
                continue
            guild_id, guild_name = result
            console.print(
                f"\n[warn]⚠ Удаление всех сообщений на сервере «{guild_name}»[/]"
            )
            confirm = Prompt.ask("Продолжить? (y/n)", default="n")
            if confirm.lower() != "y":
                continue
            count = await tool.purge_specific_server(guild_id)
            console.print(f"\n[ok]✓ Удалено {count} сообщений на {guild_name}.[/]")

        # ── 5: Парсинг по роли ───────────────────────────────────────────
        elif choice == "5":
            result = await select_guild(tool)
            if not result:
                continue
            guild_id, guild_name = result
            role_id = Prompt.ask("[accent]Введи ID роли[/]").strip()
            if not role_id:
                continue

            console.print(f"\n[accent]Парсинг участников с ролью {role_id}...[/]")
            members = await tool.parse_role_members(guild_id, role_id)

            if not members:
                console.print("[err]Участники не найдены.[/]")
            else:
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

                save = Prompt.ask(
                    "[accent]Сохранить в файл? (y/n)[/]", default="n"
                )
                if save.lower() == "y":
                    filename = f"role_{role_id}_members.txt"
                    lines = [m.get("id", "?") for m in members]
                    Path(filename).write_text("\n".join(lines), encoding="utf-8")
                    console.print(f"[ok]✓ Сохранено в {filename}[/]")

        # ── 6: Поиск сообщений ───────────────────────────────────────────
        elif choice == "6":
            result = await select_guild(tool)
            if not result:
                continue
            guild_id, guild_name = result
            query = Prompt.ask("[accent]Поисковый запрос[/]").strip()
            if not query:
                continue
            max_res = IntPrompt.ask(
                "[accent]Макс. кол-во результатов[/]", default=25
            )

            console.print(f"\n[accent]Поиск «{query}» на {guild_name}...[/]")
            msgs = await tool.search_in_guild(guild_id, query, max_res)

            if not msgs:
                console.print("[dim]Ничего не найдено.[/]")
            else:
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

        # ── 7: Экспорт канала ────────────────────────────────────────────
        elif choice == "7":
            channel_id = Prompt.ask("[accent]Введи ID канала[/]").strip()
            if not channel_id:
                continue
            output = Prompt.ask(
                "[accent]Имя файла[/]",
                default=f"export_{channel_id}.json",
            )
            console.print(f"\n[accent]Экспорт канала {channel_id}...[/]")
            count = await tool.export_channel(channel_id, output)
            console.print(f"[ok]✓ Экспортировано {count} сообщений в {output}[/]")

        # ── 8: Инфо о сервере ────────────────────────────────────────────
        elif choice == "8":
            result = await select_guild(tool)
            if not result:
                continue
            guild_id, _ = result
            info = await tool.guild_info(guild_id)
            if not info:
                console.print("[err]Не удалось получить информацию.[/]")
                continue

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
                "Участников (примерно)",
                str(info.get("approximate_member_count", "?")),
            )
            table.add_row(
                "Онлайн (примерно)",
                str(info.get("approximate_presence_count", "?")),
            )
            table.add_row("Уровень буста", str(info.get("premium_tier", 0)))
            table.add_row("Бустов", str(info.get("premium_subscription_count", 0)))
            table.add_row(
                "Верификация",
                str(info.get("verification_level", 0)),
            )
            created = snowflake_time(int(info["id"]))
            table.add_row("Создан", created.strftime("%Y-%m-%d %H:%M UTC"))

            roles = info.get("roles", [])
            table.add_row("Ролей", str(len(roles)))
            emojis = info.get("emojis", [])
            table.add_row("Эмодзи", str(len(emojis)))

            console.print(table)

        # ── 9: Кастомный статус ──────────────────────────────────────────
        elif choice == "9":
            text = Prompt.ask("[accent]Текст статуса[/]").strip()
            emoji = Prompt.ask("[accent]Эмодзи (имя, пусто = без)[/]", default="")
            ok = await tool.set_custom_status(text, emoji)
            if ok:
                console.print(f'[ok]✓ Статус установлен: "{text}"[/]')
            else:
                console.print("[err]✗ Не удалось установить статус.[/]")

        # ── 0: Выход ─────────────────────────────────────────────────────
        elif choice == "0":
            console.print("\n[dim]Пока! 👋[/]")
            break

        else:
            console.print("[err]Неверный выбор.[/]")

        Prompt.ask("\n[dim]Enter для продолжения...[/]", default="")


# ── Точка входа ──────────────────────────────────────────────────────────────


async def main() -> None:
    clear()
    console.print(Text(LOGO, style="bright_white"))

    token = Prompt.ask(
        "[accent]Вставь свой Discord токен[/]", password=True
    )
    if not token.strip():
        console.print("[err]Токен не может быть пустым![/]")
        sys.exit(1)

    console.print("\n[dim]Проверяю токен...[/]")
    client = DiscordClient(token.strip())
    tool = SelfTool(client)

    if not await tool.init():
        await client.close()
        sys.exit(1)

    console.print(f"[ok]✓ Авторизован как {tool.username}[/]")
    await asyncio.sleep(1)

    try:
        await menu_loop(tool)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
