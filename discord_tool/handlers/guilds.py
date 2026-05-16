"""Обработчики серверных операций."""

from __future__ import annotations

from rich.prompt import Confirm, Prompt
from rich.table import Table

from discord_tool.core.config import console
from discord_tool.core.utils import format_permissions, snowflake_time
from discord_tool.services.tool import SelfTool
from discord_tool.ui.prompts import select_guild


async def handle_guild_info(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, _ = result

    info = await tool.guild_info(guild_id)
    if not info:
        console.print("[dim]Не удалось получить информацию.[/]")
        return

    table = Table(
        title=info.get("name", "?"),
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white", width=22)
    table.add_column("Значение", style="white")

    table.add_row("ID", info.get("id", "?"))
    table.add_row("Владелец", info.get("owner_id", "?"))
    table.add_row("Участников", str(info.get("approximate_member_count", "?")))
    table.add_row("Онлайн", str(info.get("approximate_presence_count", "?")))
    table.add_row("Бусты", str(info.get("premium_subscription_count", 0)))
    table.add_row("Уровень буста", str(info.get("premium_tier", 0)))
    table.add_row("Верификация", str(info.get("verification_level", 0)))

    try:
        created = snowflake_time(int(info.get("id", "0")))
        table.add_row("Создан", created.strftime("%Y-%m-%d %H:%M UTC"))
    except (ValueError, OSError):
        pass

    features = info.get("features", [])
    if features:
        table.add_row("Features", ", ".join(features[:10]))

    console.print(table)


async def handle_guild_list(tool: SelfTool) -> None:
    guilds = await tool.get_guilds()
    if not guilds:
        console.print("[dim]Серверов нет.[/]")
        return

    table = Table(
        title=f"Серверы ({len(guilds)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")
    table.add_column("Владелец", style="dim", width=8)

    for i, g in enumerate(guilds, 1):
        is_owner = "Да" if g.get("owner") else "Нет"
        table.add_row(str(i), g.get("name", "?"), g["id"], is_owner)

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

    table = Table(
        title=f"Роли {guild_name} ({len(roles)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")
    table.add_column("Цвет", style="dim", width=8)
    table.add_column("Позиция", style="dim", width=4)

    for i, r in enumerate(roles, 1):
        color = f"#{r.get('color', 0):06x}" if r.get("color") else "-"
        table.add_row(
            str(i),
            r.get("name", "?"),
            r.get("id", "?"),
            color,
            str(r.get("position", 0)),
        )

    console.print(table)

    if Confirm.ask("[accent]Показать permissions роли?[/]", default=False):
        role_id = Prompt.ask("[accent]ID роли[/]").strip()
        for r in roles:
            if r.get("id") == role_id:
                perms = format_permissions(int(r.get("permissions", "0")))
                console.print(f"[accent]Permissions:[/] {', '.join(perms) or 'нет'}")
                break


async def handle_download_emojis(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result

    output_dir = f"emojis_{guild_id}"
    console.print(f"[accent]Скачивание эмодзи {guild_name}...[/]")
    count = await tool.download_emojis(guild_id, output_dir)
    console.print(f"[ok]Скачано: {count} эмодзи в {output_dir}/[/]")


async def handle_export_channel(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return

    output = f"export_{channel_id}.json"
    console.print("[accent]Экспорт...[/]")
    count = await tool.export_channel(channel_id, output)
    console.print(f"[ok]Экспортировано: {count} сообщений в {output}[/]")


async def handle_change_nickname(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result

    nick = Prompt.ask("[accent]Новый ник (пусто для сброса)[/]", default="")
    if await tool.change_nickname(guild_id, nick):
        console.print(f"[ok]Ник на {guild_name} обновлён![/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_mass_leave(tool: SelfTool) -> None:
    guilds = await tool.get_guilds()
    if not guilds:
        console.print("[dim]Серверов нет.[/]")
        return

    table = Table(
        title=f"Серверы ({len(guilds)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")

    for i, g in enumerate(guilds, 1):
        table.add_row(str(i), g.get("name", "?"), g["id"])
    console.print(table)

    console.print("[dim]Введите номера через запятую (например: 1,3,5) или 'all'[/]")
    selection = Prompt.ask("[accent]Выбор[/]").strip()

    if selection.lower() == "all":
        guild_ids = [g["id"] for g in guilds]
    else:
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(",")]
            guild_ids = [guilds[i]["id"] for i in indices if 0 <= i < len(guilds)]
        except (ValueError, IndexError):
            console.print("[dim]Неверный ввод.[/]")
            return

    if not guild_ids:
        return

    console.print(f"[warn]Покинуть {len(guild_ids)} серверов?[/]")
    if not Confirm.ask("[accent]Продолжить?[/]", default=False):
        return

    left, failed = await tool.mass_leave_guilds(guild_ids)
    console.print(f"[ok]Покинуто: {left}[/]  [err]Ошибок: {failed}[/]")
