"""Интерактивные промпты и утилиты для UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from discord_tool.core.config import console

if TYPE_CHECKING:
    from discord_tool.services.tool import SelfTool


async def select_guild(tool: SelfTool) -> tuple[str, str] | None:
    """Выбрать сервер из списка."""
    guilds = await tool.get_guilds()
    if not guilds:
        console.print("[dim]Серверов нет.[/]")
        return None

    table = Table(
        title="Серверы",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")

    for i, g in enumerate(guilds, 1):
        table.add_row(str(i), g.get("name", "?"), g["id"])
    console.print(table)

    try:
        choice = IntPrompt.ask(
            "[accent]Номер сервера[/]", default=0
        )
    except (KeyboardInterrupt, EOFError):
        return None

    if choice < 1 or choice > len(guilds):
        console.print("[dim]Отмена.[/]")
        return None

    guild = guilds[choice - 1]
    return guild["id"], guild.get("name", "?")


def pause() -> None:
    """Пауза до нажатия Enter."""
    Prompt.ask("\n[dim]Enter для продолжения[/]", default="")
