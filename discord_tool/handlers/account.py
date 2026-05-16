"""Обработчики управления аккаунтом."""

from __future__ import annotations

from rich.prompt import Prompt
from rich.table import Table

from discord_tool.core.config import HYPESQUAD_HOUSES, LOCALE_MAP, console
from discord_tool.core.utils import snowflake_time
from discord_tool.services.tool import SelfTool


async def handle_full_account_info(tool: SelfTool) -> None:
    console.print("[accent]Загрузка информации...[/]")
    info = await tool.full_account_info()

    user = info["user"]
    profile = info["profile"]
    settings = info["settings"]

    table = Table(
        title="Аккаунт",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Поле", style="bright_white", width=22)
    table.add_column("Значение", style="white")

    table.add_row("ID", user.get("id", "?"))
    table.add_row("Username", user.get("username", "?"))
    table.add_row("Display Name", user.get("global_name", "-"))
    table.add_row("Email", user.get("email", "скрыт"))
    table.add_row("Телефон", user.get("phone") or "нет")
    table.add_row("MFA", str(user.get("mfa_enabled", False)))
    table.add_row("Verified", str(user.get("verified", False)))
    table.add_row("NSFW", str(user.get("nsfw_allowed", False)))

    try:
        created = snowflake_time(int(user.get("id", "0")))
        table.add_row("Создан", created.strftime("%Y-%m-%d %H:%M UTC"))
    except (ValueError, OSError):
        pass

    bio = profile.get("user_profile", {}).get("bio", "")
    table.add_row("Био", bio[:100] if bio else "-")

    flags = user.get("flags", 0)
    table.add_row("Flags", str(flags))
    table.add_row("Premium", str(user.get("premium_type", 0)))
    table.add_row("Язык", settings.get("locale", "?"))
    table.add_row("Тема", settings.get("theme", "?"))
    table.add_row("Статус", settings.get("status", "?"))
    table.add_row("Billing", "Да" if info["has_billing"] else "Нет")

    console.print(table)


async def handle_change_bio(tool: SelfTool) -> None:
    bio = Prompt.ask("[accent]Новый био (пусто для очистки)[/]", default="")
    if await tool.change_bio(bio):
        console.print("[ok]Био обновлено![/]")
    else:
        console.print("[err]Ошибка обновления био.[/]")


async def handle_change_display_name(tool: SelfTool) -> None:
    name = Prompt.ask("[accent]Новый display name[/]").strip()
    if not name:
        return
    if await tool.change_display_name(name):
        console.print("[ok]Display name обновлён![/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_change_avatar(tool: SelfTool) -> None:
    console.print("[dim]1 — Установить аватар\n2 — Удалить аватар[/]")
    choice = Prompt.ask("[accent]Выбор[/]", default="1").strip()

    if choice == "2":
        if await tool.remove_avatar():
            console.print("[ok]Аватар удалён![/]")
        else:
            console.print("[err]Ошибка.[/]")
        return

    path = Prompt.ask("[accent]Путь к файлу (png/jpg/gif)[/]").strip()
    if not path:
        return
    if await tool.change_avatar(path):
        console.print("[ok]Аватар обновлён![/]")
    else:
        console.print("[err]Ошибка обновления аватара.[/]")


async def handle_hypesquad(tool: SelfTool) -> None:
    console.print(
        "[dim]1 — Bravery\n2 — Brilliance\n3 — Balance\n0 — Покинуть[/]"
    )
    choice = Prompt.ask("[accent]Выбор[/]").strip()

    if choice == "0":
        if await tool.leave_hypesquad():
            console.print("[ok]Покинул HypeSquad.[/]")
        else:
            console.print("[err]Ошибка.[/]")
        return

    if choice not in HYPESQUAD_HOUSES:
        console.print("[dim]Неверный выбор.[/]")
        return

    name, house_id = HYPESQUAD_HOUSES[choice]
    if await tool.change_hypesquad(house_id):
        console.print(f"[ok]HypeSquad: {name}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_set_status(tool: SelfTool) -> None:
    console.print(
        "[dim]online / idle / dnd / invisible[/]"
    )
    status = Prompt.ask("[accent]Статус[/]").strip().lower()
    if status not in ("online", "idle", "dnd", "invisible"):
        console.print("[dim]Неверный статус.[/]")
        return
    if await tool.change_status(status):
        console.print(f"[ok]Статус: {status}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_custom_status(tool: SelfTool) -> None:
    text = Prompt.ask("[accent]Текст статуса[/]").strip()
    if not text:
        return
    emoji = Prompt.ask("[accent]Эмодзи (пусто для пропуска)[/]", default="").strip()
    if await tool.set_custom_status(text, emoji):
        console.print("[ok]Кастомный статус установлен![/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_change_locale(tool: SelfTool) -> None:
    table = Table(
        title="Языки",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("Код", style="bright_white", width=8)
    table.add_column("Язык", style="white")

    for code, name in LOCALE_MAP.items():
        table.add_row(code, name)
    console.print(table)

    locale = Prompt.ask("[accent]Код языка[/]").strip()
    if not locale:
        return
    if await tool.change_locale(locale):
        console.print(f"[ok]Язык: {locale}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_change_theme(tool: SelfTool) -> None:
    console.print("[dim]dark / light[/]")
    theme = Prompt.ask("[accent]Тема[/]").strip().lower()
    if theme not in ("dark", "light"):
        console.print("[dim]Неверная тема.[/]")
        return
    if await tool.change_theme(theme):
        console.print(f"[ok]Тема: {theme}[/]")
    else:
        console.print("[err]Ошибка.[/]")


async def handle_connections(tool: SelfTool) -> None:
    conns = await tool.get_connections()
    if not conns:
        console.print("[dim]Привязанных аккаунтов нет.[/]")
        return

    table = Table(
        title=f"Connections ({len(conns)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Тип", style="white", width=14)
    table.add_column("Имя", style="white")
    table.add_column("Видимый", style="dim", width=8)
    table.add_column("Verified", style="dim", width=8)

    for i, c in enumerate(conns, 1):
        table.add_row(
            str(i),
            c.get("type", "?"),
            c.get("name", "?"),
            "Да" if c.get("visibility") else "Нет",
            "Да" if c.get("verified") else "Нет",
        )

    console.print(table)


async def handle_active_sessions(tool: SelfTool) -> None:
    sessions = await tool.get_sessions()
    if not sessions:
        console.print("[dim]Активных сессий нет.[/]")
        return

    table = Table(
        title=f"Сессии ({len(sessions)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("OS", style="white", width=14)
    table.add_column("Клиент", style="white", width=14)
    table.add_column("Последняя активность", style="dim")

    for i, s in enumerate(sessions, 1):
        client_info = s.get("client_info", {})
        table.add_row(
            str(i),
            client_info.get("os", "?"),
            client_info.get("client", "?"),
            s.get("approx_last_used_time", "?")[:19],
        )

    console.print(table)


async def handle_subscriptions(tool: SelfTool) -> None:
    subs = await tool.get_subscriptions()
    if not subs:
        console.print("[dim]Подписок нет.[/]")
        return

    table = Table(
        title=f"Подписки ({len(subs)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("Тип", style="white")
    table.add_column("Статус", style="dim")
    table.add_column("Начало", style="dim")

    for i, sub in enumerate(subs, 1):
        table.add_row(
            str(i),
            str(sub.get("type", "?")),
            sub.get("status", "?"),
            sub.get("current_period_start", "?")[:10],
        )

    console.print(table)


async def handle_boosts(tool: SelfTool) -> None:
    boosts = await tool.get_boosts()
    if not boosts:
        console.print("[dim]Бустов нет.[/]")
        return

    table = Table(
        title=f"Бусты ({len(boosts)})",
        border_style="bright_white",
        header_style="bold white",
    )
    table.add_column("#", style="bright_white", width=4)
    table.add_column("ID", style="white")
    table.add_column("Guild ID", style="dim")
    table.add_column("Cooldown", style="dim")

    for i, b in enumerate(boosts, 1):
        premium = b.get("premium_guild_subscription", {})
        table.add_row(
            str(i),
            b.get("id", "?"),
            str(premium.get("guild_id", "-")),
            str(b.get("cooldown_ends_at", "-"))[:10],
        )

    console.print(table)
