"""Главный цикл приложения."""

from __future__ import annotations

from rich.prompt import Prompt

from discord_tool.core.client import DiscordClient
from discord_tool.core.config import console
from discord_tool.core.utils import clear
from discord_tool.handlers import HANDLERS
from discord_tool.services.tool import SelfTool
from discord_tool.ui.components import draw_header, draw_menu
from discord_tool.ui.prompts import pause


async def menu_loop(tool: SelfTool) -> None:
    while True:
        clear()
        draw_header(tool.username)
        draw_menu()

        try:
            choice = Prompt.ask("[accent]Выбор[/]").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "0":
            break

        handler = HANDLERS.get(choice)
        if not handler:
            console.print("[dim]Неверный выбор.[/]")
            pause()
            continue

        try:
            await handler(tool)
        except KeyboardInterrupt:
            console.print("\n[dim]Прервано.[/]")
        except Exception as exc:
            console.print(f"[err]Ошибка: {exc}[/]")

        pause()


async def main() -> None:
    clear()
    console.print("[title]Discord Self-Tool v2.0[/]\n")

    token = Prompt.ask("[accent]Токен[/]", password=True).strip()
    if not token:
        console.print("[err]Токен не указан![/]")
        return

    client = DiscordClient(token=token)
    tool = SelfTool(client)

    console.print("[dim]Проверка токена...[/]")
    if not await tool.init():
        await client.close()
        return

    console.print(f"[ok]Авторизован: {tool.username}[/]\n")

    try:
        await menu_loop(tool)
    finally:
        await client.close()
        console.print("[dim]До свидания![/]")
