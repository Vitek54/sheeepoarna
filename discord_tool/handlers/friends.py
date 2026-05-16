"""Обработчики управления друзьями."""

from __future__ import annotations

from rich.prompt import Confirm, Prompt
from rich.table import Table

from discord_tool.core.config import console
from discord_tool.services.tool import SelfTool


async def handle_friend_list(tool: SelfTool) -> None:
    rels = await tool.get_relationships()
    friends = [r for r in rels if r.get("type") == 1]

    if not friends:
        console.print("[dim]Друзей нет.[/]")
        return

    table = Table(
        title=f"Друзья ({len(friends)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Username", style="white")
    table.add_column("Display Name", style="dim")
    table.add_column("ID", style="dim")

    for i, f in enumerate(friends, 1):
        user = f.get("user", {})
        table.add_row(
            str(i),
            user.get("username", "?"),
            user.get("global_name", "-"),
            f.get("id", "?"),
        )

    console.print(table)


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
            user = r.get("user", {})
            table.add_row(str(i), user.get("username", "?"), r.get("id", "?"))
        console.print(table)
    else:
        console.print("[dim]Входящих запросов нет.[/]")

    if outgoing:
        table = Table(
            title=f"Исходящие ({len(outgoing)})",
            border_style="bright_white",
            header_style="bold white",
        )
        table.add_column("#", style="bright_white", width=4)
        table.add_column("Username", style="white")
        table.add_column("ID", style="dim")

        for i, r in enumerate(outgoing, 1):
            user = r.get("user", {})
            table.add_row(str(i), user.get("username", "?"), r.get("id", "?"))
        console.print(table)
    else:
        console.print("[dim]Исходящих запросов нет.[/]")


async def handle_accept_all(tool: SelfTool) -> None:
    incoming, _ = await tool.get_pending_requests()
    if not incoming:
        console.print("[dim]Входящих запросов нет.[/]")
        return

    console.print(f"[accent]Принять {len(incoming)} запросов?[/]")
    if not Confirm.ask("[accent]Продолжить?[/]", default=False):
        return

    accepted = 0
    for r in incoming:
        if await tool.accept_friend_request(r["id"]):
            accepted += 1
    console.print(f"[ok]Принято: {accepted}[/]")


async def handle_block(tool: SelfTool) -> None:
    user_id = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not user_id:
        return
    if await tool.block_user(user_id):
        console.print(f"[ok]Заблокирован: {user_id}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_unblock(tool: SelfTool) -> None:
    user_id = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not user_id:
        return
    if await tool.unblock_user(user_id):
        console.print(f"[ok]Разблокирован: {user_id}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_send_request(tool: SelfTool) -> None:
    username = Prompt.ask("[accent]Username[/]").strip()
    if not username:
        return
    if await tool.send_friend_request(username):
        console.print(f"[ok]Запрос отправлен: {username}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_mass_unfriend(tool: SelfTool) -> None:
    rels = await tool.get_relationships()
    friends = [r for r in rels if r.get("type") == 1]

    if not friends:
        console.print("[dim]Друзей нет.[/]")
        return

    console.print(f"[warn]Удалить ВСЕХ {len(friends)} друзей?[/]")
    if not Confirm.ask("[accent]Продолжить?[/]", default=False):
        return

    removed, failed = await tool.mass_unfriend()
    console.print(f"[ok]Удалено: {removed}[/]  [err]Ошибок: {failed}[/]")
