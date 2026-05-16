"""Обработчики утилит."""

from __future__ import annotations

from rich.prompt import Confirm, Prompt
from rich.table import Table

from discord_tool.core.config import console
from discord_tool.services.tool import SelfTool


async def handle_close_all_dms(tool: SelfTool) -> None:
    console.print("[warn]Закрыть ВСЕ ЛС?[/]")
    if not Confirm.ask("[accent]Продолжить?[/]", default=False):
        return
    closed = await tool.close_all_dms()
    console.print(f"[ok]Закрыто: {closed} ЛС[/]")


async def handle_send_message(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return
    content = Prompt.ask("[accent]Сообщение[/]").strip()
    if not content:
        return
    if await tool.send_message(channel_id, content):
        console.print("[ok]Отправлено![/]")
    else:
        console.print("[err]Ошибка отправки.[/]")


async def handle_webhooks(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return

    webhooks = await tool.get_channel_webhooks(channel_id)
    if not webhooks:
        console.print("[dim]Вебхуков нет (или нет доступа).[/]")
        return

    table = Table(
        title=f"Вебхуки ({len(webhooks)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Имя", style="white")
    table.add_column("ID", style="dim")
    table.add_column("URL", style="dim", max_width=50)

    for i, wh in enumerate(webhooks, 1):
        url = f"https://discord.com/api/webhooks/{wh['id']}/{wh.get('token', '?')}"
        table.add_row(str(i), wh.get("name", "?"), wh["id"], url)

    console.print(table)
