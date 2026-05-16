"""Обработчики парсинга и поиска."""

from __future__ import annotations

from pathlib import Path

from rich.prompt import Confirm, Prompt
from rich.table import Table

from discord_tool.core.config import console
from discord_tool.core.utils import snowflake_time
from discord_tool.services.tool import SelfTool
from discord_tool.ui.prompts import select_guild


async def handle_parse_role(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result

    roles = await tool.get_guild_roles(guild_id)
    if not roles:
        console.print("[dim]Ролей нет.[/]")
        return

    table = Table(
        title=f"Роли на {guild_name}",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")

    for i, r in enumerate(roles, 1):
        table.add_row(str(i), r.get("name", "?"), r.get("id", "?"))
    console.print(table)

    role_id = Prompt.ask("[accent]ID роли[/]").strip()
    if not role_id:
        return

    console.print(f"\n[accent]Парсинг участников роли на {guild_name}...[/]")
    members = await tool.parse_role_members(guild_id, role_id)

    if not members:
        console.print("[dim]Участников не найдено.[/]")
        return

    table = Table(
        title=f"Участники роли ({len(members)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=6)
    table.add_column("ID", style="white", width=22)
    table.add_column("Дата создания", style="dim", width=20)
    table.add_column("Пинг", style="bright_white", width=26)

    for i, m in enumerate(members, 1):
        uid = m.get("id", "?")
        try:
            created = snowflake_time(int(uid))
            date_str = created.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, OSError):
            date_str = "?"
        table.add_row(str(i), uid, date_str, f"<@{uid}>")

    console.print(table)
    console.print(f"\n[ok]Всего: {len(members)} участников[/]")

    if Confirm.ask("[accent]Сохранить в файл?[/]", default=True):
        filename = f"parsed_{guild_id}_{role_id}.txt"
        lines: list[str] = []
        for i, m in enumerate(members, 1):
            uid = m.get("id", "?")
            try:
                created = snowflake_time(int(uid))
                date_str = created.strftime("%Y-%m-%d %H:%M UTC")
            except (ValueError, OSError):
                date_str = "?"
            lines.append(f"{i}. ID: {uid} | Создан: {date_str} | Пинг: <@{uid}>")
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

    console.print(f"[accent]Поиск '{query}' на {guild_name}...[/]")
    messages = await tool.search_in_guild(guild_id, query)

    if not messages:
        console.print("[dim]Ничего не найдено.[/]")
        return

    table = Table(
        title=f"Результаты ({len(messages)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Автор", style="white", width=18)
    table.add_column("Канал", style="dim", width=12)
    table.add_column("Содержание", style="white", max_width=50)
    table.add_column("Дата", style="dim", width=12)

    for i, msg in enumerate(messages, 1):
        author = msg.get("author", {}).get("username", "?")
        content = (msg.get("content", "") or "")[:50]
        ts = msg.get("timestamp", "")[:10]
        ch = msg.get("channel_id", "?")
        table.add_row(str(i), author, ch, content, ts)

    console.print(table)


async def handle_user_lookup(tool: SelfTool) -> None:
    user_id = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not user_id:
        return

    data = await tool.user_lookup(user_id)
    if not data:
        console.print("[dim]Пользователь не найден.[/]")
        return

    user = data.get("user", {})
    table = Table(
        title="Пользователь",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white", width=20)
    table.add_column("Значение", style="white")

    table.add_row("ID", user.get("id", "?"))
    table.add_row("Username", user.get("username", "?"))
    table.add_row("Display Name", user.get("global_name", "-"))
    table.add_row("Бот", str(user.get("bot", False)))

    try:
        created = snowflake_time(int(user.get("id", "0")))
        table.add_row("Создан", created.strftime("%Y-%m-%d %H:%M UTC"))
    except (ValueError, OSError):
        pass

    bio = data.get("user_profile", {}).get("bio", "")
    if bio:
        table.add_row("Био", bio[:100])

    table.add_row("Пинг", f"<@{user.get('id', '?')}>")

    console.print(table)


async def handle_mutual_guilds(tool: SelfTool) -> None:
    user_id = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not user_id:
        return

    guilds = await tool.mutual_guilds(user_id)
    if not guilds:
        console.print("[dim]Общих серверов нет.[/]")
        return

    table = Table(
        title=f"Общие серверы ({len(guilds)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("ID", style="white")
    table.add_column("Ник", style="dim")

    for i, g in enumerate(guilds, 1):
        table.add_row(str(i), g.get("id", "?"), g.get("nick") or "-")

    console.print(table)


async def handle_mutual_friends(tool: SelfTool) -> None:
    user_id = Prompt.ask("[accent]ID пользователя[/]").strip()
    if not user_id:
        return

    friends = await tool.mutual_friends(user_id)
    if not friends:
        console.print("[dim]Общих друзей нет.[/]")
        return

    table = Table(
        title=f"Общие друзья ({len(friends)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("ID", style="white")
    table.add_column("Username", style="dim")

    for i, f in enumerate(friends, 1):
        table.add_row(
            str(i), f.get("id", "?"), f.get("username", "?")
        )

    console.print(table)


async def handle_invite_info(tool: SelfTool) -> None:
    code = Prompt.ask("[accent]Код инвайта (или URL)[/]").strip()
    if not code:
        return

    info = await tool.invite_info(code)
    if not info:
        console.print("[dim]Инвайт не найден.[/]")
        return

    guild = info.get("guild", {})
    table = Table(
        title="Инвайт",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white", width=20)
    table.add_column("Значение", style="white")

    table.add_row("Код", info.get("code", "?"))
    table.add_row("Сервер", guild.get("name", "?"))
    table.add_row("ID сервера", guild.get("id", "?"))
    table.add_row("Онлайн", str(info.get("approximate_presence_count", "?")))
    table.add_row("Участников", str(info.get("approximate_member_count", "?")))

    inviter = info.get("inviter", {})
    if inviter:
        table.add_row(
            "Пригласил",
            f"{inviter.get('username', '?')} ({inviter.get('id', '?')})",
        )

    expires = info.get("expires_at")
    table.add_row("Истекает", expires or "Никогда")

    console.print(table)
