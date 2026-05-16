"""SelfTool — основной сервисный класс."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import httpx
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from discord_tool.core.client import DiscordClient
from discord_tool.core.config import console


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

    # ═══════════════════════════════════════════════════════════════════
    #  ПОЛУЧЕНИЕ ДАННЫХ
    # ═══════════════════════════════════════════════════════════════════

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
                ch
                for ch in resp.json()
                if ch.get("type") in (0, 2, 5, 10, 11, 12, 15)
            ]
        return []

    async def get_guild_roles(self, guild_id: str) -> list[dict[str, Any]]:
        resp = await self.client.get(f"/guilds/{guild_id}/roles")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    # ═══════════════════════════════════════════════════════════════════
    #  ПОИСК СООБЩЕНИЙ
    # ═══════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════
    #  УДАЛЕНИЕ СООБЩЕНИЙ
    # ═══════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════
    #  ПАРСИНГ УЧАСТНИКОВ ПО РОЛИ (200+ поддержка)
    # ═══════════════════════════════════════════════════════════════════

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
                members.append({"id": str(mid)})
            return members

        console.print(
            "  [dim]role-members API недоступен, пагинация по участникам...[/]"
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

        if members:
            return members

        console.print("  [dim]Пробую members-search endpoint...[/]")
        last_user_id: str | None = None
        while True:
            payload: dict[str, Any] = {
                "or_query": {},
                "and_query": {"role_ids": {"or_query": [role_id]}},
                "limit": 1000,
            }
            if last_user_id:
                payload["after"] = {
                    "guild_id": guild_id,
                    "user_id": last_user_id,
                }

            resp = await self.client.post(
                f"/guilds/{guild_id}/members-search",
                json_data=payload,
            )
            if not resp or resp.status_code != 200:
                break
            data = resp.json()
            batch_items = data.get("members", [])
            if not batch_items:
                break

            for item in batch_items:
                member = item.get("member", {})
                user = member.get("user", {})
                uid = user.get("id", "?")
                members.append(
                    {
                        "id": uid,
                        "username": user.get("username", "?"),
                        "global_name": user.get("global_name"),
                    }
                )
                last_user_id = uid

            if len(batch_items) < 1000:
                break

        return members

    # ═══════════════════════════════════════════════════════════════════
    #  ПОИСК НА СЕРВЕРЕ
    # ═══════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════
    #  ЭКСПОРТ КАНАЛА
    # ═══════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════
    #  ИНФОРМАЦИЯ О СЕРВЕРЕ
    # ═══════════════════════════════════════════════════════════════════

    async def guild_info(self, guild_id: str) -> dict[str, Any] | None:
        resp = await self.client.get(f"/guilds/{guild_id}?with_counts=true")
        if resp and resp.status_code == 200:
            return resp.json()
        return None

    # ═══════════════════════════════════════════════════════════════════
    #  КАСТОМНЫЙ СТАТУС
    # ═══════════════════════════════════════════════════════════════════

    async def set_custom_status(self, text: str, emoji_name: str = "") -> bool:
        payload: dict[str, Any] = {"custom_status": {"text": text}}
        if emoji_name:
            payload["custom_status"]["emoji_name"] = emoji_name
        resp = await self.client.patch("/users/@me/settings", json_data=payload)
        return resp is not None and resp.status_code == 200

    # ═══════════════════════════════════════════════════════════════════
    #  ПОЛНАЯ ИНФОРМАЦИЯ ОБ АККАУНТЕ
    # ═══════════════════════════════════════════════════════════════════

    async def full_account_info(self) -> dict[str, Any]:
        resp = await self.client.get("/users/@me")
        user = resp.json() if resp and resp.status_code == 200 else {}
        prof_resp = await self.client.get(f"/users/{self.user_id}/profile")
        profile = (
            prof_resp.json() if prof_resp and prof_resp.status_code == 200 else {}
        )
        settings_resp = await self.client.get("/users/@me/settings")
        settings = (
            settings_resp.json()
            if settings_resp and settings_resp.status_code == 200
            else {}
        )
        billing_resp = await self.client.get("/users/@me/billing/payment-sources")
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

    # ═══════════════════════════════════════════════════════════════════
    #  RELATIONSHIPS
    # ═══════════════════════════════════════════════════════════════════

    async def get_relationships(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/users/@me/relationships")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    async def user_lookup(self, user_id: str) -> dict[str, Any] | None:
        resp = await self.client.get(f"/users/{user_id}/profile")
        if resp and resp.status_code == 200:
            return resp.json()
        resp2 = await self.client.get(f"/users/{user_id}")
        if resp2 and resp2.status_code == 200:
            return {"user": resp2.json()}
        return None

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

    # ═══════════════════════════════════════════════════════════════════
    #  АККАУНТ — ИЗМЕНЕНИЕ
    # ═══════════════════════════════════════════════════════════════════

    async def change_hypesquad(self, house_id: int) -> bool:
        resp = await self.client.post(
            "/hypesquad/online", json_data={"house_id": house_id}
        )
        return resp is not None and resp.status_code == 204

    async def leave_hypesquad(self) -> bool:
        resp = await self.client.delete("/hypesquad/online")
        return resp is not None and resp.status_code == 204

    async def change_bio(self, bio: str) -> bool:
        resp = await self.client.patch("/users/@me", json_data={"bio": bio})
        return resp is not None and resp.status_code == 200

    async def change_display_name(self, name: str) -> bool:
        resp = await self.client.patch("/users/@me", json_data={"global_name": name})
        return resp is not None and resp.status_code == 200

    async def change_avatar(self, file_path: str) -> bool:
        p = Path(file_path)
        if not p.exists():
            console.print(f"[err]Файл не найден: {file_path}[/]")
            return False
        data = p.read_bytes()
        ext = p.suffix.lower()
        if ext == ".gif":
            mime = "image/gif"
        elif ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        else:
            mime = "image/png"
        b64 = base64.b64encode(data).decode()
        avatar_data = f"data:{mime};base64,{b64}"
        resp = await self.client.patch(
            "/users/@me", json_data={"avatar": avatar_data}
        )
        return resp is not None and resp.status_code == 200

    async def remove_avatar(self) -> bool:
        resp = await self.client.patch("/users/@me", json_data={"avatar": None})
        return resp is not None and resp.status_code == 200

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

    # ═══════════════════════════════════════════════════════════════════
    #  СЕРВЕРЫ — ОПЕРАЦИИ
    # ═══════════════════════════════════════════════════════════════════

    async def leave_guild(self, guild_id: str) -> bool:
        resp = await self.client.delete(f"/users/@me/guilds/{guild_id}")
        return resp is not None and resp.status_code == 204

    async def mass_leave_guilds(self, guild_ids: list[str]) -> tuple[int, int]:
        left = 0
        failed = 0
        for gid in guild_ids:
            if await self.leave_guild(gid):
                left += 1
            else:
                failed += 1
            await asyncio.sleep(0.5)
        return left, failed

    async def change_nickname(self, guild_id: str, nickname: str) -> bool:
        resp = await self.client.patch(
            f"/guilds/{guild_id}/members/@me",
            json_data={"nick": nickname},
        )
        return resp is not None and resp.status_code in (200, 204)

    async def download_emojis(self, guild_id: str, output_dir: str) -> int:
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

    # ═══════════════════════════════════════════════════════════════════
    #  DM — CLOSE
    # ═══════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════
    #  ДРУЗЬЯ
    # ═══════════════════════════════════════════════════════════════════

    async def block_user(self, user_id: str) -> bool:
        resp = await self.client.put(
            f"/users/@me/relationships/{user_id}",
            json_data={"type": 2},
        )
        return resp is not None and resp.status_code == 204

    async def unblock_user(self, user_id: str) -> bool:
        resp = await self.client.delete(f"/users/@me/relationships/{user_id}")
        return resp is not None and resp.status_code == 204

    async def remove_friend(self, user_id: str) -> bool:
        resp = await self.client.delete(f"/users/@me/relationships/{user_id}")
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

    # ═══════════════════════════════════════════════════════════════════
    #  УТИЛИТЫ
    # ═══════════════════════════════════════════════════════════════════

    async def get_connections(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/users/@me/connections")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    async def get_sessions(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/auth/sessions")
        if resp and resp.status_code == 200:
            return resp.json().get("user_sessions", [])
        return []

    async def get_channel_webhooks(
        self, channel_id: str
    ) -> list[dict[str, Any]]:
        resp = await self.client.get(f"/channels/{channel_id}/webhooks")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    async def get_boosts(self) -> list[dict[str, Any]]:
        resp = await self.client.get(
            "/users/@me/guilds/premium/subscription-slots"
        )
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    async def get_subscriptions(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/users/@me/billing/subscriptions")
        if resp and resp.status_code == 200:
            return resp.json()
        return []

    async def send_message(self, channel_id: str, content: str) -> bool:
        resp = await self.client.post(
            f"/channels/{channel_id}/messages",
            json_data={"content": content},
        )
        return resp is not None and resp.status_code == 200

    async def remove_my_reactions_in_channel(self, channel_id: str) -> int:
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
