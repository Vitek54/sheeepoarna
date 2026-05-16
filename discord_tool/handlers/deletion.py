"""Обработчики удаления сообщений."""

from __future__ import annotations

from rich.prompt import Confirm, Prompt

from discord_tool.core.config import console
from discord_tool.services.tool import SelfTool
from discord_tool.ui.prompts import select_guild


async def handle_purge_everywhere(tool: SelfTool) -> None:
    console.print("[warn]Удаление ВСЕХ сообщений во ВСЕХ чатах и серверах![/]")
    if not Confirm.ask("[accent]Продолжить?[/]", default=False):
        return
    total = await tool.purge_everywhere()
    console.print(f"\n[ok]Удалено: {total} сообщений[/]")


async def handle_purge_channel(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала/ЛС[/]").strip()
    if not channel_id:
        return
    total = await tool.purge_specific_channel(channel_id)
    console.print(f"\n[ok]Удалено: {total} сообщений[/]")


async def handle_purge_all_servers(tool: SelfTool) -> None:
    console.print("[warn]Удаление сообщений на ВСЕХ серверах![/]")
    if not Confirm.ask("[accent]Продолжить?[/]", default=False):
        return
    total = await tool.purge_all_servers()
    console.print(f"\n[ok]Удалено: {total} сообщений[/]")


async def handle_purge_server(tool: SelfTool) -> None:
    result = await select_guild(tool)
    if not result:
        return
    guild_id, guild_name = result
    console.print(f"[accent]Удаление на сервере {guild_name}...[/]")
    total = await tool.purge_specific_server(guild_id)
    console.print(f"\n[ok]Удалено: {total} сообщений[/]")


async def handle_remove_reactions(tool: SelfTool) -> None:
    channel_id = Prompt.ask("[accent]ID канала[/]").strip()
    if not channel_id:
        return
    console.print("[accent]Удаление реакций...[/]")
    removed = await tool.remove_my_reactions_in_channel(channel_id)
    console.print(f"[ok]Удалено реакций: {removed}[/]")
